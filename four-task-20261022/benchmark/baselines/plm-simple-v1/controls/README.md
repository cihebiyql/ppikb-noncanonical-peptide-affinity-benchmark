# 与ESM精确同cohort的原手工序列对照

**已完成**：额外150个正式选中条件、300候选、300份权重，1519个远端产物逐SHA回流本地；全部同seed/同ID配对及独立复算见 `RESULTS.md` 和 `DELIVERY-RECEIPT.json`。

目标是排除原ESM与全量手工模型使用不同eligible训练/验证/测试范围这一差别。直接复用ESM的同字节CSV和同ID：亲和力每面板7419行，source5890/771/758，target5203/1087/1129；silver效应2222行，1923/170/129。原全9116观测传统主轨保留，不覆写其结果。

原`cpu-baselines-v2`的AA20组成、未知字符比例、长度和64维二肽hash，以及原五类模型、每类原两个候选保持不变。手工亲和力174维，效应435维。原序列字段与ESM raw输入已逐行核对无差异；原手工效应targetWT/targetMUT也与ESM同靶标完全一致。模型仅表达字母序列，未编码PTM/D型化学身份。

所有0–9种子使用同一固定split；训练集拟合scaler，validation MAE选候选，完整保存两候选权重/验证预测/选中测试预测。没有测试集调参或选择性p值。运行前另有30次仅训练行的runtime canary，与150个正式选中条件/300候选拟合分列。

主比较在与ESM相同的Node23/sklearn1.4.2/numpy1.26环境进行，按view、模型家族、seed和精确test row_id逐项对齐CSV64标签与端点。常数头在两套表示下应逐元素一致，这也是身份检查。输出每种模型/分层的两侧指标、手工−ESM成对差值与十种子的均值/样本SD；不计算显著性p值。

这是方法配方的受控cohort比较，不能称为纯encoder因果实验：原手工Ridge保留auto求解器，ESM是LSQR；手工效应布局有mutant/target/WT/delta/target-delta，ESM是WT/delta/target。历史全量手工在Windows/sklearn1.9/numpy2.4训练，其同ID成绩仅作独立历史参考，不能将差值纯归因筛选。

资源：DTA owner分配core25+30及保护siblings57+62；三帧每指定核idle≥60%、全局≥40%、OS可用≥36GiB、UID RSS加3GiB≤80GiB后才准入；nice15、CPU2、≤3GiB、GPU0，队列1800s/整PGID运行3600s有界。任务结束释放CPU槽。

`comparison-protocol.json`与`execution-contract.json`冻结实际代码/输入/授权SHA；`adaptation.diff`仅包含隔离路径及保存特征矩阵。原远端指标收据及另存的本地复算均保留，评分配对没有新增fit或forward。
