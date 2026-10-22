# GS-DTA 2025：作者架构适配与运行验证

本方法作为统一基准第五篇不同论文的前训练替补，替换因权威原文 PDF 缺口而未满足本轮门槛的 MRBDTA。替换依据是资产完整性与输入兼容性，未查看验证／测试表现。MRBDTA 历史 smoke 完整保留；本目录不改旧方法或冻结源码。

原文：*GS-DTA: integrating graph and sequence models for predicting drug-target binding affinity*，BMC Genomics 2025，DOI `10.1186/s12864-025-11234-4`。已核对权威 PDF SHA256 `725e257cf378b2959afc34dd8b65d8c29787af6330c1d9fee3b464fd0a0619e3`。上游代码 commit `a36750c0c2567b5b4c3f9b3aed64eac5c40a3d3c`。

## 接入接口与模型身份

`adapter.py` 提供 `METHOD_IDS=['GS-DTA']` 以及统一五接口。`author_model.py` 是作者 `Models/gatv2_gcn.py` 的逐字节副本；两者 SHA256 均为 `73fb66ed9bfa8706c7dda6127dcbcb12aca528667f19a9dc846079bb4d3874f9`。模型无需 bug 补丁，`author-compatibility.patch` 因而为空；不可将空补丁误读为未检查。

`author_features.py` 仅从 GS-DTA 的 `create_data.py` AST 提取五个纯编码函数，配置保持原作者字母表和 1000 aa 上限。未导入作者处理整个 Davis／KIBA 的顶层语句，也未执行可能误用 GraphDTA 的 `training_validation.py`。

- 完整分子 78 维节点特征与全部原子／有向边，无原子截断；按作者每原子归一化。
- 作者不编码手性、键级或键立体信息；D/L 同拓扑分子可碰撞，不能声称分辨非天然手性。
- 蛋白固定 1000 aa 前缀并 padding，实际长度、截断、完整／有效 hash 和真实图输入 hash 全部记录。
- 回归目标由父合同预先固定为 pKd；接口拒绝非有限标签。不存在自行换算端点或拟合数据标准化。
- 原模型 6,569,063 参数。GATv2 10 头、双图分支、CNN、双层 BiLSTM、双层四头 Transformer 和原全连接尺寸均保留；未缩维。

实测 B2 形状：节点→`[38,780]`，图融合→`[2,1500]`，蛋白嵌入→`[2,1000,128]`，CNN→`[2,128,128]`，LSTM／Transformer→`[64,2,128]`，输出→`[2,1]`。CNN 把1000残基当通道、在嵌入宽度上卷积是作者代码行为，保持原样；没有将模型改写成另一架构。

## 已完成验证

使用同一冻结训练专用32条记录，SHA256 `1562172160338140f24cf3de9e2e46c6c14d5e305627caec9e37ceaacb8a8333`；未读取测试或外部标签。每次执行先保存独立合同，资源 watchdog 仅管自有子进程组。

|验证|实际结果|
|---|---|
|CPU B1／B2 前后向|通过，67个梯度张量有限|
|eval 批次逆序误差|3.73×10⁻⁹|
|单条对混批误差|3.35×10⁻⁸|
|GPU两次真实Adam更新，batch32|1.130 秒／0.0426 秒|
|GPU峰值allocated／reserved|421.5 MiB／502 MiB|
|watchdog峰值进程树RSS|2257.6 MiB|
|GPU全局内存观测增量|807 MiB，含桌面波动|

运行路线：现有 WSL Ubuntu-22.04 `cihebi`，已有通用 `/root/.venvs/peptide-omnipanel-v31-web311-20260723/bin/python`，Torch2.12.1+cu130／PyG2.6.1／RDKit2026.03.4。通过任务 `resources/local-gpu-route/vendor-dependencies` 设置 `PYTHONPATH`，没有安装或修改共享环境。

GPU执行前3次实时compute检查为空；RTX5080唯一一块GPU，CPU2、RSS4GiB／GPU观测增量4GiB／180秒上限；Torch allocator另限3GiB，给context余量。RSS0.1秒、GPU1秒采样。自有进程均结束，退出后compute仍为空。WSL compute列表只是当前可观察信息，不能据此声称全面识别所有Windows图形进程；GPU观测delta也包含桌面波动。

模型发出 Transformer memory-efficient attention backward 非确定性 warning；保持 `warn_only=True`，不可声称CUDA位级确定。原生 `batch_first=False` 与代码 `[64,B,128]` 对齐，nested tensor性能警告不属于维度bug。缺失编译scatter扩展由Torch fallback实际执行成功，未安装扩展。

`canary-cpu-v1/`、`canary-gpu-v1/` 中保留合同、结果、stdout／stderr和watchdog收据；`cpu-input-audit.jsonl`、`gpu-input-audit.jsonl` 保留32条实际输入hash。全部损失只是兼容性诊断，未保留canary权重，也未开展完整训练／调参／十随机种子评价。暖步单次吞吐不能当整个数据集ETA或所有长分子的内存保证。
