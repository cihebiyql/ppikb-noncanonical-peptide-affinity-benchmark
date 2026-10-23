"""Read actual per-job terminal receipts and owned PID state, including cache phase."""
import json,datetime as dt,os
from pathlib import Path
R=Path('/data/qlyu/projects/peptide-four-task-benchmark-20261022');H=R/'methods/dta';records=[]
for phase in ['node23-cpu-v1','node23-cpu-recovery-v2','node23-cpu-recovery-v3','node23-cached-v5']:
 index=H/phase/'jobs.json'
 if not index.exists():continue
 for j in json.loads(index.read_text())['jobs']:
  if j['stage']!='formal':continue
  log=Path(j['run_dir']);out=R/j['output_root'];launch=log/'launch.json';rec=log/'process-receipt.json';complete=out/'complete.json';state='not_started';live=False
  if launch.exists():
   ld=json.loads(launch.read_text());proc=Path('/proc')/str(ld['pid'])
   try:
    cmd=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode();live=proc.stat().st_uid==os.getuid() and j['spec_path'] in cmd and (proc/'stat').read_text().split(')')[-1].split()[0]!='Z'
   except OSError:live=False
   state='active' if live else 'terminal_partial'
  rr=json.loads(rec.read_text()) if rec.exists() else None
  if complete.exists() and rr and rr['exit_code']==0:state='complete'
  cps=list(out.rglob('best.pt')) if out.exists() else []
  epochs=[]
  if out.exists():
   for f in out.glob('candidate-*/epochs.jsonl'):
    lines=f.read_text().splitlines();epochs.append({'candidate':f.parent.name,'complete_epochs':len(lines),'last_epoch':json.loads(lines[-1])['epoch'] if lines else None})
  records.append({'view':j['view_id'],'method':j['method_id'],'seed':j['seed'],'phase':phase,'job_id':j['job_id'],'state':state,'pid_present_and_matches':live,'process_receipt':rr,'checkpoint_count':len(cps),'epochs':epochs})
stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ');p=H/('runtime-snapshot-'+stamp+'.json');p.write_text(json.dumps({'at':stamp,'scope':'Every historical resource phase; NOT unique logical model/view/seed counts; superseded unstarted contracts kept','records':records,'counts':{k:sum(x['state']==k for x in records) for k in ['complete','active','terminal_partial','not_started']}},indent=2));print(json.dumps({'path':str(p),'counts':{k:sum(x['state']==k for x in records) for k in ['complete','active','terminal_partial','not_started']}}))
