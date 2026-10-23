"""CVD-hidden JIT source identity recheck; output goes to new issued directory."""
import argparse,os,sys,inspect,importlib.metadata,json
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']=''
for key in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[key]='1'
H=Path(__file__).resolve().parents[2];sys.path.insert(0,str(H))
from common import save,sha,now
import torch
import torch.autograd.graph as graph
import torch.utils.checkpoint as checkpoint
p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
D=Path(__file__).resolve().parent;lock=json.loads((D/'actual-descriptor-runtime-lock.json').read_text())
assert not Path(a.output).exists(),'Do not overwrite an earlier runtime/JIT receipt'
assert sys.executable==lock['sys_executable']
assert str(Path(sys.executable).resolve())==lock['sys_executable_resolved']
assert sys.prefix==lock['sys_prefix'] and sys.base_prefix==lock['sys_base_prefix']
assert str(torch.__version__)==lock['torch_version'] and torch.version.cuda==lock['torch_cuda_build']
assert {k:importlib.metadata.version(k) for k in lock['packages']}==lock['packages']
for item in lock['source_checks']:assert sha(item['actual_source_path'])==item['actual_source_sha256']
assert not torch.cuda.is_initialized()
save(a.output,{'at':now(),'status':'passed_JIT_actual_runtime_source_identity','sys_executable':sys.executable,'resolved_interpreter_sha256':sha(sys.executable),'torch_version':str(torch.__version__),'torch_cuda_build':torch.version.cuda,'source_file_SHA_matches_frozen_lock':True,'lock_sha256':sha(D/'actual-descriptor-runtime-lock.json'),'probe_sha256':sha(__file__),'cuda_initialized':False,'biological_NN_forwards':0,'GPU_calls':0})
print(sha(a.output))
