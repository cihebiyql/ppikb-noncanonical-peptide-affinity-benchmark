"""Independent source-table and per-seed verification of the original generic aggregation."""
from collections import Counter,defaultdict
import datetime as dt
import math
from pathlib import Path
import statistics
from prepare_snapshot_and_mapping import HERE,ROOT,sha,load,read,write

def number(x):
    if x is None or str(x).strip()=='':return None
    value=float(x);assert math.isfinite(value);return value

def main():
    snapshot=HERE/'original-snapshot';target=read(snapshot/'generic-completed-metrics-all-panels.csv')
    mapping=load(HERE/'view-endpoint-map.json');endpointmap=mapping['by_view_id']
    cpu_path=ROOT/'baselines/recovery-20261023/CPU-RECOVERY-AUDIT.json';cpu=load(cpu_path)
    sources=[]
    for entry in cpu['per_run']:
        if entry['category']=='training':
            sources.append({'run_id':entry['run_id'],'category':'training',
                'path':ROOT/'runs'/entry['run_id']/'mean-sd-metrics.csv',
                'seed_path':ROOT/'runs'/entry['run_id']/'per-seed-metrics.csv',
                'selected':entry['selected_results'],'candidates':entry['candidate_fits']})
    assert len(sources)==6
    additional=[
        ('her2-strict-local-baselines-v1','HER2 strict local manual features','runs/her2-strict-local-baselines-v1/ten-seed-mean-sd.csv','runs/her2-strict-local-baselines-v1/all-seeds-metrics.csv',100,200),
        ('plm-simple-v1','Frozen ESM2-t6-8M','runs/plm-simple-v1/heads/mean-sd-metrics.csv','runs/plm-simple-v1/heads/per-seed-metrics.csv',150,300),
        ('plm-cohort-manual-controls-v1','Manual features on identical ESM cohorts','runs/plm-cohort-manual-controls-v1/mean-sd-metrics.csv','runs/plm-cohort-manual-controls-v1/per-seed-metrics.csv',150,300),
        ('plm-classification-contact-v1','Frozen ESM2-t6-8M classification and residue contact','runs/plm-classification-contact-v1/heads/mean-sd-metrics.csv','runs/plm-classification-contact-v1/heads/per-seed-metrics.csv',100,200)]
    for run,category,path,seedpath,selected,candidates in additional:
        sources.append({'run_id':run,'category':category,'path':ROOT/path,'seed_path':ROOT/seedpath,'selected':selected,'candidates':candidates})
    receipt_specs=[(cpu_path,'selected_training_results','candidate_fits',550,1100),
        (ROOT/'reports/her2-strict-local/STATUS.json','new_selected_training_results','new_candidate_fits',100,200),
        (ROOT/'baselines/plm-simple-v1/DELIVERY-RECEIPT.json','selected_scientific_runs','scientific_candidate_fits',150,300),
        (ROOT/'baselines/plm-simple-v1/controls/DELIVERY-RECEIPT.json','additional_selected_scientific_runs','additional_candidate_fits',150,300),
        (ROOT/'baselines/plm-classification-contact-v1/FINAL-LOCAL-RECEIPT.json','selected_conditions','candidate_fits',100,200)]
    receipts=[]
    for path,skey,ckey,expected_s,expected_c in receipt_specs:
        receipt=load(path);assert receipt[skey]==expected_s and receipt[ckey]==expected_c
        receipts.append({'path':str(path),'sha256':sha(path),'selected':receipt[skey],'candidate_fits':receipt[ckey]})
    assert sum(r['selected'] for r in receipts)==1050 and sum(r['candidate_fits'] for r in receipts)==2100
    expected={};source_meta=[];seed_values={};source_groups={};input_files={}
    for item in sources:
        path=item['path'];rows=read(path);seedrows=read(item['seed_path'])
        input_files[str(path)]=sha(path);input_files[str(item['seed_path'])]=sha(item['seed_path'])
        groups=defaultdict(set)
        for row in seedrows:
            groups[(row['view_id'],row['model'])].add(int(row['seed']))
            if 'metric' in row:
                key=(item['run_id'],row['view_id'],row['model'],row['split'],row['metric'])
                seed_values.setdefault(key,[]).append({'seed':int(row['seed']),'value':number(row['value']),'n':int(row['n'])})
            else:
                identity={'view_id','endpoint','model','seed','split','n'}
                for metric,value in row.items():
                    if metric in identity:continue
                    key=(item['run_id'],row['view_id'],row['model'],row['split'],metric)
                    seed_values.setdefault(key,[]).append({'seed':int(row['seed']),'value':number(value),'n':int(row['n'])})
        assert all(values==set(range(10)) for values in groups.values())
        assert len(groups)*10==item['selected']
        source_groups[item['run_id']]=len(groups)
        for raw in rows:
            row=dict(raw);key=(item['run_id'],row['view_id'],row['model'],row['split'],row['metric'])
            assert key not in expected
            row.update(run_id=item['run_id'],category=item['category'],evidence=str(path))
            if not row.get('task'):row['task']=endpointmap[row['view_id']]['task']
            expected[key]=row
        source_meta.append({'run_id':item['run_id'],'path':str(path),'sha256':sha(path),'seed_source':str(item['seed_path']),
            'seed_source_sha256':sha(item['seed_path']),'aggregate_rows':len(rows),'model_view_groups':len(groups),
            'selected_receipted':item['selected'],'candidate_fits_receipted':item['candidates']})
    actual={};errors=[];checks=Counter();missing_endpoints=[]
    for row in target:
        key=tuple(row[k] for k in ['run_id','view_id','model','split','metric'])
        assert key not in actual;actual[key]=row
    assert set(actual)==set(expected)
    assert len(actual)==1350 and len({key[:3] for key in actual})==105
    for key,row in actual.items():
        raw=expected[key]
        assert row['split'] in {'test','validation'}
        for field in ['run_id','category','view_id','task','model','split','metric','evidence']:
            checks['source_identity_fields']+=1
            if row[field]!=raw.get(field,''):errors.append({'identity':key,'field':field,'actual':row[field],'expected':raw.get(field,'')})
        for field in ['mean','sd','valid_seed_count','seed_count','n']:
            checks['source_numeric_fields']+=1
            if number(row[field])!=number(raw.get(field,'')):errors.append({'identity':key,'field':field,'actual':row[field],'expected':raw.get(field,'')})
        declared=endpointmap[row['view_id']]
        assert row['task']==declared['task']
        if not row['endpoint']:missing_endpoints.append({'identity':key,'declared_endpoint':declared['endpoint']})
        elif row['endpoint']!=declared['endpoint']:errors.append({'endpoint_conflict':key,'actual':row['endpoint'],'expected':declared['endpoint']})
        values=seed_values[key];assert len(values)==10 and {v['seed'] for v in values}==set(range(10))
        finite=[v['value'] for v in values if v['value'] is not None]
        recomputed={'mean':statistics.mean(finite) if finite else None,'sd':statistics.stdev(finite) if len(finite)>1 else None,
            'valid_seed_count':len(finite),'seed_count':10,'n':values[0]['n']}
        assert {v['n'] for v in values}=={int(row['n'])}
        for field,value in recomputed.items():
            checks['independent_per_seed_aggregation_fields']+=1
            old=number(row[field])
            if (old is None)!=(value is None) or (old is not None and abs(old-value)>1e-10):errors.append({'reaggregate':key,'field':field,'actual':old,'expected':value})
    training_runs=set(source_groups)
    excluded=[]
    for entry in cpu['per_run']:
        if entry['category']=='training':continue
        assert entry['run_id'] not in training_runs and entry['candidate_fits']==0
        excluded.append({'run_id':entry['run_id'],'category':entry['category'],'applications':entry['selected_results'],'candidate_fits':0,
            'absent_from_generic':not any(r['run_id']==entry['run_id'] for r in target)})
    assert sum(x['applications'] for x in excluded if x['category']=='fixed_external')==250
    assert sum(x['applications'] for x in excluded if x['category']=='fixed_common_subset')==100
    hu_path=ROOT/'reports/profaff-HU-external/STATUS.json';hu=load(hu_path)
    pepbi_path=ROOT/'reports/pepbi-conditional-external-v1/DELIVERY-RECEIPT.json';pepbi=load(pepbi_path)
    assert hu['fixed_model_applications']==100 and hu['new_fit']==0 and hu['new_tuning']==0
    assert pepbi['fixed_model_applications']==100 and pepbi['new_fit_count']==0 and pepbi['tuning_count']==0
    for item in [hu,pepbi]:assert not item.get('generic_training_count_increment',0)
    assert not any(any(word in r['run_id'].lower() for word in ['dta','swing','pepinter_native','rde','profaff-hu','pepbi']) for r in target)
    original_status=load(snapshot/'STATUS.json')
    totals=original_status['generic_formal_training_totals']
    assert totals['selected_results']==1050 and totals['candidate_fits']==2100
    assert original_status['completed_generic_metric_table']['metric_rows']==1350
    assert original_status['completed_generic_metric_table']['model_view_groups']==105
    input_files.update({str(p):sha(p) for p in [cpu_path,hu_path,pepbi_path,HERE/'view-endpoint-map.json',snapshot/'generic-completed-metrics-all-panels.csv',snapshot/'build_delivery_snapshot.py',snapshot/'STATUS.json']})
    input_files.update({r['path']:r['sha256'] for r in receipts})
    for path,expected_sha in input_files.items():assert sha(path)==expected_sha
    report={'schema':'root.generic-aggregation.independent-original-snapshot.v1','completed_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'numeric_and_training_partition_passed':not errors,'fully_qualified_for_endpoint_display':not missing_endpoints and not errors,
        'selected_training_conditions':1050,'candidate_fits_receipted':2100,'model_view_groups':105,'seeds_per_group':10,
        'aggregate_metric_rows':1350,'distinct_view_ids':len({r['view_id'] for r in target}),
        'checks':dict(checks),'errors':errors,'source_tables':source_meta,'receipt_counts':receipts,
        'endpoint_blank_rows':len(missing_endpoints),'endpoint_conflicts':sum('endpoint_conflict' in e for e in errors),
        'missing_endpoint_declarations':missing_endpoints,'old_nontraining_partition':excluded,
        'HU_fixed_external':{'applications':100,'new_fits':0,'absent_from_generic':True,'rows':hu['raw_contexts'],'source':str(hu_path),'sha256':sha(hu_path)},
        'PEPBI_conditional_fixed_external':{'applications':100,'new_fits':0,'absent_from_generic':True,'rows':27,'certified_independent_external_rows':0,'source':str(pepbi_path),'sha256':sha(pepbi_path)},
        'native_DTA_SWING_PepInter_RDE_absent_from_generic':True,
        'audit_scope':'Existing meanSD/per-seed metric tables and accepted receipts only; no weights/cache scan or model execution.',
        'input_hashes':[{'path':p,'sha256':s} for p,s in input_files.items()],
        'new_fit_count':0,'new_forward_count':0,'gpu_jobs':0,'code_sha256':sha(__file__)}
    write(HERE/'original-snapshot-independent-audit.json',report)
    print({k:v for k,v in report.items() if k not in {'input_hashes','source_tables','receipt_counts','missing_endpoint_declarations','old_nontraining_partition'}})
    assert not errors
if __name__=='__main__':main()
