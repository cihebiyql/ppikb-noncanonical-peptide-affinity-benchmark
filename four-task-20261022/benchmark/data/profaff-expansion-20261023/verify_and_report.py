"""Validate frozen source-derived tables and emit a compact evidence report.

Only reads the existing source and curated files. No training or model forward.
"""
from pathlib import Path
import csv
import hashlib
import json
import math
import collections

P=Path(__file__).resolve().parent


def h(p):
    digest=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''): digest.update(b)
    return digest.hexdigest()


def rows(name):return list(csv.DictReader((P/name).open(encoding='utf8',newline='')))


def main():
    profile=json.loads((P/'profile.json').read_text(encoding='utf8'))
    allp=rows('holdup-all-explicit-backbone-projections-external.csv')
    standard=rows('holdup-standard-core-external.csv')
    clean=rows('holdup-standard-core-no-FP-no-PPIKB-overlap-external.csv')
    fp=rows('direct-fp-separate-lineage.csv')
    cen=rows('holdup-censored-contexts.csv')
    unknown=rows('unmeasured-or-unresolved-contexts.csv')
    checks={}
    def check(k,x):checks[k]=bool(x);assert x,k
    check('point_count',len(allp)==17136)
    check('human_context_conservation',len(allp)+len(cen)+len(unknown)==64635)
    check('measured_count',len(allp)+len(cen)==59568)
    check('censor_count',len(cen)==42432)
    check('unmeasured_count',len(unknown)==5067)
    check('all_direct_FP_retained_separately',len(fp)==162)
    check('standard_core_count',len(standard)==16918)
    check('PTM_count',len(allp)-len(standard)==218)
    check('source_unchanged',all(h(Path(x['path']))==x['sha256'] for x in json.loads((P/'source-hashes.json').read_text(encoding='utf8'))))
    check('human_only_every_output',all(x['peptide_source_taxon']=='9606' for table in [allp,fp,cen,unknown] for x in table))
    check('one_row_per_original_context',all(len({x['source_excel_row'] for x in t})==len(t) for t in [allp,fp,cen,unknown]))
    check('point_vs_censor_disjoint',not({x['source_excel_row'] for x in allp}&{x['source_excel_row'] for x in cen}))
    check('finite_positive_point_labels',all(math.isfinite(float(x['label'])) and float(x['label'])>0 for x in allp))
    check('no_point_labels_or_false_negatives_in_censored',all(x['label']=='' and x['confirmed_noninteraction']=='False' for x in cen))
    check('no_point_labels_or_false_negatives_in_unmeasured',all(x['label']=='' and x['confirmed_noninteraction']=='False' for x in unknown))
    check('conservative_excludes_FP_and_possible_PPIKB_overlap',all(x['same_source_FP_available']=='False' and x['PPIKB_possible_input_overlap']=='False' for x in clean))
    check('no_synthetic_smiles',all(x['smiles']=='' and x['peptide_smiles']=='' for x in allp))
    check('domains_266',len(json.loads((P/'domain-input-provenance.json').read_text(encoding='utf8')))==266)
    check('FP_transform',all(math.isclose(float(x['label']),6-math.log10(float(x['Kd_uM'])),abs_tol=1e-12) for x in fp))
    check('only_calibrated_HU_endpoints_in_point_track',all(x['endpoint']=='holdup_derived_pKd' and x['label_kind']=='calibrated_holdup_composite_point' for x in allp))
    check('all_point_full_2022_construct_unknown',all(x['actual_assay_construct_verified']=='False' for x in allp))
    byrow={}
    for line in (P/'source-lineage-chemistry.jsonl').open(encoding='utf8'):
        x=json.loads(line);byrow[str(x['source_excel_row'])]=x
    check('sidecar_row_count',len(byrow)==64635)
    check('all_labels_trace_to_original_composite',all(math.isclose(float(x['label']),float(byrow[x['source_excel_row']]['raw_source_record']['COMP_neglogKd']),abs_tol=1e-10) for x in allp))
    check('PTM_projection_is_explicit',all(x['evaluation_stratum']=='PTM_core_backbone_projection' for x in allp if x['ptm_core']=='True'))
    ptm=collections.Counter(';'.join(byrow[x['source_excel_row']]['chemistry']['ptm_tokens']) for x in allp if x['ptm_core']=='True')
    collision_audits={}
    for name,table in [('all_projected',allp),('standard_core',standard),('default_conservative',clean)]:
        groups=collections.defaultdict(list)
        for x in table:groups[(x['target_sequence'],x['peptide_sequence'])].append(x)
        collisions=[g for g in groups.values() if len(g)>1]
        collision_audits[name]={'raw_contexts':len(table),'unique_input_pairs':len(groups),'collision_groups':len(collisions),
            'rows_in_collision_groups':sum(map(len,collisions)),
            'collision_groups_same_raw_chemical_identity':sum(len({x['peptide_sequence_raw'] for x in g})==1 for g in collisions),
            'groups':[{'model_input_group_id':g[0]['model_input_group_id'],
                       'records':[{'row_id':x['row_id'],'target_name':x['target_name'],'peptide_name':x['peptide_name'],
                                   'raw_chemical_identity':x['peptide_sequence_raw'],'label':x['label']} for x in g]} for g in collisions]}
    (P/'input-collisions.json').write_text(json.dumps(collision_audits,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    same_fp_standard=sum(x['same_source_FP_available']=='True' for x in standard)
    possible_standard=sum(x['PPIKB_possible_input_overlap']=='True' for x in standard)
    evaluation={'status':'passed','checks':checks,'counts':{'default_conservative_point_rows':len(clean),'broader_standard_core_point_rows':len(standard),
                'all_projected_point_rows':len(allp),'PTM_projected_point_rows':218,'standard_same_source_FP_rows':same_fp_standard,
                'standard_PPIKB_possible_overlap_rows':possible_standard,'PTM_point_token_counts':dict(ptm),
                'default_unique_input_pairs':collision_audits['default_conservative']['unique_input_pairs'],
                'default_input_collision_groups':collision_audits['default_conservative']['collision_groups']},
                'scope':'data verification only; no new scientific model execution',
                'not_proven':['exact 2022 fusion construct identity','complete chemical graph','family independence from training','blindness after prior ProfAff FP evaluation','universal or per-row numeric censor bounds']}
    (P/'verification.json').write_text(json.dumps(evaluation,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    evidence={'primary_paper':{'doi':'10.1038/s41467-022-33018-0','url':'https://pmc.ncbi.nlm.nih.gov/articles/PMC9482650/',
                               'local_source':'pdz.xml listed in source-hashes.json'},
              'domain_construct_supplement':{'doi':'10.3390/membranes13080737','table':'S1','scope':'source-linked isolated PDZ domain; full 2022 fusion unverified'},
              'alias_identity_checks':[{'url':f'https://rest.uniprot.org/uniprotkb/{a}.json','local_path':f'sources/uniprot-{a}.json'} for a in ['Q09666','O14745','O14907']],
              'metadata_only_retrieval':True}
    (P/'external-evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    report=f'''# ProfAff 人源数据扩展：独立附加冻结

本轮新增了可用于**条件外部亲和力评价**的 holdup 数据。推荐默认表共有 **{len(clean):,} 条**，均为标准残基 core 的显式骨架投影，已去除本研究直接 FP 同一测量情境及与 PPIKB 有潜在输入重叠的情境。更宽的标准 core 表有16,918条；包含218条明确 PTM 父残基投影的诊断表共有17,136条。没有执行模型训练或推理，原13个视图、原162条 FP 和42个效应配对均未改写。

## 真实数量与端点

| 层级／表 | 行数 | 含义与用途 |
|---|---:|---|
| 原工作簿情境 |70,479|还包含无本轮 holdup 来源的上下文，不能全部作测量标签|
| 原工作簿非空测量来源 |65,157|这是表格实际数；论文正文写65,151，6条差异保留为来源差异，未自行修改|
| 已确认人源肽来源上下文 |64,635|缓存 UniProt 9606 人源范围，418个来源 accession；逐行回原xlsx核对，无差异|
| 人源 holdup 测量上下文 |59,568|17,136个点值 +42,432个删失情境|
| 人源 quantified composite holdup pKd |17,136|220个PDZ域、423个肽名称、422个化学字符串；范围3.21134–6.65566|
| 标准 core 点值 |16,918|均有 assay 化学标签，不能称完全无修饰肽|
| 推荐保守标准 core 外测 |{len(clean):,}|从上一行去除同情境FP及PPIKB潜在重叠，支持序列／孤立域输入的条件外测|
| PTM 投影诊断点值 |218|pS、pT、Kac分层，原始token保留；父残基输入丢失PTM信息|
| 人源 direct competitive FP |162|独立端点谱系表，属于原来已评价的来源，新增量0|
| 未量化 holdup |42,432|不填0亲和力、不作负例；未重建逐行数值界限|
| 未测或来源未解决 |5,067|单列，不当成删失测量或不结合|

## 化学身份与域输入

人源全集包含424个化学字符串，所有记录都带N端biotin。TTDS、Ado-Ado、Ahx和GSGSGS连接形式分别保留。Ahx属于非标准连接残基；不能把连接臂或标签包装成大量非天然核心氨基酸样本。本轮识别到的核心改动属于PTM，**未发现可据此宣称的非天然核心残基扩展集**。4种PTM化学字符串的点值分布为 `{dict(ptm)}`。另有C端酰胺化记录，侧车单独标记。

序列视图保留实际观察到的额外氨基酸，例如N端多出的D，不把作者的10mer展示列直接替代完整实测肽。GSGSGS为肽连接片段，在骨架输入中保留。TTDS、Ado-Ado、Ahx、biotin及末端化学状态不进入氨基酸字母输入，信息缺失明确写入每行。未生成SMILES，也不提供假装化学完整的图模型输入。

266个域输入来自2023年原克隆谱系Table S1。4个别名使用2022 SQL中的同一UniProt accession、当前人源taxonomy和精确域序列包含关系核实；没有用full-length canonical序列替换域。**这仍不能证明2022实验的完整His6-MBP融合构建体完全相同**，因此只能作来源关联孤立域条件评价。点值覆盖220个域；266不是有点标签的靶标数。

## 外部独立性与使用规则

PPIKB全部21,845条记录中，同一论文DOI命中0；与当前9116条冻结PPIKB输入完全相同的域×肽输入对命中0。更保守地检查“完整PPIKB靶标包含本域序列，肽为实际骨架／作者展示motif之一”时，有6个holdup点值可能重复（全人源情境共10个）。默认表将它们排除；未据字符串相似性宣称化学等价。67个域序列可在PPIKB靶标中精确包含，故**不能称严格target-cold或family-cold**。详见重叠侧车。

17,136个holdup点中150个与直接FP同情境。holdup的有效肽浓度一部分来自FP校准，另一部分使用平均浓度；剔除同情境FP不会消除共享校准依赖。ProfAff来源也已经被前一阶段FP评价使用，**这批属于补充条件外测，不是全新盲测或前瞻验证**。默认表必须保留external-only，不能与训练混合后仍叫外部测试。

holdup与direct FP分别报告指标，不能直接合并当作同精度Kd。先报告每靶标／每肽的组内结果和宏平均，再报告总体MAE、RMSE、Spearman及Pearson；10个训练seed沿用原模型，数据视图本身不重新随机划分。按PDZ域或肽背景分组进行区间估计，避免把共享校准／背景的大量行当成独立重复。

## 四类任务适用性

| 任务 | 本批新增证据 |
|---|---|
| 绝对亲和力 |可做校准型holdup pKd外部评价；direct FP仍为原162条，分轨|
| 改动效应 |本轮未生成新配对；保留PTM和上下文谱系，需另外审计等条件关系|
| 是否相互作用 |没有新的可靠二分类负例；删失不能改成不结合|
| 接触位点 |没有逐残基接触标签，新增0|

## 文件与复核

默认外测：`holdup-standard-core-no-FP-no-PPIKB-overlap-external.csv`。更宽范围、PTM投影、FP谱系、删失与未测表各自单列。`source-lineage-chemistry.jsonl`保留每一行原测量、化学token、域来源与校准说明；`domain-input-provenance.json`保留266个域的序列来源。`source-hashes.json`冻结实际源文件SHA；`additional-manifest.json`是独立附加清单，未修改原数据清单。`verification.json`包含{len(checks)}项通过的核查，`inspect_profaff_expansion.ipynb`提供不执行模型的浏览入口。

默认表的16,806行是原始测量情境，只对应16,772个独特的模型输入对。34个输入重复组涉及68行，主要为不同来源肽名称对应相同实测序列；原值全部保留，未静默平均。`input-collisions.json`列出逐条证据；每行的`model_input_group_id`和`chemical_measurement_group_id`支持按输入／化学身份分组评价与聚类区间估计。不能把这些行称为16,806个独立分子组合。PTM投影表中还会出现不同化学实体映射到相同骨架的输入碰撞，须独立分层。

来源：[原论文与方法](https://pmc.ncbi.nlm.nih.gov/articles/PMC9482650/)、[ProfAff代码归档](https://github.com/GoglG/ProfAff)、[2023域克隆资料](https://doi.org/10.3390/membranes13080737)。
'''
    (P/'README.zh-CN.md').write_text(report,encoding='utf8')
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}},
              'cells':[{'cell_type':'markdown','metadata':{},'source':['# ProfAff human external expansion\n','Read-only profile and provenance; no model execution.\n']},
                       {'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],
                        'source':['from pathlib import Path\n','import json, csv\n','root = Path.cwd()\n','profile = json.loads((root / "profile.json").read_text(encoding="utf8"))\n','profile\n']},
                       {'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],
                        'source':['manifest = json.loads((root / "additional-manifest.json").read_text(encoding="utf8"))\n','validation = json.loads((root / "verification.json").read_text(encoding="utf8"))\n','manifest["default_point_view"], validation\n']} ]}
    (P/'inspect_profaff_expansion.ipynb').write_text(json.dumps(notebook,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    manifest=json.loads((P/'additional-manifest.json').read_text(encoding='utf8'))
    manifest['files']=[{'path':p.name,'bytes':p.stat().st_size,'sha256':h(p)} for p in sorted(P.iterdir()) if p.is_file() and p.name!='additional-manifest.json']
    manifest['verification']='verification.json'
    (P/'additional-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    reread=json.loads((P/'additional-manifest.json').read_text(encoding='utf8'))
    assert all(h(P/x['path'])==x['sha256'] for x in reread['files'])
    print(json.dumps({'passed_checks':len(checks),'counts':evaluation['counts'],'all_manifest_file_hashes_verified':True,'manifest_sha256':h(P/'additional-manifest.json')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
