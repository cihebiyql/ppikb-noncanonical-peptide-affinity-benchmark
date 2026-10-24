# 化学表示共同基准：ringfix v2独立验收

三种表示在完全相同的497训练、500验证、656测试记录上训练与评分。CLM2 Hybrid和MLM是同一论文的两种权重变体；每种表示配合5族普通预测头、10个种子、2个验证候选。150个选定模型、300次候选拟合全部验收完成。

新版测试集上Hybrid+ExtraTrees与Morgan+ExtraTrees的MAE几乎持平；所有总体R²为负，跨背景泛化能力仍然有限。

## 数据与表示

- 使用完整SMILES，肽化学表示拼接同一冻结ESM320蛋白表示。
- ringfix v2修复相邻环闭合数字的分词，保留百分号环标记；1238个唯一SMILES全部生成特征。适配器是明确记录的输入处理修改，官方权重、词表和SMILES保持原字节。
- 新版656测试与旧版502测试覆盖范围不同，两个版本的MAE不能直接当作模型改进量。
- source面板在严格闭包防火墙后为0训练，继续blocked。

{
  "fine_train": {
    "rows": 497,
    "dependency_groups": 94,
    "target_sequences": 113,
    "studies": 115,
    "chemical_strata": {
      "PTM": 34,
      "standard20_control": 440,
      "synthetic_D_backbone": 10,
      "synthetic_and_PTM": 13
    },
    "discordance_rows": 3
  },
  "validation": {
    "rows": 500,
    "dependency_groups": 122,
    "target_sequences": 145,
    "studies": 148,
    "chemical_strata": {
      "PTM": 28,
      "other_NC": 1,
      "standard20_control": 430,
      "synthetic_D_backbone": 27,
      "synthetic_and_PTM": 14
    },
    "discordance_rows": 12
  },
  "test": {
    "rows": 656,
    "dependency_groups": 146,
    "target_sequences": 171,
    "studies": 204,
    "chemical_strata": {
      "PTM": 35,
      "other_NC": 5,
      "standard20_control": 572,
      "synthetic_D_backbone": 26,
      "synthetic_and_PTM": 18
    },
    "discordance_rows": 21
  }
}

## 总体pKd结果（均值±样本SD）

|表示|预测头|MAE±SD|RMSE|Spearman|R²|
|---|---|---:|---:|---:|---:|
|hybrid|constant|1.6648±0.0000|2.0450|NA|-0.1159|
|hybrid|extra_trees|1.6150±0.0109|1.9971|0.1759|-0.0642|
|hybrid|hist_gradient_boosting|1.6636±0.0000|2.0786|0.1779|-0.1529|
|hybrid|random_forest|1.6181±0.0126|2.0035|0.1748|-0.0711|
|hybrid|ridge|2.2315±0.0000|2.8379|0.1680|-1.1490|
|mlm|constant|1.6648±0.0000|2.0450|NA|-0.1159|
|mlm|extra_trees|1.6445±0.0116|2.0279|0.0835|-0.0974|
|mlm|hist_gradient_boosting|1.6901±0.0000|2.1176|0.0675|-0.1965|
|mlm|random_forest|1.6416±0.0171|2.0234|0.1039|-0.0926|
|mlm|ridge|2.3065±0.0000|2.8737|0.1285|-1.2036|
|morgan|constant|1.6648±0.0000|2.0450|NA|-0.1159|
|morgan|extra_trees|1.6158±0.0104|2.0040|0.1129|-0.0716|
|morgan|hist_gradient_boosting|1.6040±0.0000|1.9853|0.1918|-0.0517|
|morgan|random_forest|1.6243±0.0146|2.0015|0.1556|-0.0690|
|morgan|ridge|2.5840±0.0000|3.2340|-0.0091|-1.7909|

## ExtraTrees化学分层与标注冲突敏感性

