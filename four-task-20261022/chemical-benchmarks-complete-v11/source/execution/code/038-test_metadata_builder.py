"""Synthetic numeric fixtures only; no real embeddings, model weights or NN calls."""
from pathlib import Path
import hashlib,tempfile,unittest
import numpy as np
import build_expanded as builder

def key(text):return hashlib.sha256(('nonbiological-fixture:'+text).encode()).hexdigest()
def sample():
    ids=np.asarray([key('one'),key('two')],dtype='U64');values=np.arange(640,dtype=np.float32).reshape(2,320);values[0,0]=np.float32(-0.0)
    extra=np.asarray([key('three')],dtype='U64');delta=np.full((1,320),np.nextafter(np.float32(1),np.float32(2)),dtype=np.float32)
    return ids,values,extra,delta

class Tests(unittest.TestCase):
    def test_append_preserves_every_original_and_delta_float_bit(self):
        old_ids,old,new_ids,new=sample();ids,values=builder.merge_arrays(old_ids,old,new_ids,new)
        self.assertEqual(ids[:2].tobytes(),old_ids.tobytes());self.assertEqual(values[:2].tobytes(),old.tobytes());self.assertEqual(values[2:].tobytes(),new.tobytes())
        self.assertTrue(np.signbit(values[0,0]));self.assertEqual(values.dtype,np.float32)

    def test_key_overlap_rejected(self):
        ids,old,_,new=sample()
        with self.assertRaises(ValueError):builder.merge_arrays(ids,old,ids[:1],new)

    def test_duplicate_delta_key_rejected(self):
        ids,old,new_ids,new=sample()
        with self.assertRaises(ValueError):builder.merge_arrays(ids,old,np.repeat(new_ids,2),np.repeat(new,2,axis=0))

    def test_nonfinite_vector_rejected(self):
        ids,old,new_ids,new=sample();new[0,0]=np.nan
        with self.assertRaises(ValueError):builder.merge_arrays(ids,old,new_ids,new)

    def test_fp64_silent_conversion_rejected(self):
        ids,old,new_ids,new=sample()
        with self.assertRaises(ValueError):builder.merge_arrays(ids,old.astype(np.float64),new_ids,new)

    def test_npz_roundtrip_keeps_old_prefix_bitexact(self):
        ids,old,new_ids,new=sample();keys,values=builder.merge_arrays(ids,old,new_ids,new)
        with tempfile.TemporaryDirectory() as name:
            p=Path(name)/'fixture.npz';np.savez_compressed(p,sequence_ids=keys,embeddings=values);kk,vv=builder.load_arrays(p)
            self.assertEqual(kk.tobytes(),keys.tobytes());self.assertEqual(vv.tobytes(),values.tobytes())

    def test_npz_wrong_dimension_rejected(self):
        ids,old,_,_=sample()
        with tempfile.TemporaryDirectory() as name:
            p=Path(name)/'fixture.npz';np.savez(p,sequence_ids=ids,embeddings=old[:,:319])
            with self.assertRaises(ValueError):builder.load_arrays(p)

    def test_object_pickle_key_array_rejected(self):
        ids,old,_,_=sample()
        with tempfile.TemporaryDirectory() as name:
            p=Path(name)/'fixture.npz';np.savez(p,sequence_ids=ids.astype(object),embeddings=old)
            with self.assertRaises(ValueError):builder.load_arrays(p)

    def test_spec_changes_only_two_protein_binding_fields(self):
        spec={'is_template':False,'protein_mode':'frozen_esm2','protein_cache_binding':'old','protein_cache_binding_sha256':'before','chemical_cache_manifest':'same-chemical','chemical_cache_manifest_sha256':'same-sha','chemistry_mode':'cached_encoder','nested':{'dimension':768}}
        new=builder.clone_spec(spec,Path('new-binding.json'),'after');self.assertEqual({k:v for k,v in new.items() if k not in ('protein_cache_binding','protein_cache_binding_sha256')},{k:v for k,v in spec.items() if k not in ('protein_cache_binding','protein_cache_binding_sha256')});self.assertEqual(spec['protein_cache_binding'],'old')
        with self.assertRaises(ValueError):builder.clone_spec(dict(spec,is_template=True),Path('new'),'after')
        with self.assertRaises(ValueError):builder.clone_spec(dict(spec,protein_mode='aac23'),Path('new'),'after')

if __name__=='__main__':unittest.main(verbosity=2)
