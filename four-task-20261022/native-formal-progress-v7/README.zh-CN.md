# 原完整方法正式训练：进展快照 v7

**PepInter 已进入真正的全量正式训练，但尚未完成一个候选或完整随机种子。UniAIR 已通过实际 CPU 源码导入验收，完整候选训练仍为0。** 本增量只公开已落盘的科学记录和进度边界，不运行模型、不推送仓库。

## PepInter：首段218次更新，仍在第1个epoch

seed0／candidate0首段自然结束为`paused_checkpointed`，记录218次已提交优化器更新、218个batch、5,232条训练记录；固定每epoch完整TRAIN为10,882条。检查点cursor仍是`epoch=1, next_batch=218`，`epoch_summaries=[]`：**第1个epoch尚未完成**，没有完成后的验证或测试指标，完成候选数和完整原生种子数均为0。

最新恢复槽6,925,539,880字节，SHA为`5e33ca14cd3ce9c57cf30954f13447db88839ffcf801d4a2a49e14c6d59a5640`。原结构检查证书文件SHA为`9c5d947fbe9aa28af71d4cbf40f917a9d00be21fb633945e7a4b6bb3be532a7d`；它对自有大检查点先做整文件SHA，再以CPU mmap检查结构、369个参数／369个Adam计数、scheduler、36组RoPE与72个buffer及cursor。**该次结构检查没有重新计算全部大张量有限性，也不是一次新的模型forward。** 本公开增量没有加载或复制该大文件。

公开的218行科学训练日志保留Focal、裁剪前梯度范数、学习率、全参数梯度计数、batch大小与真实／padding后长度等字段；对应数值逐字段核对原件。它们是运行时训练记录，不是验证／测试性能，也没有在本增量独立重算完整梯度。日志显示第一步学习率为0，不能把全部218次调用都称为正学习率更新。

第二段已获根任务科学与资源批准，源独审SHA为`509cb05b42b0da533c5ba800faf723e8004052fea2ceaa03ec254a3e3ce64458`。计划从218继续同一个seed、候选与采样cursor，不能重置优化器、epoch或重新借用早期成本门快照。**本快照尚未取得第二段actual启动收据，因此仅记“已批准／准备启动”，不记为running或已恢复训练。** 批准记录的原SHA见STATUS-SNAPSHOT，不等同于执行证明。

## 保真范围：作者padding与初始化暴露

正式输入已恢复作者 `longest + pad_to_multiple_of=8`，无截断；218行记录的padding长度全部符合`ceil(raw_paired_max/8)*8`。此前成本门实际991的适配差异及成功结论仍保留在[原v6历史](https://github.com/cihebiyql/ppikb-noncanonical-peptide-affinity-benchmark/blob/9a740c6934de22e8c4a81f1463dcc0c98ac7b29e/four-task-20261022/pepinter-fullB24-capability-v6/README.zh-CN.md)，不能把旧991成本直接当作正式authorpad8逐位基准。

初始化使用官方回归监督backbone并新建原分类头；原作者energy初始化权重不可用，不能声称完全恢复energy-pretraining。现有来源审计识别到2,349条预留TEST中，**59条与已公开亲和力训练对精确重合**。将来可以对同一份保存的测试预测另报排除这59条后的2,290条结果，但“无精确命中”不等于已认证未暴露，当前更没有测试结果可报。

网络保留原完整576,293,761参数、B24、5epoch／2,270步目标、原Focal和调度；GPU BF16 autocast与FP32参数／梯度结合stock CPU FP32 AdamW和activation暂存。CPU优化器后端不保证与全GPU AdamW逐位等价，序列输入也不自动表达完整PTM／非天然残基化学身份。这些是结果解释范围，不是额外创新模型。

## UniAIR：源码导入通过，资产闭环与训练未完成

CPU source-import v2已在真实计算作业通过独立审核，原审计SHA为`9529cd5f6368500b00ee0c0411686045c3248b6bfedecaab3f2b247ba637c718`。此证据对应源码模块／CPU CPP运行库的导入闭合，**不等于四专家大权重构造、完整forward、完整epoch或20候选已完成**。

已授权的10份原权重加geometry共5,904,270,047字节，最近受控状态为迁移进行中；尚未拿到所有目标文件物理落地、逐SHA与真实consumer路径的最终认证。迁移进程存在或资源批准不能替代完成证明。完整20个CPU候选完成数仍为0，完整原生种子完成数仍为0；当前合同、CPU后端排他和首个真实训练作业仍需逐步冻结核验。

## 公开范围与计数

八项约定方法中，六项的约定面板已有10种子结果；完整PepInter和UniAIR主线仍未完成。既有1,050项main与100项来源受控补充选定模型继续单列，本快照新增完整原生种子为0。

本包包含原科学记录的字段白名单、去身份摘要、确定性gzip及原件／公开件SHA映射。原私有完整收据、资源进程表、机器UUID/PID/用户名、原始输入序列／标签和大模型状态不随本增量公开。历史成本成功与OOM／unknown记录均不回写。公开准备不等同于已发布，后续发布须由根任务核对本白名单。
