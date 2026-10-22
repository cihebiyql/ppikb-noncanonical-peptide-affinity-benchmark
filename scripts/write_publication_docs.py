from pathlib import Path
import hashlib
import json
import re
import shutil

P=Path(r'D:\work\科研工作台\research-tasks\peptide-binding-nc-benchmark-20261021')
AUDIT=Path(r'D:\work\科研工作台\publication-audits\ppikb-nc-20261022')
REPO=Path(r'C:\Users\ciheb\codex-publications\ppikb-noncanonical-peptide-affinity-benchmark')
NAME='cihebiyql/ppikb-noncanonical-peptide-affinity-benchmark'
URL='https://github.com/'+NAME


def sha(q):
    h=hashlib.sha256()
    with Path(q).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def main():
    summary=json.loads((REPO/'manifest/packaging-summary.json').read_text())
    for name in ['docs','permissions','LICENSES','scripts','datasets/PPIKB-v5','support/batch','support/reproduction-standard']:
        (REPO/name).mkdir(parents=True,exist_ok=True)
    extras=[]
    def copy(q,destination):
        q=Path(q);dest=REPO/destination;dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open('xb') as output, q.open('rb') as source:shutil.copyfileobj(source,output)
        assert sha(q)==sha(dest)
        extras.append(dict(public_path=destination,bytes=dest.stat().st_size,sha256=sha(dest),source_path=str(q),modified=False))
    for q in (AUDIT/'permissions').glob('*'):
        if q.is_file():copy(q,'permissions/'+q.name)
    for n in ['summary.json','coverage.json','HANDOFF.json','skipped.json']:
        if (AUDIT/'security'/n).exists():copy(AUDIT/'security'/n,'permissions/security-'+n)
    for n in ['package_publication.py','test_package_publication.py','write_publication_docs.py']:
        copy(AUDIT/n,'scripts/'+n)
    for q in (AUDIT/'helpers').glob('*'):
        if q.is_file() and q.suffix in ['.py','.md','.json']:copy(q,'scripts/'+q.name)
    raw=P.parent/'peptide-binding-expanded-corpus-20261021/resources/PPIKB_all_endpoints'
    for n in ['PPIKB-v5-Affinity-Dataset-main.xlsx','figshare-v5-metadata.json','resource-manifest.json','all-assets-manifest.json','verification.json']:
        copy(raw/n,'datasets/PPIKB-v5/'+n)
    workspace=P.parents[1]
    for n in ['campaign.json','summary-rows.json']:
        copy(workspace/'复现/batches/peptide-binding-nc-benchmark-20261022'/n,'support/batch/'+n)
    for q in (workspace/'复现/规范').iterdir():
        if q.is_file() and q.suffix in ['.py','.md','.json']:copy(q,'support/reproduction-standard/'+q.name)
    license_sources={
        'MGraphDTA-MIT.txt':'model-audit/author-source/guaguabujianle__MGraphDTA/source/LICENSE',
        'DGDTA-GPL-3.0.txt':'model-audit/author-source/luojunwei__DGDTA/source/LICENSE',
        'MRBDTA-Apache-2.0.txt':'model-audit/author-source/LiZhang30__MRBDTA/source/LICENSE',
        'FusionDTA-Apache-2.0.txt':'model-audit/author-source/yuanweining__FusionDTA/source/LICENSE',
    }
    for n,q in license_sources.items():copy(P/q,'LICENSES/'+n)
    def write(rel,text):
        q=REPO/rel
        with q.open('x',encoding='utf-8',newline='\n') as h:h.write(text)
    write('.gitignore','__pycache__/\n*.pyc\n.artifact-downloads/\n*.partial\n.env\n.venv/\n')
    write('.gitattributes','* -text\n*.xlsx binary\n*.png binary\n*.pdf binary\n')
    original=(P/'reporting/delivery-v1/基准结果与复现说明.md').read_text()
    def rewrite(match):
        value=match.group(1).replace('\\','/')
        prefix=P.as_posix()+'/'
        if value.startswith(prefix):
            rel=value[len(prefix):]
            target='../benchmark/'+rel if (REPO/'benchmark'/rel).exists() else URL+'/releases/tag/v1.0.0'
            return ']('+target+')'
        return match.group(0)
    public=re.sub(r'\]\(<([^>]+)>\)',rewrite,original)
    public=public.replace('[本地交互报告](http://127.0.0.1:2647/)','[公开交付结构与恢复步骤](ARTIFACTS.md)')
    write('docs/基准结果与复现说明.md',public)
    write('README.md',f'''# PPIKB 非标准肽—蛋白亲和力基准

**2,099条非标准肽记录、7,520条标准肽对照，5个前人架构＋随机森林，全部10个训练随机种子。**

本仓库公开2026年10月22日完成的基准代码、数据、测试结果、训练日志、权重、缓存及分析文档。代码和便于浏览的结果位于Git，大型产物位于同一仓库的[Releases]({URL}/releases/tag/v1.0.0)。每个文件和分卷均有SHA-256清单。

## 先看结果

- [完整结果与复现说明](docs/基准结果与复现说明.md)
- [全部聚合指标CSV](benchmark/reporting/final-v1/summary.csv)
- [NC主任务指标CSV](benchmark/reporting/final-v1/main-NC.csv)
- [调参与训练元信息](benchmark/reporting/training-metadata-v1/超参数与训练元信息.md)
- [完整epoch预算诊断](benchmark/reporting/training-logs-v1/预算诊断说明.md)
- [逐文件清单](manifest/source-files.jsonl) · [分卷与校验值](manifest/artifact-assets.json) · [数据/产物恢复](docs/ARTIFACTS.md)

![NC测试MAE，10种子均值与样本SD](benchmark/reporting/figures-v1/actual-v1/figures/png/fig_01_nc_mae.png)

严格隔离后的泛化仍弱。来源与肽依赖隔离测试中，12个可训练组合的NC测试MAE均高于标准肽训练中位数常数参考（1.3178）。靶标参考同源隔离测试中，最低展示平均MAE为DeepNC-GEN的NC训练模型：1.2978±0.0554 pKd，R²为0.0638±0.0551。这里的最小均值是描述结果，不是显著性结论。

## 基准范围

| 项目 | 已完成内容 |
| --- | --- |
| 端点 | Kd转pKd；全物种；Ki/IC50保留于原库 |
| NC互斥分层 | 非天然/D型/骨架723；PTM1002；混合268；其他106 |
| 前人架构 | GraphDTA-GIN、MGraphDTA、DGDTA-CL、DeepNC-GEN、GS-DTA |
| 额外基准 | RF-Morgan2-chiral-AAC-DP；3个确定性参考规则 |
| 固定划分 | 来源＋肽依赖隔离；参考靶标同源隔离 |
| 训练对照 | NC_only与standard_only，分别验证集调参 |
| 随机种子 | 每个可训练组合均为0–9；固定数据划分 |
| 计算覆盖 | 400个有效NN候选＋80个RF候选；200＋40个选择模型 |
| 指标 | MAE、RMSE、Pearson、Spearman、R²；11,540组汇总、115,400条逐种子指标 |
| 外部验证 | PTM67主测试＋8条件样本；2条参考靶标冷是67的子集；另补8条非天然肽＋5条标准肽 |
| 独立复核 | NN600与RF120份评分重新计算，指标差异0；240结果记录全部通过验收 |

这是五个发表架构在共同PPIKB数据上的适配重训；训练预算和兼容性修补均已披露。标准训练集更大、靶标/来源分布也不同，对照不能直接作因果解释。外部数据主要验证新来源与声明化学实体，支持范围见完整报告。当前没有构建创新模型。

## 仓库与完整产物

本次原项目文件共{summary['original_files']:,}个，其中{summary['included_files']:,}个可公开文件已分配到Git或Release；{summary['excluded_files']:,}个第三方原档/运行依赖/可再生字节码等文件逐项登记在[排除清单](manifest/excluded-files.jsonl)。研究自行生成的权重、缓存、预测、指标与日志完整保留。

Git包含{summary['git_files']:,}个原项目文件；Release包含{summary['release_files']:,}个大型产物，分成{summary['release_parts']}卷。所有原项目文件按原字节保存，原始绝对路径作为历史provenance保留；本页及docs提供面向公开仓库的相对链接。

PPIKB原始v5工作簿与许可元数据见[datasets/PPIKB-v5](datasets/PPIKB-v5/)。复现标准与本次5篇登记见[support](support/)，保留了全部中断、审计失败及恢复证据。

## 获取完整内容

```bash
git clone https://github.com/{NAME}.git
cd ppikb-noncanonical-peptide-affinity-benchmark
python scripts/restore_artifacts.py
python scripts/restore_upstream.py
```

第一步恢复分卷中的研究产物，第二步按URL、commit和SHA获取上游源文件；都不会启动训练。原冻结合同中的路径、版本和运行时限作为历史证据保留。重跑环境与输入适配说明见[方法与数据说明](benchmark/report-preparation/方法与数据说明.md)及各methods目录。

## 来源与许可

PPIKB原始数据：[Figshare v5，10.6084/m9.figshare.31082407.v5](https://doi.org/10.6084/m9.figshare.31082407.v5)，**CC BY 4.0**。本研究进行端点筛选、化学分层、质量标记、严格划分与模型评估，原始21845行工作簿一并保留。外部来源和原始端点详见external-validation的清单。

第三方组件逐项遵守原许可证，见[LICENSES](LICENSES/)和[许可证据](permissions/policy.json)。GraphDTA、DeepNC、GS-DTA的固定版本缺少明确再分发许可，因此其源文件采用原链接＋固定commit＋SHA＋下载恢复；本仓库不为这些代码另授许可。MGraphDTA保留MIT、DGDTA及其修改源保留GPLv3，其他组件和论文原件保持各自许可。供应商保护运行时与安装依赖用来源记录和环境说明替代。
''')
    write('docs/ARTIFACTS.md',f'''# 完整数据与产物

## 存储布局

`benchmark/`镜像原任务目录。每份原文件在`manifest/source-files.jsonl`中都有path、bytes、sha256及storage字段：`git`表示随clone取得；`release`表示在分卷包内。`manifest/artifact-assets.json`列出精确分卷名、顺序、字节数与SHA256。

所有{summary['release_parts']}个`benchmark-artifacts.tar.gz.partNNN`附件位于[同一Release]({URL}/releases/tag/v1.0.0)。按清单顺序拼接可得到gzip压缩tar；解开后与Git的`benchmark/`目录合并。提供的恢复器流式下载和提取，不需要先把多个分卷拼接成额外的大文件。

```bash
python scripts/restore_artifacts.py
python scripts/restore_artifacts.py --verify-only
```

权重、缓存、逐条预测、大型审计JSON和完整逐种子指标保留原字节。自行生成的研究二进制不会因文件大而省略。确定性参考规则的10种子记录也保留，数值相同不代表10次独立拟合。

## 原始来源与可复用代码

`datasets/PPIKB-v5/`保存CC BY4.0的完整原始工作簿、官方许可元数据和下载校验记录；`benchmark/data-protocol/`保存本轮2099NC＋7520标准肽的处理、分组和拆分资料。

`scripts/restore_upstream.py`使用`permissions/fetch-lock.json`中的官方ZIP URL、固定commit和SHA恢复上游代码。下载原代码不等于取得再分发许可。仓库中的自编适配、入口、修复说明及有明确许可的原作者组件可直接浏览。

第三方保护运行时、环境依赖、无明确许可的源/PDF/上游混合原档，以及可再生Python字节码的逐文件排除理由在`manifest/excluded-files.jsonl`。这些文件仍在原本地目录；原链接和身份清单已保留。

原报告应用依赖受保护的供应商运行时，公开包保留自编内容、聚合数据、静态图和Markdown报告。公开README与`docs/基准结果与复现说明.md`使用GitHub相对链接；`benchmark/`中的原始文件保持其已审计SHA，包括原本的本地路径。

## 完成与失败记录

真正完成状态为`benchmark/reporting/delivery-v1/FINAL-CLOSURE.json`与`benchmark/review/postscore-driver-v2/runs/actual-v2/POSTSCORE-AUDIT-READY.json`。历史状态、两次技术中断、旧审计与行政路径失败均保留。`support/batch/summary-rows.json`只对应这次五篇架构适配重训，原其他批次未并入。

上传打包仅复制、压缩、哈希和核验，科学数据、模型与原冻结代码没有更改，也没有重新训练或挑选测试结果。
''')
    write('LICENSES/README.md','''# Component licenses and provenance

This research archive uses component-specific licensing. It does not apply a blanket MIT license to third-party material.

- PPIKB v5 source data: CC BY 4.0, https://doi.org/10.6084/m9.figshare.31082407.v5 . Credit the database authors and retain the original Figshare metadata. Changes in this benchmark include filtering, annotation, splitting, and derived analysis.
- MGraphDTA author software and marked adaptations: retain the supplied MIT license and copyright notice.
- DGDTA author software and marked adaptations: GNU GPL v3, with corresponding original and modified source, patch records, and modification descriptions retained. Compatibility changes remove unsupported GCN dropout arguments, correct the concatenated feature width, and set the LSTM batch layout.
- MRBDTA/FusionDTA exploratory author snapshots: retain their Apache 2.0 files and notices; they are historical assets and do not increase the five-model benchmark count.
- Open-access paper PDFs retained in this archive remain unchanged and retain each paper's printed terms, including noncommercial/no-derivatives conditions where present.
- GraphDTA, DeepNC, GS-DTA and other snapshots lacking explicit permission are fetched from their original repositories rather than redistributed here. The fixed URL/commit/hash inventory is retained.
- Project-authored reports, measurements, and outputs are published by the repository owner. This archive does not assert rights over original publisher documents or grant a new blanket license to all project-authored material.

See ../permissions/policy.json and ../permissions/evidence.json for exact file boundaries and evidence. Own generated figure PDFs are distinct from publisher originals. Provider-protected application runtime and installed package trees are excluded; their scientific data and authored report content remain included.
''')
    write('datasets/PPIKB-v5/README.md','''# PPIKB v5 original data

Source: https://doi.org/10.6084/m9.figshare.31082407.v5 . Official API metadata: https://api.figshare.com/v2/articles/31082407 . The local original metadata identifies CC BY 4.0: https://creativecommons.org/licenses/by/4.0/ . Preserve attribution to the PPIKB database authors as recorded in figshare-v5-metadata.json.

The original Main workbook has 21,845 rows. It includes multiple endpoints. This benchmark uses the Kd observations, preserving other endpoints in the original workbook. The cleaned modeling view is 2,099 NC plus 7,520 standard-residue observations. Chemical annotation, quality flags, fixed splits, labels, and derived results are in benchmark/data-protocol and the release artifacts.

These files are byte copies of the previously downloaded source. Checksums are recorded in manifest/additional-source-files.json at the repository root. No raw source rows were deleted from the workbook during this publication.
''')
    write('manifest/additional-source-files.json',json.dumps(extras,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='publication_docs_written',copied_extra_files=len(extras),readme_sha256=sha(REPO/'README.md'))))


if __name__=='__main__':main()
