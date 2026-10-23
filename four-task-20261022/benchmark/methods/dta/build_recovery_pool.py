"""Generate a separate resource controller revision; original controller unchanged."""
from pathlib import Path
p=Path(__file__).resolve().parent
text=(p/'node23_cpu_pool.py').read_text(encoding='utf-8')
changes={"HERE=ROOT/'methods/dta/node23-cpu-v1'":"HERE=ROOT/'methods/dta/node23-cpu-recovery-v2'",
         "'max_DTA_workers':5":"'max_DTA_workers':11",
         'default=5)':'default=11)',
         '<=5:raise':'<=11:raise',
         "for s in data['jobs']":"for s in data.get('prerequisite_smokes',data['jobs'])"}
for old,new in changes.items():
    if old not in text:raise ValueError('Original controller changed; review before generating')
    text=text.replace(old,new)
target=p/'node23_cpu_pool_recovery_v2.py'
if target.exists():raise FileExistsError(target)
target.write_text(text,encoding='utf-8')
