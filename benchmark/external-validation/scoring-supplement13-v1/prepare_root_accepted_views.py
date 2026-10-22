"""Materialize root-accepted supplementary13 views, no fitting or inference.

Historical not-adopted files and accepted external75 artifacts stay byte-identical.
The existing gold is copied exactly, never relabelled or selected by model results.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone,timedelta
import hashlib,json,math,py_compile

HERE=Path(__file__).resolve().parent;EXTERNAL=HERE.parent;PROJECT=EXTERNAL.parent
CANDIDATE=EXTERNAL/'IgG-Fc-supplementary-audit-v1'
CANDIDATE_SHA='5a4be60f2b4579d51aa1ff42257751bc8a0619ecb11c207e473b71bdb7a07bfc'
EXTERNAL75_SHA='85973838adc28c0b6b9134a28a90312162a158eafd20f8b2bf14e68e13d36c4d'
PANELS=('source_peptide_dependency_cold','target_reference_homology_cold')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def readl(path):return [json.loads(l) for l in path.open(encoding='utf-8') if l.strip()]
def dump(path,x):
 assert not path.exists(),'Accepted views must not be overwritten: '+str(path)
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def writel(path,rows):
 assert not path.exists(),'Accepted views must not be overwritten: '+str(path)
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w',encoding='utf-8') as f:
  for row in rows:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
def wsl(path):
 p=str(path).replace('\\','/');assert p[1:3]==':/'
 return '/mnt/'+p[0].lower()+p[2:]
def check_artifacts(manifest):
 for a in manifest['artifacts']:
  p=Path(a['path']);assert sha(p)==a['sha256'] and p.stat().st_size==a['bytes']

def main():
 rootmanifest=HERE/'root-accepted-manifest.json';assert not rootmanifest.exists()
 candidatepath=CANDIDATE/'postfreeze-supplement-candidate-manifest.json'
 external75path=EXTERNAL/'acceptance-manifest.json'
 assert sha(candidatepath)==CANDIDATE_SHA and sha(external75path)==EXTERNAL75_SHA
 candidate=json.loads(candidatepath.read_text(encoding='utf-8'));old75=json.loads(external75path.read_text(encoding='utf-8'))
 check_artifacts(candidate);check_artifacts(old75)
 originalinput=CANDIDATE/'supplement-inputs13-not-adopted.jsonl';originalgold=CANDIDATE/'supplement-gold13-not-adopted.jsonl'
 rows=readl(originalinput);gold=readl(originalgold);bygold={r['record_id']:r for r in gold}
 assert len(rows)==len(gold)==len(bygold)==len({r['record_id'] for r in rows})==13
 assert Counter(r['evaluation_stratum'] for r in rows)=={'synthetic_D_backbone':8,'standard20_control':5}
 fullrefsource=CANDIDATE/'target-reference-multichain.json';fullref=HERE/'provenance/target-reference-multichain.json'
 fullref.parent.mkdir(parents=True,exist_ok=True);assert not fullref.exists();fullref.write_bytes(fullrefsource.read_bytes())
 identity=json.loads(fullref.read_text(encoding='utf-8'));heavy=identity['target_reference_heavy_sequence']
 assert len(heavy)==449 and len(identity['target_reference_light_sequence'])==214
 assert [(x['chain'],x['stoichiometry']) for x in identity['reference_components']]==[('heavy',2),('light',2)]
 outrows=[]
 for source in rows:
  r=dict(source);assert len(r['target_sequence'])==449 and r['target_sequence']==heavy
  assert isinstance(r['NC_core'],bool)
  assert r['NC_core']==(r['evaluation_stratum']=='synthetic_D_backbone')
  assert 'pKd' not in r and 'Kd_M' not in r and 'reported_value' not in r
  assert r['source_HRMS_formula_and_CIP_checks_passed'] is True
  ann=r['source_chemical_annotation']
  assert r['n_terminal']==ann['n_terminal'] and r['c_terminal']==ann['c_terminal']
  assert r['disulfide_residue_positions_1based']==ann['disulfide_residue_positions_1based']==[2,12]
  assert r['actual_residue_tokens']==ann['actual_residue_tokens'] and len(r['actual_residue_tokens'])==15
  assert r['canonical_isomeric_smiles']==r['peptide_smiles']
  assert r['chemical_entity_id']==hashlib.sha256(r['canonical_isomeric_smiles'].encode()).hexdigest()
  # Complete2H2L composition is preserved independently. The authors' single
  # target-sequence interface receives exactly the declared449aa heavy reference.
  r.pop('target_reference_components')
  r.update(target_reference_components_provenance_file=str(fullref),target_reference_components_provenance_sha256=sha(fullref),
   target_sequence_scope='root_accepted449aa_heavy_reference_Fc_side_not_whole2H2L_or_actual_assayed_construct',
   target_reference_view=True,actual_assay_clone_verified=False,whole2H2L_or_lot_or_glycoform_certified=False,
   target_single_chain_view_requires_root_adoption=False,
   adoption_status='root_accepted_postfreeze_separate_supplementary_diagnostic_never_merged_into_external75',
   root_acceptance_scope='source_and_declared_chemical_cold_reference_view_only_no_performance_based_selection',
   external_source_cold_against_PPIKB=True,external_chemical_cold_against_full_PPIKB=True,
   external_reference_target_related=True,external_reference_target_cold=False,external_family_cold_certified=False,
   current_external75_membership=False,format_derived_from_fixed_author_measured_entity=True,
   chemistry_flags=['exact_author_measured_entity_format','source_formula_and_CIP_validated','N_acetyl_and_actual_C_terminal_preserved','explicit_disulfide_connectivity_preserved'],
   annotation_unresolved_components=[],study_component_id='supplement13:10.1248/cpb.c25-00637',
   target_reference_full_sha256=hashlib.sha256(heavy.encode()).hexdigest(),
   source_candidate_manifest_sha256=CANDIDATE_SHA,
   external_evaluation_status='retrospective_post_global200_selection_freeze_only')
  for key in ('peptide_smiles','canonical_isomeric_smiles','actual_residue_tokens','disulfide_residue_positions_1based','n_terminal','c_terminal','source_chemical_annotation','target_sequence'):
   assert r[key]==source[key]
  truth=bygold[r['record_id']];assert truth['qualifier']=='=' and truth['reported_unit']=='nM'
  assert math.isclose(truth['Kd_M'],truth['reported_value']*1e-9,rel_tol=1e-12)
  assert math.isclose(truth['pKd'],-math.log10(truth['Kd_M']),abs_tol=1e-12)
  outrows.append(r)
 inputpath=HERE/'inputs/input13.jsonl';goldpath=HERE/'gold/gold13.jsonl'
 writel(inputpath,outrows);goldpath.parent.mkdir(parents=True,exist_ok=True);assert not goldpath.exists();goldpath.write_bytes(originalgold.read_bytes())
 assert sha(goldpath)==sha(originalgold)
 idsall=sorted(r['record_id'] for r in outrows);idsnc=sorted(r['record_id'] for r in outrows if r['NC_core']);idsstd=sorted(r['record_id'] for r in outrows if not r['NC_core'])
 assert len(idsnc)==8 and len(idsstd)==5 and set(idsnc).isdisjoint(idsstd) and set(idsnc)|set(idsstd)==set(idsall)
 for name,ids in [('all13',idsall),('nc8',idsnc),('standard5',idsstd)]:dump(HERE/('ids-'+name+'.json'),ids)
 specs=[]
 for panel in PANELS:
  path=HERE/(panel+'-supplement13-score.cpu.json')
  spec={'split_id':panel,'holdout_id':'postfreeze-supplement13-reference-view-v1',
   'input_rows':wsl(inputpath),'input_rows_sha256':sha(inputpath),'label_rows':wsl(goldpath),'label_rows_sha256':sha(goldpath),
   'output_root':wsl(PROJECT/'formal-runs-gpu-v4/supplement13-scores-v1'/panel),
   'selection_barrier_path':wsl(PROJECT/'formal-runs-gpu-v4/all-selections-frozen.json'),
   'methods_root':wsl(PROJECT/'methods'),'cpu_threads':2,'batch_size':32,'device':'cpu','gpu_explicitly_authorized':False,
   'scientific_external_status':'Separate root-accepted retrospective source/declared-chemical-cold diagnostic:8synthetic_D_backbone+5standard20_control; all reference-target-related; single449aa heavy Fc-side reference, not whole2H2L or assayed construct/lot/glycoform certified; not familycold',
   'root_accepted_manifest_path':wsl(rootmanifest),'old_external75_modified':False,'input_accepted_without_model_scores':True,
   'nc_ids':wsl(HERE/'ids-nc8.json'),'standard_control_ids':wsl(HERE/'ids-standard5.json'),
   'reuse_one13_prediction_set_for_subgroup_metrics':True,'prepared_only_no_model_invocation':True}
  dump(path,spec);specs.append(path)
 now=datetime.now(timezone.utc)
 files=[inputpath,goldpath,fullref,*sorted(HERE.glob('ids-*.json')),*specs]
 decision={'issuer':'/root','authority':'Direct same-thread parent task accepting13 solely on traceable chemical/source/input evidence within user-authorized benchmark scope',
  'decision_text':'Accept13 as a separate post-freeze diagnostic:8synthetic_D_backbone+5standard20_control; source+declaredchemicalcold; allreference-target-related;449aaheavyFc-side reference view; preserve2H2L/lot/glycoform limits; no merge into75 and no training or model selection changes.',
  'decision_basis':['SourceDOI/PMID/title provenance independently checked against all21845 PPIKB rows.','Original-author measured entities passed explicitcaps/residue/stereochemistry/disulfide/formula checks.','Exactstereo/achiral/Morgan>=.8 audit against11256 graphs passed.','Full449heavy+214light2H2L reference identity preserved independently.'],
  'decision_did_not_consult_test_external_or_supplement_model_scores':True}
 manifest={'schema':'root-accepted-supplement13-scoring-view.v1','status':'accepted_inputs_prepared_not_inferred',
  'recorded_at_utc':now.isoformat(),'recorded_at_Asia_Shanghai':now.astimezone(timezone(timedelta(hours=8))).isoformat(),
  'root_direct_task_decision':decision,'source_candidate_manifest':str(candidatepath),'source_candidate_manifest_sha256':CANDIDATE_SHA,
  'preserved_external75_acceptance_manifest_sha256':EXTERNAL75_SHA,
  'counts':{'total':13,'NC_core':8,'standard_controls':5,'synthetic_D_backbone':8,'standard20_control':5,'PTM':0,'source_cold':13,'declared_chemical_cold':13,'reference_target_related':13,'reference_target_cold':0,'family_cold_certified':0,'whole2H2L_or_assayed_construct_certified':0,'model_predictions':0},
  'gold_policy':{'immutable_original_gold_sha256':sha(originalgold),'accepted_gold_copy_sha256':sha(goldpath),'exact_bytes_preserved':True,'location':str(goldpath),'usage':'Only after all200 original candidate selections are frozen; no relabelling, tuning, candidate reselection, or acceptance by observed test performance.','isolation':'Separatefiles and cache-only label-free input delivery under shared user account; noOS-access enforcement claim.','exposure':'Retrospective original labels previously inspected during source preparation, not prospectiveblind.'},
  'target_input_scope':'Exactly449aa heavy reference forFc-side interaction. Full2H2L provenance separately retained. No artificial light/heavy concatenation, no whole antibody/lot/glycoform or family-cold certification.',
  'evaluation_policy':'Keep this13-case supplement separate from old75 and all train/validation/test pools. Score all13once per frozen model/seed; reuse predictions to summarize8NC and5standard controls. Preserve all10seeds and missing/modelrejection reasons. One original study is not13independent systems.',
  'selection_barrier_path':wsl(PROJECT/'formal-runs-gpu-v4/all-selections-frozen.json'),
  'no_model_or_optimizer_or_cache_encoder_called_by_this_preparation':True,
  'historical_not_adopted_files_preserved':True,'external75_all_accepted_artifact_hashes_unchanged':True,
  'artifacts':[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in files]}
 dump(rootmanifest,manifest)
 assert sha(candidatepath)==CANDIDATE_SHA and sha(external75path)==EXTERNAL75_SHA
 check_artifacts(candidate);check_artifacts(old75);check_artifacts(manifest)
 py_compile.compile(str(Path(__file__)),doraise=True)
 print(json.dumps({'root_manifest':str(rootmanifest),'root_manifest_sha256':sha(rootmanifest),'label_free_input':str(inputpath),'input_sha256':sha(inputpath),'gold_copy_sha256':sha(goldpath),'counts':manifest['counts']},ensure_ascii=False))
if __name__=='__main__':main()
