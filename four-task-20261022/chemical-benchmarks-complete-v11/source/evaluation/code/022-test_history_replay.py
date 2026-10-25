"""Pure non-biological fixtures for preparation guards and numerical replay."""
import json
from pathlib import Path
import tempfile
import unittest

from evaluate_saved_predictions import metrics,pearson
from normalize_owner_mirrors import normalize
from prepare_mirrored_history import prepare
from public_artifacts import sha
from replay_public_predictions import macro,strata,summary


class ReplayGuards(unittest.TestCase):
    def test_constant_decimal_correlation_is_undefined(self):
        self.assertIsNone(pearson(list(range(53)),[1.123456789]*53))
        self.assertIsNone(metrics([{'label':str(i),'prediction':'1.123456789'} for i in range(53)])['pearson'])

    def test_strata_keep_PTM_in_historical_NC_all(self):
        names=('standard20_control','synthetic_D_backbone','PTM','synthetic_and_PTM','other_NC')
        rows=[{'row_id':str(i),'evaluation_stratum':name} for i,name in enumerate(names)]
        annotations={r['row_id']:{'residue_class_graph_discordance':str(i==4)} for i,r in enumerate(rows)}
        result=strata(rows,annotations)
        self.assertEqual(len(result['NC_all']),4)
        self.assertEqual(len(result['PTM_bearing']),2)
        self.assertEqual(len(result['synthetic_D_backbone']),1)
        self.assertEqual(len(result['flagged']),1)

    def test_summary_requires_all_ten_distinct_seeds(self):
        with self.assertRaises(ValueError):summary([{'method':'a','seed':0}],('method',))

    def test_macro_keeps_undefined_group_correlations_null(self):
        result=macro([{'global_group_id':'a','label':'0','prediction':'1'}, {'global_group_id':'b','label':'2','prediction':'3'}])
        self.assertEqual(result['all_groups'],2)
        self.assertEqual(result['mae'],1)
        self.assertIsNone(result['pearson'])
        self.assertEqual(result['pearson_valid_groups'],0)

    def test_unknown_phase_rejected_before_input_IO(self):
        with self.assertRaises(ValueError):prepare([],Path('not-read'),Path('not-created'),'expanded','invalid')

    def test_owner_normalization_checks_original_hash(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);source=root/'s.json';source.write_text('{}')
            manifest=root/'map.json';manifest.write_text(json.dumps({'files':[{'remote':'/fixture/a.json','local':str(source),'bytes':2,'sha256':'0'*64}]}))
            with self.assertRaises(ValueError):normalize([manifest],root/'output')
            self.assertFalse((root/'output').exists())

    def test_conflicting_owner_snapshots_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);maps=[]
            for i,data in enumerate((b'{}',b'[]')):
                source=root/str(i);source.write_bytes(data);manifest=root/(str(i)+'.json')
                manifest.write_text(json.dumps({'files':[{'remote':'/fixture/a.json','local':str(source),'bytes':2,'sha256':sha(data)}]}));maps.append(manifest)
            with self.assertRaises(ValueError):normalize(maps,root/'output')

    def test_exact_owner_copy_keeps_original_bytes(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);source=root/'s.json';data=b'{"value":1.2345678901234567}\n';source.write_bytes(data)
            manifest=root/'map.json';manifest.write_text(json.dumps({'files':[{'remote':'/fixture/a.json','local':str(source),'bytes':len(data),'sha256':sha(data)}]}))
            result=normalize([manifest],root/'output');self.assertEqual(result['files'],1)
            self.assertEqual((root/'output'/'00000-a.json').read_bytes(),data)
            with self.assertRaises(FileExistsError):normalize([manifest],root/'output')


if __name__=='__main__':unittest.main()
