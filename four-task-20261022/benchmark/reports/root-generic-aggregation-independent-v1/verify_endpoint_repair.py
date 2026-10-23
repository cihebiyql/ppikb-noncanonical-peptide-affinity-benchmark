"""Supplement only: declarations/provenance filled; all original values and source bytes unchanged."""
import datetime as dt
import difflib
from pathlib import Path
import shutil
from prepare_snapshot_and_mapping import HERE,ROOT,sha,load,read,write

def main():
    original=HERE/'original-snapshot';repaired=HERE/'repaired-snapshot';repaired.mkdir(exist_ok=False)
    mapping_path=HERE/'view-endpoint-map.json';mapping=load(mapping_path);mapping_sha=sha(mapping_path)
    original_audit=load(HERE/'original-snapshot-independent-audit.json');assert original_audit['numeric_and_training_partition_passed']
    files=[ROOT/'reports/build_delivery_snapshot.py',ROOT/'reports/delivery-20261023/generic-completed-metrics-all-panels.csv',ROOT/'reports/delivery-20261023/STATUS.json']
    snapshots=[]
    for source in files:
        target=repaired/source.name;shutil.copyfile(source,target);assert sha(source)==sha(target)
        snapshots.append({'source':str(source),'snapshot':str(target),'sha256':sha(target),'bytes':target.stat().st_size})
    old=read(original/'generic-completed-metrics-all-panels.csv');new=read(repaired/'generic-completed-metrics-all-panels.csv')
    assert len(old)==len(new)==1350
    assert set(new[0])-set(old[0])=={'endpoint_declaration_ref','endpoint_declaration_sha256'}
    changed_endpoints=0;checks=0;proofs={};errors=[]
    for before,after in zip(old,new):
        for field,value in before.items():
            if field=='endpoint':continue
            checks+=1
            if after[field]!=value:errors.append({'unexpected_field_change':field,'before':before,'after':after})
        declared=mapping['by_view_id'][after['view_id']]
        assert after['run_id'] in declared['run_ids'] and after['task']==declared['task']
        assert after['endpoint']==declared['endpoint'] and after['endpoint']
        if before['endpoint']:assert before['endpoint']==after['endpoint']
        else:changed_endpoints+=1
        assert after['endpoint_declaration_ref']==str(mapping_path)
        assert after['endpoint_declaration_sha256']==mapping_sha
        for proof in declared['evidence']:
            proofs[proof['path']]=proof['sha256']
        for key in ['derived_coverage_evidence','parent_view_manifest_evidence']:
            if key in declared:proofs[declared[key]['path']]=declared[key]['sha256']
    assert changed_endpoints==1190
    for path,digest in proofs.items():assert sha(path)==digest
    for item in original_audit['input_hashes']:assert sha(item['path'])==item['sha256']
    status=load(repaired/'STATUS.json')
    assert status['generic_formal_training_totals']['selected_results']==1050
    assert status['generic_formal_training_totals']['candidate_fits']==2100
    assert status['completed_generic_metric_table']['metric_rows']==1350
    assert status['completed_generic_metric_table']['model_view_groups']==105
    assert status['completed_generic_metric_table']['missing_endpoints']==0
    assert status['completed_generic_metric_table']['endpoint_cells_filled_from_original_contracts']==1190
    assert status['completed_generic_metric_table']['endpoint_declaration_sha256']==mapping_sha
    code_before=(original/'build_delivery_snapshot.py').read_text(encoding='utf-8')
    code_after=(repaired/'build_delivery_snapshot.py').read_text(encoding='utf-8')
    diff=''.join(difflib.unified_diff(code_before.splitlines(True),code_after.splitlines(True),fromfile='original/build_delivery_snapshot.py',tofile='repaired/build_delivery_snapshot.py'))
    (HERE/'root-builder-endpoint-repair.diff').write_text(diff,encoding='utf-8')
    report={'schema':'root.generic-aggregation.endpoint-repair-supplement.v1','completed_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'passed':not errors,'errors':errors,'aggregate_rows':1350,'selected_training_conditions':1050,'candidate_fits_receipted':2100,
        'model_view_groups':105,'original_endpoint_blank_rows':1190,'endpoint_cells_filled':changed_endpoints,'repaired_blank_endpoints':0,
        'old_nonempty_endpoints_preserved':160,'all_other_original_cell_checks':checks,'all_other_original_cells_unchanged':not errors,
        'new_provenance_columns_only':['endpoint_declaration_ref','endpoint_declaration_sha256'],
        'unique_contract_coverage_or_parent_proofs_SHA_checked':len(proofs),
        'endpoint_map_sha256':mapping_sha,'root_builder_original_sha256':sha(original/'build_delivery_snapshot.py'),
        'root_builder_repaired_sha256':sha(repaired/'build_delivery_snapshot.py'),
        'aggregate_original_sha256':sha(original/'generic-completed-metrics-all-panels.csv'),
        'aggregate_repaired_sha256':sha(repaired/'generic-completed-metrics-all-panels.csv'),
        'all_original_source_metric_and_receipt_inputs_unchanged':True,
        'original_numeric_audit_unchanged_sha256':sha(HERE/'original-snapshot-independent-audit.json'),
        'repaired_snapshots':snapshots,'new_fit_count':0,'new_forward_count':0,'gpu_jobs':0,'code_sha256':sha(__file__)}
    write(HERE/'endpoint-repair-supplement.json',report);print({k:v for k,v in report.items() if k!='repaired_snapshots'});assert report['passed']
if __name__=='__main__':main()
