"""Bounded read-only CPU runtime probe; no model or GPU allocation."""
import datetime
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys
import numpy
import torch
import torch_geometric
from rdkit import rdBase

root = Path(__file__).resolve().parents[2]
result = {'schema': 'fourtask.dta-cpu-runtime.v1',
          'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'hostname': socket.gethostname(), 'platform': platform.platform(),
          'python': sys.version, 'python_path': sys.executable, 'sys_prefix': sys.prefix,
          'numpy': numpy.__version__, 'torch': torch.__version__,
          'torch_geometric': torch_geometric.__version__, 'rdkit': rdBase.rdkitVersion,
          'CUDA_VISIBLE_DEVICES': os.environ.get('CUDA_VISIBLE_DEVICES'),
          'PYTHONPATH': os.environ.get('PYTHONPATH'),
          'torch_cuda_available': torch.cuda.is_available(),
          'meminfo': Path('/proc/meminfo').read_text(),
          'uptime': subprocess.check_output(['uptime'], text=True),
          'disk': dict(zip(('total', 'used', 'free'), shutil.disk_usage(root))),
          'model_imports': 0, 'models_constructed': 0, 'gpu_allocations': 0,
          'shared_environment_modified': False}
out = root/'methods/dta/cpu-fallback-v1/runtime-probe.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k != 'meminfo'}, ensure_ascii=False))
