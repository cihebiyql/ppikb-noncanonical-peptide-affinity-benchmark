"""Run the preregistered training-row canary, then the three unchanged scientific views."""
import json
import subprocess
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
steps=[[sys.executable,'-B',str(HERE/'smoke_heads.py')],
       [sys.executable,'-B',str(HERE/'run_heads.py'),'--manifest',str(HERE/'inputs/remote-manifest.json'),
        '--output',str(ROOT/'runs/plm-simple-v1/heads'),'--max-seconds','5400'],
       [sys.executable,'-B',str(HERE/'verify_results.py'),str(ROOT/'runs/plm-simple-v1/heads')],
       [sys.executable,'-B',str(HERE/'summarize_strata.py'),str(ROOT/'runs/plm-simple-v1/heads')]]
for command in steps:
    print(json.dumps({'step':command}),flush=True)
    subprocess.run(command,check=True)
