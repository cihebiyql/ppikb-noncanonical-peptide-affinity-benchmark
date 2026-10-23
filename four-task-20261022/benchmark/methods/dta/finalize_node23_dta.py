"""Archive actual Node23 terminal units; independently recompute overall metrics."""
import copy,datetime as dt,hashlib,json,shlex,subprocess,sys
from pathlib import Path
from audit_runs import independent_metrics

ROOT=Path('/data/qlyu/projects/peptide-four-task-benchmark-20261022')
HERE=ROOT/'methods/dta'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(1024**2),b''):h.update(chunk)
    return h.hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False),encoding='utf-8')

template=load(HERE/'node23-result-record.template.json')
summaries=[]
for phase in ['node23-cpu-v1','node23-cpu-recovery-v2','node23-cpu-recovery-v3']:
    home=HERE/phase;index=home/'jobs.json'
    if not index.exists():continue
    for job in load(index)['jobs']:
        log=Path(job['run_dir']);receipt=log/'process-receipt.json';unit=ROOT/job['output_root'];cp=unit/'complete.json'
        if not cp.exists() or not receipt.exists():continue
        done,r=load(cp),load(receipt)
        if r['exit_code'] or r['termination_reason'] or not r['worker_pid_absent'] or r['residual_group_pids_before_cleanup']:continue
        pred=unit/'test-predictions.jsonl'
        if sha(pred)!=done['prediction_sha256'] or done['spec_sha256']!=job['spec_sha256']:raise ValueError('Completed unit byte binding differs')
        rows=[json.loads(x) for x in pred.read_text().splitlines() if x]
        metrics=independent_metrics(rows,job['task'])
        errors={}
        for key,value in metrics.items():
            expected=done['metrics'].get(key)
            if (value is None)!=(expected is None) or (value is not None and abs(value-expected)>1e-10):errors[key]={'saved':expected,'recomputed':value}
        write(log/'overall-prediction-audit.json',{'valid':not errors,'errors':errors,'recomputed':metrics,
            'scope':'Overall saved prediction metrics only; group-level metrics remain separately preserved'})
        if errors:raise ValueError('Independent numerical mismatch: '+job['job_id'])
        contract=load(job['contract_path'])
        if sha(job['contract_path'])!=job['contract_sha256'] or shlex.split(contract['execution']['command'])!=r['command']:raise ValueError('Actual command/contract differs')
        recordpath=log/'result-record.json'
        if recordpath.exists() and (log/'result-validation.json').exists() and load(log/'result-validation.json').get('valid_for_acceptance'):
            summaries.append({'job_id':job['job_id'],'accepted':True,'preserved_existing':True});continue
        stamp=dt.datetime.now(dt.timezone.utc).isoformat()
        rec=copy.deepcopy(template)
        rec.update(is_template=False,task_id=contract['task_id'],run_id=job['job_id'],contract_path=job['contract_path'],
            contract_sha256=job['contract_sha256'],recorded_at=stamp,lifecycle_status='succeeded',
            reproduction_level='smoke' if job['stage']=='smoke' else 'training',scope_coverage='partial_subset')
        rec['claims']=[{'text':'Actual new common-data CPU '+job['stage']+' completed; validation-only candidate choice, saved test predictions and independent overall metric recomputation.',
            'evidence_type':'source_fact','evidence_paths':[str(cp),str(receipt),str(log/'overall-prediction-audit.json')],
            'limitations':'Not original-paper full reproduction. CPU/GPU and CPU1/CPU2 must be stratified; effect data are metadata-silver.'}]
        rec['assets_integrity']={k:{'status':'complete','scope':'exact contracted unit',
            'evidence_paths':[str(log/'validation.stdout.json'),str(cp)]} for k in ['datasets','code','models','environment']}
        rec['execution'].update(performed=True,command=contract['execution']['command'],working_directory=contract['execution']['working_directory'],
            environment_path=contract['environment']['environment_path'],hostname='node23',resource_probe_path=str(log/'capacity-gate.json'),
            resource_usage_path=str(receipt),seeds=contract['execution']['seeds'],started_at=r['started_at'],ended_at=r['ended_at'],
            effective_deadline_at=contract['timing']['effective_deadline_at'],timeout_seconds=contract['execution']['timeout_seconds'],
            pid=r['pid'],pgid=r['pgid'],job_object_or_tree_control='Independent private PGID supervisor with CPU affinity/RSS/wall deadline',
            exit_code=r['exit_code'],timed_out=False,termination_reason=None,handles_absent_verified_at=r['ended_at'],
            exit_verification_path=str(receipt),stdout_path=str(log/'stdout.log'),stderr_path=str(log/'stderr.log'),receipt_path=str(receipt),
            notes='CPU only; actual affinity '+str(r['cpu_affinity'])+'; standard contract thread count '+str(contract['resources']['cpu_threads']))
        target=contract['targets'][0]
        comp={k:target.get(k) for k in ['target_id','paper_endpoint','metric','metric_definition','statistical_unit','denominator','unit','paper_value']}
        comp.update(actual_value=done['metrics']['MAE'],comparability='not_comparable',passed=None,absolute_difference=None,relative_difference=None,
            reason='New common-data denominator; original paper table numerical comparison not claimed',evidence_paths=[str(cp),str(log/'overall-prediction-audit.json')])
        rec['metric_comparisons']=[comp]
        files=[p for p in unit.rglob('*') if p.is_file()]+[receipt,log/'stdout.log',log/'stderr.log',log/'overall-prediction-audit.json']
        rec['artifacts']=[{'role':'actual new run evidence','path':str(p),'location':'local','available':True,
            'size_bytes':p.stat().st_size,'sha256':sha(p)} for p in files]
        rec['differences']=[{'category':'scope/runtime','description':'Frozen common-data benchmark with explicit CPU/runtime stratum; not original full-paper reproduction',
            'effect_on_comparison':'Report host/thread strata separately; no pure-seed SD claim','evidence_type':'source_fact','evidence_paths':[job['contract_path']]}]
        rec['incomplete_reasons']=[]
        rec['review'].update(status='accepted',reviewer='dta_build exact-unit evidence review',reviewed_at=stamp,
            checks=[{'item':k,'passed':True,'reason':'Exact frozen unit inputs, actual owned process terminal state and independent overall scores checked'} for k in ['identity','assets','contract','execution','comparison','claims','preservation']],
            evidence_paths=[str(receipt),str(cp),str(log/'overall-prediction-audit.json')])
        write(recordpath,rec)
        gate=subprocess.run([sys.executable,str(ROOT/'resources/validate_reproduction.py'),'--contract',job['contract_path'],
            '--result',str(recordpath),'--check-files'],capture_output=True,text=True,timeout=120)
        (log/'result-validation.json').write_text(gate.stdout,encoding='utf-8');(log/'result-validation.stderr.log').write_text(gate.stderr,encoding='utf-8')
        validation=json.loads(gate.stdout)
        summaries.append({'job_id':job['job_id'],'accepted':validation.get('valid_for_acceptance'),'errors':validation.get('errors')})
stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
out=HERE/'node23-cpu-recovery-v3'/('result-acceptance-'+stamp+'.json')
write(out,{'at':stamp,'records':summaries,'accepted':sum(x['accepted'] is True for x in summaries)})
print(json.dumps({'records':len(summaries),'accepted':sum(x['accepted'] is True for x in summaries),'path':str(out)}))
