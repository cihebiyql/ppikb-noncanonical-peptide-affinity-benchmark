# 四任务基准：公开入口

历史公开快照保持原样；以下入口分别说明资源获取、结果和权重。科学训练完成、文件物理镜像完成、已公开上传是三个状态，不能相互代替。完整全骨干PepInter和四专家UniAIR/MoFPE基准仍待完成，组件或单步成功不补作完整训练。

|入口|状态与范围|
|---|---|
|[官方资源获取](official-resources-v1/README.zh-CN.md)|已公开；197项精确获取信息＋1项保留的历史坐标URL pending，输入获取工具不是一键完整复现。|
|[最新结果更新](results-update-v2/README.zh-CN.md)|已公开75文件；DTA150/300、SWING分类10与亲和力20、RDE10组件、PEPBI条件外测分轴；旧12:31快照13/20本地状态保留；最新全20本地事实见下方交付闭环。|
|[通用2100候选权重Release](https://github.com/cihebiyql/ppikb-noncanonical-peptide-affinity-benchmark/releases/tag/four-task-20261022-generic-candidates-v1)|已公开并核验18项资产；仅指通用候选权重，不表示全项目模型资产已全部公开。|
|[SWING亲和力模型本地交付闭环](artifact-delivery-v1/README.zh-CN.md)|本批新增收据；截至12:53UTC，source10＋target10共43,372,437,689字节全部本地SHA及Windows独审通过；这不代表43GB已公开上传。|
|[历史接触坐标归档恢复补充](contact-archive-restore-v1/README.zh-CN.md)|本批准备的独立固定HTTP来源工具；旧HTTPS锁不改，发布状态以本批提交/发布收据为准；本轮没有重下载691MB。|
|[共同测试集亲和力比较 v3](common-affinity-v3/README.zh-CN.md)|本批新增；固定 source683/target946、27方案/面板×10种子共540次已存预测评分；49320数值检查0错误，训练覆盖差异单列。|
|[DTA 300候选权重Release](https://github.com/cihebiyql/ppikb-noncanonical-peptide-affinity-benchmark/releases/tag/four-task-20261022-dta-candidates-v1)|已发布并核验19项资产、4,405,802,642字节；DTA候选权重交付。|
|[最新进展补充 v4](progress-v4/README.zh-CN.md)|UniAIR原B8首完整epoch已审37 Adam步，正式20候选仍prepare-only；SWING30种子科学/本地闭环，PDZ2026可用标签0。|
|[DTA科学日志补交](dta-logs-v1/README.zh-CN.md)|已公开独立Release：612进程日志＋300运行记录，916归档成员，10资产大小与摘要核验通过；无新增训练。|
|[自写原生工作流代码补交](native-code-v1/README.zh-CN.md)|17份已有冻结证据的自写源码；路径占位模板，NN/数值/断言/资源门保留，未交依赖与18项排除清单明确；代码公开不表示完整模型已训练完成。|
|[CPU完整一轮成本与ESM条件外测](native-cost-external-v1/README.zh-CN.md)|UniAIR CPU原B8一轮真实37Adam/63唯一验证/7008秒、独审通过；ESM100个已有模型×27候选的2700固定预测全部10种子已核，0新增fit。仍非完整原生20候选完成或完全认证独立外测。|
|[PepInter原B24 CPU两步成本实测](pepinter-CPU24-cost-v1/README.zh-CN.md)|已公开两步原始时序、全参数梯度及Adam计数、自写入口和独审；CPU FP32，0正式种子，0验证/测试，无完整权重保存。|
|[外测输入勘误与敏感性更新](pepbi-input-erratum-v1/勘误与敏感性更新.zh-CN.md)|200个既有模型、全部10种子，原27／排3后24／PTPA4分别重评分；5400条原预测保留，0新增训练，来源独立性仍分轴说明。|
|[来源受控PTPA补充基准](known-doi-ptpa-v1/README.md)|新100个选定模型／200次候选拟合，五类各10种子；300份预测和200份权重已核验。4条既有测量、1研究1蛋白，来源控制与外测边界单列。|
|[原完整GPU成本门失败记录](native-GPU-cost-status-v5/README.zh-CN.md)|UniAIR组合与PepInter原B24均发生实际显存不足；原日志、资源和独审摘要保留。推断／直接计数／未知启动分开，两个完整模型仍未完成。|
