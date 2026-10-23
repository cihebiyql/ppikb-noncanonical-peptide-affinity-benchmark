"""Administrative handoff between two individually bounded, non-overlapping owned CPU jobs."""
import datetime as dt
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
receipt_path=ROOT/'runs/plm-simple-v1/extraction-cpu-v3-formal-supervision/process-receipt.json'
output=HERE/'continuation-chain-receipt.json'
report={'started_at':dt.datetime.now(dt.timezone.utc).isoformat(),'steps':[],
        'simultaneous_scientific_jobs_maximum':1,'new_resources_added':False,
        'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
def write():output.write_text(json.dumps(report,indent=2),encoding='utf-8')
write()
deadline=time.monotonic()+5400
try:
    while not receipt_path.exists():
        if time.monotonic()>deadline:raise TimeoutError('Owned extraction did not reach terminal receipt within declared waiting budget')
        time.sleep(10)
    previous=json.loads(receipt_path.read_text())
    assert previous['pid']==203972 and previous['spec_sha256']=='2c8567fc0c1e7bbf08847ed6167b852c27112956c9b69a31ee26e2428e823440'
    assert previous['exit_code']==0 and previous['worker_pid_absent'] and not previous['termination_reason']
    report['extraction_process_receipt_sha256']=hashlib.sha256(receipt_path.read_bytes()).hexdigest();write()
    commands=[[sys.executable,'-B',str(HERE/'bind_cpu_cache.py')],
              [sys.executable,'-B',str(HERE/'prepare_heads_spec.py')],
              [sys.executable,'-B',str(HERE/'supervise_heads.py'),'--spec',str(HERE/'head-run-spec.json')]]
    for command in commands:
        start=time.monotonic()
        completed=subprocess.run(command,check=True,timeout=5600)
        report['steps'].append({'command':command,'exit_code':completed.returncode,'elapsed_seconds':time.monotonic()-start});write()
    report.update(status='succeeded',completed_at=dt.datetime.now(dt.timezone.utc).isoformat());write()
except BaseException as exc:
    report.update(status='failed',error=repr(exc),completed_at=dt.datetime.now(dt.timezone.utc).isoformat());write();raise
