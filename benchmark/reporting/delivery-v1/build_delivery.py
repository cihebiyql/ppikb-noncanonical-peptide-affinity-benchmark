"""Human-readable synthesis of the root-reviewed aggregate; no model/data scoring."""
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
P = HERE.parents[1]
SOURCE = P / 'reporting/final-v1/summary.json'
EXPECTED = 'e5f5d346c5a5ed2de98cdccd8142cbf2e0c0299df02ca7250556cca27c2ba000'
METHODS = ['GraphDTA-GIN','MGraphDTA','DGDTA-CL','DeepNC-GEN','GS-DTA','RF-Morgan2-chiral-AAC-DP']
PANELS = ['source_peptide_dependency_cold','target_reference_homology_cold']


def sha(q):
    return hashlib.sha256(Path(q).read_bytes()).hexdigest()


def link(label, relative):
    return f'[{label}](<{(P/relative).as_posix()}>)'


def main():
    assert sha(SOURCE) == EXPECTED
    rows = json.loads(SOURCE.read_text(encoding='utf-8'))
    assert all(r['completed_seed_count']==10 and not r['missing_seeds'] for r in rows)
    selected = []
    def value(method, panel, regime, cohort='NC_core', dataset='PPIKB-internal', metric='MAE'):
        hits = [r for r in rows if r['method_id']==method and r['panel']==panel and r['regime']==regime
                and r['cohort']==cohort and r['dataset_id']==dataset and r['metric']==metric and r['aggregation']=='row_micro']
        assert len(hits)==1, (method,panel,regime,cohort,dataset,metric,len(hits))
        r=hits[0];selected.append(r)
        return f"{r['mean']:.4f} ± {r['sample_sd']:.4f}" if r['mean'] is not None else '未定义'
    def table(cohort):
        result=['| 方法 | 来源/肽隔离：NC训练 | 来源/肽隔离：标准训练 | 靶标隔离：NC训练 | 靶标隔离：标准训练 |',
                '| --- | ---: | ---: | ---: | ---: |']
        for method in METHODS:
            cells=[value(method,panel,regime,cohort) for panel in PANELS for regime in ['NC_only','standard_only']]
            result.append('| '+method+' | '+' | '.join(cells)+' |')
        return '\n'.join(result)
    nc=table('NC_core');standard=table('standard20_control')
    external=['| 方法（仅NC训练） | 来源/肽隔离模型：PTM67 | 靶标隔离模型：PTM67 | 来源/肽隔离模型：非天然8 | 靶标隔离模型：非天然8 |',
              '| --- | ---: | ---: | ---: | ---: |']
    for method in METHODS:
        cells=[value(method,panel,'NC_only','external_primary67','PTM-external75') for panel in PANELS]
        cells += [value(method,panel,'NC_only','supplement_NC8','IgG-supplement13') for panel in PANELS]
        external.append('| '+method+' | '+' | '.join(cells)+' |')
    text=f'''# PPIKB非标准肽亲和力基准：结果与复现说明

本轮已完成五个已发表架构在统一PPIKB数据上的适配重训，以及一个随机森林基准。全部采用10个训练随机种子，保留全部结果；先建立基准，没有构建创新模型。

实际结果显示：严格隔离后的泛化仍弱。来源与肽依赖隔离测试中，12个可训练组合的NC测试MAE都高于标准肽训练中位数常数参考（1.3178）。靶标参考同源隔离测试中，最低平均MAE为DeepNC-GEN的NC训练模型，1.2978±0.0554 pKd，R²为0.0638±0.0551。这里的最小值是本轮描述结果，不代表显著优于其他模型。

## 1. 数据与本轮任务

任务是由肽的化学结构和蛋白参考序列预测pKd：pKd = −log10(Kd/M)。仅合并同一端点Kd；Ki、IC50保留在原始库中，不混作Kd标签。覆盖所有物种，没有只保留人源。

| 互斥数据层 | 本轮记录数 | 来源/肽隔离测试 | 靶标隔离测试 |
| --- | ---: | ---: | ---: |
| 非天然残基、D型或骨架改变（synthetic_D_backbone） | 723 | 100 | 93 |
| PTM | 1002 | 158 | 190 |
| 同时有非天然改变与PTM | 268 | 39 | 37 |
| 其他NC | 106 | 6 | 12 |
| NC合计 | 2099 | 303 | 332 |
| 标准肽对照 | 7520 | 736 | 1111 |
| 本轮总计 | 9619 | 1039 | 1443 |

“2099”是测量记录数，包含990个立体化学图、415个靶标参考和1212个图—靶标组合。它不等于2099条独立分子，更不等于2099个母体—变体对。其他NC含天然第21/22类残基等情况，不能全部称为人工残基。

PPIKB原始21845条记录完整保留。NC筛选链为4642→Kd2120→输入可用2117→浓度冲突处理2104→最终2099；标准肽链为15754→Kd7903→输入7744→历史规则7742→实体规则7737→浓度处理7582→最终7520。原始数据、排除原因和清洗版本分别保留，筛除不等于从磁盘删除。

本轮没有负例与结合位点金标，因此只交付亲和力回归结果，不把未测记录生成“不结合”标签，也不把预测接触位点视作实验标签。

## 2. 严格划分与训练对照

先对原始记录划分，再训练和评价。10个种子重复模型训练；训练、验证、测试集合保持固定。

| 固定划分 | NC训练/验证/测试 | 标准训练/验证/测试 | 隔离范围 |
| --- | --- | --- | --- |
| source_peptide_dependency_cold | 1548 / 248 / 303 | 5992 / 792 / 736 | 来源别名、立体/非立体化学图、Morgan近邻≥0.8、已观察母体和单编辑关系形成依赖组件 |
| target_reference_homology_cold | 1409 / 358 / 332 | 5324 / 1085 / 1111 | 完全相同/模型前缀相同参考、identity≥30%且双向coverage≥80%，以及≥40aa精确包含关系 |

第一种划分允许靶标重叠；第二种是按已定义序列关系隔离参考蛋白，不自动等于所有蛋白家族均未见。双冷组件最大占93.02%，本轮只作诊断，不用它作主泛化证据。

NC_only仅用该面板的NC训练/验证集；standard_only仅用标准肽训练/验证集。两者都预测同一个完整测试池，再分别报告NC、标准与化学分层。这是两个训练队列对照；两队列样本量、靶标分布不同，不能据差值因果判断“非标准训练更好/无用”。

## 3. 前人模型与调参范围

| 架构 | 论文 | 本轮处理 |
| --- | --- | --- |
| GraphDTA-GIN | [Bioinformatics，2020在线/2021卷](https://doi.org/10.1093/bioinformatics/btaa921) | 作者GIN架构与本轮输入适配 |
| MGraphDTA | [Chemical Science，2022](https://doi.org/10.1039/D1SC05180F) | 作者架构；隔离Batch原位修改影响 |
| DGDTA-CL | [BMC Bioinformatics，2023](https://doi.org/10.1186/s12859-023-05497-5) | 记录GCN不支持参数、实际拼接维度与LSTM批维兼容修补 |
| DeepNC-GEN | [PeerJ，2022](https://doi.org/10.7717/peerj.13163) | 作者GEN架构；修复原super名称错误 |
| GS-DTA | [BMC Genomics，2025](https://doi.org/10.1186/s12864-025-11234-4) | 作者架构与本轮输入适配 |
| RF-Morgan2-chiral-AAC-DP | 额外传统基准，计0篇论文 | 带手性的Morgan指纹＋蛋白AAC/二肽频率＋长度 |

这是五个发表架构在共同数据上的比较，不是五篇原论文主表的完整复现。严格近三年窗口内只有GS-DTA 2025；不宣称已完成五篇近三年肽专用模型或穷尽近五年全部文献。

五份官方仓库的完整文件快照均保留，共129文件；固定commit、ZIP CRC、提取文件SHA与官方Git blob均有核验。快照不包含完整Git历史或作者外部数据文件。来源入口：{link('上游资源清单','resources/upstream-full-v1/DELIVERY-MANIFEST.json')}；{link('方法与数据说明','report-preparation/方法与数据说明.md')}。

NN统一Adam/MSE，学习率0.001与0.0003，weight decay 0、batch32、最多20轮、patience5。仅用验证MAE选学习率与checkpoint；共400个有效候选训练、200个选中模型。实际118次选择0.001、82次选择0.0003。

随机森林200棵树、max_features=sqrt、bootstrap、深度不限；min_samples_leaf在2/5中用验证集选择，共80个候选、40个选中。17次选择2，23次选择5。所有可训练方法使用seed0–9。

总计480个有效候选训练。另保留两次技术中断与同配置恢复记录，不增加科学格数。400份有效NN完整epoch日志已核验：390份按patience5提前停止，10份达到20轮上限；轮数最少6、平均9.8325、最多20。它说明实际预算执行情况，不证明模型已收敛或充分调优。

调参证据与逐候选日志诊断：{link('超参数与训练元信息','reporting/training-metadata-v1/超参数与训练元信息.md')}；{link('预算诊断说明','reporting/training-logs-v1/预算诊断说明.md')}。原metric-only机器报告未填写可选训练metadata_map，完整训练证据在这两份独立报告中。

## 4. 同一NC测试集：10种子MAE

以下为pKd的MAE均值±样本标准差，越低越好。左两列共享NC测试303条，右两列共享NC测试332条。

{nc}

标准肽训练中位数常数参考：来源/肽隔离MAE1.3178，靶标隔离1.7572。常数模型的相关系数无法定义；保留null，不改成0。三个确定性参考均实际按10个种子调用并保存，数值相同、SD为0，不代表十次独立拟合。

## 5. 标准肽测试对照：10种子MAE

左两列共享标准测试736条，右两列共享标准测试1111条；不可与上一节的NC测试混成总体分数。

{standard}

## 6. 独立外部数据

外部样本在预测前接受并冻结。PTM共75条，67条为主测试，8条条件性敏感性样本；2条参考靶标冷样本是67条中的子集，不能把67+8+2写成77条。它们相对整个PPIKB来源和已声明化学实体隔离，但大多数靶标已有相关数据。

另有13条[2025年IgG研究](https://doi.org/10.1248/cpb.c25-00637)补充数据：8条非天然/D型/骨架改变，5条标准肽。它属于一个靶标相关研究；实际实验对象为完整IgG，模型使用449aa重链参考视图，不能当作全构建体或新蛋白家族验证。ProfAff52仅收集资源，因实体/连接臂/构建体信息不足，未纳入正式评分。

以下固定展示NC训练模型的外部MAE；两个面板训练出的模型分别评价，不合并。标准训练对照、PTM8与参考靶标冷2的全部五项指标保存在完整机器报告。

{chr(10).join(external)}

PTM与非天然改变是两种不同外部挑战，67与8也不能视作等量独立生物体系。外部结果不支持普适跨蛋白家族结论。

## 7. 分层、敏感性与指标解释

全部报告包含MAE、RMSE、Pearson、Spearman和R²；均保留逐种子值、10种子均值、样本SD、完成种子数、可定义种子数与真实分母。SD只反映训练随机性，不是生物重复置信区间。多个随机种子不增加独立靶标或来源数。

NC四类互斥分层分别评价；同时报告标准对照、按靶标/来源等权宏平均，以及冻结的共同靶标诊断：第一面板NC90/标准124、第二面板NC174/标准203。总体micro与宏平均分开保留，避免大系列主导结论。

同一立体化学图的NC/标准标注冲突涉及608条记录（357NC、251标准；60图）。剔除这些测试行的敏感性为NC274/261与标准724/1067；它复用同一批预测，没有重新清洗训练集或新增训练。因此不能称为完全去冲突后的重训证据。

五个NN的原图特征不编码立体化学；输入SMILES含手性不意味着网络特征能识别手性差异。MGraph核心还忽略所构造的edge属性。RF使用手性Morgan指纹。这是本轮模型的表示边界，不把它写成已验证的改进机制。

蛋白输入是参考序列而非已逐条认证实验构建体；构建体认证数为0。MGraph使用最多1200aa前缀，其他模型1000aa；不作肽原子数量截断。上述输入限制与实验条件差异仍会影响可解释性。

## 8. 独立核验与原始结果入口

200个NN与40个RF选中模型共完成720份评分、318960条逐样本预测。另三个确定性规则有360份评分、159480条预测记录。合计1080份评分、478440条预测记录是计算产物数量，不是生物样本数。

NN600与RF120由独立数值实现重新核验，预测—真实值连接与全部预定指标无差异。后续化学分层和宏平均扩展复用已有预测，不新增拟合、预测或测试调参。

原审计v1在RF补充13条缺少辅助子组列时停止，失败证据完整保留。修订版只在私有审计行中按原冻结ID补齐缺列；已有错误值仍拒绝，原输入、预测、标签和分组未修改。15项修复机械测试、28项恢复驱动器测试和独立源码审核通过后，RF120独立复算成功。原NN600审计经SHA绑定复用，未反复重算或选择结果。

- {link('完整指标报告','reporting/final-v1/完整报告.md')}
- {link('全部11540组聚合指标CSV','reporting/final-v1/summary.csv')}
- {link('全部逐种子指标CSV','reporting/final-v1/metrics-per-seed.csv')}
- {link('NC主结果CSV','reporting/final-v1/main-NC.csv')}
- {link('实际NC结果图PNG','reporting/figures-v1/actual-v1/figures/png/fig_01_nc_mae.png')}
- {link('原始训练候选与checkpoint','formal-runs-gpu-v4/fits')}
- {link('独立审计完整READY','review/postscore-driver-v2/runs/actual-v2/POSTSCORE-AUDIT-READY.json')}
- [本地交互报告](http://127.0.0.1:2647/)

本说明由已审核聚合指标及现有证据派生；原机器报告、原数据、逐条预测和所有冻结代码保留不动。
'''
    q=HERE/'基准结果与复现说明.md'
    with q.open('x',encoding='utf-8') as h:h.write(text)
    with (HERE/'selected-aggregate-rows.json').open('x',encoding='utf-8') as h:json.dump(selected,h,ensure_ascii=False,indent=2,allow_nan=False)
    manifest=dict(generated_at=datetime.now(timezone.utc).isoformat(),source_summary=dict(path=str(SOURCE),sha256=EXPECTED),
        root_review=dict(path=str(P/'review/root-final-summary-review-v1.json'),sha256=sha(P/'review/root-final-summary-review-v1.json')),
        artifacts={n:sha(HERE/n) for n in ['基准结果与复现说明.md','selected-aggregate-rows.json','build_delivery.py']},
        original_scientific_artifacts_modified=False,metrics_recomputed=False,raw_models_gold_predictions_read=False)
    with (HERE/'DELIVERY-MANIFEST.json').open('x',encoding='utf-8') as h:json.dump(manifest,h,ensure_ascii=False,indent=2)
    print(json.dumps(manifest,ensure_ascii=False))


if __name__=='__main__':main()
