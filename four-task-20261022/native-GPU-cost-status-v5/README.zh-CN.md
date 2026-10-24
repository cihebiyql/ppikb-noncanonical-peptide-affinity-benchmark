# 原完整 GPU 成本门：失败证据与当前状态 v5

本增量公开两次已经结束的原完整模型 GPU 成本门结果，补充此前公开进展。两次都是**实际 CUDA 分配 OOM**；没有完成本次拟议的完整训练，也不是资源看守器主动杀掉模型。原失败原件保留，本增量只读整理，不运行模型。

| 项目 | 已证实结果 | 进度边界 |
|---|---|---|
| UniAIR：原四专家＋门控，activation/residency组合，原B8、8 GiB allocator | exact-exec身份门通过后运行546.526544秒，在Gear突变图边层`torch.sparse.mm`申请1.61 GiB时OOM；错误时已分配5.68 GiB、reserved6.69 GiB | 0完整epoch、0验证/测试结果、0正式候选完成；直接保存的Adam步数仍为null |
| PepInter：原576,293,761全参数、B24×991，GPU前后向＋stock CPU AdamW准备 | 首次forward在FFN `F.silu(x1) * x2`申请140 MiB时OOM；整进程140.739292秒，worker129.06938427314162秒 | 直接证据为0 backward、0 Adam更新、0完整检查点写入/恢复、0验证/测试、0正式种子 |

## UniAIR：观察到的部分进展

双helper实际partial trace保存成功，刷写错误为空。记录7,076个activation事件，其中3,174次GPU→CPU、2,824次CPU→GPU；全部2,824次unpack均有匹配的元信息、字节数和完整SHA pack。记录28,768个residency事件、69个传输边界；原冻结存储的SHA、布局/别名及已记录边界的mode/buffer/cache/RNG守门通过。buffer与普通cache没有被搬运。这些检查不证明完整CUDA数值等价。

记录8个完整四专家循环及第9次Gear激活。结合冻结worker的顺序控制流，可**有条件推断此前8次`optimizer.step()`调用已经返回**。但没有逐步journal或检查点记录可直接认证Adam状态，因此公开JSON继续保留直接Adam计数为`null`，不把推断写成已保存8步模型，更不当作37步/完整epoch完成。

观察到的物理GPU峰值8,696 MiB，限制8,704 MiB；最低真实free为7,079 MiB，保留要求6,144 MiB。采样峰值RSS为9,528,164,352字节，预算24 GiB；此次未触发900秒timeout或资源guard。采样符合预算不等于认证每个未采样瞬间的峰值。没有生成最终result.json或完整检查点。

独审原SHA：`21951f409e682fc05332cc9b1865e025bf16ae4c1a9c63b37bcffb372f2e2fcc`。36项原raw证据归档SHA：`d2ba0edbcb29d4c2de82b13b829fe15c663f50db6409001a63b61fc2c2a40c72`。归档另含自身manifest，未递归公开原包。

## PepInter：CPU Adam 本身尚未被此次原规模运行检验

CPUAdam-only没有解决原B24×991的forward峰值。虽然入口保留GPU BF16 autocast，35个已观测Transformer block输入都是FP32；不能声称整个forward激活均为BF16。错误发生在第一次forward内部，因此本次没有实际执行CPU Adam更新，也没有完成拟议的step1保存/恢复。此前CPU FP32两步成功属于另一运行后端，不补作本次GPU成功。

实际GPU peak allocated为7,987,173,888字节、reserved为8,445,231,104字节，物理采样峰值8,518 MiB，最低真实free为7,421 MiB；资源guard停止原因为null。103次RAM采样均通过。检查范围是已有失败、phase、计数和摘要，没有独立重算原规模梯度。

独审原SHA：`96dfa206357846f791709b7be7f288325e62faf94cf396dcfa6758ee77f277ed`。71项资源/科学证据原归档SHA：`5d2a77d4321eb82e984ca97542e4587e71f1ee82d612cd1c6fbf26e1529703cf`；原包不在本公开增量中。

## 历史尝试单独保留

- 更早的UniAIR activation-only 8 GiB尝试：首批Gear sparse.mm申请332 MiB时OOM；未有已确认Adam进度，未完整epoch。这是旧机制，不与上面的组合尝试合并计步。旧合同SHA `9272c61d6a8954786cc41f39c1ccc9091934372e08ed409b48128d3e23e6b11a`，保全包SHA `a59fedfd549adc52f55c76e8bc9c15849d4b9d24dfd09d055e33e8bd9baf3468`。
- 中间一次组合入口在Popen后未证明exact exec，科学启动/forward程度保持**unknown**，不记作0次模型执行。其保全包SHA `8fff27a944a7d9815ec9c177f0b87362d90b59fe7c16c4cc0fa582a70dd0ab3f`。后来的新尝试不能倒填这次未知状态。

## 八方法与结果分母

八项约定前人方法中，五个DTA方法与SWING的约定面板共6项已完成相应10随机种子；**原完整UniAIR/MoFPE和原完整PepInter仍未完成**。已完成的RDE、冻结表征或原生头组件、成本门都单列，不能替代这两项完整训练。

已冻结的1,050项main选定结果继续使用原定义；来源受控PTPA补充100个选定模型单列，不并入main分母。这两次成本失败均新增0个正式完成种子。新的CPUAdam＋activation v2方案、9.5 GiB方案目前只标**PREP**；源码、协议或小测试通过都不表示原模型成功。

## 本增量包含什么

只公开去身份的原科学stdout/stderr gzip、PepInter逐phase日志、关键资源/独审摘要及原源文件和合同SHA。私有路径转成`source-ref:`或`package-ref:`；PID、GPU标识移除；原始资源进程表、他人命令、UUID、主机标识、序列/标签、模型权重和原rawbundle均未复制。原数字、异常栈计算语义和原件SHA保留，见[EVIDENCE-INDEX](EVIDENCE-INDEX.json)、[VALIDATION](VALIDATION.json)。

只读核对本次公开Git HEAD `2383b0a4a16c6476dd39a77523e4b68a1f0eb0ea` 与原LATEST。此目录是待根任务审查的公开准备材料，未改公开checkout、未提交、未上传。
