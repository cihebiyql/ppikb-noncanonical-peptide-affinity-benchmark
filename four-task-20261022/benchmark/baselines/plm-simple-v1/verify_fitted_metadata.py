"""Inspect hash-verified owned Ridge/scaler metadata; no fitting or prediction calls."""
import hashlib
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
RUN=ROOT/'runs/plm-simple-v1/heads'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
manifest=json.loads((HERE/'inputs/remote-manifest.json').read_text())
checks=[]
for view in manifest['views']:
    frame=pd.read_csv(view['path'],keep_default_na=False,float_precision='round_trip')
    frozen=np.load(RUN/view['id']/'features.npz',allow_pickle=False)
    assert list(frozen['row_ids'])==list(frame['row_id'])
    x=frozen['features'][frame.split.to_numpy()=='train']
    expected=np.mean(x,axis=0,dtype=np.float64)
    for seed in range(10):
        run=RUN/view['id']/'linear'/f'seed-{seed:02d}'
        candidates=json.loads((run/'candidates.json').read_text())
        for candidate in candidates:
            path=run/f'candidate-{candidate["candidate"]}.joblib'
            assert sha(path)==candidate['model_sha256']
            model=joblib.load(path)
            assert int(model[0].n_samples_seen_)==len(x)
            difference=float(np.max(np.abs(model[0].mean_-expected)))
            assert difference<1e-8
            assert model[1].solver=='lsqr' and model[1].tol==1e-4 and model[1].max_iter==1000
            iterations=int(np.max(model[1].n_iter_))
            checks.append({'view_id':view['id'],'seed':seed,'candidate':candidate['candidate'],
                'training_rows':len(x),'features':x.shape[1],'scaler_mean_max_abs_difference':difference,
                'ridge_iterations':iterations,'iteration_cap_reached':iterations>=1000,
                'model_sha256':sha(path)})
report={'passed':len(checks)==60,'checks':checks,'models_checked':len(checks),
        'iteration_cap_reached_models':sum(row['iteration_cap_reached'] for row in checks),
        'new_fit_count':0,'new_forward_count':0,'training_only_scaler_verified':True,'code_sha256':sha(__file__)}
(RUN/'fitted-metadata-independent-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({key:value for key,value in report.items() if key!='checks'}))
