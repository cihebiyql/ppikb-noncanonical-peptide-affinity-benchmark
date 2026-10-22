"""Synthetic metadata/process tests only, never actual gold or selected weights."""
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
import rfs_common as rc
import rf_score_pool as rp


class Fixture:
    def __init__(self,root):
        self.root=Path(root);self.project=self.root/'project';self.project.mkdir();self.binding_path=self.root/'binding.json'
        self.protected={self.root/'gold.jsonl',self.root/'weights.joblib',self.root/'predictions.jsonl'}
        aux=self.project/'auxiliary-rf-baseline';aux.mkdir();self.aux=aux
        self.index=self.project/'synthetic-index.json';self.index.write_text('{}')
        for name in rc.SOURCE_NAMES:
            text='# synthetic inert source\n' if name.endswith('.py') else '{}'
            if name=='rf_runner.py':text+="NN_APPROVED_INDEX_SHA="+repr(rc.sha(self.index))+"\nNN_APPROVED_INDEX_RELATIVE='synthetic-index.json'\n"
            (aux/name).write_text(text)
        metrics=self.project/'evaluation/metrics_stable.py';metrics.parent.mkdir();metrics.write_text('# synthetic inert metrics\n')
        self.files=[{'path':str(p),'sha256':rc.sha(p)} for p in [rc.HERE/n for n in ('rfs_common.py','rf_score_pool.py','rf_score_unit.py')]+[rc.TRAIN_COMMON,rc.LAUNCH/'common.py',metrics]+[aux/n for n in rc.SOURCE_NAMES]]
        self.source_sha={name:rc.sha(aux/name) for name in rc.SOURCE_NAMES}
        self.selected={'status':'frozen','validation_only':True,'gold_reads':0,'true_holdout_predictions':0,
                       'source_sha256':self.source_sha,'panel':'source_peptide_dependency_cold','regime':'NC_only','seed':0,
                       'model_path':str(self.root/'weights.joblib'),'model_sha256':'c'*64}
        self.selection_ref=self.save('selection.json',self.selected)
        self.entries=[]
        for panel in sorted(rc.PANELS):
            for regime in ('NC_only','standard_only'):
                for seed in range(10):
                    selected=(panel,regime,seed)==('source_peptide_dependency_cold','NC_only',0)
                    self.entries.append({'panel':panel,'regime':regime,'seed':seed,
                        'selection_path':self.selection_ref['path'] if selected else 'synthetic-rf-'+str(len(self.entries)),
                        'selection_sha256':self.selection_ref['sha256'] if selected else 'a'*64,'model_sha256':'c'*64})
        self.nn={'status':'all_selections_frozen','selection_count':200,'candidate_fit_count':400,
                 'selections':[{'path':'synthetic-nn-'+str(i),'sha256':'a'*64} for i in range(200)],
                 'execution_index_sha256':rc.sha(self.index)}
        self.rf={'status':'all_40_RF_selections_frozen','selection_count':40,'candidate_fit_count':80,'selections':self.entries}
        self.nn_ref=self.save('nn-barrier.json',self.nn);self.rf_ref=self.save('rf-barrier.json',self.rf)
        self.joint={'status':'all_200_NN_plus_40_RF_frozen','NN_selections':200,'RF_selections':40,'NN_candidate_fits':400,'RF_candidate_fits':80,
                    'NN_barrier_path':self.nn_ref['path'],'NN_barrier_sha256':self.nn_ref['sha256'],
                    'RF_barrier_path':self.rf_ref['path'],'RF_barrier_sha256':self.rf_ref['sha256'],
                    'RF_selection_entries':self.entries,'NN_execution_index_sha256':rc.sha(self.index)}
        self.joint_ref=self.save('joint.json',self.joint)
        input_path=self.root/'X-inputs.jsonl';input_path.write_text('{}\n');manifest=self.root/'X-manifest.json';manifest.write_text('{}')
        self.score_root=aux/'rf-scores-v1';self.spec_refs=[]
        for dataset in ('source_test','external75','supplement13'):
            spec={'method_id':rc.METHOD,'panel':'source_peptide_dependency_cold','dataset_id':dataset,
                  'cpu_threads':1,'n_jobs':1,'CUDA_VISIBLE_DEVICES':'','output_root':str(self.score_root),
                  'input_rows':str(input_path),'input_rows_sha256':rc.sha(input_path),
                  'feature_manifest':str(manifest),'feature_manifest_sha256':rc.sha(manifest),
                  'installed_assets':str(aux/'installed-assets-v1.json'),'gold_rows':str(self.root/'gold.jsonl')}
            self.spec_refs.append(self.save(dataset+'-spec.json',spec))
        self.auth={'root_RF_holdout_score_authorized':True,'allowed_score_spec_sha256':[r['sha256'] for r in self.spec_refs],
                   'source_sha256':self.source_sha,'joint_barrier_sha256':self.joint_ref['sha256'],
                   'frozen_stable_metrics_sha256':rc.sha(metrics),'deadline_unix':1792633500.}
        self.auth_ref=self.save('score-auth.json',self.auth)
        self.binding={'schema':'rf-score-unit-binding-v1','issued':True,'unit_id':'synthetic-RF__evaluation_v1',
                      'expected_hostname':'cihebi','python':sys.executable,'PYTHONPATH':'synthetic','CUDA_VISIBLE_DEVICES':'',
                      'allowed_cpu_ids':[4,5,6,7],'deadline':'2026-10-22T01:45:00+00:00','timeout_seconds':1800,
                      'entrypoint_sha256':rc.sha(rc.HERE/'rf_score_unit.py'),'pool_sha256':rc.sha(rc.HERE/'rf_score_pool.py'),'common_sha256':rc.sha(rc.HERE/'rfs_common.py'),
                      'selection':self.selection_ref,'score_specs':self.spec_refs,'authorization':self.auth_ref,
                      'joint_barrier':self.joint_ref,'NN_barrier':self.nn_ref,'RF_barrier':self.rf_ref,
                      'live_cpu_proof':self.save('cpu-proof.json',{'hostname':'cihebi','at':'2026-10-21T18:18:40+00:00'}),
                      'worker':{'path':str(aux/'rf_score.py'),'sha256':rc.sha(aux/'rf_score.py')},'code_files':self.files,
                      'receipt_root':str(rc.HERE/'synthetic-receipt-not-created'),'score_root':str(self.score_root)}
        self.contract={'is_template':False,'contract_status':'frozen','run_id':self.binding['unit_id'],
                       'execution':{'command':[sys.executable,str(rc.HERE/'rf_score_unit.py'),'--binding',str(self.binding_path)],'timeout_seconds':1800},
                       'timing':{'effective_deadline_at':self.binding['deadline'],'prior_window_expired':False,'retry_resets_clock':False},
                       'resources':{'expected_hostname':'cihebi','cpu_threads':1,'memory_limit_bytes':2*rc.GIB,'gpu_devices':[]},
                       'environment':{'environment_path':sys.prefix},
                       'benchmark_metadata':{'method_id':'RF-Classic','split_id':'source_peptide_dependency_cold','regime_id':'NC_only','seed':0},
                       'rf_score_execution_stage':{k:self.binding[k] for k in ('selection','score_specs','authorization','joint_barrier','NN_barrier','RF_barrier','live_cpu_proof','worker','code_files','receipt_root','score_root')}}
        ref=self.save('central-contract.json',self.contract);self.binding['central_contract']=ref
        self.binding['validation']=self.save('validation.json',{'valid_for_execution':True,'contract_sha256':ref['sha256']})
        self.flush()
    def save(self,name,value):
        p=self.root/name;p.write_text(json.dumps(value),encoding='utf-8');return {'path':str(p),'sha256':rc.sha(p)}
    def flush(self):self.binding_path.write_text(json.dumps(self.binding),encoding='utf-8')
    def update_joint(self):
        self.nn_ref=self.save('nn-barrier-mutated.json',self.nn);self.rf_ref=self.save('rf-barrier-mutated.json',self.rf)
        self.joint.update(NN_barrier_path=self.nn_ref['path'],NN_barrier_sha256=self.nn_ref['sha256'],RF_barrier_path=self.rf_ref['path'],RF_barrier_sha256=self.rf_ref['sha256'])
        self.joint_ref=self.save('joint-mutated.json',self.joint);self.auth['joint_barrier_sha256']=self.joint_ref['sha256']
        self.binding.update(joint_barrier=self.joint_ref,NN_barrier=self.nn_ref,RF_barrier=self.rf_ref,authorization=self.save('score-auth-mutated.json',self.auth))


