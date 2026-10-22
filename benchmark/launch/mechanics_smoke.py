"""Retained subprocess mechanics evidence. Never runs any scientific model."""
import sys,time,os,json,socket
from pathlib import Path
from common import write,sha,utc
from run_unit import run_stage
P=Path(__file__).resolve().parent/'mechanics-v1'
def main():
 P.mkdir(exist_ok=False)
 cases=[]
 for name,code,cutoff in [('success','import os,sys;print("mechanics_only",os.getpid());print("stderr_kept",file=sys.stderr)',time.time()+10),('failure','import sys;print("expected_exit7");sys.exit(7)',time.time()+10),('deadline','import time;time.sleep(5)',time.time()+.05)]:
  try:
   run_stage([sys.executable,'-c',code],P,name,cutoff);status='complete'
  except Exception as error:status=repr(error)
  cases.append({'name':name,'actual_status':status,'receipt':str(P/(name+'.receipt.json'))})
 write(P/'summary.json',{'scope':'real short subprocess mechanics only; no model training, GPU or holdout use','host':socket.gethostname(),'python':sys.executable,'at':utc(),'pid':os.getpid(),'pgid':os.getpgrp(),'cases':cases,'scientific_fits':0,'files':{p.name:sha(p) for p in P.iterdir() if p.is_file()}})
 print(json.dumps({'scope':'mechanics_only','cases':cases},indent=2))
if __name__=='__main__':main()
