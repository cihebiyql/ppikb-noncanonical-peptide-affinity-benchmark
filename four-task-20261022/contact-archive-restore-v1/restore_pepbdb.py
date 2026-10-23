"""Restore one fixed historical PepBDB archive. No extraction or artifact execution."""
from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time
import urllib.request
import uuid

SOURCE_URL = 'http://huanglab.phys.hust.edu.cn/pepbdb/db/download/pepbdb-20200318.tgz'
BASENAME = 'pepbdb-20200318.tgz'
EXPECTED_BYTES = 691391502
EXPECTED_SHA256 = '33327794f45018ecd94252c078b2e734279528d82fbed76683e9c346dec32917'
CHUNK = 1024 * 1024


class RestoreError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RestoreError('Every HTTP redirect is refused')


def _checked_path(path, *, make_directory=False):
    raw = Path(path)
    if '..' in raw.parts or '\x00' in str(raw):
        raise RestoreError('Traversal path is refused')
    if os.name == 'nt' and (str(raw).startswith(('\\\\', '//')) or ':' in str(raw)[2:]):
        raise RestoreError('UNC, device paths and alternate streams are refused')
    p = raw.absolute()
    for q in reversed([p, *p.parents]):
        try:
            info = q.lstat()
        except FileNotFoundError:
            if not make_directory:
                continue
            q.mkdir()
            info = q.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 1024:
            raise RestoreError('Filesystem links and reparse points are refused')
        if q != p or make_directory:
            if not stat.S_ISDIR(info.st_mode):
                raise RestoreError('Expected a regular directory ancestor')
        elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise RestoreError('Expected one regular file with no hard links')
    return p


def _open_existing(path):
    p = _checked_path(path)
    before = p.lstat()
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(p, flags)
    after = os.fstat(fd)
    if (not stat.S_ISREG(after.st_mode) or after.st_nlink != 1
            or getattr(after, 'st_file_attributes', 0) & 1024
            or (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)):
        os.close(fd)
        raise RestoreError('File identity changed or file is linked')
    return p, fd, after


def verify(path):
    """Offline full-size/full-SHA verification; never accesses the network."""
    p, fd, initial = _open_existing(path)
    h = hashlib.sha256()
    count = 0
    with os.fdopen(fd, 'rb') as stream:
        if initial.st_size != EXPECTED_BYTES:
            raise RestoreError('Archive byte count differs from the fixed release')
        while True:
            block = stream.read(min(CHUNK, EXPECTED_BYTES - count + 1))
            if not block:
                break
            count += len(block)
            if count > EXPECTED_BYTES:
                raise RestoreError('Archive grew past the fixed size')
            h.update(block)
        final = os.fstat(stream.fileno())
    _checked_path(p)
    current = p.lstat()
    if ((initial.st_dev, initial.st_ino, initial.st_size, initial.st_mtime_ns)
            != (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns)
            or (initial.st_dev, initial.st_ino) != (current.st_dev, current.st_ino)):
        raise RestoreError('Archive changed during verification')
    if count != EXPECTED_BYTES or h.hexdigest() != EXPECTED_SHA256:
        raise RestoreError('Archive SHA256 differs from the fixed release')
    return {'verified': True, 'bytes': count, 'sha256': h.hexdigest(), 'path': str(p)}


def _publish_no_replace(partial, destination):
    """Atomic no-overwrite rename; never creates a filesystem hard link."""
    _checked_path(partial)
    _checked_path(destination)
    if os.name == 'nt':
        # Windows rename refuses an existing destination, including a racing writer.
        os.rename(partial, destination)
    elif os.name == 'posix':
        # Do not fall back to POSIX rename(), which can replace an existing file.
        libc = ctypes.CDLL(None, use_errno=True)
        rename = getattr(libc, 'renameat2', None)
        if rename is None:
            raise RestoreError('Atomic no-replace rename is unavailable on this system')
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                           ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            if rename(fd, os.fsencode(partial.name), fd, os.fsencode(destination.name), 1):
                error = ctypes.get_errno()
                if error == errno.EEXIST:
                    raise FileExistsError(error, 'Destination already exists')
                raise RestoreError('Atomic no-replace rename failed')
        finally:
            os.close(fd)
    else:
        raise RestoreError('Unsupported atomic no-overwrite filesystem operation')


