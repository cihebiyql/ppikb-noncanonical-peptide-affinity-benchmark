# DTA 分支：数据、适配与真实执行说明

**当前进度入口：** `accepted-details-current.json` 指向逐项独立验收后的完整种子、指标、运行环境与产物证据；`accepted-census-current.json` 给出对应总数。下面带时间戳的数量属于历史快照，不能作为当前完成数。150个正式单元全部通过最终独立审计后，`final-delivery-current.json` 才会生成。

**补充的实际输入审计：** `effective-input-audit-cihebi-native-20261023T073053Z/complete.json` 覆盖五方法×三视图的实际缓存。按模型消费的节点、边索引与蛋白tokens逐字节计算，全部15个组合的有序有效输入对训练—测试精确重合数为0。蛋白长度截断、同一记录化学输入的分层注释差异及条件子集评分另行保留；有序张量哈希不能穷尽图同构等价。MGraph作者forward没有使用缓存中的edge_attr，不能把“缓存含键属性”写成“模型消费键属性”。跨环境已实际对照71954个方法×视图×记录输入条目，消费张量字节均相同；这些条目重复使用生物学记录，不是71954次独立实验，也不证明模型或梯度逐位一致。

时间戳：2026-10-23 00:50 UTC。本文是过程记录，完整成绩以各运行的 `complete.json`、逐行预测与独立审计为准。

## 任务与评价单位

五种作者架构为 GraphDTA-GIN、MGraphDTA、DGDTA-CL、DeepNC-GEN、GS-DTA。它们源自药物—靶标亲和力预测，当前作为“肽完整分子图 + 蛋白序列”的迁移基准；不能称作五个原生肽—蛋白方法的原论文全量复现。

本轮预注册三个正式数据视图：

| 数据视图 | 训练 / 验证 / 测试 | 标签 | 适配性质 |
|---|---:|---|---|
| PPIKB Kd 来源留出 scope v2 | 7125 / 977 / 1014 | pKd | 原标量回归架构，新共同数据训练 |
| PPIKB Kd 靶标留出 scope v2 | 6355 / 1378 / 1383 | pKd | 同上 |
| PPIKB metadata-silver 来源留出改动对 | 1988 / 172 / 129 | ΔpKd | 同一标量势函数 f(mut)-f(wt)，差值损失适配 |

silver 表示条件元数据筛选后的可比候选，尚未逐篇原文认证实验条件；不能宣称它是严格金标准。来源/靶标留出也不能自动解释为蛋白家族留出或新肽骨架留出。

二分类头可做明确适配，但不把亲和力未测记录自动当阴性。五方法没有原生逐残基接触头，接触/位点任务不适用。其他团队方法负责原生相互作用与位点任务。

## 原始算法与化学边界

训练引擎 `train.py` SHA256 为 `8282b3f8437eaa47afed56b8bf33fa85515f8e677153d05b6555e207bfaa9924`，冻结13份作者模块/适配器。两学习率为0.001和0.0003，Adam、batch16、20 epoch上限、patience5，验证MAE选择候选；测试在选择记录冻结后读取。

保留实际完整分子SMILES，不用标准氨基酸序列替代非天然化学实体。作者原图特征未编码原子手性，D/L异构体可能发生有效特征碰撞；其结果不能证明对非天然立体化学改动具备识别能力。MGraph蛋白序列上限1200 aa，另四方法1000 aa。标准肽、非天然残基和PTM的分层成绩必须与总体成绩并列。

整体基准另有显式手性Morgan对照：`baselines/molecular/molecular_features.py` 的生成器设置 `includeChirality=True`、`useBondTypes=True`，已有D/L差异及磷酸化变化canary和独立旧API重算证据。它可以表示输入SMILES中已经标注的立体信息；原始数据缺失的立体注释仍需单独处理。该对照与五种作者图特征的结果应结合阅读。

## 运行环境与失败保留

- Node1：Torch2.6.0+cu124、PyG2.6.1、RDKit2024.03.2、NumPy1.26.4。原GPU2正式Graph与DeepNC出现CUDA非法访问，失败日志保留。后续Node1使用独立合同说明的no-cuDNN兼容入口；原作者模型/训练引擎未变。
- WSL：Torch2.12.1+cu130、PyG2.6.1、RDKit2026.03.4。GPU正式seeds0–3独立输出；另两个真实partial没有完整第二候选，不能仅凭最佳权重宣称正式结束。
- Node23：与Node1同版本的CPU环境，最初CPU1，未启动作业经资源修订转CPU2。CPU正式seeds4–9，4 GiB RSS/任务、nice15，联合最大15任务，动态保留至少32 GiB可用内存和40%空闲。

不同主机、RDKit/Torch版本、CPU线程和后端是实际运行分层。跨层混合的10次标准差同时包含环境变化，不能只解释为随机种子方差。所有新输出与失败旧输出分开保存；原共同截止2026-10-23 01:31:20 UTC保持不变。

## MGraph数值资产复用

原预处理对所有原子对枚举找键，完整当前数据曾耗尽3600秒且尚未产生训练checkpoint。使用原生既有数值特征资产解决重复构图；没有读取旧模型权重或旧预测。

实际stage压缩包59,586,689字节，解压587,876,529字节；原资产生产环境与Node23当前环境逐版本一致。核验record_id、完整SMILES（含立体信息）、完整靶标序列哈希和冻结作者源码。旧资产覆盖9433条ID/5923种完整化学+靶标输入；当前缺失126种独特输入使用私有等价预处理补齐。

