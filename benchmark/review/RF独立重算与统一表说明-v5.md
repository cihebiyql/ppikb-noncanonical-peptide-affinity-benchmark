RF 独立重算代码已准备，当前只执行合成测试。真实 RF120 审计须等待 NN200 与 RF40 全部选择冻结，再由 root 签发新的授权。

`recompute_RF_v5.py` 独立检查 RF 的120份评分收据和53,160行预测。它不导入生产评分指标、模型代码、sklearn、RDKit，也不加载模型或特征矩阵。数值指标复用已审查并固定 SHA 的独立 NumPy 实现 `recompute_metrics.py`；旧文件保持原样。路径解码只在私有导入实例中适配 Windows/WSL，不改旧源码。

审计涵盖以下内容：

- 40个 RF 选择坐标、原 NN200 门禁、恢复版执行索引与联合屏障的 SHA。
- 六份评分规格的 SHA、训练方案/种子/数据集身份，以及输入、盲预测、金标合并结果的逐记录对应。
- 盲预测文件与零金标读取声明先持久化、合并后预测不变、完整分层元信息保留。顺序证据来自收据、文件 SHA 与已审查控制流，不称为独立操作系统访问轨迹。
- MAE、RMSE、Pearson、Spearman、R²；常数、空组等未定义值保留 null。
- NC_core 主结果、四类 NC 和标准残基对照、608冲突标记排除敏感性、等靶标与等 study_id 宏平均及有效组数。
- 冻结的共同靶标诊断：source26组/NC90/标准124；target45组/NC174/标准203。
- 外部75条分67主集、8敏感性、2参考靶标冷子集；补充13条独立分8非PTM、5标准。2条参考冷不等于家族冷；补充13条是相关靶标上的一个来源研究。

真实 RF 审计 CLI（以下路径参数由 root 在联合冻结后绑定，本文不签发授权）：

```text
python review/recompute_RF_v5.py
  --root-authorization ROOT_RF_AUDIT_AUTH.json
  --joint-barrier JOINT_NN200_RF40.json
  --task-map EXPLICIT_RF120_MAP.json
  --matched-target-manifest review/matched-target-diagnostics-v1/manifest.json
  --output NEW_RF_AUDIT_OUTPUT
```

`EXPLICIT_RF120_MAP.json` 是120项列表，每项为 `{"score_receipt":".../complete.json","holdout_spec":"...RFclassical.json"}`。不递归发现结果，不选择最好种子，不覆盖已有输出。授权对象须绑定该列表、联合屏障、审计脚本和数值 helper 的 SHA，并给出原有绝对截止时间。

审计输出包括 `per-score-audit.json`、逐种子 JSON/CSV、均值与样本 SD 的 JSON/CSV、共同靶标汇总和完整性报告。指标差异会逐项保留并返回失败，供 root 查明；不修改已冻结训练或分割。

`combine_audit_tables_v5.py` 只读取已经生成的指标审计文件，不读取原始金标、预测、模型或矩阵。它将以下三类独立分母放进同一表：

| 类别 | 收据 | 预测行 | 前人论文数 |
|---|---:|---:|---:|
| 五篇 NN 方法 | 600 | 265,800 | 5 |
| 传统 RF 参照 | 120 | 53,160 | 0 |
| 三个确定性参照 | 360 | 159,480 | 0 |

总账1,080份收据和478,440行是重复评分工作量，不是独立生物样本量或论文数量。每条指标表记录的新增论文贡献均为0；五篇论文由五个 NN 方法身份去重计数。

统一表 CLI：

```text
python review/combine_audit_tables_v5.py
  --root-authorization ROOT_COMBINED_TABLE_AUTH.json
  --joint-barrier JOINT_NN200_RF40.json
  --input-map EXPLICIT_METRIC_ASSET_MAP.json
  --output NEW_COMBINED_TABLE_OUTPUT
```

输入表包含 `NN_audit_manifest`、`RF_audit_manifest`、`reference_run_manifest`、`NN_per_score_audit`、`RF_per_score_audit` 五个 `{path,sha256}` 对象，以及明确列出的360项 `reference_score_receipts`。其完整 SHA 由 root 授权绑定。RF 审计和统一表使用不同输入列表，因此应使用分别绑定的授权文件；模板默认均未授权。

统一表保留全部十个种子、null、有效种子数、样本 SD（ddof=1）和宏平均有效组数。旧 NN/确定性参照若只保存全样本宏平均，仍标为 `all_diagnostic`，不改称 NC 宏平均。确定性参照检查各种子预测向量 SHA 相同，定义明确的 SD 应为0；这些种子不是独立生物重复。标准20残基对照也不等于已经确认无末端修饰。

旧 NN600 重算器、v3/v4 历史 manifest 和已冻结科学配置均保持不变。v5 新增代码只做准备与后续独立统计。
