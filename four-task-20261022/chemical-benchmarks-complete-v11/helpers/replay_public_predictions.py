"""Portable numerical replay of both complete230-model public cohorts.

Uses only original-byte PPIKB prediction CSVs and their licensed frozen table.
No training, inference, pickle, NumPy or checkpoint loading. Resource provenance
is separately evidenced; sanitized resource logs are not original bytes.
"""
import argparse
import collections
import csv
import io
import json
import math
import os
from pathlib import Path
import statistics
import tarfile

from evaluate_saved_predictions import metrics
from public_artifacts import safe_relative,sha

METRICS=('mae','rmse','bias','r2','pearson','spearman')
FAMILIES=('constant','ridge','random_forest','extra_trees','hist_gradient_boosting')
REPS=('hybrid','mlm','morgan','peptideclm2025')
COHORTS={
 'c3d8f4e42600f0c762bb9d2d24595a32c8f13de7a1f5018d59047d241dd8525a':(685,155),
 '4f4694b8937c6e3bd2e5b1091faf948fd66ecc57180b09d0ff5c236cded83c60':(656,146),
}


def readcsv(data):return list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'),newline='')))


def readbytes(path):
    raw=os.path.abspath(path)
    if os.name=='nt' and not raw.startswith('\\\\?\\'):raw='\\\\?\\'+raw
    return Path(raw).read_bytes()


def strata(rows,annotations):
    flag=lambda row:annotations[row['row_id']]['residue_class_graph_discordance'].strip().lower() in ('true','1','yes')
    result={'all':rows}
    for name in ('standard20_control','synthetic_D_backbone','PTM','synthetic_and_PTM','other_NC'):
        result[name]=[row for row in rows if row['evaluation_stratum']==name]
    # Historical NC_all is all chemically nonstandard records, including PTM;
    # pure synthetic/D-backbone residues remain a separate named stratum.
    result['NC_all']=[row for row in rows if row['evaluation_stratum']!='standard20_control']
    result['PTM_bearing']=[row for row in rows if row['evaluation_stratum'] in ('PTM','synthetic_and_PTM')]
    result['flagged']=[row for row in rows if flag(row)]
    result['unflagged']=[row for row in rows if not flag(row)]
    return result


def macro(rows):
    groups=collections.defaultdict(list)
    for row in rows:groups[row['global_group_id']].append(row)
    values=[metrics(group) for group in groups.values()]
    result={'all_groups':len(groups)}
    for name in METRICS:
        valid=[group[name] for group in values if group[name] is not None]
        result[name]=statistics.fmean(valid) if valid else None
        result[name+'_valid_groups']=len(valid)
    return result


def summary(rows,keys):
    groups=collections.defaultdict(list)
    for row in rows:groups[tuple(row[name] for name in keys)].append(row)
    output=[]
    for key,group in sorted(groups.items()):
        if len(group)!=10 or {row['seed'] for row in group}!=set(range(10)):raise ValueError('Every configuration requires exact seeds0..9')
        result=dict(zip(keys,key));result.update(seeds=10,n=group[0].get('n'))
        for name in METRICS:
            values=[row[name] for row in group if row[name] is not None]
            result[name+'_mean']=statistics.fmean(values) if values else None
            result[name+'_sampleSD']=statistics.stdev(values) if len(values)>1 else None
            result[name+'_valid_seeds']=len(values)
        output.append(result)
    return output


