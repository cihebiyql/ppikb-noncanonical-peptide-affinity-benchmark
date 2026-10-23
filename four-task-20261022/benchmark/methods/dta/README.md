# 五个DTA作者架构：新共同数据训练

方法为GraphDTA-GIN、MGraphDTA、DGDTA-CL（对应DGDTA论文）、DeepNC-GEN和GS-DTA。

`freeze_sources.py`只复制既有已审计作者模块及适配器，源文件不修改；`source-manifest.json`记录逐文件真实SHA。新目标与旧NC基准关联，但不恢复旧launch，不重置旧论文时钟，不使用旧结果冒充本轮训练。

## 任务适用

| 任务 | 定位 |
|---|---|
| 绝对亲和力 | 原作者回归架构在新共同数据上训练；Kd/Ki/IC50分开 |
| 改动效应 | 同一势函数f(mutant)-f(parent)，用效应损失训练；是明确适配版 |
| 是否相互作用 | 原标量输出+BCE-with-logits，属于二分类适配版；不虚构缺测阴性 |
| 接触/位点 | 原五个方法不提供逐残基头，当前不适用；不将attention当接触金标 |

所有方法均没有手性特征；D/L异构体可能具有同一有效输入。完整分子SMILES保留，不能用标准残基替代NC。MGraphDTA保留1200aa靶标前缀，其余1000aa；实际模型输入前缀必须列入重叠检查。蛋白输入缺少作者字符词表支持时拒绝并记录，不能悄悄删除字符。

## 运行边界

本目录不自行启动GPU。`jobs.json`列实际准备完成且哈希固定的spec/标准复现合同，由资源调度负责人验证后启动。共享环境不安装或更改依赖。每job线程1、PyTorch allocator2GiB、batch16、上限3600秒；调度另控制真实进程树与GPU余量。

固定学习率候选0.001、0.0003，Adam；正式20epoch/patience5，按validation MAE或logloss选最佳checkpoint和候选，训练seed0–9，固定测试分区。试跑为单独1epoch组件运行，不能当完整20epoch正式结果。每候选checkpoint、epoch日志和验证预测保留，选择冻结后方可评分测试。
