# 五方法官方完整文件快照

本目录保存冻结确切commit的官方GitHub文件归档及解压副本；没有执行作者代码、安装依赖或改变训练源码。完整文件归档与完整Git历史分别记账；LFS／子模块／外链数据未额外拉取。

| 方法 | commit | 状态 | 归档字节 | 文件数 | 许可文件 |
| --- | --- | --- | --- | --- | --- |
| GraphDTA-GIN | 6162245c6776684b391d30610850fe7077478435 | complete_exact_commit_file_archive | 1127028 | 22 | 未发现／未知 |
| MGraphDTA | 54386680e8c9562f708a0fe5d381038c62111df6 | complete_exact_commit_file_archive | 23758341 | 60 | LICENSE |
| DGDTA-CL | cc325a361f39652674f54a2120f17991f6f733f1 | complete_exact_commit_file_archive | 22555 | 8 | LICENSE |
| DeepNC-GEN | 297940199a26aa9a1afa8e3fc1a0b2c3ce9f0d38 | complete_exact_commit_file_archive | 1016899 | 22 | 未发现／未知 |
| GS-DTA | a36750c0c2567b5b4c3f9b3aed64eac5c40a3d3c | complete_exact_commit_file_archive | 967904 | 17 | 未发现／未知 |

每方法 receipt.json 记录官方URL、时间、退出与SHA；file-manifest.json记录所有归档文件的大小、CRC32、SHA；author-evaluation-split-license-inventory.json给出评价、划分、验证与checkpoint选择脚本的静态行线索。候选脚本出现关键词不证明执行正确或原实验协议已复现。

来源身份：control/registered-paper-map.json 与 report-preparation/predecessor-models.csv。既有resources只有本地依赖等资产；既有model-audit/author-source为selected-source，原件均保留。

如网络／CRC／解压失败，原失败和partial文件保留，当前任务每repo只进行一次有界网络请求。

## 逐文件完整性复核

asset-integrity-verification.json 将每份归档的完整路径集合与原先保存且 truncated=false 的官方 git-tree.json 对照，129/129 个 Git blob SHA-1一致；解压文件SHA-256和CRC全部通过。原selected-source的95个文件全部逐字节匹配。DGDTA的既有source恰好覆盖原仓库全部8个受跟踪文件；其余四份旧source分别18/22、37/60、17/22、15/17。本轮resources中新存官方压缩归档，不移动原source，也不声称下载Git历史。

许可证：MGraphDTA为MIT LICENSE；DGDTA为GPLv3 LICENSE；另三仓库在所冻结commit未发现显式LICENSE文件，保留未知。五仓库均未发现.gitmodules或小文件Git LFS pointer；外链数据与其他发布资产仍单独计量。license-evidence.json 保存实际文本开头及SHA。

评价/划分线索：GraphDTA的training.py、training_validation.py、utils.py；MGraphDTA的regression/metrics.py、regression/test.py、regression/train.py及分类/filtered_davis同名入口；DGDTA的validation.py、main.py、utils.py；DeepNC的predict.py、training_validation.py、utils.py；GS-DTA的training_validation.py、training.py、utils.py。完整路径及静态行证据见每方法inventory。
