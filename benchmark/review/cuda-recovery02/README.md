该技术恢复在以下条件下科学上可接受：原参数、seed和数据不变，原22:54:18.479676Z单元上界及01:45Z全局截止不重置；原失败完整保留，最终仍200个科学cell/400个有效候选配置。

旧pool199成功／1失败、reason为null仍应如实记录实际exit2。只有新retry pool完成200／0并实际exit0后，才能使用完整200的科学屏障。新pool用1worker，199条只verify-skip，只有失败槽位重新运行；再失败或预算不足即停止。

为保持已批准c7科学索引，先完整归档失败fit-root和receipt-root，再复用原科学路径，是“namespace reuse＋不可变旧字节归档”，不是历史path本身始终不变。归档须在旧pool实际退出、私有进程消失后，逐项绑定oldpath→archivepath、完整目录清单和文件SHA/大小；原pool日志、终端及旧bound-entry receipt不能移动或覆盖。新attempt_id、pool output_root及binding_receipt必须独立。

源码的关键时钟差异：`control/run_bound_unit.py:26–27` 以binding.deadline封顶，而 `launch/pool_supervisor.py:194` 及其whole-PGID看门狗使用index.deadline。因此新binding和新pool runtime index都应封到原单元上界，不能仅缩短binding而让pool保留更晚上界。`launch/pool_supervisor.py:213` 明确有failed时返回2，不得改写旧池退出事实。

冻结行政归档器仅检查parent contract.recovery_metadata。本方案保留原contract，因此CUDA恢复必须另以外部attempt-chain证据与该cell的最终归档关联，避免只在运行时门禁检查过、最终结果却漏记失败。先前IO -15和此次CUDA exit1都是额外未完成尝试，不能算新种子；恢复成功时主统计仍400有效配置/200选择。

详见 `REVIEW-PLAN.json`。本阶段只读取静态控制源码，未操作归档、启动任务或读取权重/预测/gold/标签。独立checker只核JSON元信息与声明清单，真实文件字节及进程消失由root实际核验后签证；不能把元信息一致称为模型字节已由本审查者重算。
