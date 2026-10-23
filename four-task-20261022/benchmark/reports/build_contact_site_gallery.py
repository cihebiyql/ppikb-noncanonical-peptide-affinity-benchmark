"""Show every held-out complex using existing ten-seed predictions only."""
# CONFIGURATION -- source positions, fixed test IDs; no fitting or inference.
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / 'data/ppikb_contact_experimental_64complex_dependency_cold_v2.csv'
RUNS = ROOT / 'runs/cpu-contact64-v1/ppikb_contact_experimental_64complex_dependency_cold_v2'
OUTPUT_DIR = ROOT / 'reports/contact-site-gallery-v3'
MODELS = ['constant', 'linear', 'random_forest', 'extra_trees', 'hist_gradient_boosting']
DISPLAY = ['Prior', 'Linear', 'Random forest', 'Extra trees', 'Histogram GB']
SEEDS = range(10)
WINDOW = 100
OUTPUT_FORMATS = ['pdf', 'png', 'jpg']
DPI = 220
EN_SERIF_FALLBACK = ['Times New Roman', 'Liberation Serif', 'DejaVu Serif']

import hashlib
import json
import textwrap
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.backends.backend_pdf import PdfPages
from openpyxl import load_workbook


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def excel(path, frames):
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        for name, frame in frames.items():
            frame.to_excel(writer, sheet_name=name[:31], index=False)
    book = load_workbook(path)
    for sheet in book:
        sheet.freeze_panes = 'A2'
        sheet.auto_filter.ref = sheet.dimensions
        for col in sheet.columns:
            sheet.column_dimensions[col[0].column_letter].width = min(
                48, max(12, max(len(str(c.value or '')) for c in col[:80]) + 2))
    book.save(path)


