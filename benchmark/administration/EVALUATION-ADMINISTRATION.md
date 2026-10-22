# 评分阶段与结果归档

权威规范第5节允许每合同多个数据和端点；第6节要求保留各阶段真实收据。因此本轮使用 **200份评价阶段合同，每份绑定3次评分**，保存600份独立评分收据。内部总248200行、主75集15000行、补充13集2600行，共265800行。没有600份独立行政合同的要求。

## 当前仅准备

- `score-spec-assets-v2/`：30份共享metadata规格，来自20个固定X缓存。内部10份，外源75与13分别按两个panel各5份。精确dataset ID为 `source_test / target_test / external75 / supplement13`，所有spec显式固定selection panel。`spec-cache-identity-verification.json`绑定所有spec SHA、20份原始cache manifest SHA、input registry规范路径及输入SHA。
- 原cache metadata只有input SHA，没有input path；实际路径依据冻结`authorized-manifest-v2.json`，sidecar明确记录这个证据边界。未修改缓存或冻结scorer。
- `evaluation-drafts-cache-identities-v3/`：200份未签发合同，采用S299–S303和原训练合同/原时钟。每份70端点：内部35；75的all75/primary67/conditional8/reference-cold2共20；补充13的all13/8NC/5标准共15。15个外部细分指标来自独立review，不能用all75替代。
- 所有准备仅读取代码和JSON metadata；没有读取raw gold、raw input、pkl、selection、checkpoint或预测。准备spec不构成真实评分授权。

## 签发前填齐

复制`score-spec-assets-v2/evaluation-plan.prebarrier.json`为新revision，只在全部400fit/200selection屏障成立后补齐：

1. `root_authorized_after_barrier=true`；授权、完整屏障、全200检查点audit的真实`{path,sha256}`。score授权须pin冻结4模块、runner和允许的30spec SHA。
2. 每unit实际selection引用、checkpoint路径/SHA。模型asset仅在与root实际全200检查点字节audit对应坐标/selectionSHA吻合时标complete；真实WSL路径按Windows行政器的remote引用保存，不伪称行政器重复读取了权重。
3. 最终launcher3、launch3、scorer4、runner及相应方法py/vocab的真实代码SHA；`evaluation_stage`引用须与后签发binding完全一致。
4. 每组3score共同1200秒，**actual_start+1200必须不晚于01:45Z**；CPU2、RSS4GiB、allocator3GiB、同runtime/UUID，仅1评分worker。原首次处理时钟与01:45Z不能重置。

```powershell
python -X utf8 administration/prepare_evaluation_contracts.py --plan <root实际postbarrier计划> --out <admin新正式目录> --issue
```

默认不带`--issue`只造草稿。脚本不执行模型。签发调用原权威validator，失败只保留未签发草稿/报告。授权、屏障、独立audit或实际代码未齐均拒签。无需修改冻结训练runner/spec/contracts/launch。

## 运行收据

`score_unit.py --binding <post-issue-binding>`的binding在合同和中央validation-envelope有精确SHA后由root签发，避免自SHA循环。launcher负责真实三次子进程、原日志、PID/PGID、截止、无覆盖和失败不重试。

unit-complete是尚未退出的子进程写出的，不能自称退出0。归档必须同时使用pool在wait后写的`pool-exit-verification.json`，保留真实退出码和进程树消失核验。外层pool与原训练预注册日志路径若不同，按实际原日志归档并在differences说明，不覆盖或重跑。

## 标准result-record

`archive_stage_result.py --contract CONTRACT --evidence EVIDENCE --out ADMIN_NEW_RESULT`支持原训练合同或新评价合同。EVIDENCE由root在实际完成后提供：

```json
{
  "root_result_archival_authorized": true,
  "global_barrier": {"path": "...all-selections-frozen.json", "sha256": "..."},
  "unit_receipt": {"path": "...unit-complete.json", "sha256": "..."},
  "pool_exit_verification": {"path": "...pool-exit-verification.json", "sha256": "..."},
  "pool_started": {"path": "...原pool unit.started.json", "sha256": "..."},
  "execution": {},
  "score_receipts": [
    {"role": "internal", "path": "...complete.json", "sha256": "..."},
    {"role": "external75", "path": "...complete.json", "sha256": "..."},
    {"role": "supplement13", "path": "...complete.json", "sha256": "..."}
  ],
  "independent_review": {"path": "...per-score-audit.json", "sha256": "..."},
  "training_stage": {
    "contract": {"path": "...原训练task-contract.json", "sha256": "..."},
    "unit_receipt": {"path": "...原训练unit-complete.json", "sha256": "..."},
    "exit_verification": {"path": "...原训练实际退出收据.json", "sha256": "..."}
  },
  "differences": []
}
```

`execution`只填实际收据明确记录的字段，不能用期望命令/文件时间猜测。pool实际exit与absence证据必需。三个score须绑定同一selection/checkpoint和正确坐标；每端点分母严格匹配。未定义相关性保留null，缺独立细分则partial。result绑定真实S编号与合同SHA，review默认pending；不自动声称full-paper或验收通过。

此metadata归档器不读取gold/预测/权重，中央结构归档使用`check_files=false`并明确范围；实际输出hash由producer、root和独立review的证据承载，不能称为新的完整payload审计。root最终若另行获得适用范围，可直接用原权威CLI `--check-files`核全产物，而不修改规范。

`validate_stage_result_index.py --index INDEX --out ADMIN_NEW_SUMMARY`读取标准合同/result JSON，逐条调用原中央validator，核40unit/论文与完整10种子矩阵，生成结果索引、摘要和新批次采纳建议。它不改旧62篇或任何注册文件；pending review不计accepted，缺seed不计完整。

无需为了行政数量再复制200份训练标准result-record：200份评价结果可各自链接真实原训练合同、完成与退出收据，并绑定三数据评分。仅有训练结果而没有完整200评价矩阵，不会被本汇总器标为可采纳的完整请求。
