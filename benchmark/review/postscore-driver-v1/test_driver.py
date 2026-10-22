"""Synthetic metadata-only driver tests; no real issuance/results are opened."""
import copy
import importlib.util
import itertools
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('synthetic_postscore_driver', HERE / 'driver.py')
d = importlib.util.module_from_spec(spec); spec.loader.exec_module(d)
cases = []


def check(name, value):
    if not value: raise AssertionError(name)
    cases.append({'case': name, 'passed': True})


def reject(name, callback, error=ValueError):
    try: callback()
    except error: check(name, True)
    else: raise AssertionError('Expected rejection: ' + name)


def fixture():
    data = {}; pools = {}; proofs = {}
    def put(name, body):
        data[name] = body; return {'path': name, 'sha256': 'SYNTHETIC_SHA_' + name}
    for family, methods in (('NN', d.NN_METHODS), ('RF', (d.RF_METHOD,))):
        units = []
        pool_ref = {'path': 'SYNTHETIC_POOL_' + family, 'sha256': 'SYNTHETIC_SHA_SYNTHETIC_POOL_' + family}
        for method, panel, regime, seed in itertools.product(methods, d.PANELS, d.REGIMES, range(10)):
            uid = '_'.join((family, method, panel, regime, str(seed)))
            root = 'SYNTHETIC_RECEIPTS/' + uid
            datasets = []; scores = []; specs = []
            for role, raw in (('internal', 'source_test' if panel == d.PANELS[0] else 'target_test'), ('external75', 'external75'), ('supplement13', 'supplement13')):
                sr = put('SYNTHETIC_SPEC_' + '_'.join((family, method, panel, raw)), {'dataset_id': raw})
                datasets.append(dict(role=role, dataset_id=raw, n=d.RAW_N[raw], score_spec=sr)); specs.append(sr)
                produced = dict(status='complete', method_id=method, regime=regime, seed=seed, n=d.RAW_N[raw], holdout_id=raw,
                    score_spec_sha256=sr['sha256'], selection_sha256='SYNTHETIC_SELECTION_' + uid,
                    stage='post-selection-score-only' if family == 'NN' else 'additional_classical_RF_post_joint_barrier_score')
                produced['split_id' if family == 'NN' else 'panel'] = panel
                cr = put('SYNTHETIC_SCORE/' + uid + '/' + raw + '/complete.json', produced)
                scores.append(dict(role=role, dataset_id=raw, n=d.RAW_N[raw], complete_path=cr['path'], complete_sha256=cr['sha256']))
            contract = put('SYNTHETIC_CONTRACT_' + uid, dict(run_id=uid, benchmark_metadata=dict(method_id='RF-Classic' if family == 'RF' else method, split_id=panel, regime_id=regime, seed=seed), evaluation_stage={'datasets': datasets}))
            binding = put('SYNTHETIC_BINDING_' + uid, dict(unit_id=uid, central_contract=contract, receipt_root=root, score_specs=specs, selection={'sha256': 'SYNTHETIC_SELECTION_' + uid}))
            unit_path = str(d.path(root) / 'unit-complete.json')
            exit_path = str(d.path(root) / 'pool-exit-verification.json')
            data[unit_path] = dict(status='complete', unit_id=uid, binding_sha256=binding['sha256'], contract_sha256=contract['sha256'], pid=100, scores=scores)
            data[exit_path] = dict(unit_id=uid, binding_sha256=binding['sha256'], index_sha256=pool_ref['sha256'], exit_code=0, private_session_handles_absent=True, pid=100)
            units.append(dict(unit_id=uid, binding=binding))
        data[pool_ref['path']] = {'issued': True, 'units': units}; pools[family] = pool_ref
        proofs[family] = put('SYNTHETIC_TOP_EXIT_' + family, dict(exit_code=0, private_session_handles_absent=True, pool_index_sha256=pool_ref['sha256'], observed_at='SYNTHETIC_TIME', session_id='SYNTHETIC_SESSION'))
    issuance = dict(schema='postjoint-240-stage-issuance.v1', stage_contracts={'NN': 200, 'RF': 40}, pools=pools)
    return issuance, proofs, data


issuance, proofs, data = fixture()
def call(mapping):
    with patch.object(d, 'bound', lambda r: mapping[r['path']]), patch.object(d, 'read', lambda p: mapping[str(p)]):
        return d.mapper(issuance, proofs)
