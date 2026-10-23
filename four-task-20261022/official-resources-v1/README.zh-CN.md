# 官方资源获取与校验

本批提供输入资源获取工具，**不是一键完整复现**。锁包含198项资源：197项具备精确恢复信息（170文件＋27归档成员），1项原始坐标归档URL待核。覆盖八项方法、四组主数据来源和19项官方预训练文件。工具只下载、校验及安全解压，不执行作者代码、安装依赖或加载模型。

- [资源锁](fetch-lock.json)：官方URL、固定commit/revision或文件身份、大小、SHA和许可范围。
- [资源索引](resource-index.csv)：197可恢复与1pending逐项清点。
- [恢复工具](restore_official.py)与[合成测试](test_restore_official.py)。
- [校验说明](VALIDATION.json)、[文件SHA清单](FILE-MANIFEST.json)。

本公开锁移除了绝对私人路径。`workspace-ref:`、`remote-record-ref:`等仅表示原审计记录的来源身份，不是可下载地址；恢复只使用每项的官方URL和SHA。第三方比对源码、原始论文、作者表和模型文件未复制到本目录。

## 用法

需要Python标准库，无需安装包。fetch/extract要求显式锁SHA；list与离线verify不会联网。当前锁SHA256：`4297d59b13169f5031ac9f72e160ca45cb076d700860b2cbea27bdeec0ce5e55`。

```text
python restore_official.py list
python restore_official.py --expect-lock-sha256 4297d59b13169f5031ac9f72e160ca45cb076d700860b2cbea27bdeec0ce5e55 fetch --id data-PPIKB-main-v5 --dest restored
python restore_official.py verify --id data-PPIKB-main-v5 --path restored/data-PPIKB-main-v5/Affinity-Dataset-main-v5.xlsx
python restore_official.py --expect-lock-sha256 4297d59b13169f5031ac9f72e160ca45cb076d700860b2cbea27bdeec0ce5e55 fetch --id data-PDZome2023-domain-source-pdf --dest restored
```

嵌套资源逐层核对父归档和成员。已有相同SHA可复用；不同内容拒绝覆盖。固定HTTPS官方域名、每跳重定向、大小/SHA、解压预算、路径穿越、符号/硬链接、reparse与归档循环均有检查，支持Windows长路径。HTTP403、认证及验证码失败会停止，不尝试绕过。

## 版本与适用范围

DTA五方法绑定实际使用的固定commit和同commit恢复归档，历史raw文件取得与兼容patch另有谱系。GraphDTA、DeepNC、GS-DTA没有明确源码许可证据，保留official-fetch；MGraphDTA MIT与DGDTA GPL3分别记录。

SWING实际a2b5bb4…版本与标注CC BY4.0的Zenodo v1并非同字节，许可不混用。PepInter代码21717699（完整commit9046f857…、MIT）、18604811回归模型（CC BY4.0）和最新21715291五张来源表分开；实际使用的旧24张监督表保持原身份。

UniAIR原代码e1b48d0…、HF模型d2a6d58…与HER2数据b0bd58a…分开。作者仓库MIT及模型card不能自动覆盖整个HER2数据包。AbSci底层测量表固定commit的自定义Clear BSD要求数据引用/发表署名Absci Corporation(2023)；该源许可不替作者衍生结构背书。[原始许可](https://raw.githubusercontent.com/AbSciBio/unlocking-de-novo-antibody-design/cd2bd4b6932b5301d435555dc22084d407e4b92b/LICENSE)

PPIKB Main v5绑定Figshare文件65742021。ProfAff原工作簿、SQL及域构建体补充分别锁定，FP与HU派生视图分轨；软件归档other-open与测量论文CC BY4.0范围分别记录。额外ESM两个官方pt也保留原下载URL及SHA，参考源码commit不冒充实际安装版本。

1项pending是接触64复合物使用的PepBDB20200318坐标归档：本地历史大小/SHA已知，官方原始URL尚待重新绑定。工具拒绝对此项fetch；当前RCSB坐标不充当原归档字节替身。

自有清洗/兼容patch、冻结视图生成和依赖环境仍是运行复现链的后续步骤。本批未做大规模线上下载或生物模型执行，197项可恢复表示精确资源锁已具备，并非197项本轮下载成功。

## 校验与许可

本批执行26项纯合成安全测试，包含正常下载模拟、坏SHA、截断/超量响应、嵌套归档、越界路径、链接、拒覆盖和Windows长路径；没有模型前向或训练。工具与说明为自有产物，资源依原来源许可使用，本目录不新设统一MIT许可。
