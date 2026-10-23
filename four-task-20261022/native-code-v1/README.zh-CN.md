# 原生工作流：自写代码补交

本包公开已有冻结与审计证据的自写工作流代码，覆盖 UniAIR 正式 v4 候选/选择/检查点、CPU epoch 与镜像 v6，以及 PepInter fullfit、原 B24 工程入口与 activation-offload logging v2。实际包含项和每项原始 SHA/公开 SHA 见 [SOURCE-MAPPING](SOURCE-MAPPING.json)；重复公开或未在本次证据集中找到冻结 SHA 的条目记录于本地审查清单，没有补造完成状态。

这些代码属于方法执行、准备或审计入口。公开代码不表示正式模型已训练完成；CPU epoch、B24、offload、镜像 v6 的实际状态沿用对应单独运行收据。作者 vendor、论文/原表/权重、用户本机 skills 和原始主机进程表均未包含。原作者实现与必要数据应按官方固定版本获取。未含或已公开条目见 [排除/去重清单](OMITTED-AND-DUPLICATE.json)，显式本地导入依赖见 [DEPENDENCIES](DEPENDENCIES.json)；其中缺少的guard模块仍保留原导入与校验，未用占位实现绕过。

机器路径与连接端点改为显式占位符，具体映射保留字符串 SHA；涉及替换的文件经 AST 重排格式，完整控制流、NN 调用、数值、断言、异常和资源门均保持一致。原始源文件及其 SHA 不变。完整原 AST 在执行路径字符串映射后与公开 AST 一致，未删减内存/磁盘/合同/源资产校验。

目录保留原项目相对布局。`<BENCHMARK_ROOT>`、`<REMOTE_BENCHMARK_ROOT>`、`<LOCAL_WORKSPACE_ROOT>`、`<APPROVED_ARTIFACT_ROOT>`、`<LOCAL_USER_HOME>` 与 `<SSH_RESEARCH_TARGET>` 都是待配置标识，不是可执行路径。应用者须绑定自己的受控目录、官方依赖、数据权限、资源政策和真实任务合同。原冻结 SHA 仍指原运行资产，公开模板不能冒用旧合同绕过新校验；这些入口在缺少依赖或合法合同的环境应失败关闭。本包不是一键完整运行环境。

只做静态语法/AST/数值与安全字段核对，没有导入科学模块、运行模型、触发 GPU、复制模型权重或推送仓库。范围与检查见 [VALIDATION](VALIDATION.json)，文件摘要见 [FILE-MANIFEST](FILE-MANIFEST.json)。
