# 冻结 ESM2 小模型基准

这是用户授权的简单预训练模型基准，属于新的通用方法条件，不是任何论文主表的完整复现。原始13个任务视图、原划分及既有成绩保持原样。

**已完成**：采用独立CPU v3提取5159条序列并完成三视图×五类头×十种子、两候选验证选参。实际结果、覆盖限制与1699文件本地交付见 `RESULTS.md`；原GPU准备v1/v2保留但未执行。

## 数据与输入

使用原始肽序列字段 `peptide_sequence_raw`，要求输入逐字符属于20种大写标准氨基酸；不转大写、不删除符号、不替换X、不从SMILES反推标准肽。效应任务先按 `reference_row_id` / `variant_row_id` 回溯原观测的原始序列，两端分别表征，同一靶标序列必须完全一致。标签、组与split继承原观测/配对视图。

每条序列预声明最多2048残基作为本次计算预算；这不是声称ESM2 API具有2048或1024的硬上限。官方实现使用随输入长度生成的旋转位置编码缓存。超预算行列入覆盖报告，绝不截断。筛选先于训练和测试打分，未参考模型表现。

| 视图 | 原行数 | 覆盖行数 | train/validation/test |
|---|---:|---:|---|
| PPIKB pKd 来源冷划分 | 9116 | 7419 | 5890/771/758 |
| PPIKB pKd 靶标冷划分 | 9116 | 7419 | 5203/1087/1129 |
| PPIKB silver ΔpKd | 2289 | 2222 | 1923/170/129 |

两个亲和力面板覆盖相同7419条观测，含521条带非标准化学注释的记录。模型仅看到记录提供的原样字母序列；**不会编码PTM、D型构象或其他非天然化学身份**。521条与完整1996条非标准记录不可混称；其余病例的覆盖限制均逐行保存。两个面板完整覆盖现有PepInter6336条件的共同测试ID（683/946），但本模型训练覆盖更广，比较时需保留这个差别。

## 模型与监督

优先官方 `facebookresearch/esm` 的 `esm2_t6_8M_UR50D`，固定checkpoint实际SHA与实际安装实现代码SHA。6层、320维，所有参数冻结，eval/inference模式，FP32，逐条输入。取第6层的真实残基均值，排除BOS、EOS和pad。亲和力特征拼接肽与靶标向量（640维）；效应拼接母体肽、变体−母体肽、同靶标向量（960维），母体/变体是配对的数学方向，不将silver关系称为认证生物WT。

五类头为常数、Ridge、随机森林、ExtraTrees、HistGradientBoosting。各有两个预声明候选，固定训练split拟合；只用validation MAE选择候选，全部0–9训练种子测试同一heldout split，保存两候选权重、验证逐行预测、选中模型测试逐行预测、指标与组/化学分层。Ridge仅在训练集拟合StandardScaler，LSQR固定tol1e-4/max_iter1000；确定性头可能十种子完全相同。

不安装依赖、不微调语言模型、不做LoRA。GPU由团队统一路由；任务单进程组、独立时间与RSS预算。既有旧PLM/MMseqs脚本与旧do_not_execute本地缓存入口不参与本次路径。

## 可追溯入口

- `coverage-manifest.json`：覆盖规则、原视图SHA、逐行覆盖和共同ID审计。
- `official-source/source-receipt.json`：官方代码冻结commit与来源文件SHA。
- `adaptation.diff`：相对既有通用CPU头实现的有限改动。
- `test_protocol.py`：原样身份门、效应向量与标签独立、split/标签保留测试。
- `feature-cache-binding.json`、`independent-local-cache-audit.json`、`local-mirror-receipt.json`：真实CPU提取、逐token/重复canary验证与完整本地交付。
- `runs/plm-simple-v1/heads/independent-recalculation.json` 与 `.local-v1.json`：远端与本地分别重算同316150个指标/选择单元，差异均为0；保留两份原记录。

官方来源：[ESM仓库](https://github.com/facebookresearch/esm)，[官方模型卡](https://huggingface.co/facebook/esm2_t6_8M_UR50D)。本目录保存的代码来自commit `2b369911bb5b4b0dda914521b9475cad1656b2ac`。
