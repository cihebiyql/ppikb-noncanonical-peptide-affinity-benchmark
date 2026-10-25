"""Independent expanded-v3 completed-candidate audit, metadata/CSV only."""
from __future__ import annotations
import argparse,csv,ctypes,hashlib,json,math,os,posixpath,time
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from ctypes import wintypes

WORKER='4576a840618537b4214908feaa6554ea2c5365573482c6a067a9df808b038ff5'
COHORT='93cdc000433e3c0babd7a5b7e183acd2fbe25649f4d2e7d5d95f5f0ad5aacae4'
LABELS='c3d8f4e42600f0c762bb9d2d24595a32c8f13de7a1f5018d59047d241dd8525a'
RECIPE='0cd5d5e04a6503af84033c72b2723e2c19e66e8a74db2315dbf0db037d955a17'
SETTINGS={'batch_size':8,'max_epochs':30,'patience':5,'weight_decay':0.01,'gradient_clip_norm':1.0,'pooling':'native_mean_pool','dtype':'float32','tf32':False,'max_tokens_including_special':768,'head':[832,256,1],'dropout':0.1,'pretraining_token_prediction_head_removed':True}
SPECS={'hybrid':'765ad532dce0f2757b9aecba262c2dbabc591b441b7a1509b46c900d7f506299','mlm':'4aa9efb626b0caaa6e164da531f1f6a17abc8cb8e58c8bee896bc82ceb897bb7'}

