# 原出版PDF补齐：3/5

新增两份来自NIH NLM NCBI官方PMC公开AWS归档的原出版PDF。核对了文件头、页数、正文DOI、官方元数据MD5以及非作者手稿身份；没有将HTML或XML渲染成PDF。

|论文|文件|页数|SHA256|
|---|---|---:|---|
|MGraphDTA|MGraphDTA-PMC-published.pdf|18|0a445649ae97d8c2ff2a10842de18bdab946bf22c9471bd81e5a6a9ef581516c|
|DeepNC|DeepNC-PMC-published.pdf|24|401fdeeb8b777f29d38628417d71ff967883575b13381b6430843e08154dce16|
|DGDTA，先前已取得|DGDTA.pdf|15|6cf263a8a267f0ca5f7aecdce791f57968b197c4cdff3e165ffa0925da3169ff|

GraphDTA与MRBDTA的正式DOI经NCBI ID Converter查询均无PMC记录，当前仍缺真正PDF。已有官方HTML原文可核对架构，但不能替代严格PDF合同门槛。

`oa.fcgi`的两次404分别属于两篇不同文章的一次调用。查阅[官方现行文档](https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/)后确认旧服务已在2026年8月退役，随后按同一官方归档的现行公开S3接口各取件一次。没有登录、凭证或挑战页重试。

MGraphDTA归档许可为CC BY-NC，DeepNC为CC BY；二者官方元数据均为`is_manuscript=false`。MGraphDTA的pdfinfo提示共享对象组语法警告，但正常解析18页，正文DOI匹配且官方MD5一致，未改原PDF字节。

绑定入口：`PDF-manifest-v2.json`、`primary-method-verification-sidecar-v2.json`。官方归档元数据、URL、MD5、失败历史均保留。旧版1/5报告作为历史文件保留，以v2作为当前PDF状态。
