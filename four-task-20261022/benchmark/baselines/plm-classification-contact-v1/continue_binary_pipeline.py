"""Current-task handoff: finished frozen-feature queue -> cache proof -> bounded binary heads."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];RUN=ROOT/'runs/plm-classification-contact-v1'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,obj):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(obj,indent=2),encoding='utf-8');temp.replace(path)
def main():
    contract=json.loads((HERE/'binary-pipeline-contract.json').read_text())
    for item in contract['code_and_protocol_hashes']:assert sha(item['path'])==item['sha256'],item['path']
    report={'started_at':dt.datetime.now(dt.timezone.utc).isoformat(),'steps':[],'status':'waiting_for_features',
        'pipeline_contract_sha256':sha(HERE/'binary-pipeline-contract.json'),'new_resources_added':False,
        'scientific_groups_concurrent_maximum':1,'code_sha256':sha(__file__)}
    out=HERE/'binary-pipeline-receipt.json';write(out,report)
    deadline=time.monotonic()+21600
    try:
        while True:
            path=RUN/'feature-queue-status.json'
            state=json.loads(path.read_text()) if path.exists() else {}
            if state.get('status')=='features_complete':break
            if state.get('status') not in {None,'running'}:raise RuntimeError('Frozen feature queue incomplete: '+state.get('status','missing'))
            if time.monotonic()>deadline:raise TimeoutError('Finite pipeline feature-wait budget exhausted')
            time.sleep(20)
        report['feature_queue_final_sha256']=sha(path);report['status']='features_complete_starting_binary';write(out,report)
        commands=[[sys.executable,'-B',str(HERE/'assemble_cache.py')],
                  [sys.executable,'-B',str(HERE/'prepare_head_spec.py')],
                  [sys.executable,'-B',str(HERE/'supervise_heads.py'),'--spec',str(HERE/'head-execution-contract.json')]]
        for command in commands:
            started=time.monotonic();completed=subprocess.run(command,check=True,timeout=9000)
            report['steps'].append({'command':command,'exit_code':completed.returncode,'elapsed_seconds':time.monotonic()-started});write(out,report)
        report.update(status='succeeded',completed_at=dt.datetime.now(dt.timezone.utc).isoformat());write(out,report)
    except BaseException as exc:
        report.update(status='failed_or_incomplete',error=repr(exc),completed_at=dt.datetime.now(dt.timezone.utc).isoformat());write(out,report);raise
if __name__=='__main__':main()
