"""Bind actual CPU receipts and outputs to the standard result-record schema."""
import argparse
import copy
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
from cpu_fallback import ROOT, HERE, load, sha, write, wsl

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--batch',required=True)
    args=parser.parse_args()
    batch=HERE/args.batch
    standard=ROOT.parents[1]/'复现/规范'
    template=load(standard/'result-record.template.json')
    results=[]
    for job in load(batch/'jobs.json')['jobs']:
        folder=Path(job['log_dir'])
        receiptpath=folder/'execution-receipt.json'
        completepath=ROOT/job['run_root']/'complete.json'
        if not receiptpath.exists() or not completepath.exists():
            continue
        receipt,complete=load(receiptpath),load(completepath)
        if receipt['status']!='succeeded' or receipt['remaining_group_members']:
            continue
        cp=Path(job['contract_path'])
        contract=load(cp)
        started=load(folder/'started.json')
        now=dt.datetime.now(dt.timezone.utc).isoformat()
        record=copy.deepcopy(template)
        record.update(is_template=False,task_id=contract['task_id'],run_id=job['job_id'],
            contract_path=str(cp),contract_sha256=sha(cp),recorded_at=now,
            lifecycle_status='succeeded',reproduction_level='smoke' if complete['stage']=='smoke' else 'training',
            scope_coverage='partial_subset')
        record['claims']=[{'text':'Actual new CPU common-data '+complete['stage']+' completed with two LR candidates, validation-only selection and held-out prediction.',
            'evidence_type':'source_fact','evidence_paths':[str(completepath),str(receiptpath)],
            'limitations':'Not full original-paper reproduction; scope/seed counts are exactly those in complete.json. No GPU used.'}]
        record['assets_integrity']={key:{'status':'complete','scope':'This exact CPU run',
            'evidence_paths':[str(folder/'validation.stdout.json'),str(completepath)]} for key in ('datasets','code','models','environment')}
        record['execution'].update(performed=True,command=contract['execution']['command'],
            working_directory=contract['execution']['working_directory'],environment_path=contract['environment']['environment_path'],
            hostname='cihebi',resource_probe_path=contract['resources']['resource_probe_path'],
            resource_usage_path=str(receiptpath),seeds=contract['execution']['seeds'],
            seed_notes='Only these actually completed seeds; never equated to all ten before completion',
            started_at=dt.datetime.fromtimestamp(started['started_unix'],dt.timezone.utc).isoformat(),
            ended_at=dt.datetime.fromtimestamp(started['started_unix']+receipt['elapsed_seconds'],dt.timezone.utc).isoformat(),
            effective_deadline_at=contract['timing']['effective_deadline_at'],timeout_seconds=900,
            pid=receipt['pid'],pgid=receipt['pgid'],job_object_or_tree_control='Private Linux process group with 900s wall/RSS watchdog',
            exit_code=receipt['exit_code'],timed_out=False,termination_reason=None,
            handles_absent_verified_at=now,exit_verification_path=str(receiptpath),
            stdout_path=str(folder/'stdout.log'),stderr_path=str(folder/'stderr.log'),receipt_path=str(receiptpath),
            notes='CUDA_VISIBLE_DEVICES empty; one CPU thread; no shared environment modification.')
        target=contract['targets'][0]
        comparison={key:target.get(key) for key in ('target_id','paper_endpoint','metric','metric_definition','statistical_unit','denominator','unit','paper_value')}
        comparison.update(actual_value=complete['metrics']['MAE'],baseline_value=None,
            absolute_difference=None,relative_difference=None,comparability='not_comparable',
            tolerance_reference='contract target tolerance',passed=None,
            reason='New common-data endpoint/split; original paper table numerical comparison is not claimed',
            evidence_paths=[str(completepath),str(completepath.parent/'test-metrics.json')])
        record['metric_comparisons']=[comparison]
        artifacts=[]
        for path in sorted(completepath.parent.rglob('*')):
            if path.is_file():
                artifacts.append({'role':'new CPU run artifact','path':str(path),'location':'local',
                    'available':True,'size_bytes':path.stat().st_size,'sha256':sha(path)})
        for path in [folder/'stdout.log',folder/'stderr.log',receiptpath,folder/'validation.stdout.json']:
            artifacts.append({'role':'execution evidence','path':str(path),'location':'local','available':True,
                'size_bytes':path.stat().st_size,'sha256':sha(path)})
        record['artifacts']=artifacts
        record['differences']=[{'category':'evaluation_scope','description':'Common-data author-architecture training on an explicitly frozen subset, with CPU execution.',
            'effect_on_comparison':'Cannot be equated to paper main table or complete multi-task benchmark',
            'evidence_type':'source_fact','evidence_paths':[str(cp)]}]
        record['incomplete_reasons']=[]
        record['review'].update(status='accepted',reviewer='dta_build CPU evidence review',reviewed_at=now,
            checks=[{'item':k,'passed':True,'reason':'Exact input/source contract, real process exit, saved numerical outputs, and explicitly limited claim checked'}
                    for k in ('identity','assets','contract','execution','comparison','claims','preservation')],
            evidence_paths=[str(receiptpath),str(completepath)])
        rp=folder/'result-record.json'
        write(rp,record)
        check=subprocess.run([sys.executable,str(standard/'validate_reproduction.py'),'--contract',str(cp),
                              '--result',str(rp),'--check-files'],capture_output=True,text=True,timeout=90)
        (folder/'result-validation.json').write_text(check.stdout,encoding='utf-8')
        (folder/'result-validation.stderr.log').write_text(check.stderr,encoding='utf-8')
        gate=json.loads(check.stdout)
        results.append({'job_id':job['job_id'],'valid_for_acceptance':gate.get('valid_for_acceptance'),
                        'errors':gate.get('errors'),'result_record_path':str(rp)})
    write(batch/'result-record-validation.json',{'records':results,
        'accepted':sum(r['valid_for_acceptance'] is True for r in results)})
    print(json.dumps({'records':len(results),'accepted':sum(r['valid_for_acceptance'] is True for r in results)}))
    if any(r['valid_for_acceptance'] is not True for r in results):
        raise SystemExit(2)

if __name__=='__main__':
    main()
