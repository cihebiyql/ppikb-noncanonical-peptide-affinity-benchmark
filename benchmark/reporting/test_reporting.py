"""Synthetic-only; no production metadata, scientific values or model calls."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('report_builder_test',Path(__file__).with_name('report_builder.py'))
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

def row(seed=0,value=0.1,**kw):
    out=dict(category='five_prior_paper_NN',dataset_id='PPIKB-internal',raw_dataset_id='source_test',panel=b.PANELS[0],method_id='GraphDTA-GIN',regime='NC_only',seed=seed,cohort='NC_core',aggregation='row_micro',metric='MAE',value=value,n=303,n_unit='observation_rows',defined_group_count=None)
    out.update(kw);return out

def full_rows():
    out=[]
    for cat,methods in b.CATEGORIES.items():
        for p in b.PANELS:
            for m in methods:
                for regime in b.REGIMES:
                    for s in range(10):
                        cohorts={'PPIKB-internal':{'all':b.ALL_N[p],'NC_core':b.NC_N[p],'standard':b.ALL_N[p]-b.NC_N[p]},'PTM-external75':{'all':75,'external_primary67':67,'external_conditional_sensitivity8':8,'external_reference_target_cold2':2},'IgG-supplement13':{'all':13,'supplement_NC8':8,'supplement_standard5':5}}
                        for dataset,groups in cohorts.items():
                            raw=('source_test' if p==b.PANELS[0] else 'target_test') if dataset=='PPIKB-internal' else 'external75' if dataset=='PTM-external75' else 'supplement13'
                            for c,n in groups.items():
                                for metric in b.METRICS:
                                    out.append(row(seed=s,value=None if metric=='Pearson' else 0.25,category=cat,dataset_id=dataset,raw_dataset_id=raw,panel=p,method_id=m,regime=regime,cohort=c,n=n,metric=metric))
    return out

class ReportingTests(unittest.TestCase):
    def test_01_null_sample_sd_and_valid_count(self):
        rs=[row(seed=s,value=None if s==0 else float(s)) for s in range(10)]
        r=b.summarize(rs)[0];self.assertEqual((r['completed_seed_count'],r['defined_seed_count']), (10,9));self.assertEqual(r['mean'],5);self.assertAlmostEqual(r['sample_sd'],2.7386127875258306);self.assertIsNone(r['values_by_seed']['0'])
    def test_02_all_null_not_zero(self):
        r=b.summarize([row(seed=s,value=None) for s in range(10)])[0];self.assertIsNone(r['mean']);self.assertIsNone(r['sample_sd'])
    def test_03_one_value_sd_null(self):
        r=b.summarize([row()])[0];self.assertIsNone(r['sample_sd']);self.assertEqual(r['missing_seeds'],list(range(1,10)))
    def test_04_constant_decimal_zero_sample_sd(self):
        r=b.summarize([row(seed=s) for s in range(10)])[0];self.assertEqual(r['sample_sd'],0)
    def test_05_main_denominator_cannot_be_all(self):
        with self.assertRaises(ValueError):b.summarize([row(n=1039)])
    def test_06_panels_remain_separate(self):
        r=b.summarize([row(),row(panel=b.PANELS[1],n=332,raw_dataset_id='target_test')]);self.assertEqual(len(r),2)
    def test_07_duplicates_nonfinite_and_raw_fields_rejected(self):
        for rs in ([row(),row()],[row(value=float('nan'))],[row(pKd=2)]):
            with self.assertRaises(ValueError):b.summarize(rs)
    def test_08_macro_defined_group_count_preserved(self):
        r=b.summarize([row(aggregation='equal_weight_study_id',n=4,n_unit='study_id_groups',defined_group_count=2)])[0];self.assertEqual(r['defined_group_count_by_seed'],{'0':2})
    def test_09_full_grid_counts_and_subgroups(self):
        rs=full_rows();b.validate_rows(rs);b.check_full_cohorts(rs);ledger=b.coverage(rs);self.assertTrue(all(x['complete'] for x in ledger.values()));self.assertEqual(sum(x['actual_complete_score_metric_sets'] for x in ledger.values()),1080)
    def test_10_missing_subgroup_cannot_claim_full(self):
        rs=[r for r in full_rows() if r['cohort']!='NC_core']
        with self.assertRaises(ValueError):b.check_full_cohorts(rs)
    def test_11_template_has_no_scores(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'template';b.produce(out,[],[],{},True);t=(out/'完整报告.md').read_text(encoding='utf-8');self.assertIn('待真实审计结果',t);self.assertEqual(b.read(out/'metrics-per-seed.json'),[]);self.assertIn('NC_core n=303',t);self.assertIn('NC_core n=332',t);self.assertFalse(b.read(out/'report-receipt.json')['raw_gold_predictions_models_training_labels_read'])
    def test_12_auth_denied_before_touching_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'auth.json';b.write(p,{'root_final_scientific_report_authorized':False})
            with self.assertRaises(PermissionError):b.authorized_inputs(p,'NEVER_OPEN','NEVER_OPEN')
    def test_13_joint_grid_required(self):
        with self.assertRaises(ValueError):b.verify_joint({'status':'all_200_NN_plus_40_RF_frozen','NN_selections':199,'RF_selections':40,'NN_execution_index_sha256':b.NN_INDEX_SHA})
    def test_14_csv_literal_null(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x.csv';b.csv_out(p,[{'x':None}]);self.assertIn('null',p.read_text(encoding='utf-8-sig'))
    def test_15_partial_explicit_gate_and_real_coverage(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);j=root/'joint.json';m=root/'manifest.json';a=root/'auth.json';r=root/'unified-per-seed-metrics.json'
            b.write(j,dict(status='all_200_NN_plus_40_RF_frozen',NN_selections=200,RF_selections=40,NN_execution_index_sha256=b.NN_INDEX_SHA));b.write(r,[row()])
            b.write(m,dict(status='partial_postjoint_metric_table_assembly',independently_audited_available_metrics=True,joint_barrier_sha256=b.sha(j),per_seed_table_sha256=b.sha(r)))
            auth=dict(root_final_scientific_report_authorized=True,source_sha256=b.source_hashes(),deadline_unix=time.time()+30,joint_barrier_sha256=b.sha(j),audited_manifest_sha256=b.sha(m));b.write(a,auth)
            with self.assertRaises(ValueError):b.authorized_inputs(a,m,j)
            auth['allow_partial_audited_coverage']=True;b.write(a,auth);rs,sm,ld,tr,_=b.authorized_inputs(a,m,j);self.assertEqual(len(rs),1);self.assertEqual(sm[0]['completed_seed_count'],1);self.assertEqual(ld['five_prior_paper_NN']['actual_complete_score_metric_sets'],0)
    def test_16_complete_metric_only_synthetic_auth_and_output(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);j=root/'joint.json';m=root/'manifest.json';a=root/'auth.json';r=root/'unified-per-seed-metrics.json'
            b.write(j,dict(status='all_200_NN_plus_40_RF_frozen',NN_selections=200,RF_selections=40,NN_execution_index_sha256=b.NN_INDEX_SHA));b.write(r,full_rows())
            b.write(m,dict(status='complete_postjoint_metric_table_assembly',joint_barrier_sha256=b.sha(j),per_seed_table_sha256=b.sha(r),ledger_score_receipts=1080,ledger_prediction_rows=478440))
            b.write(a,dict(root_final_scientific_report_authorized=True,source_sha256=b.source_hashes(),deadline_unix=time.time()+30,joint_barrier_sha256=b.sha(j),audited_manifest_sha256=b.sha(m)))
            rows,summary,ledger,tr,_=b.authorized_inputs(a,m,j);b.produce(root/'report',rows,summary,ledger,False,tr);main=b.read(root/'report/summary.json');self.assertTrue(any(x['mean'] is None for x in main));self.assertIn('独立审计指标汇总',(root/'report/完整报告.md').read_text(encoding='utf-8'))
    def test_17_source_hash_pin_rejects(self):
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/'auth.json';b.write(a,dict(root_final_scientific_report_authorized=True,source_sha256={},deadline_unix=time.time()+20))
            with self.assertRaises(ValueError):b.authorized_inputs(a,'NEVER_OPEN','NEVER_OPEN')
    def test_18_training_metadata_unknown_epochs_not_inferred(self):
        source=Path(b.__file__).read_text(encoding='utf-8');self.assertIn("completed_epoch_count=raw.get('completed_epoch_count')",source);self.assertNotIn("epochs_at_cap=raw.get('best_epoch')",source)

if __name__=='__main__':unittest.main(verbosity=2)
