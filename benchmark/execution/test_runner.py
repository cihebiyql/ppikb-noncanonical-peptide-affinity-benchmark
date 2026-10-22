"""Execution-contract tests with a disposable linear fixture, not a sixth baseline."""
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
import torch
import runner

FIXTURE = '''import torch
class Model(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.linear=torch.nn.Linear(1,1)
    def forward(self,x): return self.linear(x).reshape(-1)
def encode_record(row): return dict(x=float(len(row['target_sequence'])),y=float(row['pKd']))
def collate(items): return dict(x=torch.tensor([[i['x']] for i in items]),y=torch.tensor([i['y'] for i in items]))
def build_model(method_id,config): return Model()
def predict(model,batch,device): return model(batch['x'].to(device))
def batch_targets(batch): return batch['y']
'''

class Tests(unittest.TestCase):
    def test_metrics_empty_small_constant_nonfinite(self):
        self.assertEqual(runner.numeric_metrics([],[])['MAE'],None)
        self.assertEqual(runner.numeric_metrics([1],[2])['Pearson'],None)
        metrics=runner.numeric_metrics([1,1],[1,2])
        self.assertIsNone(metrics['R2'])
        self.assertIsNone(metrics['Spearman'])
        self.assertEqual(runner.numeric_metrics([1,2],[1,2])['R2'],1)
        with self.assertRaises(ValueError): runner.numeric_metrics([1],[float('nan')])

    def test_seed_reproducibility(self):
        runner.seed_everything(7,1)
        first=(random.random(),np.random.rand(),torch.rand(2))
        runner.seed_everything(7,1)
        second=(random.random(),np.random.rand(),torch.rand(2))
        self.assertEqual(first[:2],second[:2])
        self.assertTrue(torch.equal(first[2],second[2]))

    def test_fit_select_then_score_procedural_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            folder=root/'methods/graphdta-deepnc'
            folder.mkdir(parents=True)
            (folder/'adapter.py').write_text(FIXTURE)
            rows=[dict(record_id=str(i),pKd=float(i)/3,target_sequence='A'*(i+1),peptide_smiles='CC',
                       NC_core=i%2==0,evaluation_stratum='PTM' if i%2==0 else 'standard',
                       study_id='fixture',target_id='fixture',discordant_flag=False) for i in range(15)]
            runner.write_jsonl(root/'observations.jsonl',rows)
            runner.write_json(root/'split.json',dict(split_id='fixture',train=[str(i) for i in range(8)],
                              validation=[str(i) for i in range(8,12)],test=[str(i) for i in range(12,15)]))
            runner.prepare_panel(root/'observations.jsonl',root/'split.json',root/'panel')
            spec=dict(method_id='GraphDTA-GIN',regime='NC_only',seed=0,split_id='fixture',
                      validation_scope='same_as_regime',max_epochs=2,patience=1,batch_size=2,
                      gradient_accumulation=1,cpu_threads=1,device='cpu',
                      run_root=str(root/'run'),cache_root=str(root/'cache'),methods_root=str(root/'methods'),
                      train_rows=str(root/'panel/train.jsonl'),validation_rows=str(root/'panel/validation.jsonl'))
            for key in ('train_rows','validation_rows'): spec[key+'_sha256']=runner.sha_file(spec[key])
            runner.write_json(root/'fit.json',spec)
            original=runner.read_jsonl
            accesses=[]
            def guarded(path):
                accesses.append(str(path))
                self.assertNotIn('test',Path(path).name)
                self.assertNotIn('sealed',Path(path).name)
                return original(path)
            with patch.object(runner,'read_jsonl',guarded):
                for index in (0,1): runner.train_candidate(root/'fit.json',index)
                selection=runner.select_candidate(root/'fit.json')
            self.assertFalse(selection['holdout_metrics_consulted'])
            self.assertEqual(len(accesses),4)
            for index in (0,1):
                complete=runner.read_json(root/'run'/('candidate-'+str(index))/'complete.json')
                self.assertEqual(complete['train_n'],4)
                self.assertEqual(complete['validation_n'],2)
                self.assertEqual(complete['test_label_reads'],0)
            with self.assertRaises(FileExistsError): runner.select_candidate(root/'fit.json')
            holdout=dict(split_id='fixture',holdout_id='test',output_root=str(root/'score'),
                         input_rows=str(root/'panel/test-inputs.jsonl'),
                         label_rows=str(root/'panel/sealed-test-labels.jsonl'),
                         methods_root=str(root/'methods'),cpu_threads=1)
            for key in ('input_rows','label_rows'):holdout[key+'_sha256']=runner.sha_file(holdout[key])
            holdout['selection_barrier_path']=str(root/'not-yet-frozen.json')
            runner.write_json(root/'holdout-blocked.json',holdout)
            with patch.object(runner,'read_jsonl',side_effect=AssertionError('Holdout read before barrier')):
                with self.assertRaises(FileNotFoundError):
                    runner.score_holdout(root/'run/selection.json',root/'holdout-blocked.json')
            holdout.pop('selection_barrier_path')
            runner.write_json(root/'holdout.json',holdout)
            score=runner.score_holdout(root/'run/selection.json',root/'holdout.json')
            self.assertEqual(score['n'],3)
            self.assertTrue(score['no_parameter_updates'])

    def test_no_pooled_or_holdout_key(self):
        spec=dict(method_id='GraphDTA-GIN',regime='pooled',seed=0,validation_scope='NC_only',max_epochs=30,
                  patience=5,batch_size=32,gradient_accumulation=1)
        with self.assertRaises(ValueError):runner.validate_fit_spec(spec)
        spec.update(regime='NC_only',test_label_path='forbidden')
        with self.assertRaises(ValueError):runner.validate_fit_spec(spec)

    def test_conflict_sensitivity_reuses_predictions(self):
        rows=[dict(record_id='a',pKd=1.,NC_core=True,evaluation_stratum='PTM',graph_annotation_discordant=True),
              dict(record_id='b',pKd=2.,NC_core=True,evaluation_stratum='PTM',graph_annotation_discordant=False)]
        metrics=runner.grouped_metrics(rows,[4.,2.])
        self.assertEqual(metrics['all']['n'],2)
        self.assertEqual(metrics['exclude_discordant_sensitivity']['n'],1)
        self.assertEqual(metrics['exclude_discordant_sensitivity']['MAE'],0.)

    def test_cuda_authorization_availability_and_allocator_guard(self):
        with patch.object(torch.cuda,'is_available') as available:
            with self.assertRaises(ValueError):runner.configure_device(dict(device='cuda:0'))
            available.assert_not_called()
        with patch.object(torch.cuda,'is_available',return_value=False):
            with self.assertRaises(RuntimeError):
                runner.configure_device(dict(device='cuda:0',gpu_explicitly_authorized=True))
        with patch.object(torch.cuda,'is_available',return_value=True), \
             patch.object(torch.cuda,'device_count',return_value=1), \
             patch.object(torch.cuda,'get_device_properties',return_value=SimpleNamespace(total_memory=16*1024**3)), \
             patch.object(torch.cuda,'get_device_name',return_value='mock-device'), \
             patch.object(torch.cuda,'set_per_process_memory_fraction') as fraction:
            receipt=runner.configure_device(dict(device='cuda:0',gpu_explicitly_authorized=True,
                                                  gpu_allocator_budget_bytes=3*1024**3))
            fraction.assert_called_once_with(3/16,device=0)
            self.assertEqual(receipt['gpu_allocator_budget_bytes'],3*1024**3)
            with self.assertRaises(ValueError):
                runner.configure_device(dict(device='cuda:0',gpu_explicitly_authorized=True,
                                             gpu_allocator_budget_bytes=4*1024**3))

    def test_formal_registry_keeps_mrb_only_as_supported_interface(self):
        self.assertEqual(set(runner.FORMAL_METHOD_IDS),{'GraphDTA-GIN','MGraphDTA','DGDTA-CL','DeepNC-GEN','GS-DTA'})
        self.assertIn('MRBDTA',runner.METHOD_FOLDERS)
        self.assertNotIn('MRBDTA',runner.FORMAL_METHOD_IDS)

    def test_gpu_builder_grid_is_spec_only_and_twenty_epochs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            rows=[dict(record_id=str(i),pKd=float(i),NC_core=i%2==0,
                       evaluation_stratum='PTM' if i%2==0 else 'standard') for i in range(12)]
            runner.write_jsonl(root/'observations.jsonl',rows)
            panels=[]
            for name in ('panel_a','panel_b'):
                runner.write_json(root/(name+'.json'),dict(split_id=name,train=['0','1','2','3','4','5'],
                                  validation=['6','7','8','9'],test=['10','11']))
                runner.prepare_panel(root/'observations.jsonl',root/(name+'.json'),root/name)
                panels.append(dict(split_id=name,directory=str(root/name)))
            runner.write_json(root/'panels.json',panels)
            subprocess.run([sys.executable,str(Path(__file__).parent/'build_specs.py'),
                '--panels',str(root/'panels.json'),'--output',str(root/'specs'),
                '--run-root',str(root/'runs'),'--cache-root',str(root/'cache'),'--methods-root',str(root/'methods'),
                '--batch-size','32','--cpu-threads','2','--device','cuda:0','--gpu-explicitly-authorized'],check=True,
                capture_output=True,text=True)
            index=runner.read_json(root/'specs/execution-index.json')
            self.assertEqual(index['total_fits'],400)
            self.assertEqual(index['total_selections'],200)
            self.assertEqual(index['max_epochs'],20)
            methods=set()
            for entry in index['per_seed_selections']:
                spec=runner.read_json(entry['spec_path'])
                methods.add(spec['method_id'])
                self.assertEqual(spec['device'],'cuda:0')
                self.assertEqual(spec['batch_size'],32)
                self.assertEqual(spec['gradient_accumulation'],1)
                self.assertEqual(spec['cpu_threads'],2)
                self.assertEqual(spec['gpu_allocator_budget_bytes'],3*1024**3)
            self.assertEqual(methods,set(runner.FORMAL_METHOD_IDS))
            self.assertFalse((root/'runs').exists(),'Builder launched a model or created run output')

if __name__=='__main__':unittest.main(verbosity=2)
