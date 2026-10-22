"""Root metadata-only exit check. Run in WSL after observer89030 actually exits."""
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parents[1]
INDEX_SHA = '17c2bd173fb13c537337e99420993177e3890b9f300dbcd576d77e67a4b79b69'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    progress = read(P / 'control/scoring-launch-v1/pool-runs/progress.json')
    assert progress['complete_count'] == 200 and progress['failed_count'] == 0
    assert progress['pending'] == 0 and progress['active'] is None
    assert not progress.get('watchdog_reason')
    native_path = P / 'control/observed-pools/nn-score-real-v1/native-exit.json'
    native = read(native_path)
    assert native['native_wsl_exit_code'] == 0
    assert native['native_exit_directly_observed'] and native['actual_wait_completed']
    assert not Path('/proc/794579').exists()
    index_path = P / 'administration/i1/NN-score-pool-index.json'
    assert sha(index_path) == INDEX_SHA
    index = read(index_path)
    assert len(index['units']) == 200
    pgids = set()
    scores = rows = 0
    for entry in index['units']:
        assert sha(entry['binding']['path']) == entry['binding']['sha256']
        binding = read(entry['binding']['path'])
        root = Path(binding['receipt_root'])
        closed = read(root / 'pool-exit-verification.json')
        unit = read(root / 'unit-complete.json')
        assert closed['exit_code'] == 0 and closed['private_session_handles_absent']
        assert closed['pool_pid'] == 794579 and closed['index_sha256'] == INDEX_SHA
        assert closed['unit_id'] == entry['unit_id'] == unit['unit_id']
        assert closed['binding_sha256'] == entry['binding']['sha256'] == unit['binding_sha256']
        assert closed['pid'] == unit['pid'] and unit['status'] == 'complete'
        assert len(unit['scores']) == 3
        pgids.add(closed['pgid'])
        scores += len(unit['scores'])
        rows += sum(s['n'] for s in unit['scores'])
    live = []
    for stat in Path('/proc').glob('[0-9]*/stat'):
        try:
            values = stat.read_text().rsplit(')', 1)[1].split()
            if int(values[2]) in pgids:
                live.append(str(stat))
        except (FileNotFoundError, ProcessLookupError):
            pass
    assert not live, live
    assert scores == 600 and rows == 265800
    proof = dict(exit_code=0, native_exit_code=0, native_exit_directly_observed=True,
        pool_index_sha256=INDEX_SHA, private_session_handles_absent=True, pool_pid=794579,
        observed_at=native['observed_at'], observer_session_id=89030,
        source='Actual observer89030 wait completed; native WSL parent wait0; root verified200 unit-side exits and current absence of every private PGID and pool PID.',
        native_exit_receipt=dict(path=str(native_path), sha256=sha(native_path)),
        unit_exit_proofs_verified=200, actual_score_receipts=scores, actual_prediction_rows=rows)
    output = P / 'control/nn-score-native-exit0-proof-v1.json'
    with output.open('x', encoding='utf-8') as handle:
        json.dump(proof, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print(json.dumps(dict(path=str(output), sha256=sha(output), scores=scores, rows=rows)))


if __name__ == '__main__':
    main()
