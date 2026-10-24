# 恢复代码目录与执行小测试

本包code目录采用披露布局，直接运行native-fullfine/train_finetune.py会缺少原项目相对导入。先取得同仓库保留的global-firewall-chemical-v9目录，再运行本包的stdlib恢复器。它只使用各包SOURCE-MAPPING中的record-ref:project相对路径，把已公开自有.py及其配置还原到新的项目根；不读取私有路径，不获取模型或数据。实际已恢复24个代码/配置文件，其中19个Python源码全部恢复到原sourceSHA；stdlib6测试和恢复树原生7个tiny mock测试均通过。[stdlib收据](audit/recovery/STDLIB-TEST.actual.json) · [恢复字节](audit/recovery/RECOVERY-SMOKE.actual.json) · [tiny mock实际收据](audit/recovery/tiny-mock-actual.json) · [tiny mock日志](audit/recovery/tiny-mock-actual.stderr.txt)。

```text
python restore_project_tree.py --source ../global-firewall-chemical-v9 --source . --destination /your/new/empty/project
python -m unittest -v test_public_recovery.py
```

Windows可使用任意新的本地目录替换目标。恢复器验证每个公开文件SHA，拒绝绝对路径、..、符号链接、越界目标和异字节覆盖；相同字节文件可幂等保留。代码先尝试原字节及已记录的换行转换，能匹配sourceSHA才恢复。旧v9的CRCRLF披露换行会还原成源码身份一致的LF。原SHA无法恢复的代码立即失败。经过路径脱敏的普通JSON按公开字节恢复并记录新旧SHA；固定ringfix配方保持原SHA。

在具备现有numpy/pandas/scipy/sklearn/torch/transformers依赖的环境中，可运行原自有微调小测试：

```text
python /your/new/empty/project/baselines/chemical-encoder-finetune-20261024-v1/test_mock_interfaces.py
```

这7个小测试只用合成数组和随机初始化tiny mock encoder，不读取CLM2权重或真实生物记录。测试包含tiny梯度/优化器步骤，须与正式科学fit计数区分。无需GPU。stdlib test_public_recovery还会在临时新树实际import ringfix_adapter并执行load_recipe，核实原配方固定SHA、非覆盖和路径边界。

ringfix原准备测试里涉及真实tokenizer资产、完整v2训练源码的部分不由本公开包代跑。完整模型运行须另取官方底座、tokenizer、冻结manifest、ESM和化学cache及有权限输入，并重新绑定实际部署的源文件与资产SHA。目录恢复和tiny mock通过仅证明恢复入口及小接口可用，不替代完整训练复现。
