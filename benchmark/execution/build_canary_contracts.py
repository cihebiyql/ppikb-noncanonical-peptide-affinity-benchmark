"""Generate root-authorized 1CPU/6GiB/120s contracts for five train-only canaries."""
from pathlib import Path
import json
import runner

HERE=Path(__file__).resolve().parent
REMOTE='/data/qlyu/projects/peptide-binding-nc-benchmark-20261021/execution'
def main():
    sample=runner.read_json(HERE/'canary-staging-v1/sample-manifest.json')
    target=HERE/'canary-contracts-v1'
    target.mkdir(exist_ok=False)
    for method in runner.METHOD_FOLDERS:
        contract=dict(stage='train-only-performance-canary',method_id=method,host='node23',cpu_threads=1,
                      memory_gib=6,timeout_seconds=120,seed=0,batch_size=32,gpu_count=0,
                      train_sample=REMOTE+'/canary-staging-v1/train-only-32.jsonl',
                      train_sample_sha256=sample['train_sample_sha256'],allowed_train_ids=sample['allowed_train_ids'],
                      methods_root=REMOTE+'/canary-methods-v1',
                      receipt_path=REMOTE+'/canary-contracts-v1/'+method+'-receipt.json',
                      python='/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/.venv/bin/python',
                      CUDA_VISIBLE_DEVICES='',optimizer='Adam',learning_rate=1e-3,weight_decay=0.,
                      optimizer_steps=4,architecture='unchanged_author_default',
                      labels='only 32 frozen NC_only train records; no validation/test/external files staged',
                      shared_label_container_controller_staging=sample['controller_opened_shared_label_container'])
        runner.write_json(target/(method+'-contract.json'),contract)
    print('Five bounded canary contracts generated, no jobs launched.')

if __name__=='__main__':main()
