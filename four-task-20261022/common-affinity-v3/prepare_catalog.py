"""Freeze canonical683/946 and a complete method catalog; saved prediction bytes only."""
from collections import Counter
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
MODELS=['constant','linear','random_forest','extra_trees','hist_gradient_boosting']
DTA=['GraphDTA-GIN','MGraphDTA','DGDTA-CL','DeepNC-GEN','GS-DTA']
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def read(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def dump(path,obj):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def local(value):
    value=str(value)
    if value.startswith('record-ref:local/'):return Path('record-ref:local/'+value[len('record-ref:local/'):])
    prefix='record-ref:project/'
    if value.startswith(prefix):return ROOT/value[len(prefix):]
    path=Path(value);assert path.is_absolute();return path
def main():
    assert not (HERE/'comparison-contract.json').exists()
    canonical={};sources={};rows=[];gaps=[]
    root_generic=ROOT/'reports/delivery-20261023/generic-completed-metrics-all-panels.csv'
    assert sha(root_generic)=='60f29ff73f66845f580d4f13e0d9abc88717d30192b68c7765f6afadf7e1b447'
    sources[str(root_generic)]=sha(root_generic)
    for panel,n,expected in [('source',683,'c59382bf9298f4dddf9642c7a88d6e643184445d0276f585247d3335f116f8bc'),('target',946,'3d2700b207b0af4f57d80d9314ec03964ffcde7f567e84556e46232d1f746d0e')]:
        path=ROOT/f'methods/interaction/common-comparison-cohorts/pepinter_native6336_{panel}_test_ids.csv'
        assert sha(path)==expected;ref=read(path);assert len(ref)==n and len({r['row_id'] for r in ref})==n
        parent=ROOT/f'data/ppikb_kd_{panel}_cold_scope_v2.csv';parents={r['row_id']:r for r in read(parent)}
        assert all(parents[r['row_id']]['endpoint']=='pKd' and parents[r['row_id']]['split']=='test' and float(parents[r['row_id']]['label'])==float(r['label']) for r in ref)
        canonical[panel]={'path':str(path),'sha256':expected,'n':n,'row_ids':[r['row_id'] for r in ref],
            'parent_view':str(parent),'parent_sha256':sha(parent),'endpoint':'pKd',
            'label_float64_by_row_id':{r['row_id']:float(r['label']) for r in ref},
            'strata_by_row_id':{r['row_id']:r['evaluation_stratum'] for r in ref}}
        sources[str(path)]=expected;sources[str(parent)]=sha(parent)
        def add(method,family,seed,path,fmt='csv',expected_sha=None,source_scope=None,protocol_note=None):
            path=Path(path)
            if not path.exists():gaps.append({'panel':panel,'method':method,'seed':seed,'reason':'saved_prediction_file_missing','path':str(path)});return
            digest=sha(path)
            if expected_sha is not None:assert digest==expected_sha,str(path)
            rows.append({'panel':panel,'method':method,'family':family,'seed':seed,'path':str(path),'sha256':digest,'format':fmt,
                'canonical_n':n,'endpoint':'pKd','training_scope':source_scope,'protocol_note':protocol_note})
        for model in MODELS:
            for seed in range(10):
                for family,label in [('sequence','manual_sequence'),('morgan','chiral_Morgan')]:
                    path=ROOT/f'runs/common-prediction-comparison-v2/backbone6336__{panel}/{family}__{model}/seed-{seed:02d}/common-test-predictions.csv'
                    add(label+'__'+model,label,seed,path,source_scope='Original full9116-view training retained')
                path=ROOT/f'runs/plm-simple-v1/common-prediction-comparison/backbone6336__{panel}/esm2__{model}/seed-{seed:02d}/common-test-predictions.csv'
                add('frozen_ESM2_8M__'+model,'frozen_ESM2_8M',seed,path,source_scope='Literal20AA/2048 eligible7419 cohort; frozen8M mean pooling')
                path=ROOT/f'runs/plm-cohort-manual-controls-v1/ppikb_kd_{panel}_cold_scope_v2_esm2_raw20_len2048/{model}/seed-{seed:02d}/test-predictions.csv'
                add('manual_ESM_cohort__'+model,'manual_ESM_cohort',seed,path,source_scope='Exact same7419 train/validation/test ID cohort as frozenESM; original manual recipes retained')
        for seed in range(10):
            add('PepInter_backbone_native_head','PepInter_component',seed,
                ROOT/f'runs/common-prediction-comparison-v2/backbone6336__{panel}/PepInter_backbone_ablation_native_head/seed-{seed:02d}/common-test-predictions.csv',
                source_scope='Frozen supervised backbone; literal20AA6336 cohort, sequence chemically blind',
                protocol_note='Previously canonicalized originalCSVfloat64 labels; original workerfloat32 precision is disclosed in source audits, not claimed bit-equal to float64.')
            cached=ROOT/f'runs/common-prediction-comparison-v2/backbone6336__{panel}/PepInter_cached_native_head/seed-{seed:02d}/common-test-predictions.csv'
            if cached.exists():add('PepInter_cached_standard_only','coverage_only',seed,cached,source_scope='Standard2919 only; expected incomplete canonical coverage; never shrink683/946')
    dta_provenance=ROOT/'reports/dta-pepinter-common-fixed-v1/prediction-provenance.csv'
    sources[str(dta_provenance)]=sha(dta_provenance)
    for item in read(dta_provenance):
        panel=item['panel'];seed=int(item['seed']);path=local(item['test_predictions_path'])
        assert item['method'] in DTA and item['canonical_file_sha256']==canonical[panel]['sha256']
        assert path.exists() and sha(path)==item['test_predictions_sha256']
        rows.append({'panel':panel,'method':'DTA__'+item['method'],'family':'DTA_transfer','seed':seed,'path':str(path),
            'sha256':item['test_predictions_sha256'],'format':'jsonl','canonical_n':canonical[panel]['n'],'endpoint':'pKd',
            'training_scope':'Original full9116-view training; actual backend/input limits remain in final150 provenance',
            'protocol_note':'DGDTA-CL is the historical run identifier for the MSE paper model; not an extra contrastive model.'})
    for panel in ['source','target']:
        audit_path=ROOT/f'methods/interaction/continuation-20261023/swing-affinity/affinity-{panel}-independent-audit.latest.json'
        audit=load(audit_path);assert audit['all10_actual_and_verified'] and not audit['errors']
        assert audit['endpoint']=='experimental pKd absolute, extra chemical state omitted by sequence backbone encoder'
        sources[str(audit_path)]=sha(audit_path)
        for item in audit['results']:
            seed=item['seed'];remote=item['run']+f'/artifacts/seed_{seed}/test-predictions.csv';path=local(remote)
            if not path.exists() or sha(path)!=item['test_prediction_sha256']:
                assert re.fullmatch(r'record-ref:project/runs/interaction_continuation_swing_pKd_(source|target)_hash0_seed[0-9]+_(v2|memo_v3)/artifacts/seed_[0-9]+/test-predictions\.csv',remote)
                path=HERE/'saved-prediction-cache'/f'SWING-{panel}-seed{seed}.csv';path.parent.mkdir(parents=True,exist_ok=True)
                if not path.exists():subprocess.run(['scp','qlyu-node23:'+remote,str(path)],check=True,timeout=120)
                assert sha(path)==item['test_prediction_sha256']
            rows.append({'panel':panel,'method':'SWING_Doc2Vec_XGBRegressor','family':'SWING_endpoint_adaptation','seed':seed,
                'path':str(path),'original_remote_prediction_path':remote,'sha256':item['test_prediction_sha256'],'format':'csv',
                'canonical_n':canonical[panel]['n'],'endpoint':'pKd','training_scope':'Literal20AA7669; nativegrammar/Doc2Vec16train16infer/72D, train-only embedding; regression readout adaptation',
                'source_audit_endpoint_text':audit['endpoint'],
                'protocol_note':'Endpoint/readout adaptation and custom validation grid, not native-paper affinity task; no model object copied or loaded.'})
    assert len({(r['panel'],r['method'],r['seed']) for r in rows})==len(rows)
    expected=540;full=[r for r in rows if r['family']!='coverage_only'];assert len(full)==expected and not gaps
    extra_gaps=[{'condition':'ESM/same-cohort-manual silver-effect third view','reason':'delta_pKd_silver task; not the pKd canonical observation IDs'},
        {'condition':'UniAIR nativeRDE strictlocal component','reason':'One HER2 authorDDG context; endpoint and test IDs differ, no pKd common results'},
        {'condition':'oldGraphDTA source entry in common-v2','reason':'Duplicate logical model; use final accepted DTA provenance instead'}]
    contract={'schema':'common-affinity.fixed-canonical-comparison.v3','frozen_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'canonical':canonical,'prediction_sources':rows,'planned_full_coverage_applications':540,'planned_methods_per_panel':27,
        'source_locks':[{'path':p,'sha256':h} for p,h in sources.items()],
        'coverage_and_scope_only':extra_gaps,'eligibility_rule':'Every method-panel must have all seeds0..9, all fixed canonicalIDs, exact originalfloat64 labels andpKd endpoint; no new intersection or missing->zero.',
        'unavailable_sources':gaps,'no_test_based_method_or_subset_selection':True,
        'source_and_target_separate':True,'training_cohorts_not_equalized':True,'seed_SD_not_biological_CI':True,
        'paired_MAE_differences':'All unordered method pairs, samepanel/sameseed; no p-values or independent-experiment claim.',
        'new_fit_count':0,'new_forward_count':0,'model_objects_loaded':0,'gpu_jobs':0,'code_sha256':sha(__file__)}
    dump(HERE/'comparison-contract.json',contract)
    print({'full_applications':len(full),'coverage_only':len(rows)-len(full),'methods_per_panel':27,'small_missing_prediction_copies':len(list((HERE/'saved-prediction-cache').glob('*.csv'))) if (HERE/'saved-prediction-cache').exists() else 0})
if __name__=='__main__':main()
