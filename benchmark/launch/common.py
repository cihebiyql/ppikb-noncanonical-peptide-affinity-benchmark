"""Small stdlib-only launch primitives; no model or holdout imports."""
from pathlib import Path
import os,json,hashlib,datetime,time,signal
HARD_DEADLINE='2026-10-22T01:45:00+00:00'
GPU_UUID='GPU-e9419f8b-b24b-a22b-c8ec-8f5173f4b45a'
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(1024**2),b''):h.update(block)
 return h.hexdigest()
def path(value):
 value=str(value)
 if os.name!='nt' and len(value)>2 and value[1]==':':value='/mnt/'+value[0].lower()+value[2:].replace('\\','/')
 return Path(value)
def checked(value,expected):
 p=path(value);actual=sha(p)
 if actual!=expected:raise ValueError('SHA mismatch: '+str(p))
 return p
def write(p,value):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.tmp')
 tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');tmp.replace(p)
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def epoch(value):
 moment=datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
 if moment.tzinfo is None:raise ValueError('Deadline requires timezone')
 return moment.timestamp()
def deadline(value):
 result=epoch(value)
 if result>epoch(HARD_DEADLINE):raise ValueError('Cannot extend original deadline')
 if result<=time.time():raise TimeoutError('Original deadline expired')
 return result
def process_table():
 result={}
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   text=(p/'stat').read_text();fields=text[text.rfind(')')+2:].split();pid=int(p.name)
   result[pid]={'pid':pid,'ppid':int(fields[1]),'pgid':int(fields[2]),'session':int(fields[3]),'rss':int(fields[21])*os.sysconf('SC_PAGE_SIZE'),'start_ticks':int(fields[19]),'uid':p.stat().st_uid}
  except (FileNotFoundError,ProcessLookupError,PermissionError,ValueError):pass
 return result
def children(root,table):
 owned={root};changed=True
 while changed:
  added={pid for pid,r in table.items() if r['ppid'] in owned};new=added-owned;changed=bool(new);owned|=new
 return owned
def stop_owned_group(pgid,grace=3):
 # Only private sessions created by this supervisor qualify for group kill.
 table=process_table();members=[r for r in table.values() if r['pgid']==pgid]
 if not members:return
 if any(r['session']!=pgid or r['uid']!=os.getuid() for r in members):raise RuntimeError('Refuse to signal unowned session')
 try:os.killpg(pgid,signal.SIGTERM)
 except ProcessLookupError:return
 time.sleep(grace)
 table=process_table()
 if any(r['pgid']==pgid and r['session']==pgid and r['uid']==os.getuid() for r in table.values()):
  try:os.killpg(pgid,signal.SIGKILL)
  except ProcessLookupError:pass