def replay(cohort,heads,fullfine,output,expected_table=None,expected_macro=None):
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    raw=readbytes(cohort);cohort_sha=sha(raw)
    if cohort_sha not in COHORTS:raise ValueError('Unknown frozen scientific cohort')
    n,ngroups=COHORTS[cohort_sha];reference=[row for row in readcsv(raw) if row['split']=='test']
    if len(reference)!=n:raise ValueError('Frozen TEST count differs')
    annotations={row['row_id']:row for row in reference};ids=list(annotations)
    if len(ids)!=n or len({r['global_group_id'] for r in reference})!=ngroups:raise ValueError('Frozen ID/group counts differ')
    records=[];macros=[];seen=set();source_pins=[];saved_macro_comparisons=0
    for path,kind in ((heads,'frozen_head'),(fullfine,'full_encoder')):
        source_pins.append({'archive':Path(path).name,'sha256':sha(readbytes(path))})
        with tarfile.open(path,'r:gz') as archive:
            members=archive.getmembers();names=[member.name for member in members]
            if len(names)!=len(set(names)) or any(not member.isfile() for member in members):raise ValueError('Duplicate/nonregular archive members')
            for name in names:safe_relative(name)
            candidates=[name for name in names if name.endswith('/SELECTED-PREDICTION-INDEX.json') or name.endswith('/SELECTED-30-PREDICTION-INDEX.json')]
            if len(candidates)!=1:raise ValueError('Exactly one selected prediction index required')
            index=json.loads(archive.extractfile(candidates[0]).read())['entries']
            if len(index)!=(200 if kind=='frozen_head' else 30):raise ValueError('Incomplete selected archive')
            full_results={}
            if kind=='full_encoder':
                for name in names:
                    if not name.endswith('result.json'):continue
                    value=json.loads(archive.extractfile(name).read())
                    if not isinstance(value,dict) or 'selected_candidate' not in value or 'test' not in value.get('splits',{}):continue
                    contract=value['contract'];identity=contract['model_identity']
                    rep='peptideclm2025' if identity.get('model')=='aaronfeller/PeptideCLM-23M-all' else 'hybrid' if identity.get('repository','').endswith('hybrid-small') else 'mlm' if identity.get('repository','').endswith('mlm-small') else None
                    key=(rep,int(contract['seed']))
                    if rep is None or key in full_results:raise ValueError('Unknown/duplicate selected result metadata')
                    full_results[key]=value
                if len(full_results)!=30:raise ValueError('All30 selected result metadata required')
            for entry in index:
                rep=entry['representation'];method=rep+'__'+entry['model'] if kind=='frozen_head' else 'fullfine_'+rep
                key=(method,int(entry['seed']))
                if key in seen or entry['split']!='test' or entry['n']!=n:raise ValueError('Duplicate/wrong selected slot')
                seen.add(key);data=archive.extractfile(entry['public_archive_path']).read()
                if sha(data)!=entry['source_sha256']:raise ValueError('Original scientific prediction bytes changed')
                rows=readcsv(data)
                if [row['row_id'] for row in rows]!=ids:raise ValueError('Prediction IDs/order differ')
                for row,ref in zip(rows,reference):
                    if float(row['label'])!=float(ref['label']) or row['global_group_id']!=ref['global_group_id'] or row['evaluation_stratum']!=ref['evaluation_stratum'] or row['endpoint']!='pKd':raise ValueError('Prediction label/group/stratum/endpoint differs')
                base={'kind':kind,'method':method,'seed':int(entry['seed'])}
                records.extend(dict(base,stratum=name,**metrics(part)) for name,part in strata(rows,annotations).items())
                gm=macro(rows)
                if gm['all_groups']!=ngroups:raise ValueError('Dependency group count differs')
                producer=json.loads(archive.extractfile(entry['public_archive_path'].removesuffix('test-predictions.csv')+'result.json').read()) if kind=='frozen_head' else full_results[(rep,int(entry['seed']))]
                part=producer['splits']['test']
                if part['prediction_sha256']!=entry['source_sha256']:raise ValueError('Original producer prediction SHA differs')
                for metric in METRICS:
                    old=part['group_macro_metrics'][metric];value=old['mean'];fresh=gm[metric]
                    if not(value is None and fresh is None or value is not None and fresh is not None and math.isclose(value,fresh,rel_tol=1e-10,abs_tol=1e-10)) or old['valid_groups']!=gm[metric+'_valid_groups'] or old['all_groups']!=ngroups:raise ValueError('Producer group macro differs: '+str((method,entry['seed'],metric)))
                    saved_macro_comparisons+=1
                macros.append(dict(base,**gm))
    methods={rep+'__'+family for rep in REPS for family in FAMILIES}|{'fullfine_'+rep for rep in REPS if rep!='morgan'}
    if seen!={(method,seed) for method in methods for seed in range(10)} or len(records)!=2300:raise ValueError('Exact230 selected/2300 strata required')
    comparisons=0
    if expected_table:
        expected=readcsv(readbytes(expected_table));lookup={(row['method'],int(row['seed']),row['stratum']):row for row in expected}
        if len(lookup)!=2300 or len(expected)!=2300:raise ValueError('Expected metric table not exact2300')
        for row in records:
            prior=lookup[(row['method'],row['seed'],row['stratum'])]
            if int(prior['n'])!=row['n']:raise ValueError('Expected chemical denominator differs: '+str((row['method'],row['seed'],row['stratum'],prior['n'],row['n'])))
            for name in METRICS:
                old=None if prior[name] in ('',None) else float(prior[name]);new=row[name]
                if not (old is None and new is None or old is not None and new is not None and math.isclose(old,new,rel_tol=1e-10,abs_tol=1e-10)):raise ValueError('Original audited metric differs: '+str((row['method'],row['seed'],row['stratum'],name)))
                comparisons+=1
    macro_comparisons=0
    if expected_macro:
        prior=readcsv(readbytes(expected_macro));lookup={(r['method'],int(r['seed'])):r for r in prior}
        if len(lookup)!=230 or len(prior)!=230:raise ValueError('Expected group macro table not exact230')
        for row in macros:
            old=lookup[(row['method'],row['seed'])]
            if int(old['all_groups'])!=ngroups:raise ValueError('Expected dependency group count differs')
            for name in METRICS:
                value=None if old[name] in ('',None) else float(old[name]);fresh=row[name]
                if not(value is None and fresh is None or value is not None and fresh is not None and math.isclose(value,fresh,rel_tol=1e-10,abs_tol=1e-10)) or int(old[name+'_valid_groups'])!=row[name+'_valid_groups']:raise ValueError('Expected group macro/validity differs: '+str((row['method'],row['seed'],name)))
                macro_comparisons+=1
    bykey={(r['method'],r['seed'],r['stratum']):r for r in records};paired=[]
    for full in sorted(method for method in methods if method.startswith('fullfine_')):
        for family in FAMILIES:
            for name in strata(reference,annotations):
                for seed in range(10):
                    left=bykey[(full,seed,name)];right=bykey[('morgan__'+family,seed,name)]
                    paired.append({'full_method':full,'Morgan_family':family,'seed':seed,'stratum':name,'n':left['n'],**{metric:left[metric]-right[metric] if left[metric] is not None and right[metric] is not None else None for metric in METRICS}})
    output.mkdir(parents=True)
    tables={'per-seed-2300.csv':records,'ten-seed-summary.csv':summary(records,('kind','method','stratum')),'group-macro-230.csv':macros,'Morgan-paired-1500.csv':paired,'Morgan-paired-summary.csv':summary(paired,('full_method','Morgan_family','stratum'))}
    for name,rows in tables.items():
        with (output/name).open('x',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    result={'schema':'public.saved-predictions230.numerical-replay.v1','status':'passed','cohort_csv_sha256':cohort_sha,'selected_models':230,'TEST_rows_per_model':n,'total_selected_TEST_rows':230*n,'dependency_groups':ngroups,'all_exact_seeds':list(range(10)),'all_five_Morgan_heads':list(FAMILIES),'metric_comparisons_to_original_audit':comparisons,'group_macro_and_validity_comparisons_to_original_audit':macro_comparisons,'group_macro_and_validity_comparisons_to_producer':saved_macro_comparisons,'source_archives':source_pins,'outputs':{name:sha((output/name).read_bytes()) for name in tables},'new_fits':0,'new_predictions':0,'weights_loaded':0,'private_execution_provenance_reaudited':False}
    with (output/'REPLAY.actual.json').open('x',encoding='utf-8',newline='\n') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('cohort','heads','fullfine','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--expected-table',type=Path);parser.add_argument('--expected-macro',type=Path);args=parser.parse_args();print(json.dumps(replay(args.cohort,args.heads,args.fullfine,args.output,args.expected_table,args.expected_macro),indent=2))