def fetch(destination_directory, *, socket_timeout=30, max_seconds=3600):
    """Fetch only SOURCE_URL into a new fixed-name file; retain every failed partial."""
    if (not math.isfinite(socket_timeout) or not 1 <= socket_timeout <= 60
            or not math.isfinite(max_seconds) or not 1 <= max_seconds <= 7200):
        raise RestoreError('Socket timeout must be 1..60 s; total bound 1..7200 s')
    root = _checked_path(destination_directory, make_directory=True)
    destination = _checked_path(root / BASENAME)
    if destination.exists():
        result = verify(destination)
        result.update(downloaded=False, reused_existing=True)
        return result
    partial = root / ('.' + BASENAME + '.' + uuid.uuid4().hex + '.part')
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0)
    flags |= getattr(os, 'O_NOFOLLOW', 0)
    start = time.monotonic()
    h = hashlib.sha256()
    count = 0
    # No proxy environment, credentials, caller-supplied URLs, or redirect recovery.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(SOURCE_URL, headers={
        'User-Agent': 'PepBDBFixedLegacyRestore/1.0', 'Accept-Encoding': 'identity'})
    try:
        with os.fdopen(os.open(partial, flags, 0o600), 'wb') as stream:
            _checked_path(partial)
            with opener.open(request, timeout=min(socket_timeout, max_seconds)) as response:
                if response.geturl() != SOURCE_URL or response.status != 200:
                    raise RestoreError('Response is not the exact fixed URL with status 200')
                if response.headers.get('Content-Encoding', 'identity').lower() != 'identity':
                    raise RestoreError('Encoded HTTP responses are refused')
                if response.headers.get('Transfer-Encoding') is not None:
                    raise RestoreError('Transfer-encoded HTTP responses are refused')
                if response.headers.get('Content-Length') != str(EXPECTED_BYTES):
                    raise RestoreError('HTTP Content-Length differs from the fixed release')
                while True:
                    if time.monotonic() - start > max_seconds:
                        raise RestoreError('Bounded stream time exceeded')
                    # read1 returns after at most one underlying socket read, so a
                    # trickling peer cannot hide indefinitely inside read(n).
                    block = response.read1(min(CHUNK, EXPECTED_BYTES - count + 1))
                    if time.monotonic() - start > max_seconds:
                        raise RestoreError('Bounded stream time exceeded')
                    if not block:
                        break
                    count += len(block)
                    if count > EXPECTED_BYTES:
                        raise RestoreError('HTTP response exceeds the fixed byte limit')
                    stream.write(block)
                    h.update(block)
            stream.flush()
            os.fsync(stream.fileno())
        if count != EXPECTED_BYTES or h.hexdigest() != EXPECTED_SHA256:
            raise RestoreError('Downloaded size or SHA256 differs from the fixed release')
        verify(partial)
        _checked_path(root, make_directory=True)
        _publish_no_replace(partial, destination)
        result = verify(destination)
        result.update(downloaded=True, reused_existing=False, transport='HTTP; no TLS',
                      integrity_basis='previously trusted fixed byte count and SHA256')
        return result
    except Exception as error:
        # Preserve bytes and never silently resume, retry, overwrite or delete evidence.
        raise RestoreError('Restore stopped; partial retained if created: ' + str(partial)
                           + '; cause=' + type(error).__name__ + ': ' + str(error)) from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    v = subs.add_parser('verify', help='Offline verify an existing archive')
    v.add_argument('--path', required=True)
    f = subs.add_parser('fetch', help='Download the single fixed archive; never unpack')
    f.add_argument('--destination-directory', required=True)
    f.add_argument('--socket-timeout', type=float, default=30)
    f.add_argument('--max-seconds', type=float, default=3600)
    args = parser.parse_args()
    try:
        result = (verify(args.path) if args.command == 'verify' else fetch(
            args.destination_directory, socket_timeout=args.socket_timeout,
            max_seconds=args.max_seconds))
        print(json.dumps(result, ensure_ascii=False))
    except (RestoreError, OSError, ValueError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
