"""Synthetic-only gate/process tests. No real gold, selections or models opened."""
import copy
import datetime
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import score_common as sc
import score_pool as sp
import score_unit as su


class Fixture:
    def __init__(self, root):
        self.root=Path(root);self.project=self.root/'project';self.project.mkdir()
        self.protected={self.root/'gold.jsonl',self.root/'weights.pt',self.root/'predictions.jsonl'}
        self.selection={'status':'frozen','holdout_metrics_consulted':False,'method_id':'GraphDTA-GIN',
                        'split_id':'synthetic-source','regime':'NC_only','seed':0,
                        'checkpoint':str(self.root/'weights.pt'),'checkpoint_sha256':'c'*64}
        self.selection_ref=self.save('selection.json',self.selection)
        self.code=[]
        for p in [sc.HERE/n for n in ('score_common.py','score_pool.py','score_unit.py')]+[sc.LAUNCH/n for n in ('common.py','pool_supervisor.py','run_unit.py')]:
            self.code.append({'path':str(p),'sha256':sc.sha(p)})
        self.eval_dir=self.project/'evaluation';self.eval_dir.mkdir()
        for name in ('score_cached.py','common.py','feature_cache.py','metrics_stable.py'):
            p=self.eval_dir/name;p.write_text('# synthetic inert code\n');self.code.append({'path':str(p),'sha256':sc.sha(p)})
        self.runner=self.project/'runner.py';self.runner.write_text('# synthetic inert runner\n');self.code.append({'path':str(self.runner),'sha256':sc.sha(self.runner)})
        self.methods=self.project/'methods';self.method=self.methods/'graphdta-deepnc';self.method.mkdir(parents=True)
        p=self.method/'adapter.py';p.write_text('# synthetic no model\n');self.code.append({'path':str(p),'sha256':sc.sha(p)})
        self.score_root=self.project/'formal-runs-gpu-v4/scores'
        self.specs=[]
        for i,name in enumerate(('synthetic-internal','synthetic-external','synthetic-supplement')):
            spec={'dataset_id':name,'method_id':'GraphDTA-GIN','selection_split_id':'synthetic-source',
                  'output_root':str(self.score_root),'device':'cuda:0','gpu_explicitly_authorized':True,
                  'cpu_threads':2,'gpu_allocator_budget_bytes':3*sc.GIB,'runner':str(self.runner),
                  'methods_root':str(self.methods),'adapter_tree_sha256':sc.tree_hash(self.method),
                  'gold_rows':str(self.root/'gold.jsonl')}
            self.specs.append(self.save('spec-'+str(i)+'.json',spec))
        self.barrier={'status':'all_selections_frozen','selection_count':200,'candidate_fit_count':400,
                      'selections':[{'path':'synthetic-'+str(i),'sha256':'a'*64} for i in range(200)]}
        self.barrier_ref=self.save('barrier.json',self.barrier)
        eh={p.name:sc.sha(p) for p in self.eval_dir.glob('*.py')}
        self.audit={'status':'all_200_selections_and_checkpoints_verified',
                    'selections':[dict(path=self.selection_ref['path'] if i==0 else 'synthetic-'+str(i),sha256=self.selection_ref['sha256'] if i==0 else 'a'*64,checkpoint_sha256='c'*64) for i in range(200)],
                    'barrier_sha256':self.barrier_ref['sha256'],'execution_index_sha256':'d'*64,
                    'evaluation_code_sha256':eh}
        self.audit_ref=self.save('audit.json',self.audit)
        self.auth={'root_scoring_authorized':True,'allowed_phases':['score'],
                   'barrier_sha256':self.barrier_ref['sha256'],'barrier_audit_sha256':self.audit_ref['sha256'],
                   'execution_index_sha256':'d'*64,'evaluation_code_sha256':eh,
                   'runner_sha256':sc.sha(self.runner),'allowed_score_spec_sha256':[r['sha256'] for r in self.specs]}
        self.auth_ref=self.save('auth.json',self.auth)
        self.binding_path=self.root/'binding.json'
        self.contract={'is_template':False,'contract_status':'frozen','run_id':'synthetic__evaluation_v1',
                       'timing':{'effective_deadline_at':'2026-10-22T01:45:00+00:00','retry_resets_clock':False,'prior_window_expired':False},
                       'execution':{'command':[sys.executable,str(sc.HERE/'score_unit.py'),'--binding',str(self.binding_path)],'timeout_seconds':1200},
                       'resources':{'expected_hostname':'cihebi','cpu_threads':2,'memory_limit_bytes':4*sc.GIB,'gpu_memory_budget_bytes':3*sc.GIB,'gpu_devices':[sc.GPU_UUID]},'environment':{'environment_path':sys.prefix},
                       'benchmark_metadata':{'method_id':'GraphDTA-GIN','split_id':'synthetic-source','regime_id':'NC_only','seed':0},
                       'evaluation_stage':{'expected_score_receipts':3,'score_root':str(self.score_root),
                         'selection':self.selection_ref,'root_barrier':self.barrier_ref,'root_barrier_audit':self.audit_ref,
                         'root_score_authorization':self.auth_ref,'code_files':self.code,
                         'datasets':[{'role':role,'dataset_id':name,'n':1,'score_spec':ref} for role,name,ref in zip(('internal','external75','supplement13'),('synthetic-internal','synthetic-external','synthetic-supplement'),self.specs)]}}
        self.contract_ref=self.save('contract.json',self.contract)
        self.validation_ref=self.save('validation.json',{'valid_for_execution':True,'contract_sha256':self.contract_ref['sha256']})
        self.binding={'schema':'score-unit-binding-v1','issued':True,'unit_id':'synthetic__evaluation_v1',
                      'expected_hostname':'cihebi','python':sys.executable,'PYTHONPATH':'synthetic','gpu_uuid':sc.GPU_UUID,
                      'deadline':'2026-10-22T01:45:00+00:00','timeout_seconds':1200,
                      'entrypoint_sha256':sc.sha(sc.HERE/'score_unit.py'),'pool_sha256':sc.sha(sc.HERE/'score_pool.py'),
                      'common_sha256':sc.sha(sc.HERE/'score_common.py'),'authorization':self.auth_ref,
                      'barrier':self.barrier_ref,'audit':self.audit_ref,'central_contract':self.contract_ref,
                      'validation':self.validation_ref,'selection':self.selection_ref,'score_specs':self.specs,
                      'code_files':self.code,'receipt_root':str(sc.HERE/'synthetic-receipt-not-created'),'score_root':str(self.score_root)}
        self.flush()

    def save(self,name,value):
        p=self.root/name;p.write_text(json.dumps(value),encoding='utf-8');return {'path':str(p),'sha256':sc.sha(p)}

    def flush(self):self.binding_path.write_text(json.dumps(self.binding),encoding='utf-8')


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.f=Fixture(self.tmp.name)
        self.patchers=[mock.patch.object(sc,'PROJECT',self.f.project),mock.patch.object(sc,'runtime_gate'),
                       mock.patch.object(sc,'private_pool_gate'),mock.patch.object(sc,'deadline',return_value=1792633500.)]
        for p in self.patchers:p.start()
        self.opened=[]
        original=Path.open
        def guard(path,*args,**kwargs):
            self.opened.append(str(path))
            if path in self.f.protected:raise AssertionError('Synthetic protected model/gold/prediction opened')
            return original(path,*args,**kwargs)
        self.guard=mock.patch.object(Path,'open',guard);self.guard.start()

    def tearDown(self):
        self.guard.stop()
        for p in self.patchers[::-1]:p.stop()
        self.tmp.cleanup()

    def run_gate(self):
        self.f.flush();return sc.preflight(self.f.binding_path,now=1792620000.)

    def test_valid_metadata_gate_never_reads_model_gold_predictions(self):
        result=self.run_gate();self.assertEqual(len(result['specs']),3)

    def test_unissued_denied_before_auth_selection(self):
        self.f.binding['issued']=False
        with self.assertRaises(PermissionError):self.run_gate()
        self.assertNotIn(self.f.selection_ref['path'],self.opened)

    def test_unauthorized_denied_before_selection(self):
        self.f.auth['root_scoring_authorized']=False
        self.f.binding['authorization']=self.f.save('auth-denied.json',self.f.auth)
        with self.assertRaises(PermissionError):self.run_gate()
        self.assertNotIn(self.f.selection_ref['path'],self.opened)

    def test_incomplete_199_barrier_denied_before_selection(self):
        self.f.barrier['selection_count']=199
        ref=self.f.save('barrier-199.json',self.f.barrier)
        self.f.auth['barrier_sha256']=ref['sha256'];self.f.binding['barrier']=ref
        self.f.binding['authorization']=self.f.save('auth-199.json',self.f.auth)
        with self.assertRaises(PermissionError):self.run_gate()
        self.assertNotIn(self.f.selection_ref['path'],self.opened)

    def test_unit_timeout_cannot_exceed_original_window(self):
        self.f.flush()
        with self.assertRaises(TimeoutError):sc.preflight(self.f.binding_path,now=1792633000.)

    def test_binding_timeout_cannot_change(self):
        self.f.binding['timeout_seconds']=60
        with self.assertRaises(ValueError):self.run_gate()

    def test_validator_bound_contract_required(self):
        self.f.binding['validation']=self.f.save('badval.json',{'valid_for_execution':True,'contract_sha256':'0'*64})
        with self.assertRaises(PermissionError):self.run_gate()

    def test_code_mutation_blocks_before_model(self):
        self.f.runner.write_text('# changed\n')
        with self.assertRaises(ValueError):self.run_gate()

    def test_code_proof_cannot_point_to_gold(self):
        self.f.binding['code_files'].append({'path':str(self.f.root/'gold.jsonl'),'sha256':'0'*64})
        with self.assertRaises(ValueError):self.run_gate()

    def test_exact_three_score_specs_required(self):
        self.f.binding['score_specs']=self.f.specs[:2]
        with self.assertRaises(ValueError):self.run_gate()

    def test_unauthorized_spec_hash_blocked(self):
        self.f.binding['score_specs'][0]={'path':self.f.specs[0]['path'],'sha256':'0'*64}
        with self.assertRaises(PermissionError):self.run_gate()

    def test_selection_not_in_audit_blocked(self):
        self.f.selection['seed']=1
        self.f.binding['selection']=self.f.save('selection-mutated.json',self.f.selection)
        with self.assertRaises(PermissionError):self.run_gate()

    def test_resume_requires_complete_hash_and_real_pool_exit(self):
        root=self.f.root/'completed';root.mkdir();p=root/'unit-complete.json'
        scores=[]
        for i in range(3):
            file=root/('score-'+str(i)+'.json');file.write_text('{}')
            scores.append({'complete_path':str(file),'complete_sha256':sc.sha(file)})
        p.write_text(json.dumps({'status':'complete','binding_sha256':'b'*64,'scores':scores,'artifacts':[]}))
        (root/'unit-complete.sha256').write_text(sc.sha(p))
        with self.assertRaises(FileNotFoundError):sc.validate_complete(root,'b'*64)
        out=root/'stdout.log';out.write_text('synthetic stdout');err=root/'stderr.log';err.write_text('')
        proof=root/'pool-exit-verification.json';proof.write_text(json.dumps({'exit_code':0,'private_session_handles_absent':True,'binding_sha256':'b'*64,'stdout_path':str(out),'stdout_sha256':sc.sha(out),'stderr_path':str(err),'stderr_sha256':sc.sha(err)}))
        (root/'pool-exit-verification.sha256').write_text(sc.sha(proof))
        self.assertEqual(sc.validate_complete(root,'b'*64)['status'],'complete')
        (root/'score-0.json').write_text('{"changed":true}')
        with self.assertRaises(ValueError):sc.validate_complete(root,'b'*64)


