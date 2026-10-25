"""Standard-library fixtures for immutable scientific input/path recovery."""
import hashlib
import io
import json
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest
import zipfile

from scientific_path_bridge import path_bridge,mapped_text
from restore_scientific_inputs import check_npz,relative_path,restore


def npy(dtype,shape,payload):
    header=repr({'descr':dtype,'fortran_order':False,'shape':shape}).encode('latin1')+b'\n'
    return b'\x93NUMPY\x01\x00'+struct.pack('<H',len(header))+header+payload


def npz(path,keys=None,values=None,dtype='<f4'):
    keys=keys or [hashlib.sha256(b'synthetic-nonbiological-key').hexdigest()]
    values=values or [1.0,2.0]
    with zipfile.ZipFile(path,'w') as archive:
        archive.writestr('sequence_ids.npy',npy('<U64',(len(keys),),''.join(keys).encode('utf-32-le')))
        archive.writestr('embeddings.npy',npy(dtype,(len(keys),2),struct.pack('<'+'f'*len(values),*values)))


class ScientificRestoreTests(unittest.TestCase):
    def test_path_bridge_prefix_and_descriptor_restored(self):
        before=Path.__dict__['__new__']
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)/'recovered'
            with path_bridge(root,('/recorded/project',)):
                self.assertEqual(Path('/recorded/project/data.csv'),root/'data.csv')
                self.assertEqual(Path(root/'data.csv'),root/'data.csv')
        self.assertIs(Path.__dict__['__new__'],before)

    def test_path_bridge_restored_on_exception(self):
        before=Path.__dict__['__new__']
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaises(RuntimeError):
                with path_bridge(Path(raw),('/recorded/project',)):raise RuntimeError('fixture')
        self.assertIs(Path.__dict__['__new__'],before)

    def test_nested_bridge_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            with path_bridge(raw,('/recorded/project',)):
                with self.assertRaises(RuntimeError):
                    with path_bridge(raw,('/recorded/project',)):pass

    def test_traversal_rejected_and_other_prefix_untouched(self):
        with self.assertRaises(ValueError):mapped_text('/recorded/project/../escape','/recovered',('/recorded/project',))
        self.assertEqual(mapped_text('/different/project/file','/recovered',('/recorded/project',)),'/different/project/file')
        for name in ('../x','/absolute','a\\x','D:/x'):
            with self.assertRaises(ValueError):relative_path(name)

    def test_windows_extended_destination_not_double_mapped(self):
        root='\\\\?\\D:\\recovered'
        self.assertEqual(mapped_text('D:/recovered/a',root,('D:/recorded',)),'//?/D:/recovered/a')
        self.assertEqual(mapped_text('D:/recorded/a',root,('D:/recorded',)),'//?/D:/recovered/a')

    def test_npz_generated_features_typed_and_finite(self):
        with tempfile.TemporaryDirectory() as raw:
            p=Path(raw)/'features.npz';npz(p)
            result=check_npz(p)
            self.assertEqual((result['rows'],result['dimensions']),(1,2))

    def test_npz_pickle_object_dtype_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            p=Path(raw)/'features.npz';npz(p,dtype='|O')
            with self.assertRaises(ValueError):check_npz(p)

    def test_npz_nonfinite_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            p=Path(raw)/'features.npz';npz(p,values=[float('nan'),0])
            with self.assertRaises(ValueError):check_npz(p)

    def test_npz_duplicate_keys_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            p=Path(raw)/'features.npz';npz(p,keys=['0'*64]*2,values=[0,1,2,3])
            with self.assertRaises(ValueError):check_npz(p)

    def test_restore_refuses_existing_different_bytes(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);target=root/'tree';(target/'data').mkdir(parents=True);(target/'data/x.csv').write_bytes(b'old')
            data=b'row_id,label\nfixture,1\n';manifest={'files':[{'archive_path':'project/data/x.csv','project_relative_path':'data/x.csv','size_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}]}
            archive=root/'input.tar.gz'
            with tarfile.open(archive,'w:gz') as writer:
                for name,value in [('project/data/x.csv',data),('SCIENTIFIC-INPUT-CLOSURE.original.json',json.dumps(manifest).encode())]:
                    member=tarfile.TarInfo(name);member.size=len(value);writer.addfile(member,io.BytesIO(value))
            with self.assertRaises(ValueError):restore(archive,target)
            self.assertEqual((target/'data/x.csv').read_bytes(),b'old')


if __name__=='__main__':unittest.main()
