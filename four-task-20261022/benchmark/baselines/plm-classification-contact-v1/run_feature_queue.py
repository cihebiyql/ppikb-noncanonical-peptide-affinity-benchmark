"""Finite resumable queue; completed chunks are hash-verified and never recomputed."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import signal
import subprocess
import sys
import time
import os

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024**2),b''):h.update(b)
    return h.hexdigest()
def write(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2),encoding='utf-8');temp.replace(path)
def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',type=Path,required=True);args=parser.parse_args()
    plan=json.loads(args.plan.read_text());contract_path=Path(plan['feature_contract'])
    contract=json.loads(contract_path.read_text());root=Path(plan['output_root']);root.mkdir(parents=True,exist_ok=True)
    assert sha(contract_path)==plan['feature_contract_sha256']
    count=(contract['sequence_count']+contract['chunk_size']-1)//contract['chunk_size']
    started=time.monotonic();status={'started_at':now(),'chunk_count':count,'completed_chunks':[],
        'failed_chunks':[],'deferred_chunks':[],'plan_sha256':sha(args.plan),'status':'running'}
    progress=root/'feature-queue-status.json';write(progress,status)
    def valid_receipt(path,canary=False):
        if not path.exists():return False
        receipt=json.loads(path.read_text())
        assert receipt['status']=='succeeded' and receipt['canary']==canary
        assert receipt['contract_sha256']==sha(contract_path) and receipt['model_sha256']==contract['model_sha256']
        assert sha(path.parent/'means.npz')==receipt['means_sha256']
        for item in receipt['residue_sequences']:assert sha(item['path'])==item['sha256']
        return True
    def launch(canary=False,chunk=None):
        command=[sys.executable,'-B',plan['supervisor'],'--plan',str(args.plan)]
        command+=['--canary'] if canary else ['--chunk',str(chunk)]
        timeout=plan['queue_timeout_seconds']+(plan['canary_timeout_seconds'] if canary else plan['chunk_timeout_seconds'])+60
        completed=subprocess.run(command,timeout=timeout)
        return completed.returncode
    canary=root/'feature-canary-v1/receipt.json'
    if not valid_receipt(canary,True):
        if canary.parent.exists():
            status.update(status='canary_partial_requires_bounded_repair',completed_at=now());write(progress,status);return 2
        code=launch(canary=True)
        if code or not valid_receipt(canary,True):
            status.update(status='canary_not_completed',canary_exit_code=code,completed_at=now());write(progress,status);return code or 2
    status['canary_receipt_sha256']=sha(canary);write(progress,status)
    for chunk in range(count):
        output=root/'feature-chunks'/f'chunk-{chunk:03d}';receipt=output/'receipt.json'
        if valid_receipt(receipt):status['completed_chunks'].append(chunk);write(progress,status);continue
        if output.exists():status['failed_chunks'].append(chunk);write(progress,status);continue
        if time.monotonic()-started>plan['controller_timeout_seconds']:
            status['deferred_chunks']=list(range(chunk,count));break
        code=launch(chunk=chunk)
        if code==3 and not output.exists():
            status['deferred_chunks']=list(range(chunk,count));break
        if code or not valid_receipt(receipt):status['failed_chunks'].append(chunk)
        else:status['completed_chunks'].append(chunk)
        status['updated_at']=now();write(progress,status)
        print(json.dumps({'completed_chunks':len(status['completed_chunks']),'total_chunks':count,
            'failed_chunks':status['failed_chunks'],'elapsed_seconds':time.monotonic()-started}),flush=True)
    status.update(status='features_complete' if len(status['completed_chunks'])==count else 'features_incomplete',
        completed_at=now(),elapsed_seconds=time.monotonic()-started)
    write(progress,status);return 0 if status['status']=='features_complete' else 2
if __name__=='__main__':raise SystemExit(main())
