# 固定作者特征缓存预热

仅预计算五种作者方法在两冷划分、NC_only／standard_only训练域上的20组训练／验证编码。不构造模型，不创建优化器，不读取测试或外部验证标签，不生成亲和力评价指标。

`stage-manifest.json`和`contracts/`记录GPU正式规格来源SHA、派生CPU规格SHA、输入SHA和作者Python目录SHA。`stage/inputs/`只有四个已标注的训练／验证文件；测试标签与外部标签没有上传到此工作目录。作者编码、原子数、蛋白前缀和现有缓存signature规则均保持原样。

Node23使用既有环境：Torch2.6.0+cu124、PyG2.6.1、RDKit2024.03.2、NumPy1.26.4，CUDA不可见。最多16个nice15单核worker，每job RSS监视阈值4 GiB、墙钟1800秒，进程池RSS监视阈值64 GiB；控制器只终止自己创建的PGID。每job记录stdout、stderr、启动PID/PGID、退出码和采样峰值RSS。

每组完成后，`sync_caches.py`逐文件核验SHA和字节数，复制到主项目`encoded-cache-v3/`。Windows原子rename若发现目标已存在就失败；已有不同SHA文件保留，不覆盖。`cache-index.json`在本目录与缓存目录同步更新，供root调度读取。

`ready_cells`表示生产端校验且文件已落地，**不表示Torch2.12消费者的pickle兼容性已验证**。消费者应使用其实际GPU runner独立核验pickle、signature和adapter hash。生产特征的RDKit版本如实记录，不能改写成GPU环境版本。冲突或失败均保留收据，不篡改哈希。

正式训练由root的独立launch合同启动。本目录的耗时、文件数量和输入审计都是预处理证据，不是基准性能结果。

本次实际20组全部原合同内exit0，80个缓存／审计文件共4,206,400,411 bytes全部校验通过，输入审计累计83,780行。最慢原生MGraph标准肽任务1777.95秒，最大采样RSS1,483,247,616 bytes。没有启用600秒恢复分支，也没有实现或使用O(E)替代编码；standby恢复脚本仅保留代码。所有worker与pool均已结束，完整本地进程证据在`remote-evidence/`。
