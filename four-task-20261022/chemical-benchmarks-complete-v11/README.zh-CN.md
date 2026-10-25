# v11：肽—蛋白质 pKd 化学基准完整结果

本包保存T3内的pKd化学基准：扩展版与覆盖对照版各230个已选定模型，全部使用固定划分和随机种子0–9。两个版本的结果、全部候选训练历史、逐样本预测、冻结数据和评价代码分开提供。它不表示最初八篇方法或四类任务全部完成；DTA历史结果见[版本索引](../LATEST.md)。发布事实以仓库LATEST、Release及发布核验收据为准。

近期化学模型是两篇论文的三个权重变体：PeptideCLM-2 Hybrid-small、PeptideCLM-2 MLM-small与PeptideCLM2025。这里使用透明的亲和力回归任务适配，不把三个权重写成三篇独立方法，也不冒充作者原数据上的原始成绩。

## 数据与实际完成范围

|版本|训练／验证／测试|冻结头：候选→选定|全微调：候选→选定|选定TEST逐记录预测|
|---|---|---|---|---:|
|蛋白表示补齐版，主结果|531／570／685|400→200|60→30|157,550|
|原覆盖对照版|497／495／656|400→200|60→30|150,880|

共460个选定模型种子单元，分别属于两个嵌套数据版本。两表1648＋1786=3434是表行数相加；独特观测并集为1786。685测试包含原656测试，两个版本不能当作独立外部验证，也不能把不同分母的分数之差直接解释成方法改善。

扩展来自修复旧配对AA20准备时漏编码的47个合法蛋白，恢复138条既有非标准肽观测；没有新增实验，也没有按标签或模型错误筛选。12个超过固定2048残基限制的蛋白对应42条记录仍排除，原因保留。父级全局v3为554／579／695；原source闭包训练0，继续blocked。补充比对检出的两条VAL–external同源边使5条标准VAL隔离，没有移动到训练。

|主结果化学层|训练|验证|测试|
|---|---:|---:|---:|
|标准肽|440|425|572|
|非天然残基／D型／骨架改动|16|48|45|
|PTM|54|70|41|
|非天然与PTM混合|21|25|20|
|其他非标准|0|2|7|

