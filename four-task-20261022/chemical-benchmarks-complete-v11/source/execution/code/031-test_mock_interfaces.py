"""Synthetic CPU tests only; never load pretrained weights or call a real tokenizer."""
from __future__ import annotations
import ast
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import random
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
import numpy as np
import pandas as pd
import torch
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import train_finetune as runner
import shared_metrics as copied
import model_adapter as adapter


class RoFormerSinusoidalPositionalEmbedding(torch.nn.Embedding):
    # Interface mock of the precise official type, not an imported pretrained model.
    __module__ = 'transformers.models.roformer.modeling_roformer'
    def __init__(self):
        super().__init__(768,64)
        with torch.no_grad(): self.weight.zero_()
        self.weight.requires_grad_(False)
    @torch.no_grad()
    def forward(self, positions):
        return super().forward(positions)


class MockEncoder(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.embedding = torch.nn.Embedding(16,768)
        self.encoder = torch.nn.Module()
        self.encoder.embed_positions = RoFormerSinusoidalPositionalEmbedding()
    def forward(self,input_ids,attention_mask,return_dict=True):
        positions=torch.arange(input_ids.shape[1],device=input_ids.device)
        fixed=self.encoder.embed_positions(positions).repeat_interleave(12,dim=-1)
        return types.SimpleNamespace(last_hidden_state=self.embedding(input_ids)+fixed)


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)

    def make_model(self, seed=3):
        runner.seed_all(seed)
        return runner.PairRegressor(MockEncoder())

    def update(self, model, optimizer):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        value = model(torch.tensor([[1,2,3],[3,2,1]]),torch.ones(2,3,dtype=torch.long),torch.ones(2,320))
        loss = torch.nn.functional.mse_loss(value,torch.tensor([.2,.9]))
        loss.backward()
        self.assertTrue(all(p.grad is not None for p in model.parameters() if p.requires_grad))
        torch.nn.utils.clip_grad_norm_(model.parameters(),1.)
        optimizer.step()

    def test_same_seed_initialization_independent_of_lr(self):
        a=self.make_model();b=self.make_model()
        torch.optim.AdamW(a.parameters(),lr=runner.LRS[0])
        torch.optim.AdamW(b.parameters(),lr=runner.LRS[1])
        self.assertEqual(runner.parameter_hash(a),runner.parameter_hash(b))

    def test_complete_mock_encoder_and_regression_head_receive_gradients(self):
        model=self.make_model();optimizer=torch.optim.AdamW(model.parameters(),lr=1e-5)
        self.update(model,optimizer)
        self.assertEqual(model.head[0].in_features,1088)
        self.assertEqual(model.head[0].out_features,256)
        self.assertEqual(model.head[-1].out_features,1)

    def test_rng_optimizer_roundtrip_exact_with_dropout(self):
        model=self.make_model();optimizer=torch.optim.AdamW(model.parameters(),lr=1e-5)
        for _ in range(2):self.update(model,optimizer)
        stream=io.BytesIO()
        torch.save({'model':model.state_dict(),'optimizer':optimizer.state_dict(),
                    'rng':runner.rng_state(torch.device('cpu'))},stream)
        for _ in range(2):self.update(model,optimizer)
        expected=runner.parameter_hash(model)
        last_rng=torch.get_rng_state().clone()
        stream.seek(0);saved=torch.load(stream,weights_only=True,map_location='cpu')
        restored=self.make_model();second=torch.optim.AdamW(restored.parameters(),lr=1e-5)
        restored.load_state_dict(saved['model']);second.load_state_dict(saved['optimizer'])
        runner.restore_rng(saved['rng'],torch.device('cpu'))
        for _ in range(2):self.update(restored,second)
        self.assertEqual(expected,runner.parameter_hash(restored))
        self.assertTrue(torch.equal(last_rng,torch.get_rng_state()))

    def test_legacy_manifest_rejected(self):
        with self.assertRaises(ValueError):copied.read_views({'schema':'peptide-fourtask.views.v1','views':[]})

    def test_pure_helpers_do_not_change_cuda_visibility(self):
        self.assertEqual(os.environ['CUDA_VISIBLE_DEVICES'],'')

    def test_existing_segment_is_rejected_before_asset_or_model_load(self):
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            marker=Path(directory)/'old-checkpoint.marker';marker.write_text('preserve')
            argv=['train_finetune.py','--mode','train','--manifest','unused','--feature-spec','unused',
                  '--model-dir','unused','--asset-receipt','unused','--output',directory,
                  '--view','ppikb_kd_target_global_firewall_v1','--seed','0','--candidate','0','--max-seconds','180']
            with patch.object(sys,'argv',argv),self.assertRaises(SystemExit) as caught:
                runner.main()
            self.assertEqual(caught.exception.code,2)
            self.assertEqual(marker.read_text(),'preserve')

    def test_metric_function_source_identity_and_numeric_fixtures(self):
        provenance=json.loads((HERE/'METRICS-ORIGIN.json').read_text())
        source_path=Path(provenance['source_path'])
        if not source_path.exists():
            source_path=HERE.parent/'chemical-encoder-benchmark-20261024-v1/run_heads.py'
        source=source_path.read_text(encoding='utf-8')
        tree=ast.parse(source)
        wanted={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('finite','metrics')}
        for name,node in wanted.items():
            self.assertEqual(hashlib.sha256(ast.get_source_segment(source,node).encode()).hexdigest(),provenance['functions'][name])
        namespace={'math':math,'np':np,'spearmanr':spearmanr}
        # Test-only extraction of the two original numerical functions avoids original module side effects.
        exec(compile(ast.Module(body=[wanted['finite'],wanted['metrics']],type_ignores=[]),'<original-metric-fixture>','exec'),namespace)
        for y,p in [([1,2,3],[1.1,1.8,3.2]),([1,1],[2,2]),([2],[2]),([],[])]:
            self.assertEqual(copied.metrics(y,p),namespace['metrics'](y,p))


    def test_fixed_native_position_parameter_exactly_whitelisted(self):
        model=self.make_model()
        frozen={n for n,p in model.encoder.named_parameters() if not p.requires_grad}
        self.assertEqual(frozen,{'encoder.embed_positions.weight'})
        optimizer=torch.optim.AdamW(model.parameters(),lr=1e-5)
        original=model.encoder.encoder.embed_positions.weight.detach().clone()
        self.update(model,optimizer)
        self.assertIsNone(model.encoder.encoder.embed_positions.weight.grad)
        self.assertTrue(torch.equal(original,model.encoder.encoder.embed_positions.weight))
        bad=MockEncoder();bad.encoder.embed_positions=torch.nn.Embedding(768,64)
        with self.assertRaises(ValueError):runner.PairRegressor(bad)

    def test_differentiable_pool_includes_cls_sep_excludes_pad(self):
        model=self.make_model();model.eval()
        ids=torch.tensor([[1,2,3,0],[4,5,0,0]])
        mask=torch.tensor([[1,1,1,0],[1,1,0,0]])
        actual=model.encode_chemical(ids,mask)
        weight=model.encoder.embedding.weight
        expected=torch.stack([weight[[1,2,3]].mean(0),weight[[4,5]].mean(0)])
        self.assertTrue(actual.requires_grad)
        self.assertTrue(torch.allclose(actual,expected,atol=1e-7,rtol=1e-6))
        with self.assertRaises(ValueError):model(ids,mask,torch.ones(2,320,requires_grad=True))

    def test_five_pair_chemical_canary_interface_on_toy_encoder(self):
        original=adapter.import_path('toy_canary_fixed_fixtures',adapter.ROOT/'methods/chemical-encoders-20261024-v1/peptideclm2025_worker.py')
        token_ids={raw:[1,i+2,10] for i,raw in enumerate(original.CANARIES.values())}
        with patch.object(adapter,'tokenize_safely',side_effect=lambda tokenizer,raw:{'input_ids':token_ids[raw]}):
            out=adapter.chemical_canary(self.make_model(),object(),torch.device('cpu'))
        self.assertEqual(out['rows'],8);self.assertEqual(len(out['pairs']),5)
        self.assertEqual(out['repeat_max_abs_difference'],0.)
        self.assertTrue(all(x['max_abs_embedding_difference']>0 for x in out['pairs']))

    def test_actual_training_loop_interrupt_resume_preserves_model_adam_rng(self):
        # Entirely synthetic IDs and labels; no pretrained encoder/tokenizer/file is read.
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            base=Path(directory).resolve();self.assertTrue(base.is_relative_to(HERE.resolve()))
            full,first,resumed=[base/x for x in ('full','first','resumed')]
            for path in (full,first,resumed):path.mkdir()
            frame=pd.DataFrame({'row_id':['mock%02d'%i for i in range(24)],
                'label':np.linspace(.1,.8,24),'split':['train']*16+['validation']*4+['test']*4})
            tokens=[[1,(i%8)+2,10] for i in range(24)]
            protein=np.ones((24,320),dtype=np.float32)
            parts={'train':np.arange(16),'validation':np.arange(16,20),'test':np.arange(20,24),'external':np.asarray([],dtype=int)}
            context=(frame,tokens,protein,parts,{'scope':'toy'}, {'scope':'toy-resume-only'})
            def arguments(output,resume=None,digest=None):
                return types.SimpleNamespace(device='cpu',model_dir=Path('unused'),seed=3,candidate=0,
                    output=output,resume_checkpoint=resume,resume_sha256=digest,max_seconds=1000000,
                    checkpoint_reserve_seconds=60)
            with patch.object(runner,'load_model',side_effect=lambda *a:self.make_model(a[2])):
                runner.train_candidate(arguments(full),context,time.monotonic())
                ticks=iter([0.,1e9])
                with patch.object(runner,'time',types.SimpleNamespace(monotonic=lambda:next(ticks))):
                    runner.train_candidate(arguments(first),context,0.)
                interrupted=json.loads((first/'result.json').read_text())
                self.assertEqual(interrupted['status'],'paused_checkpointed')
                self.assertEqual(interrupted['cursor']['global_steps'],1)
                old_last=first/'last.pt';old_sha=copied.sha(old_last)
                runner.train_candidate(arguments(resumed,old_last,old_sha),context,time.monotonic())
                self.assertEqual(copied.sha(old_last),old_sha)
            expected=torch.load(full/'last.pt',weights_only=True,map_location='cpu')
            actual=torch.load(resumed/'last.pt',weights_only=True,map_location='cpu')
            self.assertEqual(expected['cursor']['global_steps'],actual['cursor']['global_steps'])
            self.assertEqual(expected['cursor']['best_val_mae'],actual['cursor']['best_val_mae'])
            for name,value in expected['model'].items():self.assertTrue(torch.equal(value,actual['model'][name]),name)
            for key,state in expected['optimizer']['state'].items():
                for name,value in state.items():
                    other=actual['optimizer']['state'][key][name]
                    if isinstance(value,torch.Tensor):self.assertTrue(torch.equal(value,other))
                    else:self.assertEqual(value,other)
            self.assertTrue(torch.equal(expected['rng']['torch_cpu'],actual['rng']['torch_cpu']))
            self.assertEqual(expected['rng']['python'],actual['rng']['python'])
            self.assertEqual(expected['rng']['numpy'],actual['rng']['numpy'])


if __name__=='__main__':
    unittest.main(verbosity=2)
