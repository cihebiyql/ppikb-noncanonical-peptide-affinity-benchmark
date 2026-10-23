# STAC／Profilin 原始测量来源复核

冻结27候选中，这两个DOI实际对应9条：STAC5条、Profilin4条。全部纳入本轮核查；39条原始模型/copy行继续折叠为原有9个测量情境。原27CSV、标签、100模型外测预测均未修改。

|候选（PEPBI Excel行）|Kd：μM|本轮原始数值证据|温度|
|---|---:|---|---|
|STAC1，125–131|3.92|作者公开原文SI Table S1一致|25°C，正文核实|
|STAC2，132–138|9.31|Table S1一致|25°C|
|STAC2 Q306L，139–145|22.4|Table S1一致，1次测量|25°C|
|STAC2 SH3-1，146–152|84|Table S1一致，1次测量|25°C|
|STAC3，153–159|10.63|Table S1一致，SEM7.32，2次测量|25°C|
|Profilin F139A/VASP，88|23.8|仍仅PEPBI转录，原表未取得|PEPBI303.15K，待原文核|
|Profilin Y133S/VASP，89|920|仍仅PEPBI转录|同上|
|Profilin F139A/mDia1，91|28.1|仍仅PEPBI转录|同上|
|Profilin Y133S/mDia1，92|540|仍仅PEPBI转录|同上|

STAC正文由[官方EuropePMC XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5692558/fullTextXML)与[OSTI原PDF](https://www.osti.gov/servlets/purl/1422225)取得，SHA见retrieval-receipt.json。SI表通过[通讯作者公开上传全文](https://www.researchgate.net/publication/320567516_Structural_insights_into_binding_of_STAC_proteins_to_voltage-gated_calcium_channels)实际读取；网页标明Filip Van Petegem于2017-10-23上传。保留author-public-web-evidence.json中的读取证据。官方SI PDF未取得，作者页面PDF链接404；未给不存在的PDF编造SHA。表中误差是SEM，PEPBI列名“KD SD”需保留此语义区别。STAC3有效浓度采用N接近1估计，误差较大，按原值保留。

STAC缓冲液与TEV去除His/MBP的处理已由正文核实；完整端基化学身份仍待证据。3条STAC2输入为SNASY…，同论文6B26/6B27沉积聚合物为SNANSY…；侧车记录该差别，不据晶体构建体擅修ITC输入。STAC1序列与6B25全长118aa完全一致。Table S2可核生物学残基范围，未完全解决切割残留差异。[原论文](https://doi.org/10.1073/pnas.1708852114)

Profilin合法全文入口未取得：出版方403，OpenAlex标closed，机构页面仅摘要与引用。PDB 2V8C/2V8F支持小鼠Profilin2a来源，4个输入与其WT序列分别只有一个F→A或Y→S替换；PEPBI写F139A/Y133S，输入位置为140/134，侧车分别保留原文编号和输入坐标。原始ITC表、温度、缓冲液及端基仍待核；描述符X不等于无修饰。全9条均为AA20序列视图，化学/实验全认证条数为0。[Profilin原论文](https://doi.org/10.1016/j.jmb.2007.10.050)

## 对100个固定手工模型的外测资格

本轮独立重读两个实际PPIKB训练视图（各9116行，包含train/validation/test），逐候选重查18个“候选×面板”：精确肽—靶标序列对及相同原测量DOI重叠均为0。证据与输入SHA在manual-source-independence.json。模型代码使用双方序列计数、长度与二肽桶等174维特征，没有预训练编码器，因此全局PLM预训练未知不作为这100模型的独立性门槛。

9条可保留为相对这100模型监督来源分离的条件验证；其中5条已补齐原始数值和温度证据、4条保留原表待核标记。化学身份认证与来源分离分别报告。此前已完整外测，属于已用测试数据；结论不扩展为盲测、新家族测试或预训练模型无暴露。5条STAC共用同一肽，4条Profilin来自同一蛋白变体系列；统计需按两篇来源和体系分组，不把39个copy视为独立重复。

本轮0训练、0模型推理、0标签更改；8项一致性检查通过。原数据的每一项剩余缺口见primary-context-sidecar.json。
