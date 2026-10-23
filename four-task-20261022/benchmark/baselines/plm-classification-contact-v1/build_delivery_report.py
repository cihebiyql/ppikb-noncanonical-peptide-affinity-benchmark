"""Publish only after complete local delivery and independent recomputation; no fitting."""
import csv
import datetime as dt
import json
from pathlib import Path
from mirror_artifacts import HERE, ROOT, RUN, sha, write

def load(path):return json.loads(path.read_text(encoding='utf-8'))
def rows(path):
    with path.open(encoding='utf-8',newline='') as stream:return list(csv.DictReader(stream))
def main():
    mirror=load(HERE/'local-mirror-receipt.json')
    independent=load(RUN/'heads/independent-recalculation.json')
    repeated=load(RUN/'heads/independent-recalculation.local-v1.json')
    cache=load(HERE/'independent-cache-audit.json')
    fitted=load(RUN/'heads/fitted-metadata-independent-audit.json')
    process=load(RUN/'heads/process-receipt.json')
    coverage=load(HERE/'coverage-manifest.json')
    pipeline=load(HERE/'binary-pipeline-receipt.json')
    common=load(RUN/'common-classification-fixed-predictions/receipt.json')
    assert all(item['passed'] for item in [mirror,independent,repeated,cache,fitted])
    assert independent['selected_runs']==repeated['selected_runs']==100
    assert independent['candidate_fits']==repeated['candidate_fits']==200
    assert process['exit_code']==0 and process['worker_pid_absent'] and not process['surviving_group_pids']
    assert pipeline['status']=='succeeded'
    assert common['fixed_prediction_applications']==100 and common['new_fit_count']==common['new_forward_count']==0
    original=ROOT/'data/view_manifest.json'
    assert sha(original)==coverage['parent_view_manifest_sha256']
    metrics=rows(RUN/'heads/mean-sd-metrics.csv')
    macro=rows(RUN/'heads/macro-mean-sd.csv')
    report=['# 冻结 ESM2 分类与接触位点基准：实际交付', '',
        '两个任务完成五类头、每类十个固定随机种子和两个验证候选：100 个选中训练条件、200 次正式候选拟合。全部候选权重、验证/测试逐行预测、日志和缓存已回到本地并逐 SHA 核验。', '',
        '| 任务 | 总行数 | 训练/验证/测试 | 标签 |', '|---|---:|---|---|']
    for view in coverage['views']:
        counts=view['split_counts'];report.append(f"| {view['task']} | {view['rows']} | {counts['train']}/{counts['validation']}/{counts['test']} | {view['endpoint']} |")
    report+=['', '## 测试结果：十种子均值 ± 样本标准差', '',
        '| 任务 | 模型 | AUROC | AUPRC | MCC | F1 | Brier |', '|---|---|---:|---:|---:|---:|---:|']
    def value(view,model,metric):
        found=[r for r in metrics if r['view_id']==view and r['model']==model and r['metric']==metric and r['split']=='test']
        assert len(found)==1
        row=found[0];assert int(row['seed_count'])==10
        return f"{float(row['mean']):.4f} ± {float(row['sd']):.4f}" if row['mean'] and row['sd'] else '未定义'
    for view in coverage['views']:
        for model in ['constant','linear','random_forest','extra_trees','hist_gradient_boosting']:
            report.append('| '+view['task']+' | '+model+' | '+' | '.join(value(view['id'],model,key) for key in ['auroc','auprc','mcc','f1','brier'])+' |')
    report+=['', '接触任务的测试集包含 12 个完整实验复合物。下表按复合物等权平均，原始每复合物及依赖组件指标、有效分母均单独保存。', '',
        '| 模型 | 复合物宏 AUROC | 复合物宏 AUPRC | 复合物宏 MCC | 有效/全部复合物 |', '|---|---:|---:|---:|---:|']
    contact=next(v for v in coverage['views'] if v['task']=='contact')
    for model in ['constant','linear','random_forest','extra_trees','hist_gradient_boosting']:
        chosen=[r for r in macro if r['view_id']==contact['id'] and r['model']==model and r['split']=='test' and r['averaging_unit']=='complex']
        def cell(key):
            r=next(r for r in chosen if r['metric']==key)
            return f"{float(r['mean']):.4f} ± {float(r['sd']):.4f}"
        ap=next(r for r in chosen if r['metric']=='auprc')
        report.append('| '+model+' | '+' | '.join(cell(k) for k in ['auroc','auprc','mcc'])+f" | {ap['valid_groups']}/{ap['all_groups']} |")
    report+=['', '## 数据、表示与比较范围', '',
        '分类保留 15,468 条原样 AA20 记录；原 17,054 条中 1,586 条因原字符串含非 AA20 符号不适用该输入接口，原划分不变。标签 0 含作者构造的 Rosetta/序列负例。作者发布的原靶标输入范围沿用原数据说明。',
        '接触保留全部 64 个实验复合物、8,625 个已观察残基，逐行原索引、氨基酸和唯一观察链偏移核验全部通过。输入为完整靶标层 6 的对应残基向量及肽均值；结构距离、坐标、真实接触标签和观察范围 mask 均不进入特征。标签表示首实验结构模型 5 Å 几何接触；未观察残基不追加为负例。原三复合物 pilot 属于这 64 个之内。',
        '官方 ESM2-t6-8M 冻结参数，eval/inference、FP32、层 6；均值排除 BOS/EOS/pad，2048 是明确计算预算，无静默截断。分类采用肽和靶标均值拼接，接触采用靶标残基与肽均值拼接。此表示只编码原序列，不能区分共享字母骨架的 PTM、D 型或其他化学身份。',
        '五类头为常数、LogisticRegression、RandomForest、ExtraTrees 和 HistGradientBoosting。scaler 只拟合训练集；验证 AUPRC 选候选，验证 MCC 固定网格选阈值，测试不参与选择。十种子固定相同划分；确定性模型的标准差可以为零。',
        '原生分类共同测试 2,349 行及去原生精确 affinity-train-hit 的 2,290 行在本分支测试预测产生前冻结，另以相同已选验证阈值复算。主测试 2,362 行保持完整。这些子集共享原测试数据，不是新增外部实验；不同方法训练覆盖和预训练资料仍需同时报告。', '',
        '## 可复核证据', '',
        f"- 远端及本地独立数值复算各 {independent['numeric_checks']} 项，错误均为 0；独立实现 AUROC/AP 的并列值处理及阈值最优性检查。",
        f"- 缓存逐序列核查 {cache['token_checks']} 个新表示、{cache['old_mean_exact_bytes_checked']} 个旧均值字节复用、{cache['per_residue_sequence_checks']} 个逐残基矩阵和 {cache['row_index_AA_proofs_checked']} 个索引证明。",
        f"- 40 个 LogisticRegression 候选 scaler 的训练集样本数/均值验证通过；达到 1500 次迭代上限的模型数为 {fitted['iteration_cap_models']}。",
        f"- 本地归档 {mirror['files_verified']} 个源文件、{mirror['bytes_verified']} 字节，源文件及压缩包 SHA 全核通过。",
        '- CPU-only、nice19、两个逻辑核，逐任务 fresh 资源门、独立进程组及 RSS/时间监督；没有占用 GPU 或安装依赖。',
        '- runtime smoke 的 20 次小样本拟合、3 个 canary forward 与正式 200 次拟合、25,336 个表示请求分开计数。', '',
        '本分支属于常用冻结 PLM 加传统头基准，与作者完整论文复现和创新模型分别登记。完整数值见 `runs/plm-classification-contact-v1/heads/`；固定共同子集见同根 `common-classification-fixed-predictions/`。']
    (HERE/'RESULTS.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    refs=[HERE/'source-artifact-manifest.json',HERE/'local-mirror-receipt.json',HERE/'independent-cache-audit.json',
        RUN/'heads/independent-recalculation.json',RUN/'heads/independent-recalculation.local-v1.json',
        RUN/'heads/fitted-metadata-independent-audit.json',RUN/'heads/process-receipt.json',HERE/'RESULTS.md']
    receipt={'schema':'frozen-esm2.binary-delivery.v1','completed_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'passed':True,'selected_training_conditions':100,'candidate_fits':200,'training_seeds':list(range(10)),
        'view_count':2,'candidate_weights':200,'formal_representation_requests':25336,'canary_representation_requests':3,
        'old_mean_vectors_reused_without_forward':622,'runtime_smoke_fits_separate':20,
        'fixed_common_cohort_applications_separate':100,
        'external_test_count':0,'new_paper_full_reproduction_count':0,'innovation_model_count':0,'gpu_jobs':0,
        'all_source_artifacts_local_verified':True,'numeric_errors_remote':len(independent['errors']),
        'numeric_errors_local':len(repeated['errors']),'new_fit_count_for_delivery':0,'new_forward_count_for_delivery':0,
        'evidence':[{'path':str(p),'sha256':sha(p)} for p in refs],'code_sha256':sha(__file__)}
    write(HERE/'DELIVERY-RECEIPT.json',receipt);print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':main()
