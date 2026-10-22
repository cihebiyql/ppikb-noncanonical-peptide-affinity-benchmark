# MGraphDTA 与 DGDTA-CL 作者实现适配

此目录负责作者方法向统一 PPIKB pKd 训练器的输入适配和必要执行修复。未修改冻结的 `model-audit/author-source/`，未新增架构或特征，未运行完整训练，不能称为原论文数值复现。

## 来源

- MGraphDTA：`guaguabujianle/MGraphDTA`，commit `54386680e8c9562f708a0fe5d381038c62111df6`，MIT。
- DGDTA-CL：`luojunwei/DGDTA`，commit `cc325a361f39652674f54a2120f17991f6f733f1`，GPL-3.0。
- `source-freeze-manifest.json` 保存原始和适配文件 SHA256；各 `.diff` 保存逐行修改。许可证原文在 frozen author-source 中，发布衍生代码时须遵循相应许可。

## 接口

`encode_record(row, method_id)` 要求 `record_id`、`pKd`、`target_sequence` 和 `canonical_isomeric_smiles` 或 `peptide_smiles`，返回含 CPU PyG Data 及有效输入元数据的可 pickle 项。省略 method_id 时返回两个方法的独立编码映射。`collate(items)` 返回含 graph、record_ids、method_id 的字典。`build_model(method_id, config)` 返回作者 nn.Module。`predict(model, batch, device)`、`batch_targets(batch)` 均返回一维张量。

MGraphDTA 保留22维原子特征、6维边特征及作者单图 minmax。作者核心 GraphConv 不使用这些边属性；此事实没有隐藏。蛋白采用作者字典和1200 aa前缀。DGDTA保留78维原子特征、无向双向边和1000 aa蛋白前缀。两种图均不截断原子，均未编码原子手性；DGDTA亦无键级或键立体特征。同构立体异构体可能具有完全相同输入，不能据此声称预测D/L差异。

## 必要修复

1. MGraphDTA：顶层 forward 克隆 Data，避免其深层 DenseBlock/GraphConv 对 data.x 的赋值污染调用方或复用缓存；不改变数值计算图。
2. DGDTA：`GCNConv` 不支持 `dropout` 参数（PyG2.6会透传到MessagePassing报错），删除这个无效参数；保留作者显式 dropout。
3. DGDTA：图分支为 `78×10×2=1560` 维，蛋白分支128维，拼接1688维；全连接入口由硬编码256修复为 `xd_features*10*2+dense_output_dim`。
4. DGDTA：LSTM输入为 `[B,1000,128]`，设置 `batch_first=True`，防止将批中样本当成循环序列。此修复改变错误执行语义，评测须标明修正版作者实现。其后作者 Conv1d 使用1000个通道、沿128维嵌入做卷积的结构仍保留。
5. DGDTA：原 create_data.py 顶层读取作者数据；只提取未改动的功能函数，防止 import 时启动无关数据管线。没有使用带测试集选优的作者训练循环。

## 验证边界

`smoke.py` 仅测试两个人工输入的CPU前向、有限梯度、单条/批量/逆序一致性及缓存隔离；资源合同见 `smoke-contract.json`。正式训练的划分、调参、十种子和外部验证由统一运行合同控制。本目录不生成任何基准性能结果。