maps, internal, reference_inputs = call(data)
check('strict_600NN_120RF_receipt_maps', len(maps['NN']) == 600 and len(maps['RF']) == 120)
check('strict240_existing_internal_inputs', len(internal) == 240)
check('exact_six_reference_specs_not_random_seed_choice', len(reference_inputs) == 6 and {(x['split_id'], x['dataset_id']) for x in reference_inputs} == set(itertools.product(d.PANELS, ('PPIKB-internal', 'PTM-external75', 'IgG-supplement13'))))
check('RF_administrative_alias_maps_only_to_RF_method', all(x['produced']['method_id'] == d.RF_METHOD for x in internal if x['family'] == 'RF'))
bad = copy.deepcopy(data); bad[proofs['NN']['path']]['exit_code'] = 1
reject('nonzero_top_pool_exit_rejected', lambda: call(bad))
bad = copy.deepcopy(data); bad[proofs['RF']['path']]['private_session_handles_absent'] = False
reject('live_pool_session_rejected', lambda: call(bad))
bad = copy.deepcopy(data); bad[proofs['RF']['path']]['pool_index_sha256'] = 'OTHER'
reject('top_exit_for_other_pool_rejected', lambda: call(bad))
bad = copy.deepcopy(data); bad['SYNTHETIC_POOL_NN']['units'].pop()
reject('199_NN_issued_units_rejected', lambda: call(bad))
bad = copy.deepcopy(data); score_name = next(k for k in bad if k.startswith('SYNTHETIC_SCORE/NN'))
bad[score_name]['regime'] = 'OTHER'
reject('producer_coordinate_mismatch_rejected', lambda: call(bad))
bad = copy.deepcopy(data); exit_name = next(k for k in bad if k.endswith('pool-exit-verification.json'))
bad[exit_name]['pid'] = 999
reject('unit_exit_PID_mismatch_rejected', lambda: call(bad))
bad = copy.deepcopy(data); unit_name = next(k for k in bad if k.endswith('unit-complete.json'))
bad[unit_name]['scores'].pop()
reject('only_two_datasets_rejected', lambda: call(bad))
bad = copy.deepcopy(data); bad[score_name]['n'] += 1
reject('producer_row_count_mismatch_rejected', lambda: call(bad))
with tempfile.TemporaryDirectory(prefix='synthetic_postscore_sha_') as folder:
    file = Path(folder) / 'synthetic.json'; file.write_text(json.dumps({'synthetic': True}))
    r = d.ref(file); check('metadata_SHA_binding_positive', d.bound(r) == {'synthetic': True})
    file.write_text('{}'); reject('changed_metadata_SHA_rejected', lambda: d.bound(r))
reads = []
with patch.object(d, 'read', lambda x: reads.append(x)), patch.object(sys, 'argv', ['driver.py', '--inputs', 'NO_READ']):
    reject('CLI_explicit_flag_required_before_input_read', d.main, PermissionError)
check('unauthorized_CLI_read_count_zero', not reads)
reject('document_true_alone_insufficient', lambda: d.guard({'root_postscore_audit_authorized': True}, False), PermissionError)
reject('flag_true_document_false_rejected', lambda: d.guard({'root_postscore_audit_authorized': False}, True), PermissionError)
if sys.platform == 'win32':
    with patch.object(d.time, 'time', lambda: d.DEADLINE - 100):
        reject('global_cutoff_cannot_extend', lambda: d.guard({'root_postscore_audit_authorized': True, 'deadline_unix': d.DEADLINE + 1}, True), TimeoutError)
        reject('expired_cutoff_stops_before_issuance', lambda: d.guard({'root_postscore_audit_authorized': True, 'deadline_unix': d.DEADLINE - 200}, True), TimeoutError)
    check('Windows_WSL_path_roundtrip', d.wsl(d.path('/mnt/d/work/example.json')) == '/mnt/d/work/example.json')
check('no_metric_implementation_or_monkeypatch', 'def metrics(' not in (HERE / 'driver.py').read_text() and 'local_path =' not in (HERE / 'driver.py').read_text())
report = dict(schema='postscore-driver-v1-synthetic-verification', status='passed', passed_cases=len(cases), cases=cases,
    driver_sha256=d.sha(HERE / 'driver.py'), environment=dict(python=sys.executable, platform=sys.platform), actual_pipeline_runs=0,
    actual_issuance_joint_selections_gold_predictions_weights_labels_matrices_read=False,
    synthetic_scope='Mocked complete issued240-unit/720-receipt metadata mapping plus generic temporary JSON SHA checks; no real pipeline execution.')
(HERE / 'synthetic-verification.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'status': report['status'], 'passed_cases': len(cases)}))
