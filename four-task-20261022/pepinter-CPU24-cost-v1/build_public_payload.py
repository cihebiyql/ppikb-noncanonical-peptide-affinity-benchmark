from pathlib import Path
import json,hashlib,gzip,io,shutil,ast,re,subprocess
R=Path(__file__).resolve().parents[2]; O=Path(__file__).resolve().parent
B=R/'methods/interaction/continuation-20261023/native-full-classification-CPU24-prepare-v1'
def sha(b):return hashlib.sha256(b).hexdigest()
def put(n,b):
 p=O/n;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb') as f:f.write(b)
def js(n,j):put(n,(json.dumps(j,ensure_ascii=False,indent=2)+'\n').encode())
source_map=[]; omitted=[]; numeric_checks=0
banned={'model_PID','model_PGID','runtime_CPU_affinity','affinity','pid','pgid','cpu_affinity','command','residual_group_pids_before_cleanup'}
def scrub(v,trail=''):
 global numeric_checks
 if isinstance(v,dict):
  o={}
  for k,x in v.items():
   t=trail+'/'+k
   if k in banned:omitted.append({'json_pointer':t,'reason':'process or assigned-CPU identity, not scientific measurement'});continue
   o[k]=scrub(x,t)
  return o
 if isinstance(v,list):return [scrub(x,trail+'/'+str(i)) for i,x in enumerate(v)]
 if isinstance(v,str) and (v.startswith('/data/') or re.match(r'^[A-Z]:[\\/]',v)):
  q=v.replace('\\','/'); marker='peptide-four-task-benchmark-20261022/'
  return 'record-ref:'+q.split(marker,1)[-1] if marker in q else 'asset-ref:'+Path(q).name
 if isinstance(v,(int,float)) and not isinstance(v,bool):numeric_checks+=1
 return v

def convert(src,dst,expected=None):
 p=B/src;raw=p.read_bytes();s=sha(raw)
 if expected:assert s==expected,(src,s)
 j=json.loads(raw);out=scrub(j);js(dst,out)
 source_map.append({'source_ref':'record-ref:'+str(p.relative_to(R)).replace('\\','/'),'source_sha256':s,'public_file':dst,'public_sha256':sha((O/dst).read_bytes()),'operation':'identity-field omission and absolute-path-to-record-ref only'})
 return j
summary=convert('v5result/summary.json','evidence/summary.json','05ddbba1d85c37450acbbbefccacaa267457d7c380b3bda23ddcc5c4bf5fc440')
audit=convert('CPU24-v5-cost.independent-audit.json','evidence/independent-audit.json','253b22f0f9e6406a8e88b8186d04775dbe15964eff3023033c9a411ecabc22bc')
convert('v5result/frozen-config.json','evidence/frozen-config.json')
receipt=convert('v5actual/dispatch/process-receipt.json','evidence/process-receipt.json')
for src,dst in [('CPU24-v5-cost.phase-times.csv','evidence/phase-times.csv'),('v5result/phase-timings.jsonl','evidence/phase-timings.jsonl')]:
 p=B/src;b=p.read_bytes();put(dst,b);source_map.append({'source_ref':'record-ref:'+str(p.relative_to(R)).replace('\\','/'),'source_sha256':sha(b),'public_file':dst,'public_sha256':sha(b),'operation':'byte-identical'})
for src,dst in [('methods/interaction/pepinter_full_classification_CPU24_cost_v1.py','code/pepinter_full_classification_CPU24_cost_v1.py'),('methods/interaction/continuation-20261023/native-full-classification-CPU24-prepare-v1/cpu24_observe.py','code/continuation-20261023/native-full-classification-CPU24-prepare-v1/cpu24_observe.py')]:
 p=R/src;b=p.read_bytes();put(dst,b);assert ast.dump(ast.parse(b))==ast.dump(ast.parse((O/dst).read_bytes()))
 source_map.append({'source_ref':'record-ref:'+src,'source_sha256':sha(b),'public_file':dst,'public_sha256':sha(b),'operation':'byte-identical self-authored code; full AST unchanged'})
