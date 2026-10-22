"""Bounded three-dataset scoring entrypoint; only a private issued pool may run."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

from score_common import HERE, HOST, preflight, score_outputs, validate_complete, reference, path, read, sha, checked, write, utc


def run_stage(argv, folder, name, cutoff):
    out, err = folder / (name + '.stdout.log'), folder / (name + '.stderr.log')
    started_at, started = utc(), time.monotonic()
    with out.open('xb') as stdout, err.open('xb') as stderr:
        child = subprocess.Popen(argv, stdout=stdout, stderr=stderr, env=os.environ.copy(), start_new_session=False)
        write(folder / (name + '.started.json'), {'argv':argv, 'pid':child.pid,
              'pgid':os.getpgid(child.pid), 'parent_pid':os.getpid(), 'started_at':started_at,
              'new_process_session':False, 'unit_deadline_epoch':cutoff})
        timed_out = False
        while child.poll() is None:
            if time.time() >= cutoff:
                timed_out = True
                child.terminate()
                try:
                    child.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
                break
            time.sleep(.2)
        result = {'argv':argv, 'pid':child.pid, 'unit_pgid':os.getpgrp(), 'exit_code':child.returncode,
                  'timed_out':timed_out, 'started_at':started_at, 'ended_at':utc(),
                  'elapsed_seconds':time.monotonic()-started,
                  'stdout':str(out), 'stdout_sha256':sha(out),
                  'stderr':str(err), 'stderr_sha256':sha(err),
                  'direct_child_exited':not Path('/proc',str(child.pid)).exists()}
        write(folder / (name + '.receipt.json'), result)
    if timed_out:
        raise TimeoutError('Unit deadline reached; private pool owns whole-session cleanup')
    if child.returncode:
        raise RuntimeError(name + ' exited ' + str(child.returncode))
    return result


def execute(binding_path):
    context = preflight(binding_path, reserve_full_timeout=False)
    binding = context['binding']
    binding_sha = sha(binding_path)
    folder = path(binding['receipt_root'])
    if folder.exists():
        if (folder / 'unit-complete.json').exists():
            return {'status':'verified_complete_skipped', 'receipt':validate_complete(folder,binding_sha)}
        raise FileExistsError('Preserve prior incomplete/failed unit; no retry or overwrite')
    if time.time() + int(binding['timeout_seconds']) > context['deadline_epoch']:
        raise TimeoutError('Cannot start: full three-score timeout exceeds original deadline')
    outputs = score_outputs(context)
    if any(p.exists() for p in outputs):
        raise FileExistsError('Existing scoring output preserved; no partial-unit retry')
    folder.mkdir(parents=True,exist_ok=False)
    unit_started_at = utc()
    write(folder / 'unit-started.json', {'status':'running', 'unit_id':binding['unit_id'],
          'pid':os.getpid(), 'pgid':os.getpgrp(), 'session_id':os.getsid(0),
          'parent_pool_pid':os.getppid(), 'binding_sha256':binding_sha,
          'selection_sha256':binding['selection']['sha256'],
          'contract_sha256':binding['central_contract']['sha256'],
          'validation_sha256':binding['validation']['sha256'],
          'spec_sha256':[r['sha256'] for r in binding['score_specs']],
          'code_files':binding['code_files'], 'started_at':unit_started_at,
          'original_global_deadline':binding['deadline'],
          'unit_deadline_epoch':context['unit_cutoff_epoch'],
          'per_unit_timeout_seconds':binding['timeout_seconds'],
          'all_preflight_gates_before_model_or_gold':True})
    try:
        scores = []
        for index, (ref, output) in enumerate(zip(binding['score_specs'], outputs)):
            if time.time() >= context['unit_cutoff_epoch']:
                raise TimeoutError('Original scoring clock reached')
            argv = [sys.executable, str(HERE.parents[1] / 'evaluation/score_cached.py'), 'score',
                    '--authorization',str(path(binding['authorization']['path'])),
                    '--barrier',str(path(binding['barrier']['path'])),
                    '--barrier-audit',str(path(binding['audit']['path'])),
                    '--selection',str(path(binding['selection']['path'])),
                    '--spec',str(path(ref['path']))]
            stage = run_stage(argv, folder, 'score-' + str(index), context['unit_cutoff_epoch'])
            complete = output / 'complete.json'
            receipt = read(complete)
            if receipt.get('status') != 'complete' or receipt.get('selection_sha256') != binding['selection']['sha256'] or receipt.get('score_spec_sha256') != ref['sha256']:
                raise ValueError('Score output identity mismatch')
            for name, field in [('blind-predictions.jsonl','blind_predictions_sha256'),('predictions.jsonl','predictions_sha256')]:
                checked(output/name, receipt[field])
            dataset_id = context['specs'][index]['dataset_id']
            dataset_meta = next(d for d in context['contract']['evaluation_stage']['datasets'] if d['dataset_id'] == dataset_id)
            if receipt['n'] != dataset_meta['n']:
                raise ValueError('Scored row count differs from frozen evaluation contract')
            scores.append({'complete_path':str(complete), 'complete_sha256':sha(complete),
                           'dataset_id':dataset_id, 'role':dataset_meta['role'], 'n':receipt['n'], 'stage':stage})
        artifacts = []
        for root in outputs + [folder]:
            for p in sorted(root.rglob('*')):
                if p.is_file():
                    artifacts.append({'path':str(p), 'sha256':sha(p)})
        result = {'status':'complete', 'unit_id':binding['unit_id'],
                  'binding_sha256':binding_sha, 'selection_sha256':binding['selection']['sha256'],
                  'contract_sha256':binding['central_contract']['sha256'],
                  'validation_sha256':binding['validation']['sha256'],
                  'spec_sha256':[r['sha256'] for r in binding['score_specs']],
                  'code_files':binding['code_files'], 'scores':scores, 'artifacts':artifacts,
                  'pid':os.getpid(), 'pgid':os.getpgrp(), 'ended_at':utc(),
                  'execution':{'performed':True, 'hostname':HOST, 'pid':os.getpid(), 'pgid':os.getpgrp(),
                      'started_at':unit_started_at, 'ended_at':utc(), 'exit_code':None,
                      'exit_status':'verified separately by supervising pool after this unit exits',
                      'stdout_path':os.environ.get('NC_SCORE_UNIT_STDOUT_PATH'),
                      'stderr_path':os.environ.get('NC_SCORE_UNIT_STDERR_PATH'),
                      'exit_verification_path':str(folder/'pool-exit-verification.json')},
                  'global_deadline':binding['deadline'], 'retry_clock_reset':False,
                  'claim':'Three post-barrier frozen-model score calls; no fitting or parameter update'}
        write(folder/'unit-complete.json',result)
        (folder/'unit-complete.sha256').write_text(sha(folder/'unit-complete.json')+'\n')
        return result
    except BaseException as error:
        write(folder/'unit-failed.json', {'status':'failed', 'unit_id':binding['unit_id'],
              'error':repr(error), 'traceback':traceback.format_exc(), 'ended_at':utc(),
              'binding_sha256':binding_sha, 'global_deadline':binding['deadline'],
              'retry_clock_reset':False})
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binding',required=True)
    args=parser.parse_args()
    try:
        result=execute(args.binding)
    except BaseException as error:
        write(HERE/'rejections'/('unit-'+str(time.time_ns())+'-'+str(os.getpid())+'.json'),
              {'status':'rejected_or_failed', 'at':utc(), 'binding_path':args.binding,
               'error':repr(error), 'pid':os.getpid(), 'scorer_gate_required_before_reads':True})
        raise
    print(__import__('json').dumps(result))


if __name__=='__main__':main()
