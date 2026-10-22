"""Read installed package/source facts; instantiate only unfitted RF estimators."""
from pathlib import Path
import inspect
import json
import os
import platform
import shutil
import sys
import features

HERE=Path(__file__).resolve().parent
def main():
    import sklearn,numpy,scipy,joblib,rdkit
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.tree import DecisionTreeRegressor
    from rdkit.Chem import rdFingerprintGenerator
    source_dir=HERE/'assets/sklearn-source';source_dir.mkdir(parents=True,exist_ok=False)
    source_files={}
    for name,object_ in [('RandomForestRegressor',RandomForestRegressor),('DecisionTreeRegressor',DecisionTreeRegressor)]:
        source=Path(inspect.getfile(object_))
        target=source_dir/source.name
        shutil.copy2(source,target)
        source_files[name]=dict(installed_path=str(source),sha256=features.sha(source),frozen_copy=str(target))
    defaults=RandomForestRegressor().get_params(deep=False)
    profiles=[]
    for index,leaf in enumerate((2,5)):
        values=dict(defaults,n_estimators=200,max_features='sqrt',min_samples_leaf=leaf,n_jobs=1,random_state=0,
                    bootstrap=True,max_depth=None)
        profiles.append(dict(candidate_index=index,effective_parameters_seed0=values))
    record=dict(stage='installed_library_and_unfitted_parameter_probe_only',python=sys.version,executable=sys.executable,
        host=platform.node(),CUDA_VISIBLE_DEVICES=os.environ.get('CUDA_VISIBLE_DEVICES'),
        versions=dict(sklearn=sklearn.__version__,numpy=numpy.__version__,scipy=scipy.__version__,joblib=joblib.__version__,rdkit=rdkit.__version__),
        source_files=source_files,RF_init_signature=str(inspect.signature(RandomForestRegressor)),installed_RF_defaults=defaults,
        candidate_profiles=profiles,Morgan_generator_info=features.GENERATOR.GetInfoString(),
        Morgan_native_module=dict(path=str(rdFingerprintGenerator.__file__),sha256=features.sha(Path(rdFingerprintGenerator.__file__))),
        feature_spec_sha256=features.sha(HERE/'feature-spec-v1.json'),feature_code_sha256=features.sha(HERE/'features.py'),
        real_fits=0,gold_reads=0,trained_model_reads=0)
    (HERE/'installed-assets-v1.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record,indent=2))
if __name__=='__main__':main()
