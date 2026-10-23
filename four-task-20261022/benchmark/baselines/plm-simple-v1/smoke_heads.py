"""Bounded training-row-only estimator/runtime canary; not a scientific result."""
import json
from pathlib import Path
import time
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
import run_heads

HERE=Path(__file__).resolve().parent
started=time.time()
manifest=json.loads((HERE/'inputs/remote-manifest.json').read_text())
checks=[]
for view in manifest['views']:
    frame=pd.read_csv(view['path'],keep_default_na=False,float_precision='round_trip')
    frame=frame.loc[frame.split=='train'].head(44).reset_index(drop=True)
    x,audit=run_heads.build_features(frame,view['task']);y=frame.label.to_numpy(dtype=float)
    assert audit['chemical_identity_encoded'] is False
    for name,grid in run_heads.models(False).items():
        for candidate,parameters in enumerate(grid):
            est=run_heads.make_model(name,parameters,0,False)
            with threadpool_limits(limits=2):
                est.fit(x[:40],y[:40]);pred=est.predict(x[40:])
            assert pred.shape==(4,) and np.isfinite(pred).all()
            if name=='linear':
                np.testing.assert_allclose(est[0].mean_,x[:40].mean(axis=0,dtype=np.float64),rtol=1e-8,atol=1e-8)
            checks.append({'view':view['id'],'model':name,'candidate':candidate,'features':x.shape[1],
                           'fit_rows':40,'query_rows':4,'only_frozen_training_rows_opened_for_fitting':True})
report={'passed':len(checks)==30,'checks':checks,'toy_runtime_fit_count':len(checks),
        'scientific_selected_run_count':0,'elapsed_seconds':time.time()-started,'test_rows_used':0,
        'code_sha256':run_heads.sha(__file__)}
(HERE/'head-runtime-canary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
