# 最终中文报告生成器

准备模式已实现；当前交付仅模板与纯合成机械测试。生成器使用Python标准库，不调用模型、不拟合、不安装依赖。

生成空模板：

```text
python report_builder.py template --output reporting/template-v1
```

联合NN200＋RF40屏障、独立指标审计与root明确授权后：

```text
python report_builder.py actual --authorization ROOT_REPORT_AUTH.json --audited-manifest AUDITED_DIR/unified-table-manifest.json --joint-barrier JOINT_BARRIER.json --output reporting/final-v1
```

授权字段：`root_final_scientific_report_authorized=true`、`source_sha256`（本目录四源文件）、`audited_manifest_sha256`、`joint_barrier_sha256`、`deadline_unix`。模板见 authorization-template.json，默认false。尚未完成时可由root明确允许partial审计覆盖，协议见 FIELD-MAPPING.md。真实生成不在本准备任务内执行。

输出：完整报告.md（结果先行）、README.md、main-NC.csv、summary.csv/.json、metrics-per-seed.csv/.json、coverage.json、report-receipt.json，以及可选training-metadata.json。6个可训练方法与3个确定性参考分别呈现；五指标保留10种子原值、均值、样本SD与有效组数。

本轮为五个已发表架构在相同肽—蛋白数据上的重训比较，严格近三年只有GS-DTA2025；RF为普通手工特征基准，0篇作者方法。本轮先建立基准。原论文、作者代码、数据/构建体范围和输入盲区统一链接 report-preparation/方法与数据说明.md。

运行机械测试：`python -m unittest discover -s reporting -p test_reporting.py -v`。纯合成测试临时文件由测试自行创建，与任何真实科学结果目录隔离。
