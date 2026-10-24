# 指标阅读

- per-seed-metrics.csv：三种表示、五个回归器、种子0–9、十个总体/化学/flag分层的全部固定测试指标。
- ten-seed-mean-sampleSD.csv：相应均值、样本SD、有效种子数。空值对应未定义相关性，不填0。
- matched-head-paired-seed-MAE.csv：同一预测头、相同seed编号的表示A减B的MAE描述统计，无p值；不同表示的随机轨迹不因seed编号相同而相同。

所有测试均为同一502条，原flag21仍保留；exclude_discordance是固定预测重评分的481条，训练未去掉3条flag。非天然/D/骨架只有14个测试样本且训练9条，PTM34、混合17分别评价。不同分层标签分布不同，不能仅凭低MAE认定某类化学更容易。
