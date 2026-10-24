"""Report chemistry-specific external coverage without inventing missing molecules."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import pandas as pd

from chemical_features import ChemicalFeatures, json_read, resolve, sha
from run_heads import read_views, write_json


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--feature-spec',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    manifest_path=args.manifest.resolve()
    manifest=json_read(manifest_path)
    read_views(manifest)
    features=ChemicalFeatures(args.feature_spec)
    reports=[]
    for view in manifest.get('external_views',[]):
        path=resolve(view.get('path') or view['csv_path'],manifest_path.parent)
        if not view.get('sha256') or sha(path)!=view['sha256']:
            raise ValueError('External source CSV SHA mismatch')
        frame=pd.read_csv(path,keep_default_na=False,float_precision='round_trip')
        reasons=Counter()
        ids=[]
        for row in frame.to_dict('records'):
            reason=features.coverage_reason(row,view.get('task','affinity'))
            if reason:
                reasons[reason]+=1
            else:
                ids.append(row['row_id'])
        reports.append({'id':view['id'],'source_rows':len(frame),'input_eligible_rows':len(ids),
                        'eligible_ids':ids,'exclusion_reasons':dict(reasons),
                        'qualification':view.get('qualification',view.get('independence','unreported')),
                        'input_sha256':view['sha256']})
    write_json(args.output,{'schema':'chemical-encoder.external-coverage.v1',
               'manifest_sha256':sha(manifest_path),'feature_spec_sha256':sha(args.feature_spec),
               'views':reports,'molecules_synthesized_from_sequence':0,'new_fits':0,'new_predictions':0})
    print(json.dumps({'external_views':len(reports),'coverage':[{k:v for k,v in x.items() if k!='eligible_ids'} for x in reports]},ensure_ascii=False))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
