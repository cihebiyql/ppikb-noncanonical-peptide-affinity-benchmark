# 自有代码公开范围

保留原项目相对层级的code/包含：metadata防火墙构建/校验、离线CLM2提取器、完整SMILES缓存接口、标签无关共同输入覆盖、五族十种子头训练、外测化学字段覆盖、独立预测重算和合成接口测试。模型原生ChemPepMTR.py/config.py、词表、预训练权重与实验表不在本包；按官方坐标恢复并核原SHA。

源文件路径转换只用于披露，`record-ref:`不是可执行本地路径。原科学运行源码SHA保留在收据中；公开源码SHA见SOURCE-MAPPING与FILE-MANIFEST，两者各有含义。恢复运行时需提供有权限的原输入/资源及路径配置，不从这个无原始数据的公开包直接推断一键可执行。

synthetic test_contracts.py用临时数值和假cache验证接口，不计正式模型或实际化学canary。生产缓存只接受native实际canary；合成fixture通过显式测试参数开放。所有实验预处理只在train拟合，超参/轮次/阈值仅用validation，测试和外测只评价。
