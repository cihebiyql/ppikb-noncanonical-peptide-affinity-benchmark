"""Authorized metric-only Chinese report. No raw-label/model/prediction readers."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

HERE = Path(__file__).resolve().parent
PANELS = ('source_peptide_dependency_cold', 'target_reference_homology_cold')
REGIMES = ('NC_only', 'standard_only')
METRICS = ('MAE', 'RMSE', 'Pearson', 'Spearman', 'R2')
NN = ('GraphDTA-GIN', 'MGraphDTA', 'DGDTA-CL', 'DeepNC-GEN', 'GS-DTA')
RF = 'RF-Morgan2-chiral-AAC-DP'
REFERENCES = ('reference:train_mean', 'reference:train_median', 'reference:target_reference_train_median')
CATEGORIES = {'five_prior_paper_NN': NN, 'auxiliary_handcrafted_RF': (RF,), 'three_deterministic_references': REFERENCES}
EXPECTED_LEDGER = {'five_prior_paper_NN': (600,265800), 'auxiliary_handcrafted_RF': (120,53160), 'three_deterministic_references': (360,159480)}
NC_N = dict(zip(PANELS,(303,332)))
ALL_N = dict(zip(PANELS,(1039,1443)))
FIELDS = ('category','dataset_id','panel','method_id','regime','cohort','aggregation','metric')
ROW_FIELDS = set(FIELDS) | {'paper_count_contribution','prior_paper_method_id','raw_dataset_id','seed','value','n','n_unit','defined_group_count'}
NN_INDEX_SHA = 'c7b3bde68c9a741c0ac3f255a825e4a55dd7234e2b4e6d48f212fee8d5609ab1'
SOURCES = ('report_builder.py','report-spec-v1.json','FIELD-MAPPING.md','README.md')

def path(value):
    import os
    s=str(value).replace('\\','/')
    if os.name!='nt' and len(s)>2 and s[1:3]==':/': s='/mnt/'+s[0].lower()+'/'+s[3:]
    elif os.name=='nt' and s.startswith('/mnt/') and len(s)>7 and s[6]=='/': s=s[5].upper()+':'+s[6:]
    return Path(s)

def read(p): return json.loads(path(p).read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(path(p).read_bytes()).hexdigest()
def require(p,digest):
    if sha(p)!=digest: raise ValueError('SHA mismatch: '+str(p))
def write(p,obj): path(p).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def source_hashes(): return {n:sha(HERE/n) for n in SOURCES}

def csv_out(p,rows):
    fields=sorted({k for r in rows for k in r})
    with path(p).open('w',encoding='utf-8-sig',newline='') as h:
        w=csv.DictWriter(h,fieldnames=fields);w.writeheader()
        for r in rows:
            w.writerow({k:'null' if v is None else json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})

def validate_rows(rows):
    seen=set()
    for r in rows:
        if set(r)-ROW_FIELDS: raise ValueError('Unexpected fields: metric-only input required')
        if r['category'] not in CATEGORIES or r['method_id'] not in CATEGORIES[r['category']]: raise ValueError('Method/category mismatch')
        if r['panel'] not in PANELS or r['regime'] not in REGIMES or type(r['seed']) is not int or r['seed'] not in range(10): raise ValueError('Unknown coordinate')
        if r['metric'] not in METRICS or type(r['n']) is not int or r['n']<0: raise ValueError('Metric/count invalid')
        if r['value'] is not None and (isinstance(r['value'],bool) or not math.isfinite(float(r['value']))): raise ValueError('Nonfinite metric')
        key=tuple(r[k] for k in FIELDS)+(r['seed'],)
        if key in seen: raise ValueError('Duplicate per-seed metric')
        seen.add(key)
        if r['dataset_id']=='PPIKB-internal':
            if r.get('raw_dataset_id') != ('source_test' if r['panel']==PANELS[0] else 'target_test'): raise ValueError('Internal dataset/panel mismatch')
            expected=NC_N[r['panel']] if r['cohort']=='NC_core' else ALL_N[r['panel']]-NC_N[r['panel']] if r['cohort']=='standard' else ALL_N[r['panel']] if r['cohort']=='all' else None
        elif r['dataset_id']=='PTM-external75':
            if r.get('raw_dataset_id')!='external75': raise ValueError('External identity mismatch')
            expected={'all':75,'external_primary67':67,'external_conditional_sensitivity8':8,'external_reference_target_cold2':2}.get(r['cohort'])
        elif r['dataset_id']=='IgG-supplement13':
            if r.get('raw_dataset_id')!='supplement13': raise ValueError('Supplement identity mismatch')
            expected={'all':13,'supplement_NC8':8,'supplement_standard5':5}.get(r['cohort'])
        else: raise ValueError('Unknown dataset')
        if expected is not None and r['aggregation']=='row_micro' and r['n']!=expected: raise ValueError('Cohort denominator mismatch')
        if r['defined_group_count'] is not None and (type(r['defined_group_count']) is not int or not 0<=r['defined_group_count']<=r['n']): raise ValueError('Group-count invalid')

def summarize(rows):
    validate_rows(rows);groups=defaultdict(list)
    for r in rows: groups[tuple(r[k] for k in FIELDS)].append(r)
    summary=[]
    for key,rs in sorted(groups.items()):
        rs=sorted(rs,key=lambda r:r['seed']);nums=[float(r['value']) for r in rs if r['value'] is not None]
        summary.append(dict(zip(FIELDS,key),mean=statistics.mean(nums) if nums else None,sample_sd=statistics.stdev(nums) if len(nums)>1 else None,
            completed_seed_count=len(rs),defined_seed_count=len(nums),missing_seeds=sorted(set(range(10))-{r['seed'] for r in rs}),
            n_by_seed={str(r['seed']):r['n'] for r in rs},n_unit=rs[0]['n_unit'],
            defined_group_count_by_seed={str(r['seed']):r['defined_group_count'] for r in rs},
            values_by_seed={str(r['seed']):r['value'] for r in rs}))
    return summary

def coverage(rows):
    present={(r['category'],r['dataset_id'],r['panel'],r['method_id'],r['regime'],r['seed'],r['metric']) for r in rows if r['cohort']=='all' and r['aggregation']=='row_micro'}
    counts={(r['category'],r['dataset_id'],r['panel'],r['method_id'],r['regime'],r['seed']):r['n'] for r in rows if r['cohort']=='all' and r['aggregation']=='row_micro' and r['metric']=='MAE'}
    out={}
    for cat,methods in CATEGORIES.items():
        desired={(cat,d,p,m,r,s,k) for d in ('PPIKB-internal','PTM-external75','IgG-supplement13') for p in PANELS for m in methods for r in REGIMES for s in range(10) for k in METRICS}
        complete_keys=[(cat,d,p,m,r,s) for d in ('PPIKB-internal','PTM-external75','IgG-supplement13') for p in PANELS for m in methods for r in REGIMES for s in range(10) if all((cat,d,p,m,r,s,k) in present for k in METRICS)]
        complete_scores=len(complete_keys)
        out[cat]={'expected_scores':EXPECTED_LEDGER[cat][0],'actual_complete_score_metric_sets':complete_scores,'expected_prediction_rows':EXPECTED_LEDGER[cat][1],
                  'actual_complete_prediction_rows':sum(counts[k] for k in complete_keys),'missing_metric_coordinates':len(desired-present),'complete':desired<=present}
    return out

def check_full_cohorts(rows):
    present={(r['category'],r['dataset_id'],r['panel'],r['method_id'],r['regime'],r['seed'],r['metric'],r['cohort']) for r in rows if r['aggregation']=='row_micro'}
    scopes={'PPIKB-internal':('NC_core','standard'), 'PTM-external75':('external_primary67','external_conditional_sensitivity8','external_reference_target_cold2'), 'IgG-supplement13':('supplement_NC8','supplement_standard5')}
    for cat,methods in CATEGORIES.items():
        for dataset,cohorts in scopes.items():
            desired={(cat,dataset,p,m,r,s,k,c) for p in PANELS for m in methods for r in REGIMES for s in range(10) for k in METRICS for c in cohorts}
            if not desired<=present:raise ValueError('Complete audit lacks prespecified NC/standard/external cohort coordinates')

def fmt(r):
    if r is None: return '待真实审计结果'
    if r['mean'] is None: return '未定义（0/'+str(r['completed_seed_count'])+'有效）'
    sd='null' if r['sample_sd'] is None else f"{r['sample_sd']:.4f}"
    return f"{r['mean']:.4f} ± {sd}（{r['defined_seed_count']}/{r['completed_seed_count']}有效）"

def table(summary,panel,dataset,cohort,aggregation='row_micro',references=False):
    selected=[r for r in summary if r['panel']==panel and r['dataset_id']==dataset and r['cohort']==cohort and r['aggregation']==aggregation and (r['method_id'] in REFERENCES)==references]
    lookup={(r['method_id'],r['regime'],r['metric']):r for r in selected}
    methods=REFERENCES if references else NN+(RF,)
    out=['| 方法 | 训练队列 | n／group | MAE ↓ | RMSE ↓ | Pearson ↑ | Spearman ↑ | R² ↑ |','| --- | --- | --- | --- | --- | --- | --- | --- |']
    for m in methods:
        for reg in REGIMES:
            first=lookup.get((m,reg,'MAE')); counts=sorted(set(first['n_by_seed'].values())) if first else []
            n='/'.join(map(str,counts)) if counts else '待审计'
            out.append('| '+ ' | '.join((m,reg,n,*(fmt(lookup.get((m,reg,k))) for k in METRICS)))+' |')
    return '\n'.join(out)

def render(summary,ledger,template=False,training=None):
    state='待真实审计结果' if template else '独立审计指标汇总'
    out=['# 肽—蛋白结合亲和力基准报告', '',state,'',
         '主比较：在每个固定 NC_core 测试集上，比较 NC_only 与 standard_only 训练。两面板分别呈现，单位为 pKd；MAE、RMSE 越低越好，相关与 R² 越高越好。', '']
    if not template:
        out+=['## 实际覆盖','', '| 类别 | 完整指标组／预期评分 | 完整指标组对应预测行／预期 | 缺失指标坐标 |','| --- | --- | --- | --- |']
        for cat,x in ledger.items():out.append(f"| {cat} | {x['actual_complete_score_metric_sets']}/{x['expected_scores']} | {x['actual_complete_prediction_rows']}/{x['expected_prediction_rows']} | {x['missing_metric_coordinates']} |")
        out+=['','缺失、未定义与成功结果分别保存；预期量不代表实际完成量。','']
    out+=['## 主结果：相同 NC 测试集','']
    for panel in PANELS:
        out += [f'### {panel}：NC_core n={NC_N[panel]}','',table(summary,panel,'PPIKB-internal','NC_core'),'']
    out+=['## 确定性参考规则（单列）','','参考规则由相应训练队列的均值、中位数和靶标参考中位数生成。十个种子复用同一规则结果，种子间零波动不构成十次独立拟合。','']
    for panel in PANELS:out += [f'### {panel}：NC_core','',table(summary,panel,'PPIKB-internal','NC_core',references=True),'']
    out+=['## 化学分层、标准对照与敏感性','']
    internal_cohorts=('synthetic_D_backbone','PTM','synthetic_and_PTM','other_NC','standard','NC_core_exclude_discordant_sensitivity','standard_exclude_discordant_sensitivity')
    for panel in PANELS:
        for cohort in internal_cohorts:
            out += [f'### {panel} / {cohort}','',table(summary,panel,'PPIKB-internal',cohort),'']
    out+=['同预测排除冲突的审计字段可能仅提供 exclude_discordant:<stratum>；所有可用字段原名保存在详细表中，缺少 NC 专属汇总时显示待审计。','']
    out+=['## 独立外部验证','', '75 条 PTM 外测按主集67、条件敏感性8与参考靶标冷2分别报告；参考冷2包含在主集67中。另13条为单独诊断，分8条 synthetic_D_backbone 与5条标准对照。','']
    for panel in PANELS:
        for dataset,cohorts in (('PTM-external75',('external_primary67','external_conditional_sensitivity8','external_reference_target_cold2')),('IgG-supplement13',('supplement_NC8','supplement_standard5'))):
            for cohort in cohorts:out += [f'### {panel} / {dataset} / {cohort}','',table(summary,panel,dataset,cohort),'']
    out+=['## 靶标与来源等权汇总及 matched 诊断','', '详细表保留 equal_weight_target_id、equal_weight_target_reference_sequence_sha、equal_weight_study_id，以及 matched_row_micro、matched_equal_target_reference、matched_equal_study_id。只展示审计实际提供的 cohort；all_diagnostic 继续标为全测试池诊断，不能转称 NC 专属 macro。','',
          '来源＋肽冷面板 matched 参考靶标26个（NC90／标准124）；参考同源冷面板45个（NC174／标准203）。这些固定子集分别评价同一组靶标条件，训练量差异仍需保留。','']
    for panel in PANELS:
        for cohort in ('NC_matched','standard_matched'):out += [f'### {panel} / {cohort}','',table(summary,panel,'PPIKB-internal',cohort,'matched_row_micro'),'']
    macro=[r for r in summary if r['aggregation'] not in ('row_micro','matched_row_micro')]
    out+=['可用 macro 指标行数：'+('待真实审计结果' if template else str(len(macro)))+'。逐 seed 有效组数、总组数、有效 seed 数与未定义值见 summary.csv / metrics-per-seed.csv。','']
    out+=['## 方法、调参与证据','',
          '五个已发表架构在共同 PPIKB 数据上重训：GraphDTA-GIN、MGraphDTA、DGDTA-CL、DeepNC-GEN、GS-DTA。严格近三年窗口内为 GS-DTA（2025）。RF 为传统手工特征基准，计0篇作者方法；本轮先完成基准。', '',
          'NN：每个方法×面板×训练队列×seed 搜索 LR=0.001／0.0003，最多20 epochs，patience5，以同队列 validation MAE 选择 epoch 与候选。RF：200树、sqrt特征采样、leaf2／5两候选，按相同规则选择。测试与外部标签在选择后用于评分。','',
          '十种子汇总为均值±样本标准差（ddof=1），每项同时保留有效 seed 数。未定义保持 null；样本标准差描述训练随机性。两个面板不合并为独立样本，种子不作为生物重复，不进行 seed t-test。', '',
          '输入与注释范围统一见 [方法与数据说明]('+ (HERE.parent/'report-preparation/方法与数据说明.md').as_posix() +')：蛋白为参考序列及作者1000／1200aa前缀；五个NN存在原子手性盲区，RF仅利用输入已指定手性。608行图—原注释冲突保留并作同测试预测排除敏感性。数据量和靶标分布不同，队列差异同时包含这些因素。外部75与13为回顾性评价，13采用449aa重链Fc侧参考视图。该说明及其原paper/code链接集中保存构建体、方法修复与实体证据。','',
          '预登记执行账目分列：NN400个有效候选fit、200个选择；另保留1次 I/O 中断尝试及同seed同设置的新输出路径恢复。RF80个候选fit、40个选择；三条确定性规则形成120个规则调用、360次评分。评分总账预期1080次／478440行，其中NN600／265800、RF120／53160、reference360／159480；完成量以本报告的真实覆盖和独立清单为准。','',
          '全部逐epoch日志、候选验证结果、选择收据、逐记录预测与检查点保留在原路径：execution／control运行清单、auxiliary-rf-baseline/real-runs-v1、evaluation评分输出与review审计清单。报告读取指标和授权训练元信息，原始数据保持原档。','']
    if training is None:out+=['### 训练预算使用','','待授权训练 complete／selection 元信息。best_epoch 可从现有收据读取；最后完成epoch、实际earlystop与达到20epoch上限在来源缺字段时保留 null，不能由 best_epoch 反推。','']
    else:out+=['### 训练预算使用','',f"已读取授权训练元信息 {len(training)} 份，详细记录见 training-metadata.json。候选耗时可求和为进程累计秒；并行墙钟需独立运行清单。缺失的实际停止epoch保留 null。",'']
    return '\n'.join(out)+'\n'

def verify_joint(joint):
    if (joint.get('status'),joint.get('NN_selections'),joint.get('RF_selections'))!=('all_200_NN_plus_40_RF_frozen',200,40) or joint.get('NN_execution_index_sha256')!=NN_INDEX_SHA: raise ValueError('Full approved NN200+RF40 joint barrier required')

def authorized_inputs(auth_file,manifest_file,joint_file):
    auth=read(auth_file)
    if auth.get('root_final_scientific_report_authorized') is not True: raise PermissionError('Await explicit root post-joint audited-metric reporting authorization')
    if time.time()>=auth.get('deadline_unix',0): raise TimeoutError('Reporting authorization expired')
    if auth.get('source_sha256')!=source_hashes(): raise ValueError('Reporting source not authorized')
    require(joint_file,auth['joint_barrier_sha256']);joint=read(joint_file);verify_joint(joint)
    require(manifest_file,auth['audited_manifest_sha256']);manifest=read(manifest_file)
    if manifest.get('joint_barrier_sha256')!=auth['joint_barrier_sha256']: raise ValueError('Audit uses different joint barrier')
    full=manifest.get('status')=='complete_postjoint_metric_table_assembly'
    if not full and not (auth.get('allow_partial_audited_coverage') is True and manifest.get('status')=='partial_postjoint_metric_table_assembly' and manifest.get('independently_audited_available_metrics') is True): raise ValueError('Accepted independent complete or explicitly permitted partial metric assembly required')
    # Fixed filenames only: never follow raw-gold/model/prediction paths.
    metric_file=path(manifest_file).parent/'unified-per-seed-metrics.json'
    require(metric_file,manifest['per_seed_table_sha256']);rows=read(metric_file)
    summary=summarize(rows);ledger=coverage(rows)
    if full:
        if not all(x['complete'] for x in ledger.values()) or (manifest.get('ledger_score_receipts'),manifest.get('ledger_prediction_rows'))!=(1080,478440): raise ValueError('Complete manifest has missing scores or wrong ledger')
        check_full_cohorts(rows)
    training=None
    if auth.get('training_metadata_map'):
        ref=auth['training_metadata_map'];require(ref['path'],ref['sha256']);entries=read(ref['path']);training=[]
        for entry in entries:
            q=path(entry['path'])
            if q.name not in ('complete.json','selection.json','failed.json') or entry['kind'] not in ('NN_candidate','NN_selection','NN_interrupted','RF_candidate','RF_selection'): raise ValueError('Only explicit training metadata receipts accepted')
            require(q,entry['sha256']);raw=read(q)
            keep=('status','method_id','panel','split_id','regime','seed','candidate_index','best_epoch','elapsed_seconds','elapsed_fit_seconds','hyperparameters','selection_metric','fit_spec_sha256','spec_sha256')
            row={k:raw[k] for k in keep if k in raw};row.update(kind=entry['kind'],path=str(q),sha256=entry['sha256'],completed_epoch_count=raw.get('completed_epoch_count'),early_stopped=raw.get('early_stopped'),epochs_at_cap=raw.get('epochs_at_cap'))
            if 'candidates' in raw:row['candidate_metadata']=[{k:c[k] for k in ('candidate_index','hyperparameters','best_epoch','elapsed_seconds','effective_parameters','validation_MAE') if k in c} for c in raw['candidates']]
            training.append(row)
    return rows,summary,ledger,training,auth

def produce(output,rows,summary,ledger,template,training=None,provenance=None):
    out=path(output);out.mkdir(parents=True,exist_ok=False)
    csv_out(out/'metrics-per-seed.csv',rows);write(out/'metrics-per-seed.json',rows)
    csv_out(out/'summary.csv',summary);write(out/'summary.json',summary)
    main=[r for r in summary if r['dataset_id']=='PPIKB-internal' and r['cohort']=='NC_core' and r['aggregation']=='row_micro']
    csv_out(out/'main-NC.csv',main);write(out/'coverage.json',ledger)
    (out/'完整报告.md').write_text(render(summary,ledger,template,training),encoding='utf-8')
    (out/'README.md').write_text(('当前状态：待真实审计结果。\n' if template else '当前状态：已授权的独立审计指标组表。\n')+'\n从 完整报告.md 的 NC_core 主表开始；main-NC.csv 保存主表的五指标长表，summary.csv 保存全部分层及macro，metrics-per-seed.csv / .json 保存逐seed原值（null保留）。coverage.json明确缺失。\n',encoding='utf-8')
    if training is not None:write(out/'training-metadata.json',training)
    write(out/'report-receipt.json',dict(status='template_waiting_real_audit' if template else 'authorized_metric_only_report',source_sha256=source_hashes(),raw_gold_predictions_models_training_labels_read=False,model_calls=0,fitting=0,provenance=provenance or {},artifacts={p.name:sha(p) for p in out.iterdir() if p.is_file()}))

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    t=sub.add_parser('template');t.add_argument('--output',required=True)
    a=sub.add_parser('actual');a.add_argument('--authorization',required=True);a.add_argument('--audited-manifest',required=True);a.add_argument('--joint-barrier',required=True);a.add_argument('--output',required=True)
    args=p.parse_args()
    if args.command=='template':produce(args.output,[],[],{},True)
    else:
        rows,summary,ledger,training,auth=authorized_inputs(args.authorization,args.audited_manifest,args.joint_barrier)
        produce(args.output,rows,summary,ledger,False,training,dict(authorization_sha256=sha(args.authorization),audited_manifest_sha256=auth['audited_manifest_sha256'],joint_barrier_sha256=auth['joint_barrier_sha256']))

if __name__=='__main__':main()
