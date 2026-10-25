# 评价与独立验收代码

本目录保存实际使用或为最终验收冻结的自有代码，逐文件执行源 SHA 与公开 SHA 见 SOURCE-MAPPING.json；最终“实际使用”以最终审计收据记录为准。恢复助手按原项目相对目录恢复原字节，邻接 import/runpy 关系保持。源中的项目 IO 常量保留，用执行期 scientific_path_bridge 映射；不修改数据 SHA、模型身份或数学检查。

- audit_training60_expanded_local_v4.py：检查 60 候选、570 条验证预测、训练轮次及验证选择，TEST 不参与。
- audit_selected30_expanded_local_v3.py：检查 30 已选模型的 685 条测试预测、10 个化学分层和 155 组宏指标。其原历史 docstring 的 selected20 文本不改变实际 30 项检查。
- combine_expanded30_and200_v2.py：检查 230 配置种子单元、2300 分层指标，以及全部 5 个 Morgan 头的成对对照。
- build_expanded_readable_report_v3.py / summarize_training60_stops.py：从已审证据生成报告和停止轮次汇总。
- audit_results.py / audit_external_coverage.py / shared_metrics.py / evaluate_saved_predictions.py：冻结头验收、覆盖、指标及保存预测重评。

原执行来源审计要求原始 SHA 对应的完整镜像及资源合同。公开日志的用户名、命令与设备 UUID 已伪名化，公开 SHA 因此不同；不得把清理后的日志充作原字节通过原资源 SHA 检查。原始审计收据与逐文件 source→public 映射提供可追溯证据。原 Windows CPU1/IDLE/Job2GiB/180s guard 也保持；它是执行环境条件，不是科学模型逻辑。

跨平台的保存预测数学复核使用 evaluate_saved_predictions.py（标准库，无 Torch、权重或重训练），以公开原字节预测 CSV 和固定数据表为输入。完整候选选择、所有 seed、分层和组宏检查由最终公开重验入口补齐。原资源来源审计与公开数学重验应分别报告。
