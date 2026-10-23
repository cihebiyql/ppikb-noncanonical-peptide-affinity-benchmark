# 原生RDE组件：HER2局部变体十随机种子基准

记录生成时间（UTC）：2026-10-23T09:45:57.932223+00:00。完整UniAIR分轨进度以文末动态索引为准。

原生RDE组件已完成10个独立随机种子的真实训练，共20个学习率候选。所有检查点、优化器状态、逐轮日志、验证集选择和测试预测均已保留并独立核验。
在同一组63条测试记录上，RDE的MAE为0.517 ± 0.018、Spearman为0.639 ± 0.020；该固定测试上的平均MAE低于所列五种传统对照。

结果端点使用作者原始DDG标量，物理单位未认证。均值与样本标准差（ddof=1）描述10个初始化种子的变化；63条测试记录来自同一HER2背景。

## 数据与划分

- 419条测量均与原始AbSci SPR表的CDR1/2/3序列及Kd唯一对应，全部保留。
- 结构输入包含H120/L107抗体可变域与581 aa HER2；作者原始特征流程提取128残基界面patch。WT为处理后的实验PDB来源，MT为作者提供的建模结构。
- 依据完整H+L序列的Hamming距离≤1构造连通分量，共357组、67条邻接边；训练/验证/测试为293/63/63，跨划分邻接边为0。
- 所有模型使用相同测试ID及作者DDG标签。非天然残基/PTM、短肽、绝对pKd和结合位点任务由项目对应数据视图另行评价。

## 模型与调参

使用作者发布的DDG_RDE_Network，加载公开无监督RDE.pt并冻结该基座，其余原生参数按种子0–9独立初始化。本轮训练没有加载有监督SKEMPI专家权重。实际实例化参数为7,227,381个，其中1,907,369个可训练；发布SI参数表中的RDE规模与此实际实例化数不同，记录按实际代码和权重保存。

损失为原生masked双向MSE，包含正向预测与逆向预测。每种子比较Adam学习率3e-4和1e-4，beta=(0.9,0.999)，weight decay=0，batch=16；最多30轮，验证原生MSE连续5轮未改进停止，ReduceLROnPlateau参数为factor=0.8、patience=5、min_lr=1e-6。梯度裁剪遵循作者实际入口中的关闭状态。

各候选先按最低验证MSE选择轮次，再按验证集正向MAE选择学习率；相等时优先3e-4。测试集在选择记录冻结后才评价。此训练预算是共同任务的预冻结预算，作者原始主表训练预算独立列在协议中。

## 同63条测试记录的结果

| 模型 | MAE（均值±SD） | RMSE（均值±SD） | Spearman（均值±SD） |
|---|---:|---:|---:|
| 原生 RDE 组件 | 0.517 ± 0.018 | 0.662 ± 0.027 | 0.639 ± 0.020 |
| ExtraTrees | 0.593 ± 0.009 | 0.766 ± 0.009 | 0.477 ± 0.025 |
| 随机森林 | 0.598 ± 0.010 | 0.779 ± 0.007 | 0.457 ± 0.020 |
| Ridge | 0.603 ± 0.000 | 0.767 ± 0.000 | 0.492 ± 0.000 |
| HistGradientBoosting | 0.637 ± 0.000 | 0.812 ± 0.000 | 0.457 ± 0.000 |
| 常数均值 | 0.720 ± 0.000 | 0.903 ± 0.000 | 未定义 |

RDE的Pearson为0.685 ± 0.029，R²为0.461 ± 0.044。完整五项指标、逐种子值和配对MAE差值保存在下列表格。确定性传统模型跨种子的标准差接近零，原始浮点值照常保存。

## 验证证据

- 10个种子具有10种不同的初始可训练参数SHA；同一种子的两个学习率候选采用相同初始参数。
- 20份候选检查点逐一核对SHA、93个Adam状态张量的step计数、已执行轮数、所选轮次、参数变化与冻结RDE基座一致性。
- 10份测试预测逐一核对63个ID、分量组、标签及全部指标；学习率选择依据验证集重新计算。
- 21次本lane实际GPU终态（含组件失败/推理/训练）的stdout、stderr、合同、真实校验和终态lease已回收到本地；210个文件逐一核SHA。
- 先前显存和配置失败均单独保留，未作为额外种子或成功训练计入上述10个模型。

## 研究范围

该结果衡量同一HER2背景中的局部变体泛化，属于作者原生RDE组件的共同任务适配。无监督基座的训练成员未认证。完整四专家UniAIR/MoFPE独立跟踪：原生两条训练输入的一步训练已通过，原batch8的单次9GiB尝试因显存不足停止，目前等待12GiB安全资源窗口。固定发布专家的419条推理和新训练结果分开归档。

## 交付入口

- [20候选与10种子的机器可读总表](summary.json)
- [逐模型逐种子指标](all-model-seed-metrics.csv)
- [均值与样本标准差](mean-and-sample-SD.csv)
- [同种子与传统对照的配对MAE差值](paired-seed-MAE-differences.csv)
- [冻结训练协议]〔record-ref:peptide-four-task-benchmark-20261022/methods/uniair/continuation-20261023/local-training-protocol-v1/training-protocol.json〕
- [冻结划分及组级审计]〔record-ref:peptide-four-task-benchmark-20261022/methods/uniair/continuation-20261023/local-training-protocol-v1/split-manifest.json〕
- [21次实际GPU终态日志与合同索引]〔record-ref:peptide-four-task-benchmark-20261022/methods/uniair/continuation-20261023/owned-gpu-terminal-log-index-v1.json〕
- [本地210文件SHA核验](evidence/local-GPU-log-export-verification-v1.json)
- [固定发布权重的419条诊断图与报告]〔record-ref:peptide-four-task-benchmark-20261022/methods/uniair/continuation-20261023/fixed-inference-diagnostics-v2/report.pdf〕
- [当前完整UniAIR分轨进展](evidence/continuation-status-v2.json)

每种子的原始模型/优化器状态、候选历史与测试预测位于`runs/uniair_rde_native_local_formal_seed00_v6`至`seed09_v6`；`execution-provenance/`内保存该次运行真实合同和日志。

## 原始来源

- [UniAIR官方Supplementary Information](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs42256-026-01243-7/MediaObjects/42256_2026_1243_MOESM1_ESM.pdf)。
- [作者代码固定commit](https://github.com/hanrthu/UniAIR/tree/e1b48d0aecd8247544e123726378dbbd43ef9bb6)。
- [作者权重固定revision](https://huggingface.co/Jesse7/UniAIR_model/tree/d2a6d58e93a94194579f8ff8ccc34d94895dd173)。
- [原始SPR数据来源固定commit](https://github.com/AbSciBio/unlocking-de-novo-antibody-design/tree/cd2bd4b6932b5301d435555dc22084d407e4b92b)。
