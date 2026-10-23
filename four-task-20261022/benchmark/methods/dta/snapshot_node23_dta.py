"""Read current owned-job evidence, not stale controller status or guessed completion."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path

ROOT=Path('/data/qlyu/projects/peptide-four-task-benchmark-20261022')
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024**2),b''):h.update(block)
    return h.hexdigest()

completed=[];active=[];failed=[];duplicates={}
for name in ['node23-cpu-v1','node23-cpu-recovery-v2','node23-cpu-recovery-v3']:
    index=ROOT/'methods/dta'/name/'jobs.json'
    if not index.exists():continue
    for job in read(index)['jobs']:
        if job['stage']!='formal':continue
        unit=ROOT/job['output_root'];complete=unit/'complete.json';log=Path(job['run_dir'])
        key=(job['view_id'],job['method_id'],job['seed'])
        if complete.exists():
            data=read(complete);pred=unit/'test-predictions.jsonl'
            valid=pred.exists() and sha(pred)==data['prediction_sha256'] and data['spec_sha256']==job['spec_sha256']
            row={'view_id':key[0],'method_id':key[1],'seed':key[2],'phase':name,'valid_prediction_hash':valid,
                 'complete_path':str(complete),'elapsed_seconds':data['elapsed_seconds'],'n':data['metrics']['n']}
            completed.append(row);duplicates.setdefault(key,[]).append(row)
            continue
        launch=log/'launch.json'
        if not launch.exists():continue
        record=read(launch);p=Path('/proc')/str(record['pid'])
        try:
            cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
            text=(p/'stat').read_text();parts=text[text.rfind(')')+2:].split()
            live=job['spec_path'] in cmd and parts[0]!='Z' and p.stat().st_uid==os.getuid()
        except OSError:live=False
        if live:
            stage='encoding_or_loading_train_validation';epoch=None;candidate=None
            for ci in range(2):
                ep=unit/f'candidate-{ci}'/'epochs.jsonl'
                if ep.exists():
                    stage='training_or_validation';candidate=ci
                    lines=ep.read_text().splitlines()
                    epoch=json.loads(lines[-1])['epoch'] if lines else None
            if (unit/'selection.json').exists():stage='postselection_test_scoring'
            active.append({'view_id':key[0],'method_id':key[1],'seed':key[2],'phase':name,
                'pid':record['pid'],'cpu_affinity':record['cpu_affinity'],'stage':stage,
                'last_completed_epoch':epoch,'candidate':candidate})
        elif (log/'process-receipt.json').exists():
            receipt=read(log/'process-receipt.json')
            failed.append({'view_id':key[0],'method_id':key[1],'seed':key[2],'phase':name,
                'exit_code':receipt['exit_code'],'termination_reason':receipt['termination_reason']})
stamp=dt.datetime.now(dt.timezone.utc)
result={'at':stamp.isoformat(),'completed':completed,'active':active,'failed_or_partial':failed,
        'counts':{'completed':len(completed),'active':len(active),'failed_or_partial':len(failed)},
        'duplicate_completed_logical_units':[[*key] for key,rows in duplicates.items() if len(rows)>1],
        'scope':'Node23 formal source/target/effect only; excludes WSL GPU, old NC runs and 633-row CPU subtask'}
folder=ROOT/'methods/dta/node23-cpu-recovery-v3/snapshots';folder.mkdir(exist_ok=True)
(folder/(stamp.strftime('%Y%m%dT%H%M%SZ')+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
