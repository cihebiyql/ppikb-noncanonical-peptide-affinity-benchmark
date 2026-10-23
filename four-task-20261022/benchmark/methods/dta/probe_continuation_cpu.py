import sys,socket,json,datetime as dt
from pathlib import Path
import torch,numpy,torch_geometric
from rdkit import rdBase
R=Path('/data/qlyu/projects/peptide-four-task-benchmark-20261022');p=R/'methods/dta/continuation-cpu-v1/probe-runtime.json';assert socket.gethostname()=='node23';assert not p.exists();x={'at':dt.datetime.now(dt.timezone.utc).isoformat(),'hostname':socket.gethostname(),'python':sys.version,'executable':sys.executable,'torch':torch.__version__,'numpy':numpy.__version__,'pyg':torch_geometric.__version__,'RDKit':rdBase.rdkitVersion,'shared_environment_modified':False};p.write_text(json.dumps(x,indent=2));print(json.dumps(x))
