from pathlib import Path
import json,hashlib,gzip,io,re,tarfile,subprocess
R=Path('.');O=R/'publication/native-GPU-cost-status-public-v5'
def sha(b):return hashlib.sha256(b).hexdigest()
def js(n,j):p=O/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
U=R/'reports/uniair-combined-observed-cost-terminal-independent-v1/independent-audit.json';P=R/'reports/pepinter-stock-CPUAdam8-cost-terminal-audit-v1/independent-audit.json'
assert sha(U.read_bytes())=='21951f409e682fc05332cc9b1865e025bf16ae4c1a9c63b37bcffb372f2e2fcc';assert sha(P.read_bytes())=='96dfa206357846f791709b7be7f288325e62faf94cf396dcfa6758ee77f277ed'
u=json.loads(U.read_text(encoding='utf-8'));p=json.loads(P.read_text(encoding='utf-8'));maps=[];checks=0
# Explicit summaries; do not publish member process tables or all author-source paths.
us={k:u[k] for k in ['schema','decision','terminal','resource','activation','progress','old_unknown_attempt','not_done']}
us['terminal']={k:v for k,v in us['terminal'].items() if k not in ['remaining_owned_pids','strict_leases']}
us['residency']={k:v for k,v in u['residency'].items() if k!='boundary_sequence'}
us['actual']={k:u['actual'][k] for k in ['contract_sha256','canonical_valid','exec_exact_trace_three_events','exec_exact_argv_birth_pgid_sid_cwd_match','descriptor_sha256','worker_sha256','helpers_and_resource_sources']}
us['source_archive']={k:u['archive'][k] for k in ['bytes','sha256','manifest_sha256','members_verified']};us['source_audit_sha256']=sha(U.read_bytes())
us['actual']['helpers_and_resource_sources']={re.sub(r'_node[0-9]+_', '_<HOST>_', k):v for k,v in us['actual']['helpers_and_resource_sources'].items()}
js('evidence/uniair-observed-failure-summary.json',us);js('evidence/pepinter-CPUAdam-only-failure-audit.json',p)
def numbercheck(a,b):
 global checks
 if isinstance(b,dict):
  for k,v in b.items():numbercheck(a[k],v)
 elif isinstance(b,list):
  assert len(a)==len(b)
  for x,y in zip(a,b):numbercheck(x,y)
 elif isinstance(b,(int,float)) and not isinstance(b,bool):assert type(a)==type(b) and a==b;checks+=1
for k in ['terminal','resource','activation','progress','residency']:numbercheck(u[k],us[k])
numbercheck(p,p)
for origin,out,operation in [(U,'evidence/uniair-observed-failure-summary.json','explicit scientific sections selected, identity/process/source-table excluded'),(P,'evidence/pepinter-CPUAdam-only-failure-audit.json','byte-value JSON copy; no identity fields present')]:maps.append({'source_ref':'record-ref:'+origin.as_posix(),'source_sha256':sha(origin.read_bytes()),'public_file':out,'public_sha256':sha((O/out).read_bytes()),'operation':operation})
replacement_counts={'private_paths':0,'process_ids':0,'GPU_identifiers':0}
def pathref(m):
 replacement_counts['private_paths']+=1;s=m.group(0);mark='peptide-four-task-benchmark-20261022/'
 if mark in s:return 'source-ref:'+s.split(mark,1)[1]
 if '/site-packages/' in s:return 'package-ref:'+s.split('/site-packages/',1)[1]
 if '/src/' in s:return 'author-source-ref:'+s.split('/src/',1)[1]
 return 'source-ref:'+s.rsplit('/',1)[-1]
def redact(s):
 s=re.sub(r'(?:/data1?/|[A-Z]:[\\/])[^\s\"\x27<>]+',pathref,s)
 s,n=re.subn(r'\bProcess\s+\d+\b','Process <PROCESS_ID>',s);replacement_counts['process_ids']+=n
 s,n=re.subn(r'\bGPU\s+\d+\b','GPU <DEVICE>',s);replacement_counts['GPU_identifiers']+=n
 s,n=re.subn(r'GPU-[0-9a-fA-F-]{16,}','<GPU_UUID>',s);replacement_counts['GPU_identifiers']+=n
 return s
def gz_source(name,raw,source_ref):
 text=raw.decode('utf-8');clean=redact(text);b=clean.encode();f=O/'logs'/name;f.parent.mkdir(exist_ok=True);bio=io.BytesIO()
 with gzip.GzipFile(filename='',fileobj=bio,mode='wb',mtime=0) as q:q.write(b)
 f.write_bytes(bio.getvalue());assert gzip.decompress(f.read_bytes())==b
 maps.append({'source_ref':source_ref,'source_sha256':sha(raw),'source_bytes':len(raw),'public_file':'logs/'+name,'public_sha256':sha(f.read_bytes()),'sanitized_plaintext_sha256':sha(b),'operation':'deterministic gzip; private paths/process/GPU identifiers replaced only','source_lines':len(text.splitlines()),'public_lines':len(clean.splitlines())});assert len(text.splitlines())==len(clean.splitlines())
 return clean
