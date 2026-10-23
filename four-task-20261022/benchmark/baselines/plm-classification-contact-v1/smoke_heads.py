"""Both-class, training-row-only runtime canary of all five binary families/two candidates."""
import json
from pathlib import Path
import time
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
import run_heads as baseline

HERE=Path(__file__).resolve().parent
started=time.time();manifest=json.loads((HERE/'inputs/remote-manifest.json').read_text());checks=[]
for view in manifest['views']:
    frame=pd.read_csv(view['path'],keep_default_na=False,float_precision='round_trip')
    training=frame.loc[frame.split=='train'];negative=training.loc[training.label.astype(float)==0].head(22)
    positive=training.loc[training.label.astype(float)==1].head(22)
    assert len(negative)==len(positive)==22
    sample=pd.concat([negative.head(20),positive.head(20),negative.tail(2),positive.tail(2)]).reset_index(drop=True)
    x,audit=baseline.build_features(sample,view['task']);y=sample.label.to_numpy(dtype=float)
    altered=sample.copy();altered['label']=1-altered['label'].astype(float)
    altered['minimum_heavyatom_distance_A']=-12345.;altered['observed_target']='NEVER_A_FEATURE'
    other,_=baseline.build_features(altered,view['task']);np.testing.assert_array_equal(x,other)
    for name,grid in baseline.models(True).items():
        for candidate,parameters in enumerate(grid):
            estimator=baseline.make_model(name,parameters,0,True)
            with threadpool_limits(limits=2):
                estimator.fit(x[:40],y[:40]);pred=baseline.predict(estimator,x[40:],True)
            assert pred.shape==(4,) and np.isfinite(pred).all() and ((pred>=0)&(pred<=1)).all()
            if name=='linear':np.testing.assert_allclose(estimator[0].mean_,x[:40].mean(0,dtype=np.float64),atol=1e-8,rtol=1e-8)
            checks.append({'view_id':view['id'],'model':name,'candidate':candidate,'train_rows':40,
                'query_training_rows':4,'features':x.shape[1],'feature_label_geometry_invariance_checked':True})
receipt={'passed':len(checks)==20,'checks':checks,'toy_runtime_fits':len(checks),'scientific_selected_runs':0,
         'test_rows_used':0,'new_PLM_forward_calls':0,'elapsed_seconds':time.time()-started,'code_sha256':baseline.sha(__file__)}
(HERE/'head-runtime-canary.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps(receipt))
