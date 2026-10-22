# 指标字段映射与分母

报告输入来自独立审计组表器 `review/combine_audit_tables_v5.py`。只打开 root 显式绑定的 `unified-table-manifest.json` 与同目录固定文件 `unified-per-seed-metrics.json`；没有目录扫描和原始评分读入逻辑。

| 输入字段 | 报告处理 |
| --- | --- |
| category | five_prior_paper_NN / auxiliary_handcrafted_RF / three_deterministic_references 三类分账 |
| dataset_id | PPIKB-internal / PTM-external75 / IgG-supplement13 |
| raw_dataset_id | source_test / target_test / external75 / supplement13；与panel一致性检查 |
| panel | 两面板单独保留，禁止跨panel池化 |
| method_id / regime / seed | 原身份及 NC_only / standard_only；seed0–9逐项保留 |
| cohort / aggregation | 原名保留，不能由all重命名为NC_core |
| metric / value | 五指标，null原值保留，非有限数拒绝 |
| n / n_unit | 各seed观测数或group数，主NC固定303／332 |
| defined_group_count | 原样保留，macro相关等可定义组数 |

summary 每组按 category/dataset_id/panel/method_id/regime/cohort/aggregation/metric 聚合。输出 mean、sample_sd、completed_seed_count、defined_seed_count、missing_seeds、values_by_seed、n_by_seed、defined_group_count_by_seed；不足两项可定义值的SD为null。CSV用字面量null，JSON用真正null。

主表仅 `PPIKB-internal / NC_core / row_micro`。`all`1039／1443为诊断分母，不能替代303／332。标准对照为736／1111。化学四层为 synthetic_D_backbone / PTM / synthetic_and_PTM / other_NC。608原注释冲突排除敏感性仅显示审计提供的原字段；缺少NC整体敏感性时不从分层指标重建。

外测75：external_primary67 / external_conditional_sensitivity8 / external_reference_target_cold2（2包含于67）。补充13：supplement_NC8 / supplement_standard5。补充13保留独立dataset。matched：NC_matched / standard_matched，matched_row_micro、matched_equal_target_reference、matched_equal_study_id。来源＋肽冷为26参考靶标、NC90/标准124；参考同源冷45、NC174/标准203。

macro的aggregation：equal_weight_target_id、equal_weight_target_reference_sequence_sha、equal_weight_study_id。旧NN/reference仅all_diagnostic就保留此名；不会推断NC专属macro。所有实际可用macro保存完整summary及逐seed表。

## 训练元信息（未来另行授权）

授权可绑定 `training_metadata_map: {path,sha256}`。map数组元素 `{kind,path,sha256}`，kind仅 NN_candidate / NN_selection / NN_interrupted / RF_candidate / RF_selection，文件名仅 complete.json / selection.json / failed.json。此入口不会跟随metadata中的checkpoint、validation预测或数据路径。

NN候选 complete的best_epoch、hyperparameters.learning_rate、elapsed_seconds直接保留。selection中的candidate_index及candidate_metadata可说明实际LR选择。RF有效参数可读candidate_metadata.effective_parameters。现NN complete不含最后epoch，因此 completed_epoch_count / early_stopped / epochs_at_cap 保留null；不能从best_epoch推断实际earlystop或epochcap。若需准确数量，应由独立运行审计产生这些元字段再冻结新版report schema。候选elapsed_seconds之和是进程累计秒，不能当并行墙钟。

## 覆盖和缺失

完整组表清单必须1080次评分／478440行且三类的all指标坐标齐全。主NC及预定外部分组另按坐标核验。可显式接受partial审计清单，此时报告实际完整五指标评分组数及缺失数，缺失seed不补0。无任何真实指标的template显示“待真实审计结果”。

README及完整报告保留原训练/评分资产入口；根运行清单负责具体路径映射。报告不改原日志、预测、检查点及冻结方法。
