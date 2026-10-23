"""Training-row-only runtime check for the unchanged manual learner grid."""
import json
from pathlib import Path
import time
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
import run_manual_controls as control
HERE=Path(__file__).resolve().parent
started=time.time();checks=[]
manifest=json.loads((HERE/'remote-manifest.json').read_text())
for view in manifest['views']:
    frame=pd.read_csv(view['path'],keep_default_na=False,float_precision='round_trip')
    frame=frame.loc[frame.split=='train'].head(44).reset_index(drop=True)
    x,_=control.build_features(frame,view['task']);y=frame.label.to_numpy(dtype=float)
    for name,grid in control.models(False).items():
        for candidate,parameters in enumerate(grid):
            estimator=control.make_model(name,parameters,0,False)
            with threadpool_limits(limits=2):
                estimator.fit(x[:40],y[:40]);pred=estimator.predict(x[40:])
            assert np.isfinite(pred).all() and pred.shape==(4,)
            if name=='linear':np.testing.assert_allclose(estimator[0].mean_,x[:40].mean(0,dtype=np.float64),atol=1e-8,rtol=1e-8)
            checks.append({'view_id':view['id'],'model':name,'candidate':candidate,'features':x.shape[1],'train_rows':40,'query_training_rows':4})
report={'passed':len(checks)==30,'checks':checks,'toy_runtime_fit_count':len(checks),
    'scientific_selected_run_count':0,'test_rows_used':0,'elapsed_seconds':time.time()-started,'code_sha256':control.sha(__file__)}
(HERE/'runtime-canary.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
