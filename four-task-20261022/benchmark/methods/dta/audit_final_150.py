"""Once all150 are accepted, independently bind dataset identities, labels, metrics and candidate assets."""
from pathlib import Path
import collections,datetime as dt,hashlib,json
from audit_runs import independent_metrics
from export_complete_dta_report import complete_gate,local
from stopping_rules import validate_stopping
H=Path(__file__).resolve().parent;R=H.parents[1]
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def lines(p):return [json.loads(x) for x in Path(p).read_text(encoding='utf-8-sig').splitlines() if x.strip()]
def same_rows(actual,expected):
 assert len(actual)==len(expected)
 for a,b in zip(actual,expected):
  assert a['label']==float(b['label'])
  for key in ['record_id','row_id','source','group_id','target_id','stratum','evaluation_stratum','endpoint','split']:assert a.get(key)==b.get(key),(key,a.get(key),b.get(key))
def main():
 pointer=load(H/'accepted-census-current.json');accepted=load(local(pointer['path']));assert sha(local(pointer['path']))==pointer['sha256'];complete_gate(accepted['records'])
 dp=load(H/'accepted-details-current.json');assert sha(local(dp['path']))==dp['sha256'];details=load(local(dp['path']));assert details['source_accepted_census_sha256']==pointer['sha256'] and len(details['records'])==150
 records=[];errors=[];checks=0
 for row in details['records']:
  v,m,seed=row['view'],row['method'],row['seed'];unit=local(row['path']).parent;c=load(unit/'complete.json');selection=load(unit/'selection.json');scores=load(unit/'test-metrics.json');pred=lines(unit/'test-predictions.jsonl')
  assert sha(unit/'test-predictions.jsonl')==c['prediction_sha256']==row['prediction_sha256'];assert sha(unit/'selection.json')==c['selection_sha256']
  spec=load(H/'specs'/f'{v}--{m}--formal--seed{seed}.json');frozen={}
  for part in ['train','validation','test']:
   ref=spec['paths'][part];path=R/ref['path'];assert sha(path)==ref['sha256'];frozen[part]=lines(path);assert len(frozen[part])==ref['n']==c['sample_counts'][part]
  same_rows(pred,frozen['test']);assert scores['all']==c['metrics']
  candidates=[]
  for x in selection['candidates']:
   folder=unit/('candidate-'+str(x['candidate_index']));vp=lines(folder/'validation-predictions.jsonl');same_rows(vp,frozen['validation']);assert sha(folder/'best.pt')==x['checkpoint_sha256'] and sha(folder/'validation-predictions.jsonl')==x['validation_predictions_sha256']
   val=independent_metrics(vp,c['task']);assert abs(val['MAE']-x['best_validation_score'])<=1e-10
   epochs=lines(folder/'epochs.jsonl');assert all(e['train_n']==len(frozen['train']) for e in epochs);assert 1<=len(epochs)<=20
   assert x['best_epoch']==min(range(len(epochs)),key=lambda i:epochs[i]['validation']['MAE'])
   stopping=validate_stopping(epochs,x['best_epoch'],len(frozen['train']))
   candidates.append({'index':x['candidate_index'],'checkpoint_sha256':sha(folder/'best.pt'),'validation_predictions_sha256':sha(folder/'validation-predictions.jsonl'),**stopping})
  assert len(candidates)==2 and selection['winner']==min(selection['candidates'],key=lambda x:(x['best_validation_score'],x['candidate_index']))['candidate_index']
  groups={'all':{'all':pred},'strata':collections.defaultdict(list),'groups':collections.defaultdict(list)}
  for x in pred:groups['strata'][x.get('evaluation_stratum') or x.get('stratum') or 'unknown'].append(x);groups['groups'][x.get('group_id') or x.get('target_id') or 'unknown'].append(x)
  for level,buckets in groups.items():
   for name,data in buckets.items():
    actual=independent_metrics(data,c['task']);expected=scores['all'] if level=='all' else scores[level][name]
    for metric,value in actual.items():
     checks+=1;e=expected.get(metric)
     if (value is None)!=(e is None) or (value is not None and abs(value-e)>1e-10):errors.append({'key':[v,m,seed],'level':level,'group':name,'metric':metric,'saved':e,'actual':value})
  records.append({'logical_key':[v,m,seed],'unit_path':str(unit),'complete_sha256':sha(unit/'complete.json'),'test_metrics_sha256':sha(unit/'test-metrics.json'),'test_prediction_sha256':sha(unit/'test-predictions.jsonl'),'selection_sha256':sha(unit/'selection.json'),'test_and_validation_identity_and_labels_exact':True,'candidates':candidates})
 stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ');out=H/('final-all150-independent-audit-'+stamp+'.json');out.write_text(json.dumps({'at':stamp,'accepted_census_sha256':pointer['sha256'],'accepted_details_sha256':dp['sha256'],'units':records,'unit_count':len(records),'candidate_count':sum(len(x['candidates']) for x in records),'metric_checks':checks,'errors':errors,'scope':'All150 complete scientific assets and exact frozen test/validation labels; independent numerical recomputation, no fit or model forward'},indent=2));print(json.dumps({'path':str(out),'units':len(records),'candidates':sum(len(x['candidates']) for x in records),'metric_checks':checks,'errors':len(errors)}))
 if errors:raise SystemExit(2)
if __name__=='__main__':main()
