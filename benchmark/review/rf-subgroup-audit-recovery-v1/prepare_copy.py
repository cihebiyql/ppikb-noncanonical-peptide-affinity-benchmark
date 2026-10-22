"""Create a versioned, minimal RF audit copy; never alter frozen v5/data."""
import ast
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REVIEW = HERE.parent
source = REVIEW / 'recompute_RF_v5.py'
expected = '9d6f1e67d6a08c45316014729ffc850e1d59bd6ab3da1c989bcb4280e731e905'
if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
    raise ValueError('Frozen RFv5 source changed')
text = source.read_text(encoding='utf-8')
changes = [
    ('P = Path(__file__).resolve().parent.parent', 'REVIEW = Path(__file__).resolve().parent.parent\nP = REVIEW.parent'),
    ("Path(__file__).with_name('recompute_metrics.py')", "REVIEW / 'recompute_metrics.py'"),
    ("            if flag not in row or type(row[flag]) is not bool or row[flag] != (row['record_id'] in wanted):\n                raise ValueError('External subgroup flag missing or changed')",
     "            if flag in row and (type(row[flag]) is not bool or row[flag] != (row['record_id'] in wanted)):\n                raise ValueError('Existing external subgroup flag changed')\n            if flag not in row:\n                # Private audit rows only: frozen ID membership, never gold or predictions.\n                row[flag] = row['record_id'] in wanted"),
]
for i, (old, new) in enumerate(changes):
    if text.count(old) != (2 if i == 1 else 1):
        raise ValueError('Unexpected source replacement count')
    text = text.replace(old, new)
ast.parse(text)
with (HERE / 'recompute_RF_v6.py').open('x', encoding='utf-8', newline='\n') as handle:
    handle.write(text)
print(hashlib.sha256((HERE / 'recompute_RF_v6.py').read_bytes()).hexdigest())
