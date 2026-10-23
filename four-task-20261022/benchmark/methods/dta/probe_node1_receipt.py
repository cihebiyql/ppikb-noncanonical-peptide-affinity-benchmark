import json
from pathlib import Path
R=Path('/data/qlyu/projects/peptide-four-task-benchmark-20261022');jid='ppikb_kd_source_cold_scope_v2--MGraphDTA--formal--seed2--no-cudnn-cache-v4--admission-v1'
d=R/'resources/mgraph-backend-v4/dispatch'/jid
print((d/'dispatch.json').read_text());c=json.loads((R/'resources/mgraph-backend-v4'/(jid+'.contract.json')).read_text());print(json.dumps({'execution':c['execution'],'resources':c['resources'],'targets':c['targets']},indent=2))
