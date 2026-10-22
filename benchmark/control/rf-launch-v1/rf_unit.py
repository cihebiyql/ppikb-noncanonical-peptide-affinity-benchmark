"""Run exactly one root-authorized CPU RF two-profile fit/selection unit."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from rf_common import HERE,HOST,preflight,validate_complete,full_timeout_fits,path,read,sha,checked,write,utc


def execute(binding_path):
    context=preflight(binding_path,reserve=False)
    binding,spec=context['binding'],context['spec'];bsha=sha(binding_path)
    receipts=path(binding['receipt_root']);output=path(spec['output_root'])
    if receipts.exists():
        if (receipts/'unit-complete.json').exists():return {'status':'verified_complete_skipped','receipt':validate_complete(receipts,bsha)}
        raise FileExistsError('Prior RF attempt retained; no automatic retry')
    if output.exists():raise FileExistsError('Prior RF candidates/output retained; no retry')
    if not full_timeout_fits(context['cutoff']):raise TimeoutError('Full 1800sec RF unit cannot fit original cutoff')
    receipts.mkdir(parents=True,exist_ok=False)
    started=utc();clock=time.monotonic();cutoff=min(context['cutoff'],time.time()+1800)
    argv=[sys.executable,str(context['worker']),'fit','--spec',str(path(binding['spec']['path'])),'--authorization',str(path(binding['authorization']['path']))]
    write(receipts/'unit-started.json',{'status':'running','unit_id':binding['unit_id'],'binding_sha256':bsha,
          'pid':os.getpid(),'pgid':os.getpgrp(),'parent_pool_pid':os.getppid(),'started_at':started,
          'argv':argv,'CUDA_VISIBLE_DEVICES':os.environ.get('CUDA_VISIBLE_DEVICES'),
          'CPU_affinity':sorted(os.sched_getaffinity(0)),'global_deadline':binding['deadline'],
          'unit_deadline_epoch':cutoff,'timeout_seconds':1800,'gold_reads':0,'score_started':False})
    out=receipts/'worker.stdout.log';err=receipts/'worker.stderr.log'
    try:
        with out.open('xb') as stdout,err.open('xb') as stderr:
            child=subprocess.Popen(argv,stdout=stdout,stderr=stderr,env=os.environ.copy(),start_new_session=False)
            write(receipts/'worker-started.json',{'argv':argv,'pid':child.pid,'pgid':os.getpgid(child.pid),'started_at':utc(),'new_session':False})
            timed_out=False
            while child.poll() is None:
                if time.time()>=cutoff:
                    timed_out=True;child.terminate()
                    try:child.wait(timeout=1)
                    except subprocess.TimeoutExpired:child.kill();child.wait()
                    break
                time.sleep(.2)
            worker_exit={'pid':child.pid,'pgid':os.getpgrp(),'exit_code':child.returncode,'timed_out':timed_out,
                         'direct_child_exited':not Path('/proc',str(child.pid)).exists(),'ended_at':utc(),
                         'stdout_path':str(out),'stdout_sha256':sha(out),'stderr_path':str(err),'stderr_sha256':sha(err)}
            write(receipts/'worker-exit.json',worker_exit)
        if timed_out:raise TimeoutError('Original RF unit deadline reached')
        if child.returncode:raise RuntimeError('RF worker exit '+str(child.returncode))
        selection=read(output/'selection.json')
        if selection.get('status')!='frozen' or selection.get('validation_only') is not True or selection.get('gold_reads')!=0 or selection.get('true_holdout_predictions')!=0 or selection['spec_sha256']!=binding['spec']['sha256']:
            raise ValueError('RF selection is not frozen train/validation-only')
        if (selection['panel'],selection['regime'],selection['seed'])!=context['coordinate']:raise ValueError('RF selected coordinate mismatch')
        candidates=selection['candidates']
        if len(candidates)!=2 or {c['candidate_index'] for c in candidates}!={0,1} or any(c['status']!='complete' for c in candidates):raise ValueError('Both RF candidates must be complete')
        winner=min(candidates,key=lambda c:(c['validation_MAE'],c['candidate_index']))
        if selection['candidate_index']!=winner['candidate_index'] or selection['model_sha256']!=winner['model_sha256']:raise ValueError('RF winner was not validation-MAE/tie-index choice')
        checked(selection['model_path'],selection['model_sha256'])
        top=read(output/'complete.json')
        if top.get('status')!='complete':raise ValueError('RF worker top-level completion absent')
        artifacts=[{'path':str(p),'sha256':sha(p)} for root in (output,receipts) for p in sorted(root.rglob('*')) if p.is_file()]
        complete={'status':'complete','unit_id':binding['unit_id'],'binding_sha256':bsha,
                  'spec_sha256':binding['spec']['sha256'],'contract_sha256':binding['central_contract']['sha256'],
                  'validation_sha256':binding['validation']['sha256'],'authorization_sha256':binding['authorization']['sha256'],
                  'source_code_files':binding['code_files'],'selection_path':str(output/'selection.json'),
                  'selection_sha256':sha(output/'selection.json'),'candidate_fit_count':2,'artifacts':artifacts,
                  'pid':os.getpid(),'pgid':os.getpgrp(),'hostname':HOST,'started_at':started,'ended_at':utc(),
                  'elapsed_seconds':time.monotonic()-clock,'exit_code':None,
                  'exit_verification_path':str(receipts/'pool-exit-verification.json'),
                  'worker_exit':worker_exit,'global_deadline':binding['deadline'],'retry_resets_clock':False,
                  'gold_reads':0,'score_started':False,'paper_count':0}
        write(receipts/'unit-complete.json',complete)
        (receipts/'unit-complete.sha256').write_text(sha(receipts/'unit-complete.json')+'\n')
        return complete
    except BaseException as error:
        write(receipts/'unit-failed.json',{'status':'failed','unit_id':binding['unit_id'],'binding_sha256':bsha,
              'error':repr(error),'traceback':traceback.format_exc(),'ended_at':utc(),'global_deadline':binding['deadline'],
              'retry_resets_clock':False,'gold_reads':0,'score_started':False})
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--binding',required=True);args=parser.parse_args()
    try:result=execute(args.binding)
    except BaseException as error:
        try:write(HERE/'rejections'/('unit-'+str(time.time_ns())+'-'+str(os.getpid())+'.json'),{'status':'rejected_or_failed','at':utc(),'error':repr(error),'binding_path':args.binding,'pid':os.getpid(),'score_started':False})
        except Exception:pass
        raise
    print(__import__('json').dumps(result))


if __name__=='__main__':main()
