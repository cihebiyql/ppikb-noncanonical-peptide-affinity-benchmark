"""Public metadata/log preparation; original inputs are never edited.

Not a model runner. Each transformation is explicit and both byte hashes remain
in the publication index. Original PPIKB prediction CSVs can remain byte-identical
under their source CC BY 4.0 terms; arbitrary raw-input fields are not allowlisted.
"""
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import tarfile

PREDICTION_FIELDS = {'row_id', 'source', 'split', 'group_id', 'global_group_id', 'endpoint', 'evaluation_stratum', 'label', 'prediction'}
SECRET_PATTERNS = [
    re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,})\b'),
    re.compile(r'(?i)(?:authorization\s*[:=]\s*["\']?bearer\s+)[A-Za-z0-9_.~+/-]{12,}'),
    re.compile(r'-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----'),
]
RAW_FIELDS = {'sequence', 'protein_sequence', 'peptide_sequence', 'target_sequence', 'peptide_smiles', 'smiles', 'input_ids', 'token_ids', 'raw_labels', 'labels'}
PATH_PATTERNS = [
    (re.compile(r'(?i)[CD]:[\\/]+work[\\/]+科研工作台[\\/]+research-tasks[\\/]+peptide-four-task-benchmark-20261022'), 'record-ref:project'),
    (re.compile(r'/data/qlyu/projects/peptide-four-task-benchmark-20261022'), 'record-ref:project'),
    (re.compile(r'/data1/qlyu-peptide-four-task-benchmark-20261022'), 'record-ref:compute-artifacts'),
    (re.compile(r'/data/qlyu/projects/peptide-binding-benchmark-20261020'), 'record-ref:runtime-project'),
    (re.compile(r'(?i)[A-Z]:[\\/]+(?:Users|work|tmp)[\\/]+[^\s"\'<>]+'), 'record-ref:private-local-path'),
    (re.compile(r'/(?:home|mnt|data|data1|scratch)/qlyu[^\s"\'<>]*'), 'record-ref:private-compute-path'),
    (re.compile(r'(?i)\b(?:node1|node23)(?:\.[A-Za-z0-9.-]+)?\b'), 'compute-node-ref'),
    (re.compile(r'\bqlyu\b'), 'compute-user-ref'),
    (re.compile(r'\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b'), 'private-network-ref'),
    (re.compile(r'(?<![A-Za-z0-9:/-])/(?:home|mnt|scratch|data|data1)/[^\s"\'<>]+'), 'record-ref:private-path#sha256:'),
    (re.compile(r'\bGPU-[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b'), 'gpu-ref:sha256:'),
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe_relative(raw):
    p = PurePosixPath(raw)
    if not raw or '\\' in raw or ':' in raw or p.is_absolute() or any(x in ('', '.', '..') for x in raw.split('/')):
        raise ValueError('Unsafe archive/public path')
    return p


def extract_checked(archive_path, output):
    """No tarfile.extractall, links, absolute paths, traversal or overwrite."""
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    with tarfile.open(archive_path, 'r:gz') as archive:
        members = archive.getmembers()
        paths = [safe_relative(x.name) for x in members]
        if len({x.as_posix() for x in paths}) != len(paths):
            raise ValueError('Duplicate archive members')
        for member, relative in zip(members, paths):
            if not member.isfile():
                raise ValueError('Only ordinary archive members are accepted')
            target = output.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(archive.extractfile(member).read())
    inventory = json.loads((output / 'COLLECTION.original.json').read_text(encoding='utf-8'))
    expected = {x['archive_path']: x for x in inventory['files'] if x['disposition'] == 'collected_original_bytes'}
    if set(expected) != {x.as_posix() for x in paths} - {'COLLECTION.original.json'}:
        raise ValueError('Inventory/member mismatch')
    for name, record in expected.items():
        data = output.joinpath(*safe_relative(name).parts).read_bytes()
        if len(data) != record['size_bytes'] or sha(data) != record['sha256']:
            raise ValueError('Collected original bytes fail source binding')
    return inventory


def sanitize_text(value):
    changes = []
    for index, (pattern, replacement) in enumerate(PATH_PATTERNS):
        def replace(match):
            actual=replacement+sha(match.group(0).encode())[:20] if replacement.endswith('#sha256:') or replacement=='gpu-ref:sha256:' else replacement
            changes.append({'rule': 'private_path_or_host_' + str(index), 'removed_text_sha256': sha(match.group(0).encode()), 'replacement': actual})
            return actual
        value = pattern.sub(replace, value)
    for index, pattern in enumerate(SECRET_PATTERNS):
        def replace_secret(match):
            changes.append({'rule': 'credential_' + str(index), 'removed_text_sha256': sha(match.group(0).encode()), 'replacement': '[REDACTED-CREDENTIAL]'})
            return '[REDACTED-CREDENTIAL]'
        value = pattern.sub(replace_secret, value)
    return value, changes


def sanitize_json(value, pointer=''):
    changes = []
    if isinstance(value, dict):
        result = {}
        actor=value.get('user',value.get('username'))
        unrelated=isinstance(actor,str) and actor!='qlyu'
        for key, child in value.items():
            public_key,key_changes=sanitize_text(key)
            if public_key in result:
                public_key+=' #source-key-sha256='+sha(key.encode())
            location = pointer + '/' + public_key
            changes.extend(dict(change,json_pointer=location,json_key=True) for change in key_changes)
            if key.lower() in ('user','username','owner_user') and isinstance(child,str):
                result[public_key]='compute-user-ref:sha256:'+sha(child.encode())[:20]
                changes.append({'rule':'private_compute_user_pseudonym','json_pointer':location,'removed_value_sha256':sha(child.encode())})
            elif unrelated and key.lower() in ('cmdline','command_line','command','argv','args','name') and isinstance(child,(str,list)):
                result[public_key]='unrelated-process-command-ref:sha256:'+sha(json.dumps(child,ensure_ascii=False).encode())[:20]
                changes.append({'rule':'unrelated_process_command_not_project_science','json_pointer':location,'removed_value_sha256':sha(json.dumps(child,ensure_ascii=False).encode())})
            elif key.lower() in RAW_FIELDS or key.lower().endswith(('_smiles','_sequence')):
                changes.append({'rule': 'raw_input_field_not_in_this_log_release', 'json_pointer': location, 'removed_value_sha256': sha(json.dumps(child, ensure_ascii=False, sort_keys=True).encode())})
                result[public_key] = {'withheld': 'Raw input or unclassified label array; original retained locally and source hash indexed'}
            else:
                result[public_key], child_changes = sanitize_json(child, location)
                changes.extend(child_changes)
        return result, changes
    if isinstance(value, list):
        result = []
        for index, child in enumerate(value):
            cleaned, child_changes = sanitize_json(child, pointer + '/' + str(index))
            result.append(cleaned)
            changes.extend(child_changes)
        return result, changes
    if isinstance(value, str):
        result, changes = sanitize_text(value)
        return result, [dict(x, json_pointer=pointer) for x in changes]
    return value, []  # Exact numeric/scientific leaves remain numeric and equal.


def inspect_prediction_csv(data, expected_rows=None, expected_ids=None):
    stream = io.StringIO(data.decode('utf-8-sig'), newline='')
    reader = csv.DictReader(stream)
    if not reader.fieldnames or set(reader.fieldnames) != PREDICTION_FIELDS:
        raise ValueError('Prediction CSV requires explicit field-by-field license/privacy review')
    rows = list(reader)
    ids = [row['row_id'] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate prediction record IDs')
    if expected_rows is not None and len(rows) != expected_rows:
        raise ValueError('Prediction row count mismatch')
    if expected_ids is not None and ids != list(expected_ids):
        raise ValueError('Prediction ID/order mismatch')
    if any('ppikb' not in row['source'].lower() for row in rows):
        raise ValueError('Non-PPIKB data require a separate redistribution review')
    if any(row['endpoint'] != 'pKd' for row in rows):
        raise ValueError('Mixed/unexpected endpoints')
    for row in rows:
        if not all(math.isfinite(float(row[key])) for key in ('label', 'prediction')):
            raise ValueError('Non-finite experimental label or prediction')
    return {'n': len(rows), 'row_id_order_sha256': sha(('\n'.join(ids) + '\n').encode()), 'fields': reader.fieldnames, 'transform': 'none; original UTF8 prediction CSV bytes preserved under PPIKB CC BY4.0 with attribution'}


def prepare_bytes(data, suffix):
    text = data.decode('utf-8-sig')
    if suffix == '.json':
        parsed = json.loads(text)
        cleaned, changes = sanitize_json(parsed)
        result = (json.dumps(cleaned, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode() if changes else data
    elif suffix == '.jsonl':
        result, changes = [], []
        for index, line in enumerate(text.splitlines()):
            cleaned, additions = sanitize_json(json.loads(line), '/' + str(index))
            result.append(json.dumps(cleaned, ensure_ascii=False, allow_nan=False))
            changes.extend(additions)
        result = ('\n'.join(result) + '\n').encode() if changes else data
    else:
        cleaned, changes = sanitize_text(text)
        # A raw biological input printed in a log needs an explicit manual rule;
        # fail closed instead of silently omitting an entire candidate's history.
        if suffix!='.py':
            for match in re.finditer(r'(?im)\b(?:peptide_smiles|protein_sequence|peptide_sequence|target_sequence|input_ids|token_ids)\s*[:=]', cleaned):
                # Actual 4GiB OOM traceback prints this source call, not token
                # values. Preserve the failure and symbolic code line. This
                # exact exception does not permit numeric input arrays.
                symbolic_traceback = match.group(0).replace(' ','')=='input_ids=' and cleaned[match.end():].startswith('ids, attention_mask=mask, return_dict=True)')
                if not symbolic_traceback:
                    raise ValueError('Raw input field in text requires explicit reviewed redaction')
        result = cleaned.encode() if changes else data
    decoded = result.decode('utf-8-sig')
    if any(pattern.search(decoded) for pattern in SECRET_PATTERNS):
        raise ValueError('Secret scanner found a residual match')
    return result, changes


def deterministic_archive(files, output):
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    with output.open('xb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as compressed, tarfile.open(fileobj=compressed, mode='w|') as archive:
        for name, data in sorted(files.items()):
            safe_relative(name)
            member = tarfile.TarInfo(name)
            member.size = len(data)
            member.mode = 0o644
            member.mtime = 0
            archive.addfile(member, io.BytesIO(data))
    return {'sha256': sha(output.read_bytes()), 'size_bytes': output.stat().st_size, 'members': len(files)}
