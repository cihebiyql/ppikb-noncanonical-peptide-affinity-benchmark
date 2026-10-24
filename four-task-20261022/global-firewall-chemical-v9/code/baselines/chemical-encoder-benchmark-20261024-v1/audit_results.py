"""Recalculate saved head metrics and validation selection without loading estimators."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def recalculate(y, p, effect=False):
    y, p = np.asarray(y, np.float64), np.asarray(p, np.float64)
    n = len(y)
    residual = p - y
    varying = n > 1 and np.ptp(y) > 0 and np.ptp(p) > 0
    def corr(left, right):
        left, right = left - left.mean(), right - right.mean()
        return float(np.dot(left, right) / np.sqrt(np.dot(left, left) * np.dot(right, right)))
    denominator = np.dot(y-y.mean(), y-y.mean())
    result = {'n': n, 'mae': float(np.abs(residual).sum()/n),
            'rmse': float(np.sqrt(np.dot(residual, residual)/n)), 'bias': float(residual.sum()/n),
            'r2': float(1-np.dot(residual,residual)/denominator) if denominator > 0 else None,
            'pearson': corr(y,p) if varying else None,
            'spearman': corr(rankdata(y),rankdata(p)) if varying else None}
    if effect:
        nonzero = y != 0
        result['nonzero_effect_n'] = int(nonzero.sum())
        result['direction_accuracy_nonzero'] = float(np.mean(np.sign(y[nonzero]) == np.sign(p[nonzero]))) if nonzero.any() else None
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--require-ten-seeds', action='store_true')
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    errors, checks, groups = [], 0, {}
    expected_units, actual_units, contract_sha_by_view = set(), set(), {}
    def check(test, why):
        nonlocal checks
        checks += 1
        if not test:
            errors.append(why)
    def same(a,b):
        if a is None or b is None:
            return a is b
        return math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-10)
    for contract_path in sorted(args.output.glob('*/frozen-head-contract.json')):
        contract = read(contract_path)
        view_id, contract_sha = contract['view_id'], sha(contract_path)
        if view_id in contract_sha_by_view:
            check(contract_sha_by_view[view_id] == contract_sha, f'Conflicting contracts for {view_id}')
        contract_sha_by_view[view_id] = contract_sha
        declared_seeds = set(contract['seeds'])
        if args.require_ten_seeds:
            check(declared_seeds == set(range(10)), f'Contract does not declare ten seeds for {view_id}')
        seeds = set(range(10)) if args.require_ten_seeds else declared_seeds
        expected_units.update((view_id, name, seed) for name in contract['models'] for seed in seeds)
    for result_path in sorted(args.output.glob('*/*/seed-*/result.json')):
        result = read(result_path)
        unit = (result['view_id'], result['model'], result['seed'])
        check(unit not in actual_units, f'Duplicate model-seed result {unit}')
        actual_units.add(unit)
        check(result.get('status') == 'succeeded', f'Unsuccessful {result_path}')
        contract_path = result_path.parents[2]/'frozen-head-contract.json'
        check(sha(contract_path) == result['contract_sha256'], f'Contract SHA {result_path}')
        contract = read(contract_path)
        check(contract_sha_by_view.get(result['view_id']) == result['contract_sha256'], f'Result references conflicting contract {unit}')
        manifest_path = Path(contract['global_manifest_path'])
        check(sha(manifest_path) == contract['global_manifest_sha256'], f'Global freeze SHA {result_path}')
        check(sha(contract['input_path']) == contract['input_sha256'], f'Input SHA {result_path}')
        source = pd.read_csv(contract['input_path'],keep_default_na=False,float_precision='round_trip').set_index('row_id')
        check(source.index.is_unique,f'Frozen source IDs must be unique {result_path}')
        binding = contract['column_binding']
        expected_split = source[binding['split']].replace({'fine_train':'train','finetune_train':'train','val':'validation','valid':'validation','external_test':'external'})
        effect = result['task'] == 'effect'
        candidates = []
        for candidate in result['candidates']:
            check(sha(candidate['model_path']) == candidate['model_sha256'],f'Checkpoint SHA {result_path}')
            check(sha(candidate['validation_path']) == candidate['validation_sha256'],f'Validation prediction SHA {result_path}')
            frame = pd.read_csv(candidate['validation_path'],keep_default_na=False,float_precision='round_trip')
            check(not frame.row_id.duplicated().any(),f'Duplicate VAL IDs {result_path}')
            check(set(frame.row_id) == set(source.index[expected_split=='validation']),f'Complete frozen VAL ID set {result_path}')
            check(np.array_equal(frame.label.to_numpy(float),source.loc[frame.row_id,binding['label']].to_numpy(float)),f'Original VAL labels {result_path}')
            mm = recalculate(frame.label.to_numpy(float),frame.prediction.to_numpy(float),effect)
            for key,value in mm.items():
                check(same(value,candidate['validation_metrics'].get(key)),f'Candidate VAL {key} {result_path}')
            candidates.append((mm['mae'],candidate['candidate']))
            if result['model'] == 'ridge':
                check(candidate.get('scaler_audit',{}).get('mean_matches_training') is True,f'Ridge train-only scaler {result_path}')
        winner = min(candidates)[1]
        check(winner == result['selected_candidate'],f'Validation-only selection {result_path}')
        selection = read(result_path.parent/'selection.json')
        check(selection['selected_candidate'] == winner and selection['test_used_for_selection'] is False and selection['external_used_for_selection'] is False,
              f'Selection freeze {result_path}')
        for split,item in result['splits'].items():
            check(sha(item['prediction_path']) == item['prediction_sha256'],f'Selected prediction SHA {result_path}')
            frame = pd.read_csv(item['prediction_path'],keep_default_na=False,float_precision='round_trip')
            check(not frame.row_id.duplicated().any(),f'Duplicate {split} IDs {result_path}')
            check(set(frame.row_id) == set(source.index[expected_split==split]),f'Complete frozen {split} ID set {result_path}')
            check(np.array_equal(frame.label.to_numpy(float),source.loc[frame.row_id,binding['label']].to_numpy(float)),f'Original {split} labels {result_path}')
            for key,value in recalculate(frame.label.to_numpy(float),frame.prediction.to_numpy(float),effect).items():
                check(same(value,item['metrics'].get(key)),f'{split} metric {key} {result_path}')
            for stratum in item['subgroups']:
                sub = frame[frame[stratum['column']].astype(str)==stratum['value']]
                for key,value in recalculate(sub.label.to_numpy(float),sub.prediction.to_numpy(float),effect).items():
                    check(same(value,stratum.get(key)),f'{split} stratum {stratum["value"]} {key} {result_path}')
            group_values = []
            for group in item['group_metrics']:
                sub = frame[frame.group_id.astype(str) == group['group_id']]
                mm = recalculate(sub.label.to_numpy(float),sub.prediction.to_numpy(float),effect)
                group_values.append(mm)
                for key,value in mm.items():
                    check(same(value,group.get(key)),f'{split} group {group["group_id"]} {key} {result_path}')
            for key,value in item['group_macro_metrics'].items():
                valid = [mm[key] for mm in group_values if mm.get(key) is not None]
                check(value['valid_groups']==len(valid) and value['all_groups']==len(group_values),f'{split} macro group counts {key} {result_path}')
                check(same(value['mean'],float(np.mean(valid)) if valid else None),f'{split} macro mean {key} {result_path}')
        key = result['view_id']+'|'+result['model']
        groups.setdefault(key,set()).add(result['seed'])
    check(bool(groups),'No completed saved model runs')
    missing_units = sorted(expected_units - actual_units)
    extra_units = sorted(actual_units - expected_units)
    check(not missing_units, f'Missing declared model-seed units: {missing_units}')
    check(not extra_units, f'Unexpected model-seed units: {extra_units}')
    if args.require_ten_seeds:
        for key,seeds in groups.items():
            check(seeds==set(range(10)),f'Incomplete seeds {key}: {sorted(seeds)}')
    receipt = {'schema':'chemical-head.saved-result-audit.v1','valid':not errors,'checks':checks,
               'errors':errors,'seeds_by_combination':{k:sorted(v) for k,v in groups.items()},
               'expected_model_seed_units':len(expected_units),'actual_model_seed_units':len(actual_units),
               'missing_units':missing_units,'extra_units':extra_units,
               'loaded_estimators':0,'new_fits':0,'new_encoder_inference':0}
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    args.receipt.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False))
    return 0 if not errors else 1


if __name__=='__main__':
    raise SystemExit(main())
