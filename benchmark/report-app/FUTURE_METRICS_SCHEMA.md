# 后续成绩的接口

当前`metrics.rows=[]`，应用显示“统一评测后更新”，没有示例成绩。

接收root独立核算并审阅的CSV或JSON，不接收JSONL、训练/测试标签、逐记录预测或检查点。CSV必须有以下列；JSON为同结构的数组，或`{"rows": [...]}`：

`method_id,panel_id,regime_id,chemistry_id,evaluation_set_id,metric_id,mean,sd,n,seed_count`

- panel_id：`source_peptide_dependency_cold`、`target_reference_homology_cold`。
- regime_id：`NC_only`、`standard_only`。
- chemistry_id：四个NC互斥组、`standard20_control`；汇总可用`NC_all`或`all`，需要保留原评价分母。
- metric_id：`MAE,RMSE,Pearson,Spearman,R2`。mean、sd未定义时用null，不能写0或NaN。
- n：该行测试样本数；seed_count：实际可用种子数，最高10。不足10必须如实保留。
- dataset不同或敏感性分母不同，用不同evaluation_set_id；75外测与13补诊断分别列示，不混成一个总成绩。

另需root审阅manifest，字段`kind="reviewed_aggregate_performance"`、`reviewed=true`、`independently_recomputed=true`、`all_required_selections_frozen=true`、`summary_sha256=<真实汇总文件SHA>`。这是导入门槛，不是本应用完成独立核算的声明。

执行`python import_reviewed_metrics.py --summary <汇总CSV/JSON> --review-manifest <审阅manifest>`。脚本保留app ID、其他证据和原snapshot备份，只更新metrics查询，设置buildStatus=updating。随后按app/AGENTS.md用共享builder构建；核对scope与root浏览器检查后设complete并重建同一项目。禁止重复运行初始化脚本覆盖新成绩或改app身份。

数据导入不运行模型、不评分、不发布，也不读取评测底层文件。
