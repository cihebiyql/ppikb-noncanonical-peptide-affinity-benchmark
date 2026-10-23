"""Freeze only the 44 CPU-owned missing fits; all scientific hyperparameters unchanged."""
import copy,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];H=ROOT/'methods/dta/continuation-cpu-v1';REMOTE='/data/qlyu/projects/peptide-four-task-benchmark-20261022'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);assert not p.exists();p.write_text(json.dumps(x,indent=2))
def main():
 rp=ROOT/'resources/continuation-20261023/route-manifest.json';assert sha(rp)=='ccc9c632a4c62410e303038b22b5ffa19143a898f65c3e4fd22e0acdf898ea8f';route=load(rp);jobs=[]
 for r in route['routes']:
  if r['assigned_route']!='node23-cpu':continue
  base=ROOT/r['base_spec_relative_path'];assert sha(base)==r['base_spec_sha256'];s=load(base);assert s['method_id']!='MGraphDTA';old=copy.deepcopy(s);jid=r['original_job_id']+'--node23-cpu-continuation-v1';out=f"runs/dta_continuation_cpu_v1/{s['view_id']}/{s['method_id']}/formal/seed-{s['seed']}";s.update(job_id=jid,run_root=out,cpu_threads=2,timeout_seconds=7200,resource_revision='Explicit user campaign cap cancellation; CPU2/4GiB/7200s per fit; all original science unchanged',previous_spec_sha256=sha(base));p=H/'specs'/(jid+'.json');write(p,s)
  allowed={'job_id','run_root','cpu_threads','timeout_seconds','resource_revision','previous_spec_sha256'};assert all(old.get(k)==s.get(k) for k in set(old)|set(s) if k not in allowed)
  jobs.append({**r,'job_id':jid,'spec_relative_path':p.relative_to(ROOT).as_posix(),'spec_sha256':sha(p),'output_root':out,'timeout_seconds':7200,'cpu_threads':2,'memory_limit_bytes':4*1024**3,'sample_counts':{k:v['n'] for k,v in s['paths'].items()}})
 assert len(jobs)==44
 rank={'ppikb_kd_source_cold_scope_v2':0,'ppikb_effect_metadata_silver_source_cold':1,'ppikb_kd_target_cold_scope_v2':2};jobs.sort(key=lambda j:(rank[j['view_id']],j['seed'],j['method_id']))
 write(H/'jobs.json',{'schema':'fourtask.cpu-continuation.v1','campaign_id':route['campaign_id'],'route_manifest_sha256':sha(rp),'total_campaign_cap':None,'max_concurrent':8,'cpu_allowed_physical_pairs':[8,10,12,14,16,18,20,22],'SWING_reserved':list(range(8))+list(range(32,40)),'jobs':jobs});print(json.dumps({'jobs':44,'index':str(H/'jobs.json'),'sha256':sha(H/'jobs.json')}))
if __name__=='__main__':main()