MODELS=['hybrid','mlm','2025']
WORKERS={"2025":"4a9256ad9dd6d2c1eb2718f14a766db6ba9000633312cab1308325e50b12aaff","hybrid":"4576a840618537b4214908feaa6554ea2c5365573482c6a067a9df808b038ff5","mlm":"4576a840618537b4214908feaa6554ea2c5365573482c6a067a9df808b038ff5"}
SETTINGS_BY_MODEL=json.loads(r'''{"2025":{"batch_size":8,"max_epochs":30,"patience":5,"weight_decay":0.01,"gradient_clip_norm":1,"pooling":"adapted_masked_mean_including_cls_sep","dtype":"float32","tf32":false,"max_tokens_including_special":768,"head":[1088,256,1],"dropout":0.1,"pretraining_token_prediction_head_removed":true,"parameter_counts":{"encoder_total":43029504,"encoder_learnable":42980352,"native_fixed_sinusoidal":49152,"head":279041,"total":43308545,"trainable":43259393},"fixed_native_position_parameter":"encoder.embed_positions.weight","common_reference_manifest_sha256":"93cdc000433e3c0babd7a5b7e183acd2fbe25649f4d2e7d5d95f5f0ad5aacae4"},"hybrid":{"batch_size":8,"max_epochs":30,"patience":5,"weight_decay":0.01,"gradient_clip_norm":1,"pooling":"native_mean_pool","dtype":"float32","tf32":false,"max_tokens_including_special":768,"head":[832,256,1],"dropout":0.1,"pretraining_token_prediction_head_removed":true},"mlm":{"batch_size":8,"max_epochs":30,"patience":5,"weight_decay":0.01,"gradient_clip_norm":1,"pooling":"native_mean_pool","dtype":"float32","tf32":false,"max_tokens_including_special":768,"head":[832,256,1],"dropout":0.1,"pretraining_token_prediction_head_removed":true}}''')
IDENTITIES=json.loads(r'''{"2025":{"model":"aaronfeller/PeptideCLM-23M-all","revision":"a0847d8231d236645a2c4f629590118716c6fdda","weights_sha256":"b0c76524025a560bc429f50591dbf5555f638a977dcf79a55f52965ddec88669","pooling":"adapted_masked_mean_including_cls_sep","embedding_dimension":768,"max_tokens_including_special":768,"pretrained_corpus_test_entity_exposure":"unknown","input_adapter":"peptideclm2025_spe_cccc_to_cc_cc_v1","input_adapter_sha256":"18c93586978208d2772f9bc249066c9ecce6dfe58558bebca2f08d9502bc7bd2","input_adapter_recipe_sha256":"0fe967597586337d3684c6c9de95560e70df1ea1efcd44a8db6f55870808e0d2","source_manifest_sha256":"c1541420d34a09a642d3390011a3e4419b011ad01cb5a77e65e2b6a743a0f914","original_safe_loader_sha256":"2205c3f2de478f72a58f01fc16352ee86a372b792c5a563ce40dec3e972c1688","actual_metadata_coverage_sha256":"55a3082b0b1fdd416db2724cbf1e9d37d0622de94146e1e2afa095c3224eb82d","tokenizer_identity":"project_SPE_output_adapter_not_author_native"},"hybrid":{"repository":"aaronfeller/peptideclm-2-hybrid-small","revision":"62d5db6922a5a5ece56f9cd5adc48ab2b19d2e57","asset_sha256":{"ChemPepMTR.py":"a3b6c48b48a9035bfda6dc7c29c67d7ed6ce74161a3eb116abe3c8a0a438a395","README.md":"20193b1633c3aff3e2e8fc3e546f7f6051f4977ebfa0d8f97b0bcde645467e9b","__init__.py":"a9d40b412d57f23ef80732ca1b25a7cc249282bea5968c3b476dbf5664a14bbc","config.json":"1aed699cdfb7e5c4ef06666a48f185f4b1bc5711dbccdbd6da2412abd2bf2295","config.py":"0c8fdf80e5a6eb86b5e019b50cace117579058d09183d7e45c692f61aef621a5","model.safetensors":"c4c2b341d219516f1a5771b123858ba4bb1be55ea35e1b634e627517ccceb06d","special_tokens_map.json":"5d5b662e421ea9fac075174bb0688ee0d9431699900b90662acd44b2a350503a","tokenizer.json":"d7cfeefb9290fb094430641a53dcfeba580efc60b64bb4a84225366d7dc75d98","tokenizer_config.json":"09a7db7532214b31a8b6ceacd30e26aad089c2c0364b3b5387b3a3681bd23f63"},"asset_receipt_sha256":"b4c82a9706a8ba52f9d7ddf0d3bae2da099fc2642b44f8835676b96a7702679c","tokenizer_adapter":{"name":"ringfix-v2-percent-preserving","recipe_sha256":"0cd5d5e04a6503af84033c72b2723e2c19e66e8a74db2315dbf0db037d955a17","adapter_source_sha256":"e16d7aa4ae16961a9d2f55bdc7a14373c194a2d2e6631c803db307e96bad81ca","base_tokenizer_sha256":"d7cfeefb9290fb094430641a53dcfeba580efc60b64bb4a84225366d7dc75d98","weights_unchanged":true,"vocabulary_unchanged":true,"smiles_unchanged":true}},"mlm":{"repository":"aaronfeller/peptideclm-2-mlm-small","revision":"7fe899df4d9753224aefa955ed0cf859d181e693","asset_sha256":{"ChemPepMTR.py":"a3b6c48b48a9035bfda6dc7c29c67d7ed6ce74161a3eb116abe3c8a0a438a395","README.md":"9991584f7d85f87cc4de0f32ec65dc278e1b3715cd2c35df560a3eff46f59f9e","__init__.py":"a9d40b412d57f23ef80732ca1b25a7cc249282bea5968c3b476dbf5664a14bbc","config.json":"1aed699cdfb7e5c4ef06666a48f185f4b1bc5711dbccdbd6da2412abd2bf2295","config.py":"0c8fdf80e5a6eb86b5e019b50cace117579058d09183d7e45c692f61aef621a5","model.safetensors":"713fb214c51d42bd038b4dd71928ea5f5e0c3c2cf58be1fce8345cc395ef5f4a","special_tokens_map.json":"5d5b662e421ea9fac075174bb0688ee0d9431699900b90662acd44b2a350503a","tokenizer.json":"d7cfeefb9290fb094430641a53dcfeba580efc60b64bb4a84225366d7dc75d98","tokenizer_config.json":"09a7db7532214b31a8b6ceacd30e26aad089c2c0364b3b5387b3a3681bd23f63"},"asset_receipt_sha256":"b4c82a9706a8ba52f9d7ddf0d3bae2da099fc2642b44f8835676b96a7702679c","tokenizer_adapter":{"name":"ringfix-v2-percent-preserving","recipe_sha256":"0cd5d5e04a6503af84033c72b2723e2c19e66e8a74db2315dbf0db037d955a17","adapter_source_sha256":"e16d7aa4ae16961a9d2f55bdc7a14373c194a2d2e6631c803db307e96bad81ca","base_tokenizer_sha256":"d7cfeefb9290fb094430641a53dcfeba580efc60b64bb4a84225366d7dc75d98","weights_unchanged":true,"vocabulary_unchanged":true,"smiles_unchanged":true}}}''')
SPECS.update({'2025':'8b126e2c28f26e466b8efe0da6e8a12ba96842885e4864f5339a8b611efed74b'})

