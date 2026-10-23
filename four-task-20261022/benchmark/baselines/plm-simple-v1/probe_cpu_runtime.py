"""Read-only environment provenance for a new generic CPU-head contract."""
import hashlib
import importlib.metadata
import json
import platform
import socket
import sys
from pathlib import Path

import numpy
import pandas
import scipy
import sklearn
import joblib
import threadpoolctl

here=Path(__file__).resolve().parent
obj={'hostname':socket.gethostname(),'python':sys.version,'executable':sys.executable,
     'versions':{},'module_hashes':{},'shared_environment_modified':False}
for module in [numpy,pandas,scipy,sklearn,joblib,threadpoolctl]:
    obj['versions'][module.__name__]=getattr(module,'__version__',None)
    obj['module_hashes'][module.__name__]={'path':module.__file__,
        'sha256':hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()}
(here/'cpu-runtime-lock.json').write_text(json.dumps(obj,indent=2),encoding='utf-8')
print(json.dumps(obj))
