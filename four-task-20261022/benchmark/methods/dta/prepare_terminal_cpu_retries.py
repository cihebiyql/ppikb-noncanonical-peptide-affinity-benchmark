"""Administrative only: reconcile eligible old bounded CPU failures to pending. Never launch science."""
import datetime as dt,hashlib,json,sys
from pathlib import Path
R=Path('/data/qlyu/projects/peptide-four-task-benchmark-20261022');H=R/'methods/dta'
sys.path.insert(0,str(R/'resources/continuation-20261023'))
import work_ownership_v2 as w
import work_retry_v1 as retry
def load(p):return json.loads(Path(p).read_text())
def main():
 rows=[]
 for j in load(H/'continuation-cpu-v2/jobs.json')['inherited_jobs']:
  k=[j['view_id'],j['method_id'],j['seed']];e=w.snapshot()['entries'][w.key(k)];row={'logical_key':k,'ledger_state':e['state'],'owner':e['owner']}
  if e['owner']=='node23-cpu' and e['state']=='failed':
   rp=Path(e['evidence']['receipt_path']);out=R/j['output_root']
   row['result']=retry.requeue_failed(k,'node23-cpu',e['claim_token'],rp,w.sha(rp),out,R/'protocol/continuation-20261023/user-authorization.json')
  rows.append(row)
 stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ');p=H/('terminal-cpu-retry-admission-'+stamp+'.json');p.write_text(json.dumps({'at':stamp,'administrative_only':True,'scientific_execution':False,'rows':rows},indent=2));print(json.dumps({'path':str(p),'states':[{'key':x['logical_key'],'state':x['ledger_state'],'requeued':x.get('result',{}).get('ok',False)} for x in rows]}))
if __name__=='__main__':main()