def model_identifier_matches(model,identity):
 if model not in IDENTITIES:return False
 field='model' if model=='2025' else 'repository'
 return identity.get(field)==IDENTITIES[model][field]

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024**2),b''):h.update(b)
 return h.hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def rows(p):
 with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def ranks(a):
 order=sorted(range(len(a)),key=lambda i:a[i]);out=[0.]*len(a);start=0
 while start<len(a):
  end=start+1
  while end<len(a) and a[order[end]]==a[order[start]]:end+=1
  for i in order[start:end]:out[i]=(start+end+1)/2
  start=end
 return out
def corr(a,b):
 if len(a)<2 or max(a)==min(a) or max(b)==min(b):return None
 ma=sum(a)/len(a);mb=sum(b)/len(b)
 return sum((x-ma)*(y-mb) for x,y in zip(a,b))/math.sqrt(sum((x-ma)**2 for x in a)*sum((y-mb)**2 for y in b))
def metrics(y,p):
 n=len(y);e=[b-a for a,b in zip(y,p)];ss=sum(x*x for x in e);ym=sum(y)/n;den=sum((x-ym)**2 for x in y)
 return {'n':n,'mae':sum(map(abs,e))/n,'rmse':math.sqrt(ss/n),'bias':sum(e)/n,'r2':1-ss/den if den else None,'pearson':corr(y,p),'spearman':corr(ranks(y),ranks(p))}
