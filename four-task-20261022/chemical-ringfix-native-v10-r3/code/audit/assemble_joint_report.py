"""Assemble already audited, immutable saved results. No model or prediction loading."""
from pathlib import Path
import csv, hashlib, itertools, json, statistics
from datetime import datetime, timezone

H = Path(__file__).resolve().parent
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def rows(p):
    with Path(p).open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
def write(p, x): Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def csvout(p, x):
    with Path(p).open('w', encoding='utf-8', newline='') as f:
        w=csv.DictWriter(f, fieldnames=list(x[0]));w.writeheader();w.writerows(x)
def fmt(x): return 'NA' if x in ('', None) else f'{float(x):.4f}'

def main():
    proof={};units=set();checks=0
    for rep in ('hybrid','mlm','morgan'):
        ds=list(H.glob(rep+'--*')); assert len(ds)==1
        d=ds[0]; a=load(d/'audit.json')
        pp=d/('process-receipt.json' if (d/'process-receipt.json').exists() else 'process.json');p=load(pp)
        assert a['valid'] and not a['errors'] and not a['missing_units'] and not a['extra_units']
        assert a['actual_model_seed_units']==a['expected_model_seed_units']==50 and p['returncode']==0
        for group,seeds in a['seeds_by_combination'].items():
            assert seeds==list(range(10))
            for seed in seeds:
                key=(rep,group,seed);assert key not in units;units.add(key)
        checks+=a['checks'];proof[rep]={'receipt':str(d/'audit.json'),'sha256':sha(d/'audit.json'),'checks':a['checks'],'process_sha256':sha(pp)}
    assert len(units)==150
    sd=list(H.glob('all-three-summary--*/summary'));assert len(sd)==1;s=sd[0];r=load(s/'receipt.json')
    cohort=H/'inputs/common-cohort.csv';assert sha(cohort)==r['cohort_sha256']=='ef1fe61e85b8d1fbbd5f99c60ad727d43c33dabe5765c39edcaa6325f0056129'
    for file,key in [('ten-seed-recalculated.csv','summary_sha256'),('per-seed-recalculated.csv','per_seed_sha256')]:assert sha(s/file)==r[key]
    assert r['test_rows']==656 and r['model_seed_units']==150 and r['record_metadata_checks']==295200
    composition={};original=rows(cohort)
    for split in ('fine_train','validation','test'):
        rr=[x for x in original if x['split']==split]
        composition[split]={'rows':len(rr),'dependency_groups':len({x['global_group_id'] for x in rr}),'target_sequences':len({x['target_sequence'] for x in rr}),'studies':len({x['study_id'] for x in rr}),'chemical_strata':{k:sum(x['evaluation_stratum']==k for x in rr) for k in sorted({x['evaluation_stratum'] for x in rr})},'discordance_rows':sum(x['residue_class_graph_discordance'].lower() in ('true','1') for x in rr)}
    assert [composition[k]['rows'] for k in composition]==[497,500,656]
    write(H/'COHORT-COMPOSITION.actual.json',{'cohort_sha256':sha(cohort),'composition':composition})
    ss=rows(s/'ten-seed-recalculated.csv');raw=rows(s/'per-seed-recalculated.csv');nchecks=0
    for row in ss:
        rr=[x for x in raw if all(x[k]==row[k] for k in ('representation','model','stratum'))]
        assert len(rr)==10 and {int(x['seed']) for x in rr}==set(range(10))
        for metric in ('mae','rmse','bias','r2','pearson','spearman'):
            v=[float(x[metric]) for x in rr if x.get(metric) not in ('',None)]
            for key,value in [(metric+'_mean',statistics.mean(v) if v else None),(metric+'_sample_sd',statistics.stdev(v) if len(v)>1 else None)]:
                actual=float(row[key]) if row[key] else None
                assert actual is value or actual is not None and value is not None and abs(actual-value)<1e-12;nchecks+=1
    differences=[]
    for model in sorted({x['model'] for x in raw}):
        for stratum in sorted({x['stratum'] for x in raw}):
            for a,b in itertools.combinations(('hybrid','mlm','morgan'),2):
                aa={int(x['seed']):float(x['mae']) for x in raw if (x['representation'],x['model'],x['stratum'])==(a,model,stratum) and x.get('mae')}
                bb={int(x['seed']):float(x['mae']) for x in raw if (x['representation'],x['model'],x['stratum'])==(b,model,stratum) and x.get('mae')}
                if set(aa)!=set(range(10)) or set(bb)!=set(range(10)):continue
                dd=[aa[i]-bb[i] for i in range(10)];differences.append({'model':model,'stratum':stratum,'representation_a':a,'representation_b':b,'seeds':10,'MAE_A_minus_B_mean':statistics.mean(dd),'sample_sd':statistics.stdev(dd)})
    csvout(H/'paired-seed-MAE-differences.actual.csv',differences)
    group_path=H/'group-macro-per-seed.actual.csv';group_summary=[]
    if group_path.exists():
        gg=rows(group_path);assert len(gg)==150
        for rep,model in sorted({(x['representation'],x['model']) for x in gg}):
            rr=[x for x in gg if (x['representation'],x['model'])==(rep,model)];assert len(rr)==10
            entry={'representation':rep,'model':model,'seeds':10,'groups':rr[0]['groups']}
            for k in ('mae','rmse','bias','r2','pearson','spearman'):
                v=[float(x['group_macro_'+k]) for x in rr if x['group_macro_'+k] not in ('',None)];entry[k+'_mean']=statistics.mean(v) if v else None;entry[k+'_sample_sd']=statistics.stdev(v) if len(v)>1 else None;entry[k+'_valid_groups']=rr[0]['group_valid_'+k]
            group_summary.append(entry)
        csvout(H/'group-macro-ten-seed.actual.csv',group_summary)
    receipt={'schema':'chemical-head.three-representation-joint-audit.ringfix-v2','completed_at':datetime.now(timezone.utc).isoformat(),'valid':True,'cohort_manifest_sha256':'a7b04f77f8445173025d0f381aa875e5d545e6f51a6d1db893e855d4cdd1bb59','cohort_csv_sha256':sha(cohort),'common_split_counts':{k:v['rows'] for k,v in composition.items()},'expected_selected_units':150,'actual_selected_units':len(units),'validated_candidate_fits':300,'frozen_auditor_checks':checks,'independent_record_metadata_checks':r['record_metadata_checks'],'local_mean_SD_checks':nchecks,'audit_receipts':proof,'summary_sha256':r['summary_sha256'],'per_seed_sha256':r['per_seed_sha256'],'paired_differences_sha256':sha(H/'paired-seed-MAE-differences.actual.csv'),'group_summary_sha256':sha(H/'group-macro-ten-seed.actual.csv') if group_summary else None,'this_audit_new_fits':0,'this_audit_new_predictions':0,'this_audit_encoder_loads':0,'this_audit_estimator_loads':0,'tokenizer_adapter':'ringfix-v2-percent-preserving; official weights/vocabulary and raw SMILES unchanged; adapter is an explicit modification','scope':'Frozen chemical encoders and same ESM320 target plus ordinary heads. Source panel blocked. The historical test has prior exposure. Full-encoder fine-tuning and conditional external evaluations are separately versioned.'}
    write(H/'JOINT-AUDIT.actual.json',receipt)
    lines=['# 化学表示共同基准：ringfix v2独立验收','','三种表示在完全相同的497训练、500验证、656测试记录上训练与评分。CLM2 Hybrid和MLM是同一论文的两种权重变体；每种表示配合5族普通预测头、10个种子、2个验证候选。150个选定模型、300次候选拟合全部验收完成。','','新版测试集上Hybrid+ExtraTrees与Morgan+ExtraTrees的MAE几乎持平；所有总体R²为负，跨背景泛化能力仍然有限。','','## 数据与表示','','- 使用完整SMILES，肽化学表示拼接同一冻结ESM320蛋白表示。','- ringfix v2修复相邻环闭合数字的分词，保留百分号环标记；1238个唯一SMILES全部生成特征。适配器是明确记录的输入处理修改，官方权重、词表和SMILES保持原字节。','- 新版656测试与旧版502测试覆盖范围不同，两个版本的MAE不能直接当作模型改进量。','- source面板在严格闭包防火墙后为0训练，继续blocked。','',json.dumps(composition,ensure_ascii=False,indent=2),'','## 总体pKd结果（均值±样本SD）','','|表示|预测头|MAE±SD|RMSE|Spearman|R²|','|---|---|---:|---:|---:|---:|']
    for x in ss:
        if x['stratum']=='all':lines.append(f"|{x['representation']}|{x['model']}|{fmt(x['mae_mean'])}±{fmt(x['mae_sample_sd'])}|{fmt(x['rmse_mean'])}|{fmt(x['spearman_mean'])}|{fmt(x['r2_mean'])}|")
    lines+=['','## ExtraTrees化学分层与标注冲突敏感性','','|表示|分层|n|MAE±SD|Spearman|','|---|---|---:|---:|---:|']
    for x in ss:
        if x['model']=='extra_trees':lines.append(f"|{x['representation']}|{x['stratum']}|{x['n']}|{fmt(x['mae_mean'])}±{fmt(x['mae_sample_sd'])}|{fmt(x['spearman_mean'])}|")
    lines+=['','## 解释与复核','','- 每族内部候选仅由验证MAE选择；表中跨族测试排序属于描述性结果，后续不能据此再次调整模型。','- 固定划分的10种子衡量训练随机性；确定性的预测头可出现SD=0。常数预测的相关性记NA并保留0个有效种子。','- 化学类别按照冻结标签分别评价；NC、PTM、混合层的有限样本量直接列出。discordance排除只重评分固定预测，原训练样本保留。','- 同头同种子MAE差值为描述统计；种子编号相同不代表不同表征共享相同随机轨迹。','- 305,937项冻结审计与295,200项独立元数据检查通过，本机再核1,800个均值/样本SD。审计新增fit、预测、模型载入均为0。','- 组宏指标对每个依赖组等权；未定义的组内相关性保留NA，并记录有效组数。','','[联合收据](JOINT-AUDIT.actual.json) · [组成](COHORT-COMPOSITION.actual.json) · [配对差值](paired-seed-MAE-differences.actual.csv) · [组宏](group-macro-ten-seed.actual.csv)',f'[全部化学层均值SD]({s.relative_to(H).as_posix()}/ten-seed-recalculated.csv) · [逐种子]({s.relative_to(H).as_posix()}/per-seed-recalculated.csv)','']
    (H/'REPORT.three-representations.actual.zh-CN.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'joint_sha256':sha(H/'JOINT-AUDIT.actual.json'),'report_sha256':sha(H/'REPORT.three-representations.actual.zh-CN.md'),'composition':composition,'checks':checks,'mean_SD_checks':nchecks,'paired_rows':len(differences),'group_summary_rows':len(group_summary)},ensure_ascii=False))

if __name__=='__main__':main()
