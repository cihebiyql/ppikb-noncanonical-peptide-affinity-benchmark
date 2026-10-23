"""Read trusted hash-verified binary models; check training-only scaler and convergence metadata."""
import json
import joblib
import numpy as np
import pandas as pd
from mirror_artifacts import HERE, ROOT, RUN, sha, write

manifest=json.loads((HERE/'inputs/remote-manifest.json').read_text())
checks=[]
for view in manifest['views']:
    frame=pd.read_csv(view['path'],keep_default_na=False,float_precision='round_trip')
    obj=np.load(RUN/'heads'/view['id']/'features.npz',allow_pickle=False)
    assert list(obj['row_ids'])==list(frame.row_id)
    x=obj['features'][frame.split.to_numpy()=='train'];mean=x.mean(0,dtype=np.float64)
    for seed in range(10):
        directory=RUN/'heads'/view['id']/'linear'/f'seed-{seed:02d}'
        for candidate in json.loads((directory/'candidates.json').read_text()):
            path=directory/f'candidate-{candidate["candidate"]}.joblib'
            assert sha(path)==candidate['model_sha256']
            model=joblib.load(path)
            assert int(model[0].n_samples_seen_)==len(x)
            delta=float(np.max(np.abs(model[0].mean_-mean)));assert delta<1e-8
            assert model[1].max_iter==1500 and model[1].class_weight=='balanced'
            checks.append({'view_id':view['id'],'seed':seed,'candidate':candidate['candidate'],
                'training_samples':len(x),'n_features':x.shape[1],'scaler_mean_max_abs_difference':delta,
                'solver':model[1].solver,'max_iter':model[1].max_iter,'n_iter':model[1].n_iter_.tolist(),
                'hit_iteration_cap':bool(np.any(model[1].n_iter_>=model[1].max_iter)),'model_sha256':sha(path)})
report={'passed':len(checks)==40,'models_checked':len(checks),'training_only_scaler_verified':True,
    'iteration_cap_models':sum(r['hit_iteration_cap'] for r in checks),'new_fit_count':0,'new_forward_count':0,
    'checks':checks,'code_sha256':sha(__file__)}
write(RUN/'heads/fitted-metadata-independent-audit.json',report)
print(json.dumps({k:v for k,v in report.items() if k!='checks'}))
