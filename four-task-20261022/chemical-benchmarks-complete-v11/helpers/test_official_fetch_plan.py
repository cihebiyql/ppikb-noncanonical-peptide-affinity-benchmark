"""No-network fixtures for the official frozen-input acquisition helper."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fetch_locked_inputs import acquire,official_url,target_path


class FetchPlanTests(unittest.TestCase):
    def test_plan_never_downloads_or_rewrites_original_receipt(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);(root/'ASSET-RECEIPT.actual.json').write_bytes(b'original receipt\n')
            lock={'files':[{'project_relative_path':'model/config.json','url':'https://huggingface.co/fixture/repo/resolve/fixed/config.json','sha256':hashlib.sha256(b'{}').hexdigest(),'size_bytes':2}],'vendor_members':[]}
            with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected network')):
                result=acquire(lock,root)
            self.assertEqual(result['new_downloads'],0)
            self.assertEqual((root/'ASSET-RECEIPT.actual.json').read_bytes(),b'original receipt\n')

    def test_changed_existing_asset_refused(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);(root/'config.json').write_bytes(b'preserve')
            lock={'files':[{'project_relative_path':'config.json','url':'https://huggingface.co/fixture/repo/resolve/fixed/config.json','sha256':hashlib.sha256(b'{}').hexdigest(),'size_bytes':2}],'vendor_members':[]}
            with self.assertRaises(ValueError):acquire(lock,root)
            self.assertEqual((root/'config.json').read_bytes(),b'preserve')

    def test_only_official_https_urls_and_confined_destinations(self):
        for url in ('http://huggingface.co/file','https://unrelated.invalid/file','https://user:password@huggingface.co/file'):
            with self.assertRaises(ValueError):official_url(url)
        with tempfile.TemporaryDirectory() as raw:
            for name in ('../outside','/absolute','D:/outside','a\\b'):
                with self.assertRaises(ValueError):target_path(Path(raw),name)


if __name__=='__main__':unittest.main()
