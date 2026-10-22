"""Mechanical tests only: no model imports, GPU use, scientific fits or holdouts."""
import unittest,tempfile,subprocess,sys,os,time,json
from pathlib import Path
from common import sha,write,read,checked,process_table,stop_owned_group
from run_unit import run_stage,validate_complete
from pool_supervisor import ownership_gate,cache_gate
class LaunchTest(unittest.TestCase):
 def test_hash_rejects_mutation(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'input.txt';p.write_text('immutable');h=sha(p);checked(p,h);p.write_text('changed')
   with self.assertRaises(ValueError):checked(p,h)
 def test_actual_short_child_logs_exit_and_group(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);r=run_stage([sys.executable,'-c','import os,sys;print(os.getpid());print("mechanical_stderr",file=sys.stderr)'],p,'short',time.time()+10)
   self.assertEqual(r['exit_code'],0);self.assertIn('mechanical_stderr',(p/'short.stderr.log').read_text());self.assertEqual(r['stdout_sha256'],sha(p/'short.stdout.log'))
   if hasattr(os,'getpgrp'):self.assertEqual(read(p/'short.started.json')['pgid'],os.getpgrp())
 def test_actual_failed_child_keeps_receipt(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(RuntimeError):run_stage([sys.executable,'-c','import sys;print("mechanics_only");sys.exit(7)'],Path(d),'failed',time.time()+10)
   self.assertEqual(read(Path(d)/'failed.receipt.json')['exit_code'],7)
 def test_unknown_gpu_pid_blocks_without_signalling(self):
  okay,unknown=ownership_gate({'compute':[{'pid':1234},{'pid':5678}]},{1234})
  self.assertFalse(okay);self.assertEqual(unknown,[{'pid':5678}])
 def test_missing_or_mutated_cache_defers(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'cache.pkl';unit={'feature_cache_proofs':[{'path':str(p),'sha256':'0'*64}]};self.assertFalse(cache_gate(unit,True)[0]);p.write_text('cache');unit['feature_cache_proofs'][0]['sha256']=sha(p)
   memo={};self.assertTrue(cache_gate(unit,True,memo)[0]);p.write_text('changed-cache');self.assertFalse(cache_gate(unit,True,memo)[0])
 def test_resume_only_if_all_artifact_hashes_match(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);asset=root/'artifact';asset.write_text('mechanics_not_checkpoint')
   receipt={'status':'complete','spec_sha256':'a','contract_sha256':'b','validation_sha256':'c','artifacts':{str(asset):sha(asset)}};write(root/'unit-complete.json',receipt);(root/'unit-complete.sha256').write_text(sha(root/'unit-complete.json'))
   validate_complete(root,'a','b','c');asset.write_text('changed')
   with self.assertRaises(ValueError):validate_complete(root,'a','b','c')
 @unittest.skipUnless(os.name=='posix' and Path('/proc').exists(),'Linux owned session test')
 def test_real_private_session_tree_stop(self):
  p=subprocess.Popen([sys.executable,'-c','import subprocess,sys,time;subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"]);time.sleep(30)'],start_new_session=True)
  try:
   time.sleep(.3);self.assertTrue(any(r['pgid']==p.pid for r in process_table().values()));stop_owned_group(p.pid,grace=.1);p.wait(timeout=5)
   self.assertNotEqual(p.returncode,0)
  finally:
   if p.poll() is None:stop_owned_group(p.pid,grace=0);p.wait(timeout=5)
if __name__=='__main__':unittest.main()
