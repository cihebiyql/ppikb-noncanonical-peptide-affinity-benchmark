# 冻结作者方法的统一训练执行器

本目录只实现训练与评价执行，不更改数据划分或作者架构。正式五个方法为 GraphDTA-GIN、MGraphDTA、DGDTA-CL、DeepNC-GEN、GS-DTA。MRBDTA保留历史smoke和可调用接口，不纳入本轮400个候选。正式实验由 root 冻结资源和输入合同后启动；本目录不会自行提交训练。

## 冻结实验规则

- 两个数据代理提供的冷划分，每种方法分别训练 NC_only 和 standard_only；没有 pooled 训练。
- 每组合 seeds 0–9，两个配置：Adam learning_rate 1e-3 / 3e-4，weight_decay=0；MSE直接拟合pKd，未标准化标签。
- 当前预注册最大20轮、patience5；每个候选按其自身域验证MAE保存最好检查点，再按验证MAE选择候选，同值按较小候选编号选择。旧CPU30轮方案只保留历史草案，未开始正式fit。
- `validation_scope=same_as_regime`：NC_only只用NC验证标签，standard_only只用标准肽验证标签；跨域测试单列。
- 本轮五个正式模型batch32，作者架构保持不变。旧MRBDTA接口仍限定batch1、累积8个独立反传，不同时保留8个计算图。
- 固定作者默认架构和dropout；训练时train()，验证/测试时eval()+no_grad()；float32、关闭TF32，记录种子、CPU线程、全部文件哈希。

## CLI顺序

1. `runner.py prepare --observations model-observations.jsonl --split panel.json --output prepared-panel`
2. `build_specs.py --panels panels.json --output specs --run-root runs --cache-root cache --methods-root ../methods --batch-size 32 --cpu-threads 1`
3. `runner.py fit --spec specs/one-seed.json --candidate-index 0`，以及候选1。
4. `runner.py select --spec specs/one-seed.json`，只有两个候选都完整成功才创建不可覆盖的selection.json。
5. `runner.py freeze-barrier --index specs/execution-index.json --output runs/all-selections-frozen.json`
6. `runner.py score --selection runs/.../selection.json --holdout-spec specs/panel-score.json`

第1步split格式为 `{split_id, train:[record_id...], validation:[...], test:[...]}`。第2步panels格式为两个 `{split_id,directory}` 元素的JSON列表。执行器不替代数据代理的化学近邻、同源、来源泄漏审计。

原生 frozen-v1 数据由 `adopt_frozen.py --frozen ... --output ...` 直接适配。控制器打开共享labels.jsonl容器，但只物化各panel训练/验证标签，测试输入无pKd；正式score阶段才从密封标签容器提取对应测试ID的pKd。不能把控制器准备流程描述成从未打开全标签文件。`formal-specs-v2/` 是旧CPU30轮绝对路径草案；`formal-specs-v1/` 是更早的相对路径草案，均未启动、不用于当前运行。

上段v2是旧CPU30轮绝对路径草案，同样保留而不运行。新GPU方案应在root提供WSL实际目录后生成独立的 `formal-specs-gpu-v3/`，不得覆盖或重用v2规格。GPU builder参数为 `--device cuda:0 --gpu-explicitly-authorized --cpu-threads 2 --batch-size 32 --max-epochs 20`；省略device时默认CPU。

GPU worker先验证显式授权和CUDA可用性，再构建／迁移模型；CUDA不可用时失败，不暗中改为CPU。可选 `gpu_allocator_budget_bytes` 通过PyTorch allocator fraction限制分配预算，builder默认3 GiB。该限制不覆盖CUDA context或进程RSS，root launcher需另限单卡最多3个自有并发进程、每进程RSS4GB并监测实际显存。仍为float32、TF32关闭、seed固定、deterministic_algorithms警告模式；不承诺GPU逐位确定。

正式score-spec要求全局选择屏障，验证全部五方法×两panel×两regime×十seed的200个独立selection均已冻结、400个候选完成且SHA匹配，才允许开始测试评价。

prepare把原始测试记录拆成没有pKd的输入和单独sealed-test-labels.jsonl。fit spec不能带test/external/holdout键，fit和select入口只读取训练与验证文件。score是首次读取留出标签的入口，要求已有冻结selection及检查点哈希，不构建优化器。此流程是可审计的程序约束，不是操作系统访问控制。

外部集同样通过独立holdout-spec送入score；科学独立性由数据代理核查，不能仅凭文件名external认定。holdout-spec需包含 `split_id,holdout_id,input_rows,input_rows_sha256,label_rows,label_rows_sha256,output_root,methods_root,cpu_threads,batch_size,scientific_external_status`。

## 文件和结果

每候选保存started.json、完整epochs.jsonl、best.pt、best-validation-predictions.jsonl、best-validation-metrics.json及complete.json；失败则保存failed.json而不伪装成功。每个seed的selection.json冻结两个候选、最佳轮次、验证MAE、文件哈希与选择规则。测试/外测保存所有逐行预测和分层MAE、RMSE、Pearson、Spearman、R²。空组、小样本或恒定数值不能定义的指标保存JSON null，不代填0。

预测保留record/source、靶标、论文、NC/标准分层、非天然/PTM子类与冲突标志。冲突行仍参与既定训练；用同一份测试预测额外汇报剔除显式discord布尔标志后的敏感性指标，不重新训练或换测试集合选优。

编码cache以输入ID、分子、蛋白、标签和adapter目录全部Python文件哈希核验，禁止加载旧输入或旧适配源码的缓存；各mini-batch重新collate，避免Data.x污染。使用本项目自己生成的pickle缓存，不能加载不可信外来pickle。

## 小样验证

`test_runner.py` 使用临时线性测试夹具验证种子复现、指标null、域过滤、禁止pooled、fit/select不访问留出路径、先冻结再score和输入哈希。该夹具不是新增基准模型。

`performance_canary.py --contract canary.json` 只接受32条来自冻结train ID的记录，执行4次Adam更新，不留模型权重、不读取验证/测试/外部标签。合同指定主机、现成环境、CPU线程、内存和timeout；root根据收据决定正式训练资源。运行时间外推必须注明小样输入长度与正式输入分布可能不同。

`implementation-verification.json`、`canary-contracts-v1/`、`verify_execution.py` 记录的是旧CPU方案及包含MRBDTA的历史canary，不是新GS-DTA GPU方案的运行证据。新方案的GPUcanary与正式启动证据由root独立launch目录保管。
