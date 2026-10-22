# 额外传统RF基准：准备阶段

本方法不是创新模型、不是作者论文复现，论文贡献计数为0；不替代五篇NN工作，不修改原NN200 selections／400 fits／600 scores合同。

## 固定特征与模型

2469维float32：全分子（所有片段）Morgan radius2／2048bit／includeChirality=True；蛋白原始1000字符前缀AAC20＋相邻二肽400＋有效前缀长度1。长度不是full-reference长度。AAC分母为完整prefix长度，DP为L−1；unknown不计入标准氨基酸计数、不压缩或补齐，仍保留在长度分母、打断pair，L=1的DP全0。

输入直接取canonical_isomeric_smiles或peptide_smiles，RDKit sanitize=True/removeHs=False，不调用MolToSmiles改写，不去盐、中和、补手性或修复分子。只使用已给手性；未知手性不补，也不保证2048bit无碰撞。所有规则见feature-spec-v1.json。

RandomForestRegressor为现成sklearn实现：200 trees、sqrt、bootstrap=True、max_depth=None、n_jobs=1、random_state=seed。唯一两候选min_samples_leaf=2／5，其他参数取实际安装sklearn默认并全部显式冻结于installed-assets-v1.json。源码原件、编译tree模块、Morgan原生模块和版本SHA均留档。

## 数据与划分

固定X只读frozen9619 label-free inputs、旧external75及独立supplement13；没有y、没有学习型变换。X-final-manifest-v1.json绑定全部输入与矩阵／IDs／audit SHA。原始分割不动；representation-alias-audit-v1.json只数特征别名，无标签和性能驱动筛选。

40 RF units=两panel×NC_only/standard_only×seeds0–9，80候选fits。同regime train和validation严格匹配冻结IDs。真实fit只可从execution/prepared-panels-wsl-v3/<panel>/train.jsonl和validation.jsonl取标签，禁止从全frozen labels.jsonl读训练标签。全局无标签X可共用，因为仅固定规则，无数据拟合。

## 未来真实fit接口（目前未授权）

`python rf_runner.py fit --spec specs-v1/ONE_UNIT.json --authorization ROOT_NEW_BOUNDED_AUTH.json`

一个unit依次训练两个预声明profile；candidate0完成即保存model.joblib、全部validation逐行预测和complete.json，再开始candidate1。两者都成功后按本regime validation MAE选优，同值选较小candidate_index。保存selection.json与顶层complete.json；后者引用selection SHA。失败保存failed.json及所有已完成候选。没有用test或外源做选优。

root的新授权必须显式root_real_RF_fit_authorized=true、精确spec SHA白名单、source_sha256、原deadline_unix。尚未签发的模板默认false，不能开始真实训练。资源由独立外部supervisor限制CPU4×1、每worker RSS2GiB／1800秒、n_jobs1、CUDA空；线程环境OMP/MKL/OPENBLAS均1。worker不充当budget watchdog。

JSON落盘使用PID/thread/UUID唯一tmp。对短暂PermissionError按0.05到1秒有界重试，持久错误仍fail-closed并保留tmp；不能在资源监督线程阻塞clock/RSS。新control/rf-launch-v1由另一个代理独立负责，旧NN脚本不改。

## 联合屏障及未来评分

`python rf_runner.py rf-barrier --index specs-v1/task-spec-index.json --output RF40_BARRIER.json`

`python rf_runner.py joint-barrier --NN-barrier ORIGINAL_NN200_BARRIER.json --RF-barrier RF40_BARRIER.json --output JOINT_200_PLUS_40.json`

RF40原子屏障不能替代或降低NN200门槛。joint-barrier重新核原NN200与RF40完整格、selection SHA，并链接两个原始barrier SHA，不改旧文件；独立NN scorer仍保持原代码，由root高层授权joint后再调用。

NN200路径和index SHA以root接受的administration/io-recovery01/execution-index-v5-recovery.json（c7b3bde68c9a741c0ac3f255a825e4a55dd7234e2b4e6d48f212fee8d5609ab1）为准，包含隔离的__io_recovery01替代slot。旧v4 failed证据保留，不能强求其全部完成；NN科学协议、模型、data IDs及200格不变。

`python rf_score.py --authorization ROOT_POST_JOINT_SCORE_AUTH.json --joint-barrier JOINT.json --selection ONE_RF_SELECTION.json --spec score-specs-v1/ONE_DATASET_PANEL.json`

仅在原NN200＋RF40均冻结及root明确评分授权后加载RF权重。先用固定X保存blind-predictions.jsonl及blind-complete.json，再首次hash/open gold。全部输入metadata、strata、608冲突flag、blind原预测、来源和SHA保留；指标复用已冻结evaluation/metrics_stable.py，外部67/8/2和NC8/std5交独立review重算。

6份metadata score-spec明确两panel×内部/75/13输入映射。RF40 selections对应120 score runs／53160行；NN600／265800和deterministic参考360／159480独立列账。

## 本轮证据

仅完成无标签X、源码/版本/协议/spec准备和纯合成机械测试。测试中RF确在32个人工molecule/reference特征与随机标签上拟合、序列化和验证流程；这些是临时合成fixture，删除后不进入实际40unit结果。真实RF fits=0，真实gold/已训权重读取=0，真实holdout predictions=0。

机械测试包括两profile、seed复现、joblib回读、完整synthetic unit过滤与保留、授权拒绝、残缺joint阻断、暂态／持久文件分享冲突和写重试期间独立budget tick。没有依据任何真实表现改profile或决定是否采用。
