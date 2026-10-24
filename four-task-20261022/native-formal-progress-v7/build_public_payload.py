from pathlib import Path
import json,hashlib,tarfile,gzip,io,datetime,subprocess
R=Path('.');O=R/'publication/native-formal-progress-public-v7';H=R/'resources/continuation-20261023/pepinter-formal-candidate0-segment1-terminal-preservation-v1';A=H/'smallproof.tar.gz'
def sha(b):return hashlib.sha256(b).hexdigest()
def sh(p):return sha(p.read_bytes())
def js(n,j):p=O/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert sh(A)=='97e1b2457a25cbc48d06ed9e88701247ecc9e360299d3cbc98f696c3b3f4e18c'
C=R/'resources/continuation-20261023/pepinter-paused218-inspector-actual-v1/inspection-certificate.json';J=R/'reports/pepinter-formal-segment2-resource-independent-v1/independent-audit.json';U=R/'reports/uniair-parallel-CPU-route-feasibility-v1/runtime-prepare-v1/native-source-import-v2/ACTUAL-INDEPENDENT-AUDIT.json';P=R/'methods/interaction/continuation-20261024/full-CPUAdam-activation-formal-v1/PREPARE-PROTOCOL.json'
assert sh(C)=='9c5d947fbe9aa28af71d4cbf40f917a9d00be21fb633945e7a4b6bb3be532a7d';assert sh(J)=='509cb05b42b0da533c5ba800faf723e8004052fea2ceaa03ec254a3e3ce64458';assert sh(U)=='9529cd5f6368500b00ee0c0411686045c3248b6bfedecaab3f2b247ba637c718'
checks=0;mapping=[]
def scrub(x):
 if isinstance(x,dict):return {k:scrub(v) for k,v in x.items() if k not in ['pid','pgid','uid','hostname','host','job_id','birth','boot_id','GPU_name','GPU_capability','remaining_owned','remaining_owned_pids','scientific_pid','supervisor_pid']}
 if isinstance(x,list):return [scrub(v) for v in x]
 if isinstance(x,str) and (x.startswith('/data') or x.startswith('/publicfs')):
  mark='peptide-four-task-benchmark-20261022/';return 'artifact-ref:'+x.split(mark,1)[1] if mark in x else 'artifact-ref:'+x.rsplit('/',1)[-1]
 return x

def verify(a,b):
 global checks
 if isinstance(b,dict):
  for k,v in b.items():verify(a[k],v)
 elif isinstance(b,list):
  assert len(a)==len(b)
  for x,y in zip(a,b):verify(x,y)
 elif isinstance(b,(int,float)) and not isinstance(b,bool):assert type(a)==type(b) and a==b;checks+=1

def selected(src,j,dst,allow):
 out=scrub({k:j[k] for k in allow});verify(j,out);js(dst,out);mapping.append({'source_ref':'record-ref:'+src.as_posix(),'source_sha256':sh(src),'public_file':dst,'public_sha256':sh(O/dst),'operation':'explicit scientific allowlist,privateidentity omitted and absolute paths to artifact-ref'})

def putgzip(dst,raw,source_ref,source_sha=None):
 f=O/dst;f.parent.mkdir(parents=True,exist_ok=True);b=io.BytesIO()
 with gzip.GzipFile(filename='',fileobj=b,mode='wb',mtime=0) as g:g.write(raw)
 f.write_bytes(b.getvalue());assert gzip.decompress(f.read_bytes())==raw;mapping.append({'source_ref':source_ref,'source_sha256':source_sha or sha(raw),'public_file':dst,'public_sha256':sh(f),'public_plaintext_sha256':sha(raw),'operation':'deterministic gzip of explicit scientific fields; no process tables'})
