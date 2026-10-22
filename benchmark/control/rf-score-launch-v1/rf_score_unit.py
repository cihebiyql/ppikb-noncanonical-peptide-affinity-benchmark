"""One authorized RF selection, three frozen datasets, no fitting or tuning."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from rfs_common import HERE,HOST,METHOD,preflight,score_outputs,validate_complete,full_timeout_fits,path,read,sha,checked,write,utc

DATASET_COUNTS={'source_test':1039,'target_test':1443,'external75':75,'supplement13':13}


def score_stage(argv,folder,name,cutoff):
    out=folder/(name+'.stdout.log');err=folder/(name+'.stderr.log');started=utc();mono=time.monotonic()
    with out.open('xb') as stdout,err.open('xb') as stderr:
        child=subprocess.Popen(argv,stdout=stdout,stderr=stderr,env=os.environ.copy(),start_new_session=False)
        write(folder/(name+'.started.json'),{'argv':argv,'pid':child.pid,'pgid':os.getpgid(child.pid),'started_at':started,'new_session':False})
        timed_out=False
        while child.poll() is None:
            if time.time()>=cutoff:
                timed_out=True;child.terminate()
                try:child.wait(timeout=1)
                except subprocess.TimeoutExpired:child.kill();child.wait()
                break
            time.sleep(.2)
        result={'argv':argv,'pid':child.pid,'pgid':os.getpgrp(),'exit_code':child.returncode,'timed_out':timed_out,
                'direct_child_exited':not Path('/proc',str(child.pid)).exists(),'started_at':started,'ended_at':utc(),
                'elapsed_seconds':time.monotonic()-mono,'stdout_path':str(out),'stdout_sha256':sha(out),
                'stderr_path':str(err),'stderr_sha256':sha(err)}
        write(folder/(name+'.exit.json'),result)
    if timed_out:raise TimeoutError('Original1800sec three-score unit deadline reached')
    if child.returncode:raise RuntimeError(name+' exited '+str(child.returncode))
    return result


def execute(binding_path):
    context=preflight(binding_path,reserve=False);binding=context['binding'];bsha=sha(binding_path)
    folder=path(binding['receipt_root']);outputs=score_outputs(context)
    if folder.exists():
        if (folder/'unit-complete.json').exists():return {'status':'verified_complete_skipped','receipt':validate_complete(folder,bsha)}
        raise FileExistsError('Prior RF score attempt retained; no retry')
    if any(p.exists() for p in outputs):raise FileExistsError('Prior RF scores retained; no partial-unit retry')
    if not full_timeout_fits(context['cutoff']):raise TimeoutError('Full1800sec score window exceeds original cutoff')
    folder.mkdir(parents=True,exist_ok=False);started=utc();cutoff=min(context['cutoff'],time.time()+1800)
    write(folder/'unit-started.json',{'status':'running','unit_id':binding['unit_id'],'binding_sha256':bsha,'pid':os.getpid(),'pgid':os.getpgrp(),
          'parent_pool_pid':os.getppid(),'started_at':started,'CPU_affinity':sorted(os.sched_getaffinity(0)),
          'CUDA_VISIBLE_DEVICES':os.environ.get('CUDA_VISIBLE_DEVICES'),'global_deadline':binding['deadline'],
          'unit_deadline_epoch':cutoff,'selection_sha256':binding['selection']['sha256'],'joint_barrier_sha256':binding['joint_barrier']['sha256'],
          'gates_before_model_gold_reads':True,'scoring_only':True})
    try:
        scores=[]
        for i,(ref,spec,output) in enumerate(zip(binding['score_specs'],context['specs'],outputs)):
            argv=[sys.executable,str(context['worker']),'--authorization',str(path(binding['authorization']['path'])),
                  '--joint-barrier',str(path(binding['joint_barrier']['path'])),'--selection',str(path(binding['selection']['path'])),
                  '--spec',str(path(ref['path']))]
            result=score_stage(argv,folder,'score-'+str(i),cutoff)
            complete_path=output/'complete.json';receipt=read(complete_path)
            p,r,s=context['coordinate']
            if receipt.get('status')!='complete' or receipt.get('method_id')!=METHOD or (receipt['panel'],receipt['regime'],receipt['seed'])!=(p,r,s):raise ValueError('RF score receipt coordinate mismatch')
            if receipt['selection_sha256']!=binding['selection']['sha256'] or receipt['score_spec_sha256']!=ref['sha256'] or receipt['selected_model_sha256']!=context['selection']['model_sha256']:raise ValueError('RF score selected/spec/model SHA mismatch')
            if receipt.get('parameter_updates')!=0 or receipt.get('blind_before_gold') is not True or receipt.get('paper_count_contribution')!=0:raise ValueError('RF score must be blind-first without fitting')
            dataset=spec['dataset_id']
            if receipt['dataset_id']!=dataset or receipt['n']!=DATASET_COUNTS[dataset]:raise ValueError('RF score dataset/row count mismatch')
            for name,field in [('blind-predictions.jsonl','blind_predictions_sha256'),('predictions.jsonl','predictions_sha256')]:checked(output/name,receipt[field])
            scores.append({'dataset_id':dataset,'role':'internal' if dataset.endswith('_test') else dataset,'n':receipt['n'],
                           'complete_path':str(complete_path),'complete_sha256':sha(complete_path),'selected_model_sha256':receipt['selected_model_sha256'],
                           'predictions_sha256':receipt['predictions_sha256'],'blind_predictions_sha256':receipt['blind_predictions_sha256'],'stage':result})
        artifacts=[{'path':str(p),'sha256':sha(p)} for root in outputs+[folder] for p in sorted(root.rglob('*')) if p.is_file()]
        result={'status':'complete','unit_id':binding['unit_id'],'binding_sha256':bsha,'selection_sha256':binding['selection']['sha256'],
                'joint_barrier_sha256':binding['joint_barrier']['sha256'],'contract_sha256':binding['central_contract']['sha256'],
                'validation_sha256':binding['validation']['sha256'],'score_spec_sha256':[r['sha256'] for r in binding['score_specs']],
                'source_code_files':binding['code_files'],'scores':scores,'prediction_rows':sum(s['n'] for s in scores),'artifacts':artifacts,
                'pid':os.getpid(),'pgid':os.getpgrp(),'hostname':HOST,'started_at':started,'ended_at':utc(),'exit_code':None,
                'exit_verification_path':str(folder/'pool-exit-verification.json'),'global_deadline':binding['deadline'],'retry_resets_clock':False,
                'parameter_updates':0,'paper_count':0}
        write(folder/'unit-complete.json',result);(folder/'unit-complete.sha256').write_text(sha(folder/'unit-complete.json')+'\n')
        return result
    except BaseException as error:
        write(folder/'unit-failed.json',{'status':'failed','unit_id':binding['unit_id'],'binding_sha256':bsha,
              'error':repr(error),'traceback':traceback.format_exc(),'ended_at':utc(),'global_deadline':binding['deadline'],'retry_resets_clock':False})
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--binding',required=True);args=parser.parse_args()
    try:result=execute(args.binding)
    except BaseException as error:
        try:write(HERE/'rejections'/('unit-'+str(time.time_ns())+'-'+str(os.getpid())+'.json'),{'status':'rejected_or_failed','at':utc(),'error':repr(error),'binding_path':args.binding,'pid':os.getpid()})
        except Exception:pass
        raise
    print(__import__('json').dumps(result))


if __name__=='__main__':main()
