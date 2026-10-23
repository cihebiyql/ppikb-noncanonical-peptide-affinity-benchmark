"""Read-only actual descriptor interpreter/source identity; CVD hidden, no NN."""
import os,sys,json,inspect,importlib.metadata
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']=''
for key in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[key]='1'
H=Path(__file__).resolve().parents[2];sys.path.insert(0,str(H))
from common import save,sha,now
import torch,torch.autograd.graph as graph,torch.utils.checkpoint as checkpoint
D=Path(__file__).resolve().parent
old=json.loads((D.parent/'activation-offload-prepare-v1/installed-Torch-source-inspection.json').read_text())
descriptor=json.loads((D.parent/'activation-offload-prepare-v1/scientific-descriptor.json').read_text())
expected_interpreter=descriptor['argv'][0]
assert Path(sys.executable).resolve()==Path(expected_interpreter).resolve()
assert str(torch.__version__)==old['torch_version']=='2.6.0+cu124'
objects={'save_on_cpu':graph.save_on_cpu,'saved_tensors_hooks':graph.saved_tensors_hooks,'checkpoint_nonreentrant_generator':checkpoint._checkpoint_without_reentrant_generator,'NoopSaveInputs':checkpoint._NoopSaveInputs,'checkpoint_hook':checkpoint._checkpoint_hook}
checks=[]
for entry in old['entries']:
    obj=objects[entry['symbol']];actual_path=inspect.getsourcefile(obj)
    text=inspect.getsource(obj)
    import hashlib
    digest=hashlib.sha256(text.encode()).hexdigest()
    assert sha(actual_path)==entry['installed_file_sha256']
    assert digest==entry['extracted_sha256']
    checks.append({'symbol':entry['symbol'],'actual_source_path':actual_path,'actual_source_sha256':sha(actual_path),'actual_extract_sha256':digest,'matches_original_reviewed_source':True})
record={'at':now(),'status':'passed_actual_descriptor_interpreter_runtime_mapping','invoked_descriptor_interpreter':expected_interpreter,'sys_executable':sys.executable,'sys_executable_resolved':str(Path(sys.executable).resolve()),'proc_self_exe_resolved':str(Path('/proc/self/exe').resolve()),'sys_prefix':sys.prefix,'sys_base_prefix':sys.base_prefix,'torch_version':str(torch.__version__),'torch_file':torch.__file__,'torch_cuda_build':torch.version.cuda,'source_checks':checks,'packages':{k:importlib.metadata.version(k) for k in ['torch','transformers','numpy','tokenizers']},'environment':{'CUDA_VISIBLE_DEVICES':os.environ['CUDA_VISIBLE_DEVICES'],'OMP_NUM_THREADS':os.environ['OMP_NUM_THREADS'],'MKL_NUM_THREADS':os.environ['MKL_NUM_THREADS'],'OPENBLAS_NUM_THREADS':os.environ['OPENBLAS_NUM_THREADS']},'cuda_initialized':torch.cuda.is_initialized(),'native_models_constructed':0,'model_forwards_optimizer_steps':0,'probe_source_sha256':sha(__file__),'original_descriptor_sha256':sha(D.parent/'activation-offload-prepare-v1/scientific-descriptor.json'),'reviewed_source_inspection_sha256':sha(D.parent/'activation-offload-prepare-v1/installed-Torch-source-inspection.json'),'required_future_JIT_gate':'Recompute actual graph.py/checkpoint.py source SHA and actual interpreter/Torch mapping using this same probe immediately before execution; mismatch stops before NN construction.'}
assert not record['cuda_initialized']
save(D/'actual-descriptor-runtime-lock.json',record);print(json.dumps(record))
