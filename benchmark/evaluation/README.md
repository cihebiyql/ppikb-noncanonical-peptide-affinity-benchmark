# 留出集固定X缓存与延后评分

本目录独立于冻结的execution/runner.py、作者methods、训练输出及数据合同。固定X缓存只读取label-free inputs，编码器所需的pKd=0仅是Data.y占位，既不是实验标签也不用于数据拟合。

## 当前缓存范围

- 原v1：source test 1,039条、target test 1,443条、external75 75条，各五方法，共15缓存。
- 独立补充：supplement13 13条（8 synthetic_D_backbone、5 standard20_control），各五方法，另增5缓存。其449 aa heavy reference保留，不能称靶标家族冷泛化。
- `authorized-manifest-v2.json`前15个job与原v1逐项相同；13与75没有合并。原v2继承的顶层IgG13_included=false漏更新，真实有效值为true，纠正记录在`manifest-v2-metadata-correction.json`；原活动manifest及所有输入、签名均保留不改。

缓存签名为SHA256(schema、method_id、实际input文件bytes SHA、adapter Python树SHA、占位0)。同一方法／输入的X可被所有seed和训练regime重用。缓存producer记录Node23 Torch2.6／PyG2.6.1／RDKit2024.03.2；模型训练／预测的GPU运行时版本另记，不能混写。

`feature_cache.py`拒绝带gold键的输入，逐批证明全部Data.y为0；仅调用原始encoder和collate，不构造或运行模型。Node23合同为最多8单核、nice15、RSS监视4GiB、每job1800秒、CUDA不可见。本次pool用7个编码worker，另留1个CPU给明确批准的训练32条随机模型验证。

`forward-y-parity-receipt.json`来自五个真实作者随机初始化模型（seed314159），只使用已批准TRAIN32；真实TRAIN y、占位0、任意123.456三组预测在相同batch精确相同，X字节相同，单条／batch／排列测试通过。没有读真实留出gold、selection或已训权重，也没有对真实留出做forward。此证明的adapter树SHA会在正式scorer中重检。

## 两层评分授权

当前所有真实评分均未授权。`authorization.example.json`默认false，不能执行。

1. 全部200 selection冻结之后，root签发允许`barrier_audit`的授权。运行：

   `python score_cached.py audit-barrier --authorization ROOT_AUDIT_AUTH.json --barrier ALL_SELECTIONS.json --execution-index EXECUTION_INDEX.json --output VERIFIED_BARRIER.json`

   一次完整检查五方法×两panel×两regime×十seed，核200 selection及checkpoint SHA、两候选完整性与验证MAE选择、fit spec出处。此步骤不读gold、不做模型forward。

2. root在独立score授权中固定上述audit SHA、完整barrier SHA、scorer代码SHA、冻结runner SHA及允许的score-spec SHA，再运行：

   `python score_cached.py score --authorization ROOT_SCORE_AUTH.json --barrier ALL_SELECTIONS.json --barrier-audit VERIFIED_BARRIER.json --selection ONE_SELECTION.json --spec ONE_SCORE_SPEC.json`

   每次重检当前selection/checkpoint、code/input/cache SHA和y独立证明。先eval()+no_grad()从固定X生成并保存blind-predictions.jsonl及blind-complete.json；之后才首次打开gold bytes，按record_id连接并计算指标。任何模型state变化都阻断。未建立优化器，不更新参数。

`score-spec`可任意指定dataset_id、holdout_kind和output_root；75与13各用自己的缓存、input和gold源，不能互换。未来外源67／8／2及其他子集由独立review从全部保留的元数据flag重新计算；该scorer不认证外部独立性。

## 结果与检查

正式输出保留blind原预测及SHA、joined predictions、全部原有strata/非天然/PTM/来源/构建体/608冲突flag、总体和分层MAE/RMSE/Pearson/Spearman/R²及剔除discordant敏感性。独立`metrics_stable.py`用精确all(x==x[0])恒定判断，修复[0.1]*3造成伪相关／巨大负R²的问题，未定义项保存null；MAE/RMSE公式和冻结训练／选优不改。完整外部细分由独立review负责。

`test_gates.py`仅使用临时合成元数据：验证无授权零文件访问、完整200格／残缺格阻断、cache身份与blind文件必须早于任何gold字节访问。实际训练32 parity单独记录。所有真正的score receipt和亲和力指标都只能在未来root授权后产生。

这里的gate是可审计程序流程，不是操作系统安全隔离。禁止修改冻结训练合同或用缓存占位0当真实标签。