|表示|分层|n|MAE±SD|Spearman|
|---|---|---:|---:|---:|
|hybrid|all|656|1.6150±0.0109|0.1759|
|hybrid|standard20_control|572|1.6223±0.0094|0.1540|
|hybrid|synthetic_D_backbone|26|0.9723±0.0456|0.3085|
|hybrid|PTM|35|1.3603±0.0432|0.2452|
|hybrid|synthetic_and_PTM|18|2.7298±0.0265|0.0973|
|hybrid|other_NC|5|1.8883±0.0867|0.5774|
|hybrid|NC_all|84|1.5651±0.0308|0.3529|
|hybrid|PTM_bearing|53|1.8254±0.0328|0.1610|
|hybrid|exclude_discordance|635|1.6018±0.0103|0.1693|
|hybrid|flagged_discordance|21|2.0154±0.0919|-0.1905|
|mlm|all|656|1.6445±0.0116|0.0835|
|mlm|standard20_control|572|1.6487±0.0131|0.0550|
|mlm|synthetic_D_backbone|26|1.1630±0.0646|0.0392|
|mlm|PTM|35|1.3561±0.0699|0.4659|
|mlm|synthetic_and_PTM|18|2.7194±0.0494|0.3100|
|mlm|other_NC|5|1.8130±0.0677|0.5774|
|mlm|NC_all|84|1.6157±0.0540|0.3304|
|mlm|PTM_bearing|53|1.8191±0.0588|0.3566|
|mlm|exclude_discordance|635|1.6356±0.0121|0.0623|
|mlm|flagged_discordance|21|1.9118±0.1316|-0.0496|
|morgan|all|656|1.6158±0.0104|0.1129|
|morgan|standard20_control|572|1.6270±0.0099|0.0771|
|morgan|synthetic_D_backbone|26|1.1352±0.0597|-0.2691|
|morgan|PTM|35|1.2622±0.0479|0.0119|
|morgan|synthetic_and_PTM|18|2.6097±0.0371|0.6267|
|morgan|other_NC|5|1.7308±0.0906|0.5774|
|morgan|NC_all|84|1.5395±0.0352|0.4047|
|morgan|PTM_bearing|53|1.7199±0.0365|0.3098|
|morgan|exclude_discordance|635|1.6065±0.0095|0.0945|
|morgan|flagged_discordance|21|1.8976±0.1286|0.3266|

## 解释与复核

- 每族内部候选仅由验证MAE选择；表中跨族测试排序属于描述性结果，后续不能据此再次调整模型。
- 固定划分的10种子衡量训练随机性；确定性的预测头可出现SD=0。常数预测的相关性记NA并保留0个有效种子。
- 化学类别按照冻结标签分别评价；NC、PTM、混合层的有限样本量直接列出。discordance排除只重评分固定预测，原训练样本保留。
- 同头同种子MAE差值为描述统计；种子编号相同不代表不同表征共享相同随机轨迹。
- 305,937项冻结审计与295,200项独立元数据检查通过，本机再核1,800个均值/样本SD。审计新增fit、预测、模型载入均为0。
- 组宏指标对每个依赖组等权；未定义的组内相关性保留NA，并记录有效组数。

[联合收据](record-ref:project/baselines/chemical-encoder-benchmark-20261024-v1/actual-results-audit-ringfix-v2/JOINT-AUDIT.actual.json) · [组成](record-ref:project/baselines/chemical-encoder-benchmark-20261024-v1/actual-results-audit-ringfix-v2/COHORT-COMPOSITION.actual.json) · [配对差值](record-ref:project/baselines/chemical-encoder-benchmark-20261024-v1/actual-results-audit-ringfix-v2/paired-seed-MAE-differences.actual.csv) · [组宏](record-ref:project/baselines/chemical-encoder-benchmark-20261024-v1/actual-results-audit-ringfix-v2/group-macro-ten-seed.actual.csv)
[全部化学层均值SD](record-ref:project/baselines/chemical-encoder-benchmark-20261024-v1/actual-results-audit-ringfix-v2/all-three-summary--20261024T205552Z/summary/ten-seed-recalculated.csv) · [逐种子](record-ref:project/baselines/chemical-encoder-benchmark-20261024-v1/actual-results-audit-ringfix-v2/all-three-summary--20261024T205552Z/summary/per-seed-recalculated.csv)
