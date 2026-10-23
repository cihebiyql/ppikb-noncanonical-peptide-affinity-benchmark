# PepBDB 2020-03-18 历史坐标归档恢复补充

本补充为原[HTTPS官方资源锁](../official-resources-v1/README.zh-CN.md)的一项历史pending提供独立获取方式。原锁的197项恢复信息和1项pending保持原字节，本工具不修改、扩展或放宽通用HTTPS恢复器。

固定来源：`http://huanglab.phys.hust.edu.cn/pepbdb/db/download/pepbdb-20200318.tgz`。固定字节数691391502，固定SHA256：`33327794f45018ecd94252c078b2e734279528d82fbed76683e9c346dec32917`。原始归档许可未声明；工具只从原来源获取，不在本仓库再分发691MB归档。

历史原取得清单和维护者全量重读支持上述固定身份。原HTTPS请求失败的TLS EOF如实保留，没有关闭证书验证；HTTP HEAD返回200和相同Content-Length。[来源元数据](ORIGIN-METADATA.json)只证明定位信息，不能当作本轮远端完整下载成功。传输是没有TLS的HTTP，完整性依靠事先可信的固定全文件SHA；没有把HTTP声称为TLS认证传输。

本公开准备再次对已有原691MB文件做了一次完全离线全文件核验，大小/SHA均一致；[新核验收据](offline-full-verify.json)。本轮没有重新下载、解压、解析坐标或运行模型。

## 用法

仅需Python标准库。在独占、可信且可写目录中操作。

```text
python restore_pepbdb.py verify --path existing/pepbdb-20200318.tgz
python restore_pepbdb.py fetch --destination-directory new-archive-directory --socket-timeout 30 --max-seconds 3600
python -B -m unittest -v test_restore_pepbdb
```

脚本只支持唯一URL、固定文件名、大小和SHA；不接受调用者URL、镜像或自定义校验值，拒绝任何重定向、非200、Content-Length不符、内容/传输编码、超长/短读和坏SHA。没有解压、安装依赖、执行归档内容的功能。

已有目标只做离线校验，差异文件不覆盖。符号/硬链接和Windows reparse均拒绝。下载失败保留独占新partial，既不删除/续写旧partial，也不自动重试。成功后采用原子不覆盖改名；不支持该原子能力的平台拒绝完成，不回退成可覆盖操作。不从代理环境取得凭据。

socket超时1–60秒，流读取累计预算1–7200秒；一次阻塞读取可延续至socket超时，后续本地SHA复核不含于网络预算。需要严格总墙钟上限时，调用者另设自己进程的总timeout。程序不是对恶意并发改变目录的其他本机用户的隔离边界。

## 已验收范围

原工具在Windows和WSL/Linux各通过25项小字节模拟网络安全测试；本公开副本再次在Windows通过25项。测试覆盖固定接口、正常/坏SHA/短读/超量/超时、重定向、编码、partial保留、链接与拒覆盖；没有据此声称真实HTTP全归档下载、真实网络超时或Windows junction实机测试已通过。

[Windows源测试收据](test-receipt-windows.json) · [WSL源测试收据](test-receipt-wsl-linux.json) · [本批验证](VALIDATION.json) · [固定补充声明](addendum.json) · [文件SHA](FILE-MANIFEST.json)

## 资源口径勘误

新policy-v5使用真实`memory.free`，声明预算之外计入512MiB context及6144MiB外部负载增长预留；27项合成测试已由根独立复验。旧“6GiB”标签没有证明严格真实物理峰值≤6GiB，历史结果和日志原样保留，没有按新口径回改成绩。[勘误说明](resource-policy-correction.zh-CN.md)与[机器摘要](resource-policy-correction.json)不包含实际设备/进程身份、他人命令行或私人路径。

本包为自有恢复工具、测试、说明和来源校验元数据；没有复制第三方论文、原作者源码、配置秘密或大权重。准备时未提交或推送；实际公开状态以仓库提交/发布收据为准。
