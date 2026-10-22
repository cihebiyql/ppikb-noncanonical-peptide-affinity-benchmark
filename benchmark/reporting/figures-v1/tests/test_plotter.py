"""Artificial aggregate fixtures only; no project metrics/predictions/models."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
spec=importlib.util.spec_from_file_location('plot_nc_mae_test',Path(__file__).resolve().parents[1]/'plot_nc_mae.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
TESTS=Path(__file__).resolve().parent

def fixture():
    rows=[]
    for panel in p.PANELS:
        for i,method in enumerate(p.METHODS):
            for j,regime in enumerate(p.REGIMES):
                rows.append(dict(category='auxiliary_handcrafted_RF' if method==p.METHODS[-1] else 'five_prior_paper_NN',dataset_id='PPIKB-internal',panel=panel,method_id=method,regime=regime,cohort='NC_core',aggregation='row_micro',metric='MAE',mean=.25+i*.12+j*.04,sample_sd=.015+i*.006,completed_seed_count=10,defined_seed_count=10,missing_seeds=[],n_by_seed={str(s):p.N[panel] for s in range(10)},n_unit='observation_rows'))
    return rows

class PlotterTests(unittest.TestCase):
    def test_01_exact24_fixed_order_and_unmodified_values(self):
        rows=fixture();before=copy.deepcopy(rows);out=p.select_rows(list(reversed(rows)));self.assertEqual(rows,before);self.assertEqual(out,rows)
    def test_02_missing_duplicate_unknown_rejected(self):
        cases=[fixture()[:-1],fixture()+fixture()[:1]]
        q=fixture();q[0]['method_id']='invented';cases.append(q)
        for rows in cases:
            with self.assertRaises(ValueError):p.select_rows(rows)
    def test_03_negative_null_nonfinite_sd_rejected(self):
        for value in (-1,None,float('nan'),float('inf'),True):
            q=fixture();q[0]['sample_sd']=value
            with self.assertRaises(ValueError):p.select_rows(q)
    def test_04_negative_null_mean_rejected(self):
        for value in (-1,None,float('nan'),True):
            q=fixture();q[0]['mean']=value
            with self.assertRaises(ValueError):p.select_rows(q)
    def test_05_all1039_cannot_replace_NC303(self):
        q=fixture();q[0]['n_by_seed']={str(s):1039 for s in range(10)}
        with self.assertRaises(ValueError):p.select_rows(q)
    def test_06_ten_defined_completed_and_no_missing_required(self):
        for k,v in (('completed_seed_count',9),('defined_seed_count',9),('missing_seeds',[9]),('n_unit','target_groups')):
            q=fixture();q[0][k]=v
            with self.assertRaises(ValueError):p.select_rows(q)
    def test_07_all_and_deterministic_reference_excluded(self):
        rows=fixture();a=copy.deepcopy(rows[0]);a['cohort']='all';a['n_by_seed']={str(s):1039 for s in range(10)};r=copy.deepcopy(rows[0]);r['method_id']='reference:train_mean';r['category']='three_deterministic_references';self.assertEqual(len(p.select_rows(rows+[a,r])),24)
    def test_08_explicit_authorization_precedes_input_access(self):
        with self.assertRaises(PermissionError):p.read_reviewed(argparse.Namespace(root_reviewed_aggregate=False,summary='NEVER_OPEN',summary_sha256='',output='NEVER_WRITE'))
    def test_09_sha_rejection_and_same_input_dir(self):
        with tempfile.TemporaryDirectory(dir=TESTS) as td:
            source=Path(td)/'summary.json';source.write_text(json.dumps(fixture()),encoding='utf-8')
            args=argparse.Namespace(root_reviewed_aggregate=True,summary=str(source),summary_sha256='0'*64,output=str(Path(td)/'out'))
            with self.assertRaises(ValueError):p.read_reviewed(args)
            args.summary_sha256=p.sha(source);args.output=td
            with self.assertRaises(ValueError):p.read_reviewed(args)
    def test_10_data_health_is_descriptive_only(self):
        text=p.health(fixture(),1234);self.assertIn('Normality',text);self.assertIn('not applicable',text);self.assertIn('24',text)
    def test_11_full_synthetic_exports_and_exact_process_values(self):
        with tempfile.TemporaryDirectory(dir=TESTS) as td:
            q=fixture();out=Path(td)/'synthetic-output';r=p.produce(q,out,'SYNTHETIC_INPUT_SHA',len(json.dumps(q)),synthetic=True)
            self.assertEqual(r['status'],'synthetic_mechanical_only');self.assertEqual(r['groups'],24);self.assertFalse(r['summary_recalculated']);self.assertEqual(r['render']['backend'].lower(),'agg')
            for ext in p.OUTPUT_FORMATS:self.assertTrue((out/'figures'/ext/('fig_01_nc_mae.'+ext)).stat().st_size>100)
            saved=json.loads((out/'process_data/fig_01_original_aggregate_rows.json').read_text(encoding='utf-8'));self.assertEqual(saved,q)
            self.assertTrue((out/'00_data_health.md').exists());self.assertTrue((out/'process_data/fig_01_data.csv').exists())
            if r['xlsx']['available']:
                import openpyxl
                w=openpyxl.load_workbook(out/'process_data/fig_01_data.xlsx',read_only=True);sheet=w.active;data=list(sheet.values);columns=list(data[0]);raw=data[1][columns.index('mean_original_json')];self.assertEqual(json.loads(raw),q[0]['mean']);w.close()
    def test_12_undefined_seed_values_rejected(self):
        q=fixture();q[0]['values_by_seed']={str(s):None for s in range(10)}
        with self.assertRaises(ValueError):p.select_rows(q)

if __name__=='__main__':unittest.main(verbosity=2)
