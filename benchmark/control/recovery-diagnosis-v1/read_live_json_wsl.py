"""Optional observer for the owner: read active progress with POSIX sharing.

No writer, model, artifact cleanup or scoring code is called.
"""
from pathlib import Path
import argparse,json,os,re
ap=argparse.ArgumentParser();ap.add_argument('--path',required=True);args=ap.parse_args()
project=Path(__file__).resolve().parents[2];target=Path(args.path).resolve()
if os.name!='posix' or not target.is_relative_to(project) or target.name!='progress.json':raise ValueError('Use WSL and the owned project progress.json path')
data=json.loads(target.read_text(encoding='utf-8-sig'));reason=data.get('reason') or data.get('watchdog_reason') or ''
cls=re.search(r'(\w+Error)',reason);eno=re.search(r'\((\d+),',reason)
output={k:data.get(k) for k in ['status','at','complete_count','failed_count','pending','active','deadline']}
output.update(reason_class=cls.group(1) if cls else None,reason_errno=int(eno.group(1)) if eno else None,raw_error_message_omitted=True,observer='WSL POSIX read')
print(json.dumps(output,ensure_ascii=False))
