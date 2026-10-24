from pathlib import Path
import json,hashlib,gzip,io,tarfile,collections,csv,datetime
R=Path('.');O=R/'publication/pepinter-fullB24-capability-public-v6';A=R/'reports/pepinter-CPUAdam-activation-cost-independent-v1';H=R/'resources/continuation-20261023/pepinter-CPUAdam-activation-cost-success-preservation-v1'
def sha(b):return hashlib.sha256(b).hexdigest()
def js(n,j):p=O/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
F=A/'FINAL-ACCEPTANCE.json';S=A/'own-snapshot-audit.json';E=A/'small-evidence-independent-audit.json';Q=A/'resource-preservation-independent-audit.json'
assert sha(F.read_bytes())=='a4c23a6412e0a5f24ff52838befede726b7c743bb6de49b616d833ef10f896c5';assert sha(S.read_bytes())=='250e12c9d8e570ac5d1ba11d979ab9e153f02628e31b329853eafb4849aa2002'
f=json.loads(F.read_text(encoding='utf-8'));s=json.loads(S.read_text(encoding='utf-8'));e=json.loads(E.read_text(encoding='utf-8'));q=json.loads(Q.read_text(encoding='utf-8'))
checks=0;mapping=[]
def verify(a,b):
 global checks
 if isinstance(b,dict):
  for k,v in b.items():verify(a[k],v)
 elif isinstance(b,list):
  assert len(a)==len(b)
  for x,y in zip(a,b):verify(x,y)
 elif isinstance(b,(int,float)) and not isinstance(b,bool):assert type(a)==type(b) and a==b;checks+=1

def scrub(v):
 if isinstance(v,dict):return {k:scrub(x) for k,x in v.items() if k not in ['affinity','hostname','host','boot_id','pid','pgid','scientific_pid','CPU','remaining_owned_pids','fresh_live_campaign_leases']}
 if isinstance(v,list):return [scrub(x) for x in v]
 if isinstance(v,str) and v.startswith('/data'):
  key='peptide-four-task-benchmark-20261022/'
  return 'artifact-ref:'+v.split(key,1)[1] if key in v else 'artifact-ref:'+v.rsplit('/',1)[-1]
 return v

def audit_extract(src,j,n,selected):
 public=scrub(selected);verify(selected,public);js(n,public);mapping.append({'source_ref':'record-ref:'+src.as_posix(),'source_sha256':sha(src.read_bytes()),'public_file':n,'public_sha256':sha((O/n).read_bytes()),'operation':'explicit scientific allowlist; paths to artifact-ref and identity fields omitted only'})
accept={k:f[k] for k in ['schema','decision','scope','evidence','independently_verified','runtime_records_not_fully_recomputable','training_resources','historical_failures_unchanged','not_claimed']};audit_extract(F,f,'evidence/final-acceptance-summary.json',accept)
keys=['schema','passed','snapshot_sha256','snapshot_bytes','SHA_verified_before_torch_load_at','torch','map_location','weights_only','trusted_own_checkpoint_only','CUDA_initialized','model_constructions','original_weight_loads','forward_training_calls','model_state_entries','unique_parameter_tensors','parameter_elements','optimizer_states','optimizer_state_tensors','FP32_moment_elements','all_model_and_state_values_finite','all_Adam_steps','optimizer_group_lr','scheduler','cursor','mapping_sha256','same_object_aliases','RNG_structure','limitations']
audit_extract(S,s,'evidence/own-snapshot-audit-summary.json',{k:s[k] for k in keys})
# Only arithmetic on existing small audit JSON, no Torch / checkpoint load.
assert len(s['parameters'])==369 and sum(x['numel'] for x in s['parameters'])==576293761
assert all(x['CPU_finite'] and x['Adam_step']==2 and x['moment_shape_dtype_finite_and_sq_nonnegative'] for x in s['parameters'])
small={k:e[k] for k in ['schema','passed','raw_file_SHA_count','contract_sha256','canonical_valid','exact_identity_birth_argv_PGID_SID','terminal','two_update_runtime_records','phase_counts','phase_durations_seconds','all_phase_nesting_completed','memory_gate_samples','all_memory_gate_samples_passed','activation','native_block_input_records','all_original_B24_T991_FP32_block_inputs','resources','scope','limitations']};audit_extract(E,e,'evidence/small-evidence-independent-summary.json',small)
archive=H/'smallproof.tar.gz';assert sha(archive.read_bytes())=='66db7dae32faa77bf93047c0d22316df0e8e47d9e7af31756cbfb9ac89389299';assert q['verified_files']==148
prefix='runs/pepinter_CPUAdam_activation_twoStep_B24_TRAIN991_GPU8GiB_v1/artifacts/'
source_meta=[]
def save_gzip(n,raw,source_ref):
 p=O/n;p.parent.mkdir(parents=True,exist_ok=True);stream=io.BytesIO()
 with gzip.GzipFile(filename='',fileobj=stream,mode='wb',mtime=0) as g:g.write(raw)
 p.write_bytes(stream.getvalue());assert gzip.decompress(p.read_bytes())==raw
 mapping.append({'source_ref':source_ref,'source_sha256':sha(raw),'source_bytes':len(raw),'public_file':n,'public_sha256':sha(p.read_bytes()),'operation':'deterministic gzip; original scientific text bytes identical'})
