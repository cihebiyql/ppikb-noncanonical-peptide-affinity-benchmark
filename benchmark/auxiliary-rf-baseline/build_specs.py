"""Only metadata/IDs: construct 40 unsigned RF units / 80 fixed candidates."""
from pathlib import Path
import common

def main():
    output=common.HERE/'specs-v1';output.mkdir(exist_ok=False)
    x=common.HERE/'X-final-manifest-v1.json';assets=common.HERE/'installed-assets-v1.json'
    units=[]
    for panel in common.PANELS:
        root=common.PROJECT/'execution/prepared-panels-wsl-v3'/panel
        for regime in common.REGIMES:
            idsroot=common.PROJECT/'data-protocol/frozen-v1/splits'/panel/regime
            trainids=idsroot/'train-ids.json';validids=idsroot/'validation-ids.json'
            for seed in range(10):
                name=f'{panel}__RFclassical__{regime}__seed-{seed}'
                spec=dict(method_id=common.METHOD,panel=panel,regime=regime,seed=seed,
                    train_rows=str(root/'train.jsonl'),validation_rows=str(root/'validation.jsonl'),
                    train_rows_sha256=common.sha(root/'train.jsonl'),validation_rows_sha256=common.sha(root/'validation.jsonl'),
                    train_ids=str(trainids),validation_ids=str(validids),
                    train_ids_sha256=common.sha(trainids),validation_ids_sha256=common.sha(validids),
                    train_n=len(common.read(trainids)),validation_n=len(common.read(validids)),
                    feature_manifest=str(x),feature_manifest_sha256=common.sha(x),
                    installed_assets=str(assets),installed_assets_sha256=common.sha(assets),
                    candidates=[dict(candidate_index=0,min_samples_leaf=2),dict(candidate_index=1,min_samples_leaf=5)],
                    selection='own-regime validation MAE, tie lower candidate_index',
                    output_root=str(common.HERE/'real-runs-v1'/name),
                    real_fit_authorized=False,resource_contract='root must issue fresh bounded CPU-only fit contract',
                    baseline_metadata=dict(additional_classical_baseline=True,author_reproduction=False,paper_count=0,
                        NN200_and400_unchanged=True,global_clock_not_reset=True))
                file=output/(name+'.json');common.write(file,spec)
                units.append(dict(unit_id=name,spec_path=str(file),spec_sha256=common.sha(file),
                    panel=panel,regime=regime,seed=seed,selection_path=str(common.path(spec['output_root'])/'selection.json')))
    common.write(output/'task-spec-index.json',dict(status='prepared_unsigned_no_real_fit',units=units,unit_count=40,candidate_fit_count=80,
        expected_RF_score_count=120,expected_prediction_rows=53160,original_NN_selection_count=200,
        source_feature_manifest_sha256=common.sha(x),source_asset_manifest_sha256=common.sha(assets),
        actual_real_RF_fits=0,global_clock_not_reset=True))
    print('Prepared40RF units/80candidates; no model fitted.')
if __name__=='__main__':main()
