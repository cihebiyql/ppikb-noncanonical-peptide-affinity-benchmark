"""Self-owned POSIX reader plus frozen atomic writer, no model imports."""
import sys,json,hashlib,os
from pathlib import Path
p=Path(__file__).resolve().parent
sys.path.insert(0,str(p.parents[1]/'launch'))
import common
target=p/'wsl_reader.synthetic.json';target.write_text('{"synthetic_only":true,"old":true}')
with target.open('rb') as reader:
 before=reader.read();reader.seek(0)
 common.write(target,{'synthetic_only':True,'new':True})
 result={'scenario':'WSL_reader_open_while_atomic_replace','ok':True,'pid':os.getpid(),'error_class':None,'errno':None,'reader_still_sees_original_inode_bytes':reader.read()==before,'target_has_new_json':json.loads(target.read_text()).get('new') is True,'synthetic_only':True,'models_started':0}
(p/'wsl_reader.receipt.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
