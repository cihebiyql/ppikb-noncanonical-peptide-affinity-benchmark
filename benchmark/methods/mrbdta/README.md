# MRBDTA 作者架构适配

本目录独占，冻结作者源码位于 `../../model-audit/author-source/LiZhang30__MRBDTA/source/`，没有修改。上游 commit 为 `e338dd2f3aa55a09ba8b82c1ee5e79dc3aaab95c`。这是 MRBDTA 对 PPIKB 的配置适配基准，不是原论文数据集指标的完整复现。

## 输入与执行约定

- `METHOD_IDS=['MRBDTA']`。`adapter.py` 提供约定的 `encode_record`、`collate`、`build_model`、`predict`、`batch_targets` 五接口。
- SMILES 优先使用数据合同已有 `canonical_isomeric_smiles`，后备为原 `peptide_smiles`。保留大小写、`@`、斜线、反斜线、全部片段和完整分子；不转大写，不做非标准残基到标准残基映射，不截断分子。
- 显式启用作者 `DataHelper.py` 注释给出的 `CharIsoSmiSet`，token 1–64，Embedding 65；蛋白 token 1–25，Embedding 26。0 只用于 padding，未知字符报错，绝不静默替换。
- 蛋白采用作者 KIBA main 的 1000 aa 前缀配置。不是对实验构建体的断言。每条写出完整长度、有效长度、截断标志、完整及有效 SHA256；SMILES 原生位置编码容量 5000，超长显式阻断。
- 当前 9,619 条均可编码；SMILES 最长 1,878，蛋白最长 8,525，1,489 条蛋白因前缀配置发生截断。详见 `input-audit.jsonl` 和汇总。此为全部模型观测池审计，不能当作最终训练测试划分已冻结。
- 作者注意力维度为 `[B,H,L,L]`；位置编码使用 `[B,L,D]→[L,B,D]→[B,L,D]`，保持原样。未发现跨样本轴耦合。

作者对 padding 位置也求和，普通动态 padding 会使同条样本随同批最长输入改变预测。这里保留求和架构，通过 `predict` 逐条去掉 padding 后运行，使预测不依赖批次组成。逻辑 batch 可以大于 1，但不是向量化并行前向；训练需要积累多个计算图。建议真实 batch 1，若需有效更大 batch，在统一 runner 中显式使用梯度累积并记录。不得将 batch 数字解释为同时并行的样本数。

## 必要兼容补丁

`author-compatibility.patch` 和 `source-manifest.json` 保存全部变更及理由：

1. 采用作者提供的异构 SMILES 词表，并修复最大 token 索引的 Embedding 容量。
2. 将每次 forward 新建的 `LayerNorm(...).cuda()` 改为设备无关的 functional layer norm。原作者每次新建的 gamma=1、beta=0 从未被优化器追踪；本修复维持同样的无持久仿射状态，不擅自增加可训练 norm。
3. 求和后保留 batch 维度，只将最后标量输出 reshape 为 `[B]`，修复 B=1 崩溃。
4. 隔离副本不包含作者训练 main 和未使用的 metrics 导入。

`d_model=128,d_ff=512,d_k=d_v=32,n_layers=1,n_heads=4` 原生配置保留，三流／每模态架构未缩减，3,392,384 个参数。接口拒绝将这些结构尺寸当作调参项。

## 已执行验证

冻结 `smoke-contract.json` 后，在 node23 独占 `methods/mrbdta/smoke-v1` 目录运行一次 CPU smoke：1 CPU、6 GiB 虚拟地址空间硬上限、180 秒超时、CUDA 禁用；没有优化器更新、安装或 GPU 使用。

真实输入 SMILES 长度 202／165、蛋白长度 179／251。batch 1 和 2 前后向均通过，51 个参数张量具有有限梯度；eval 逆序以及单条对混批最大绝对误差均为 0。模型执行 0.477 秒，峰值 RSS 499,900 KiB。详见 `smoke-receipt.json` 和完整命令日志。

最长分子不能从上述小输入开销外推：仅三流返回的 float32 注意力矩阵就需要 `3×4×4×(L_SMILES²+L_protein_effective²)` 字节，尚不包含分数、反传缓存、参数／优化器状态。`input-audit.jsonl` 对每条记录保存此下界。

另冻结 `long-smoke-contract.json`，在独占 `smoke-long-v1` 目录按同样 CPU1／6 GiB／180 秒上限实测最长真实分子：SMILES 1,878 字符完整保留，配对实际蛋白 403 aa（无需截断，也未人为补长）。一次 forward 为 0.682 秒，backward 为 0.898 秒，模型执行共 1.663 秒；峰值 RSS 825,720 KiB（806.4 MiB）。3,392,384 个参数及 51 个梯度张量均有限。没有 optimizer 更新；这是资源 canary，不是一次训练 epoch。收据见 `long-smoke-receipt.json`。CPU 墙钟不能冒称 GPU 耗时，整个 campaign 预算还需统一 runner 的吞吐测量。

未执行全训练、10 种子运行、超参选择或测试指标评价；这些由 root 统一冻结合同和调度。不能把本 smoke loss 当成任何亲和力评价指标。