assert source_map[-2]['source_sha256']=='1990c38c875fedb716a4e0d5ecfac96c8c03ebcfa2d70c6c2235133ff6bc37ec'
for name in ['stdout.log','stderr.log']:
 p=B/'v5actual/dispatch'/name;b=p.read_bytes();assert b==b''
 buf=io.BytesIO()
 with gzip.GzipFile(filename='',fileobj=buf,mode='wb',mtime=0) as f:f.write(b)
 n='logs/'+name+'.gz';put(n,buf.getvalue());assert gzip.decompress((O/n).read_bytes())==b
 source_map.append({'source_ref':'record-ref:'+str(p.relative_to(R)).replace('\\','/'),'source_sha256':sha(b),'source_bytes':0,'public_file':n,'public_sha256':sha(buf.getvalue()),'operation':'deterministic gzip of original empty log; no contents removed'})
e=B/'CPU24-v5-cost.E-local-SHA-audit.json';er=json.loads(e.read_text());assert sha(e.read_bytes())=='a1466675e567b22f469bc9ddcdede7cdbb211741538b5a6d214b77d56b61d385'
keys=['at','all_files_physically_local_on_E_and_rehashed','file_count','total_bytes','official7GB_initializer_not_duplicated','new_trained_full_checkpoint_count','gate_did_not_save_fullweights_or_head_snapshot','new_fit_or_forward']
js('evidence/local-preservation-attestation.json',{'source_receipt_sha256':sha(e.read_bytes()),'published_allowlisted_fields':{k:er[k] for k in keys},'private_storage_locations_and_volume_policy_omitted':True})
js('SOURCE-MAPPING.json',{'schema':'pepinter.cpu24.public-source-map.v1','files':source_map,'omitted_identity_fields':omitted,'other_excluded_assets':['author NN/vendor modules','TRAIN sequences, labels and row IDs','published initializer tensors','raw resource process tables','private volume policy','full training checkpoint (not produced)','head before/after weight snapshots (not produced)']})
head=subprocess.check_output(['git','-C',str(R/'publication/github-checkout/four-task-20261022'),'rev-parse','HEAD'],text=True).strip()
assert head=='8e818dc09ff1f9b7e83a3d46f2b41819e7c46cb2'
js('PUBLIC-CONTEXT.json',{'read_only_public_Git_HEAD':head,'LATEST_sha256':sha((R/'publication/github-checkout/four-task-20261022/LATEST.md').read_bytes()),'repository':'https://github.com/cihebiyql/ppikb-noncanonical-peptide-affinity-benchmark','existing_code_dependencies':'native-code-v1/methods/interaction/common.py; remaining loader/pepinter_extract and author implementation require original separately audited assets; no substitute implementation included','self_authored_worker_previously_in_native_code_v1':False,'publication_status':'prepared_for_root_review_not_published'})
# Exact scientific-number preservation for every retained JSON pointer, no model imports.
def verify(a,b,path=''):
 global checked
 if isinstance(b,dict):
  for k,v in b.items():verify(a[k],v,path+'/'+k)
 elif isinstance(b,list):
  assert len(a)==len(b)
  for i,v in enumerate(b):verify(a[i],v,path+'/'+str(i))
 elif isinstance(b,(int,float)) and not isinstance(b,bool):assert type(a)==type(b) and a==b,(path,a,b);checked+=1
checked=0
for x in source_map:
 if x['public_file'].endswith('.json'):
  src=R/x['source_ref'].removeprefix('record-ref:');verify(json.loads(src.read_bytes()),json.loads((O/x['public_file']).read_bytes()))
assert summary['parameters']==summary['trainable_parameters']==576293761
assert len(summary['step_records'])==2 and all(x['parameters_with_gradient']==576293761 for x in summary['step_records'])
assert summary['new_optimizer_steps']==2 and summary['validation_test_rows']==summary['completed_baseline_seeds']==0
assert summary['encoder_update_probe']>0 and audit['head_numeric_before_after_saved'] is False
assert receipt['exit_code']==0 and receipt['worker_pid_absent'] and receipt['residual_group_pids_before_cleanup']==[]
js('VALIDATION.json',{'status':'passed','new_model_imports':0,'new_fit_or_forward':0,'new_GPU':0,'retained_scientific_numeric_values_exactly_checked':checked,'copied_code_ASTs_exact':2,'raw_scientific_logs':2,'raw_log_bytes':0,'gzip_roundtrips_exact':2,'original_audit_sha256':sha((B/'CPU24-v5-cost.independent-audit.json').read_bytes()),'original_E_receipt_sha256':sha(e.read_bytes()),'raw_process_tables_not_included':True,'published_original_input_sequences_or_labels':False,'trained_weights_produced_or_included':False,'head_weight_change_directly_measured':False,'completed_formal_baseline_seeds':0})
print(json.dumps({'created':len(source_map),'numeric_checks':checked,'head':head}))
