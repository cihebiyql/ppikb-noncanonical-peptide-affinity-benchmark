"""Read-only RDKit presence checks; no package installations."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

record = {"windows_python":sys.executable,"windows_rdkit_present":importlib.util.find_spec("rdkit") is not None,
          "new_packages_installed":False,"wsl_scope":"system python3 only, not a claim about every WSL environment"}
code = "import importlib.util,json,sys;print(json.dumps(dict(python=sys.executable,rdkit_present=importlib.util.find_spec('rdkit') is not None)))"
try:
    result = subprocess.run(["wsl.exe","-d","Ubuntu-22.04","--","python3","-B","-c",code],capture_output=True,text=True,timeout=20)
    record["wsl"] = {"exit_code":result.returncode,"stdout":result.stdout,"stderr":result.stderr}
except subprocess.TimeoutExpired:
    record["wsl"] = {"timeout_seconds":20}
path = Path(__file__).resolve().parent/"probes"/"windows-wsl-rdkit.json"
path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(record,ensure_ascii=False))
