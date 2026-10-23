"""Read-only scientific unit census, preserving runtime and logical duplicates."""
import json,hashlib,datetime as dt,socket,sys
from pathlib import Path
R=Path('/data/qlyu/projects/peptide-four-task-benchmark-20261022') if sys.platform!='win32' else Path(__file__).resolve().parents[2]
methods={'GraphDTA-GIN','MGraphDTA','DGDTA-CL','DeepNC-GEN','GS-DTA'}
records=[];invalid=[]
for p in (R/'runs').rglob('complete.json'):
 try:
  x=json.loads(p.read_text());m=x.get('method_id')
  if m not in methods or x.get('stage')!='formal':continue
  pred=p.parent/'test-predictions.jsonl'
  valid=pred.exists() and hashlib.sha256(pred.read_bytes()).hexdigest()==x['prediction_sha256']
  row={'path':str(p),'method':m,'view':x['view_id'],'seed':x['seed'],'task':x['task'],'n':x.get('sample_counts'),'metrics':x.get('metrics'),'elapsed_seconds':x.get('elapsed_seconds'),'prediction_hash_valid':valid,'prediction_sha256':x['prediction_sha256'],'job_id':x['job_id']}
  runtime=p.parent/'runtime.json'
  if runtime.exists():row['runtime']=json.loads(runtime.read_text())
  (records if valid else invalid).append(row)
 except (OSError,ValueError,KeyError):continue
stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ');out=R/'methods/dta'/('census-'+socket.gethostname()+'-'+stamp+'.json');out.write_text(json.dumps({'at':stamp,'scope':'saved formal complete only; not standard acceptance/independent audit','records':records,'invalid':invalid},indent=2));print(json.dumps({'records':len(records),'invalid':len(invalid),'path':str(out)}))
