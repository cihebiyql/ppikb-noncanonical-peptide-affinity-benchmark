"""Sequential cache and scaler acceptance checks; no model prediction or fitting."""
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
for name in ['verify_cache.py','verify_fitted_metadata.py']:
    command=[sys.executable,'-B',str(HERE/name)]
    print(json.dumps({'readonly_audit_command':command,'new_fit_count':0,'new_forward_count':0}),flush=True)
    subprocess.run(command,check=True,timeout=600)