prefix='runs/pepinter_formal_CPUAdamActivation_seed00_candidate00_segment01_v1/artifacts/'
with tarfile.open(A,'r:gz') as t:
 members={m.name:m for m in t.getmembers() if m.isfile()}
 def get(n):
  m=members[n];assert m.isfile() and not m.issym() and not m.islnk();return t.extractfile(m).read()
 summary_raw=get(prefix+'summary.json');summary=json.loads(summary_raw);pub=scrub(summary);verify(summary,pub);assert pub['status']=='paused_checkpointed' and pub['complete_candidate'] is False and pub['cursor']['completed_optimizer_steps']==218 and pub['cursor']['epoch_rows']==5232 and pub['cursor']['epoch_summaries']==[]
 js('evidence/pepinter-segment01-summary.json',pub);mapping.append({'source_ref':'archive-sha256:'+sh(A)+'#'+prefix+'summary.json','source_sha256':sha(summary_raw),'public_file':'evidence/pepinter-segment01-summary.json','public_sha256':sh(O/'evidence/pepinter-segment01-summary.json'),'operation':'snapshotpath identity only replaced; originalscientificvalues preserved'})
 raw=get(prefix+'steps.jsonl');steps=[json.loads(x) for x in raw.decode().splitlines() if x];assert len(steps)==218 and sum(x['rows'] for x in steps)==5232 and [x['batch'] for x in steps]==list(range(218));out=[]
 allowed=['epoch','batch','native_batch_mean_Focal','gradient_norm_before_clip','learning_rate_used','learning_rate_after_scheduler','parameters_with_gradient','rows','paired_token_length','raw_paired_token_max','fullstate_audit_this_step']
 for x in steps:
  y={k:x[k] for k in allowed};verify(x,y);assert y['paired_token_length']==(y['raw_paired_token_max']+7)//8*8;out.append(y)
 putgzip('logs/pepinter-segment01-training-steps.jsonl.gz',''.join(json.dumps(y)+'\n' for y in out).encode(),'archive-sha256:'+sh(A)+'#'+prefix+'steps.jsonl',sha(raw))
 raw=get(prefix+'phase-timings.jsonl');phase=[json.loads(x) for x in raw.decode().splitlines() if x];allowed=['phase','status','elapsed_seconds','RSS_before_bytes','RSS_after_bytes','RSS_peak_bytes','GPU_allocated_bytes','GPU_reserved_bytes','GPU_peak_allocated_bytes','GPU_peak_reserved_bytes','step','epoch','error_type'];out=[]
 for x in phase:
  y={k:x[k] for k in allowed if k in x};verify(x,y);out.append(y)
 putgzip('logs/pepinter-segment01-phase-timings.jsonl.gz',''.join(json.dumps(y)+'\n' for y in out).encode(),'archive-sha256:'+sh(A)+'#'+prefix+'phase-timings.jsonl',sha(raw))
 dp='resources/continuation-20261023/priority-dispatch/pepinter_formal_CPUAdamActivation_seed00_candidate00_segment01_v1--20261024T014340607931/'
 for n in ['stdout.log','stderr.log']:
  raw=get(dp+n);assert raw==b'';putgzip('logs/pepinter-segment01-'+n+'.gz',raw,'archive-sha256:'+sh(A)+'#'+dp+n)
 dispatch=json.loads(get(dp+'dispatch.json'));resource={k:dispatch[k] for k in ['status','started_at','finished_at','exit_code','stop_reason','contract_sha256','peak_owned_gpu_mib','peak_owned_rss_bytes','minimum_observed_actual_free_mib'] if k in dispatch};verify(dispatch,resource);js('evidence/pepinter-segment01-terminal-resource-summary.json',resource)
