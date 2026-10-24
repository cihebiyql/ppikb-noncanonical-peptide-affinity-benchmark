"""Freeze common input coverage before any head fitting or evaluation selection."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path, PureWindowsPath
import time

import pandas as pd

from chemical_features import ChemicalFeatures, json_read, resolve, sha
from run_heads import read_views, write_json


def anchor_inherited_paths(value, original_base):
    """Keep original manifests immutable while preserving their relative-reference meaning."""
    if isinstance(value, list):
        return [anchor_inherited_paths(item, original_base) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if isinstance(item, str) and item and (key == 'path' or key.endswith('_path')):
            if '://' in item or item.startswith('record-ref:'):
                result[key] = item
            elif Path(item).is_absolute() or PureWindowsPath(item).is_absolute():
                result[key] = item
            else:
                result[key] = str((original_base / item).resolve())
        else:
            result[key] = anchor_inherited_paths(item, original_base)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--feature-spec', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-seconds', type=int, default=180)
    args = parser.parse_args()
    started = time.monotonic()
    manifest_path = args.manifest.resolve()
    manifest = json_read(manifest_path)
    views = read_views(manifest)
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError('Refuse to overwrite a prior frozen model cohort')
    args.output.mkdir(parents=True, exist_ok=True)
    representations = [(path.resolve(), ChemicalFeatures(path)) for path in args.feature_spec]
    if len({path for path, _ in representations}) != len(representations):
        raise ValueError('A feature specification cannot be supplied twice')
    output_views, coverage, exclusions = [], [], []
    for view in views:
        if view.get('status') not in ('ready','frozen','model_ready'):
            output_views.append(anchor_inherited_paths(view, manifest_path.parent))
            coverage.append({'view_id':view['id'],'status':'not_run',
                             'reason':view.get('reason',view.get('qualification','Global freeze view is blocked'))})
            continue
        path = resolve(view.get('path') or view['csv_path'], manifest_path.parent)
        if sha(path) != view['sha256']:
            raise ValueError('Global freeze input changed before model-cohort freeze')
        frame = pd.read_csv(path, keep_default_na=False, float_precision='round_trip')
        keep = []
        for index, row in enumerate(frame.to_dict('records')):
            if time.monotonic() - started >= args.max_seconds:
                raise TimeoutError('Input-coverage audit time budget exhausted before freeze')
            reasons = {str(path): encoder.coverage_reason(row, view.get('task','affinity'))
                       for path, encoder in representations}
            reasons = {key:value for key,value in reasons.items() if value is not None}
            if not reasons:
                keep.append(index)
            else:
                exclusions.append({'view_id': view['id'], 'row_id': row['row_id'],
                                   'split': row[view.get('split_column','split')],
                                   'evaluation_stratum': row.get('evaluation_stratum','unreported'),
                                   'reasons': json.dumps(reasons,ensure_ascii=False,sort_keys=True)})
        retained = frame.iloc[keep].copy()
        split_column = view.get('split_column','split')
        present = set(retained[split_column])
        if not {'validation','test'}.issubset(present) or not present.intersection({'fine_train','finetune_train','train'}):
            raise ValueError(f'Common chemical input coverage empties a required split: {view["id"]}')
        output = args.output / f"{view['id']}.csv"
        retained.to_csv(output,index=False,float_format='%.17g')
        updated = dict(view, path=str(output.resolve()), sha256=sha(output),
                       rows=len(retained), split_counts={str(k):int(v) for k,v in retained[split_column].value_counts().items()},
                       source_global_view_sha256=view['sha256'], status='frozen')
        output_views.append(updated)
        coverage.append({'view_id':view['id'],'original_rows':len(frame),'retained_rows':len(retained),
                         'excluded_rows':len(frame)-len(retained),'split_counts':updated['split_counts'],
                         'strata_by_split':{str(split):{str(k):int(v) for k,v in local.evaluation_stratum.value_counts().items()}
                                           for split,local in retained.groupby(split_column)} if 'evaluation_stratum' in retained else {}})
    if exclusions:
        pd.DataFrame(exclusions).to_csv(args.output/'input-only-exclusions.csv',index=False)
    else:
        pd.DataFrame(columns=['view_id','row_id','split','evaluation_stratum','reasons']).to_csv(args.output/'input-only-exclusions.csv',index=False)
    frozen = dict(anchor_inherited_paths(manifest, manifest_path.parent), views=output_views)
    frozen['inherited_metadata_scope'] = 'Anchored producer, input_manifest, outputs and summaries refer to the original global freeze; views/model_cohort describe the derived input coverage.'
    frozen['model_cohort'] = {
        'schema':'chemical-encoder.common-input-cohort.v1',
        'created_at':datetime.now(timezone.utc).isoformat(),
        'source_global_manifest_path':str(manifest_path),'source_global_manifest_sha256':sha(manifest_path),
        'feature_specifications':[{'path':str(path),'sha256':sha(path),'feature_audit':encoder.audit} for path,encoder in representations],
        'criterion':'intersection of complete source chemical input and declared frozen encoder/protein cache coverage',
        'labels_predictions_or_test_performance_used_for_filtering':False,
        'old_split_and_dependency_groups_preserved':True,
        'exclusions_path':str((args.output/'input-only-exclusions.csv').resolve()),
        'exclusions_sha256':sha(args.output/'input-only-exclusions.csv'),'coverage':coverage,
    }
    write_json(args.output/'frozen-manifest.json',frozen)
    print(json.dumps({'status':'frozen','views':coverage,'new_head_fits':0,'new_encoder_inference':0},ensure_ascii=False))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
