"""Freeze the pre-repair aggregate and derive endpoints solely from frozen contracts/views."""
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def read(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False),encoding='utf-8')
def main():
    directory=HERE/'original-snapshot';directory.mkdir(parents=True,exist_ok=False)
    originals=[ROOT/'reports/build_delivery_snapshot.py',ROOT/'reports/delivery-20261023/generic-completed-metrics-all-panels.csv',ROOT/'reports/delivery-20261023/STATUS.json']
    frozen=[]
    for path in originals:
        target=directory/path.name;shutil.copyfile(path,target);assert sha(path)==sha(target)
        frozen.append({'original':str(path),'snapshot':str(target),'sha256':sha(target),'bytes':target.stat().st_size})
    rows=read(directory/'generic-completed-metrics-all-panels.csv')
    parent_path=ROOT/'data/view_manifest.json';parent=load(parent_path);parentviews={v['id']:v for v in parent['views']}
    coverage_paths=[ROOT/'baselines/plm-simple-v1/coverage-manifest.json',ROOT/'baselines/plm-classification-contact-v1/coverage-manifest.json']
    coverage={v['id']:(v,p) for p in coverage_paths for v in load(p)['views']}
    evidence={};byview={};runviews=sorted({(r['run_id'],r['view_id']) for r in rows})
    for run_id,view_id in runviews:
        if run_id=='her2-strict-local-baselines-v1':
            contractpath=ROOT/'runs'/run_id/'task-contract.json';contract=load(contractpath)
            manifestpath=Path(contract['input_manifest']['path']);assert sha(manifestpath)==contract['input_manifest']['sha256']
            view=next(v for v in load(manifestpath)['views'] if v['id']==view_id)
            endpoint,task=view['endpoint'],view['task'];ev=[contractpath,manifestpath]
        else:
            base=ROOT/'runs'/run_id
            if run_id in {'plm-simple-v1','plm-classification-contact-v1'}:base=base/'heads'
            contractpath=base/view_id/'task-contract.json';contract=load(contractpath)
            assert contract['view_id']==view_id
            endpoint,task=contract['endpoint'],contract['task'];ev=[contractpath]
        item={'view_id':view_id,'endpoint':endpoint,'task':task,'run_ids':[run_id],
            'evidence':[{'path':str(p),'sha256':sha(p)} for p in ev],'endpoint_inferred_from_metrics':False}
        if view_id in coverage:
            view,path=coverage[view_id];assert view['endpoint']==endpoint and view['task']==task
            parent_id=view['parent_view_id'];assert parentviews[parent_id]['endpoint']==endpoint
            item.update(parent_view_id=parent_id,parent_endpoint=parentviews[parent_id]['endpoint'],
                derived_coverage_evidence={'path':str(path),'sha256':sha(path)},
                parent_view_manifest_evidence={'path':str(parent_path),'sha256':sha(parent_path)})
        elif view_id in parentviews:
            assert parentviews[view_id]['endpoint']==endpoint and parentviews[view_id]['task']==task
            item['parent_view_manifest_evidence']={'path':str(parent_path),'sha256':sha(parent_path)}
        if view_id in byview:
            existing=byview[view_id];assert (existing['endpoint'],existing['task'])==(endpoint,task)
            existing['run_ids'].append(run_id);existing['evidence']+=item['evidence']
        else:byview[view_id]=item
        evidence[(run_id,view_id)]=item
    blanks=[r for r in rows if not r['endpoint']]
    conflicts=[r for r in rows if r['endpoint'] and r['endpoint']!=byview[r['view_id']]['endpoint']]
    mapping={'schema':'generic.endpoint-declarations.independent-map.v1','recorded_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'original_snapshot':frozen,'view_count':len(byview),'run_view_conditions':len(runviews),'by_view_id':byview,
        'original_blank_endpoint_rows':len(blanks),'original_nonblank_endpoint_conflicts':len(conflicts),
        'generic_rows':len(rows),'new_fit_count':0,'new_forward_count':0,'code_sha256':sha(__file__)}
    write(HERE/'view-endpoint-map.json',mapping)
    with (HERE/'view-endpoint-map.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['view_id','task','endpoint','parent_view_id','run_ids','evidence'])
        writer.writeheader()
        for item in byview.values():writer.writerow({**{k:item.get(k,'') for k in ['view_id','task','endpoint','parent_view_id']},
            'run_ids':'|'.join(item['run_ids']),'evidence':json.dumps(item['evidence'],ensure_ascii=False)})
    print({'rows':len(rows),'views':len(byview),'run_view_conditions':len(runviews),'blank_endpoint_rows':len(blanks),'conflicts':len(conflicts),'map_sha256':sha(HERE/'view-endpoint-map.json')})
if __name__=='__main__':main()