class MechanicalTests(unittest.TestCase):
    def test_gate_modules_import_no_model_or_scoring_runtime(self):
        for module in ('torch','torch_geometric','rdkit','runner','score_cached'):
            self.assertNotIn(module,sys.modules)

    def test_original_clock_extension_denied(self):
        with self.assertRaises(ValueError):sc.deadline('2026-10-22T01:45:01+00:00')

    def test_no_shortened_unit_window(self):
        self.assertFalse(sp.full_timeout_fits(1000,now=0))
        self.assertTrue(sp.full_timeout_fits(1200,now=0))

    def test_unknown_compute_only_blocks_new_launch(self):
        okay,unknown=sp.ownership_gate({'compute':[{'pid':41},{'pid':42}]},{41})
        self.assertFalse(okay);self.assertEqual(unknown,[{'pid':42}])

    def test_pool_rejects_partial_199_unit_index_before_any_binding(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'index.json'
            value={'schema':'score-unit-index-v1','issued':True,'supervisor_sha256':sc.sha(sc.HERE/'score_pool.py'),
                   'unit_sha256':sc.sha(sc.HERE/'score_unit.py'),'common_sha256':sc.sha(sc.HERE/'score_common.py'),
                   'deadline':sc.HARD_DEADLINE,'output_root':str(sc.HERE/'synthetic-pool-not-created'),
                   'max_concurrent':1,'timeout_seconds':1200,'units':[{'unit_id':'synthetic-'+str(i)} for i in range(199)]}
            p.write_text(json.dumps(value))
            with mock.patch.object(sp,'runtime_gate'),mock.patch.object(sp,'deadline',return_value=time.time()+5000),mock.patch.object(sp,'preflight') as gate:
                with self.assertRaises(ValueError):sp.verify_index(p,sc.sha(p))
                gate.assert_not_called()

    def test_watchdog_RSS_limit(self):
        state={'monotonic_deadline':500}
        self.assertEqual(sp.watchdog_decision(1000,state,{'rss_bytes':4*sc.GIB+1},wall_now=0,mono_now=0),'owned_worker_RSS_above_4GiB')
        self.assertIsNone(sp.watchdog_decision(1000,state,{'rss_bytes':4*sc.GIB},wall_now=0,mono_now=0))

    def test_watchdog_global_and_original_unit_deadlines(self):
        state={'monotonic_deadline':500}
        self.assertEqual(sp.watchdog_decision(1000,state,{'rss_bytes':0},wall_now=0,mono_now=500),'unit_original_1200sec_deadline')
        self.assertEqual(sp.watchdog_decision(1000,state,{'rss_bytes':0},wall_now=1000,mono_now=0),'original_global_deadline')

    def test_private_pool_direct_invocation_rejected(self):
        with mock.patch.dict(os.environ,{},clear=True),mock.patch.object(sc.os,'getpid',return_value=10),mock.patch.object(sc.os,'getpgrp',return_value=11,create=True):
            with self.assertRaises(RuntimeError):sc.private_pool_gate('/synthetic',{})

    @unittest.skipUnless(os.name=='posix' and Path('/proc').is_dir(),'requires Linux private PGID controls')
    def test_cleanup_kills_only_owned_private_session(self):
        process=subprocess.Popen([sys.executable,'-c','import subprocess,sys,time;subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]);time.sleep(60)'],start_new_session=True)
        time.sleep(.3)
        self.assertTrue(sp.session_state(process.pid)['pids'])
        sp.cleanup_private(process.pid,process)
        self.assertFalse(sp.session_state(process.pid)['pids'])
        self.assertIsNotNone(process.returncode)


if __name__=='__main__':unittest.main(verbosity=2)
