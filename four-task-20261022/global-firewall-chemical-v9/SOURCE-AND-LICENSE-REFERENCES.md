# 官方资源、固定版本与许可边界

PeptideCLM-2正式论文：[JCIM DOI10.1021/acs.jcim.6c00652](https://pubs.acs.org/doi/10.1021/acs.jcim.6c00652)。本批Hybrid与MLM是同一论文两个变体，不能计为两篇方法复现。

- [官方代码](https://github.com/AaronFeller/PeptideCLM-2/tree/6b9708d4cb05717307d310daaf1c0f88c71ff084)，声明MIT；第三方源码未复制入本包。
- [Hybrid small固定模型版本](https://huggingface.co/aaronfeller/peptideclm-2-hybrid-small/tree/62d5db6922a5a5ece56f9cd5adc48ab2b19d2e57)，权重126690964字节，SHA c4c2b341d219516f1a5771b123858ba4bb1be55ea35e1b634e627517ccceb06d。
- [MLM small固定模型版本](https://huggingface.co/aaronfeller/peptideclm-2-mlm-small/tree/7fe899df4d9753224aefa955ed0cf859d181e693)，权重126690964字节，SHA 713fb214c51d42bd038b4dd71928ea5f5e0c3c2cf58be1fce8345cc395ef5f4a。
- [官方预训练语料卡](https://huggingface.co/datasets/aaronfeller/peptideclm-2-pretraining-data)：论文声明PubChem、ESMAtlas、LIPID MAPS来源；目标MLM及99个计算描述符。Hybrid不是全无监督，具体测试实体的语料暴露尚未穷尽认证。
- [ESM官方代码/模型入口](https://github.com/facebookresearch/esm)：本批目标侧为ESM2-t6-8M层6均值、320维冻结表示。其第三方条款分别适用。
- [RDKit官方实现](https://github.com/rdkit/rdkit)：Morgan控制使用原始完整分子、radius2/2048/includeChirality及10描述符，蛋白输入同ESM320。
- [PPIKB论文](https://www.nature.com/articles/s41597-026-07962-1)、[ProfAff论文](https://www.nature.com/articles/s41467-022-33018-0)：原表与测量许可分别适用，本包只披露聚合结果、流程与原SHA，不重新授权第三方原始数据。

底座与Tokenizer按官方license/model card取得。本批自有流程代码和数据引用分别处理；此包没有把第三方模型、语料、原实验记录统一改授许可。原公共仓库的其他官方资源获取工具继续保留其版本和范围。
