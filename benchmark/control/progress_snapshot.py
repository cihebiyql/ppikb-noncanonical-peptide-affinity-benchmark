"""Report real run receipts; do not read held-out labels or predictions."""
from pathlib import Path
from collections import Counter
import datetime as dt
import json

ROOT=Path(__file__).resolve().parent.parent
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def main():
    fits=ROOT/'formal-runs-gpu-v4/fits'
    completed=[];failed=[];selections=[]
    for p in fits.glob('*/candidate-*/complete.json'):
        d=load(p);completed.append(d)
    for p in fits.glob('*/candidate-*/failed.json'):failed.append(str(p.relative_to(ROOT)))
    for p in fits.glob('*/selection.json'):
        d=load(p);selections.append(d)
    methods=['GraphDTA-GIN','MGraphDTA','DGDTA-CL','DeepNC-GEN','GS-DTA']
    bymethod={m:dict(candidate_fits_complete=sum(r['method_id']==m for r in completed),units_selected=sum(r['method_id']==m for r in selections),expected_fits=80,expected_units=40) for m in methods}
    pools=[]
    for p in (ROOT/'launch').glob('pool-runs-*/progress.json'):
        d=load(p);pools.append(dict(path=str(p),status=d.get('status'),at=d.get('at'),active=d.get('active'),complete_count=d.get('complete_count'),failed_count=d.get('failed_count'),pending=d.get('pending')))
    snapshot=dict(project='PPIKB NC affinity five-prior-method benchmark',updated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        phase='training_and_validation_selection',methods=methods,NC_records=2099,standard_control_records=7520,
        panels=['source_peptide_dependency_cold','target_reference_homology_cold'],regimes=['NC_only','standard_only'],
        seeds=list(range(10)),hyperparameters=[{'learning_rate':.001,'weight_decay':0.},{'learning_rate':.0003,'weight_decay':0.}],
        candidate_fits_complete=len(completed),candidate_fits_expected=400,selected_units=len(selections),selected_units_expected=200,
        failed_candidate_records=failed,per_method=bymethod,pools=pools,
        all_selections_frozen=(ROOT/'formal-runs-gpu-v4/all-selections-frozen.json').exists(),
        test_scoring_started=any((ROOT/'formal-runs-gpu-v4').glob('scores/**/*predictions*')),
        raw_sources_preserved=True,novel_models=0,PepLand_excluded=True,
        external_prepared_records=dict(PTM_source_and_chemical_cold=75,PTM_primary=67,PTM_conditional_sensitivity=8,synthetic_D_backbone_supplementary_reference_view=8,standard_supplementary_reference_view=5),
        external_generalization_limit='PTM75 has2 reference-target-cold cases. Supplement13 uses related single heavy-chain reference for a whole2H2L antibody; no family-cold or actual construct claim.',
        hard_deadline='2026-10-22T01:45:00+00:00',full_training_completed=len(selections)==200)
    (ROOT/'STATUS.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:snapshot[k] for k in ['phase','candidate_fits_complete','selected_units','all_selections_frozen','test_scoring_started']}))

if __name__=='__main__':main()
