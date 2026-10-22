本目录只准备后评分驱动器；当前真实运行数为0。实际执行须由root检查冻结版本后，显式给出命令行授权和输入文档授权。

```powershell
& 'C:\Users\ciheb\AppData\Local\Programs\Python\Python311\python.exe' `
  'D:\work\科研工作台\research-tasks\peptide-binding-nc-benchmark-20261021\review\postscore-driver-v1\driver.py' `
  --inputs ROOT_ACTUAL_POSTSCORE_INPUTS.json --root-postscore-audit-authorized
```

`inputs.example.json` 默认未授权。真实输入须绑定driver冻结manifest、真实POSTJOINT-ISSUANCE、同一joint、两个评分池退出证明、原有绝对截止时间和本目录内全新输出目录。deadline不得超过2026-10-22 01:45 UTC；不会延时或自动重试。每个顶层池证明须包含exit_code整数0、private_session_handles_absent=true、pool_index_sha256和observed_at；root另保留真实session_id、pool_pid及工具wait来源等可用证据。

驱动器先沿 issuance→pool index→issued binding→central contract→unit-complete.scores 的链条，核对200个NN单元和40个RF单元的精确坐标、240份实际unit退出证明及600/120份producer收据。每个单元固定三数据集；不glob发现结果，不择优挑种子。RF-Classic只作为中央合同的行政alias，实际科学method_id仍为RF-Morgan2-chiral-AAC-DP。

随后生成明确任务映射和单独root授权，依次运行：

1. 原joint的WSL元信息门禁，通过后Windows执行原NN600独立重算。
2. Windows执行冻结RF v5独立重算120份收据。
3. 再次原joint元信息门禁，通过后Windows执行三个确定性参照全部十种子，保留360份评分。
4. 原v5 combine合并已审计指标。
5. 原v6 extension审计既有内部360 case（NN200/RF40/参照120）。
6. 原v6 merge生成新统一manifest。原1080评分／478440行／五篇前人方法计数保持不变。

所有数值计算均由已冻结原脚本执行，driver没有指标公式、训练或模型加载。它只读取已闭合的JSON收据/控制元信息，不读取原始gold、prediction、训练label、权重或矩阵。预测文件SHA沿原收据声明传递，真正字节和数值核查由冻结独立审计器执行。

运行环境已经验证为现有WindowsPython311＋NumPy2.4.6，不需要Torch或新增依赖。旧NN/ref helper原本支持WSL路径到Windows的转换，因此全部数值CLI直接在Windows运行。原 `joint_audit_gate_v4.py` 的路径方向相反：driver用WSL `/usr/bin/python3` 私有 `runpy` 调用其原 `require_joint` 函数，仅核240个选择的元信息，然后Windows调用原数值CLI。共同NN barrier路径/SHA、授权和deadline由driver严格绑定。没有monkeypatch，没有修改冻结源文件。此安排不等于运行原joint CLI的端到端子进程包装。

准备验证包括完整240单元／720收据的合成元信息映射、22项合成门禁/身份检查、七个冻结Windows数值/driver CLI的help接口，以及一次原joint函数对合成未授权文档的预期拒绝。没有执行真实joint门禁或真实数值流水线。

每个子进程退出后才读取闭合产物。子进程日志、退出码、命令和时间分别保留；NumPy线程数为1、CUDA不可见，输出为UTF-8。独立审计不完整或指标不一致立即停止，保存 `POSTSCORE-AUDIT-FAILED.json` 和现有产物，不修补指标、不重训或重选模型。输出目录必须全新，既有失败也不覆盖。

全部成功时输出 `POSTSCORE-AUDIT-READY.json`，含实际unified v6 manifest及SHA、NN/RF per-score审计索引、三参照manifest、v5 base/v6 extension索引、全部步骤收据和原issuance/joint链接，供行政归档。驱动器不签收中央论文结果、不修改登记库，也不自行启动原评分池。
