"""Synthetic CPU tests only; never load CLM2 weights or call a real tokenizer."""
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
# The production worker needs transformers; this local test uses no model/tokenizer.
if importlib.util.find_spec('transformers') is None:
    stub = types.ModuleType('transformers')
    stub.PreTrainedTokenizerFast = object
    sys.modules['transformers'] = stub
import train_finetune_ringfix as runner
import shared_metrics as copied


class MockEncoder(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.embedding = torch.nn.Embedding(8, 512)

    def forward(self, input_ids, attention_mask):
        x = self.embedding(input_ids)
        mask = attention_mask.unsqueeze(-1)
        return types.SimpleNamespace(mean_pool=(x*mask).sum(1)/mask.sum(1))


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
        self.assertTrue(all(p.grad is not None for p in model.parameters()))
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
        self.assertEqual(model.head[0].in_features,832)
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
            source_path=HERE.parents[1]/'baselines/chemical-encoder-benchmark-20261024-v1/run_heads.py'
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


if __name__=='__main__':
    unittest.main(verbosity=2)
