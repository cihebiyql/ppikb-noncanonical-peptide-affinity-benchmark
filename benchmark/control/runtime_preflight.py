"""Inspect the exact local execution runtime; construct or fit no model."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import torch
import torch_geometric
import rdkit
import scipy
import numpy
import psutil

def main():
    root=Path(__file__).resolve().parent.parent
    assert platform.node()=='cihebi'
    assert torch.cuda.is_available()
    torch.set_num_threads(2)
    torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cudnn.allow_tf32=False
    torch.backends.cudnn.benchmark=False
    torch.backends.cudnn.deterministic=True
    torch.use_deterministic_algorithms(True,warn_only=True)
    prop=torch.cuda.get_device_properties(0)
    snapshot=dict(schema='nc-local-training-runtime.v1',observed_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        hostname=platform.node(),pid=os.getpid(),python=sys.version,executable=sys.executable,
        sys_prefix=sys.prefix,torch=torch.__version__,torch_geometric=torch_geometric.__version__,
        PyG_module=torch_geometric.__file__,rdkit=rdkit.__version__,numpy=numpy.__version__,scipy=scipy.__version__,
        cuda_runtime=torch.version.cuda,CUDA_VISIBLE_DEVICES=os.environ.get('CUDA_VISIBLE_DEVICES'),
        PYTHONPATH=os.environ.get('PYTHONPATH'),GPU_name=prop.name,GPU_total_memory_bytes=prop.total_memory,
        available_host_memory_bytes=psutil.virtual_memory().available,
        numerical_policy=dict(parameter_dtype='float32',input_graph_dtype='float32',autocast=False,
            float32_matmul_precision=torch.get_float32_matmul_precision(),cuda_matmul_allow_tf32=torch.backends.cuda.matmul.allow_tf32,
            cudnn_allow_tf32=torch.backends.cudnn.allow_tf32,deterministic_algorithms=True,
            deterministic_warn_only=True,author_CUDA_nondeterminism_warnings_retained=True),
        raw_nvidia_smi=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits'],text=True),
        source_code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),models_constructed=0,models_fitted=0,
        environment_modified=False,route='existing generic WSL runtime plus task-local reused dependencies; not PLM helper execution')
    dest=root/'resources/local-gpu-route/runtime-freeze-for-training.json'
    dest.write_text(json.dumps(snapshot,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({k:v for k,v in snapshot.items() if k not in ['sys_prefix','raw_nvidia_smi','PYTHONPATH']},ensure_ascii=False))

if __name__=='__main__':main()
