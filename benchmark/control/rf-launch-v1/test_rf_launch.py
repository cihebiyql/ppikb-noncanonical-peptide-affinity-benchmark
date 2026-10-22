"""Only synthetic metadata and sleeping-process mechanics; zero real RF fits."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
import rf_common as rc
import rf_pool as rp


class Fixture:
    def __init__(self,root):
        self.root=Path(root);self.project=self.root/'project';self.project.mkdir();self.binding_path=self.root/'binding.json'
        self.protected={self.root/'holdout-gold.jsonl',self.root/'model.joblib',self.root/'predictions.jsonl'}
        self.aux=self.project/'auxiliary-rf-baseline';self.aux.mkdir()
        self.assets={'candidate_profiles':[{'candidate_index':i,'effective_parameters_seed0':{'n_jobs':1,'n_estimators':200,'min_samples_leaf':leaf}} for i,leaf in enumerate((2,5))]}
        for name in rc.SOURCE_NAMES:
            (self.aux/name).write_text(json.dumps(self.assets) if name=='installed-assets-v1.json' else '# synthetic inert code\n' if name.endswith('.py') else '{}')
        self.files=[{'path':str(p),'sha256':rc.sha(p)} for p in [rc.HERE/n for n in ('rf_common.py','rf_pool.py','rf_unit.py')]+[rc.LAUNCH/'common.py']+[self.aux/n for n in rc.SOURCE_NAMES]]
        panel=self.project/'execution/prepared-panels-wsl-v3/source_peptide_dependency_cold';panel.mkdir(parents=True)
        self.spec={'method_id':rc.METHOD,'panel':'source_peptide_dependency_cold','regime':'NC_only','seed':0,'output_root':str(self.root/'future-output')}
        for key,name in [('train_rows','train.jsonl'),('validation_rows','validation.jsonl'),('train_ids','train-ids.json'),('validation_ids','validation-ids.json'),('feature_manifest','feature-manifest.json')]:
            p=panel/name;p.write_text('[]');self.spec[key]=str(p);self.spec[key+'_sha256']=rc.sha(p)
        self.spec['installed_assets']=str(self.aux/'installed-assets-v1.json');self.spec['installed_assets_sha256']=rc.sha(self.spec['installed_assets'])
        self.spec_ref=self.save('spec.json',self.spec)
        self.auth={'root_real_RF_fit_authorized':True,'allowed_spec_sha256':[self.spec_ref['sha256']],
                   'deadline_unix':1792633500.,'source_sha256':{n:rc.sha(self.aux/n) for n in rc.SOURCE_NAMES}}
        self.auth_ref=self.save('auth.json',self.auth)
        self.proof_ref=self.save('cpu-proof.json',{'hostname':'cihebi','at':'2026-10-21T18:18:40+00:00'})
        worker={'path':str(self.aux/'rf_runner.py'),'sha256':rc.sha(self.aux/'rf_runner.py')}
        self.binding={'schema':'rf-unit-binding-v1','issued':True,'unit_id':'RF-Classic__synthetic',
                      'expected_hostname':'cihebi','python':sys.executable,'PYTHONPATH':'synthetic','CUDA_VISIBLE_DEVICES':'',
                      'allowed_cpu_ids':[4,5,6,7],'deadline':'2026-10-22T01:45:00+00:00','timeout_seconds':1800,
                      'entrypoint_sha256':rc.sha(rc.HERE/'rf_unit.py'),'pool_sha256':rc.sha(rc.HERE/'rf_pool.py'),'common_sha256':rc.sha(rc.HERE/'rf_common.py'),
                      'authorization':self.auth_ref,'live_cpu_proof':self.proof_ref,'spec':self.spec_ref,'worker':worker,
                      'code_files':self.files,'receipt_root':str(rc.HERE/'synthetic-receipt-not-created')}
        self.contract={'is_template':False,'contract_status':'frozen','run_id':self.binding['unit_id'],
                       'execution':{'command':[sys.executable,str(rc.HERE/'rf_unit.py'),'--binding',str(self.binding_path)],'timeout_seconds':1800},
                       'timing':{'effective_deadline_at':self.binding['deadline'],'prior_window_expired':False,'retry_resets_clock':False},
                       'resources':{'expected_hostname':'cihebi','cpu_threads':1,'memory_limit_bytes':2*rc.GIB,'gpu_devices':[]},
                       'environment':{'environment_path':sys.prefix},
                       'benchmark_metadata':{'method_id':'RF-Classic','split_id':self.spec['panel'],'regime_id':'NC_only','seed':0},
                       'rf_execution_stage':{k:self.binding[k] for k in ('spec','authorization','live_cpu_proof','worker','code_files','receipt_root')}}
        contract_ref=self.save('contract.json',self.contract)
        self.binding['central_contract']=contract_ref
        self.binding['validation']=self.save('validation.json',{'valid_for_execution':True,'contract_sha256':contract_ref['sha256']})
        self.flush()

    def save(self,name,value):
        p=self.root/name;p.write_text(json.dumps(value),encoding='utf-8');return {'path':str(p),'sha256':rc.sha(p)}
    def flush(self):self.binding_path.write_text(json.dumps(self.binding),encoding='utf-8')


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.f=Fixture(self.temp.name)
        self.patchers=[mock.patch.object(rc,'PROJECT',self.f.project),mock.patch.object(rc,'runtime_gate'),mock.patch.object(rc,'private_pool_gate'),mock.patch.object(rc,'deadline',return_value=1792633500.)]
        for p in self.patchers:p.start()
        self.opens=[];original=Path.open
        def guard(p,*args,**kwargs):
            self.opens.append(str(p))
            if p in self.f.protected:raise AssertionError('Protected synthetic holdout/model/prediction accessed')
            return original(p,*args,**kwargs)
        self.guard=mock.patch.object(Path,'open',guard);self.guard.start()
    def tearDown(self):
        self.guard.stop()
        for p in self.patchers[::-1]:p.stop()
        self.temp.cleanup()
    def gate(self):self.f.flush();return rc.preflight(self.f.binding_path)
    def test_valid_gate_opens_no_holdout_or_weights(self):self.assertEqual(self.gate()['coordinate'],('source_peptide_dependency_cold','NC_only',0))
    def test_unissued_binding_rejects_before_spec(self):
        self.f.binding['issued']=False
        with self.assertRaises(PermissionError):self.gate()
        self.assertNotIn(self.f.spec_ref['path'],self.opens)
    def test_fit_authorization_false_rejects_before_spec(self):
        self.f.auth['root_real_RF_fit_authorized']=False;self.f.binding['authorization']=self.f.save('denied.json',self.f.auth)
        with self.assertRaises(PermissionError):self.gate()
        self.assertNotIn(self.f.spec_ref['path'],self.opens)
    def test_changed_code_blocks(self):
        (self.f.aux/'rf_runner.py').write_text('# changed')
        with self.assertRaises(ValueError):self.gate()
    def test_changed_train_input_blocks(self):
        Path(self.f.spec['train_rows']).write_text('["changed"]')
        with self.assertRaises(ValueError):self.gate()
    def test_model_cannot_be_a_code_proof(self):
        self.f.binding['code_files'].append({'path':str(self.f.root/'model.joblib'),'sha256':'0'*64})
        with self.assertRaises(ValueError):self.gate()
    def test_validator_requires_exact_contract_sha(self):
        self.f.binding['validation']=self.f.save('badval.json',{'valid_for_execution':True,'contract_sha256':'0'*64})
        with self.assertRaises(PermissionError):self.gate()
    def test_wrong_unit_timeout_blocked(self):
        self.f.binding['timeout_seconds']=60
        with self.assertRaises(ValueError):self.gate()
    def test_resume_requires_real_exit_proof_and_unchanged_artifacts(self):
        folder=self.f.root/'completed';folder.mkdir();artifact=folder/'candidate.txt';artifact.write_text('synthetic')
        p=folder/'unit-complete.json';p.write_text(json.dumps({'status':'complete','binding_sha256':'b'*64,'artifacts':[{'path':str(artifact),'sha256':rc.sha(artifact)}]}))
        (folder/'unit-complete.sha256').write_text(rc.sha(p))
        with self.assertRaises(FileNotFoundError):rc.validate_complete(folder,'b'*64)
        out=folder/'stdout.log';out.write_text('');err=folder/'stderr.log';err.write_text('')
        proof=folder/'pool-exit-verification.json';proof.write_text(json.dumps({'exit_code':0,'private_session_handles_absent':True,'binding_sha256':'b'*64,'stdout_path':str(out),'stdout_sha256':rc.sha(out),'stderr_path':str(err),'stderr_sha256':rc.sha(err)}))
        (folder/'pool-exit-verification.sha256').write_text(rc.sha(proof))
        self.assertEqual(rc.validate_complete(folder,'b'*64)['status'],'complete')
        artifact.write_text('changed')
        with self.assertRaises(ValueError):rc.validate_complete(folder,'b'*64)
    def test_clock_must_leave_full_1800_seconds(self):
        with mock.patch.object(rc.time,'time',return_value=1792632000.):
            with self.assertRaises(TimeoutError):self.gate()
    def test_source_auth_hash_must_match(self):
        self.f.auth['source_sha256']['rf_runner.py']='0'*64;self.f.binding['authorization']=self.f.save('badsource.json',self.f.auth)
        with self.assertRaises(ValueError):self.gate()


class Mechanics(unittest.TestCase):
    def test_launcher_imports_no_ML(self):
        for name in ('sklearn','numpy','torch','rdkit','rf_runner','rf_score'):self.assertNotIn(name,sys.modules)
    def test_full_window_cannot_shrink(self):
        self.assertFalse(rc.full_timeout_fits(1799,now=0));self.assertTrue(rc.full_timeout_fits(1800,now=0))
    def test_worker_and_pool_RSS_limits(self):
        states={'u':{'unit_monotonic_deadline':100}}
        self.assertEqual(rp.budget_decision(200,states,{'u':{'rss_bytes':2*rc.GIB+1}},0,wall=0,mono=0),'owned_RF_worker_RSS_above_2GiB')
        self.assertEqual(rp.budget_decision(200,states,{'u':{'rss_bytes':0}},8*rc.GIB+1,wall=0,mono=0),'owned_RF_pool_RSS_above_8GiB')
    def test_original_unit_global_and_writer_deadlines(self):
        states={'u':{'unit_monotonic_deadline':100}}
        self.assertEqual(rp.budget_decision(200,states,{},0,wall=0,mono=100),'original_RF_unit_1800sec_deadline')
        self.assertEqual(rp.budget_decision(200,states,{},0,wall=200,mono=0),'original_global_deadline')
        self.assertTrue(rp.budget_decision(200,states,{},0,writer_error='permission',wall=0,mono=0).startswith('persistent_writer_error'))
    def test_atomic_writer_retries_permission_without_shared_temp(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'progress.json';original=Path.replace;calls=[]
            def flaky(source,target):
                calls.append(source.name)
                if len(calls)<=2:raise PermissionError('synthetic reader lock')
                return original(source,target)
            with mock.patch.object(Path,'replace',flaky):rc.write(p,{'synthetic':True})
            self.assertEqual(json.loads(p.read_text()),{'synthetic':True});self.assertEqual(len(calls),3)
            self.assertNotEqual(calls[0],'progress.json.tmp')
    def test_persistent_IO_failure_bounded(self):
        with tempfile.TemporaryDirectory() as temp,mock.patch.object(Path,'replace',side_effect=PermissionError('synthetic persistent')) as replace,mock.patch.object(rc.time,'sleep'):
            with self.assertRaises(PermissionError):rc.write(Path(temp)/'p.json',{})
            self.assertEqual(replace.call_count,7)
    def test_progress_retry_does_not_block_independent_watchdog_ticks(self):
        with tempfile.TemporaryDirectory() as temp:
            original=Path.replace;calls=[];ticks=[];done=threading.Event()
            def flaky(source,target):
                calls.append(1)
                if len(calls)<=4:raise PermissionError('synthetic lock')
                return original(source,target)
            def ticker():
                while not done.wait(.1):ticks.append(time.monotonic())
            watcher=threading.Thread(target=ticker);watcher.start()
            with mock.patch.object(Path,'replace',flaky):
                writer=rc.ProgressWriter();event=writer.submit(Path(temp)/'progress.json',{'test':True})
                self.assertTrue(event.wait(3));writer.close()
            done.set();watcher.join();self.assertGreaterEqual(len(ticks),5)
    @unittest.skipUnless(os.name=='posix' and Path('/proc').exists(),'Linux private PGID required')
    def test_real_synthetic_private_PGID_cleanup(self):
        child=subprocess.Popen([sys.executable,'-c','import subprocess,sys,time;subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]);time.sleep(60)'],start_new_session=True)
        time.sleep(.3);self.assertTrue(rp.private_state(child.pid)['pids']);rp.cleanup(child.pid,child)
        self.assertFalse(rp.private_state(child.pid)['pids']);self.assertIsNotNone(child.returncode)
    def test_partial39_index_rejects_before_binding(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'index.json';p.write_text(json.dumps({'schema':'rf-unit-index-v1','issued':True,
                'supervisor_sha256':rc.sha(rc.HERE/'rf_pool.py'),'unit_sha256':rc.sha(rc.HERE/'rf_unit.py'),'common_sha256':rc.sha(rc.HERE/'rf_common.py'),
                'deadline':'2026-10-22T01:45:00+00:00','max_concurrent':4,'timeout_seconds':1800,
                'output_root':str(rc.HERE/'synthetic-pool-not-created'),'units':[{'unit_id':str(i)} for i in range(39)]}))
            with mock.patch.object(rp,'runtime_gate'),mock.patch.object(rp,'deadline',return_value=time.time()+5000),mock.patch.object(rp,'preflight') as gate:
                with self.assertRaises(ValueError):rp.verify_index(p,rc.sha(p))
                gate.assert_not_called()


if __name__=='__main__':unittest.main(verbosity=2)
