"""Plot completed ten-seed traditional baselines without retraining/selection."""
# CONFIGURATION -- frozen completed inputs, separate output, SD across fit seeds.
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
INPUT_FILES = [ROOT / 'runs/cpu-v2/mean-sd-metrics.csv',
               ROOT / 'runs/cpu-molecular-v1/mean-sd-metrics.csv',
               ROOT / 'runs/cpu-effect-v1/mean-sd-metrics.csv',
               ROOT / 'runs/cpu-contact64-v1/mean-sd-metrics.csv',
               ROOT / 'runs/cpu-contact64-v1/macro-mean-sd-by-unit.csv',
               ROOT / 'runs/cpu-v2/subgroup-mean-sd-metrics.csv',
               ROOT / 'runs/cpu-molecular-v1/subgroup-mean-sd-metrics.csv',
               ROOT / 'runs/cpu-additional-v1/mean-sd-metrics.csv']
OUTPUT_DIR = ROOT / 'reports/figures-v1'
PROJECT_TITLE = 'Completed traditional baselines: frozen ten-seed results'
EN_SERIF_FALLBACK = ['Times New Roman', 'Liberation Serif', 'DejaVu Serif', 'serif']
CN_SERIF_FALLBACK = ['SimSun', 'Noto Serif CJK SC', 'serif']
OUTPUT_FORMATS = ['pdf', 'png', 'jpg']
DPI = 300
ERROR_BAR = 'SD'
ALPHA = None  # No inferential test on ten reused-test-set fitting seeds.
DEFAULT_DECIMALS = 3

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
from matplotlib.ticker import FormatStrFormatter
from openpyxl import load_workbook

MODELS = ['constant', 'linear', 'random_forest', 'extra_trees', 'hist_gradient_boosting']
MODEL_LABELS = ['Prior', 'Linear', 'Random forest', 'Extra trees', 'Histogram GB']

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def font(candidates):
    known = {f.name for f in font_manager.fontManager.ttflist}
    return next((x for x in candidates if x in known), 'DejaVu Serif')

def excel(path, frames):
    with pd.ExcelWriter(path, engine='openpyxl') as w:
        for name, frame in frames.items():
            frame.to_excel(w, sheet_name=name[:31], index=False)
    book = load_workbook(path)
    for sheet in book:
        sheet.freeze_panes = 'A2'
        sheet.auto_filter.ref = sheet.dimensions
        for col in sheet.columns:
            sheet.column_dimensions[col[0].column_letter].width = min(44, max(12, max(len(str(c.value or '')) for c in col[:80]) + 2))
    book.save(path)

def point_panel(ax, frame, ylabel):
    for i, (rep, marker, color, offset) in enumerate([
        ('Sequence', 'o', 'black', -0.10), ('Chiral Morgan', 's', '0.55', 0.10)]):
        f = frame[frame['representation'] == rep].set_index('model').loc[MODELS]
        ax.errorbar(np.arange(5) + offset, f['mean'], yerr=f['sd'], fmt=marker,
                    ms=4.5, capsize=3, lw=1, color=color, label=rep)
    ax.set_xticks(np.arange(5), MODEL_LABELS, rotation=25, ha='right')
    ax.set_ylabel(ylabel)
    ax.yaxis.set_major_formatter(FormatStrFormatter('%.2f'))
    ax.grid(axis='y', color='0.9', linewidth=.6)
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(.8)

