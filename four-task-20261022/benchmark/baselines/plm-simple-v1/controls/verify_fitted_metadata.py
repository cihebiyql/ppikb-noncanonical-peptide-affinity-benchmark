"""Check original-auto Ridge/scalers against actual training-only manual features, no predict/fit."""
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from verify_manual_controls import sha

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
RUN=ROOT/'runs/plm-cohort-manual-controls-v1'
manifest=json.loads((HERE/'remote-manifest.json').read_text());checks=[]
for view in manifest['views']:
    frame=pd.read_csv(view['path'],keep_default_na=False,float_precision='round_trip')
    obj=np.load(RUN/view['id']/'features.npz',allow_pickle=False)
    assert list(obj['row_ids'])==list(frame.row_id)
    x=obj['features'][frame.split.to_numpy()=='train'];mean=x.mean(0,dtype=np.float64)
    for seed in range(10):
        run=RUN/view['id']/'linear'/f'seed-{seed:02d}'
        for candidate in json.loads((run/'candidates.json').read_text()):
            path=run/f'candidate-{candidate["candidate"]}.joblib';assert sha(path)==candidate['model_sha256']
            model=joblib.load(path);assert model[1].solver=='auto'
            assert int(model[0].n_samples_seen_)==len(x)
            delta=float(np.max(np.abs(model[0].mean_-mean)));assert delta<1e-8
            checks.append({'view_id':view['id'],'seed':seed,'candidate':candidate['candidate'],
                'n_training':len(x),'n_features':x.shape[1],'scaler_mean_max_abs_difference':delta,
                'configured_solver':model[1].solver,'model_sha256':sha(path)})
report={'passed':len(checks)==60,'models_checked':len(checks),'training_only_scaler_verified':True,
    'new_fit_count':0,'new_forward_count':0,'checks':checks,'code_sha256':sha(__file__)}
(RUN/'fitted-metadata-independent-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='checks'}))