class Gates(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.f=Fixture(self.temp.name);self.opens=[]
        self.patches=[mock.patch.object(rc,'PROJECT',self.f.project),mock.patch.object(rc,'runtime_gate'),mock.patch.object(rc,'private_pool_gate'),mock.patch.object(rc,'deadline',return_value=1792633500.)]
        for p in self.patches:p.start()
        original=Path.open
        def guard(p,*args,**kwargs):
            self.opens.append(str(p))
            if p in self.f.protected:raise AssertionError('Synthetic protected gold/weights/prediction read')
            return original(p,*args,**kwargs)
        self.guard=mock.patch.object(Path,'open',guard);self.guard.start()
    def tearDown(self):
        self.guard.stop()
        for p in self.patches[::-1]:p.stop()
        self.temp.cleanup()
    def gate(self):self.f.flush();return rc.preflight(self.f.binding_path)
    def test_valid_metadata_gate_no_model_gold_pred_reads(self):self.assertEqual(self.gate()['coordinate'],('source_peptide_dependency_cold','NC_only',0))
    def test_fit_permission_cannot_authorize_score(self):
        self.f.auth.pop('root_RF_holdout_score_authorized');self.f.auth['root_real_RF_fit_authorized']=True
        self.f.binding['authorization']=self.f.save('fit-only.json',self.f.auth)
        with self.assertRaises(PermissionError):self.gate()
        self.assertNotIn(self.f.selection_ref['path'],self.opens)
    def test_unissued_denied(self):
        self.f.binding['issued']=False
        with self.assertRaises(PermissionError):self.gate()
    def test_joint_NN199_denied_before_selection(self):
        self.f.nn['selection_count']=199;self.f.update_joint()
        with self.assertRaises(PermissionError):self.gate()
        self.assertNotIn(self.f.selection_ref['path'],self.opens)
    def test_RF39_denied_before_selection(self):
        self.f.rf['selection_count']=39;self.f.update_joint()
        with self.assertRaises(PermissionError):self.gate()
    def test_joint_RF_coordinate_grid_incomplete(self):
        self.f.joint['RF_selection_entries']=self.f.entries[:-1];self.f.update_joint()
        with self.assertRaises(PermissionError):self.gate()
    def test_wrong_source_proof_rejected(self):
        (self.f.aux/'rf_score.py').write_text('# changed')
        with self.assertRaises(ValueError):self.gate()
    def test_binary_cannot_be_code_proof(self):
        self.f.binding['code_files'].append({'path':str(self.f.root/'weights.joblib'),'sha256':'0'*64})
        with self.assertRaises(ValueError):self.gate()
    def test_validator_must_bind_actual_contract(self):
        self.f.binding['validation']=self.f.save('bad-val.json',{'valid_for_execution':True,'contract_sha256':'0'*64})
        with self.assertRaises(PermissionError):self.gate()
    def test_three_specs_exactly_required(self):
        self.f.binding['score_specs']=self.f.spec_refs[:2]
        with self.assertRaises(PermissionError):self.gate()
    def test_exact_spec_permission_required(self):
        self.f.binding['score_specs'][0]={'path':self.f.spec_refs[0]['path'],'sha256':'0'*64}
        with self.assertRaises(PermissionError):self.gate()
    def test_selection_must_be_in_joint(self):
        self.f.selected['seed']=1;self.f.binding['selection']=self.f.save('wrong-selection.json',self.f.selected)
        with self.assertRaises(PermissionError):self.gate()
    def test_whole_1800_original_window_required(self):
        with mock.patch.object(rc.time,'time',return_value=1792632000.):
            with self.assertRaises(TimeoutError):self.gate()
    def test_resume_SHA_and_actual_pool_exit_required(self):
        folder=self.f.root/'complete';folder.mkdir();scores=[]
        for i in range(3):
            p=folder/('score'+str(i)+'.json');p.write_text('{}');scores.append({'complete_path':str(p),'complete_sha256':rc.sha(p)})
        p=folder/'unit-complete.json';p.write_text(json.dumps({'status':'complete','binding_sha256':'b'*64,'scores':scores,'artifacts':[]}));(folder/'unit-complete.sha256').write_text(rc.sha(p))
        with self.assertRaises(FileNotFoundError):rc.validate_complete(folder,'b'*64)
        out=folder/'stdout.log';out.write_text('');err=folder/'stderr.log';err.write_text('')
        proof=folder/'pool-exit-verification.json';proof.write_text(json.dumps({'exit_code':0,'private_session_handles_absent':True,'binding_sha256':'b'*64,'stdout_path':str(out),'stdout_sha256':rc.sha(out),'stderr_path':str(err),'stderr_sha256':rc.sha(err)}));(folder/'pool-exit-verification.sha256').write_text(rc.sha(proof))
        self.assertEqual(rc.validate_complete(folder,'b'*64)['status'],'complete')
        (folder/'score0.json').write_text('changed')
        with self.assertRaises(ValueError):rc.validate_complete(folder,'b'*64)


class Mechanics(unittest.TestCase):
    def test_no_ML_imports(self):
        for name in ('numpy','sklearn','torch','rdkit','rf_runner','rf_score'):self.assertNotIn(name,sys.modules)
    def test_full_timeout_fit(self):self.assertFalse(rc.full_timeout_fits(1799,now=0));self.assertTrue(rc.full_timeout_fits(1800,now=0))
    def test_direct_unit_without_private_session_denied(self):
        with mock.patch.object(rc.os,'getpid',return_value=10),mock.patch.object(rc.os,'getpgrp',return_value=11,create=True):
            with self.assertRaises(RuntimeError):rc.private_pool_gate('/synthetic')
    def test_budget_worker_pool_and_clocks(self):
        states={'s':{'unit_monotonic_deadline':100}}
        self.assertEqual(rp.budget_decision(200,states,{'s':{'rss_bytes':2*rc.GIB+1}},0,wall=0,mono=0),'owned_RF_worker_RSS_above_2GiB')
        self.assertEqual(rp.budget_decision(200,states,{},8*rc.GIB+1,wall=0,mono=0),'owned_RF_pool_RSS_above_8GiB')
        self.assertEqual(rp.budget_decision(200,states,{},0,wall=200,mono=0),'original_global_deadline')
        self.assertEqual(rp.budget_decision(200,states,{},0,wall=0,mono=100),'original_RF_unit_1800sec_deadline')
    def test_partial39_index_denies_before_bindings(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'index.json';p.write_text(json.dumps({'schema':'rf-score-unit-index-v1','issued':True,
                'supervisor_sha256':rc.sha(rc.HERE/'rf_score_pool.py'),'unit_sha256':rc.sha(rc.HERE/'rf_score_unit.py'),'common_sha256':rc.sha(rc.HERE/'rfs_common.py'),
                'deadline':'2026-10-22T01:45:00+00:00','max_concurrent':4,'timeout_seconds':1800,'output_root':str(rc.HERE/'synthetic-pool-not-created'),
                'units':[{'unit_id':str(i)} for i in range(39)]}))
            with mock.patch.object(rp,'runtime_gate'),mock.patch.object(rp,'deadline',return_value=time.time()+5000),mock.patch.object(rp,'preflight') as gate:
                with self.assertRaises(ValueError):rp.verify_index(p,rc.sha(p))
                gate.assert_not_called()
    def test_writer_retries_without_blocking_budget_ticks(self):
        with tempfile.TemporaryDirectory() as temp:
            original=Path.replace;calls=[];ticks=[];done=threading.Event()
            def flaky(source,target):
                calls.append(1)
                if len(calls)<=4:raise PermissionError('synthetic shared lock')
                return original(source,target)
            def ticker():
                while not done.wait(.1):ticks.append(time.monotonic())
            t=threading.Thread(target=ticker);t.start()
            with mock.patch.object(Path,'replace',flaky):
                writer=rc.ProgressWriter();event=writer.submit(Path(temp)/'progress.json',{'test':True});self.assertTrue(event.wait(3));writer.close()
            done.set();t.join();self.assertGreaterEqual(len(ticks),5)
    def test_persistent_writer_failure_bounded(self):
        with tempfile.TemporaryDirectory() as temp,mock.patch.object(Path,'replace',side_effect=PermissionError('synthetic persistent')) as replace,mock.patch.object(rc._train.time,'sleep'):
            with self.assertRaises(PermissionError):rc.write(Path(temp)/'progress.json',{})
            self.assertEqual(replace.call_count,7)
    @unittest.skipUnless(os.name=='posix' and Path('/proc').exists(),'Linux private process sessions required')
    def test_synthetic_private_parent_child_cleanup(self):
        child=subprocess.Popen([sys.executable,'-c','import subprocess,sys,time;subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]);time.sleep(60)'],start_new_session=True)
        time.sleep(.3);self.assertTrue(rp.private_state(child.pid)['pids']);rp.cleanup(child.pid,child);self.assertFalse(rp.private_state(child.pid)['pids'])


if __name__=='__main__':unittest.main(verbosity=2)
