"""Execute runtime canary, declared manual controls, and independent fixed-prediction checks."""
import json
from pathlib import Path
import subprocess
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
output=ROOT/'runs/plm-cohort-manual-controls-v1'
steps=[[sys.executable,'-B',str(HERE/'smoke_controls.py')],
       [sys.executable,'-B',str(HERE/'run_manual_controls.py'),'--manifest',str(HERE/'remote-manifest.json'),
        '--output',str(output),'--max-seconds','3300'],
       [sys.executable,'-B',str(HERE/'verify_manual_controls.py'),str(output)]]
for command in steps:
    print(json.dumps({'step':command}),flush=True);subprocess.run(command,check=True)
