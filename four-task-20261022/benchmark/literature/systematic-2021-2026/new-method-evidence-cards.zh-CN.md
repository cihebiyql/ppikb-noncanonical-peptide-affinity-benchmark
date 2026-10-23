# 五项新近直接方法：源码与数据证据卡

本文件区分论文任务、公开默认实现和本轮真实资产。代码仅作文本检查，未安装依赖、导入模型、训练或推理。

## VITAL（NMI，2026）

原文：[Quantitative and interface-aware prediction…](https://doi.org/10.1038/s42256-026-01291-z)。作者代码：[BADDxmu/VITAL](https://github.com/BADDxmu/VITAL)，固定commit `ece8466f5e71ebf828840b61c17e38695605ddb0`。

- 输入：FASTA双方序列，ESM2、iFeature及SPOT1D等特征；“几何感知”不能反推为每个预测都必须输入实验PDB。未查到任意NC/PTM化学身份API。
- 原生输出：二元概率、ASM及DeSite位点；`DeSite_BSU.py`计算ASM衍生BSU。该指标可以评价结合强度相关性，未有直接pKd校准证据时不可报为pKd预测。
- 公共默认实现：`prediction.py:38`加载TorchScript；核心`ckpts/VITAL.pt`在tree中是134字节LFS指针。本轮静态源文件不是完整训练源码/权重交付。
- 实际数据：benchmark9701行PDB—pepchain—proteinchain；原索引train17806=8905正+8901负，test1600=800正+800负。正例9705行对应9701唯一ID，4个ID跨split重复，逐ID在`datasets/VITAL-index-integrity.json`。
- 当前接触64个PDB有42出现在总表、37出现在训练正例PDB集合。须进一步逐链和同源核查，不能直接独立外测。

## SaMCL（Briefings in Bioinformatics，2026）

原文：[SaMCL](https://doi.org/10.1093/bib/bbag178)。代码：[xh20011225/SaMCL](https://github.com/xh20011225/SaMCL)，固定commit `09aa3eb6751759dff75528cf0f600a5f3d903d04`，33个轻量文件。

- 原生任务：是否相互作用、肽侧及蛋白侧位点；没有定量Kd/改动效应回归输出。
- 例表只有2行，含双方sequence、site label、`com_seq`与interaction。不能把例表当完整benchmark。
- `dataset.py`采用标准20AA词表/手工特征以及SaProt结构token，未知字符零向量不是非天然残基编码；原长度截断肽50、蛋白800。
- 当前PepInter分类可考虑共同数据适配；PPIKB接触仅比较蛋白侧且重新核对残基、截断和接触定义。缺当前完整肽侧接触gold，不能声称完整三任务已覆盖。

## HGT-PepPI（JCIM，2026）

原文：[HGT-PepPI](https://doi.org/10.1021/acs.jcim.5c03139)。作者入口：[bliulab](https://bliulab.net/HGT-PepPI/document)。zip已保存，SHA在其stage-manifest中；网站“Submitted”与正式出版日期不一致，以DOI元数据分别记录。

- 原生任务：ProtT5/异质图二元预测；alanine-scan案例不等于原生校准ΔKd回归器。
- 真实文本为`>positive_id`、`Peptide:`、`Protein:`；X是未知AA标志，不代表实际NC化学身份。
- 实际pair数：训练17244；Test1440=2880；Test167=510；Test251=498。保留原文件名，报告实际分母。
- 与当前PepInter完全相同序列对：训练4838；测试673、35、22。0 exact overlap也不证明同源/构建体/预训练独立；本资源不直接注册独立外测。

## PepBAN（JCIM，2025）

原文：[PepBAN](https://doi.org/10.1021/acs.jcim.5c01713)。代码：[SyLi22/PepBAN](https://github.com/SyLi22/PepBAN)，固定commit `f4c24a92402185def82738de5dcb81e494620402`，40个选中文件约10.4MB。

- 论文明确提出原子分辨分子图处理含NC的环肽；不能因默认脚本仅见序列就否认论文此分支。
- 公开默认`dataloader.py`读取`Peptide,Protein,Y`，`utils.py:28/32`按ID取ESM2层33 mean表示；KPGT/concat参数只查到记录。完整公开原子图训练/特征路径未核实。
- 核心任务是二元分类；BAN注意力解释不能代替监督接触位点评价，未见物理Kd回归标签证据。
- `cyclic peptide/cyl.csv`为493行`id,smiles,labels`正例化学表。target_train740行、target_test186行（99正/87负），不是493个独立亲和力值。
- CSV ID不带`.pdb`，FASTA带该后缀。只去除字面末尾`.pdb`后740/186行序列全部能关联，无冲突；此为ID匹配，不恢复或替换任何残基。test与当前PepAff有1个完全相同序列对，train有3个。化学身份等价、人源范围、负例测量/构造机制仍未知，不注册独立外测。

## UMPPI（JCIM，2025）

原文：[UMPPI](https://doi.org/10.1021/acs.jcim.4c02365)。代码：[mrjohnmpu/UMPPI](https://github.com/mrjohnmpu/UMPPI)，固定commit `ba0763d4e770471a87db2c636cf70f1f2c46c84e`，7个轻量文件。

- 原生任务为二元识别与双方位点，多任务范围与SaMCL比较时应保留这一先例。
- 默认输入为标准序列、二级结构/理化与ESM2等特征，没有任意NC/PTM化学结构API的证据。
- 作者完整数据入口为Drive，本轮未下载；Zenodo记录15851934只有一个约33.6KB脚本，不能称为完整数据/权重镜像。
- 适合进入后续分类/位点模型候选；不能拿它直接填PPIKB定量亲和力结果。

## 额外亲和力与外测资源

[DeepPpIScore](https://doi.org/10.1038/s41401-025-01659-8)官方代码已固定commit `1b3fbceff2dd3723a34fedc3c40180d2ef54b218`，17个小文件。445行PDBbind2020衍生表都标Kd，但无靶序列字段，NC和cyclic标志均为常数1。ACE端帽/侧链环不能直接认证为非天然核心残基或宏环。其README使用“min-min score”，先做结构评分相关性，未校准不能输出pKd单位。

[PepPAP](https://doi.org/10.1016/j.ijbiomac.2024.133811)原文给出[作者代码](https://github.com/ChunhuaLab/PepPAP)，当前公共端点404，收据已保留；尚无成功clone/数据下载。它仍是应比较的原生序列亲和力方法候选，状态应报告为资源未取得。

[PEPBI](https://doi.org/10.1038/s41597-025-05754-7)工作簿官方SHA核验通过，329行仅147序列对，温度/晶体copy不能丢弃；[PepXPro](https://doi.org/10.64898/2026.08.09.743757)70条样本明确包含22PPIKB与1PEPBI，不能算新增独立证据。

本轮没有修改原13数据视图或合并训练集，没有替换原八方法，没有新增公开仓库。新资源需先完成人源、条件、化学身份与训练暴露审计，才能冻结新外测合同。
