# 手性分子指纹传统亲和力/效应基准

本分支补充化学信息可辨识的传统对照，不改变已完成的序列基准，也不引入创新架构或新依赖。

## 输入与特征

仅使用数据组冻结的两个PPIKB pKd面板和2289条metadata-silver效应配对，原始SMILES、row_id、标签、分区、NC/PTM/标准残基层原字节保留于`inputs/`。缺失或无法解析的SMILES不改成序列、不偷偷丢行，直接留下失败。

- 肽：完整SMILES经RDKit解析，Morgan radius2、2048位、`includeChirality=True`，保留键类型及环信息；不截断原子。
- 另加10个经典RDKit描述符：分子量、LogP、TPSA、HBD、HBA、旋转键、FractionCSP3、重原子、环及脂肪环数。
- 蛋白：完整冻结参考序列的20AA组成、非20字母比例、log长度及空串指示，共23维；不冒充实际实验构建体。
- 绝对亲和力为2058维分子特征＋23维蛋白特征，共2081维。
- 效应为WT分子特征、MUT−WT分子特征差和同靶标蛋白特征，共4139维；若蛋白本身改变，不使用这套同靶标接口。

源SMILES能表达的手性和PTM会进入指纹。此能力不证明源SMILES完全等同实验化学身份；残基注释—图冲突标记仍保留。真实D/L canary指纹不同、PTM例子特征不同，只验证编码器，不等于生物学准确性。

## 模型与选择

常数(mean/median)、Ridge(alpha0.1/10，LSQR/tol1e−4/max_iter1000)、RF、ExtraTrees、HistGB，各2个预声明候选、种子0–9。Ridge、常数等确定性模型在固定划分上可完全相同，不人为添加随机性。

RF/ExtraTrees使用48或64棵树、深度8或14、min_samples_leaf3或2。HistGB使用40/80轮、15/31叶、learning_rate0.05/0.1、max_bins64，明确是为高维指纹的CPU2预算预先设置。标准化只拟合训练集，选择只看validation MAE；所有候选权重及验证预测保留。

metadata-silver ΔpKd仍缺逐对同条件认证，不能因分子表征更完整而升级为严格金标。新传统结果不能冒称八篇前人论文复现。

## 环境与资源

Windows当前Python和WSL系统python未发现RDKit；未安装新包。Node23已有SWING venv实际提供RDKit2024.03.2、NumPy1.26.4、pandas2.2.3、SciPy1.11.4和sklearn1.4.2，七项分子/估计器测试通过。

采用Node23单一CPU2任务、core28–29、nice15、6GB内存上限、45分钟有界监督，无GPU。已与SWING四个CPU1 worker协调，Node23该组最多6CPU。监督只控制自有PID/PGID，记录日志、资源峰值、退出和残留检查，未修改共享环境。

入口为`run_molecular_baselines.py`，特征代码`molecular_features.py`，资源监督`supervise_molecular.py`。源代码相对原冻结CPU runner的改动见`adaptation.diff`；数据/代码/运行spec与payload均有SHA证据。正式输出为新目录`runs/cpu-molecular-v1/`。
