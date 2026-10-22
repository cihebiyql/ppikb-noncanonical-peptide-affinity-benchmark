"""Independent frozen-scorer source + pure synthetic review, no model/real data."""
import ast,math,json
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import recompute_metrics as audit

R=Path(__file__).resolve().parent;P=R.parent;E=P/'evaluation'

def isolate(path,names,namespace):
 tree=ast.parse(path.read_text(encoding='utf-8'));functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
 assert {n.name for n in functions}==set(names)
 exec(compile(ast.Module(body=functions,type_ignores=[]),'isolated_synthetic_source_review','exec'),namespace)
 return namespace,tree

def main():
 frozen=audit.read_json(E/'FROZEN-SCORER-v1.json')
 for name,digest in frozen['evaluation_code_sha256'].items():audit.require_hash(E/name,digest)
 audit.require_hash(P/'execution/runner.py',frozen['frozen_runner_sha256'])
 pure,_=isolate(E/'metrics_stable.py',['_finite','_unit_centered','numeric_metrics','grouped_metrics'],{'np':np,'rankdata':audit.average_ranks})
 cases=[([],[]),([.1],[.2]),([.1]*3,[.2,.3,.4]),([1,2,3],[.1]*3),([.1]*3,[.1]*3),([1,2,3],[1,3,2]),([1,1,2],[2,2,3]),([1,2,3],[3,2,1])]
 near=np.array([.1,np.nextafter(.1,1.)]);cases.extend([(near,near),(near,near[::-1])])
 rng=np.random.default_rng(712)
 for n in [2,3,17,100]:
  for _ in range(8):
   y=rng.normal(size=n)+5;p=y+rng.normal(size=n);cases.append((y,p))
 maxdiff={key:0. for key in audit.METRICS}
 for y,p in cases:
  expected=audit.metrics(y,p);actual=pure['numeric_metrics'](y,p)
  assert expected['n']==actual['n']
  for key in audit.METRICS:
   a,b=expected[key],actual[key]
   if a is None:assert b is None,(key,a,b)
   else:
    assert b is not None and math.isfinite(b)
    assert math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-10),(key,a,b)
    maxdiff[key]=max(maxdiff[key],abs(a-b))
  json.dumps(actual,allow_nan=False)
 # Gate functions run against in-memory metadata strings only, never actual
 # selection/checkpoint/prediction/gold files.
 docs={};reads=[];hashes=[];sha_map={}
 def read(path):reads.append(str(path));return docs[str(path)]
 def sha(path):hashes.append(str(path));return sha_map[str(path)]
 common=SimpleNamespace(read_json=read,sha=sha)
 ns={'common':common,'Path':Path,'code_hashes':lambda:frozen['evaluation_code_sha256']}
 ns,tree=isolate(E/'score_cached.py',['authorize','validate_gate','_join_gold_after_blind'],ns)
 docs['auth']={'root_scoring_authorized':False}
 try:ns['validate_gate']('auth','barrier','barrier-audit','selection','score-spec');raise AssertionError('Unauthorized access allowed')
 except PermissionError:pass
 assert reads==['auth'] and not hashes
 docs['auth']={'root_scoring_authorized':True,'allowed_phases':['score'],'evaluation_code_sha256':frozen['evaluation_code_sha256'],'allowed_score_spec_sha256':['approved'],'barrier_sha256':'barrier-sha','barrier_audit_sha256':'audit-sha','execution_index_sha256':'index-sha'}
 sha_map['score-spec']='wrong';reads.clear();hashes.clear()
 try:ns['validate_gate']('auth','barrier','barrier-audit','selection','score-spec');raise AssertionError('Unapproved spec allowed')
 except PermissionError:pass
 assert reads==['auth'] and hashes==['score-spec']
 sha_map.update({'score-spec':'approved','barrier':'barrier-sha','barrier-audit':'audit-sha'})
 docs['barrier']={'status':'all_selections_frozen','selection_count':200,'selections':[{}]*199};docs['barrier-audit']={}
 reads.clear();hashes.clear()
 try:ns['validate_gate']('auth','barrier','barrier-audit','selection','score-spec');raise AssertionError('199-entry barrier allowed')
 except ValueError:pass
 assert 'selection' not in reads and 'selection' not in hashes
 reads.clear();hashes.clear()
 try:ns['_join_gold_after_blind']({'gold_rows':'gold-must-not-open'},'missing-proof',[],[],'fake');raise AssertionError('Missing blind proof allowed')
 except KeyError:pass
 assert not hashes and all('gold-must-not-open' not in x for x in reads)
 # Static call-order review of the complete score function. It is NOT executed.
 module=ast.parse((E/'score_cached.py').read_text(encoding='utf-8'))
 score=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='score')
 assert isinstance(score.body[0],ast.Assign) and isinstance(score.body[0].value,ast.Call) and score.body[0].value.func.id=='validate_gate'
 calls=[n for n in ast.walk(score) if isinstance(n,ast.Call)]
 predict=next(n.lineno for n in calls if isinstance(n.func,ast.Attribute) and n.func.attr=='predict_rows')
 blind=next(n.lineno for n in calls if isinstance(n.func,ast.Attribute) and n.func.attr=='write_jsonl' and any(isinstance(x,ast.Constant) and x.value=='blind-predictions.jsonl' for x in ast.walk(n)))
 proof=next(n.lineno for n in calls if isinstance(n.func,ast.Attribute) and n.func.attr=='write_json' and any(isinstance(x,ast.Constant) and x.value=='blind-complete.json' for x in ast.walk(n)))
 gold=next(n.lineno for n in calls if isinstance(n.func,ast.Name) and n.func.id=='_join_gold_after_blind')
 assert predict<blind<proof<gold
 text=(E/'score_cached.py').read_text(encoding='utf-8')
 assert "'target_sequence','peptide_sequence','peptide_sequence_raw'" in text
 assert "record={key:val for key,val in row.items() if key not in excluded}" in text
 assert "metadata['dataset_id'] in internal_panel" in text
 assert 'optimizer' not in text and 'backward(' not in text
 # Tie cache provenance to exact method/input/source/zero-placeholder identities.
 common_source=(E/'common.py').read_text(encoding='utf-8')
 cache_source=(E/'feature_cache.py').read_text(encoding='utf-8')
 assert all(x in common_source for x in ['schema=SCHEMA','method_id=method_id','input_sha256=input_sha256','adapter_tree_sha256=adapter_tree_sha256','placeholder_pKd=0.0'])
 assert "common.sha(cache_path)!=metadata['cache_sha256']" in cache_source
 assert "payload['record_ids']!=[row['record_id'] for row in rows]" in cache_source
 assert "assert_zero_targets(adapter,payload['items'])" in cache_source
 output={'schema':'independent-frozen-cached-scorer-source-review.v1','status':'source_and_synthetic_checks_passed_prepared_only','utc':datetime.now(timezone.utc).isoformat(),
  'frozen_scorer_manifest_path':str(E/'FROZEN-SCORER-v1.json'),'frozen_scorer_manifest_sha256':audit.sha(E/'FROZEN-SCORER-v1.json'),
  'reviewed_code_sha256':frozen['evaluation_code_sha256'],'training_runner_sha256_unchanged':frozen['frozen_runner_sha256'],
  'synthetic_numeric_cases':len(cases),'synthetic_numeric_max_abs_difference_vs_independent':maxdiff,
  'decimal_constant_and_nextafter_cases_passed':True,'pure_metadata_negative_gate_cases':4,
  'static_blind_first_call_line_order':{'predict':predict,'blind_file':blind,'blind_receipt':proof,'join_gold':gold},
  'full_metadata_preserved_except_raw_sequences_SMILES':True,'selected_model_state_fingerprint_check_present':True,
  'no_fit_optimizer_or_candidate_selection_in_score':True,
  'source_review_conclusions':['Every public score entry requires root authorization bound to exact code and score-spec SHA plus immutable200-selection barrier and full-grid audit.','Gold byte hashing/open occurs only after persisted complete blind prediction file and matching proof/hash in inspected source.','Label-free cache signatures bind method,input bytes,adapter source andzero placeholder; payload SHA/order/y0 are rechecked at load.','Classification/discordance/source/external membership metadata survive blind and joined rows. Independent subgroup/matched-reference macros remain a separate postfreeze audit.','Exact decimal constant handling resolves the frozen trainer metric edge without changing training or validation selection logic.'],
  'administrative_condition':'Spec dataset_id equality to cache metadata and input registry exact path/SHA is additionally enforced by reviewed30-spec authorization proof; scorer itself does not compare output dataset_id to metadata dataset_id.',
  'scope_limits':['Static inspected call paths and pure synthetic metadata/math only; not a proof of actual execution or OS-level access control.','SciPy rankdata is used by scorer; independent numeric comparison injects an independently written average-rank implementation.','Real barrier,selected files,model weights,pickle payloads,true gold andreal predictions were NOT opened by this review.'],
  'real_gold_reads':0,'real_prediction_reads':0,'actual_selection_or_model_checkpoint_reads':0,'pickle_payload_reads':0,
  'model_constructions_or_forwards':0,'formal_scoring_authorized_by_review':False}
 audit.write_json(R/'frozen-cached-scorer-source-review-v1.json',output)
 print(json.dumps({'status':output['status'],'synthetic_numeric_cases':len(cases),'negative_gate_cases':4,'real_gold_reads':0,'model_or_prediction_reads':0,'source_review_path':str(R/'frozen-cached-scorer-source-review-v1.json')},ensure_ascii=False))

if __name__=='__main__':main()
