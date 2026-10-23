"""Pre-execution leakage, cache identity, source-label and residue-index checks."""
import csv
import hashlib
import json
from pathlib import Path
import unittest
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def read(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
class Interfaces(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.manifest=json.loads((HERE/'coverage-manifest.json').read_text(encoding='utf-8'))
    def test_labels_splits_and_membership_preserved(self):
        for view in self.manifest['views']:
            source={r['row_id']:r for r in read(ROOT/'data'/(view['parent_view_id']+'.csv'))}
            derived=read(view['path'])
            for row in derived:
                self.assertEqual(row['label'],source[row['row_id']]['label'])
                self.assertEqual(row['split'],source[row['row_id']]['split'])
                self.assertEqual(row['group_id'],source[row['row_id']]['group_id'])
            self.assertEqual(len(derived),view['rows'])
    def test_contact_aa_and_1based_index_and_no_geometry_features(self):
        view=next(v for v in self.manifest['views'] if v['task']=='contact')
        rows=read(view['path']);proof=json.loads((HERE/'inputs/contact-sequence-index-proof.json').read_text())
        self.assertEqual(len(rows),8625);self.assertEqual(len(proof),8625)
        indexed={r['row_id']:r for r in proof}
        for row in rows:
            index=int(row['residue_index']);p=indexed[row['row_id']]
            self.assertEqual(index,p['residue_index1'])
            self.assertEqual(row['target_sequence'][index-1],row['target_residue_aa'])
            self.assertEqual(row['target_residue_aa'],p['observed_chain_residue_aa'])
            self.assertEqual(p['substring_occurrences'],1)
            self.assertTrue(p['sequence_index_AA_equal'])
        self.assertFalse({'minimum_heavyatom_distance_A','observed_target','coordinates'} & set(rows[0]))
    def test_missing_jobs_are_unlabeled_and_do_not_reextract_old_means(self):
        jobs=[json.loads(line) for line in (HERE/'inputs/missing-representations.jsonl').read_text().splitlines()]
        allowed={'sequence_id','sequence','length','need_mean','need_residue','existing_mean_preserved','priority'}
        reuse=json.loads((HERE/'inputs/old-cache-reuse.json').read_text(encoding='utf-8'))
        old={r['sequence_id'] for r in reuse['vectors']}
        for row in jobs:
            self.assertEqual(set(row),allowed)
            self.assertEqual(hashlib.sha256(row['sequence'].encode('ascii')).hexdigest(),row['sequence_id'])
            self.assertLessEqual(row['length'],2048)
            if row['need_mean']:self.assertNotIn(row['sequence_id'],old)
        self.assertEqual(len(jobs),25336)
    def test_old_mean_vector_bytes_match_per_vector_hash(self):
        reuse=json.loads((HERE/'inputs/old-cache-reuse.json').read_text(encoding='utf-8'))
        path=Path(reuse['old_cache_path'])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),reuse['old_cache_sha256'])
        archive=np.load(path,allow_pickle=False);vectors=archive['embeddings'];ids=archive['sequence_ids']
        self.assertEqual(len(reuse['vectors']),622)
        for item in reuse['vectors']:
            self.assertEqual(ids[item['source_row_index']],item['sequence_id'])
            self.assertEqual(hashlib.sha256(vectors[item['source_row_index']].tobytes()).hexdigest(),item['source_vector_sha256'])
if __name__=='__main__':unittest.main(verbosity=2)
