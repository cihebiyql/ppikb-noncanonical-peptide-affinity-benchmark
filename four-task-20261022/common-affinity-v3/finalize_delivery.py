"""Publish-safe metadata/report assembly only; never loads a model or raw features."""
import collections
import csv
import datetime
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
GENERIC_SHA = '60f29ff73f66845f580d4f13e0d9abc88717d30192b68c7765f6afadf7e1b447'


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(pathlib.Path(path).read_text(encoding='utf-8-sig'))


def dump(name, obj):
    (HERE / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def rel(path):
    return pathlib.Path(path).resolve().relative_to(ROOT.resolve()).as_posix()


def entry(path):
    path = pathlib.Path(path)
    return {'path': rel(path), 'bytes': path.stat().st_size, 'sha256': sha(path)}


def main():
    contract = load(HERE / 'comparison-contract.json')
    score = load(HERE / 'score-receipt.json')
    audit = load(HERE / 'independent-audit.json')
    assert audit['passed'] and not audit['errors']
    assert score['eligible_fixed_applications'] == 540
    assert sha(ROOT / 'reports/delivery-20261023/generic-completed-metrics-all-panels.csv') == GENERIC_SHA
    for item in contract['prediction_sources'] + contract['source_locks']:
        assert sha(item['path']) == item['sha256'], item['path']

    canonical = {}
    for panel, item in contract['canonical'].items():
        canonical[panel] = {key: item[key] for key in ['sha256', 'n', 'parent_sha256', 'endpoint']}
        canonical[panel].update(path=rel(item['path']), parent_view=rel(item['parent_view']),
                                chemistry_counts=dict(collections.Counter(item['strata_by_row_id'].values())))
    methods = {}
    for item in contract['prediction_sources']:
        methods.setdefault(item['method'], {key: item.get(key) for key in ['method', 'family', 'training_scope', 'protocol_note']})
    public_protocol = {
        'schema': 'common-affinity.public-safe-protocol.v3',
        'private_frozen_contract_sha256': sha(HERE / 'comparison-contract.json'),
        'canonical_test_cohorts': canonical,
        'seeds': list(range(10)), 'endpoint': 'pKd',
        'method_catalog': list(methods.values()),
        'eligibility_rule': contract['eligibility_rule'],
        'coverage_and_scope_only': contract['coverage_and_scope_only'],
        'source_locks': [{**item, 'path': rel(item['path'])} for item in contract['source_locks']],
        'source_and_target_separate': True, 'no_test_based_subset_or_method_selection': True,
        'training_cohorts_not_equalized': True,
        'uncertainty': 'Sample SD (ddof=1) over computational seeds; not biological confidence intervals.',
        'paired_comparison': 'All unordered method pairs per panel and same seed; MAE_A - MAE_B; no p-values reported or used.',
        'undefined_metrics': 'Unavailable correlations are null/empty, never zero-imputed; valid seed counts retained.',
        'precision': 'Canonical original CSV float64 labels. Historical PepInter worker float32 precision is disclosed in original audits; its saved common prediction labels were separately canonicalized.',
        'new_fits': 0, 'new_forwards': 0, 'deserialized_models': 0, 'GPU_jobs': 0,
        'generic_selected_model_count_unchanged': 1050, 'generic_candidate_fit_count_unchanged': 2100,
        'generic_aggregate_sha256': GENERIC_SHA,
        'no_raw_label_map_or_sequences_in_this_protocol': True,
    }
    dump('PUBLIC-PROTOCOL.json', public_protocol)

    swing = ROOT / 'methods/interaction/continuation-20261023/swing-affinity'
    closure_path = swing / 'all20-physical-local-and-independent-numerical-closure.json'
    closure = load(closure_path)
    assert closure['total_model_seed_count'] == 20
    refs = closure['per_seed_actual_local_SHA_receipts']
    assert {(x['panel'], x['seed']) for x in refs} == {(p, s) for p in ['source', 'target'] for s in range(10)}
    for item in refs:
        assert sha(item['path']) == item['sha256']
    numerical = []
    for panel in ['source', 'target']:
        path = swing / f'affinity-{panel}-independent-audit.local-final.json'
        item = load(path)
        assert item['all10_actual_and_verified'] and item['completed_and_verified_seeds'] == list(range(10)) and not item['errors']
        numerical.append(entry(path))
    old_status = ROOT / 'reports/delivery-20261023/STATUS.json'
    # The old public snapshot is an immutable point-in-time delivery, not a live counter.
    addendum = {
        'schema': 'state-addendum.saved-prediction-comparison.v3',
        'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'swing_absolute_pKd_scientific_models': 20,
        'swing_absolute_pKd_physically_local_models': 20,
        'actual_local_model_payload_bytes': closure['total_actual_model_payload_bytes'],
        'closure_completed_at': closure['completed_at'],
        'closure': entry(closure_path), 'local_final_numerical_audits': numerical,
        'small_per_seed_receipts_rehashed': 20,
        'large_payloads_not_rehashed_in_this_comparison': True,
        'original_public_stage_snapshot_not_rewritten': entry(old_status),
        'original_snapshot_interpretation': 'The earlier 12:31 UTC snapshot recorded 13/20 local at that time; this separate later addendum records 20/20 after actual SHA closure.',
        'no_new_scientific_experiment': True, 'new_fit': 0, 'new_forward': 0,
    }
    assert addendum['actual_local_model_payload_bytes'] == 43372437689
    dump('STATE-ADDENDUM.json', addendum)

    with (HERE / 'ten-seed-mean-sampleSD.csv').open(encoding='utf-8-sig', newline='') as f:
        summaries = list(csv.DictReader(f))
    rows = {(x['panel'], x['method'], x['stratum']): x for x in summaries}
    assert len(rows) == 432

    def fmt(row, metric):
        m, s = row[metric + '_mean'], row[metric + '_sampleSD']
        return f'{float(m):.4f} ± {float(s):.4f}' if m and s else '未定义'

    lines = [
        '# 固定共同测试集亲和力比较 v3', '',
        '在预先冻结的同一批测试记录上，完成来源隔离 source 683 条、靶标隔离 target 946 条的比较。每面板包含 27 个完整模型/表征方案，每方案使用种子 0–9，共 540 次固定预测评分。所有模型均复用已经保存的预测，本轮没有训练、推理或加载模型对象。', '',
        '比较端点统一为 pKd。逐条核对测试 ID、原始 CSV 的 float64 标签及端点，共 439,830 项记录级检查；独立复算 49,320 项数值检查，包含与既有固定子集结果的 2,880 项交叉核对，错误为 0，最大绝对差 2.84×10⁻¹⁴。', '',
        '## 解释范围', '',
        '共同测试记录已经对齐，训练覆盖和表征条件仍有差异。原手工序列、手性 Morgan 与五个 DTA 方法使用原 9,116 条视图；ESM 与配套手工对照使用完全相同的 7,419 条可编码记录；SWING 使用 7,669 条记录；PepInter 骨架头使用 6,336 条记录。因此这些分数反映各既定方案在共同测试集上的表现，不能仅据此归因于架构或预训练。', '',
        'ESM 与同队列手工对照具有相同 train/validation/test ID，但沿用各自已冻结的特征与头部配置（包括 Ridge 求解器差异）。DTA 是迁移到本任务的前人模型；历史标识 DGDTA-CL 对应实际采用 MSE 的模型，不另算一个对比学习方案。SWING 是原生 grammar/Doc2Vec 表征加回归端点适配及验证集网格，不作为原论文亲和力任务的完整复现。PepInter 为冻结监督骨架与头部组件，其监督预训练暴露与普通 ESM 预训练分开解释。', '',
        '手性 Morgan 从实际 SMILES 提取 radius=2、2048 位、includeChirality=True 指纹；字母序列方法不能识别相同骨架对应的 D/L、PTM 等完整化学差异。五个 DTA 图实现的手性表达限制见原最终审计。共同队列仅覆盖 source 60 条、target 88 条带非标准注释记录，不能代替完整非标准肽主测试。', '',
        '表格按方案名称排列，列出全部 27 个方案，不按测试性能筛选。数值为十种子均值 ± 样本标准差（ddof=1）；确定性模型种子 SD 为 0 属于真实结果。它们描述计算重复，不能作为独立生物实验置信区间。', '',
    ]
    for panel, title in [('source', '来源隔离：共同测试 683 条'), ('target', '靶标隔离：共同测试 946 条')]:
        lines += ['## ' + title, '', '| 模型/表征方案 | MAE | RMSE | R² | 非标准注释子集 MAE |', '|---|---:|---:|---:|---:|']
        for method in sorted(methods):
            if method == 'PepInter_cached_standard_only':
                continue
            item = rows[panel, method, 'all']
            nc = rows[panel, method, 'NC_all']
            lines.append(f"| {method} | {fmt(item, 'mae')} | {fmt(item, 'rmse')} | {fmt(item, 'r2')} | {fmt(nc, 'mae')} |")
        lines += ['', '非标准注释子集样本量：' + ('60' if panel == 'source' else '88') + '。完整标准肽、PTM、其他非标准残基、D/骨架变化及交集分层见汇总 CSV。', '']
    lines += [
        '## 从现有结果可以得出的判断', '',
        '来源隔离的共同队列中，多数方法的 R² 接近 0 或为负；靶标隔离中也仅有有限提升。部分树模型超过常数先验，但当前结果不支持“复杂模型普遍优于传统基准”的结论。两面板独立报告，来源隔离表现不能替代新靶标外推证据。', '',
        '## 覆盖、精度与配对差值', '',
        '仅标准肽的 PepInter cached 组件虽然完成十种子，但只覆盖 source 288/683、target 425/946，列入 coverage.csv，不缩小共同队列为它补排名。效应任务、UniAIR 单 HER2 背景 DDG 组件及 RDE 属于不同端点或测试记录，不加入此绝对亲和力表。旧 GraphDTA 固定比较条目与最终 DTA 结果为同一逻辑模型，采用最终记录避免重复。', '',
        '本轮以 canonical 原始 CSV float64 标签统一重算。PepInter 原 worker 的 float32 标签精度差异在既有审计中保留；共同预测文件此前已单独对齐原始标签，不把原 worker 的数值误写为 float64 位级相同。未定义相关性保留空值及 valid_seeds，不填成 0。', '',
        '全部无序模型对均按同面板、同种子计算 MAE_A − MAE_B：7,020 条种子差值、702 条均值/样本 SD 汇总。负值表示 A 的 MAE 较低。未报告或使用 p 值；相同种子编号不等于不同模型共享同一随机轨迹，此处只作计算性配对汇总。', '',
        '八个报告分层包括总体、五个互斥化学注释层及 NC_all、PTM_bearing 两个派生层。派生层与基础层重叠，不能相加计算新样本数。', '',
        '## 文件与状态', '',
        '- [完整十种子汇总](ten-seed-mean-sampleSD.csv)、[逐种子指标](per-seed-metrics.csv)、[覆盖清单](coverage.csv)。',
        '- [全部模型对差值汇总](paired-seed-MAE-summary.csv)、[逐种子差值](paired-seed-MAE-differences.csv)。',
        '- [独立数值审计](independent-audit.json)、[评分收据](score-receipt.json)、[公开协议](PUBLIC-PROTOCOL.json)。',
        '- [后续物理交付状态补充](STATE-ADDENDUM.json)：SWING pKd 20/20 已完成本地 SHA 与独立数值闭环，模型字节 43,372,437,689。原已公开 12:31 快照当时的 13/20 记录保持冻结。',
        '- [公开文件白名单](publication-scope.json)与[最终交付收据](DELIVERY-RECEIPT.json)。原始标签映射合同和单条预测缓存仅本地保存，不属于公开负载。', '',
        '本轮不增加 generic 1,050 个已选模型或 2,100 次候选拟合的计数；540 次固定评分不是新训练，27 个方案也不等于 27 篇论文或 27 个独立实验。', '',
    ]
    (HERE / 'REPORT.zh-CN.md').write_text('\n'.join(lines), encoding='utf-8')

    private = ['comparison-contract.json', 'saved-prediction-cache/']
    public = [
        'REPORT.zh-CN.md', 'PUBLIC-PROTOCOL.json', 'STATE-ADDENDUM.json',
        'coverage.csv', 'per-seed-metrics.csv', 'ten-seed-mean-sampleSD.csv',
        'paired-seed-MAE-differences.csv', 'paired-seed-MAE-summary.csv',
        'independent-audit.json', 'score-receipt.json', 'prediction-provenance.json',
        'preparation-note-v1.json', 'prepare_catalog.py', 'score_common.py',
        'verify_common.py', 'finalize_delivery.py', 'publication-scope.json',
        'DELIVERY-RECEIPT.json', 'local-file-index.json',
    ]
    dump('publication-scope.json', {
        'schema': 'publication.allowlist.common-affinity-v3',
        'prepared_only_not_uploaded_by_this_task': True,
        'public_allowlist_relative_to_this_directory': public,
        'private_excluded_paths': private,
        'reason': 'Private frozen contract and cached original prediction CSV contain original per-record truth; public outputs contain aggregate analysis and metadata/code only.',
        'recursive_directory_upload_forbidden': True,
        'external_references_are_metadata_not_automatic_publication_authorization': True,
    })
    for filename in public:
        if filename not in ['DELIVERY-RECEIPT.json', 'local-file-index.json']:
            assert (HERE / filename).is_file(), filename
    # Assert the public protocol cannot leak rowwise identifiers/labels through its metadata.
    public_text = (HERE / 'PUBLIC-PROTOCOL.json').read_text(encoding='utf-8')
    for marker in ['label_float64_by_row_id', 'strata_by_row_id', 'PPIKB_all_endpoints:', 'peptide_sequence', 'target_sequence']:
        assert marker not in public_text, marker
    receipt = {
        'status': 'complete_independently_verified_fixed_prediction_comparison',
        'completed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'canonical_test_n': {'source': 683, 'target': 946},
        'methods_per_panel': 27, 'complete_method_panel_conditions': 54,
        'seed_ids': list(range(10)), 'fixed_scoring_applications': 540,
        'coverage_only_conditions': 2, 'per_seed_stratum_metric_rows': 4320,
        'ten_seed_summary_rows': 432, 'paired_difference_rows': 7020,
        'paired_summary_rows': 702, 'exact_ID_label_endpoint_checks': 439830,
        'independent_numeric_checks': 49320,
        'existing_fixed_score_cross_checks': 2880,
        'numeric_errors': 0, 'max_abs_numeric_difference': audit['maximum_absolute_numeric_difference'],
        'no_dynamic_test_intersection': True, 'no_test_tuning': True,
        'new_fit': 0, 'new_forward': 0, 'model_deserializations': 0, 'GPU_jobs': 0,
        'training_not_equalized': True, 'not_a_biological_significance_analysis': True,
        'generic_selected_1050_unchanged': True, 'generic_candidate_2100_unchanged': True,
        'generic_aggregate_sha256': GENERIC_SHA,
        'swing_local_closure_referenced_models': 20,
        'old_public_stage_snapshot_unchanged': True,
        'public_protocol_checked_without_raw_labels_or_sequences': True,
        'publication_status': 'prepared_allowlist_only; no upload or push in this task',
        'output_artifacts': [entry(HERE / n) for n in public if n not in ['DELIVERY-RECEIPT.json', 'local-file-index.json']],
        'private_frozen_contract': entry(HERE / 'comparison-contract.json'),
        'unchanged_prediction_sources': len(contract['prediction_sources']),
        'code_sha256': sha(__file__),
    }
    dump('DELIVERY-RECEIPT.json', receipt)
    files = [x for x in HERE.rglob('*') if x.is_file() and x.name != 'local-file-index.json']
    dump('local-file-index.json', {
        'schema': 'local-delivery.file-index.v1',
        'self_excluded_to_avoid_recursive_hash': True,
        'files': [{**entry(x), 'publication': 'public_allowlisted' if x.relative_to(HERE).as_posix() in public else 'private_local_only'} for x in sorted(files)],
    })
    print({'status': receipt['status'], 'receipt_sha256': sha(HERE / 'DELIVERY-RECEIPT.json'),
           'public_files': len(public), 'local_files_indexed': len(files),
           'generic_csv_sha256': sha(ROOT / 'reports/delivery-20261023/generic-completed-metrics-all-panels.csv')})


if __name__ == '__main__':
    main()
