本修订仅修复独立RF审计的辅助分组元信息装配，不修改模型、输入、预测、金标、分组定义或原冻结v5源码。

真实失败诊断：external75原输入的external_primary／external_conditional_sensitivity／external_reference_target_cold三列完整且均为bool，与冻结ID逐项一致，计67／8／2。缺列的是supplement13的external_supplement_NC及external_supplement_standard；输入和原blind/joined预测均无这两列，13条ID一致，原生产器未丢失输入本来已有的字段。旧RFv5在已完成记录/金标连接校验后、分组指标计算前，错误地要求这些辅助列必须预先存在。

新 `recompute_RF_v6.py` 在私有审计rows上按原SHA冻结的ids-nc8／ids-standard5补齐缺失列，并继续核对NC_core、化学层与8／5分组。所有已存在的flag必须是bool并与同一ID定义相等，冲突、null或错误类型仍失败。分组不从gold、预测值、模型或表现推断。原文件和失败stdout／stderr／FAILED产物保持原样。

该副本的CLI与原RFv5一致。03阶段授权的 `script_sha256` 绑定本副本SHA；其余字段不变。原combine、v6 extension/merge继续调用原RFv5门禁，因此它们的授权 `script_sha256` 仍须绑定原RFv5，不能全局替换。

```text
WINDOWS_PYTHON311 review/rf-subgroup-audit-recovery-v1/recompute_RF_v6.py
  --root-authorization ROOT_RF_AUDIT_AUTH.json
  --joint-barrier ACTUAL_JOINT.json
  --task-map EXPLICIT_RF120_MAP.json
  --matched-target-manifest review/matched-target-diagnostics-v1/manifest.json
  --output NEW_RF_AUDIT_OUTPUT
```

相对原v5仅三类变化：新子目录的project／numeric-helper定位；私有行的缺失flag装配；对应错误文本。AST检查确认true label join、input/pred/blind SHA、分组定义、五指标、120／53160完整性和十种子汇总代码均保持原样。数值helper仍为原baf78bfa…冻结实现。根运行新的resume driver显式复用已通过的NN600审计，不重跑NN、不重训或重评分。此目录只完成代码及合成验证，真实RF审计由root另行执行。

本诊断只证明失败来自辅助元信息必填条件，不代表尚未完成的RF120独立指标验证已经通过。新的完整审计仍须验证全部记录、金标和指标。原01:45截止不延长。
