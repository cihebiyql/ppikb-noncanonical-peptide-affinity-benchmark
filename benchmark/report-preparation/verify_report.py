"""Verify report arithmetic and metadata provenance without reading any gold."""
from pathlib import Path
import json,hashlib,datetime
P=Path(__file__).resolve().parent
def main():
 data=json.loads((P/'method-data-evidence.json').read_text(encoding='utf-8'));audit=json.loads((P/'report-read-audit.json').read_text(encoding='utf-8'))
 assert sum(r['rows'] for r in data['chemical_categories'])==9619
 assert sum(r['rows'] for r in data['raw_residue_class_counts'])==21845
 assert sum(r['rows'] for r in data['raw_parsed_endpoint_counts'])==21845
 assert sum(r['rows'] for r in data['chemical_categories'] if r['category']!='standard20_control')==2099
 assert len(data['predecessor_models'])==len({r['doi'] for r in data['predecessor_models']})==5
 assert len(data['training_specs_metadata'])==5
 for cohort,n in [('NC',2099),('standard20_control',7520)]:
  flow=[r for r in data['quality_filter_flow'] if r['cohort']==cohort]
  assert flow[-1]['retained']==n
  for i,r in enumerate(flow):
   assert r['before']-r['excluded_this_stage']==r['retained']
   if i:assert r['before']==flow[i-1]['retained']
 for r in data['split_regime_counts']:
  assert r['train']+r['validation']+r['test']==(2099 if r['regime']=='NC_only' else 7520)
  assert r['test']-r['test_sensitivity_excluded']==r['test_sensitivity_rows']
 assert data['performance_results_included'] is False and audit['gold_opened'] is False and audit['predictions_opened'] is False and audit['checkpoints_opened'] is False
 for entry in audit['opened_sources']:
  low=entry['path'].lower().replace('\\','/')
  assert not any(token in low for token in ['/gold/','posttraining-gold','/labels.jsonl','sealed-test-label','prediction','/best.pt','formal-runs-gpu-v4','encoded-cache-v3'])
  assert hashlib.sha256(Path(entry['path']).read_bytes()).hexdigest()==entry['sha256']
 assert len(data['source_evidence'])==len({r['evidence_id'] for r in data['source_evidence']})==28
 out={'verified_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'all_checks_passed':True,'cohort_rows':9619,'NC_rows':2099,'standard_rows':7520,'distinct_predecessor_papers':5,'evidence_cards':28,'metadata_sources_checked':len(audit['opened_sources']),'gold_or_predictions_or_checkpoints_read':False,'report_sha256':hashlib.sha256((P/'方法与数据说明.md').read_bytes()).hexdigest(),'files':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in P.iterdir() if p.is_file() and p.name!='verification.json'}}
 (P/'verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in out.items() if k!='files'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
