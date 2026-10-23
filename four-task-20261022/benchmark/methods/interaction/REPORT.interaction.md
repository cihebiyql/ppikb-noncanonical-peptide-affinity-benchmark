# PepInter与SWING：本轮共同数据复现记录

更新时间：2026-10-23T02:02:01.603444+00:00。数值为随机种子间均值 ± 样本标准差；同一固定测试分区用于全部种子。

## 已完成的训练与外部评价

| 面板 | 完整种子 | 每种子测试量 | MAE | RMSE | Pearson | 状态 |
|---|---:|---:|---:|---:|---:|---|
| PepInter-standard2919-source | 10 | 288 | 1.57775 ± 0.03429 | 1.89896 ± 0.02059 | -0.01364 ± 0.02258 | completed_independently_audited |
| PepInter-NC-backbone-source | 10 | 683 | 1.45615 ± 0.00711 | 1.79811 ± 0.01000 | 0.10778 ± 0.01568 | completed_independently_audited |
| PepInter-standard2919-source-ProfAff162 | 10 | 162 | 0.95236 ± 0.09272 | 1.08982 ± 0.10212 | -0.03519 ± 0.04158 | completed_independently_audited |
| PepInter-NC-backbone6336-source-ProfAff162 | 10 | 162 | 1.01970 ± 0.15303 | 1.15150 ± 0.15826 | -0.20007 ± 0.03792 | completed_independently_audited |
| PepInter-standard2919-target | 10 | 425 | 1.56690 ± 0.01543 | 1.99193 ± 0.01164 | -0.07237 ± 0.02710 | completed_independently_audited |
| PepInter-NC-backbone-target | 10 | 946 | 1.64273 ± 0.01252 | 2.03629 ± 0.00781 | 0.10194 ± 0.02407 | completed_independently_audited |
| PepInter-standard2919-target-ProfAff162 | 10 | 162 | 0.86456 ± 0.08244 | 0.99279 ± 0.08423 | 0.01621 ± 0.04434 | completed_independently_audited |
| PepInter-NC-backbone6336-target-ProfAff162 | 10 | 162 | 1.09113 ± 0.10986 | 1.22030 ± 0.11061 | -0.07712 ± 0.07283 | completed_independently_audited |
| SWING-author-grammar-Doc2Vec-XGBClassifier-inductive | 9 | 2362 | — | — | — | partial |

SWING分类另外报告AUROC、AUPRC、F1、MCC、平衡准确率与Brier，见逐种子独立审计。它的负标签包括作者构造负例。

模型间排名须使用完全相同测试行与原标签；native6336、旧缓存2919与全量9116的测试分母不同，表中指标用于记录各自预先声明的覆盖范围。`common-comparison-cohorts/`提供683/946固定测试ID，可对其他基线既有预测作同一交集重算，无需新增训练或forward。

## NC/PTM与标准肽的输入覆盖

PPIKB冻结主视图共9116条观测。PepInter使用原样20AA序列、target≤960及peptide≤64，不作替换、去符号或截断，得到6336条：5931标准对照、298 PTM、27 synthetic/D/backbone、54 synthetic+PTM、26 other NC。另1447条字符不受词表支持、1333条超原生长度策略，仍完整保留在全量数据中。

本组件采用化学骨架信息消融：保留每条SMILES与化学类别用于评价，但编码器仅看原样序列。完整非天然化学识别的对照来自其他化学图基线。源冷测试60条NC、623条标准；靶冷测试88条NC、858条标准。

| 面板/分层 | 测试量 | MAE | RMSE | Pearson |
|---|---:|---:|---:|---:|
| PepInter-NC-backbone-source/PTM | 53 | 1.11736 ± 0.03692 | 1.35472 ± 0.04344 | 0.03601 ± 0.03962 |
| PepInter-NC-backbone-source/synthetic_and_PTM | 1 | 2.12729 ± 0.16070 | 2.12729 ± 0.16070 | — |
| PepInter-NC-backbone-source/other_NC | 3 | 1.68805 ± 0.09771 | 1.80551 ± 0.09088 | — |
| PepInter-NC-backbone-source/synthetic_D_backbone | 3 | 0.47063 ± 0.06603 | 0.55417 ± 0.07930 | 0.29917 ± 0.18244 |
| PepInter-NC-backbone-source/standard20_control | 623 | 1.48752 ± 0.00551 | 1.83407 ± 0.00892 | 0.11330 ± 0.01697 |
| PepInter-NC-backbone-target/PTM | 59 | 1.35758 ± 0.09933 | 1.64976 ± 0.08830 | -0.00184 ± 0.08705 |
| PepInter-NC-backbone-target/synthetic_and_PTM | 14 | 1.42099 ± 0.08357 | 1.57429 ± 0.07445 | 0.04988 ± 0.24834 |
| PepInter-NC-backbone-target/synthetic_D_backbone | 12 | 1.07084 ± 0.05421 | 1.31927 ± 0.07574 | 0.46705 ± 0.11315 |
| PepInter-NC-backbone-target/other_NC | 3 | 1.53193 ± 0.14689 | 1.66101 ± 0.13524 | — |
| PepInter-NC-backbone-target/standard20_control | 858 | 1.67435 ± 0.01376 | 2.07592 ± 0.00911 | 0.09015 ± 0.01796 |

