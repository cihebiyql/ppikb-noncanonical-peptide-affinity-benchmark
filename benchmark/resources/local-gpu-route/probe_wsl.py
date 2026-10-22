import importlib.metadata as md
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import sysconfig
import time

OUT = Path(__file__).resolve().parent
packages = ['torch', 'rdkit', 'torch-geometric', 'aiohttp', 'psutil', 'pyparsing', 'xxhash', 'numpy', 'scipy', 'fsspec', 'jinja2', 'requests', 'tqdm', 'packaging', 'typing-extensions', 'networkx', 'pandas', 'setuptools', 'sympy']
versions = {}
for name in packages:
    try:
        dist = md.distribution(name)
        versions[name] = {'version': dist.version, 'root': str(dist.locate_file('')), 'requires': dist.requires or []}
    except md.PackageNotFoundError:
        versions[name] = None
probes = []
for _ in range(3):
    result = {}
    for key, command in [('gpus', ['nvidia-smi', '--query-gpu=uuid,name,memory.total,memory.used,utilization.gpu', '--format=csv,noheader,nounits']), ('compute', ['nvidia-smi', '--query-compute-apps=pid,process_name,used_memory', '--format=csv,noheader,nounits'])]:
        call = subprocess.run(command, capture_output=True, text=True, timeout=10)
        result[key] = {'exit_code': call.returncode, 'stdout': call.stdout.strip(), 'stderr': call.stderr.strip()}
    result['time_epoch'] = time.time()
    probes.append(result)
    if any(result[k]['exit_code'] != 0 for k in ('gpus', 'compute')) or result['compute']['stdout']:
        break
    time.sleep(2)
receipt = {'python': sys.version, 'executable': sys.executable, 'platform': platform.platform(), 'machine': platform.machine(), 'SOABI': sysconfig.get_config_var('SOABI'), 'host': platform.node(), 'packages': versions, 'gpu_probes': probes, 'three_empty_compute_probes': len(probes) == 3 and all(not p['compute']['stdout'] and p['compute']['exit_code'] == 0 for p in probes)}
receipt['installed_distribution_versions'] = {d.metadata['Name']: d.version for d in md.distributions()}
(OUT / 'wsl-live-probe.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({k:v for k,v in receipt.items() if k != 'packages'}))
