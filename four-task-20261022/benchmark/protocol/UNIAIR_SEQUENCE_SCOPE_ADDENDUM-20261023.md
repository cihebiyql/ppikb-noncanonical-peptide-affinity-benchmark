# HER2输入序列与原检查点暴露范围补充

本任务419个HER2体系的实际输入为H链变量域120aa、L链变量域107aa和靶标链581aa。先前部分说明将两个变量域合称“Fab227aa”，该术语在当前报告中改为“抗体变量域输入”；原始数据、分区、标签和模型均未改变。它属于一般抗体—蛋白任务，短肽主基准的样本数不因该数据而增加。

原AbSci spr-controls中的419个CDR1/2/3与Kd均有唯一匹配，输入序列和改动一致。这个匹配认证到当前变量域与读数层级；完整SPR构建体与全部化学身份另保留未认证状态。

对已保存的14条公开人源1N8Z记录，利用实际WT/MT坐标序列完成唯一链别名与变量域片段匹配：官方A/L链观察长度214aa，B/H链220aa，C/靶标581aa；本任务仅取对应107/120aa变量域，靶标581aa一致。14个官方MT变量域加靶标输入与当前419个输入的精确交集为0。完整构建体不同，且发布检查点引用另一份resplit文件，实际训练成员未完全核实；该审计不升级为新复合物或预训练无暴露结论。

作者DDG数值符合a×ln(Kd[nM]/1.9)，a约为0.59245198；使用拟合系数完整精度时数值残差约2.66×10⁻¹⁵，Kd升高对应正方向。完整温度/热力学单位映射尚未认证，主报告使用author_DDG标量，不将其标为已认证kcal/mol。

严格局部训练使用293/63/63，由本任务实际H/L变量域拼接序列的Hamming≤1依赖组件分组得到；原298/60/61诊断视图仍保留。固定419条推理、RDE重训、完整四专家MoFPE重训各自登记。

证据入口：

- `methods/uniair/continuation-20261023/official-HER2-variant-domain-overlap-v4/summary.json`及逐行坐标/序列SHA。
- `methods/uniair/continuation-20261023/continuation-status-v2.json`及各项独立审计。
- `methods/uniair/continuation-20261023/fixed-inference-diagnostics-v2/report.pdf`，保持原419条数值。

原`data/source_task_matrix.json`与13视图清单保留冻结历史；其旧术语和方向未核实描述应结合本补充解释。
