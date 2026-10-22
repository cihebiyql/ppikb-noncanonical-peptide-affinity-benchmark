"""Resolve a post-issuance launch binding; preserve its parent's process group."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys

def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def path(value):
    if len(value)>2 and value[1]==':' and os.name!='nt':
        return Path('/mnt/'+value[0].lower()+'/'+value[3:].replace('\\','/'))
    return Path(value)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--binding',required=True)
    args=parser.parse_args();binding=read(args.binding)
    assert binding['schema']=='nc-post-issue-unit-binding-v1'
    contractpath=path(binding['contract']);contract=read(contractpath)
    assert sha(contractpath)==binding['contract_sha256']
    assert contract['run_id']==binding['unit_id']
    assert contract['is_template'] is False and contract['contract_status']=='frozen'
    now=dt.datetime.now(dt.timezone.utc)
    global_deadline=dt.datetime.fromisoformat(binding['deadline'].replace('Z','+00:00'))
    actual_deadline=min(global_deadline,now+dt.timedelta(seconds=contract['execution']['timeout_seconds']))
    if actual_deadline<=now:raise RuntimeError('No remaining authorized execution window')
    wrapper=path(binding['wrapper'])
    assert sha(wrapper)==binding['wrapper_sha256']
    argv=[sys.executable,str(wrapper),'--spec',str(path(binding['spec'])),'--spec-sha256',binding['spec_sha256'],
          '--contract',str(contractpath),'--contract-sha256',binding['contract_sha256'],
          '--validation',str(path(binding['validation'])),'--validation-sha256',binding['validation_sha256'],
          '--deadline',actual_deadline.isoformat()]
    receipt=path(binding['binding_receipt'])
    receipt.parent.mkdir(parents=True,exist_ok=True)
    if receipt.exists():raise FileExistsError('Launch binding was already used; preserve its original attempt')
    receipt.write_text(json.dumps(dict(unit_id=binding['unit_id'],binding_sha256=sha(args.binding),
        binding_path=str(Path(args.binding).resolve()),started_at=now.isoformat(),
        global_deadline=global_deadline.isoformat(),per_unit_timeout_seconds=contract['execution']['timeout_seconds'],
        actual_unit_deadline=actual_deadline.isoformat(),actual_resolved_argv=argv,pid=os.getpid(),pgid=os.getpgrp()),indent=2),encoding='utf-8')
    os.execv(sys.executable,argv)

if __name__=='__main__':main()