with tarfile.open(archive,'r:gz') as t:
 members={m.name:m for m in t.getmembers() if m.isfile()};assert len(members)==149
 def get(n):
  m=members[n];assert m.isfile() and not m.issym() and not m.islnk();b=t.extractfile(m).read();source_meta.append({'archive_member':n,'source_sha256':sha(b),'source_bytes':len(b)});return b
 raw=get(prefix+'summary.json');summary=json.loads(raw);public=scrub({k:v for k,v in summary.items() if k!='loading'});verify(summary,public);js('evidence/runtime-summary.json',public);mapping.append({'source_ref':'archive-sha256:'+sha(archive.read_bytes())+'#'+prefix+'summary.json','source_sha256':sha(raw),'public_file':'evidence/runtime-summary.json','public_sha256':sha((O/'evidence/runtime-summary.json').read_bytes()),'operation':'initializer/tokenizer metadata omitted, private snapshot paths to artifact-ref; scientific numbers kept'})
 for n in ['phase-timings.jsonl']:
  raw=get(prefix+n);rows=[json.loads(x) for x in raw.decode().splitlines() if x];out=[]
  for j in rows:y=scrub(j);verify(j,y);out.append(y)
  p=O/'evidence'/n;p.write_text(''.join(json.dumps(y,ensure_ascii=False)+'\n' for y in out),encoding='utf-8');mapping.append({'source_ref':'archive-sha256:'+sha(archive.read_bytes())+'#'+prefix+n,'source_sha256':sha(raw),'public_file':'evidence/'+n,'public_sha256':sha(p.read_bytes()),'operation':'JSON serialization, scientific values preserved'})
 for step in [1,2]:
  n=f'activation-step{step}.json';raw=get(prefix+n);j=json.loads(raw);assert j['status']=='completed' and j['original_error'] is None
  verify(j,j);counts=dict(collections.Counter(x['op'] for x in j['events']));assert counts=={'preserve':42,'offload':95,'restore':94};save_gzip('logs/'+n+'.gz',raw,'archive-sha256:'+sha(archive.read_bytes())+'#'+prefix+n)
 for n in ['stdout.log','stderr.log']:
  key='resources/continuation-20261023/priority-dispatch/pepinter_CPUAdam_activation_twoStep_B24_TRAIN991_GPU8GiB_v1--20261024T002523458581/'+n;raw=get(key);assert raw==b'';save_gzip('logs/'+n+'.gz',raw,'archive-sha256:'+sha(archive.read_bytes())+'#'+key)
 raw=get(prefix+'frozen-config.json');j=json.loads(raw);pub=scrub(j);verify(j,pub);js('evidence/frozen-config.json',pub);source_meta.append({'public_file':'evidence/frozen-config.json','source_sha256':sha(raw)})
 csvraw=get('resources/continuation-20261023/pepinter-CPUAdam-activation-cost-success-preservation-v1/phase-costs-resource-annotated.csv');(O/'evidence/phase-costs.csv').write_bytes(csvraw);assert csvraw==(H/'phase-costs-resource-annotated.csv').read_bytes();mapping.append({'source_ref':'record-ref:'+(H/'phase-costs-resource-annotated.csv').as_posix(),'source_sha256':sha(csvraw),'public_file':'evidence/phase-costs.csv','public_sha256':sha(csvraw),'operation':'byte-identical scientific phase CSV'})
seal=json.loads((H/'terminal-resource-proof.json').read_text(encoding='utf-8'));keys=['status','exit_code','worker_pid_absent','supervisor_pid_absent','contract_sha256','peak_owned_gpu_mib','physical_limit_mib','minimum_actual_free_mib','required_foreign_reserve_mib','peak_owned_rss_bytes','rss_limit_bytes','resource_guard_stop_reason','steps','nonzero_lr_steps','first_step_lr','baseline_seeds','validation_test_rows'];audit_extract(H/'terminal-resource-proof.json',seal,'evidence/resource-terminal-summary.json',{k:seal[k] for k in keys})
sourcepins={}
for folder in [R/'methods/interaction/continuation-20261023/stockCPUAdam-activation-prepare-v2',R/'methods/interaction/continuation-20261023/stockCPUAdam-activation-prepare-v1']:
 if folder.exists():
  for p in folder.glob('*.py'):
   h=sha(p.read_bytes())
   if h.startswith(('b9324','727b767','06cf607')):sourcepins[p.name]=h
assert {'b9324b6cc7bfbf075df7f55c0000823bfa5183be84cdf729c367535a09c9a3ea','727b767171ff2e7b319e73a517830929a138d6c6c714308aa60b69a87b75a66f','06cf607def620e6d4bf35fa5e457aa54ea1d55c50d6040bf854554b0e1f259d2'}<=set(sourcepins.values())
js('EVIDENCE-INDEX.json',{'final_acceptance_sha256':sha(F.read_bytes()),'deep_snapshot_audit_sha256':sha(S.read_bytes()),'archive_sha256':sha(archive.read_bytes()),'raw_evidence_files':148,'archive_manifest_extra_file':1,'archive_not_redistributed':True,'final_snapshot_sha256':s['snapshot_sha256'],'final_snapshot_bytes':s['snapshot_bytes'],'large_snapshot_not_loaded_or_copied_here':True,'source_pins':sourcepins,'source_and_public_mapping':mapping,'selected_archive_member_source_hashes':source_meta})
js('VALIDATION.json',{'status':'passed','retained_JSON_scientific_numeric_values_exact':checks,'gzip_roundtrip_files':4,'snapshot_model_entries_count':369,'snapshot_audit_json_numel_sum':576293761,'snapshot_artifact_new_CPU_loads_here':0,'first_step_nonzero_lr':False,'positive_lr_updates':1,'Adam_calls':2,'original_NN_weight_GPU_execution':0,'snapshot_model_weights_input_sequences_labels_included':False,'private_process_tables_or_rawbundle_recursion':False})
print(json.dumps({'numeric_checks':checks,'source_pins':sourcepins,'new_files':len([p for p in O.rglob('*') if p.is_file()])}))
