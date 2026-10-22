本次追加预注册只补指标范围，不改变训练、数据划分、预测或选择。当前真实执行为0；分组ID已经从原始测试输入的无标签视图冻结。

内部360个诊断case为 NN200＋RF40＋确定性参照120。它们复用446,760行既有预测，不计新评分、预测样本或论文；原NN600/RF120/参照360、478,440行总账及五篇论文计数不变。NN/ref原320个case规则不变；RF40只补四NC层宏，并精确核对已有NC/标准clean和NC/标准宏。

| 面板 | NC主集 | NC排冲突 | 标准对照 | 标准排冲突 |
|---|---:|---:|---:|---:|
| source_peptide_dependency_cold | 303 | 274 | 736 | 724 |
| target_reference_homology_cold | 332 | 261 | 1111 | 1067 |

冻结目录是 `nc-scope-frozen-groups-v6/`。组定义使用原冻结输入中的布尔 `NC_core`、`evaluation_stratum` 和原独立helper的冲突判定；清洁集合为既有测试组与非冲突记录的交集，没有重新划分。每个面板的输入路径/SHA、组文件/SHA和完整ID均保留。原始来源标识缺失有source156行、target161行（全测试池口径），不填补；按cohort重新报告缺失记录ID、计数和非缺失机器来源别名。

补充微指标是 NC_core_exclude_discordant_sensitivity 和 standard_exclude_discordant_sensitivity 的MAE、RMSE、Pearson、Spearman、R²；从各自完整行集重新计算，不平均分层指标。补充宏平均分别覆盖 NC_core、四类NC和standard，按完整target_reference_sequence_sha和study_id等权；保留每组指标、观测数、有效组数、缺失组数及source_refs。study_id只是机器来源别名，不称独立实验。面板和训练方案分别保留，全部种子0–9保存；SD为训练重复的样本SD。

执行代码是 `nc_scope_extension_v6.py audit`。真实执行需要新的 root_NC_scope_extension_authorized 授权，同时复用冻结v5的严格联合门禁，因此授权还需 root_RF_independent_audit_authorized、v5 script_sha256、helper/task-map/joint SHA等字段。新字段另绑定extension_script_sha256和group_manifest_sha256。NN600/RF120独立审计与参照360都须先完成。所有期限使用原有绝对截止时间，不延01:45。

```text
python review/nc_scope_extension_v6.py audit
  --root-authorization ROOT_V6_EXTENSION_AUTH.json
  --joint-barrier JOINT_NN200_RF40.json
  --case-map EXPLICIT_INTERNAL360_CASE_MAP.json
  --group-manifest review/nc-scope-frozen-groups-v6/manifest.json
  --output NEW_V6_EXTENSION_OUTPUT
```

case map明确列360项。每项有category、source_receipt、predictions、input_metadata，后面三项均为 `{path,sha256}`。NN/RF还必须明确绑定blind_predictions与blind_proof；确定性参照原脚本没有单独盲文件，其blind_predictions必须为空或省略，改以原receipt的预测向量SHA验证，不能制造盲证据。input_metadata必须原样采用分组manifest中对应面板的对象。原NN/RF收据必须分别在已完成独立审计的per-score记录中；原预测文件SHA和ID须对应，没有新gold读取、模型调用或训练。授权需同时绑定base_NN_per_score_audit与base_RF_per_score_audit。

新输出为360个不可变case sidecar、25,200条canonical长指标、十种子汇总与extension-manifest。missing_source_refs等详细元信息完整保存在sidecar。canonical长表只使用旧v5列，不添加reporting v1白名单之外的列。RF已有30个key/case共1,200项须精确相等后去重，新合并长表增加24,000个指标key；这些均不是新的评分case。

`merge_metric_extension_v6.py` 仅合并已审计的v5指标表与v6新增指标，不读原始预测。它需要新的root_NC_metric_merge_authorized和冻结v5联合授权字段，另绑定merge_script_sha256。输入map为 `base_v5_manifest` 和 `v6_extension_manifest` 两个 `{path,sha256}` 对象。旧base行逐值保持；重复语义key的value/n/n_unit/defined_group_count必须完全一致才去重，否则失败。v6元信息明确自己的schema_version6、generated_by及“旧v5＋v6补充”来源，不能冒称旧v5工具新增了指标。

```text
python review/merge_metric_extension_v6.py
  --root-authorization ROOT_V6_MERGE_AUTH.json
  --joint-barrier JOINT_NN200_RF40.json
  --input-map BASE_V5_AND_V6_EXTENSION_MAP.json
  --output NEW_V6_UNIFIED_OUTPUT
```

reporting v1的源检查结论：其通用完成状态 `complete_postjoint_metric_table_assembly` 可真实用于完成后的v6合并；它没有锁定schema版本，但第25/53行有严格列白名单。因此v6保持canonical列，丰富元信息另存sidecar，原reporting四文件无需修改。合成测试验证新NCclean和宏cohort可通过原validate_rows，而直接塞missing_source_refs列会被拒绝。新v6 manifest仍显式公开生成器和版本，不隐去扩展来源。

RF增加的是对既有40个内部预测文件的指标审计case，不增加fit、score或预测。已有RF NC/标准clean及NC/标准targetref/study宏与v6使用相同独立helper和过滤语义；每个RF case都必须与其v5独立审计值完全一致。RF v5没有四类NC各自的宏，本次在首次真实holdout前预注册这部分补充，从相同已存预测计算，不冒称原v5已提供。