def main():
    assert all(OUTPUT_DIR.resolve() != p.parent.resolve() for p in INPUT_FILES)
    for part in ['process_data', 'figures/pdf', 'figures/png', 'figures/jpg']:
        (OUTPUT_DIR / part).mkdir(parents=True, exist_ok=True)
    frames = [pd.read_csv(p, float_precision='round_trip') for p in INPUT_FILES]
    raw = pd.concat([f.assign(source_file=str(p.relative_to(ROOT))) for p, f in zip(INPUT_FILES, frames)], ignore_index=True)
    inventory = pd.DataFrame({'column': raw.columns, 'dtype': raw.dtypes.astype(str).values,
                              'missing': raw.isna().sum().values, 'unique': raw.nunique().values})
    health = ['# Completed-result table health', '',
        f'Loaded rows={len(raw)}, columns={len(raw.columns)}, memory={raw.memory_usage(deep=True).sum()} bytes.',
        f'Exact duplicate rows with source identity retained: {int(raw.duplicated().sum())}.', '',
        inventory.to_string(index=False), '', raw.select_dtypes('number').describe().to_string(), '',
        'Undefined correlation cells in constant models are expected and preserved. All plotting rows must have finite mean/SD, nonnegative SD and ten valid seeds.',
        'No rows are removed because their performance is poor. No dataset or training split is changed.',
        'Normality, VIF, pooled correlation and outlier deletion are inapplicable: these are heterogeneous aggregate outcomes, not independent observations or predictor columns.',
        'No p-values or biological-confidence intervals are computed from fitting seeds. Error bars are sample SD across ten fits on one frozen test set.']
    (OUTPUT_DIR / '00_data_health.md').write_text('\n'.join(health), encoding='utf-8')
    excel(OUTPUT_DIR / 'process_data/01_loaded_and_inventory.xlsx', {'loaded': raw, 'inventory': inventory})
    plt.rcParams.update({'font.family': 'serif', 'font.serif': [font(EN_SERIF_FALLBACK), font(CN_SERIF_FALLBACK)],
        'font.size': 9, 'axes.labelsize': 10, 'xtick.labelsize': 8, 'ytick.labelsize': 9,
        'legend.fontsize': 9, 'legend.frameon': False, 'axes.unicode_minus': False, 'axes.spines.top': True,
        'axes.spines.right': True, 'savefig.dpi': DPI, 'pdf.fonttype': 42})
    fig_records, plotting_tables = [], {}
    plans = [('01_source_cold', 'ppikb_kd_source_cold_scope_v2', 'mae', frames[0], frames[1],
              'Test MAE (pKd units)', 'Source/peptide dependency holdout; n=1,014 measurements.'),
             ('02_target_cold', 'ppikb_kd_target_cold_scope_v2', 'mae', frames[0], frames[1],
              'Test MAE (pKd units)', 'Reference-target homology holdout; n=1,383 measurements.'),
             ('03_effect_silver', 'ppikb_effect_metadata_silver_source_cold', 'mae', frames[2], frames[1],
              'Test MAE (delta pKd units)', 'Metadata-matched effect diagnostic; n=129 dependent pairs, not certified same-condition gold.')]
    with PdfPages(OUTPUT_DIR / 'report.pdf') as report:
        for name, view, metric, seq, mol, ylabel, context in plans:
            table = pd.concat([f[(f['view_id'] == view) & (f['split'] == 'test') & (f['metric'] == metric)].assign(representation=r)
                               for f, r in [(seq, 'Sequence'), (mol, 'Chiral Morgan')]], ignore_index=True)
            validate_table(table, expected=10)
            fig, ax = plt.subplots(figsize=(7.2, 4.6))
            point_panel(ax, table, ylabel)
            ax.legend(loc='best')
            fig.subplots_adjust(left=.12, right=.97, bottom=.32, top=.96)
            caption = f'{context} Points show all five predeclared traditional model families, mean +/- sample SD across seeds 0-9; preprocessing and selection used train/validation only. Chemical features do not consistently improve every holdout, so results are retained for all models without test-based reselection.'
            fig.text(.06, .025, textwrap.fill(caption, 112), fontsize=8, va='bottom')
            save_figure(fig, name, report, table, caption, fig_records, plotting_tables)
        micro = frames[3]
        macro = frames[4]
        a = micro[(micro['split'] == 'test') & (micro['metric'] == 'auprc')].assign(representation='Residue micro', denominator=1470)
        b = macro[(macro['split'] == 'test') & (macro['metric'] == 'auprc') & (macro['averaging_unit'] == 'structure_id')].assign(representation='Complex macro', denominator=12)
        table = pd.concat([a, b], ignore_index=True)
        validate_table(table, expected=10)
        fig, ax = plt.subplots(figsize=(7.2, 4.6))
        for rep, off, marker, color in [('Residue micro', -.10, 'o', 'black'), ('Complex macro', .10, 's', '0.55')]:
            f = table[table['representation'] == rep].set_index('model').loc[MODELS]
            ax.errorbar(np.arange(5) + off, f['mean'], yerr=f['sd'], fmt=marker, color=color, capsize=3, ms=4.5, label=rep)
        ax.set_xticks(np.arange(5), MODEL_LABELS, rotation=25, ha='right')
        ax.set_ylabel('Contact prediction AUPRC')
        ax.yaxis.set_major_formatter(FormatStrFormatter('%.2f'))
        ax.grid(axis='y', color='0.9', linewidth=.6)
        ax.legend(loc='best')
        fig.subplots_adjust(left=.12, right=.97, bottom=.32, top=.96)
        caption = 'Experimental-contact holdout from 64 linked complexes: test n=12 complexes and 1,470 observed residues. Sequence-only baselines use no true coordinates as features; points are ten-seed mean +/- SD. Micro and equal-complex macro AUPRC have different weighting and reference prevalence; geometric contacts are not functional-site validation.'
        fig.text(.06, .025, textwrap.fill(caption, 112), fontsize=8, va='bottom')
        save_figure(fig, '04_contact64', report, table, caption, fig_records, plotting_tables)
        strata = ['standard20_control', 'synthetic_D_backbone', 'PTM', 'synthetic_and_PTM', 'other_NC']
        names = ['Standard residues', 'Synthetic / D / backbone', 'PTM', 'Mixed', 'Other nonstandard']
        table = pd.concat([f[(f['view_id'] == 'ppikb_kd_source_cold_scope_v2') & (f['split'] == 'test') &
                              (f['metric'] == 'mae') & (f['subgroup_column'] == 'evaluation_stratum')].assign(representation=r)
                           for f, r in [(frames[5], 'Sequence'), (frames[6], 'Chiral Morgan')]], ignore_index=True)
        validate_table(table, expected=50)
        fig, axes = plt.subplots(2, 3, figsize=(10.5, 7.7))
        for ax, subgroup, name in zip(axes.flat, strata, names):
            local = table[table['subgroup'] == subgroup]
            point_panel(ax, local, 'MAE (pKd units)')
            n = int(local['n'].iloc[0])
            ax.text(.02, 1.03, f'{name}; n={n}', transform=ax.transAxes, fontsize=9)
        axes.flat[-1].set_visible(False)
        handles, labels = axes.flat[0].get_legend_handles_labels()
        fig.legend(handles, labels, loc='lower right', bbox_to_anchor=(.96, .18))
        fig.subplots_adjust(left=.08, right=.97, bottom=.17, top=.95, hspace=.70, wspace=.40)
        caption = 'Mutually exclusive residue-annotation strata in the source/peptide holdout. All five model families and both representations are shown with ten-seed mean +/- SD; denominators vary by stratum. Chemical-label discordance remains flagged in the main data, and these descriptive panels do not establish statistical significance or broad nonstandard-residue transfer.'
        fig.text(.04, .025, textwrap.fill(caption, 156), fontsize=8, va='bottom')
        save_figure(fig, '05_residue_strata', report, table, caption, fig_records, plotting_tables)
        table = frames[7][(frames[7]['view_id'] == 'pepinter_classification_target_cold') &
                          (frames[7]['split'] == 'test') & frames[7]['metric'].isin(['auprc', 'auroc'])].copy()
        validate_table(table, expected=10)
        fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.6))
        for ax, metric, label in zip(axes, ['auprc', 'auroc'], ['AUPRC', 'AUROC']):
            local = table[table['metric'] == metric].set_index('model').loc[MODELS]
            ax.errorbar(np.arange(5), local['mean'], yerr=local['sd'], fmt='o', color='black', capsize=3, ms=4.5)
            reference = float(local.loc['constant', 'mean'])
            ax.axhline(reference, color='0.6', linestyle='--', linewidth=.8)
            ax.set_xticks(np.arange(5), MODEL_LABELS, rotation=25, ha='right')
            ax.set_ylabel(label)
            ax.yaxis.set_major_formatter(FormatStrFormatter('%.2f'))
            ax.grid(axis='y', color='0.9', linewidth=.6)
            ax.set_ylim(0, 1)
        fig.subplots_adjust(left=.08, right=.97, bottom=.32, top=.96, wspace=.32)
        caption = 'Interaction classification on the full declared PepInter test view, n=2,577 examples. Points are ten-seed mean +/- SD for the five sequence-descriptor baselines; dashed lines show the constant-score AUPRC prevalence or AUROC reference. Author-constructed negatives define this task, and these full-view denominators differ from vocabulary-restricted SWING evaluation.'
        fig.text(.04, .025, textwrap.fill(caption, 156), fontsize=8, va='bottom')
        save_figure(fig, '06_interaction_classification', report, table, caption, fig_records, plotting_tables)
    excel(OUTPUT_DIR / 'process_data/99_all_plot_values.xlsx', plotting_tables)
    receipt = dict(at=datetime.now(timezone.utc).isoformat(), report_format='figure PDF with captions; reportlab unavailable, no dependency installed',
        inputs=[dict(path=str(p), sha256=sha(p)) for p in INPUT_FILES], figures=fig_records,
        error_bars=ERROR_BAR, significance_tests_performed=False, fits_or_predictions_added=0,
        fonts=[font(EN_SERIF_FALLBACK), font(CN_SERIF_FALLBACK)])
    (OUTPUT_DIR / 'figure-receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTPUT_DIR / 'captions.md').write_text('\n\n'.join(f"**{f['id']}** {f['caption']}" for f in fig_records), encoding='utf-8')
    print(json.dumps({'figures': len(fig_records), 'plot_rows': sum(x['rows'] for x in fig_records), 'output': str(OUTPUT_DIR)}))

def validate_table(frame, expected):
    if len(frame) != expected or not np.isfinite(frame[['mean', 'sd']].to_numpy()).all():
        raise ValueError('Incomplete or nonfinite plotted data')
    if (frame['sd'] < 0).any() or (frame['valid_seed_count'] != 10).any() or (frame['seed_count'] != 10).any():
        raise ValueError('Plot requires all ten fitting seeds and nonnegative SD')

def save_figure(fig, name, report, table, caption, records, tables):
    for suffix in OUTPUT_FORMATS:
        fig.savefig(OUTPUT_DIR / f'figures/{suffix}/fig_{name}.{suffix}', dpi=DPI)
    report.savefig(fig)
    excel(OUTPUT_DIR / f'process_data/fig_{name}_data.xlsx', {'plot_data': table})
    tables[name[:31]] = table
    records.append(dict(id=name, rows=len(table), caption=caption,
                        files=[dict(path=f'figures/{s}/fig_{name}.{s}', sha256=sha(OUTPUT_DIR / f'figures/{s}/fig_{name}.{s}')) for s in OUTPUT_FORMATS]))
    plt.close(fig)

if __name__ == '__main__':
    main()
