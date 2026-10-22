"""Validate a frozen unit, fit exactly two LR candidates, then freeze selection.

No score command exists here. Child runners inherit this unit's process group.
"""
import argparse,os,sys,socket,time,subprocess,traceback,datetime
from pathlib import Path
from common import read,sha,path,checked,write,utc,deadline,epoch,GPU_UUID,HARD_DEADLINE

def preflight(args):
 if os.name!='posix' or os.getpgrp()!=os.getpid() or os.getsid(0)!=os.getpid() or str(os.getppid())!=os.environ.get('NC_POOL_OWNER_PID'):raise ValueError('Unit requires its supervising pool and private process session')
 specpath=checked(args.spec,args.spec_sha256);contractpath=checked(args.contract,args.contract_sha256);validationpath=checked(args.validation,args.validation_sha256)
 spec=read(specpath);contract=read(contractpath);validation=read(validationpath)
 if validation.get('valid_for_execution') is not True:raise ValueError('Validator did not permit execution')
 binding=validation.get('contract_sha256') or validation.get('launch_binding',{}).get('contract_sha256')
 if binding!=args.contract_sha256:raise ValueError('Validation is not bound to this exact contract')
 if 'central_validation_path' in validation:
  report=read(checked(validation['central_validation_path'],validation['central_validation_sha256']))
  if report.get('valid_for_execution') is not True:raise ValueError('Central validator did not permit execution')
 if contract.get('is_template') is not False or contract.get('contract_status')!='frozen':raise ValueError('Unissued contract')
 proof=spec.get('launch_proof') or contract.get('execution',{}).get('launch_proof')
 if not isinstance(proof,dict):raise ValueError('Missing actual launch asset proof')
 expected=proof['expected_hostname']
 if socket.gethostname()!=expected or contract['resources']['expected_hostname']!=expected:raise ValueError('Actual hostname mismatch')
 if path(contract['environment']['environment_path']).resolve()!=Path(sys.prefix).resolve():raise ValueError('Actual virtual environment mismatch')
 cutoff=deadline(args.deadline)
 if cutoff>epoch(contract['timing']['effective_deadline_at']):raise ValueError('Requested deadline exceeds contract clock')
 timeout=int(contract['execution']['timeout_seconds'])
 if not 0<timeout<=7200:raise ValueError('Per-unit timeout must be positive and <=7200 seconds')
 cutoff=min(cutoff,time.time()+timeout)
 if contract['timing'].get('prior_window_expired') is True:raise ValueError('Prior execution window is expired')
 if contract['timing'].get('retry_resets_clock') is not False:raise ValueError('Retry clock policy missing')
 if spec.get('device')!='cuda:0' or spec.get('gpu_explicitly_authorized') is not True:raise ValueError('Explicit GPU-only formal unit required')
 if os.environ.get('CUDA_VISIBLE_DEVICES')!=GPU_UUID:raise ValueError('Wrong actual GPU visibility')
 if not 0<int(spec.get('gpu_allocator_budget_bytes',0))<=3*1024**3:raise ValueError('Missing allocator budget')
 if int(spec.get('cpu_threads',0))!=2 or int(spec['max_epochs'])!=20 or int(spec['patience'])!=5:raise ValueError('Wrong formal CPU/epoch/patience budget')
 if spec['candidates']!=[{'learning_rate':.001,'weight_decay':0.0},{'learning_rate':.0003,'weight_decay':0.0}]:raise ValueError('Changed LR search')
 meta=contract['benchmark_metadata']
 if (spec['method_id'],spec['split_id'],spec['regime'],spec['seed'])!=(meta['method_id'],meta['split_id'],meta['regime_id'],meta['seed']):raise ValueError('Contract/spec scientific identity mismatch')
 if spec['method_id'] not in {'GraphDTA-GIN','MGraphDTA','DGDTA-CL','DeepNC-GEN','GS-DTA'}:raise ValueError('Not one of frozen five methods')
 runner=checked(proof['runner_path'],proof['runner_sha256'])
 files=proof.get('files',[])
 if not files:raise ValueError('No author/adapter code assets proved')
 for item in files:
  name=str(item['path']).lower()
  if path(item['path']).name in {'labels.jsonl','gold.jsonl','posttraining-gold.jsonl'} or any(x in name for x in ['sealed-test','test-inputs','external-validation/gold','external-validation\\gold']):raise ValueError('Holdout content excluded from fit launch proof')
  checked(item['path'],item['sha256'])
 for key in ['train_rows','validation_rows']:checked(spec[key],spec[key+'_sha256'])
 return spec,contract,proof,runner,cutoff

def validate_complete(root,specsha,contractsha,validationsha):
 checked(root/'unit-complete.json',(root/'unit-complete.sha256').read_text().strip())
 receipt=read(root/'unit-complete.json')
 if receipt.get('status')!='complete' or (receipt['spec_sha256'],receipt['contract_sha256'],receipt['validation_sha256'])!=(specsha,contractsha,validationsha):raise ValueError('Resume provenance mismatch')
 for file,expected in receipt['artifacts'].items():checked(file,expected)
 return receipt

