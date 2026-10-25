"""Synthetic metadata-only contract tests; no biological arrays or models."""
from pathlib import Path
import tempfile, unittest
from collections import Counter
import build_freeze as build

class Tests(unittest.TestCase):
    def test_reviewed_edge_transitive_closure(self):
        nodes=[{'target':v} for v in ('synthetic-A','synthetic-B','synthetic-C')]
        pairs=[{'target_a_sha256':build.hs(a),'target_b_sha256':build.hs(b),'source_pair_id':str(i)} for i,(a,b) in enumerate([('synthetic-A','synthetic-B'),('synthetic-B','synthetic-C')])]
        u=build.UF(3);counts=Counter();proof=build.add_reviewed_target_edges(u,nodes,pairs,counts)
        self.assertEqual(len({u.find(i) for i in range(3)}),1);self.assertEqual(counts['target_homology_supplemental_reviewed'],2);self.assertEqual(len(proof),2)

    def test_missing_target_hash_rejected(self):
        with self.assertRaises(ValueError):build.add_reviewed_target_edges(build.UF(1),[{'target':'synthetic-A'}],[{'target_a_sha256':build.hs('synthetic-A'),'target_b_sha256':build.hs('absent'),'source_pair_id':'fixture'}],Counter())

    def setup_panels(self,p):
        old=p/'parent';new=p/'new';old.mkdir();new.mkdir()
        for root in (old,new):
            for panel in ('source','target'):
                d=root/panel;d.mkdir()
                roles=[{'dataset':'fixture','row_id':'row','role':'validation','global_group_id':'before','anchor':'validation','role_reason':'locked_legacy_kd_validation'}]
                build.writecsv(d/'role_assignments.csv',roles)
                build.writecsv(d/'fine_affinity.csv',[{'row_id':'row','split':'validation','global_group_id':'before','label':'0.1234567890123456'}])
        return old,new

    def test_only_validation_to_external_quarantine_allowed(self):
        with tempfile.TemporaryDirectory() as name:
            old,new=self.setup_panels(Path(name));before=(build.PARENT,build.OUT);build.PARENT,build.OUT=old,new
            try:
                build.writecsv(new/'target/role_assignments.csv',[{'dataset':'fixture','row_id':'row','role':'quarantine','global_group_id':'after','anchor':'external','role_reason':'dependency_to_external'}])
                build.writecsv(new/'target/fine_affinity.csv',[],['row_id','split','global_group_id','label'])
                build.verify_role_inheritance()
                self.assertEqual(len(build.readcsv(new/'ROLE-CHANGES.actual.csv')),1)
            finally:build.PARENT,build.OUT=before

    def test_heldout_promotion_is_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            old,new=self.setup_panels(Path(name));before=(build.PARENT,build.OUT);build.PARENT,build.OUT=old,new
            try:
                build.writecsv(new/'target/role_assignments.csv',[{'dataset':'fixture','row_id':'row','role':'fine_train','global_group_id':'after','anchor':'development','role_reason':'bad'}])
                with self.assertRaises(ValueError):build.verify_role_inheritance()
            finally:build.PARENT,build.OUT=before

    def test_retained_label_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            old,new=self.setup_panels(Path(name));before=(build.PARENT,build.OUT);build.PARENT,build.OUT=old,new
            try:
                build.writecsv(new/'target/fine_affinity.csv',[{'row_id':'row','split':'validation','global_group_id':'before','label':'0.1234567890123457'}])
                with self.assertRaises(ValueError):build.verify_role_inheritance()
            finally:build.PARENT,build.OUT=before

if __name__=='__main__':unittest.main(verbosity=2)
