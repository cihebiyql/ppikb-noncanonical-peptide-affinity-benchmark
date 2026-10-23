# 四来源四任务数据合同

本轮仅冻结输入与标签，不读取模型预测后选择样本。固定train/validation/test，训练种子0–9不改测试分区。

PPIKB保留原完整分子、残基类型与全部原始标签。旧9619点Kd经本轮明确病毒物种/命名毒素scope隔离503，当前9116；恢复了旧v1名字子串误排的39条人蛋白/受体/antitoxin记录。scope-v1仅诊断，正式采用scope-v2。实际9116按完整CSV核对。

PPIKB source/peptide-dependency-cold与target-reference-homology-cold是两个不同面板，不能宣称同时双冷。PepInter/PepAff按作者targetcluster及exacttarget并组，用预定hash分区，不按标签平衡；肽可能跨分区，不是peptidecold。不同数据源分别训练，不把跨源测试自动称独立外测。PepAff混合pAffinity不混入pKd。

PPIKB效应先对原始观测分区，再保留分区内metadata-matched一残基编辑；a/b是词典序参考方向，不推断真实母体身份。label=pKd(b)-pKd(a)，正数表示数值pKd增加；条件/构建体未全认证故严格gold=0，全部silver。共享原观测不跨分区。

HER2原419测试标签和实际坐标输入完整保留；Fab伙伴227aa不是短肽。单背景local诊断以实际变体双方序列实体并组hash划分298/60/61；共享WT背景是任务定义的一部分，不叫跨背景迁移。此localtrack不得再把原419称独立外测。作者ddG物理单位/方向未独立认证，保持author_ddG_unit_unverified；原Kd(nM)另换算pKd。

ProfAff162全部external-only；原112是其子集，不能累加。完整原化学字符串和PTM逐残基tokens保留，序列骨架视图显式省略biotin-TTDS/PTM化学信息，不称化学感知模型。42对PTM差值来自68个既有观测，只有2个骨架17个域；条件资格silver，42对sequence-only输入全相同。

接触任务原pilot为PPIKB关联3个实验复合物。扩展v2完整扫描后已取得64个明确来源关联实验复合物、8625个观察残基；任意双方重原子最小距离<=5Å为几何接触。按PDB/目标/肽近邻并成40个依赖组件(最大7结构)，整体分为38/14/12个复合物，不硬拆。原pilot保留但不能与包含它的64结构求和。非接触不是不结合，最小距离/坐标/观察链仅用于标签审计，不可作sequence-only输入；预测突变体不作为实验金标。45个Xray及19个solution-NMR均采用来源档案第一model几何。

所有原件只读。缺测、占位0、检测哨兵不转换成阴性或精确亲和力。未就绪格保持明确原因，不以任务矩阵登记冒充训练完成。
