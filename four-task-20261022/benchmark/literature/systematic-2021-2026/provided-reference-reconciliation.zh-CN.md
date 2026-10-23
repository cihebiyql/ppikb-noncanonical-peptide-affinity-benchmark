# 用户已有参考清单核对与补差

原文SHA256：`0319aeb1aa7b8915b82c973efbc4d03dc9a8909f58a1120935aef5ba755f6f71`。原文自报58论文/34资源；附件是txt，所链xlsx未随本附件提供。本轮对可见67条加粗表格行识别出62条文献/资源行和5条任务定义行，62条均逐行对照，重复资源保留原行位置。不能凭txt重建或认证xlsx的全部58/34条。

62条参考行共涉及56个别名键；正文另外明确提到DeepPepPI与TPepPro，合计58个可见名称键，均有对应身份/分栏条目。补充表取得23项原始身份元数据，DDGPred身份另有独立更正文件。原80目录保持为固定主检索结果，本补充单列，不把用户早已给出的VITAL、HSM、PEPBI、ASHI等称为首次发现。

## 明确纠正

- 原文行82：PepInter text points to PPIKB DOI10.1038/s41597-026-07962-1; correct10.1038/s42004-026-02168-3. Claimed3670 is reported source size, not current3620 frozen derived rows.
- 原文行193：Same PepInter/PPIKB URL mismatch; affinity source/cleaned view counts retained separately.
- 原文行172：UniAIR text points to ScientificData s41597-026-07984-9; correct NMI10.1038/s42256-026-01243-7.
- 原文行234：Graphinity link s42256-023-00619-3 is wrong; correct NatureComputSci10.1038/s43588-025-00823-8.
- 原文行233：SPECTRA link is journal homepage; exact primary10.1038/s42256-024-00931-6 verified.
- 原文行170：DSSA-PPI link is unrelated worker-proxy journal-impact page; corrected primary10.1039/d5sc08898d; no proxy fetched.
- 原文行114：Original table points to2019calcineurin eLife rather thanB56; original text later corrects to10.1021/acsmeasuresciau.1c00008. Correct Crossref online2021-07-19, outside window.
- 原文行194：SKEMPI row links unrelated arXiv; exact primary10.1093/bioinformatics/bty635 verified.
- 原文行195：ABBind online2015/print2016; original2016 is issue date, not first online.
- 原文行166：RDE identity verified from frozen official UniAIR SI bibliography and Crossref preprint; exact ICLR conference version not independently closed here.

## ASHI v2实际小资源

官方Zenodo v2的README及2,796,483字节原始SIMBA压缩表已下载，官方MD5与本地SHA核验。实际12153编码行/4051独特肽，全部每肽3个编码；DMS 9120编码行/3040独特肽，来自10个source分组。原始列识别9个域/bait、30个z-score列，没有预聚合SIMBA-score列。

这核实了用户原参考中4051/3040/10的对应层次，尚未逐条认证source分组就是完整化学母体身份。source内有实验控制与人工序列，不能假定每行均为人源天然肽。z-score/筛选读数不是Kd，不新增硬负例或大量两两配对；尚未冻结新可训练/独立外测视图。

## 剩余身份/实物缺口

- DDGPred最初Crossref模糊查询返回无关条目，已拒绝；后经DDAffinity原文参考文献和Crossref精确DOI闭合为Shan2022 PNAS论文10.1073/pnas.2122954119。仅核书目身份，没有功能分析/运行。
- SemiSVR精确DOI10.1093/bioinformatics/btq657、Li2010精确DOI10.1016/j.jmb.2010.03.005均经PubMed/出版社及Crossref核实；SemiSVR实际2010在线/2011刊期，均在窗口外。
- HSM使用2026更正版本；CAMP、B56、GeoPPI、GraphDTA等窗口外条目分栏保留，不拿在线/刊期混换扩大窗口。
- ASHI全ProP-PD58.4MB等大表本轮未下载；SIMBA2025、HD2与磷酸化模拟等只核论文身份，不把参考自报量称本轮清洗结果。
- 本补充无训练/推理，不替换原八方法、不创建公开仓库。