archive=R/'resources/continuation-20261023/combined-observed-cost-failure-preservation-v1/smallproof.tar.gz';assert sha(archive.read_bytes())=='d2ba0edbcb29d4c2de82b13b829fe15c663f50db6409001a63b61fc2c2a40c72'
with tarfile.open(archive,'r:gz') as t:
 members={m.name:m for m in t.getmembers()};assert len([m for m in members.values() if m.isfile() and m.name.startswith('raw/')])==36
 suffix='priority-dispatch/uniair_native_MoFPE_combined_observed_exec_cost_gate_v1--20261023T225528/'
 for name in ['stderr.log','stdout.log']:
  m=next(m for k,m in members.items() if suffix+name in k);raw=t.extractfile(m).read();gz_source('uniair-'+name+'.gz',raw,'archive-sha256:'+sha(archive.read_bytes())+'#'+m.name)
 for name in ['dispatch.json']:
  m=next(m for k,m in members.items() if suffix+name in k);raw=t.extractfile(m).read();j=json.loads(raw)
  keys=['status','started_at','finished_at','exit_code','stop_reason','peak_owned_gpu_mib','peak_owned_rss_bytes','minimum_observed_actual_free_mib','stdout_sha256','stderr_sha256','contract_sha256']
  picked={k:j[k] for k in keys if k in j};numbercheck(j,picked);js('evidence/uniair-resource-dispatch-summary.json',picked);maps.append({'source_ref':'archive-sha256:'+sha(archive.read_bytes())+'#'+m.name,'source_sha256':sha(raw),'public_file':'evidence/uniair-resource-dispatch-summary.json','operation':'scientific resource allowlist only; no process lists, PID, UUID, command or host'})
 for short in ['activation-transfer-receipt.json','residency-transfer-receipt.json','combined-state.json']:
  m=next(m for k,m in members.items() if k.endswith('/'+short));raw=t.extractfile(m).read();js('evidence/'+short+'.source-attestation.json',{'source_sha256':sha(raw),'source_bytes':len(raw),'source_archive_sha256':sha(archive.read_bytes()),'publish_scope':'counts and invariant results in independent summary; raw trace not recursively redistributed'})
pepbase=P.parent
for name in ['stderr.log','stdout.log']:gz_source('pepinter-'+name+'.gz',(pepbase/'raw-dispatch'/name).read_bytes(),'record-ref:'+(pepbase/'raw-dispatch'/name).as_posix())
phase=pepbase/'raw-science/phase-timings.jsonl';lines=[json.loads(x) for x in phase.read_text(encoding='utf-8').splitlines() if x]
clean=[]
for x in lines:
 y=dict(x)
 if 'error' in y:y['error']=redact(y['error'])
 numbercheck(x,y);clean.append(y)
f=O/'evidence/pepinter-phase-timings.jsonl';f.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in clean),encoding='utf-8');maps.append({'source_ref':'record-ref:'+phase.as_posix(),'source_sha256':sha(phase.read_bytes()),'public_file':f.relative_to(O).as_posix(),'operation':'JSON values preserved; error text identity replacement only'})
mem=pepbase/'raw-science/memory-gates.jsonl';samples=[json.loads(x) for x in mem.read_text(encoding='utf-8').splitlines() if x];summary={'sample_count':len(samples),'minimum_MemAvailable_bytes':min(x['MemAvailable_bytes'] for x in samples),'all_samples_passed':all(x['passed'] for x in samples),'registered_reservation_records_not_published':True,'source_sha256':sha(mem.read_bytes())};assert summary['sample_count']==p['memory_samples'] and summary['minimum_MemAvailable_bytes']==p['minimum_OS_available_bytes'];checks+=2;js('evidence/pepinter-RAM-sampling-summary.json',summary)
pa=R/'resources/continuation-20261023/pepinter-CPU1-Adam-cost-failure-preservation-v1/smallproof.tar.gz';assert sha(pa.read_bytes())=='5d2a77d4321eb82e984ca97542e4587e71f1ee82d612cd1c6fbf26e1529703cf'
js('EVIDENCE-INDEX.json',{'uniair_audit_sha256':sha(U.read_bytes()),'uniair_raw_bundle_sha256':sha(archive.read_bytes()),'uniair_raw_member_count':36,'pepinter_audit_sha256':sha(P.read_bytes()),'pepinter_raw_bundle_sha256':sha(pa.read_bytes()),'pepinter_raw_member_count':71,'bundles_not_redistributed':True,'own_scientific_sources':maps})
js('VALIDATION.json',{'status':'passed','retained_JSON_scientific_number_checks':checks,'scientific_log_gzip_roundtrips':4,'identity_replacements':replacement_counts,'NN_model_weight_GPU_execution':0,'raw_dataset_sequence_or_labels_included':False,'raw_resource_process_tables_included':False,'original_weights_included':False,'original_raw_bundles_copied_or_repacked':False,'new_training_or_model_success_claims':False})
print('payload scientific numeric checks',checks,'files',len(list(O.rglob('*'))))
