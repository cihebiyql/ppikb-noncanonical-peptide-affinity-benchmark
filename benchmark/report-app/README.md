# 本地数据与方法报告应用

当前预览：`http://127.0.0.1:2647/`。静态server只绑定loopback，PID与路径见`server-receipt.json`；不是Sites发布，也没有新建任务或定时器。

共享Data preparer建立`app/`，保留复制的AGENTS和保护壳；用bundled Node与插件预编译runtime构建，无依赖安装。内容只修改`app/src/content/report/`和`app/src/data.json`。稳定artifact ID为`report:5569696c-9519-43ed-9a7a-073a11d14850`。

当前应用包含：

- 2099 NC／7520标准对照、四个互斥NC组、可重叠细类及筛选计数。
- 真实panel/regime/chemistry筛选、训练／验证／测试分母、608冲突敏感性和参考前缀范围。
- 五篇经典／近期作者架构与必要修复；另计RF冻结2469维、200树与leaf2/5配置。
- 原75 PTM与另13（8非PTM＋5标准）的独立性边界；28条来源证据。
- `metrics.rows=[]`明确空态。没有任何示例／虚构成绩。

状态栏内104/200等是协调者当轮指令的静态背景，明确标注非实时；它不随训练更新，也不是成绩。最新RF配置已仅从允许的四份冻结元数据补齐，未打开真实模型、selection、标签、矩阵或指标。

## 构建

先阅读`app/AGENTS.md`。使用：

```powershell
& 'C:\Users\ciheb\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' 'C:\Users\ciheb\.codex\plugins\cache\openai-curated-remote\data-analytics\1.0.11\scripts\data-app.mjs' build --project-dir 'D:\work\科研工作台\research-tasks\peptide-binding-nc-benchmark-20261021\report-app\app' --separate-data
```

共享builder核验保护边界，生成`app/dist/index.html`、完整内容寻址snapshot sidecar及`data-app-build.json`。server固定服务整个dist，重建后URL不变。不要用另一份HTML代替，也不要改共享runtime绕过构建检查。

## 后续成绩

`FUTURE_METRICS_SCHEMA.md`描述导入字段及审阅manifest。`import_reviewed_metrics.py`仅接受独立核算并审阅、全部选择冻结之后的聚合CSV/JSON；它备份旧snapshot、保留artifact ID和其他证据，只更新metrics查询。之后设置完成状态、共享重建，并在原浏览器tab复核。不要重新运行初始化脚本覆盖已经导入的成绩。

## 验证与剩余检查

`verification.json`核验真实计数、定义与组件ID、来源文件scope、零性能行、未审阅导入拒绝、AGENTS原样、HTTP与HTML／sidecar哈希。root已实际浏览首版，确认首屏／真条形图／panel与regime筛选对应数值正确、空态明确；最终RF和默认tooltip绑定已更新，待root在同一tab完成最终化学筛选、窄屏和来源侧栏复核。子代理没有自行创建或控制浏览器。
