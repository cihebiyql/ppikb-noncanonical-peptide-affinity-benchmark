# GS-DTA2025替补方法静态审计

结论：可作为第五篇不同论文方法的候选替补。选择依据为公开资产与输入兼容性，没有运行预测或比较性能。正式训练前仍由主代理冻结新合同并执行有界smoke。

论文：[GS-DTA](https://doi.org/10.1186/s12864-025-11234-4)，2025，原出版PDF10页；SHA `725e257cf378b2959afc34dd8b65d8c29787af6330c1d9fee3b464fd0a0619e3`。官方归档MD5、PDF正文DOI、非作者手稿身份均核对。

作者代码：https://github.com/zhuziguang/GS-DTA ，commit `a36750c0c2567b5b4c3f9b3aed64eac5c40a3d3c`。源码为有界HTTP冻结快照，15项文件逐字节SHA核验，Python静态语法均通过。源码仓库未声明许可；论文许可为CC BY-NC-ND。

模型：`D:\work\科研工作台\research-tasks\peptide-binding-nc-benchmark-20261021\model-audit\author-source\zhuziguang__GS-DTA\source\Models\gatv2_gcn.py` 的 `GATv2_GCN_CNN_BiLSTM_Transformer`。

输入：PyG Batch x float[N,78], edge_index long[2,E], batch long[N], target long[B,1000]；输出[B,1]。预处理采用作者GraphDTA同款78维图特征，无分子原子数截断；完整SMILES先解析为完整分子图。只需现成torch、PyG以及数据预处理RDKit/NumPy/NetworkX，无结构或PLM依赖。

化学特征缺少手性及键序，须明确作为拓扑化学基线。蛋白采用作者1000aa前缀，所有截断与有效输入hash按现行协议保留。

静态张量流：分子双分支1560＋624→2184→1500→128；蛋白CNN/pool输出[B,128,64]，显式permute至[64,B,128]后进入BiLSTM与Transformer，最终[B,128]；双方拼接256维回归。这个LSTM布局不沿样本轴递归。

作者入口存在两个陷阱：`training.py`采用test-MSE选模型且models目录大小写不符；`training_validation.py`实际复制GraphDTA模型导入。必须加载被冻结的GS-DTA模型类并使用本轮验证集选择的共同trainer，不可把错误入口跑通称GS-DTA。

保存了资产静态合同asset-static-audit-contract.json；该合同明确禁止直接训练，不代替行政代理的正式运行合同。

未执行任何作者代码、推理或训练，没有装依赖、改共享环境，也没有复现论文应用案例。
