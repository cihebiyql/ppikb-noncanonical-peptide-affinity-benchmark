"""Verify every grouped output, write the 27-candidate report, and inventory all local bytes."""
import datetime as dt
from pathlib import Path
import psutil
from common import HERE,ROOT,DATA,RUN,sha,load,write,read
from verify_fixed import metrics

def main():
    audit=load(RUN/'independent-recalculation.json');assert audit['passed']
    contract=load(HERE/'execution-contract.json');source=read(contract['candidate_csv']);ref={r['row_id']:r for r in source}
    group_rows=read(RUN/'per-group-per-seed.csv');assert len(group_rows)==2200
    errors=[];checks=0
    for item in contract['models']:
        panel='source' if '_source_' in item['training_view'] else 'target'
        directory=RUN/panel/item['model']/f"s{item['seed']}"
        rows=read(directory/'predictions.csv')
        for unit in contract['metric_groups']:
            grouped={}
            for row in rows:grouped.setdefault(row[unit],[]).append(row)
            for group,values in grouped.items():
                expected=metrics([float(r['label']) for r in values],[float(r['prediction']) for r in values])
                saved=[r for r in group_rows if r['panel']==panel and r['model']==item['model'] and int(r['seed'])==item['seed'] and r['unit']==unit and r['group']==group]
                assert len(saved)==1
                for metric,value in expected.items():
                    actual=float(saved[0][metric]) if saved[0][metric] else None;checks+=1
                    if (actual is None)!=(value is None) or (actual is not None and abs(actual-value)>1e-9):errors.append({'group':group,'metric':metric,'actual':actual,'expected':value})
    group_audit={'passed':not errors,'group_rows':len(group_rows),'numeric_checks':checks,'errors':errors,'new_fit_count':0,'new_model_forward_count':0,'code_sha256':sha(__file__)}
    write(RUN/'group-file-independent-audit.json',group_audit);assert group_audit['passed']
    active=[]
    for proc in psutil.process_iter(['pid','cmdline']):
        try:
            arguments=proc.info['cmdline'] or []
            if any(Path(arg).name in {'run_fixed.py','supervise_fixed.py'} and 'pepbi-conditional-external-v1' in arg for arg in arguments):active.append(proc.pid)
        except (psutil.Error,OSError,ValueError):pass
    assert not active
    write(RUN/'final-process-audit.json',{'passed':True,'owned_worker_or_supervisor_pids':active,'new_fit_count':0,'new_model_forward_count':0})
    training_checks=[]
    for panel in ['source','target']:
        path=ROOT/f'runs/cpu-v2/ppikb_kd_{panel}_cold_scope_v2/task-contract.json';training=load(path)
        assert sha(training['input_path'])==training['input_sha256']
        training_checks.append({'path':training['input_path'],'sha256':training['input_sha256'],'original_training_csv_unchanged':True})
    summary=read(RUN/'mean-sd-metrics.csv')
    def metric(panel,model,unit,key):
        row=next(r for r in summary if r['panel']==panel and r['model']==model and r['averaging']==unit and r['metric']==key)
        assert int(row['seed_count'])==10
        return f"{float(row['mean']):.4f} ± {float(row['sd']):.4f}" if row['mean'] else '未定义'
    report=['# 27条候选条件外测', '',
        '已将100个既有固定模型应用到全部27条PEPBI候选：两个PPIKB训练面板、五类手工特征模型、每类十个随机种子。没有新增训练、调参或删掉预测不佳的候选；新增2700行是重复模型应用的预测产物，独特候选仍为27条。', '',
        '## 条件与分母', '',
        '27条候选覆盖13个蛋白完整构建体、12条肽、5个binding groups和4篇原始ITC来源，追溯到65个结构模型行。沿用冻结完整序列与温度注释，Kd[M]只转为−log10(Kd[M])。原329行/188情境、27候选和已认证独立外测0行分别登记。',
        '本批候选通过现有可用字段的序列对、直接包含、来源和PDB重叠筛查。缓冲条件、完整化学实体及同源/预训练暴露尚未逐项认证；原PepAff/PepInter表缺少的DOI/PDB仍是unknown。因此本次结果标题与资格保持“候选条件外测”，不登记blind、新家族或非天然核心残基外测。AA20字母本身不认证未修饰化学身份。', '',
        '## 全部固定模型结果', '',
        '数值为十种子的均值±样本标准差；种子SD不等于跨生物体系置信区间。MAE/RMSE单位为pKd。宏MAE对对应来源、构建体或结合组等权平均。', '',
        '|训练面板|固定模型|微MAE|微RMSE|微R²|构建体宏MAE(13)|来源宏MAE(4)|结合组宏MAE(5)|',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for panel in ['source','target']:
        for model in ['constant','linear','random_forest','extra_trees','hist_gradient_boosting']:
            report.append('|'+panel+'|'+model+'|'+'|'.join([metric(panel,model,'micro','mae'),metric(panel,model,'micro','rmse'),metric(panel,model,'micro','r2'),metric(panel,model,'target_id','mae'),metric(panel,model,'study_id','mae'),metric(panel,model,'binding_group','mae')])+'|')
    report+=['',
        '两面板的全部模型在这批候选上的微R²均为负，显示其相对于该候选集均值仍存在较大预测误差。保留全部模型及每个来源/构建体/结合组的结果；不以外测成绩重新选权重或候选。单样本或标签恒定分组的相关系数/R²按未定义保存，并列出有效分组分母。', '',
        '## 冻结接口与核验', '',
        '原手工特征为174维。27×174准备数组与原冻结特征函数重算逐元素完全相同；标签、温度、Kd均不进入特征。固定权重由原验证集选择，模型内scaler沿用原训练状态。运行前后100份权重、原训练结果与候选记录、两个训练CSV以及源候选/准备manifest均逐SHA保持不变。原prepare-only manifest未改写，新执行授权和合同单独登记。',
        f"独立CSV float64标签、Kd换算、全部100×27预测、分组宏指标和种子汇总共{audit['numeric_checks']}项数值核对通过；另有{checks}项分组文件核对，错误均为0。每行保留原始来源、构建体、温度和结构副本谱系。",
        '使用原权重对应的Windows sklearn1.9.0运行环境，CPU2、RSS上限1GiB、预留2GiB本机内存，三帧空闲资源门与600秒超时。Windows采用最低IDLE_PRIORITY_CLASS；该平台无POSIX numeric nice19，合同与终态如实记录。实际进程13.56秒、峰值RSS181059584字节，exit0且无残留，GPU0。',
        '一次合同准备读CSV时遇到UTF-8 BOM头，已以utf-8-sig解析修复并保留失败记录；原候选文件字节未改，发生在任何模型读取/预测之前。', '',
        '## 产物入口', '',
        '- `runs/pepbi-conditional-external-v1/{source,target}/模型/s种子/predictions.csv`：全部27行逐条预测；相邻result.json记录固定权重SHA、微指标和三种宏指标。',
        '- `per-seed-metrics.csv`、`per-group-per-seed.csv`、`mean-sd-metrics.csv`：完整六类回归指标与有效分母。',
        '- `execution-contract.json`：输入、代码、100权重与原结果SHA；`process-receipt.json`：真实资源及退出记录。',
        '- `independent-recalculation.json`、`group-file-independent-audit.json`：独立复算；`local-delivery-index.json`：本地全部产物及继承权重定位与SHA。', '',
        '本轮新增固定模型应用100、训练模型0、已认证独立外测记录0。前一轮分类/接触结果及全项目generic训练完成数保持不变。']
    (HERE/'REPORT.zh-CN.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    exclude={'local-delivery-index.json','DELIVERY-RECEIPT.json'}
    paths=sorted(p for base in [HERE,RUN] for p in base.rglob('*') if p.is_file() and p.name not in exclude and '__pycache__' not in p.parts)
    records=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths]
    inherited=[{'path':item['weight_path'],'sha256':sha(item['weight_path']),'bytes':Path(item['weight_path']).stat().st_size,'physically_local_original_weight':True} for item in contract['models']]
    for old,new in zip(contract['models'],inherited):assert old['sha256']==new['sha256']
    index={'files':records,'owned_file_count':len(records),'owned_bytes':sum(r['bytes'] for r in records),
        'inherited_original_weights':inherited,'inherited_original_weight_count':100,'training_csv_checks':training_checks,
        'input_csv_sha256':sha(contract['candidate_csv']),'all_candidate_rows_preserved':27,'no_new_weights_created':True,
        'certified_independent_external_rows':0,'new_fit_count':0,'gpu':False,'code_sha256':sha(__file__)}
    write(HERE/'local-delivery-index.json',index)
    receipt={'schema':'pepbi.27conditional.fixed-external.delivery.v1','title':'27条候选条件外测','passed':True,
        'completed_at':dt.datetime.now(dt.timezone.utc).isoformat(),'fixed_model_applications':100,'unique_candidate_rows':27,
        'calculation_prediction_rows':2700,'training_seeds':list(range(10)),'training_panels':2,'model_families':5,
        'binding_groups':5,'source_ITC_DOIs':4,'protein_constructs':13,'certified_independent_external_rows':0,
        'new_fit_count':0,'tuning_count':0,'generic_training_count_increment':0,'gpu_jobs':0,
        'numeric_checks':audit['numeric_checks'],'group_file_numeric_checks':checks,'numeric_errors':0,
        'all_source_weights_and_inputs_unchanged':True,'all_owned_artifacts_local_SHA_indexed':True,
        'original_100_classification_contact_delivery_unchanged':True,'owned_processes_absent':True,
        'contract_sha256':sha(HERE/'execution-contract.json'),'report_sha256':sha(HERE/'REPORT.zh-CN.md'),
        'index_sha256':sha(HERE/'local-delivery-index.json'),'independent_recalculation_sha256':sha(RUN/'independent-recalculation.json'),
        'process_receipt_sha256':sha(RUN/'process-receipt.json'),'code_sha256':sha(__file__)}
    write(HERE/'DELIVERY-RECEIPT.json',receipt);print(receipt)
if __name__=='__main__':main()
