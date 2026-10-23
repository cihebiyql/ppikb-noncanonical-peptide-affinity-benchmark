# 原目标逐项验收台账 v2：当前进展

审计时间：2026-10-23T04:54:24.825545+00:00。这是当前进展审计，项目继续执行；本报告没有启动、停止或改动科学任务。

**800个传统选中训练结果已完成并有本地资产：旧550 + HER2严格局部100 + 冻结ESM2简单头150，共1600个候选权重。DTA已独立验收90/150个主逻辑任务，仍缺60个。原目标尚未整体完成。** HU100次固定外测、RDE419条固定推理、训练canary及组件结果分别列示，均没有被加进800训练结果或混算成八篇完整复现。

## 本次实际核查

读取800份真实选中结果及其候选清单，逐条件确认完整0–9种子，检查全部1600个候选文件和1600份选中验证／测试预测本地存在；每个view×model抽核一个真实权重与测试预测SHA及实际预测分母。另抽核五个DTA作者架构的真实selection、检查点、验证／测试预测，PepInter四组头权重、旧SWING成功预测与退出收据、RDE419分阶段预测／原始输入／退出收据及最终419行。大模型和全体文件的既有流式SHA、独立指标审计已按实际收据覆盖范围引用，未重复扫描几十GB资产。抽核错误数：**0**。

旧550的全面审计覆盖1100候选和9400个指标；HER2新100覆盖200候选／92500指标；ESM新150覆盖300候选／316150指标并有全1699文件本地SHA回流与独立资源owner验证。ESM是冻结小语言模型＋简单头，三视图实际覆盖7419/7419/2222行、测试758/1129/129；它不能冒充9116全量覆盖或化学完整表征。新matched-manual控制分支当时真实运行，尚未由本台账计入已验收800。

## 四来源与四任务

|来源|绝对亲和力|改动效应|是否相互作用|接触位点|
|---|---|---|---|---|
|PPIKB|9116条pKd，同观测两划分；1996条NC/PTM注释|2289条metadata-silver ΔpKd，尚非逐对同条件金标|当前没有独立实测阴性任务；缺测不能当阴性|64个引用实验复合物／8625个观测残基标签，仅标准输入|
|UniAIR/HER2|419条原Kd(nM)，Fab-PPI延伸|419条作者DDG；单位与符号未认证，严格局部293/63/63|没有冻结的一般短肽结合阴性队列|作者建模突变结构／界面输入不等于实验接触真值|
|PepAffDB/PepInter|3620条混合pAffinity，独立端点；新native共同训练尚未完成|没有冻结的可比较改动效应金标|17054条作者构造负例分类；方法实际覆盖各异|没有可冒充监督金标的注意力／位点数据|
|ProfAff/PDZ|162直接FP；17136校准HU点，其中默认16806情境／16772输入，FP/HU分轨|42个直接FP PTM差值外测，与162共享底层测量|42432删失、5067未测单列，不变成不结合|本批无冻结接触标注|

13个原视图已逐文件重核行数和SHA。112 FP子集、162 FP超集、42效应对不能相加为新独立观测；3复合物pilot包含在64内。HER2原419固定推理与新局部训练来自同背景，不能互称独立外测。HU来源已在旧FP评价出现且存在共享校准依赖，属于条件外测。非天然核心残基、PTM与连接臂化学状态仍按元数据区分；ESM/PepInter骨架输入以及五个DTA的无手性特征不能称完整化学辨识。

完整逐项适用性／未具备原因见`data-task-matrix.csv`。

## 八方法的真实完成层级

五个DTA是原作者网络在新共同数据上的重训，效应任务为势函数差值适配。它们属于DTA架构控制，不能写成五个原生肽PPI专用方法，亦不声称完成原Davis/KIBA全论文实验。当前native residue-site头不适用。

**DGDTA更正：原论文第7页明确采用MSE。`DGDTA-CL`只是保留的内部运行别名，不存在已证实的“遗漏原对比预训练”缺口。** 已核PDF字节SHA与root纠正记录；旧closed审计保留为历史，当前验收以`reports/dgdta-identity-correction.json`更正为准。

DTA截至 `20261023T044345Z` 有 **90/150** 个去重科学完整输出；随后 `20261023T045212Z` 的accepted census已按相同90个逻辑键全部闭合，仍缺 **60** 个。旧59保留原验收；新增31由本地28与远端3分别重核33990与5034个指标、两候选权重／验证预测／selection／test SHA、匹配的真实exit0和进程消失证明。新增31条审计／索引／退出收据链接已逐SHA抽核，远端3个条件回流的全部88文件／82.27MB亦在本轮实际重新读回SHA通过。当前90的observed与accepted集合完全一致，`unaccepted_observed=[]`。后续任务仍需逐键新验收，不能仅凭complete.json扩大90。

