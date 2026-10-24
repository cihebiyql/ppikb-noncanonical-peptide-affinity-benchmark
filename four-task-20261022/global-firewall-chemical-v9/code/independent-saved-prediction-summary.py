"""Independent standard-library reanalysis of fixed predictions; never loads models."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
from datetime import datetime, timezone


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def rows(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def ranks(values):
    ordered=sorted(range(len(values)),key=values.__getitem__)
    result=[0.]*len(values)
    cursor=0
    while cursor<len(ordered):
        end=cursor+1
        while end<len(ordered) and values[ordered[end]]==values[ordered[cursor]]:
            end+=1
        rank=(cursor+end-1)/2+1
        for index in ordered[cursor:end]:result[index]=rank
        cursor=end
    return result


def corr(a,b):
    if len(a)<2 or max(a)==min(a) or max(b)==min(b):return None
    ma,mb=statistics.mean(a),statistics.mean(b)
    aa,bb=[x-ma for x in a],[x-mb for x in b]
    return math.fsum(x*y for x,y in zip(aa,bb))/math.sqrt(math.fsum(x*x for x in aa)*math.fsum(x*x for x in bb))


def metric(y,p):
    if not y:return {'n':0}
    n=len(y);mean=statistics.mean(y)
    err=[b-a for a,b in zip(y,p)]
    ss=math.fsum(x*x for x in err);den=math.fsum((x-mean)**2 for x in y)
    return {'n':n,'mae':math.fsum(abs(x) for x in err)/n,'rmse':math.sqrt(ss/n),
            'bias':math.fsum(err)/n,'r2':1-ss/den if den>0 else None,
            'pearson':corr(y,p),'spearman':corr(ranks(y),ranks(p))}


def selected(stratum,row):
    chemistry=row['evaluation_stratum']
    flag=row.get('residue_class_graph_discordance','').lower()
    if flag not in ('','false','true','0','1'):raise ValueError('Unexpected frozen discordance value')
    discord=flag in ('true','1')
    if stratum=='all':return True
    if stratum=='exclude_discordance':return not discord
    if stratum=='flagged_discordance':return discord
    if stratum=='NC_all':return chemistry!='standard20_control'
    if stratum=='PTM_bearing':return chemistry in ('PTM','synthetic_and_PTM')
    return chemistry==stratum


def write_csv(path,values):
    if not values:return
    keys=list(values[0])
    with Path(path).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(values)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cohort',type=Path,required=True)
    parser.add_argument('--input',action='append',required=True,help='representation=artifact-directory')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    truth={r['row_id']:r for r in rows(args.cohort)}
    expected_ids={key for key,row in truth.items() if row['split']=='test'}
    strata=['all','standard20_control','synthetic_D_backbone','PTM','synthetic_and_PTM','other_NC',
            'NC_all','PTM_bearing','exclude_discordance','flagged_discordance']
    raw=[];provenance=[];checks=0;units=set()
    for item in args.input:
        representation,value=item.split('=',1)
        base=Path(value)
        contracts=list(base.glob('*/frozen-head-contract.json'))
        assert len(contracts)==1
        contract=json.loads(contracts[0].read_text())
        assert contract['input_sha256']==sha(args.cohort)
        expected={(representation,model,seed) for model in contract['models'] for seed in range(10)}
        found=set();candidates=0
        for path in sorted(base.glob('*/*/seed-*/result.json')):
            result=json.loads(path.read_text())
            unit=(representation,result['model'],result['seed'])
            assert unit not in units
            units.add(unit);found.add(unit)
            assert result['status']=='succeeded' and len(result['candidates'])==2
            candidates+=len(result['candidates'])
            predpath=Path(result['splits']['test']['prediction_path'])
            assert sha(predpath)==result['splits']['test']['prediction_sha256']
            pred=rows(predpath)
            assert len(pred)==len({r['row_id'] for r in pred})
            assert {r['row_id'] for r in pred}==expected_ids
            for row in pred:
                assert float(row['label'])==float(truth[row['row_id']]['label'])
                assert row['evaluation_stratum']==truth[row['row_id']]['evaluation_stratum']
                assert row['group_id']==truth[row['row_id']]['global_group_id']
                checks+=3
            for stratum in strata:
                subset=[r for r in pred if selected(stratum,truth[r['row_id']])]
                mm=metric([float(r['label']) for r in subset],[float(r['prediction']) for r in subset])
                raw.append({'representation':representation,'model':result['model'],'seed':result['seed'],'stratum':stratum,**mm})
            provenance.append({'representation':representation,'result_path':str(path),'result_sha256':sha(path),
                               'test_prediction_path':str(predpath),'test_prediction_sha256':sha(predpath)})
        assert found==expected,('Incomplete or unexpected frozen 5-family x 10seed set',sorted(expected-found),sorted(found-expected))
        assert candidates==100
    summary=[]
    for representation in sorted({x['representation'] for x in raw}):
        for model in sorted({x['model'] for x in raw if x['representation']==representation}):
            for stratum in strata:
                selected_rows=[x for x in raw if (x['representation'],x['model'],x['stratum'])==(representation,model,stratum)]
                assert len(selected_rows)==10
                entry={'representation':representation,'model':model,'stratum':stratum,'n':selected_rows[0]['n'],'seeds':10}
                assert len({x['n'] for x in selected_rows})==1
                for key in ['mae','rmse','bias','r2','pearson','spearman']:
                    values=[x[key] for x in selected_rows if x.get(key) is not None]
                    entry[key+'_mean']=statistics.mean(values) if values else None
                    entry[key+'_sample_sd']=statistics.stdev(values) if len(values)>1 else None
                    entry[key+'_valid_seeds']=len(values)
                summary.append(entry)
    write_csv(args.output/'per-seed-recalculated.csv',raw)
    write_csv(args.output/'ten-seed-recalculated.csv',summary)
    (args.output/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    receipt={'schema':'chemical-head.independent-saved-prediction-summary.v1','completed_at':datetime.now(timezone.utc).isoformat(),
             'source_code_sha256':sha(__file__),'cohort_path':str(args.cohort),'cohort_sha256':sha(args.cohort),
             'test_rows':len(expected_ids),'model_seed_units':len(units),'record_metadata_checks':checks,
             'new_fits':0,'new_encoder_inferences':0,'loaded_estimators':0,'new_predictions':0,
             'sensitivity_role':'Discordance exclusions score existing fixed predictions only; train still contains flagged observations.',
             'summary_sha256':sha(args.output/'ten-seed-recalculated.csv'),'per_seed_sha256':sha(args.output/'per-seed-recalculated.csv')}
    (args.output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'receipt':receipt,'overall':[x for x in summary if x['stratum']=='all']},ensure_ascii=False))


if __name__=='__main__':main()
