# 完整数据与产物

## 存储布局

`benchmark/`镜像原任务目录。每份原文件在`manifest/source-files.jsonl`中都有path、bytes、sha256及storage字段：`git`表示随clone取得；`release`表示在分卷包内。`manifest/artifact-assets.json`列出精确分卷名、顺序、字节数与SHA256。

所有7个`benchmark-artifacts.tar.gz.partNNN`附件位于[同一Release](https://github.com/cihebiyql/ppikb-noncanonical-peptide-affinity-benchmark/releases/tag/v1.0.0)。按清单顺序拼接可得到gzip压缩tar；解开后与Git的`benchmark/`目录合并。提供的恢复器流式下载和提取，不需要先把多个分卷拼接成额外的大文件。

```bash
python scripts/restore_artifacts.py
python scripts/restore_artifacts.py --verify-only
```

权重、缓存、逐条预测、大型审计JSON和完整逐种子指标保留原字节。自行生成的研究二进制不会因文件大而省略。确定性参考规则的10种子记录也保留，数值相同不代表10次独立拟合。

## 原始来源与可复用代码

`datasets/PPIKB-v5/`保存CC BY4.0的完整原始工作簿、官方许可元数据和下载校验记录；`benchmark/data-protocol/`保存本轮2099NC＋7520标准肽的处理、分组和拆分资料。

`scripts/restore_upstream.py`使用`permissions/fetch-lock.json`中的官方ZIP URL、固定commit和SHA恢复上游代码。下载原代码不等于取得再分发许可。仓库中的自编适配、入口、修复说明及有明确许可的原作者组件可直接浏览。

第三方保护运行时、环境依赖、无明确许可的源/PDF/上游混合原档，以及可再生Python字节码的逐文件排除理由在`manifest/excluded-files.jsonl`。这些文件仍在原本地目录；原链接和身份清单已保留。

原报告应用依赖受保护的供应商运行时，公开包保留自编内容、聚合数据、静态图和Markdown报告。公开README与`docs/基准结果与复现说明.md`使用GitHub相对链接；`benchmark/`中的原始文件保持其已审计SHA，包括原本的本地路径。

## 完成与失败记录

真正完成状态为`benchmark/reporting/delivery-v1/FINAL-CLOSURE.json`与`benchmark/review/postscore-driver-v2/runs/actual-v2/POSTSCORE-AUDIT-READY.json`。历史状态、两次技术中断、旧审计与行政路径失败均保留。`support/batch/summary-rows.json`只对应这次五篇架构适配重训，原其他批次未并入。

上传打包仅复制、压缩、哈希和核验，科学数据、模型与原冻结代码没有更改，也没有重新训练或挑选测试结果。
