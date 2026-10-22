"""Synthetic JSON only. Exercise the existing frozen common.write unchanged."""
import argparse,json,sys,time,hashlib,os
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--target',required=True);ap.add_argument('--receipt',required=True);ap.add_argument('--scenario',required=True);args=ap.parse_args()
project=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(project/'launch'))
import common
expected='35c91d520885e6a447be2863ff7b60df91a8a2bfbc30c336fff7d7cbfd9a1632'
assert hashlib.sha256(Path(common.__file__).read_bytes()).hexdigest()==expected
p=Path(args.target);result={'scenario':args.scenario,'target':str(p),'pid':os.getpid(),'common_sha256':expected,'synthetic_only':True,'models_started':0,'before_exists':p.exists()}
try:
 common.write(p,{'synthetic_only':True,'scenario':args.scenario,'pid':os.getpid(),'write_time_ns':time.time_ns()})
 result.update(ok=True,error_class=None,errno=None,error_path=None,error_path2=None)
except BaseException as error:
 result.update(ok=False,error_class=type(error).__name__,errno=getattr(error,'errno',None),error_path=getattr(error,'filename',None),error_path2=getattr(error,'filename2',None))
result['temporary_exists_after']=(p.with_name(p.name+'.tmp')).exists()
result['target_sha256_after']=hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
Path(args.receipt).write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
