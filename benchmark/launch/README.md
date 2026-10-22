# 正式基准启动器

这里只实现启动、资源监控与收据，不新增模型，也不评分。五方法为GraphDTA-GIN、MGraphDTA、DGDTA-CL、DeepNC-GEN、GS-DTA。每unit顺序执行两个LR fit，再冻结validation选择；评分须由root另在全200个unit选择冻结后统一执行。

## 冻结输入

参见`unit-index.template.json`；模板`issued=false`永不启动。真实索引由root在独占control目录签发，CLI绑定索引字节SHA。运行中不追加/修改该索引。可在首批结束后签发新revision索引与新pool output_root，复用同一unit receipt_root；完整且全部SHA一致的unit会跳过，失败/不完整unit不会自动重新运行或重置时钟。

每个spec需`launch_proof`：

```json
{"expected_hostname":"cihebi","runner_path":"/mnt/d/.../execution/runner.py","runner_sha256":"actual SHA256","receipt_root":"/mnt/d/.../launch/receipts/ISSUED_UNIT_ID","files":[{"path":"actual author/adapter Python source","sha256":"actual SHA256"}]}
```

也支持合同`execution.launch_proof`。`files`必须为非空实际源码资产列表，不放测试或外部标签。训练/验证JSONL另按spec已有路径与SHA检查。合同须`is_template=false`、`contract_status=frozen`、实际host/environment匹配、有效原截止未过；GPU、CPU2、20epochs/patience5及两个冻结LR均严格核对。

validation须含`valid_for_execution=true`且`contract_sha256`绑定本unit。若中心校验器原报告没有绑定字段，签发独立envelope：

```json
{"valid_for_execution":true,"contract_sha256":"actual contract SHA","central_validation_path":"D:\\...\\central-validator-report.json","central_validation_sha256":"actual report SHA"}
```

wrapper会复核中心报告真实SHA和`valid_for_execution`。只保守映射已签发的Windows绝对路径到WSL `/mnt/<drive>/`，不更改合同/报告字节。

## 实际CLI

由root配置真实环境后启动：

```text
/root/.venvs/peptide-omnipanel-v31-web311-20260723/bin/python launch/pool_supervisor.py --index ACTUAL_WSL_INDEX --index-sha256 ACTUAL_SHA
```

pool生成的真实unit命令为：

```text
PYTHON run_unit.py --spec PATH --spec-sha256 SHA --contract PATH --contract-sha256 SHA --validation PATH --validation-sha256 SHA --deadline 2026-10-22T01:45:00+00:00
```

环境必须显式设置指定GPU UUID和模板中的PYTHONPATH。wrapper原样用当前解释器执行`runner.py fit --spec ... --candidate-index 0`、候选1、`runner.py select --spec ...`。不生成伪命令或score命令。

正式合同也支持root提供的固定入口：每unit若有`unit_binding,unit_binding_sha256,bound_entrypoint,bound_entrypoint_sha256`四字段，先核验两文件SHA，实际执行`[index.python,bound_entrypoint,"--binding",unit_binding]`；root入口execv进入同wrapper。四字段不能只填一部分。unit wrapper要求自身为pool创建的私有session leader、父PID与pool环境标记一致，不能绕过监督直接启动。

## 边界与预算

每unit私有PGID由pool `start_new_session=True`创建，wrapper及runner子进程继承该组，不再另建session。只signal本pool创建、当前UID且session等于PGID的进程组，不signal GPU查询中的陌生PID。独立watchdog每0.2秒检查原截止和进程树RSS，约每秒写`progress.json`；GPU查询阻塞不阻塞心跳/截止watchdog。

原global截止固定，允许更短CLI截止。每unit还按合同timeout（正数且≤7200秒）从第一次launch monotonic计算，取与global较早者；仅本unit超时只终止自己的组并保留失败。wrapper同时记录global、requested与effective unit截止，不能延长原clock。

root采用最多2并发，CPU2/unit，RSS4GiB/unit，host整个pool12GiB，Torch allocator≤3GiB/unit，总GPU预约≤8GiB。RSS按/proc整session进程累加、含supervisor；GPU按明确allocator预约和`memory.used - 保守graphics baseline`监控，后者可能包含系统图形波动，因此超预算时仅停止自己的组。GPU allocator预算不等于上下文/驱动总内存。

启动前保存3个实际GPU样本，要求没有外部报告compute PID和超过声明门槛的利用率。每次启动前再查；发现未知/无法映射PID或查询失败则暂停新launch。WSL NVIDIA列表可能遗漏或使用Windows PID，空列表不能宣称完美跨OS可见性，限制写入每个GPU样本。

`feature_cache_required=true`时每unit必须有签发的train/validation缓存路径与SHA。缺失/不匹配只defer，不在GPU worker临时构图；已核验稳定cache按size/mtime/inode复用SHA检查，变化后重查。卡住的缓存与外部GPU进程在进度中明确列出。

所有stage stdout/stderr、真实argv、PID/PGID、退出码、检查点/选择/收据SHA保留。完整unit另有receipt SHA；resume要求所有产物一致。失败与中断保留，不删除旧目录或换run重置clock。

## 已验证范围

`test_launch.py`是机械测试，真实短子进程验证stdout/stderr/exit/PGID继承、私有session整组停止、错误SHA拒绝、缓存gate、未知GPU PIDgate、完整收据resume检查。`mechanics_smoke.py`保留短成功、失败和截止子进程证据；没有科学训练、GPU使用或测试集/外部标签访问。正式pool仅由root在行政签发后启动。
