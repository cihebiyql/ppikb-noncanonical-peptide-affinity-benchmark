# CPU手工特征基准

新运行仅使用本轮data/view_manifest.json的冻结任务视图。模型为常数/频率先验、线性(Ridge或逻辑回归)、RandomForest、ExtraTrees、HistGradientBoosting，共五类，每类两个预声明候选，种子0–9。常数及Ridge等确定性模型在固定数据分区上可能得到相同结果，仍保留十次运行，不把重复拟合称为十个独立生物实验。

每条序列用20AA组成、原始非20字母比例、log长度、空串指示和64桶确定性二肽频率编码。肽和靶标分别编码；效应额外包含母体与改动差特征；位点使用序列位置、残基身份和局部7残基窗口，禁止输入距离或真接触。非天然残基/PTM化学身份不由该手工序列表征完整编码，小写字母不偷偷转换成标准残基；作为序列信息受限对照披露。

训练只读取train；StandardScaler只拟合train。回归按validation MAE选优，分类按validation AUPRC选优(单类验证以负Brier选择)，分类阈值仅按validation MCC在0.1–0.9的预声明网格选择。test/external只对胜出模型评分。保留所有候选权重和validation预测、十种子测试预测、分组/化学类别指标与mean±SD。单类AUC、常数相关性等未定义项保持null。资源限定CPU两线程，无GPU。

运行入口：`run_cpu_baselines.py`。`independent_recalculate.py`从保存的预测文件重算指标，`test_cpu_baselines.py`检验分区门槛、特征独立性及标签/原符号边界。输出是本轮新训练，不能称为八篇论文主表的复现。