def main():
    assert OUTPUT_DIR.resolve() != INPUT.parent.resolve()
    for part in ['process_data', 'figures/pdf', 'figures/png', 'figures/jpg']:
        (OUTPUT_DIR / part).mkdir(parents=True, exist_ok=True)
    source = pd.read_csv(INPUT, float_precision='round_trip')
    assert len(source) == 8625 and source.row_id.is_unique
    test = source.loc[source.split.eq('test')].copy().set_index('row_id', drop=False)
    assert len(test) == 1470 and test.structure_id.nunique() == 12
    assert np.isfinite(test.minimum_heavyatom_distance_A).all()
    assert np.array_equal(test.label.to_numpy(), (test.minimum_heavyatom_distance_A <= 5).astype(int).to_numpy())
    test['target_amino_acid'] = [r.target_sequence[int(r.residue_index) - 1] for r in test.itertuples()]
    for _, group in test.groupby('structure_id'):
        assert group.target_sequence.nunique() == group.observed_target.nunique() == 1
        seq, obs = group.target_sequence.iloc[0], group.observed_target.iloc[0]
        group = group.sort_values('residue_index')
        assert seq.count(obs) == 1 and len(group) == len(obs)
        positions = np.arange(seq.index(obs) + 1, seq.index(obs) + len(obs) + 1)
        assert np.array_equal(positions, group.residue_index.to_numpy())
        assert ''.join(group.target_amino_acid) == obs

    inventory = pd.DataFrame({'column': test.columns, 'dtype': test.dtypes.astype(str).values,
                              'missing': test.isna().sum().values, 'unique': test.nunique().values})
    health = ['# Contact-site gallery: input health', '',
        f'Test rows: {len(test)}; columns: {len(test.columns)}; memory: {test.memory_usage(deep=True).sum()} bytes.',
        f'Exact duplicate rows: {int(test.duplicated().sum())}; unique row IDs: {test.row_id.nunique()}.', '',
        inventory.to_string(index=False), '', test.select_dtypes('number').describe().to_string(), '',
        'All 12 test complexes are included in lexical structure-ID order. No example is selected by performance.',
        'Every displayed residue maps exactly once to the source target sequence; indices are 1-based source-sequence positions, not PDB residue numbers.',
        'Geometric labels equal minimum peptide-to-target heavy-atom distance <=5 Angstrom. Only observed target residues are labeled.',
        'No row is deleted or relabeled. Missing/unobserved parts of full target proteins are not negative labels.',
        'Normality, VIF, outlier deletion and hypothesis tests are inapplicable to a descriptive visualization of fixed predictions.',
        'Distance is checked only against reference labels and never passed to a prediction model.']
    (OUTPUT_DIR / '00_data_health.md').write_text('\n'.join(health), encoding='utf-8')
    excel(OUTPUT_DIR / 'process_data/01_test_rows_and_inventory.xlsx',
          {'test_rows': test.reset_index(drop=True), 'inventory': inventory})

    input_receipts = [{'path': str(INPUT), 'sha256': sha(INPUT)}]
    summary = test[['row_id', 'structure_id', 'pdb_id', 'target_id', 'residue_index',
                    'target_amino_acid', 'label', 'minimum_heavyatom_distance_A']].copy()
    for model in MODELS:
        probabilities, decisions = [], []
        for seed in SEEDS:
            directory = RUNS / model / f'seed-{seed:02d}'
            pfile, rfile = directory / 'test-predictions.csv', directory / 'result.json'
            pred = pd.read_csv(pfile, float_precision='round_trip').set_index('row_id', drop=False)
            result = json.loads(rfile.read_text(encoding='utf-8'))
            assert result['status'] == 'succeeded' and result['seed'] == seed and result['model'] == model
            assert result['input_sha256'] == input_receipts[0]['sha256']
            assert pred.index.is_unique and set(pred.index) == set(test.index)
            pred = pred.loc[test.index]
            for column in ['label', 'structure_id', 'residue_index', 'group_id', 'split']:
                assert np.array_equal(pred[column].to_numpy(), test[column].to_numpy()), (model, seed, column)
            prob = pred.prediction.to_numpy(float)
            threshold = float(result['threshold'])
            assert np.isfinite(prob).all() and ((prob >= 0) & (prob <= 1)).all()
            assert np.allclose(pred.threshold, threshold, atol=1e-15, rtol=0)
            assert np.array_equal((prob >= threshold).astype(int), pred.predicted_class.to_numpy())
            probabilities.append(prob)
            decisions.append(pred.predicted_class.to_numpy())
            input_receipts.extend({'path': str(path), 'sha256': sha(path)} for path in [pfile, rfile])
        summary[model + '_mean_probability'] = np.mean(probabilities, axis=0)
        summary[model + '_seed_sd'] = np.std(probabilities, axis=0, ddof=1)
        summary[model + '_positive_vote_fraction'] = np.mean(decisions, axis=0)

    summary.reset_index(drop=True).to_csv(OUTPUT_DIR / 'process_data/all-test-residue-predictions.csv', index=False)
    excel(OUTPUT_DIR / 'process_data/02_all_predictions.xlsx', {'predictions': summary.reset_index(drop=True)})
    available = {f.name for f in font_manager.fontManager.ttflist}
    selected_font = next((f for f in EN_SERIF_FALLBACK if f in available), 'DejaVu Serif')
    plt.rcParams.update({'font.family': 'serif', 'font.serif': [selected_font], 'font.size': 9,
                         'axes.spines.top': True, 'axes.spines.right': True, 'savefig.facecolor': 'white'})
    captions, index_rows = [], []
    with PdfPages(OUTPUT_DIR / 'report.pdf') as report:
        for figure_no, (structure, frame) in enumerate(summary.groupby('structure_id', sort=True), 1):
            frame = frame.sort_values('residue_index')
            original = test.loc[frame.index]
            blocks = [frame.iloc[start:start + WINDOW] for start in range(0, len(frame), WINDOW)]
            fig, axes = plt.subplots(len(blocks), 1, figsize=(11.2, 1.6 + 2.4 * len(blocks)), squeeze=False)
            fig.subplots_adjust(left=.145, right=.93, bottom=.9 / fig.get_figheight(),
                                top=1 - .7 / fig.get_figheight(), hspace=.65)
            last_image = None
            for ax, block in zip(axes[:, 0], blocks):
                matrix = np.full((6, WINDOW), np.nan)
                matrix[:, :len(block)] = np.vstack([block.label.to_numpy()] + [block[m + '_mean_probability'].to_numpy() for m in MODELS])
                color_map = plt.colormaps['cividis'].copy()
                color_map.set_bad('white')
                last_image = ax.imshow(matrix, aspect='auto', vmin=0, vmax=1, cmap=color_map, interpolation='nearest')
                ax.set_yticks(range(6), ['True contact'] + DISPLAY)
                ticks = np.unique(np.r_[np.arange(0, len(block), 10), len(block) - 1])
                if len(ticks) > 2 and ticks[-1] - ticks[-2] < 5:
                    ticks = np.delete(ticks, -2)
                ax.set_xticks(ticks, [f'{int(block.iloc[i].residue_index)}\n{block.iloc[i].target_amino_acid}' for i in ticks], fontsize=8)
                ax.set_xlabel('Source target-sequence position (1-based) and amino acid', fontsize=8)
                ax.set_yticks(np.arange(.5, 5.5, 1), minor=True)
                ax.grid(which='minor', axis='y', color='white', linewidth=.5)
                ax.tick_params(which='minor', left=False)
                for spine in ax.spines.values():
                    spine.set_visible(True)
                    spine.set_linewidth(.7)
            color_ax = fig.add_axes([.95, .29, .012, .4])
            cb = fig.colorbar(last_image, cax=color_ax, ticks=[0, .5, 1])
            cb.set_label('Reference label / mean model score', fontsize=8)
            pdb = frame.pdb_id.iloc[0]
            peptide = original.peptide_sequence.iloc[0]
            fig.text(.145, .98, f'{figure_no:02d}. PDB {pdb.upper()} | {structure} | target {frame.target_id.iloc[0]}',
                     ha='left', va='top', fontsize=11)
            fig.text(.145, .98 - .22 / fig.get_figheight(), f'Peptide: {peptide} | observed residues: {len(frame)} | contacts: {int(frame.label.sum())}',
                     ha='left', va='top', fontsize=9)
            caption = (f'Figure {figure_no}. All {len(frame)} observed target residues in held-out complex {structure}. '
                       'The first row is the experimental-structure geometric contact label (heavy-atom distance <=5 Angstrom); '
                       'other rows show arithmetic mean prediction scores from ten independently fitted seeds for each fixed baseline. '
                       'This displays agreement and errors along the chain without selecting a favorable example or introducing a new prediction threshold. '
                       'The mean is descriptive, not a newly trained or calibrated ensemble. Gray/blue low values indicate lower score; yellow high values indicate higher score.')
            captions.append(caption)
            fig.text(.145, .015, '\n'.join(textwrap.wrap(
                'All 12 held-out complexes are shown. Source-sequence positions are not PDB residue numbers. '
                'Labels describe geometric contacts, not functional hotspots. Mean scores are descriptive; per-seed scores and thresholds remain unchanged.',
                width=133)), fontsize=8, va='bottom', ha='left')
            slug = f'fig_{figure_no:02d}_{structure}'
            for fmt in OUTPUT_FORMATS:
                fig.savefig(OUTPUT_DIR / f'figures/{fmt}/{slug}.{fmt}', dpi=DPI, bbox_inches='tight')
            report.savefig(fig, bbox_inches='tight')
            plt.close(fig)
            excel(OUTPUT_DIR / f'process_data/fig_{figure_no:02d}_data.xlsx', {'figure': frame.reset_index(drop=True)})
            index_rows.append({'figure': figure_no, 'structure_id': structure, 'pdb_id': pdb,
                               'target_id': frame.target_id.iloc[0], 'observed_residues': len(frame),
                               'true_contacts': int(frame.label.sum()), 'peptide_sequence': peptide,
                               'image': f'figures/png/{slug}.png'})

    pd.DataFrame(index_rows).to_csv(OUTPUT_DIR / 'process_data/complex-index.csv', index=False)
    (OUTPUT_DIR / 'captions.md').write_text('\n\n'.join(captions), encoding='utf-8')
    explanation = '''# 留出测试复合物的结合位点预测

这里展示全部12个留出测试复合物，共1470个有实验结构坐标的靶标残基。打开 `report.pdf` 可逐页查看；`figures/png/` 有逐复合物图片。

第一行是真实几何接触标签：靶标残基与肽的最小重原子距离不超过5 Å记为接触。后五行分别是先验、线性、随机森林、极端随机树和直方图梯度提升基准的预测分数，取同一模型10个训练种子的算术均值。所有测试复合物按名称顺序展示，未依据结果挑选。

横轴是本数据表中完整靶标序列的1起始位置和氨基酸，不是PDB编号。只展示有结构坐标且可唯一映射的残基；其余位置不填作负例。这些标签反映结构中的空间接触，不能直接解释为功能热点、亲和力变化或新对接实验验证。

均值图用于查看模型是否把高分放在真实接触附近。它没有新增训练、推理、调参或测试集阈值选择，也不作为新增集成模型成绩。原始逐种子概率、各自验证集选定的阈值与分类结果完整保留。侧表另提供分数的种子间样本标准差，以及各模型10个种子中判为接触的比例；这些描述不等同于生物学置信区间。

`process_data/all-test-residue-predictions.csv` 可逐残基查分；每张图都有同名工作簿。`00_data_health.md` 记录行号、标签、序列映射与缺失检查。`gallery-receipt.json` 记录所有输入与输出的SHA256。
'''
    (OUTPUT_DIR / 'README.zh-CN.md').write_text(explanation, encoding='utf-8')
    outputs = [{'path': str(p.relative_to(OUTPUT_DIR)), 'bytes': p.stat().st_size, 'sha256': sha(p)}
               for p in sorted(OUTPUT_DIR.rglob('*')) if p.is_file() and p.name != 'gallery-receipt.json']
    write_json(OUTPUT_DIR / 'gallery-receipt.json', {'created_at': datetime.now(timezone.utc).isoformat(),
        'status': 'generated_pending_visual_review', 'test_complexes': len(index_rows), 'test_residues': len(test),
        'models': MODELS, 'seeds': list(SEEDS), 'new_fit_count': 0, 'new_model_forward_count': 0,
        'reference_geometry_used_as_model_input': False, 'all_test_complexes_included': True,
        'input_files': input_receipts, 'script_sha256': sha(Path(__file__)), 'outputs': outputs})
    print(json.dumps({'complexes': len(index_rows), 'residues': len(test), 'outputs': len(outputs),
                      'output_dir': str(OUTPUT_DIR)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