[两份完整冻结CSV与许可](data/DATA-LICENSE-AND-PROVENANCE.json)保留原24列、序列、完整SMILES与GT原字节。来源为Zhu等人的[PPIKB Figshare v5](https://doi.org/10.6084/m9.figshare.31082407.v5)，CC BY4.0，处理与归属说明随数据提供。所有1786条的蛋白输入都是`database_reference_not_certified_assay_construct`；实验构建体未逐条认证。

## 比较与结果入口

扩展版全微调Hybrid的总体MAE为1.57864±0.02782 pKd，Morgan ET为1.58880±0.01552；差约0.01 pKd。PTM41条和混合20条上，三个全微调模型都未超过Morgan ET；纯非天然45条上冻结Hybrid ET优于三个全微调。各配置十种子的总体R²均值均为负。总体小幅改善不能概括成非天然或PTM任务已解决，全部不利结果均保留。

四个冻结表示均使用完整肽SMILES与同一蛋白ESM2-t6-8M的320维缓存。Hybrid／MLM总维数832，2025为1088，手性Morgan为2378（2048位指纹＋10个描述符＋320蛋白维度）。每个表示配constant、Ridge、RF、ExtraTrees、HistGB，各两候选；验证MAE选优。全部Morgan五族保留，不根据TEST只挑有利对照。

CLM2环编号分词修复与2025的`cccc→cc,cc`分词修复各有独立版本／配方，保持原词表、原权重和原SMILES，旧可编码输入的token ID不变。2025使用显式适配的masked mean（包含CLS／SEP），不称作者原生pooling。初始UNK失败与后续修复的历史保留；有限化学canary通过只证明这些输入可区分，不证明所有非天然／PTM都能准确预测。

全微调更新化学编码器和普通回归头，蛋白ESM保持冻结；两学习率1e-5／3e-5，batch8、最大30轮、patience5，验证选择检查点。扩展60候选实际共480轮，全部由patience5停止。它与冻结头共享数据、标签、种子和蛋白输入；容量、维度、训练开销与调参内容不同，不是等FLOPs比较。

- [扩展版全部2300条逐种子分层指标](evidence/expanded-final/results/expanded/COMBINED-2300-per-seed-metrics.actual.csv)
- [扩展版十种子均值与样本SD](evidence/expanded-final/results/expanded/COMBINED-230-ten-seed-summary.actual.csv)
- [155组宏指标](evidence/expanded-final/results/expanded/COMBINED-GROUP-MACRO-230-per-seed.actual.csv)
- [全微调与全部五类Morgan的逐种子差值](evidence/expanded-final/results/expanded/FULL-vs-ALL5-MORGAN-1500-paired-seed-differences.actual.csv)
- [完整可读结果报告](evidence/expanded-final/reports/expanded/REPORT.zh-CN.md)
- [固定协议与解释范围](evidence/expanded-final/reports/expanded/COMPARISON-AND-LIMITS.zh-CN.md)
- [覆盖对照版2300条指标](evidence/accepted-control-and-heads/results/control/2300-per-seed-metrics.csv)

报告MAE、RMSE、Pearson、Spearman、R²与bias；未定义项保留为空／null。标准、纯非天然、PTM、混合与其他类别分开；历史字段`NC_all`包含全部非标准类别，也包括PTM。21条化学注释冲突保留，另报排除flag后的664条敏感性结果。十种子SD是固定数据上的训练随机性，不是生物重复或数据置信区间。协议写于冻结头结果已知、全微调未完成时，不称盲预注册。

## 完整日志、预测与权重索引

[Release资产清单](RELEASE-ASSETS.json)列出逐项大小、SHA和下载地址：两个版本的全部冻结头与全微调历史、所有候选验证、选定VAL／TEST逐ID原预测、训练轮次、实际成本与资源事件，以及原科学输入／生成缓存。预测CSV含许可范围内的原GT，保留原字节；不是只公开均值表。

每套冻结头的4个进程产生4份stdout＋4份stderr，200份`candidates.json`记录400个候选，不是400份独立进程stdout。正式扩展60训练没有科学失败；两次资源门零spawn延后、三代控制器及历史快照均保留。首个选定TEST的NFS等待后在460.112秒内自然成功，处于原deadline内，不能写成timeout。IO-local只是未执行备用PREP，原执行链没有因此换源。

其他已发生的成本内存失败及不利结果保留。资源日志中第三方用户名、无关进程原命令与设备UUID伪名化；数字PID、Unix UID和资源用量保留。每文件列原SHA、公开SHA和变换记录。大检查点保留原生产及已核镜像SHA索引；没有为打包载入它们，也没有声称全部大权重已上传GitHub。

## 代码与复核层级

[执行源码索引](source/execution/SOURCE-MAPPING.json)恢复39份自有科学源／必要JSON的原SHA；[评价源码索引](source/evaluation/SOURCE-MAPPING.json)包含实际独立审计、230汇总、组宏、Morgan成对比较与保存预测重算代码。第三方源码、tokenizer和上游权重按[官方固定revision／SHA清单](UPSTREAM-INPUTS-LOCK.json)获取，不给所有第三方材料套用统一许可。

描述统计的`describe_labels.py`保留原字节，按原项目相对布局运行：将本包`data/expanded-frozen.csv`置于重建树的`publication/chemical-benchmarks-complete-v11/data-component-v1/expanded-frozen.csv`，从该项目根运行恢复后的脚本。公共跨平台结果重放入口是下面已经实测的`helpers/replay_public_predictions.py`。

已完成：从原CSV重算完整指标；原源码与冻结manifest／spec／cachebinding守卫、原配方及五份生成缓存恢复验真。尚未在一台全新机器上从公开归档重新完成NN训练。`scientific_path_bridge.py`的已有验证覆盖Path层元数据／NPZ／守卫，不等于验证了Torch或safetensors的所有直接字符串路径。

下载全部Release资产到同一目录后，可在本包目录执行纯数值复核：

```text
python helpers/replay_public_predictions.py --cohort data/expanded-frozen.csv --heads ASSET_DIR/expanded-heads-all-candidates-logs-and-predictions.tar.gz --fullfine ASSET_DIR/expanded-fullfine-all-candidates-logs-and-predictions.tar.gz --expected-table evidence/expanded-final/results/expanded/COMBINED-2300-per-seed-metrics.actual.csv --expected-macro evidence/expanded-final/results/expanded/COMBINED-GROUP-MACRO-230-per-seed.actual.csv --output NEW_OUTPUT_DIR
```

该入口只读固定数据与已存预测，检查230模型、0–9种子、2300化学分层、155组宏与全部Morgan对照，不载模型、不重训；数值对照容差为1e-10，原指标表和原预测仍按原字节提供。原资源来源审计需要原始镜像SHA上下文；公开清理后的资源JSON不能冒作原字节通过旧SHA检查。

## 外部验证和任务边界

当前完整认证的独立化学外测gold为0。历史六点中2018两点存在荧光标记实体与未标记SMILES疑似错配，仍隔离；剩余2017四点仅为条件诊断参考，不认证gold。不能把未标记IC50换算为Kd补标签。基础模型历史预训练实体暴露保持未知。

本包训练的是Kd点值的pKd回归；Ki、IC50、二元相互作用、接触／界面以及突变效应需各自标签和合同。完整肽化学可被表示，不等于蛋白侧PTM、所有实验实体或所有化学改动已认证。最初八篇和四任务的其他状态仍按[历史与当前任务索引](../LATEST.md)记录。
