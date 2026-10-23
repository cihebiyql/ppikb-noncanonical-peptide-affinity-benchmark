"""Generate a concise numerical report only after actual delivery and independent checks."""
import csv
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
RUN=ROOT/'runs/plm-simple-v1'
def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def read(path):
    with Path(path).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def fmt(mean,sd):return f'{float(mean):.4f} ± {float(sd):.4f}' if mean and sd else '—'

mirror=load(HERE/'local-mirror-receipt.json')
independent=load(RUN/'heads/independent-recalculation.json')
assert mirror['passed'] and independent['passed'] and independent['selected_runs']==150
coverage=load(HERE/'coverage-manifest.json')
binding=load(HERE/'feature-cache-binding.json')
extraction=load(HERE/'feature-cache-cpu-v3/receipt.json')
feature_process=load(RUN/'extraction-cpu-v3-formal-supervision/process-receipt.json')
head_process=load(RUN/'heads/process-receipt.json')
common=load(RUN/'common-prediction-comparison/comparison-receipt.json')
assert common['fixed_prediction_evaluations']==200 and common['old_summary_unchanged']
summary=read(RUN/'heads/mean-sd-metrics.csv')
names={'constant':'常数','linear':'Ridge','random_forest':'随机森林','extra_trees':'ExtraTrees','hist_gradient_boosting':'HistGradientBoosting'}
lines=['# 冻结 ESM2 小模型基准：实际结果', '',
    '三个视图、五类简单头、每类两个验证候选及十个固定训练种子均已完成。共150个选中训练条件、300次正式候选拟合；另30次仅使用训练行的运行时canary单列。语言模型参数全部冻结，表示提取没有监督拟合。此项是通用基准条件，不计为新增论文的完整复现。','',
    f'全部产物已回流本地，逐文件SHA验证通过：{mirror["files_verified"]}个文件。独立CSV64重算检查{independent["metric_cells"]}个指标/选参单元，差异0；本地再次重算同一批单元也为0差异，原远端收据保留。','',
    '在这次预声明配置中，树模型对亲和力常数基线有有限改进，silver效应增益很小；Ridge在三个视图均明显弱于常数。这些结果保留原样，没有依据测试结果扩大参数网格或重新选模型。','',
    '## 主测试结果','',
    '| 原划分/任务 | 模型 | n | MAE均值±样本SD | RMSE均值±样本SD | R²均值±样本SD |',
    '|---|---|---:|---:|---:|---:|']
for view in coverage['views']:
    label='ΔpKd silver' if view['task']=='effect' else ('pKd 来源冷划分' if 'source_cold' in view['id'] else 'pKd 靶标冷划分')
    for model,name in names.items():
        indexed={r['metric']:r for r in summary if r['view_id']==view['id'] and r['model']==model and r['split']=='test'}
        values=[fmt(indexed[m]['mean'],indexed[m]['sd']) for m in ['mae','rmse','r2']]
        lines.append(f'| {label} | {name} | {view["split_counts"]["test"]} | '+ ' | '.join(values)+' |')
