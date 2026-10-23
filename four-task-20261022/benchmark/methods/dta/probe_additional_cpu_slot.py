"""Read-only CPU slot capacity observation, no reservation or scientific work."""
import datetime as dt,json,os
from pathlib import Path
import psutil
cores=[25,30,57,62];frames=[]
for _ in range(3):
 per=psutil.cpu_times_percent(interval=1,percpu=True)
 uidrss=0
 for p in psutil.process_iter(['uids','memory_info']):
  try:
   if p.info['uids'].real==os.getuid():uidrss+=p.info['memory_info'].rss
  except (psutil.Error,KeyError,TypeError):pass
 avail=psutil.virtual_memory().available
 frame={'at':dt.datetime.now(dt.timezone.utc).isoformat(),'idle_percent':sum(x.idle for x in per)/len(per),'core_idle':{str(c):per[c].idle for c in cores},'available_bytes':avail,'uid_rss_bytes':uidrss}
 frame['passed']=frame['idle_percent']>=40 and min(frame['core_idle'].values())>=60 and avail-3*1024**3>=36*1024**3 and uidrss+3*1024**3<=80*1024**3
 frames.append(frame)
result={'cores':[25,30],'siblings':[57,62],'frames':frames,'passed':all(x['passed'] for x in frames),'scope':'actual point-in-time capacity, receiving owner must recheck at own admission'}
dest=Path('/data/qlyu/projects/peptide-four-task-benchmark-20261022/methods/dta/additional-CPU-slot-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json');dest.write_text(json.dumps(result,indent=2));print(json.dumps({'path':str(dest),**result}))
