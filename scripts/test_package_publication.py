import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
import package_publication as p


class PackageTests(unittest.TestCase):
    def test_split_roundtrip_and_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);writer=p.SplitWriter(base/'assets',base/'progress.json',size=57)
            data=b'synthetic scientific artifact\n'*100
            with gzip.GzipFile(fileobj=writer,mode='wb',mtime=0) as zipped:
                with tarfile.open(fileobj=zipped,mode='w|') as tar:
                    info=tarfile.TarInfo('benchmark/synthetic.txt');info.size=len(data)
                    tar.addfile(info,io.BytesIO(data))
            writer.close();self.assertGreater(len(writer.assets),1)
            joined=b''
            for part in writer.assets:
                b=(base/'assets'/part['name']).read_bytes()
                self.assertEqual(len(b),part['bytes']);self.assertLessEqual(len(b),57)
                self.assertEqual(hashlib.sha256(b).hexdigest(),part['sha256']);joined+=b
            with tarfile.open(fileobj=io.BytesIO(joined),mode='r:gz') as tar:
                self.assertEqual(tar.extractfile('benchmark/synthetic.txt').read(),data)

    def test_hash_reader(self):
        data=b'ordinary metadata only';reader=p.HashReader(io.BytesIO(data),'synthetic.json',True)
        self.assertEqual(reader.read(8)+reader.read(),data)
        self.assertEqual(reader.hash.hexdigest(),hashlib.sha256(data).hexdigest())

    def test_credential_pattern_spanning_chunks_blocks_without_value(self):
        value=b'gh' + b'p_' + b'A'*36
        reader=p.HashReader(io.BytesIO(value),'synthetic.json',True)
        reader.read(4)
        with self.assertRaisesRegex(ValueError,'value withheld'):reader.read()

    def test_explicit_permission_exclusion(self):
        policy={'excluded_prefixes':[{'prefix':'vendor/','reason':'third-party'}],'excluded_paths':[{'path':'private.env','reason':'credential'}]}
        self.assertEqual(p.exclusion('vendor/file.py',policy),'third-party')
        self.assertEqual(p.exclusion('private.env',policy),'credential')
        self.assertIsNone(p.exclusion('results/seed0.json',policy))
        self.assertIsNotNone(p.exclusion('model/__pycache__/x.pyc',policy))


if __name__=='__main__':unittest.main()
