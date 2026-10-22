"""Execute only the five bounded contracts, max two 1CPU children concurrently."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import time

HERE=Path(__file__).resolve().parent
def one(path):
    contract=json.loads(path.read_text())
    assert os.uname().nodename=='node23'
    assert contract['cpu_threads']==1 and contract['memory_gib']<=6 and contract['timeout_seconds']==120
    log=path.with_name(path.stem.replace('-contract','')+'.log')
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    started=time.time()
    with log.open('w') as handle:
        process=subprocess.Popen(['timeout','--kill-after=5','120',contract['python'],str(HERE/'performance_canary.py'),
                                  '--contract',str(path)],cwd=HERE,env=env,stdout=handle,stderr=subprocess.STDOUT)
        returncode=process.wait(timeout=135)
    return dict(method_id=contract['method_id'],returncode=returncode,seconds=time.time()-started,
                pid=process.pid,contract=str(path),log=str(log),receipt_path=contract['receipt_path'])
def main():
    paths=sorted((HERE/'canary-contracts-v1').glob('*-contract.json'))
    assert len(paths)==5
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(one,paths))
    receipt=dict(stage='five_bounded_train_only_canaries',host=os.uname().nodename,max_parallel=2,
                 no_formal_candidate_training=True,results=results)
    (HERE/'canary-contracts-v1/launch-receipt.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