lines += ['', 'SD表示十次头训练的变化，不是独立样本抽样置信区间；确定性头的SD为0是正常结果。全部逐行预测、候选权重、验证指标、种子指标、组宏平均和化学分层保留在对应run目录。','',
    '## 输入覆盖与比较','',
    '亲和力每面板从9116条保留7419条（6898标准注释、521非标准注释）；两面板是相同观测的不同固定划分，不能当14838个独立测量。原始非AA20肽符号造成1447条原因标记，>2048残基预算造成283条，其中33条同时命中两类原因；原数据没有删除。效应从2289对保留2222对，剔除的67对均超靶标长度预算，原测试129对全部保留。','',
    '亲和力测试中的非标准注释为来源62条、靶标112条；效应测试仅2条PTM。模型直接使用原记录的字母字符串，未表示PTM、D构象、非天然化学身份；这些分层成绩不能被称为化学敏感性证明。','',
    '原样有效输入共4650个亲和力肽/靶标组合、1160个效应组合。三个视图的精确有效输入跨split碰撞均为0；重复观测和组内相关性仍需保留。','',
    '另外按现有共同测试ID重算了200个ESM头评价：标准2919条件测试288/425行，骨架6336条件测试683/946行，均完整覆盖。旧比较表只读，原始CSV float64标签与端点逐ID一致。训练覆盖、预训练来源和模型输入不同已保留，不能把同测试分母解释为这些条件完全相同，也不是八篇方法全部共同覆盖。','',
    '补充固定预测的残基注释/分子图不一致标记敏感性：只在评分时排除已有flags，测试数分别758→717、1129→1035、129→125；主预测文件150份SHA不变，新增拟合/forward均为0。训练仍分别含440、316、117条flag观测，不能称为干净数据重训。标准/NC/PTM/D型各层和两种评分政策的十种子指标均保留。','',
    'ProfAff的原始字符串含biotin-ttds及修饰标记，在本次原样AA20条件下覆盖为0；未私自改用投影骨架。既有ProfAff条件骨架外测仍保留在原模型分支。HER2延伸外测的单位/普通PPI任务边界也保留，当前此分支未新增外部forward。','',
    '## 模型与资源','',
    '官方ESM2-t6-8M，实际7512474参数；fair-esm2.0.0、Torch2.6.0+cu124环境，所有实际计算均在CPU。第6层320维均值，排除BOS/EOS/pad，FP32、eval/inference、requires_grad=false。5159条唯一序列的缓存冻结。最长实际输入2004残基；2048是预声明计算预算，不是API硬上限。','',
    '实际安装发行版的108份Python源文件已逐SHA归档；下载的官方main commit是参考来源，未被当成安装发行版的未知commit。本地独立验证5159条序列/token身份，三条canary向量与正式缓存逐元素一致；60个Ridge候选的真实scaler均值和训练行数与固定训练子集一致，LSQR到1000次迭代上限的模型为0。','',
    f'主权重SHA256：`{extraction["model_sha256"]}`。特征SHA256：`{binding["embedding_sha256"]}`。','',
    f'特征正式worker/PGID{feature_process["pid"]}，耗时{feature_process["elapsed_seconds"]:.2f}s，峰RSS{feature_process["peak_rss_bytes"]/1024**3:.3f}GiB；头训练worker/PGID{head_process["pid"]}，耗时{head_process["elapsed_seconds"]:.2f}s，峰RSS{head_process["peak_rss_bytes"]/1024**3:.3f}GiB。均CPU2、core30/31、GPU0、退出0且整组无残留。','',
    '验证MAE选择两个预声明候选，Ridge scaler仅拟合训练集；所有种子使用同一原始heldout split。原GPU准备v1/v2未执行，独立CPU v3合同及其实际结果保留。最长序列行政断言曾误写为2048而不是清单实际2004，已在任何正式特征开始前修正检查；成功canary没有重跑，失败准备日志保留。','',
    '## 文件入口','',
    '- `coverage-manifest.json` 与 `effective-input-identity-audit.json`：覆盖与split身份。',
    '- `feature-cache-binding.json`：实际CPU缓存绑定；`model-assets/download-receipt.json`：官方来源。',
    '- `runs/plm-simple-v1/heads/`：正式模型、两候选、完整预测与指标。',
    '- `runs/plm-simple-v1/common-prediction-comparison/`：同ID子集与合并只读旧表。',
    '- `runs/plm-simple-v1/residue-flag-sensitivity-v1/`：不重训的注释flag评分敏感性。',
    '- `local-mirror-receipt.json`、`full-artifact-source-manifest.json`：全资产实际SHA。',
    '', '当前仅完成此分支三个主视图；相互作用分类/接触位点的既有五类十种子CPU基准仍在其原分支，新ESM未冒充覆盖这些任务。']
(HERE/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(HERE/'RESULTS.md')