|视图|方法|已观测完整种子|尚缺种子（census时点）|
|---|---|---:|---|
|effect_metadata_silver_source_cold|GraphDTA-GIN|6/10|6,7,8,9|
|effect_metadata_silver_source_cold|MGraphDTA|3/10|3,4,5,6,7,8,9|
|effect_metadata_silver_source_cold|DGDTA-CL|6/10|6,7,8,9|
|effect_metadata_silver_source_cold|DeepNC-GEN|6/10|6,7,8,9|
|effect_metadata_silver_source_cold|GS-DTA|6/10|6,7,8,9|
|kd_source_cold|GraphDTA-GIN|10/10|无|
|kd_source_cold|MGraphDTA|4/10|4,5,6,7,8,9|
|kd_source_cold|DGDTA-CL|6/10|6,7,8,9|
|kd_source_cold|DeepNC-GEN|7/10|7,8,9|
|kd_source_cold|GS-DTA|6/10|6,7,8,9|
|kd_target_cold|GraphDTA-GIN|6/10|6,7,8,9|
|kd_target_cold|MGraphDTA|3/10|3,4,5,6,7,8,9|
|kd_target_cold|DGDTA-CL|9/10|9|
|kd_target_cold|DeepNC-GEN|6/10|6,7,8,9|
|kd_target_cold|GS-DTA|6/10|6,7,8,9|

PepInter旧四个pKd面板各10/10完成，范围分别为standard2919（test288/425）和backbone6336（含405条NC注释，test683/946）的**冻结监督骨干＋回归头组件**。这不是完整原生微调。新原生576M分类网络的CPU FP32一次optimizer step确实成功并已全本地保全，但为smoke：0个完整分类基准种子、0测试。正式分类特征块与10seed头仍待完成，混合pAffinity任务完整链也未闭合。

SWING旧组保存成功种子1–9，0失败；范围是原生grammar/Doc2Vec72维16epoch＋两个XGB分类候选的明确inductive适配，实际覆盖15468/test2362，并非整个17054/test2577。新PYTHONHASHSEED=0组单独从0–9运行，不能拿新0拼成旧组10。04:39的真实/proc确认新组0–7八个worker存活，8/9等槽；当时无新完整10seed结果。后续pKd两面板共20种子仍须单独完成。

UniAIR当前完成的是**RDE专家fold0的419条固定推理**：312条超时前缀＋107条续算后缀已核对唯一ID、原标签、顺序、SHA，MAE1.6718／RMSE1.9516／Spearman0.4540（作者字段尺度）。它是0训练拟合，不是10种子重训，不是完整MoFPE，亦非无预训练暴露的新复合物外测。

随后8GiB的真实RDE canary通过一个epoch：train293、validation63、19次optimizer step、0test；独立检查93个Adam状态step计数均19及checkpoint中冻结／可训练参数SHA，正式10seed仍为0完成。CPU微批梯度等价测试是0optimizer诊断，不算fit。四专家源码／16权重与类导入就绪，full/fast v2在缺省`lora_tune`参数处失败、0成功forward；后续修订按新合同另验。HER2传统50个DDG结果已经对齐同一63条test ID，不能替代该RDE任务。

逐方法source链接、层级、10seed范围及缺口见`method-scope-matrix.csv`。

## 当前进程与收据时间

本台账直接只读/proc捕获三台实际主机：Node1、Node23、cihebi WSL，时间分别见`processes-*.json`。04:39捕获中Node23八个新SWING worker和八个DTA CPU worker真实存在；WSL target DGDTA seed8 worker1176538真实存在，之前seed6 PID1174652已经不能代表当前live状态。Node1的DTA MGraph包装worker及当时CPU梯度诊断另有真实argv证据。后续退出以实际新收据为准；本台账不会用旧PID或queue注册数证明完成。

资源政策仍是最多三块GPU、入场显存低于12GiB／利用率低于60%并逐任务核进程、余量、UUID和预算。新CPU generic任务使用各自有界低优先级进程控制；本次审计没有启动模型或改变任何进程。持续占用是否满足规则由真实准入／退出收据负责，登记或闲显存快照不是预留。

## 交给root的具体验收缺口

1. 按`DTA-observed-missing-seeds.csv`完成剩余60个view×method×seed；现90已闭合，之后每个新增输出仍需两候选权重、selection、逐ID预测、真实exit0、无残留及本地SHA逐键验收。滚动训练可能已在census之后产生更多输出，应以新census更新，不能手工相加。
2. 新SWING hash0分类0–9完整验收，再完成两pKd面板0–9；旧9个成功种子仅作保全结果。
3. 原生PepInter完成真实分类特征／头10种子及规定评价；完整微调与冻结骨干组件分别计数。混合pAffinity共同任务的完成状态仍须单列。
4. UniAIR严格局部RDE完成20个候选拟合／10个正式种子，并在相同authorDDG/test63与传统对照比较；full/fast及多专家主链仍需成功端到端证据。物理DDG单位未知保持未知。
5. 补齐八方法真正共同的适用数据覆盖／测试ID矩阵；相同原CSV不等于相同可用行或有效输入。独立NC核心残基／新靶家族外测证据仍有限，不能用标准HU或同背景HER2替代。
6. 新远端／live资产完成后保留全权重、日志、失败和SHA回流；当前已完成800与旧大资产保全不能证明未来任务全本地。近五年文献“全部查全”和本轮全部新增公开GitHub推送，本次证据尚未验证到该强度。

## 旧入口为何不能当live

`resources/STATUS.json`仍写早期local-queue-v1、旧worker1633074与较早失败，不能用于当前PID和完成数。根`STATUS.json`是带时戳的行政快照，其new_fits=0描述快照构建自身，不表示整个项目无新拟合。interaction v3仅记录02:02旧批次，UniAIR旧delivery-v2仍是import-only/拒绝历史；原final审计是旧59输出批次的证据。

建议新增统一live入口，引用各owner的实际census、完整验收表、process snapshot与其时戳，显示observed／accepted／本地保全三列。旧文件保持历史原件。此目录ledger.json可作为本次审计快照，不自动代表未来实时状态。
