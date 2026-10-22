"""Add the global selection barrier to the still-unlaunched v2 scoring drafts."""
from pathlib import Path
import runner
HERE=Path(__file__).resolve().parent
def main():
    for path in (HERE/'formal-specs-v2').glob('*-score.json'):
        spec=runner.read_json(path)
        expected=str(HERE/'formal-runs-v1/all-selections-frozen.json')
        if spec.get('selection_barrier_path') not in (None,expected):raise ValueError('Different gate configured')
        spec['selection_barrier_path']=expected
        runner.write_json(path,spec)
    print('Draft scoring gates complete. No fits or scoring launched.')
if __name__=='__main__':main()
