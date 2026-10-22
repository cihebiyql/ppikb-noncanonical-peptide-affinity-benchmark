# NC主表 MAE 图（准备版）

当前仅脚本与纯合成机械测试就绪；actual-v1 尚未生成，未读取真实指标、金标、预测、模型或训练标签。

root审核报告汇总表并绑定SHA后，运行：

```text
python reporting/figures-v1/plot_nc_mae.py --root-reviewed-aggregate --summary REVIEWED_DIR/ten-seed-summary.json --summary-sha256 REVIEWED_SHA256 --output reporting/figures-v1/actual-v1 --wall-seconds 180
```

现冻结reporter实际文件名为summary.json，也接受此名；它与ten-seed-summary.json使用 FIELD-MAPPING.md 的同一summary数组schema。flag在打开输入前检查。每份绘图输入必须由root审核；脚本不会寻找或读取raw数据、预测及模型。

从完整summary数组筛取PPIKB-internal / NC_core / row_micro / MAE，排除三个reference，验证恰好24组＝6方法×2面板×2训练队列，completed=defined=10、missing_seeds为空、n_by_seed每seed为对应303／332、n_unit=observation_rows、均值和样本SD有限且非负。缺失、重复、未知身份、不一致分母或未定义值均拒绝。顺序固定GraphDTA-GIN、MGraphDTA、DGDTA-CL、DeepNC-GEN、GS-DTA、RF；没有最佳seed选择或均值/SD重算。

图为两面板分组柱，灰阶与纹理区别两训练队列，共享y刻度；四边框、运行时serif字体回退和显式数字格式。误差条为10训练seed样本SD，非生物重复或生物置信区间。300dpi PNG/JPG及矢量PDF/SVG保存在独立输出目录的figures/。00_data_health.md先完成24组结构校验；normality/VIF不适用于这张描述性汇总图。

process_data/保存精确CSV、原24组JSON，以及现成openpyxl可用时的XLSX。XLSX同时保存数值列和mean_original_json/sample_sd_original_json文字列，保证原JSON值可精确追溯。receipt记录输入SHA、脚本SHA、库版本、字体、全部产物SHA；中文caption单列。仅单张图PDF，不生成额外完整方法报告。

机械测试：`python -m unittest discover -s reporting/figures-v1/tests -p test_plotter.py -v`。所有合成fixture仅置于tests下的临时目录，输出标记SYNTHETIC，退出后自动删除；不写actual-v1或app。没有安装新依赖。
