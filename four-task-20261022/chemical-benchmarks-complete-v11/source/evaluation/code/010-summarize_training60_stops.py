"""Summarize accepted expanded60 actual training stopping metadata; no fits."""
import argparse,csv,hashlib,json,runpy,statistics
from pathlib import Path
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--utility',required=True);ap.add_argument('--training-review',type=Path,required=True);ap.add_argument('--training-review-sha',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 u=runpy.run_path(a.utility);j,proc=u['guard']();assert sha(a.training_review)==a.training_review_sha;d=json.loads(a.training_review.read_text());assert d['status']=='passed' and not d['errors'] and d['exact_candidate_count']==60 and d['complete_mirrored']==60 and d['no_TEST']
 assert d['manifest_sha256']==u['COHORT'] and d['input_csv_sha256']==u['LABELS'];assert not a.output.exists();a.output.mkdir(parents=True)
 detail=[];summary=[]
 for q in d['candidates']:
  epoch=q['epochs'];stale=q['stale'];budget=epoch==30;patience=stale>=5;assert 1<=epoch<=30 and (budget or patience)
  reason='max_epoch30_and_patience5' if budget and patience else 'max_epoch30_budget_complete' if budget else 'patience5_early_stop'
  detail.append({k:q[k] for k in ['key','model','seed','candidate','epochs','best_epoch','global_steps','stale'] }|{'derived_stop_rule':reason,'max_epoch_budget_reached':budget,'patience_reached':patience,'convergence_established':False})
 for model in ['hybrid','mlm','2025']:
  rr=[q for q in detail if q['model']==model];assert len(rr)==20;ee=[q['epochs'] for q in rr];bb=[q['best_epoch'] for q in rr]
  summary.append({'model':model,'candidates':20,'epochs_min':min(ee),'epochs_max':max(ee),'epochs_mean':statistics.mean(ee),'epochs_sampleSD':statistics.stdev(ee),'best_epoch_min':min(bb),'best_epoch_max':max(bb),'best_epoch_mean':statistics.mean(bb),'best_epoch_sampleSD':statistics.stdev(bb),'patience5_before_budget':sum(q['derived_stop_rule']=='patience5_early_stop' for q in rr),'max30_budget_complete':sum(q['max_epoch_budget_reached'] for q in rr),'max30_and_patience5':sum(q['derived_stop_rule']=='max_epoch30_and_patience5' for q in rr)})
 names=['TRAINING-STOP-60-per-candidate.actual.csv','TRAINING-STOP-3-model-summary.actual.csv']
 for name,rr in zip(names,[detail,summary]):
  with (a.output/name).open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
 receipt={'schema':'expanded60.accepted-training-stop-summary.v1','status':'PASS','training_review_sha256':a.training_review_sha,'source_sha256':sha(__file__),'metric_file_hashes':{n:sha(a.output/n) for n in names},'summary':summary,'interpretation':'Derived from actual epochs/stale cursor and frozen max30/patience5. Budget completion is not evidence of convergence. No TEST-based budget changes.','NN':0,'fit':0,'process':proc};p=a.output/'TRAINING-STOP-SUMMARY.actual.json';p.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'receipt':str(p),'sha256':sha(p),'summary':summary}))
if __name__=='__main__':main()