## 方法与参数冻结

SWING保留作者三项交互语言函数，Grantham polarity、k=7、padding=9；Doc2Vec为72维、dm=0、window=7、min_count=1、alpha=0.42、训练16 epochs、推断16 epochs、workers=1。词表与Doc2Vec只在train拟合，validation/test用infer_vector。XGBClassifier两候选depth=1/6、200棵树、learning_rate=0.1；按验证log-loss选优后评价test。作者原cross_pred用全体序列拟合表征，本轮严格inductive划分为明确适配。

PepInter载入官方监督回归检查点提取2304维原生池化向量，再按seed独立初始化原作者2304→4608→1 RegressionHead。AdamW、MSE、FP32、batch128、weight_decay0.01、20 epochs、patience5、梯度裁剪1；学习率1e-5与1e-4按验证MAE选优。GPU资源修订保留这些科学配置，禁用AMP/TF32并记录每seed后端。

## 外部数据与误差解释

ProfAff162为112条带标签标准骨架观测加50条PTM观测，输入为作者domain/backbone视图，完整融合构建体和化学状态的表示有差异。已发布PepAff训练对的exact序列交集为0；同源和骨干预训练暴露仍需保留条件性标记。它承担条件性外部测量验证。

42条PTM效应由68条共享绝对观测构成。逐pair核验父/变体ID、target及实际输入hash后，从既有绝对预测作差。相同序列骨架使预测差值为0；该结果用于揭示序列编码信息损失。它不增加独立实验样本或新训练。

原headworker以float32标签计算指标，CSV保留原float64标签。对目标2919等面板，近似标签在float32下合并造成Spearman小幅差异；独立审计分别重现两种精度，以CSV精度的重算值作为报告指标，不覆盖旧指标或放宽容差。

## 保存与未完成项

所有两候选权重、训练历史、验证预测、选择记录、测试预测和原始日志均保留。CPU完整/活跃seed与GPU未来seed通过冻结NAS独占claim区分，避免同seed重复正式计数。source旧CPU进程在完成seed2后因预声明路由哨兵退出1；target旧批次在seed4candidate1达到内部上限，candidate0原件保留并只续跑未保存candidate1。

SWING分类有效结果为严格审计的seeds1–9。原Node1 seed0实际已保存16epochs表征、两个分类器和验证选优，但test推断超时。尝试重载后的10条历史validation最大概率偏差0.22843，超预先声明1e-7门槛，因此两个续跑分片均在test之前停止。安装包源码表明infer初始向量还依赖Python内置hash，原启动spec未记录PYTHONHASHSEED，原进程已消失；这一原状态恢复限制完整保留，不能补作第10个有效成绩。新Node23恢复seed0于01:23:43达到原7200s整组上限、exit−15、worker已消失，最终只到epoch7，所有日志原样保留。

SWING亲和力回归适配准备完成但尚未执行，PepInter当前为冻结骨干组件。两方法的接触位点评价需要原生监督输出与真实接触标签。

| 本地归档 | 已验证文件/预期 | 状态 |
|---|---:|---|
| pepinter-cached-target-complete-small.transfer.json | 110/110 | succeeded |
| pepinter-cached-target20-headweights.transfer.json | 20/20 | succeeded |
| pepinter-nc-source-complete-small.transfer.json | 122/122 | succeeded |
| pepinter-nc-source-profaff162-complete.transfer.json | 50/50 | succeeded |
| pepinter-nc-source20-headweights.transfer.json | 20/20 | succeeded |
| pepinter-nc-target-complete-small.transfer.json | 139/139 | succeeded |
| pepinter-nc-target-profaff162-complete.transfer.json | 46/46 | succeeded |
| pepinter-nc-target21-preserved-headweights.transfer.json | 21/21 | succeeded |
| pepinter-source20-headweights.transfer.json | 20/20 | succeeded |
| pepinter-target-profaff162-complete.transfer.json | 46/46 | succeeded |
| swing-final-failed-attempts-preserved.transfer.json | 48/48 | succeeded |
| swing-original0-completed-training-retained.transfer.json | 19/19 | succeeded |
| swing-seeds1-9-complete-representations.transfer.json | 27/27 | succeeded |

官方7GB检查点本地下载状态：succeeded。只有stream SHA、字节数和远端exit全部通过才标为本地完整。归档可以在科学截止后继续，归档不产生新fit/pred。

证据入口：`status.interaction.v3.json`、`review/`、`result-records/standard-validation-index.json`、`nc-backbone-ablation/manifest.json`、`nc-backbone-ablation/merged-feature-manifest.json`、`archives/*.transfer.json`。
