# 本轮复现行政准备

本目录只准备本轮 NC2099 亲和力比较的合同和证据格式，不执行模型、不改旧结果、不登记新论文编号。正式标准与 validator 仍使用 [复现流程与验收标准](../../../复现/规范/复现流程与验收标准-v1.md)，不复制另一套放行规则。

## 根代理需补齐的真实信息

1. 至少五个不同前人论文的稳定任务 ID、DOI/版本、PDF 与 SHA、官方代码 commit/许可证、旧任务和运行 ID。五个随机种子、五个头部、五种普通回归器均不能替代五篇论文。代码适配与原论文全表复现分开声明。
2. 每个模型非天然残基/PTM输入的真实处理方式与信息保留审计。缺失/未知字符不可映射为普通氨基酸后声称支持非标准化学。
3. 最终入组的原始记录清单、唯一实体/重复测量组、化学分层、标准对照、split 与泄漏审计文件及落盘 SHA。2099 是候选起点，不能先编造严格划分后的分母。
4. 本轮训练方案和所有调参候选；只在训练/验证选择模型。test 与 external 封存；外部独立性检查在模型评分前冻结。各模型使用同一 split/评价分母并同时报告输入覆盖率。
5. 真实 host、隔离环境、依赖快照、数值策略、启动命令/工作目录、数据与权重实际可读性、即时 CPU/GPU 计算进程和内存/IO/存储探测。至多三张确实可用的 GPU，不由剩余显存推断空闲。
6. 每篇针对本轮目标的首次实质处理时间、所有关联旧准备时间和适用期限。每篇十小时含准备、等待和执行；所有 seeds/splits 共用同一时钟，重试不重置。与旧62篇、平台拒绝或已到期流程的关联必须保留。Twin Peaks 和已被拒绝的原文单位调查不重试。
7. 执行前冻结合同、输入字节 SHA、日志路径、整进程树控制、内存/线程/worker预算、timeout（不得超过剩余有效期限）。根代理统一启动，结束后核验进程消失、退出码、原预测/检查点/指标/失败和 SHA，再提交 result-record 复核。

## 草稿生成

复制 `campaign-config.skeleton.json` 为新的配置文件。填入 `methods`、`splits`、`training_regimes` 和明确 `targets` 后：

```powershell
python -X utf8 administration/prepare_campaign.py --config administration/campaign-config.v1.json --out administration/drafts-v1
```

每个 `method × split × regime × seeds 0–9` 生成一个权威模板衍生的草稿合同和未执行结果模板；不覆盖旧草稿。方法条目可携带 `identity/code/models/environment/resources/execution/timing/restriction_check`，直接继承同名标准字段。split 条目携带 `datasets`，training regime 只保存真实训练口径，不推断模型命令。

生成文件永远 `is_template=true`、`contract_status=draft`、`actual_runs=0`。根代理在真实方法和资源就绪后生成另存的正式冻结合同，运行权威 validator；不得将草稿状态改成执行成功。

```powershell
python -X utf8 D:/work/科研工作台/复现/规范/validate_reproduction.py --contract <正式冻结合同> --check-files
```

必须读取实际 `valid_for_execution` 与检查细节。外机引用在本机 validator 中可被标为跳过，执行机仍需真实复核，不能当作已经 hash 验证。

## 可复用的旧运行基建（只读定位）

- `../../peptide-binding-expanded-corpus-20261021/administration/windows_supervisor_v3.py`：现成 Windows Job Object 整树限制、合同/输入 SHA 校验、launch probe、stdout/stderr、timeout、退出收据。它**禁用GPU、固定两核亲和，只通过 Python runpy 启动脚本**，不能直接用作 SSH/GPU 训练调度器；本轮行政元数据记录真实内容，不夸大能力。
- `../../peptide-binding-expanded-corpus-20261021/administration/baseline-Kd-source-cold-v4/`：冻结合同、输入 manifest、supervisor spec 的参考形状，仅供阅读；旧合同已到期，不能复用旧 deadline 运行。
- `../../peptide-binding-expanded-corpus-20261021/code/baselines/runner.py`：旧普通基线调参与结果保存模式，仅是参考，不代表本轮已复现五篇前人模型。
- `../../peptide-binding-expanded-corpus-20261021/catalog/run_native_inference_v2.py`：旧原生推理资产入口参考；输入/任务语义需新审核，不默认支持非标准化学。

## 结果保留要求

`result-tables.schema.json` 描述逐样本预测、逐 seed 指标与所有调参候选。`result-record.template.json` 仍以权威模板为准，补充表不替代正式运行收据。

至少保留全部 seeds 0–9 的超参数搜索记录、最佳配置、checkpoint/权重、验证和测试逐样本预测、化学分层和整体指标、环境/数值策略、日志与失败。先按 seed 报告，再给十个 seeds 的均值/样本标准差；不得只报最佳 seed。重复预测十次不能称为独立重训十次。非天然残基、PTM、两者混合、标准对照、化学身份未解诊断五层分开，不重复累计混合样本。

新目标使用原有模型在新数据上的受控训练比较，声明为该范围的复现/适配；原论文主表数值若不同数据端点应写 `not_comparable`，不伪算复现误差。外部候选缺少原始 DOI、实际化学身份、测量条件或构建体时，不能提前称独立金标准。

## 冻结数据事实第二版

`campaign-config.frozen-data-facts-v2.json` 与 `drafts-frozen-data-facts-v2/draft-index.json` 已采纳数据所有者的 `frozen-v1/manifest.json`，用真实面板名 `source_peptide_dependency_cold`、`target_reference_homology_cold`，以及真实五层 `synthetic_D_backbone / PTM / synthetic_and_PTM / other_NC / standard20_control`。每个草稿包含 all、五层、NC_core 的五指标共35个端点，分母来自冻结的 summary。历史草稿第一版未覆盖。

源依赖面板实际 train/validation/test=7540/1040/1039；参考同源面板=6733/1443/1443。前者巨型依赖组件使70/15/15不可达，合同保留实际比例；不拆分依赖组件凑比例。

`freeze_contracts.py` 读取 `adoption.skeleton.json` 形式的真实字段覆盖，默认只检查；增加 `--freeze` 后也仅签发中央 validator 实际允许的合同，永不执行命令。输出必须是 administration 下的新 revision，不能覆盖旧合同；缺PDF、身份、资源、输入、期限等门槛的单元保存未签发草稿和中央报告。没有任何跳过PDF或改写deadline的实现。

```powershell
python -X utf8 administration/freeze_contracts.py --adoption administration/adoption.real-facts-v1.json --out administration/formal-v1 --freeze
```

在 adoption 的 `draft_index_path` 指向第二版；shared、methods、splits、units 分别填写共享、模型、面板与逐运行事实。真实 runner 单元应由 root 的 `execution/run_unit.py` 串行 fit0、fit1、select；holdout score 在选择冻结后另阶段执行。正式启动仍由根代理即时核对远端SHA/资源/剩余时间，中央校验中跳过的remote引用不等于远端验证完成。
