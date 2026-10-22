"""Add actual launch provenance to fresh v4 specs; preserve v3 drafts."""
from pathlib import Path
import hashlib
import json

PROJECT=Path(__file__).resolve().parent.parent
WSL='/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021'
FOLDERS={'GraphDTA-GIN':'graphdta-deepnc','MGraphDTA':'mgraph-dgdta','DGDTA-CL':'mgraph-dgdta','DeepNC-GEN':'graphdta-deepnc','GS-DTA':'gs-dta'}
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def wsl(p):return WSL+'/'+str(Path(p).relative_to(PROJECT)).replace('\\','/')
def write(p,obj):Path(p).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    out=PROJECT/'control/gpu-fit-specs-v4';out.mkdir(exist_ok=False)
    old=PROJECT/'execution/formal-specs-gpu-v3/execution-index.json'
    prior=load(old)
    drafts=load(PROJECT/'administration/drafts-gpu-five-facts-v3/draft-index.json')
    mapping={(r['method_id'],r['split_id'],r['regime_id'],r['seed']):r for r in drafts['runs']}
    specs={}
    runner=PROJECT/'execution/runner.py'
    common=[runner,PROJECT/'control/run_bound_unit.py',PROJECT/'control/user-authorization.json',PROJECT/'launch/common.py',PROJECT/'launch/run_unit.py',PROJECT/'launch/pool_supervisor.py',PROJECT/'resources/local-gpu-route/runtime-freeze-for-training.json',PROJECT/'resources/local-gpu-route/dependency-import-verification.json',PROJECT/'data-protocol/frozen-v1/manifest.json']
    output=[];jobs=[]
    for record in prior['per_seed_selections']:
        p=PROJECT/'execution/formal-specs-gpu-v3'/Path(record['spec_path']).name
        spec=load(p)
        key=(spec['method_id'],spec['split_id'],spec['regime'],spec['seed'])
        draft=mapping[key];uid=draft['run_id']
        method_files=[p for p in sorted((PROJECT/'methods'/FOLDERS[spec['method_id']]).rglob('*.py')) if '__pycache__' not in p.parts]
        spec['run_root']=WSL+'/formal-runs-gpu-v4/fits/'+uid
        spec['launch_proof']=dict(expected_hostname='cihebi',runner_path=wsl(runner),runner_sha256=sha(runner),receipt_root=WSL+'/launch/receipts-v4/'+uid,files=[dict(path=wsl(x),sha256=sha(x)) for x in [*common,*method_files]])
        path=out/(uid+'.json');write(path,spec)
        row=dict(unit_id=uid,method_id=key[0],split_id=key[1],regime_id=key[2],seed=key[3],spec_path=str(path),spec_wsl_path=wsl(path),spec_sha256=sha(path),draft_contract_path=draft['contract_draft_path'],selection_path=spec['run_root']+'/selection.json',binding_wsl_path=WSL+'/control/unit-bindings-v4/'+uid+'.json')
        output.append(row)
        for index in (0,1):jobs.append(dict(unit_id=uid,candidate_index=index,spec_path=str(path),spec_sha256=sha(path)))
    assert len(output)==200 and len(jobs)==400 and len(mapping)==200
    write(out/'execution-index.json',dict(schema='nc-gpu-fit-specs-v4',issued=False,predecessor_index=str(old),predecessor_index_sha256=sha(old),units=output,candidate_fits=jobs,per_seed_selections=[dict(spec_path=r['spec_wsl_path'],selection_path=r['selection_path']) for r in output],total_fits=400,total_selections=200,run_root=WSL+'/formal-runs-gpu-v4',cache_root=WSL+'/encoded-cache-v3',root_policy='No holdout score before all200 selections freeze; data/protocol immutable; five published author models; no innovation model'))
    print(json.dumps(dict(unit_specs=len(output),candidate_fits=len(jobs),execution_index_sha256=sha(out/'execution-index.json'))))

if __name__=='__main__':main()
