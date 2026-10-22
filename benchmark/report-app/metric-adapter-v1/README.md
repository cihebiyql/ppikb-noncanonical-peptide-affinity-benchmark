# 已审阅聚合指标 → 旧应用格式

此helper只转换聚合格式。准备阶段仅用了静态FIELD-MAPPING与合成行，**真实summary／金标／逐记录预测／模型／标签读取均为0**；app、旧importer和冻结reporting均未修改。

## 实际CLI

Root在完整指标独立核算、联合选择屏障及原summary审阅通过后，填写`authorization.template.json`的新副本；模板所有授权flag默认false，不能执行。

```powershell
python adapter.py --authorization <显式root授权JSON> --summary <授权绑定的ten-seed-summary.json> --output <metric-adapter-v1下全新输出目录>
```

授权须有true的`root_metric_adapter_authorized / reviewed / independently_recomputed / all_required_selections_frozen`，以及本adapter代码SHA、原summary路径/SHA、source-review路径/SHA、联合屏障路径/SHA。可提供有时区的`expires_at`；过期会拒绝。先验证root授权及review/barrier文件哈希，再读取唯一绑定的summary。没有目录扫描、原始评分逻辑或metadata引用跟随；联合屏障的完整性由root的权威源审阅负责，此helper只核验绑定与哈希。

输入只接受JSON聚合数组，或恰有一个`rows`／`summary`数组的容器。最大100MiB、100,000行。输出目录必须位于本helper目录内且之前不存在；不会覆盖旧结果或写入app。

## 默认保留什么

- 仅`row_micro`、`matched_row_micro`进入旧格式，`n_unit`必须严格为`observation_rows`。
- 每组`n_by_seed`必须覆盖所有完成seed且每个n相同，才能输出单一n；变化时直接拒绝，不取均值、最小值或第一项。
- mean原值→mean，sample_sd原值→sd，不重算、不四舍五入；null保持null。
- **defined_seed_count→seed_count**，不能换成completed_seed_count。10次训练全部完成但相关系数全未定义时，旧表seed_count为0；这表示0个可定义指标值，并非没有训练。完整完成数和null信息保留在mapping-trace及原summary。
- 计数本身若为null，旧importer无法表示，明确拒绝，不猜为0/10。缺少两项可定义值时SD保持null。
- 面板、训练regime、三类方法账目都保留。evaluation_set_id为逐段URL编码后的`category|dataset_id|原cohort|aggregation`，不能跨内部测试、PTM外测75、IgG补13或敏感性scope合并。

## 化学类别映射

完整映射在`cohort-mapping.json`。主规则：

| 原cohort | chemistry_id |
| --- | --- |
| NC_core | NC_all |
| 四个NC层 | 原类名 |
| standard／standard20_control | standard20_control |
| all | all |
| exclude_discordant_sensitivity | all，保持整体敏感性，不伪造NC整体 |
| 明确的NC_core_exclude_discordant_sensitivity | NC_all，仅在源真的给出该行时 |
| exclude_discordant:已知层 | 对应层，原clean名称保留在evaluation_set_id |
| external_primary67／conditional8／referencecold2 | PTM，三者保持独立evaluation_set_id |
| supplement_NC8／supplement_standard5 | synthetic_D_backbone／standard20_control |
| NC_matched／standard_matched | NC_all／standard20_control；仅matched_row_micro |

默认核对303/332主NC、736/1111标准、1039/1443整体、67/8/2外测、8/5补集及90/124、174/203 matched观测分母。没有的NC整体clean指标不从四个strata的mean重建。

## Macro和未知scope

已知macro（target、target-reference、study等权及matched两类等权）不进入旧表。`excluded-macros.json`保留每条原始macro聚合行、source_index和排除原因，原完整summary SHA也保留；完整报告继续拥有全部macro。不会把group数填进旧表样本n。

`all_diagnostic`只以原名保留在macro排除清单，不转成NC macro。未知cohort或aggregation默认报错。确需排除时，root授权提供`explicit_exclusions`：每条至少绑定`category,dataset_id,cohort,aggregation,reason`，还可收紧panel/method/regime/metric；转换产物逐条留存，不静默丢弃。

## 输出及后续边界

- `app-metrics.json`／CSV：兼容旧importer的十字段。
- `mapping-trace.json`：原坐标、完成／可定义seed、n_by_seed和映射关系。
- `excluded-macros.json`／`explicit-exclusions.json`：全部排除原行及理由。
- `conversion-provenance.json`／`artifact-manifest.json`：原summary、root review、联合屏障、代码和输出哈希。
- `import-review-json.template.json`／CSV模板：已填转换结果SHA，**reviewed仍为false**。Root完成格式复核后再在新副本显式签发；helper不自签审阅，也不调用旧importer或builder。

旧UI里的seed_count应解释为“指标可定义的种子数”。实际完成数、原始null和所有macro仍以完整报告为准。此目录不修改任何UI。

## 合成验证

运行`python -m unittest test_adapter -v`。测试覆盖10seed、null/恒定相关、可定义seed不足、原SD、2/8/67、补8/5、all不冒充NC、clean不重建、matched观察行、macro群组数隔离、未知scope、n跨seed变化拒绝、NaN拒绝、未授权不读源、输出模板待root审阅。所有数值都是隔离测试fixture，不会进入应用。