def guard():
 k=ctypes.WinDLL('kernel32',use_last_error=True);k.GetCurrentProcess.restype=wintypes.HANDLE
 current=k.GetCurrentProcess();pm=ctypes.c_size_t();sm=ctypes.c_size_t()
 k.GetProcessAffinityMask.argtypes=[wintypes.HANDLE,ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_size_t)]
 k.SetProcessAffinityMask.argtypes=[wintypes.HANDLE,ctypes.c_size_t];k.SetPriorityClass.argtypes=[wintypes.HANDLE,wintypes.DWORD]
 if not k.GetProcessAffinityMask(current,ctypes.byref(pm),ctypes.byref(sm)):raise ctypes.WinError(ctypes.get_last_error())
 one=pm.value & -pm.value
 if not k.SetProcessAffinityMask(current,one) or not k.SetPriorityClass(current,0x40):raise ctypes.WinError(ctypes.get_last_error())
 class Basic(ctypes.Structure):
  _fields_=[('ProcessUser',ctypes.c_longlong),('JobUser',ctypes.c_longlong),('Flags',wintypes.DWORD),('MinWS',ctypes.c_size_t),('MaxWS',ctypes.c_size_t),('Active',wintypes.DWORD),('Affinity',ctypes.c_size_t),('Priority',wintypes.DWORD),('Scheduling',wintypes.DWORD)]
 class IO(ctypes.Structure):_fields_=[(x,ctypes.c_ulonglong) for x in ['Read','Write','Other','ReadBytes','WriteBytes','OtherBytes']]
 class Extended(ctypes.Structure):_fields_=[('Basic',Basic),('IO',IO),('ProcessMemory',ctypes.c_size_t),('JobMemory',ctypes.c_size_t),('PeakProcessMemory',ctypes.c_size_t),('PeakJobMemory',ctypes.c_size_t)]
 k.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR];k.CreateJobObjectW.restype=wintypes.HANDLE
 k.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
 k.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE]
 job=k.CreateJobObjectW(None,None);info=Extended();info.Basic.Flags=0x100;info.ProcessMemory=2*1024**3
 if not job or not k.SetInformationJobObject(job,9,ctypes.byref(info),ctypes.sizeof(info)) or not k.AssignProcessToJobObject(job,current):raise ctypes.WinError(ctypes.get_last_error())
 return job,{'pid':os.getpid(),'cpu_affinity_mask':one,'priority':'IDLE','Windows_process_commit_limit_bytes':2*1024**3,'wall_time_limit_seconds':180,'Linux_AS_limit_not_applicable':True}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mapping',type=Path,required=True);ap.add_argument('--progress',required=True);ap.add_argument('--terminal',required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--canonical-root',required=True);ap.add_argument('--formal-output-marker',required=True);a=ap.parse_args()
 job,proc=guard();started=time.monotonic();checks=0;errors=[];small=[];large=[];candidates=[];initials=defaultdict(set);runtime=set();paths={}
 if a.output.exists():raise ValueError('Unique audit attempt required')
 a.output.mkdir(parents=True)
 def check(ok,msg):
  nonlocal checks
  checks+=1
  if not ok:errors.append(msg)
  if time.monotonic()-started>180:raise TimeoutError('Audit180s budget exceeded')
 def get(remote):
  if remote not in paths:raise ValueError('Required exact metadata missing from mirror: '+remote)
  return paths[remote]
 mapping=load(a.mapping)
 for q in mapping['files']:
  p=Path(q.get('local_mirror') or q['local']);check(p.stat().st_size==q['bytes'],q['remote']+': bytes');check(sha(p)==q['sha256'],q['remote']+': local mirror SHA');paths[q['remote']]=p
 for remote,p in list(paths.items()):
  if remote.endswith('/SOURCE-TO-NFS-MIRROR.json'):
   proof=load(p)
   for q in proof['files']:
    if q['mirror'] in paths:check(sha(paths[q['mirror']])==q['sha256'],q['mirror']+': original byte binding');paths[q['source']]=paths[q['mirror']]
 progress=load(get(a.progress));terminal=load(get(a.terminal));expected={f'{m}-seed{s:02d}-candidate{c}' for m in MODELS for s in range(10) for c in [0,1]}
 check(terminal['status']=='all60_training_candidates_complete_mirrored_no_TEST','Terminal60 status')
 check({q['key'] for q in progress['completed']}==expected and len(progress['completed'])==60,'Exact60 completed set')
 check(progress['training_candidates_complete_and_mirrored']==60 and not progress['active'] and progress['never_issued']==0 and progress['no_TEST_or_selection_invoked'],'No pending/no TEST')
 canonical=a.canonical_root.rstrip('/')+'/'
 actual={p[len(canonical):].split('/')[0] for p in paths if p.startswith(canonical)}
 check(actual==expected,'Canonical exact60; no pilot included')
 for item in sorted(progress['completed'],key=lambda q:q['key']):
  key=item['key'];mirror=item['mirror'];root=next(q['mirror'].rsplit('/',1)[0] for q in mirror['files'] if q['mirror'].endswith('/result.json'));fp=lambda n:get(root+'/'+n)
  result=load(fp('result.json'));contract=result['contract'];cursor=result['cursor'];start=load(fp('started.json'));argv=start['args'];m,s,c=key.split('-');seed=int(s[4:]);ci=int(c[9:])
  check(result['status']=='succeeded' and result['complete_candidate'] is True and result['test_evaluated'] is False,key+': successful train-only')
  check(contract['seed']==seed and contract['candidate']==ci and contract['learning_rate']==[1e-5,3e-5][ci],key+': seed/LR')
  check(contract['runner_sha256']==WORKERS[m] and contract['manifest_sha256']==COHORT and contract['input_csv_sha256']==LABELS,key+': science/cohort/labels')
  check(contract['device_type']=='cuda' and contract['threads']==1 and contract['settings']['dtype']=='float32' and contract['settings']['tf32'] is False,key+': runtime')
  check(contract['settings']==SETTINGS_BY_MODEL[m] and contract['feature_spec_sha256']==SPECS[m],key+': fixed settings and encoder spec')
  check(model_identifier_matches(m,contract['model_identity']),key+': exact model-specific encoder identifier')
  check(contract['protein_encoder_frozen'] is True and contract['chemical_encoder_frozen'] is False and result['trainable_parameters']==(43259393 if m=='2025' else 31674369),key+': trainability')
  check(contract['split_counts']=={'train':531,'validation':570,'test':685,'external':0},key+': counts')
  check(contract['model_identity']==IDENTITIES[m],key+': exact scientific model identity')
  if m=='2025':check(contract['model_adapter_sha256']=='d935cd85f8009e8c243fb42550c24dbe08f22e55a77fe8efbc6d81f35052fc27' and contract['asset_verifier_sha256']=='900827f3778996544572360606c7303deaedcce4964faeba01b57b97cf109807' and contract['dataset_binding_sha256']=='4425a38dd0dd7f62e6971905b3a1bc72c98652148c62706f5ed584848a437e80',key+': exact2025 safe helper/adapter/dataset')
  check(argv['device']=='cuda' and argv['threads']==1 and start['mode']=='train' and a.formal_output_marker in argv['output'],key+': actual formal args')
  check(hashlib.sha256(json.dumps(contract,sort_keys=True).encode()).hexdigest()==result['fingerprint'],key+': fingerprint')
  check(load(fp('contract.json'))==contract,key+': contract sidecar')
  runtime.add((contract['torch'],contract['numpy'],contract['python'],contract['device_type'],contract['threads']));initials[(m,seed)].add(result['initial_parameter_sha256'])
  manifest=get(argv['manifest']);check(sha(manifest)==COHORT,key+': actual manifest bytes');view=next(v for v in load(manifest)['views'] if v['id']==contract['view_id']);src=view['path']
  if not src.startswith('/'):src=posixpath.join(posixpath.dirname(argv['manifest']),src)
  src=posixpath.normpath(src)
  source=get(src);check(sha(source)==view['sha256']==LABELS,key+': actual raw labels bytes')
  refs=[q for q in rows(source) if q['split']=='validation'];vp=rows(fp('best-validation.csv'))
  check(len(refs)==570 and [q['row_id'] for q in refs]==[q['row_id'] for q in vp],key+': VAL570 IDs/order')
  check([float(q['label']) for q in refs]==[float(q['label']) for q in vp],key+': exact VAL labels')
  mm=metrics([float(q['label']) for q in vp],[float(q['prediction']) for q in vp]);history=cursor['history'];logs=[json.loads(q) for q in fp('epochs.jsonl').read_text().splitlines() if q.strip()]
  check(logs==history,key+': epoch records');best=None;bestepoch=None;stale=0
  for epoch,h in enumerate(history,1):
   check(h['epoch']==epoch and h['global_steps']==epoch*67 and h['training_rows']==531 and h['validation']['n']==570,key+': epoch steps/rows')
   if best is None or h['validation']['mae']<best:best=h['validation']['mae'];bestepoch=epoch;stale=0
   else:stale+=1
  check(cursor['epoch']==len(history) and cursor['global_steps']==len(history)*67 and cursor['next_offset']==0,key+': final cursor')
  check(best==cursor['best_val_mae'] and bestepoch==cursor['best_epoch'] and stale==cursor['stale_epochs'] and 1<=len(history)<=30 and (len(history)==30 or stale==5),key+': early stop/best')
  for metric,value in mm.items():
   stored=history[bestepoch-1]['validation'].get(metric);check(value is None and stored is None or value is not None and stored is not None and abs(value-stored)<=5e-12,key+': VAL '+metric)
  events=[json.loads(q) for q in fp('checkpoint-events.jsonl').read_text().splitlines() if q.strip()]
  check([q for q in events if q['kind']=='best'][-1]['sha256']==result['best_model_sha256'],key+': best event')
  check(events[-1]['kind']=='last_completed' and events[-1]['sha256']==result['last_checkpoint']['sha256'],key+': last event')
  dispatch=load(get(mirror['dispatch_path']));check(dispatch['exit_code']==0 and dispatch['remaining_owned_pids']==[] and dispatch['status']=='succeeded',key+': real terminal')
  check(dispatch['contract_sha256']==mirror['contract_sha256'] and sha(get(dispatch['job_path']))==dispatch['job_sha256'],key+': issued job binding')

  rjob=load(get(dispatch['job_path']));rc=load(get(rjob['contract_path']));rav=rc['argv'];cap=8192 if m=='2025' else 4096
  check(sha(get(rjob['contract_path']))==dispatch['contract_sha256']==rjob['contract_sha256'] and rav==rjob['argv']==rc['execution']['command'],key+': actual resource contract and argv bytes')
  check(rc['allocator_cap_mib']==cap and rc['context_mib']==512 and rc['reserve_mib']==6144 and rc['resources']['cpu_threads']==1 and rc['resources']['memory_limit_bytes']==4*1024**3,key+': actual model budget and CPU/RSS bound')
  check(rc['worker_sha256']==WORKERS[m] and rc['seed']==seed and rc['candidate']==ci and rc['expected_learning_rate']==[1e-5,3e-5][ci] and rc['resume_allowed'] is False and rc['initialization_policy']=='official_pretrained_only_no_training_state',key+': source/seed/LR official init resource declaration')
  check(rav[rav.index('--mode')+1]=='train' and rav[rav.index('--candidate')+1]==str(ci) and rav[rav.index('--seed')+1]==str(seed) and rav[rav.index('--threads')+1]=='1' and rav[rav.index('--device')+1]=='cuda' and not any(x.startswith('--resume') for x in rav),key+': actual fixed training args, no old fit state')
  admissionSHA=rc['source_admission']['sha256'];allowedAdmissions={'e7a8da89a30aef90e541fb1d0af03db37e459e2405ee86d1153f37234b6adb45':'bc05baf199a9ca453042b905222ad51b4067ba19c8ec39ab73eb140ac73977c2','6024a60bba6ffbfbb272757145e3c5a7dffa1582044b230d7f95174ef4f11c81':'40eb02add0c4302b30f7f3aedbab5f61ab69ffdbe8b158a9303f38834721ce91','ce515d3394e0f209387bf0b7bef20f83ce654e5debd54167f6166d0772342823':'9dc4e35249a53021b77779126a792aeda4049afb655af402c77a3a2f63829c5d'}
  check(admissionSHA in allowedAdmissions and rc['cost_review']['sha256']=='5e7ee6ee6418779e125be50c7b55fef305a081f7bcc38a89310eb7f8bc034058',key+': approved controller revision and same actualcost GO')
  sourceM=allowedAdmissions.get(admissionSHA);check(any(q['path'].endswith('/SOURCE-MANIFEST.json') and q['sha256']==sourceM for q in rc['assets']),key+': resource source-manifest asset binding')
  allocator=load(get(rav[rav.index('--proof')+1]));check(allocator['pid']==dispatch['pid'] and allocator['worker_sha256']==WORKERS[m] and allocator['allocator_cap_bytes']==cap*1024**2 and allocator['CUDA_VISIBLE_DEVICES']==rc['gpu_uuid']==dispatch['gpu_uuid'] and allocator['applied_before_worker_model_import'] is True and allocator['no_allocator_configuration_override'] is True,key+': actual allocator applied before model')
  tr=[json.loads(t) for t in get(rc['run_dir']+'/exec-identity-trace.jsonl').read_text().splitlines() if t.strip()];ex=[t for t in tr if t['event']=='launch_guard_exact_exec_proven'];check(len(ex)==1 and ex[0]['spawned_pid']==dispatch['pid'] and ex[0]['identity']['uid']==1030 and ex[0]['identity']['argv']==rav and ex[0]['identity']['starttime_ticks']==dispatch['process_starttime_ticks'],key+': exact kernel scientist PID/birth/argv')
  if key=='mlm-seed00-candidate1':
   lineage=rc.get('resource_attempt_lineage') or {};check(lineage.get('kind')=='fresh_resource_attempt_not_training_resume' and lineage.get('previous_claim',{}).get('sha256')=='34f9a38c6e7a86bd9989fac8853e67301b2d5ab22180540a4135f27a96c4a94e' and lineage.get('previous_dispatch',{}).get('sha256')=='5b5598742ba534fcf4771f48abd711a95d24ff79cf18579702c6090a74591721',key+': exact reviewed0spawn immutable lineage')

  check(mirror['all_bytes_verified'] and mirror['scientific_manifests_unmodified'],key+': production mirror proof')
  checkpoint_proofs={Path(q['mirror']).name:q for q in mirror['files']}
  check(checkpoint_proofs['best.pt']['sha256']==result['best_model_sha256'] and checkpoint_proofs['last.pt']['sha256']==result['last_checkpoint']['sha256'],key+': checkpoint receipt identities')
  for q in mirror['files']:
   if q['bytes']<=1024**2:
    p=get(q['mirror']);name=Path(q['mirror']).name;check(p.stat().st_size==q['bytes'] and sha(p)==q['sha256'],key+': independent small file '+name);small.append({'candidate':key,'file':name,'sha256':q['sha256'],'locally_hashed':True,'remote_source_independently_reread':False})
   else:large.append({'candidate':key,'file':Path(q['mirror']).name,'bytes':q['bytes'],'production_sha256':q['sha256'],'independently_full_hashed':False})
  candidates.append({'key':key,'model':m,'seed':seed,'candidate':ci,'epochs':len(history),'global_steps':cursor['global_steps'],'best_epoch':bestepoch,'stale':stale,'validation_metrics':mm,'initial_sha':result['initial_parameter_sha256'],'directory':root,'candidate_result_sha256':sha(fp('result.json')),'best_validation_sha256':sha(fp('best-validation.csv')),'mirror_marker_sha256':sha(fp('SOURCE-TO-NFS-MIRROR.json')),'best_model_original_path':result['best_model_path'],'best_validation_original_path':result['validation_path'],'best_model_nfs_path':root+'/best.pt','best_model_production_sha256':result['best_model_sha256'],'best_model_bytes':checkpoint_proofs['best.pt']['bytes'],'scientific_fingerprint':result['fingerprint'],'model_identity':contract['model_identity'],'feature_spec_sha256':contract['feature_spec_sha256'],'worker_sha256':WORKERS[m],'settings':contract['settings'],'source_admission_sha256':admissionSHA,'resource_contract_sha256':dispatch['contract_sha256'],'actual_scientific_pid':dispatch['pid'],'actual_scientific_birth':dispatch['process_starttime_ticks'],'actual_GPU_UUID':dispatch['gpu_uuid'],'allocator_cap_GiB':cap/1024,'no_TEST':result['test_evaluated'] is False})
 check(len(initials)==30 and all(len(v)==1 for v in initials.values()),'TwoLR same initialization30groups')
 check(all(len({next(iter(v)) for (model,s),v in initials.items() if model==m})==10 for m in MODELS),'Ten distinct seeds per encoder')
 check(len(runtime)==1,'Uniform actual runtime')
 report={'schema':'chemical-expanded-v3.independent-training60-local.v1','at_utc':datetime.now(timezone.utc).isoformat(),'status':'passed' if not errors else 'failed','checks':checks,'errors':errors,'complete_mirrored':len(candidates),'no_TEST':progress['no_TEST_or_selection_invoked'] and all(q['no_TEST'] for q in candidates),'manifest_sha256':COHORT,'input_csv_sha256':LABELS,'split_counts':{'train':531,'validation':570,'test':685,'external':0},'parent_global_manifest_sha256':'971a1feaafeae45e0e4f29092b80405419d8d47100b0a3e5e936c82ecc0e44c0','canonical_root':a.canonical_root,'exact_candidate_count':len(candidates),'exact_encoder_seed_pairs':len(initials),'runtime_set':[list(q) for q in runtime],'small_files':small,'large_files':large,'candidates':candidates,'mapping_sha256':sha(a.mapping),'independently_hashed_map_files':len(mapping['files']),'progress_sha256':sha(get(a.progress)),'terminal_sha256':sha(get(a.terminal)),'process':proc,'seconds':time.monotonic()-started,'new_nn_forwards':0,'new_fits':0,'weights_deserialized':0,'hash_boundary':'Local small files independently hashed against production and mirror-map receipts. Remote source bytes and large checkpoints are not independently reread or deserialized in this audit.'}
 p=a.output/'TRAINING-INDEPENDENT-AUDIT.actual.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'status':report['status'],'checks':checks,'errors':errors,'report':str(p),'sha256':sha(p),'seconds':report['seconds']}));return bool(errors)

if __name__=='__main__':raise SystemExit(main())