def run_stage(argv,folder,name,cutoff):
 started=utc();start=time.monotonic();out=folder/(name+'.stdout.log');err=folder/(name+'.stderr.log')
 with out.open('xb') as stdout,err.open('xb') as stderr:
  process=subprocess.Popen(argv,stdout=stdout,stderr=stderr,env=os.environ.copy(),start_new_session=False)
  write(folder/(name+'.started.json'),{'argv':argv,'pid':process.pid,'pgid':os.getpgid(process.pid) if hasattr(os,'getpgid') else None,'parent_pid':os.getpid(),'started_at':started,'starts_new_session':False})
  timed_out=False
  while process.poll() is None:
   if time.time()>=cutoff:
    process.terminate()
    try:process.wait(timeout=3)
    except subprocess.TimeoutExpired:process.kill();process.wait()
    timed_out=True;break
   time.sleep(.2)
  receipt={'argv':argv,'pid':process.pid,'parent_pgid':os.getpgrp() if hasattr(os,'getpgrp') else None,'exit_code':process.returncode,'timed_out':timed_out,'started_at':started,'finished_at':utc(),'elapsed_seconds':time.monotonic()-start,'stdout':str(out),'stdout_sha256':sha(out),'stderr':str(err),'stderr_sha256':sha(err)}
  write(folder/(name+'.receipt.json'),receipt)
 if timed_out:raise TimeoutError('Original unit deadline reached; supervisor owns entire PGID watchdog')
 if process.returncode:raise RuntimeError(name+' exited '+str(process.returncode))
 return receipt

def execute(args):
 spec,contract,proof,runner,cutoff=preflight(args);folder=path(proof['receipt_root'])
 if folder.exists():
  if (folder/'unit-complete.json').exists():return {'status':'verified_complete_skipped','receipt':validate_complete(folder,args.spec_sha256,args.contract_sha256,args.validation_sha256)}
  raise FileExistsError('Existing failed/incomplete unit retained; no silent retry or new run')
 folder.mkdir(parents=True)
 write(folder/'unit-started.json',{'status':'running','unit_id':contract['run_id'],'pid':os.getpid(),'pgid':os.getpgrp(),'hostname':socket.gethostname(),'spec_sha256':args.spec_sha256,'contract_sha256':args.contract_sha256,'validation_sha256':args.validation_sha256,'requested_deadline':args.deadline,'global_deadline':contract['timing']['effective_deadline_at'],'effective_unit_deadline':datetime.datetime.fromtimestamp(cutoff,datetime.timezone.utc).isoformat(),'contract_timeout_seconds':contract['execution']['timeout_seconds'],'started_at':utc(),'test_label_reads':0,'external_label_reads':0})
 try:
  for index in [0,1]:run_stage([sys.executable,str(runner),'fit','--spec',str(path(args.spec)),'--candidate-index',str(index)],folder,'candidate-'+str(index),cutoff)
  run_stage([sys.executable,str(runner),'select','--spec',str(path(args.spec))],folder,'selection',cutoff)
  runroot=path(spec['run_root']);selection=read(runroot/'selection.json')
  if selection.get('status')!='frozen' or selection.get('fit_spec_sha256')!=args.spec_sha256:raise ValueError('Selection not frozen for spec')
  checked(selection['checkpoint'],selection['checkpoint_sha256'])
  artifacts={str(p):sha(p) for p in sorted(runroot.rglob('*')) if p.is_file()}
  artifacts.update({str(p):sha(p) for p in folder.iterdir() if p.is_file()})
  complete={'status':'complete','unit_id':contract['run_id'],'finished_at':utc(),'spec_sha256':args.spec_sha256,'contract_sha256':args.contract_sha256,'validation_sha256':args.validation_sha256,'selection':str(runroot/'selection.json'),'selection_sha256':sha(runroot/'selection.json'),'artifacts':artifacts,'test_label_reads':0,'external_label_reads':0,'score_started':False}
  write(folder/'unit-complete.json',complete);(folder/'unit-complete.sha256').write_text(sha(folder/'unit-complete.json')+'\n');return complete
 except BaseException as exc:
  write(folder/'unit-failed.json',{'status':'failed','finished_at':utc(),'error':repr(exc),'traceback':traceback.format_exc(),'deadline':args.deadline,'clock_reset':False});raise
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['spec','spec-sha256','contract','contract-sha256','validation','validation-sha256','deadline']:p.add_argument('--'+name,required=True)
 args=p.parse_args()
 try:result=execute(args)
 except BaseException as error:
  write(Path(__file__).parent/'rejections'/(str(time.time_ns())+'-'+str(os.getpid())+'.json'),{'status':'rejected_or_failed','at':utc(),'args':vars(args),'error':repr(error),'traceback':traceback.format_exc(),'actual_pid':os.getpid(),'score_started':False});raise
 print(__import__('json').dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
