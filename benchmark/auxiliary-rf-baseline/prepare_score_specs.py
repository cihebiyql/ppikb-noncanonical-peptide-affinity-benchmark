"""Six metadata-only RF scoring contracts. Never open or hash gold/model files."""
import common

def main():
    output=common.HERE/'score-specs-v1';output.mkdir(exist_ok=False)
    source=common.PROJECT/'administration/score-spec-assets-v2'
    entries=[]
    for panel in common.PANELS:
        for dataset in (('source_test' if panel==common.PANELS[0] else 'target_test'),'external75','supplement13'):
            source_file=source/(dataset+'__'+panel+'__GraphDTA-GIN.json')
            metadata=common.read(source_file)
            # Gold identity is inherited only as existing metadata strings.
            # There is intentionally no require/hash/open of metadata['gold_rows'].
            spec=dict(method_id=common.METHOD,panel=panel,dataset_id=dataset,
                holdout_kind=metadata['holdout_kind'],input_rows=metadata['input_rows'],
                input_rows_sha256=metadata['input_rows_sha256'],gold_rows=metadata['gold_rows'],gold_rows_sha256=metadata['gold_rows_sha256'],
                feature_dataset_id='PPIKB9619' if dataset in ('source_test','target_test') else dataset,
                feature_manifest=str(common.HERE/'X-final-manifest-v1.json'),
                feature_manifest_sha256=common.sha(common.HERE/'X-final-manifest-v1.json'),
                installed_assets=str(common.HERE/'installed-assets-v1.json'),
                output_root=str(common.HERE/'rf-scores-v1'),cpu_threads=1,n_jobs=1,CUDA_VISIBLE_DEVICES='',
                NN_metadata_source=str(source_file),NN_metadata_source_sha256=common.sha(source_file),
                prepared_metadata_only_not_score_authorization=True,joint_gate_required='NN200 AND RF40, root authorized')
            file=output/(dataset+'__'+panel+'__RFclassical.json');common.write(file,spec)
            entries.append(dict(dataset_id=dataset,panel=panel,feature_dataset_id=spec['feature_dataset_id'],
                score_spec_path=str(file),score_spec_sha256=common.sha(file),input_rows_sha256=spec['input_rows_sha256'],
                gold_metadata_sha256=spec['gold_rows_sha256'],source_metadata_sha256=common.sha(source_file)))
    common.write(output/'score-spec-index.json',dict(status='six_RF_score_metadata_specs_prepared_unissued',entries=entries,
        spec_count=6,future_RF_selections=40,future_RF_score_runs=120,expected_prediction_rows=53160,
        real_gold_reads=0,real_prediction_reads=0,real_model_reads=0,real_RF_scores=0,
        NN600_and265800_unchanged=True,external_subsets_recomputed_by_independent_review=True))
    print('SixRF score metadata specs ready; gold/model files never opened or hashed.')
if __name__=='__main__':main()
