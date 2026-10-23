import hashlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import restore_pepbdb as r


class Response(io.BytesIO):
    def __init__(self, payload, *, length=None, status=200, url=r.SOURCE_URL, encoding=None):
        super().__init__(payload)
        self.status = status
        self.url = url
        self.headers = {'Content-Length': str(len(payload) if length is None else length)}
        if encoding is not None:
            self.headers['Content-Encoding'] = encoding

    def geturl(self):
        return self.url


class Opener:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request.full_url, timeout))
        return self.response


class Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.payload = b'synthetic archive bytes only\n'
        self.byte_patch = patch.object(r, 'EXPECTED_BYTES', len(self.payload))
        self.sha_patch = patch.object(r, 'EXPECTED_SHA256', hashlib.sha256(self.payload).hexdigest())
        self.byte_patch.start()
        self.sha_patch.start()

    def tearDown(self):
        self.sha_patch.stop()
        self.byte_patch.stop()
        self.temporary.cleanup()

    def call(self, response, **kwargs):
        opener = Opener(response)
        with patch.object(r.urllib.request, 'build_opener', return_value=opener):
            result = r.fetch(self.root / 'out', **kwargs)
        self.assertEqual(opener.requests[0][0], r.SOURCE_URL)
        return result

    def expect_partial(self, response, **kwargs):
        with self.assertRaises(r.RestoreError):
            self.call(response, **kwargs)
        self.assertFalse((self.root / 'out' / r.BASENAME).exists())
        self.assertEqual(len(list((self.root / 'out').glob('*.part'))), 1)

    def test_success_exact_fixed_origin(self):
        result = self.call(Response(self.payload))
        self.assertTrue(result['downloaded'])
        self.assertEqual((self.root / 'out' / r.BASENAME).read_bytes(), self.payload)
        self.assertFalse(list((self.root / 'out').glob('*.part')))

    def test_offline_verify_never_builds_network(self):
        p = self.root / 'existing.tgz'
        p.write_bytes(self.payload)
        with patch.object(r.urllib.request, 'build_opener', side_effect=AssertionError('network')):
            self.assertTrue(r.verify(p)['verified'])

    def test_existing_identical_no_network(self):
        (self.root / 'out').mkdir()
        p = self.root / 'out' / r.BASENAME
        p.write_bytes(self.payload)
        with patch.object(r.urllib.request, 'build_opener', side_effect=AssertionError('network')):
            self.assertFalse(r.fetch(p.parent)['downloaded'])

    def test_existing_wrong_never_overwritten(self):
        (self.root / 'out').mkdir()
        p = self.root / 'out' / r.BASENAME
        p.write_bytes(b'KEEP')
        with self.assertRaises(r.RestoreError):
            r.fetch(p.parent)
        self.assertEqual(p.read_bytes(), b'KEEP')

    def test_wrong_size_offline(self):
        p = self.root / 'x'
        p.write_bytes(b'x')
        with self.assertRaises(r.RestoreError):
            r.verify(p)

    def test_wrong_sha_offline(self):
        p = self.root / 'x'
        p.write_bytes(b'x' * len(self.payload))
        with self.assertRaises(r.RestoreError):
            r.verify(p)

    def test_wrong_sha_preserves_full_partial(self):
        self.expect_partial(Response(b'x' * len(self.payload)))
        self.assertEqual(next((self.root / 'out').glob('*.part')).stat().st_size, len(self.payload))

    def test_short_stream_preserved(self):
        self.expect_partial(Response(self.payload[:-1], length=len(self.payload)))
        self.assertEqual(next((self.root / 'out').glob('*.part')).stat().st_size, len(self.payload) - 1)

    def test_oversize_stream_not_published(self):
        self.expect_partial(Response(self.payload + b'x', length=len(self.payload)))

    def test_bad_declared_length(self):
        self.expect_partial(Response(self.payload, length=99))

    def test_missing_declared_length(self):
        response = Response(self.payload)
        response.headers = {}
        self.expect_partial(response)

    def test_non_200_status(self):
        self.expect_partial(Response(self.payload, status=206))

    def test_response_url_cannot_change(self):
        self.expect_partial(Response(self.payload, url=r.SOURCE_URL + '?changed=1'))

    def test_encoded_response_refused(self):
        self.expect_partial(Response(self.payload, encoding='gzip'))

    def test_transfer_encoding_refused(self):
        response = Response(self.payload)
        response.headers['Transfer-Encoding'] = 'chunked'
        self.expect_partial(response)

    def test_every_redirect_refused(self):
        for url in (r.SOURCE_URL, 'https://huanglab.phys.hust.edu.cn/pepbdb/db/download/pepbdb-20200318.tgz',
                    'http://example.org/x'):
            with self.subTest(url=url), self.assertRaises(r.RestoreError):
                r.NoRedirect().redirect_request(None, None, 302, '', {}, url)

    def test_timeout_keeps_partial(self):
        response = Response(self.payload)
        with patch.object(response, 'read1', side_effect=TimeoutError('bounded synthetic timeout')):
            self.expect_partial(response)

    def test_wall_deadline_keeps_partial(self):
        with patch.object(r.time, 'monotonic', side_effect=[0, 2]):
            self.expect_partial(Response(self.payload), max_seconds=1)

    def test_invalid_bounds_before_network_or_files(self):
        for kwargs in ({'max_seconds': 0}, {'max_seconds': float('nan')},
                       {'socket_timeout': 61}, {'max_seconds': 7201}):
            with self.subTest(kwargs=kwargs), self.assertRaises(r.RestoreError):
                r.fetch(self.root / 'out', **kwargs)
        self.assertFalse((self.root / 'out').exists())

    def test_traversal_refused(self):
        with self.assertRaises(r.RestoreError):
            r.fetch(self.root / 'nested' / '..' / 'out')

    def test_hardlinked_file_refused(self):
        p = self.root / 'x'
        p.write_bytes(self.payload)
        try:
            os.link(p, self.root / 'link')
        except OSError as error:
            self.fail('This synthetic hardlink test requires an ordinary local filesystem: ' + str(error))
        with self.assertRaises(r.RestoreError):
            r.verify(p)

    def test_symlink_refused_when_supported(self):
        p = self.root / 'x'
        p.write_bytes(self.payload)
        link = self.root / 'link'
        try:
            link.symlink_to(p)
        except OSError:
            # Windows often disallows creating symlinks; exercise the same lstat
            # symlink/reparse predicates synthetically without elevated rights.
            real_lstat = Path.lstat
            info = p.lstat()
            class Reparse:
                st_mode = info.st_mode
                st_nlink = 1
                st_file_attributes = 1024
            def fake_lstat(path, *args, **kwargs):
                return Reparse() if path == p else real_lstat(path, *args, **kwargs)
            with patch.object(Path, 'lstat', fake_lstat), self.assertRaises(r.RestoreError):
                r.verify(p)
        else:
            with self.assertRaises(r.RestoreError):
                r.verify(link)

    def test_destination_ancestor_reparse_refused(self):
        p = self.root / 'out'
        p.mkdir()
        real_lstat = Path.lstat
        info = p.lstat()
        class Reparse:
            st_mode = info.st_mode
            st_nlink = 1
            st_file_attributes = 1024
        def fake_lstat(path, *args, **kwargs):
            return Reparse() if path == p else real_lstat(path, *args, **kwargs)
        with patch.object(Path, 'lstat', fake_lstat), self.assertRaises(r.RestoreError):
            r.fetch(p)

    def test_atomic_publication_race_does_not_overwrite(self):
        original = r._publish_no_replace
        def racing_publish(partial, destination):
            destination.write_bytes(b'RACING KEEP')
            return original(partial, destination)
        with patch.object(r, '_publish_no_replace', side_effect=racing_publish):
            with self.assertRaises(r.RestoreError):
                self.call(Response(self.payload))
        self.assertEqual((self.root / 'out' / r.BASENAME).read_bytes(), b'RACING KEEP')
        self.assertEqual(len(list((self.root / 'out').glob('*.part'))), 1)

    def test_production_pin_not_a_user_input(self):
        self.assertEqual(r.SOURCE_URL, 'http://huanglab.phys.hust.edu.cn/pepbdb/db/download/pepbdb-20200318.tgz')
        with self.assertRaises(TypeError):
            r.fetch(self.root / 'out', url='http://example.org/elsewhere')


if __name__ == '__main__':
    unittest.main(verbosity=2)