私有预处理只将N²找键改为逐键双向枚举后按(i,j)词典序排序。原参考同样按(i,j)次序遍历，因此边列表及方向顺序相同；节点、边属性、归一化、蛋白编码均沿用原函数。19个真实/边界实例已逐tensor核对dtype、shape与array_equal，包括长链、环、手性、PTM、无边分子。原冻结源码不改。

当前source/target六个partition与effect三个partition均已落盘，逐行映射保留。旧graph.y全部清零，实际训练使用本轮冻结标签；effect两实体从当前完整source数值图按完整输入键重排。Node1可消费这些Node23生产的CPU数值张量，但必须匹配同一Torch/PyG/RDKit/NumPy版本；未把RDKit26缓存冒充RDKit24数值表示。

`cache-reuse-v3/manifest-node23-with-effect.json`记录真实producer、文件SHA与映射。正式CPU新阶段为`node23-cached-v5`；前序v4只被标准合同门槛拒绝、模型未启动，拒绝证据保留。

## 已有可核验证据

截至本记录，Node23五种原生smoke全部成功，Graph来源留出seeds4–9六个正式单元完成；独立逐行指标重算与标准result acceptance共11/11通过。另有独立预定义D-backbone633行子集的CPU GraphDTA十种子完整训练，该子集结果必须单列，不能替代9116条共同数据目标。

CPU源MGraph构图六个超时、DGDTA CPU2部分正式单元超时，均保留完整运行证据。新cache阶段训练已实际启动，但没有完成标记前不纳入正式成绩。任何仅smoke、部分epoch、单候选或缺失预测的单元均不算完成10随机种子。

## 完整十种子组合（00:57 UTC已核验）

GraphDTA-GIN × 来源留出主视图已取得全部10个逻辑种子：WSL GPU0–3与Node23 CPU4–9。测试每次1014条；混合环境汇总MAE1.54806±0.04389、RMSE1.95713±0.03957、R²−0.16485±0.04740。GPU分层MAE1.5584，CPU分层1.5412。合并SD包含环境差异，按分层同时报告。该结果并不显示强预测能力。证据在 `source-GraphDTA-ten-seed-confirmed/`。

DGDTA-CL为保留的旧运行索引名称，实际对应DGDTA的动态图注意力、GCN与BiLSTM架构。作者原训练入口main.py第72行明确使用nn.MSELoss()，原论文第7页也说明使用MSE；此前将旧索引解释为对比学习、声称缺少对比预训练阶段，是事实误读，现予以更正。本轮仍属于共同数据上的作者架构重训，训练预算和划分采用本轮方案，不能称为原论文数值复现。DGDTA图还缺少显式键级特征。

WSL GPU截至00:54，52个完成单元（42正式+10smoke）的逐行预测指标已独立重算，零差异；不能据此认为所有组合十种子闭合。独立全量数值特征审计9/9分区通过。所有尚在训练、超时和不满足截止启动门槛的作业继续按真实状态清点。


## 用户授权继续后的增量验收（2026-10-23 04:52 UTC）

用户明确取消本轮总时限，后续各作业仍有独立有界资源合同。原01:31:20截止、失败与partial记录作为历史保留；本节取代把该旧截止解释为当前停止条件的读法。续算没有缩减样本、两学习率候选、20 epoch上限、patience5或10个种子的目标。

当前已逐项验收90/150个共同数据正式单元：原59加新增31。新增结果独立复算39,024项总体、化学类别和组内指标，零差异；两个候选的最佳权重、验证预测、选择记录和测试预测均核验SHA。真实进程收据证明exit0且自有进程组无残留，不能仅凭complete.json判断成功。远端新增3单元的88份科学产物、日志与合同已回流本地并核验全部SHA。

| 视图 | 方法 | 已验收种子数 | 缺失种子 |
|---|---|---:|---|
| ppikb_effect_metadata_silver_source_cold | GraphDTA-GIN | 6/10 | 6,7,8,9 |
| ppikb_effect_metadata_silver_source_cold | MGraphDTA | 3/10 | 3,4,5,6,7,8,9 |
| ppikb_effect_metadata_silver_source_cold | DGDTA-CL | 6/10 | 6,7,8,9 |
| ppikb_effect_metadata_silver_source_cold | DeepNC-GEN | 6/10 | 6,7,8,9 |
| ppikb_effect_metadata_silver_source_cold | GS-DTA | 6/10 | 6,7,8,9 |
| ppikb_kd_source_cold_scope_v2 | GraphDTA-GIN | 10/10 |  |
| ppikb_kd_source_cold_scope_v2 | MGraphDTA | 4/10 | 4,5,6,7,8,9 |
| ppikb_kd_source_cold_scope_v2 | DGDTA-CL | 6/10 | 6,7,8,9 |
| ppikb_kd_source_cold_scope_v2 | DeepNC-GEN | 7/10 | 7,8,9 |
| ppikb_kd_source_cold_scope_v2 | GS-DTA | 6/10 | 6,7,8,9 |
| ppikb_kd_target_cold_scope_v2 | GraphDTA-GIN | 6/10 | 6,7,8,9 |
| ppikb_kd_target_cold_scope_v2 | MGraphDTA | 3/10 | 3,4,5,6,7,8,9 |
| ppikb_kd_target_cold_scope_v2 | DGDTA-CL | 9/10 | 9 |
| ppikb_kd_target_cold_scope_v2 | DeepNC-GEN | 6/10 | 6,7,8,9 |
| ppikb_kd_target_cold_scope_v2 | GS-DTA | 6/10 | 6,7,8,9 |

完整权威索引为accepted-common-census-continuation-20261023T045212Z.json；后续完成数量以更新后的独立验收索引为准。CPU/GPU、Torch/RDKit和no-cuDNN后端分层持续保留。
