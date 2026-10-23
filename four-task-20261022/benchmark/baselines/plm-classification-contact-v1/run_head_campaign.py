"""The two frozen binary tasks run after immutable means/residue caches have been assembled."""
import json
from pathlib import Path
import subprocess
import sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];RUN=ROOT/'runs/plm-classification-contact-v1/heads'
steps=[[sys.executable,'-B',str(HERE/'smoke_heads.py')],
       [sys.executable,'-B',str(HERE/'run_heads.py'),'--manifest',str(HERE/'inputs/remote-manifest.json'),
        '--output',str(RUN),'--max-seconds','6900'],
       [sys.executable,'-B',str(HERE/'verify_heads.py'),str(RUN)],
       [sys.executable,'-B',str(HERE/'summarize_binary_results.py')]]
for command in steps:
    print(json.dumps({'step':command}),flush=True);subprocess.run(command,check=True)
