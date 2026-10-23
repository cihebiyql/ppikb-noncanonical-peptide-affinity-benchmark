import json,datetime as dt
from pathlib import Path
R=Path('/data/qlyu/projects/peptide-four-task-benchmark-20261022');p=R/'resources/routed-gpu-audit-node1.json';x=json.loads(p.read_text());rows=[]
for r in x['rows']:
 o=R/r['output_root'];rows.append({**r,'science_started_actual':(o/'started.json').exists(),'science_complete_file_actual':(o/'complete.json').exists()})
out=R/'methods/dta/gpu-route-terminal-history-node1.json';out.write_text(json.dumps({'at':dt.datetime.now(dt.timezone.utc).isoformat(),'rows':rows},indent=2));print(str(out))
