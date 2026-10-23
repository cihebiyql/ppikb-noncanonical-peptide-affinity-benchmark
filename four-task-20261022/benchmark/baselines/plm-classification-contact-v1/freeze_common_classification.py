"""Freeze pre-existing common test IDs before outcomes; do not shrink any ESM test view."""
import csv
import hashlib
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
SOURCE=ROOT/'methods/interaction/common-comparison-cohorts'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
manifest=json.loads((HERE/'coverage-manifest.json').read_text(encoding='utf-8'))
view=next(v for v in manifest['views'] if v['task']=='classification')
reference={r['row_id']:r for r in read(view['path']) if r['split']=='test'}
cohorts=[]
for name in ['classification-target-cold-native-common-test2349.csv','classification-target-cold-native-common-test-no-exact-affinitytrain2290.csv']:
    path=SOURCE/name;rows=read(path)
    missing=[r['row_id'] for r in rows if r['row_id'] not in reference]
    assert not missing
    for row in rows:
        ref=reference[row['row_id']]
        assert ref['split']==row['split']=='test'
        assert len(ref['embedding_peptide'])==int(row['peptide_length']) and len(ref['embedding_target'])==int(row['target_length'])
    cohorts.append({'name':path.stem,'path':str(path),'sha256':sha(path),'rows':len(rows),
        'row_ids':[r['row_id'] for r in rows],'missing_ESM_primary_test_ids':missing,
        'scope':'Common ID mask frozen by native method owner, not new external independent observations',
        'no_exact_affinitytrain_subset_is_not_general_unexposed_claim':'no-exact-affinitytrain' in name})
result={'schema':'frozen-esm2.classification-common-IDs.v1','primary_test_rows':len(reference),
    'primary_input_sha256':view['sha256'],'cohorts':cohorts,'frozen_before_ESM_classification_test_predictions':True,
    'existing_primary_test_not_shrunk':True,'threshold_policy':'Reuse full frozen validation-selected threshold; never tune common-subset test threshold',
    'training_and_pretraining_coverage_different_between_methods':True,
    'native_owner_manifest_sha256':sha(SOURCE/'classification-target-cold-native-common.manifest.json')}
target=HERE/'common-classification-cohorts.json';assert not target.exists();target.write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'primary_test':len(reference),'common_rows':[r['rows'] for r in cohorts],'all_IDs_covered':True}))
