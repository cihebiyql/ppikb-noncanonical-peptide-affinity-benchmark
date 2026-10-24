# PepInter 原 B24×991：两步 GPU 能力门通过

**新机制已实际完成原 B24×991 两次完整前向／反向／优化器事务，并成功保存与恢复检查点。** 运行自然退出0，过程与最终自有快照均经独立审计。这是能力与成本门成功，尚未完成原计划五个epoch、20个正式候选或10随机种子；没有使用验证集或测试集。

本次保留原完整576,293,761可训练参数、原网络与Focal、原批量24和已冻结适配输入的配对长度991，结合GPU计算、saved-activation CPU暂存及stock CPU FP32 AdamW。实际环境为Torch2.6.0+cu124。CPU优化器后端与全GPU AdamW不保证逐位相等，不能把工程能力门称为原论文性能复现。

## 已知输入适配差异

作者 `lightning.py` 分类训练577–580行与推理845–848行均使用 `DataCollatorWithPadding(padding="longest", pad_to_multiple_of=8)`。本次已成功成本门的旧适配 `encode` 只做 longest，未设置 multiple-of-8，因此实际长度是991；作者相同批次按此规则应补到**992**。原完整文件SHA与两处摘录SHA见 [INPUT-ADAPTER-SCOPE](INPUT-ADAPTER-SCOPE.json)，没有补造未知的完整commit SHA。

这项成功仍证明完整网络与B24在所记录991适配输入上的能力，**不等于作者collator完全复现，也不构成authorpad8成本或逐位基准**。padding变化可能改变dropout RNG消耗和数值结果。正式主线将恢复authorpad8；首正式段在本次元数据修订时尚未运行。原成本、phase、日志、trace和快照计数均保持原字节。

## 已完成的两步

| 项目 | 第一步 | 第二步 |
|---|---:|---:|
| 使用的学习率 | 0 | 8.849557522123894e-7 |
| Focal batch均值（运行记录） | 0.06584683060646057 | 0.0680360198020935 |
| 裁剪前梯度范数（运行记录） | 0.7448099255561829 | 0.6851398348808289 |
| forward耗时（秒） | 18.91747614648193 | 18.342748945578933 |
| backward耗时（秒） | 17.526906995102763 | 12.141405081376433 |
| CPU Adam＋copyback＋scheduler组合耗时（秒） | 20.608019615523517 | 13.332887823693454 |
| 完成后的Adam状态步数 | 1 | 2 |

**共有2次Adam调用，只有1次使用正学习率。** 第一步学习率为0，不能称为第一次非零参数更新。原调度为113步warmup／2,270总步；本次只执行前两步。最终调度学习率为1.7699115044247788e-6。

step1真实写盘后在step2之前恢复；step2又将同一提交快照路径原子替换为最终状态。最终快照6,916,041,472字节，SHA为`299775e0ecff49e1de6a4fa08943efbc8bf681d1967a7b6f66f551a781fa6fee`。本增量不复制或加载该大文件。

独立审计在原保全位置**先验证SHA再CPU加载自有快照**，确认369个模型参数张量、576,293,761参数元素、369个optimizer states、1,107个CPU状态张量、1,152,587,522个FP32矩元素，全部有限，Adam step均为2，二阶矩非负；scheduler、mapping、cursor及RNG结构匹配。step1旧快照字节已被最终快照替换，因此step1恢复依据是当时实际write/restore phase、SHA和冻结代码；没有重新加载已经不存在的旧字节。

编码器／分类头探针分别记录正变化8.284114301204681e-7与8.856877684593201e-7。初始探针张量、logits和完整梯度没有独立保存，因此这两项变化、Focal和梯度范数属于经来源认证的运行记录，不能声称已经由原张量独立重算。GPU参数copyback全等也是原worker的运行时断言；独立快照未另存CPU master值供再次逐项对比。

## 两份 activation trace 与成本

两步各记录231事件：42 preserve、95 offload、94 restore。每一步94个restore都能关联先前相同meta／payload SHA；每步unique CPU payload为4,084,480,708字节，CPU空dummy保持原语义。公开gzip保留两份原始科学trace的全部元信息、计数与payload摘要，没有原激活值、输入序列或标签。原始CUDA激活字节没有另存，因此不声称这次归档重算了CUDA逐位往返。

受控整进程耗时约364.039秒，worker实际记录341.9072650671005秒。观察物理GPU峰值7,690 MiB、最低真实free8,249 MiB（要求保留6,144 MiB）；worker peak allocated6,731,026,944字节、reserved7,566,524,416字节。worker峰值RSS **24,382,328,832字节，低于32 GiB预算**。277次内存门采样均通过，作业没有资源guard停止原因。阶段原CSV保留父子嵌套标记，不能重复相加；“CPU Adam＋copyback＋scheduler”未分别插桩，不能将整段都算作CPU Adam自身耗时。

## 证据范围与状态

独立最终验收原SHA：`a4c23a6412e0a5f24ff52838befede726b7c743bb6de49b616d833ef10f896c5`；自有快照深审原SHA：`250e12c9d8e570ac5d1ba11d979ab9e153f02628e31b329853eafb4849aa2002`。148份小型科学／资源证据保全包SHA：`66db7dae32faa77bf93047c0d22316df0e8e47d9e7af31756cbfb9ac89389299`，另有归档manifest；本公开增量只取明确科学文件，不递归公开原包或私人进程表。

运行源码固定：activation helper`b9324b6cc7bfbf075df7f55c0000823bfa5183be84cdf729c367535a09c9a3ea`、worker`727b767171ff2e7b319e73a517830929a138d6c6c714308aa60b69a87b75a66f`、stockCPUAdam helper`06cf607def620e6d4bf35fa5e457aa54ea1d55c50d6040bf854554b0e1f259d2`。实际合同SHA为`cd4a2b7f94490fd31f96686e064b8e56a90f204a9c96bf3ba8e71e66e7462275`。

此前[两个GPU成本门OOM及未知启动历史](https://github.com/cihebiyql/ppikb-noncanonical-peptide-affinity-benchmark/blob/d7e294be1e37c3120c3cd0ace496d4c36bac88cf/four-task-20261022/native-GPU-cost-status-v5/README.zh-CN.md)保持原结果。这次是后续新机制的成功，不回写旧失败；UniAIR完整训练仍未完成，PepInter完整五epoch／正式20候选／10seed也仍待执行。新增正式完成种子为0，验证／测试记录为0，既有1,050 main与100来源受控补充模型分母不变。

本目录只准备公开材料：去私密路径的JSON摘要、原phaseCSV、两份activation trace与原0字节stdout/stderr的确定性gzip，以及逐源／公开SHA映射。没有新增训练、加载模型或大快照，没有复制模型权重、原始输入序列或标签，也没有修改公开checkout或推送仓库。
