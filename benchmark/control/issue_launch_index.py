"""Bind issued contracts to ready caches; issue an immutable launch phase."""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import json

ROOT=Path(__file__).resolve().parent.parent
WSL='/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021'
GPU='GPU-e9419f8b-b24b-a22b-c8ec-8f5173f4b45a'
SHA_CACHE={}
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    p=Path(p);before=p.stat();key=(str(p.resolve()),before.st_size,before.st_mtime_ns)
    if key not in SHA_CACHE:
        h=hashlib.sha256()
        with p.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        after=p.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('Artifact changed during hashing')
        SHA_CACHE[key]=h.hexdigest()
    return SHA_CACHE[key]
def wsl(p):return WSL+'/'+str(Path(p).relative_to(ROOT)).replace('\\','/')
def local(p):return ROOT/str(p).split('peptide-binding-nc-benchmark-20261021/',1)[1] if str(p).startswith('/mnt/d/') else Path(p)
def write(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists():raise FileExistsError('Immutable issued file already exists: '+str(p))
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',required=True);parser.add_argument('--initial-five',action='store_true');parser.add_argument('--ready-only',action='store_true');parser.add_argument('--regime',choices=['NC_only','standard_only'])
    args=parser.parse_args()
    specs=load(ROOT/'control/gpu-fit-specs-v4/execution-index.json')
    issued=load(ROOT/'administration/issued-gpu-v4/freeze-index.json')
    assert issued['frozen_units']==issued['ready_units']==200 and issued['blocked_units']==0
    contracts={r['run_id']:r for r in issued['records']}
    caches=load(ROOT/'feature-cache-preparation/cache-index.json')['by_cell']
    bound=ROOT/'control/run_bound_unit.py';wrapper=ROOT/'launch/run_unit.py'
    units=[];deferred=[]
    for r in specs['units']:
        uid=r['unit_id'];c=contracts[uid]
        if args.regime and r['regime_id']!=args.regime:continue
        if args.initial_five and (r['seed']!=0 or r['regime_id']!='NC_only' or r['split_id']!='source_peptide_dependency_cold'):continue
        key='__'.join([r['split_id'],r['method_id'],r['regime_id']])
        cache=caches.get(key)
        if not cache or cache.get('status')!='materialized_producer_verified':
            if args.ready_only:deferred.append(uid);continue
            raise RuntimeError('Feature cache not yet ready: '+key)
        proofs=[]
        for entry in cache['outputs']:
            if entry['filename'].endswith('.pkl'):
                p=Path(entry['local_path'])
                assert sha(p)==entry['sha256']
                proofs.append(dict(path=wsl(p),sha256=entry['sha256']))
        assert len(proofs)==2
        bindingfile=ROOT/'control/unit-bindings-v4'/(uid+'.json')
        binding=dict(schema='nc-post-issue-unit-binding-v1',unit_id=uid,
            wrapper=wsl(wrapper),wrapper_sha256=sha(wrapper),spec=r['spec_wsl_path'],spec_sha256=r['spec_sha256'],
            contract=wsl(Path(c['contract_path'])),contract_sha256=c['contract_sha256'],
            validation=wsl(Path(c['validation_binding_path'])),validation_sha256=c['validation_binding_sha256'],
            deadline='2026-10-22T01:45:00+00:00',binding_receipt=WSL+'/launch/bound-entry-receipts-v4/'+uid+'.json')
        if bindingfile.exists():assert load(bindingfile)==binding
        else:write(bindingfile,binding)
        units.append(dict(unit_id=uid,spec=r['spec_wsl_path'],spec_sha256=r['spec_sha256'],
            contract=binding['contract'],contract_sha256=binding['contract_sha256'],
            validation=binding['validation'],validation_sha256=binding['validation_sha256'],
            unit_binding=wsl(bindingfile),unit_binding_sha256=sha(bindingfile),
            bound_entrypoint=wsl(bound),bound_entrypoint_sha256=sha(bound),feature_cache_proofs=proofs))
    if args.initial_five:assert len(units)==5
    # Round-robin method/seed first; groups cannot change the frozen scientific fits.
    names={m:i for i,m in enumerate(['GraphDTA-GIN','MGraphDTA','DGDTA-CL','DeepNC-GEN','GS-DTA'])}
    lookup={r['unit_id']:r for r in specs['units']}
    units.sort(key=lambda u:(lookup[u['unit_id']]['regime_id']!='NC_only',lookup[u['unit_id']]['seed'],lookup[u['unit_id']]['split_id'],names[lookup[u['unit_id']]['method_id']]))
    index=dict(schema='nc-unit-index-v1',issued=True,expected_hostname='cihebi',gpu_uuid=GPU,
        deadline='2026-10-22T01:45:00+00:00',python='/root/.venvs/peptide-omnipanel-v31-web311-20260723/bin/python',
        PYTHONPATH=WSL+'/resources/local-gpu-route/vendor-dependencies',max_concurrent=2,
        graphics_baseline_memory_bytes=4970000000,startup_max_utilization_percent=20,
        feature_cache_required=True,supervisor_sha256=sha(ROOT/'launch/pool_supervisor.py'),
        wrapper_sha256=sha(wrapper),common_sha256=sha(ROOT/'launch/common.py'),
        output_root=WSL+'/launch/pool-runs-'+args.phase,units=units,
        issued_at=dt.datetime.now(dt.timezone.utc).isoformat(),remaining_scientific_units_not_in_this_phase=200-len(units),
        cache_not_ready_units=deferred,scoring_started=False,
        global_score_barrier='All200 frozen scientific selections required before any holdout scoring')
    out=ROOT/'control'/('unit-index-'+args.phase+'.json');write(out,index)
    print(json.dumps(dict(path=wsl(out),sha256=sha(out),units=len(units),remaining=200-len(units))))

if __name__=='__main__':main()
