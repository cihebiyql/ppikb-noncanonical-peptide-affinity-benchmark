"""Synthetic numerical interface tests; no real encoder, biological model or official fit."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

from chemical_features import ChemicalFeatures, raw_key, sha
from run_heads import metrics, read_views, run_view, validate_frame, write_json


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-head-contract-')
        self.root = Path(self.temp.name)
        self.smiles = ['fixture-input-a', 'fixture-input-b', 'fixture-input-c']
        np.savez_compressed(self.root/'features.npz',smiles_sha256=np.asarray([raw_key(x) for x in self.smiles]),
                            embeddings=np.asarray([[1.,2.],[3.,4.],[2.,5.]],dtype=np.float32))
        canary={'passed':True,'scope':'synthetic_fixture_not_chemical_validation',
                'tests':{x:{'passed':True} for x in ['chirality','ptm','noncanonical']}}
        write_json(self.root/'canary.json',canary)
        self.binding={'schema':'chemical-encoder.cache.v1','status':'succeeded',
            'keys_kind':'sha256_raw_smiles','no_truncation':True,'chemical_canary_passed':True,
            'chemical_canary_receipt':'canary.json','chemical_canary_receipt_sha256':sha(self.root/'canary.json'),
            'embedding_file':'features.npz','embedding_sha256':sha(self.root/'features.npz'),
            'model_identity':'synthetic-numerical-fixture-not-real-encoder'}
        write_json(self.root/'cache-manifest.json',self.binding)
        self.spec={'schema':'chemical-encoder.head-feature-spec.v1','is_template':False,
            'chemistry_mode':'cached_encoder','chemical_cache_manifest':'cache-manifest.json',
            'chemical_cache_manifest_sha256':sha(self.root/'cache-manifest.json'),'protein_mode':'aac23'}
        write_json(self.root/'spec.json',self.spec)

    def fixture_encoder(self):
        return ChemicalFeatures(self.root/'spec.json',allow_synthetic_fixture=True)

    def tearDown(self):
        self.temp.cleanup()

    def frame(self):
        data=[]
        for index in range(36):
            split='fine_train' if index<24 else 'validation' if index<30 else 'test'
            data.append({'row_id':f'fixture-{index}','split':split,'global_group_id':f'fixture-group-{index}',
                         'label':float(index%5)+index*.01,'endpoint':'pKd','target_sequence':'ACDE',
                         'peptide_smiles':self.smiles[index%3],
                         'evaluation_stratum':'synthetic_numerical_fixture','source':'not-biological-data'})
        return pd.DataFrame(data)

    def view(self,path):
        return {'id':'synthetic-fixture','path':str(path),'sha256':sha(path),'status':'frozen',
                'task':'affinity','endpoint':'pKd','split_column':'split','group_column':'global_group_id'}

    def test_legacy_manifest_rejected(self):
        with self.assertRaises(ValueError):
            read_views({'schema':'peptide-fourtask.views.v1','views':[]})

    def test_template_rejected(self):
        self.spec['is_template']=True
        write_json(self.root/'spec.json',self.spec)
        with self.assertRaises(ValueError):
            self.fixture_encoder()

    def test_formal_constructor_rejects_boolean_fixture(self):
        with self.assertRaises(ValueError):
            ChemicalFeatures(self.root/'spec.json')

    def test_missing_chemical_validation_rejected(self):
        self.binding['chemical_canary_passed']=False
        write_json(self.root/'cache-manifest.json',self.binding)
        self.spec['chemical_cache_manifest_sha256']=sha(self.root/'cache-manifest.json')
        write_json(self.root/'spec.json',self.spec)
        with self.assertRaises(ValueError):
            self.fixture_encoder()

    def test_cache_tampering_rejected(self):
        with (self.root/'features.npz').open('ab') as handle:
            handle.write(b'tamper')
        with self.assertRaises(ValueError):
            self.fixture_encoder()

    def native_canary(self):
        pairs=[('alanine_L','alanine_D'),('serine','phosphoserine'),
               ('alanine_L','aminobutyrate'),('alanine_L','alaninamide')]
        canary={'schema':'chemical-encoder.canary.v1','status':'succeeded',
                'model_identity':self.binding['model_identity'],'all_finite':True,'no_unknown_tokens':True,
                'no_truncation':True,'repeat_max_abs_difference':0.,
                'pairs':[{'a':a,'b':b,'token_ids_differ':True,'max_abs_embedding_difference':0.5} for a,b in pairs]}
        write_json(self.root/'canary.json',canary)
        self.binding.pop('chemical_canary_receipt',None)
        self.binding.pop('chemical_canary_receipt_sha256',None)
        self.binding['canary_sha256']=sha(self.root/'canary.json')
        write_json(self.root/'cache-manifest.json',self.binding)
        self.spec['chemical_cache_manifest_sha256']=sha(self.root/'cache-manifest.json')
        write_json(self.root/'spec.json',self.spec)

    def test_native_extractor_receipt_schema(self):
        self.native_canary()
        encoder=self.fixture_encoder()
        self.assertEqual(encoder.chemical_dimension,2)

    def test_native_canary_wrong_assets_rejected(self):
        self.native_canary()
        canary=json.loads((self.root/'canary.json').read_text())
        canary['model_identity']='different-assets'
        write_json(self.root/'canary.json',canary)
        self.binding['canary_sha256']=sha(self.root/'canary.json')
        write_json(self.root/'cache-manifest.json',self.binding)
        self.spec['chemical_cache_manifest_sha256']=sha(self.root/'cache-manifest.json')
        write_json(self.root/'spec.json',self.spec)
        with self.assertRaises(ValueError):
            self.fixture_encoder()

    def test_blocked_source_preserved_in_common_cohort(self):
        self.native_canary()
        frame=self.frame()
        source=self.root/'frozen.csv'
        frame.to_csv(source,index=False,float_format='%.17g')
        manifest={'schema':'peptide.cross-task-firewall.v1','status':'frozen','frozen':True,
                  'views':[{'id':'blocked-source','status':'blocked','reason':'zero eligible train','path':'frozen.csv'},self.view(source)],
                  'external_views':[{'id':'external-fixture','path':'frozen.csv','sha256':sha(source)}],
                  'outputs':[{'path':'frozen.csv','sha256':sha(source)}]}
        write_json(self.root/'global-manifest.json',manifest)
        out=self.root/'common-cohort'
        proc=subprocess.run([sys.executable,str(Path(__file__).with_name('prepare_model_cohort.py')),
            '--manifest',str(self.root/'global-manifest.json'),'--feature-spec',str(self.root/'spec.json'),
            '--output',str(out)],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
        updated=json.loads((out/'frozen-manifest.json').read_text())
        self.assertEqual(updated['views'][0]['status'],'blocked')
        self.assertEqual(updated['model_cohort']['coverage'][1]['retained_rows'],36)
        self.assertEqual(Path(updated['views'][0]['path']),source.resolve())
        self.assertEqual(Path(updated['external_views'][0]['path']),source.resolve())
        self.assertEqual(Path(updated['outputs'][0]['path']),source.resolve())
        self.assertEqual(updated['external_views'][0]['sha256'],sha(source))

    def test_same_spec_basename_cannot_hide_input_failure(self):
        self.native_canary()
        first,second=self.root/'first/spec.json',self.root/'second/spec.json'
        first.parent.mkdir();second.parent.mkdir()
        np.savez_compressed(self.root/'small-features.npz',smiles_sha256=np.asarray([raw_key(x) for x in self.smiles[1:]]),
                            embeddings=np.asarray([[3.,4.],[2.,5.]],dtype=np.float32))
        small_binding=dict(self.binding,embedding_file='small-features.npz',embedding_sha256=sha(self.root/'small-features.npz'))
        write_json(self.root/'small-cache.json',small_binding)
        first_spec=dict(self.spec,chemical_cache_manifest=str((self.root/'small-cache.json').resolve()),
                        chemical_cache_manifest_sha256=sha(self.root/'small-cache.json'))
        second_spec=dict(self.spec,chemical_cache_manifest=str((self.root/'cache-manifest.json').resolve()))
        write_json(first,first_spec);write_json(second,second_spec)
        source=self.root/'frozen.csv';self.frame().to_csv(source,index=False,float_format='%.17g')
        write_json(self.root/'global-manifest.json',{'schema':'peptide.cross-task-firewall.v1','status':'frozen','frozen':True,'views':[self.view(source)]})
        out=self.root/'cohort-collision-test'
        proc=subprocess.run([sys.executable,str(Path(__file__).with_name('prepare_model_cohort.py')),
            '--manifest',str(self.root/'global-manifest.json'),'--feature-spec',str(first),'--feature-spec',str(second),
            '--output',str(out)],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
        result=json.loads((out/'frozen-manifest.json').read_text())
        self.assertEqual(result['model_cohort']['coverage'][0]['retained_rows'],24)
        excluded=pd.read_csv(out/'input-only-exclusions.csv')
        self.assertEqual(len(excluded),12)
        self.assertIn(str(first.resolve()),json.loads(excluded.iloc[0].reasons))

    def test_labels_never_affect_features(self):
        encoder=self.fixture_encoder()
        frame=self.frame()
        a,_=encoder.build(frame,'affinity')
        frame['label']=frame.label*1000+1234
        b,_=encoder.build(frame,'affinity')
        self.assertTrue(np.array_equal(a,b))

    def test_unknown_chemical_not_projected(self):
        encoder=self.fixture_encoder()
        frame=self.frame()
        frame.loc[0,'peptide_smiles']='unsupported-full-chemical-identity'
        self.assertEqual(encoder.coverage_reason(frame.iloc[0].to_dict()),'chemical_cache_unavailable_or_unsupported_input')
        with self.assertRaises(KeyError):
            encoder.build(frame,'affinity')

    def test_missing_smiles_not_replaced_by_sequence(self):
        encoder=self.fixture_encoder()
        row=self.frame().iloc[0].to_dict()
        row['peptide_smiles']=''
        row['peptide_sequence']='ACDE'
        self.assertEqual(encoder.coverage_reason(row),'missing_actual_complete_smiles')

    def test_cross_split_group_rejected(self):
        frame=self.frame()
        frame.loc[35,'global_group_id']=frame.loc[0,'global_group_id']
        with self.assertRaises(ValueError):
            validate_frame(frame,self.view(self.root/'features.npz'))

    def test_pretraining_rows_not_fitted(self):
        frame=self.frame()
        frame.loc[0,'split']='pretrain'
        result=validate_frame(frame,self.view(self.root/'features.npz'))
        self.assertNotIn('fixture-0',set(result.row_id))
        self.assertEqual((result.split=='train').sum(),23)

    def test_mixed_endpoints_rejected(self):
        frame=self.frame()
        frame.loc[0,'endpoint']='pIC50'
        with self.assertRaises(ValueError):
            validate_frame(frame,self.view(self.root/'features.npz'))

    def test_constant_correlation_is_null(self):
        result=metrics([1.,2.,3.],[2.,2.,2.])
        self.assertIsNone(result['pearson'])
        self.assertIsNone(result['spearman'])
        self.assertEqual(result['mae'],2/3)

    def test_synthetic_five_family_fit_and_saved_recalculation(self):
        import time
        frame=self.frame()
        source=self.root/'frozen.csv'
        frame.to_csv(source,index=False,float_format='%.17g')
        view=self.view(source)
        manifest={'schema':'peptide.cross-task-firewall.v1','status':'frozen','frozen':True,'views':[view]}
        write_json(self.root/'global-manifest.json',manifest)
        out=self.root/'runs'
        run_view(view,self.root/'global-manifest.json',self.fixture_encoder(),out,
                 time.monotonic()+60,1,[0],['constant','ridge','random_forest','extra_trees','hist_gradient_boosting'])
        receipt=self.root/'audit.json'
        proc=subprocess.run([sys.executable,str(Path(__file__).with_name('audit_results.py')),
                             '--output',str(out),'--receipt',str(receipt)],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
        result=json.loads(receipt.read_text())
        self.assertTrue(result['valid'])
        self.assertEqual(len(result['seeds_by_combination']),5)
        for name in ('constant','ridge','random_forest','extra_trees','hist_gradient_boosting'):
            saved=json.loads((out/'synthetic-fixture'/name/'seed-00/result.json').read_text())
            self.assertEqual(len(saved['candidates']),2)
            self.assertEqual(saved['splits']['test']['metrics']['n'],6)
        # A second identical invocation verifies saved SHA and skips, rather than rewriting fits.
        before={str(p):sha(p) for p in out.rglob('*.joblib')}
        run_view(view,self.root/'global-manifest.json',self.fixture_encoder(),out,
                 time.monotonic()+60,1,[0],['constant','ridge','random_forest','extra_trees','hist_gradient_boosting'])
        self.assertEqual(before,{str(p):sha(p) for p in out.rglob('*.joblib')})
        withheld=out/'synthetic-fixture/extra_trees/seed-00/result.json'
        withheld.rename(withheld.with_name('result-withheld.json'))
        proc=subprocess.run([sys.executable,str(Path(__file__).with_name('audit_results.py')),
                             '--output',str(out),'--receipt',str(receipt)],capture_output=True,text=True,encoding='utf-8')
        self.assertNotEqual(proc.returncode,0)
        result=json.loads(receipt.read_text())
        self.assertIn(['synthetic-fixture','extra_trees',0],result['missing_units'])


if __name__=='__main__':
    unittest.main()