cert=json.loads(C.read_text(encoding='utf-8'));selected(C,cert,'evidence/pepinter-218-structural-inspection.json',['schema','checkpoint','actual_SHA_verified','mmap_CPU_metadata_only','identity','sampler_sha256','sampler_matches_exact_frozen_plan','committed_steps','cursor','mapping_sha256','checkpoint_state_structural_audit','source_inspector_sha256','latest_index_sha256','prior_terminal_sha256','prior_launch_sha256','prior_config_sha256','originalNN_forward_or_newfit'])
j=json.loads(J.read_text(encoding='utf-8'));selected(J,j,'evidence/pepinter-segment02-resource-review-summary.json',['schema','decision','descriptor_sha256','factory_sha256','resource_manifest_sha256','science_resume_proof','resource_proof','limitations'])
u=json.loads(U.read_text(encoding='utf-8'));selected(U,u,'evidence/uniair-source-import-v2-audit-summary.json',['schema','passed','NN_training','new_model_forward','audit_scope','input_readback_sha256','audit_code_sha256','source_import_receipt_sha256','process_receipt_sha256','limitations'])
proto=json.loads(P.read_text(encoding='utf-8'));fidelity={'protocol_sha256':sh(P),'initializer':proto['initializer'],'padding_backend':proto['padding_backend'],'clean2290':proto['clean2290'],'CPUAdam_backend':'stockCPUFP32optimizer withGPU BF16 autocast/FP32parameters and gradients;not fullGPUoptimizerbitwiseequivalence','validation_TEST_this_segment':{'completed_validation':False,'TESTrows':0,'completed_epochs':0,'completed_candidates':0,'completed_full_native_seeds':0}}
fidelity=scrub(fidelity);js('FIDELITY-SCOPE.json',fidelity);assert fidelity['initializer']['exact_released_affinitytrain_overlap_in_test2349']==59
rootrefs=[]
for f in (R/'reports/continuation-root-review-20261024').glob('*.json'):
 h=sh(f)
 if h.startswith(('b7b','9ac')):rootrefs.append({'source_ref':'record-ref:'+f.as_posix(),'source_sha256':h,'role':'Rootapprovedsegment02 metadata;not actualstartupreceipt'})
assert len(rootrefs)>=2,rootrefs
js('STATUS-SNAPSHOT.json',{'schema':'fourtask.native-formal-progress.public.v7','as_of_scope':'Root task assignment and immutable segment01 evidence;newactualsegment02receipt absent from thissnapshot','PepInter':{'seed':0,'candidate':0,'segment01_status':'paused_checkpointed','committed_optimizer_steps':218,'epoch':1,'rows_processed_in_epoch':5232,'full_training_rows_each_epoch':10882,'completed_epochs':0,'complete_candidate':False,'full5epoch_target':5,'complete_native_seed':False,'validation_or_TEST_results':0,'latest_snapshot_bytes':6925539880,'latest_snapshot_sha256':'5e33ca14cd3ce9c57cf30954f13447db88839ffcf801d4a2a49e14c6d59a5640','inspector_certificate_actualSHA':sh(C),'inspector_limit':'CPU mmap STRUCTURAL audit;not newfinitevalue recomputation or neuralforward','segment02':'Rootscience/resourceapproved,owner preparingstartup;no actualreceipt in thissnapshot,not certified running','segment02_approval_refs':rootrefs},'UniAIR':{'source_import_v2':'actualPASS audited;originalmodule/CPP-import scope,not expertweightload/fullforwardfit','source_import_audit_sha256':sh(U),'physical_assets_transfer':'in_progress_reported_at_scope_cutoff;not allfileSHAclosure certified','planned10weights_plus_geometry_bytes':5904270047,'transfercompletion_certified':False,'full20candidate_completed':0,'fullnative_seed_completed':0},'benchmark_totals':'Existing1050main and100known-source-supplement remain distinct;newfullnativecompletedseeds0','old_v6_cost_and_v5_failures':'immutable history kept;no overwrittenresults','NN_weight_GPU_or_snapshot_execution_here':0})
js('EVIDENCE-INDEX.json',{'segment01_raw_archive_sha256':sh(A),'checkpointbinary_not_loaded_or_copied':True,'inspection_certificate_actual_sha256':sh(C),'segment02_independent_resource_audit_sha256':sh(J),'UniAIR_source_import_actual_audit_sha256':sh(U),'source_to_public_files':mapping,'private_raw_receipts_process_tables_not_redistributed':True})
js('VALIDATION.json',{'status':'passed','retained_JSON_scientific_numbers_exact':checks,'training_log_rows':218,'training_rows_sum':5232,'all_padded_lengths_author_multiple8_formula_checked':True,'completed_epoch_summaries_empty':True,'no_full_candidate_or_seed_completion_claim':True,'four_gzip_roundtrips':True,'source_inspector_is_structure_not_finite_value_recomputation':True,'segment02_running_not_claimed':True,'no_NN_GPU_weight_large_state_reads':True})
print(json.dumps({'numeric_checks':checks,'training_logs':len(steps),'phase_records':len(phase),'Rootapproval_refs':len(rootrefs)}))
