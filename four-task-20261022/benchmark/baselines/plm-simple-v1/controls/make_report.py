"""Report every paired family under identical frozen coverage, without significance selection."""
import csv
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
RUN=ROOT/'runs/plm-cohort-manual-controls-v1'
def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))
with (RUN/'paired-with-esm/paired-mean-sd.csv').open(encoding='utf-8') as f:rows=list(csv.DictReader(f))
mirror=load(HERE/'local-mirror-receipt.json');audit=load(RUN/'independent-recalculation.json')
paired=load(RUN/'paired-with-esm/independent-recalculation.json');receipt=load(RUN/'paired-with-esm/comparison-receipt.json')
assert mirror['passed'] and audit['passed'] and paired['passed']
names={'constant':'常数','linear':'Ridge','random_forest':'随机森林','extra_trees':'ExtraTrees','hist_gradient_boosting':'HistGradientBoosting'}
lines=['# 与ESM同cohort的原手工序列对照：实际结果','',
    '同一训练/验证/测试覆盖下，ESM配合树模型在两个绝对亲和力面板上有有限MAE改善；Ridge明显更差，silver效应没有一致优势。这些配方差异在cohort对齐后仍存在，不能仅用eligible样本范围不同解释。','',
    '本次保留原手工特征、原五类模型和原两候选，实际新训练150个选中条件/300个候选，种子0–9。未重用旧模型冒充新训练，也未根据测试成绩扩大网格。原全9116传统主轨及原ESM结果均保持不变。','',
    '## 同样本、同seed的MAE比较','',
    '下表均为十种子的均值±样本SD。Δ=手工MAE−ESM MAE，正值表示ESM MAE较低；SD来自十个配对种子差值，不是两组SD相加。','',
    '| 任务/原划分 | 模型 | 测试n | 手工MAE | ESM MAE | 配对Δ |',
    '|---|---|---:|---:|---:|---:|']
for suffix,label in [('ppikb_kd_source_cold_scope_v2_esm2_raw20_len2048','pKd 来源冷划分'),
                     ('ppikb_kd_target_cold_scope_v2_esm2_raw20_len2048','pKd 靶标冷划分'),
                     ('ppikb_effect_metadata_silver_source_cold_esm2_raw20_len2048','ΔpKd silver')]:
    for model,name in names.items():
        row=next(r for r in rows if r['view_id']==suffix and r['model']==model and r['stratum']=='all' and r['metric']=='mae')
        cells=[f'{float(row[p+"_mean"]):.4f} ± {float(row[p+"_sd"]):.4f}' for p in ['manual','esm','delta_manual_minus_ESM']]
        lines.append(f'| {label} | {name} | {row["n"]} | '+' | '.join(cells)+' |')
lines += ['', 'RMSE、R²、偏差、Pearson、Spearman及效应方向准确率的全部配对种子指标另存CSV；标准/NC/PTM/非天然及混合注释共九个评分层均保留。未计算显著性p值。十种子SD描述头训练随机性，不代表独立生物体系的抽样区间。','',
    '## 对齐与验核','',
    '- 直接复用ESM同字节输入CSV：source7419（5890/771/758）、target7419（5203/1087/1129）、silver2222（1923/170/129）；train/validation/test ID完全相同，原字段与ESM raw序列逐行无差异。',
    '- 所有150对同view/同模型家族/同seed测试预测使用完全相同ID、CSV64标签、端点、group与化学分层；匹配时删减测试行0，生成100800行逐样本配对结果。',
    f'- 常数头{receipt["constant_prediction_rows_exactly_identical"]}行逐元素完全相同。两套表示共用同标签/划分的这一检查通过。',
    f'- 手工模型{audit["metric_cells"]}个候选选参、主指标、组与分层数值独立重算差异0；本地同批重算另存，不覆盖远端原收据。配对输出再用NumPy/SciPy/sklearn独立核对{paired["numeric_checks"]}项，差异0。',
    f'- {mirror["files_verified"]}个远端产物、{mirror["bytes_verified"]}字节已完整回本地并逐SHA一致，含300个候选权重、600份候选/选中预测CSV、特征矩阵与日志。60个真实Ridge/scaler权重的训练行数与均值仅对应固定训练子集。','',
    '## 解释边界与保留主轨','',
    '这次比较控制了训练、验证、测试cohort和Node23的sklearn1.4.2/numpy1.26环境。原手工Ridge按原配方保留auto求解器，ESM是LSQR；效应特征布局也不同（手工435维含mutant/target/WT/delta/target-delta，ESM960维为WT/delta/target）。因此结果属于两套方法配方的同cohort比较，不是纯encoder因果效应。','',
    '原全量手工主轨在Windows/sklearn1.9/numpy2.4下训练；它保持独立，可在原目录查阅。将其历史成绩与本次直接相减还会混入训练/验证覆盖及数值环境差别，不能把变化纯归因eligible筛选。','',
    '两个亲和力面板覆盖同7419条观测，不能当14838条独立测量；含521条非标准化学注释，但两种序列基准均未表达PTM、D构象或非天然化学身份。此控制没有新增外部forward、分类/接触位点结果或论文全文复现计数。','',
    '## 资源与文件','',
    'Node23 core25+30，保护siblings57+62；CPU2、nice15、3GiB上限、GPU0，三帧fresh idle/UID RSS/OS reserve门通过。科学worker/PGID306167，345.83s，峰RSS0.265GiB，退出0且无残留；全部CPU槽已释放。另30次训练行runtime canary单列，不计正式选中条件。','',
    '- `comparison-protocol.json`、`execution-contract.json`：输入/代码/授权SHA及预声明规则。',
    '- `runs/plm-cohort-manual-controls-v1/`：150个新模型条件、全部候选、独立验核和完整日志。',
    '- `runs/plm-cohort-manual-controls-v1/paired-with-esm/`：150份同ID配对CSV、逐种子与均值SD，以及独立重算。',
    '- `local-mirror-receipt.json`、`source-artifact-manifest.json`：本地真实资产逐文件校验。']
(HERE/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');print(HERE/'RESULTS.md')
