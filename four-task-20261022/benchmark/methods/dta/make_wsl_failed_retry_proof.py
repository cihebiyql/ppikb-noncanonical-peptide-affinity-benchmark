"""Generate fresh WSL-native absence plus immutable partial hashes for exactly two failed guard stops."""
from pathlib import Path
import datetime as dt,hashlib,json,shutil,socket
R=Path(__file__).resolve().parents[2];H=R/'methods/dta';B=R/'resources/continuation-20261023'
KEYS=[['ppikb_kd_target_cold_scope_v2','DeepNC-GEN',6],['ppikb_kd_source_cold_scope_v2','DeepNC-GEN',8]]
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for x in iter(lambda:f.read(1024**2),b''):h.update(x)
 return h.hexdigest()
def group(pgid):
 out=[]
 for proc in Path('/proc').iterdir():
  if not proc.name.isdigit():continue
  try:
   s=(proc/'stat').read_text().split(')')[-1].split()
   if s[0]!='Z' and int(s[2])==pgid:out.append(int(proc.name))
  except (OSError,ValueError):pass
 return out
stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ');dest=H/('wsl-failed-retry-proof-'+stamp);dest.mkdir();units=[]
for i,key in enumerate(KEYS):
 v,m,seed=key;name=f'{v}--{m}--formal--seed{seed}--wsl-worksteal1--admit1';dp=B/'dispatch'/name/'dispatch.json';q=load(dp);assert q['status']=='failed' and q['exit_code']==-15 and q['stop_reason']=='cross_host_telemetry_unavailable' and q['remaining_owned_pids']==[] and not group(q['pgid'])
 issued=load(B/'issued'/name/'issued.json');assert issued['logical_key']==key;out=R/issued['output_root'];assert out.is_dir() and not (out/'complete.json').exists();assert load(out/'started.json')['spec_sha256']==issued['spec_sha256']
 assets=[{'relative_path':str(p.relative_to(out)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(out.rglob('*')) if p.is_file()];assert any(x['relative_path']=='started.json' for x in assets)
 mirrored=f'{i:02d}.dispatch.json';shutil.copyfile(dp,dest/mirrored);assert sha(dest/mirrored)==sha(dp)
 resource=[]
 for p in [dp.parent/'stdout.log',dp.parent/'stderr.log',B/'issued'/name/'issued.json',B/'issued'/name/'contract.json',dp.parent/'validation.stdout.json']:
  resource.append({'original_path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)})
 units.append({'logical_key':key,'original_dispatch_path':str(dp),'dispatch_sha256':sha(dp),'receipt_mirror_filename':mirrored,'pgid':q['pgid'],'fresh_non_z_group_members':group(q['pgid']),'complete_present':(out/'complete.json').exists(),'partial_output_path':str(out),'partial_assets':assets,'all_partial_file_hashes_verified':True,'resource_assets':resource})
assert all(x['fresh_non_z_group_members']==[] and x['complete_present'] is False for x in units)
proof={'schema':'fourtask.wsl-failed-task-absence-proof.v1','at':dt.datetime.now(dt.timezone.utc).isoformat(),'hostname':socket.gethostname(),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'units':units,'scope':'actual local WSL namespace inspection and original file SHA reads only; no signal, fit, forward or new claim'}
p=dest/'proof.json';p.write_text(json.dumps(proof,indent=2));print(json.dumps({'directory':str(dest),'proof_sha256':sha(p),'units':len(units)}))
