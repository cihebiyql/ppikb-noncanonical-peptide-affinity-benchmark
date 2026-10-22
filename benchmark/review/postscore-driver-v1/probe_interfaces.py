"""Preparation only: CLI --help and denied synthetic joint metadata preflight."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).parent; REVIEW = HERE.parent
spec = importlib.util.spec_from_file_location('postscore_interface_paths', HERE / 'driver.py')
d = importlib.util.module_from_spec(spec); spec.loader.exec_module(d)
import numpy
results = []
commands = [('NN', REVIEW / 'recompute_metrics.py', ['--help']), ('references', REVIEW / 'deterministic_references.py', ['--help']),
    ('RF', REVIEW / 'recompute_RF_v5.py', ['--help']), ('combine', REVIEW / 'combine_audit_tables_v5.py', ['--help']),
    ('extension', REVIEW / 'nc_scope_extension_v6.py', ['audit', '--help']), ('merge', REVIEW / 'merge_metric_extension_v6.py', ['--help']),
    ('driver', HERE / 'driver.py', ['--help'])]
for name, file, args in commands:
    r = subprocess.run([sys.executable, str(file), *args], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
    if r.returncode: raise RuntimeError(name + ': ' + r.stderr)
    results.append(dict(name=name, exit_code=0, scope='help only; no data opened'))
with tempfile.TemporaryDirectory(prefix='SYNTHETIC_joint_denied_', dir=HERE) as folder:
    auth = Path(folder) / 'SYNTHETIC_auth.json'; auth.write_text(json.dumps({'root_joint_real_audit_authorized': False}))
    code = "import runpy,sys; m=runpy.run_path(sys.argv[1]); m['require_joint'](sys.argv[2],sys.argv[3],'nn')"
    r = subprocess.run(['wsl.exe', '--exec', '/usr/bin/python3', '-c', code, d.wsl(REVIEW / 'joint_audit_gate_v4.py'), d.wsl(auth), 'SYNTHETIC_NEVER_READ_JOINT'], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
    if r.returncode == 0 or 'PermissionError' not in r.stderr: raise RuntimeError('Expected original joint rejection: ' + r.stderr)
    results.append(dict(name='original_joint_function_denies_synthetic_auth_before_joint_read', exit_code=r.returncode, expected_rejection=True, metadata_only=True))
report = dict(status='passed', verified_python=sys.executable, numpy=numpy.__version__, checks=results,
    actual_full_joint_or_numeric_pipeline_executed=False, source_monkeypatched=False,
    actual_issuance_selections_gold_predictions_weights_labels_or_matrices_read=False,
    execution_split='Original joint require_joint function in WSL for metadata only; original numeric CLI help in Windows. Not an end-to-end run of original joint CLI wrapper.')
(HERE / 'interface-probe.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'status': 'passed', 'checks': len(results), 'numpy': numpy.__version__}))
