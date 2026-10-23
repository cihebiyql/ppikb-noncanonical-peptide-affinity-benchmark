"""CPU-only immutable cached-input fingerprints. No encoder/model construction, forward, fit or split edit."""
import argparse,collections,datetime as dt,gc,gzip,hashlib,importlib.metadata,json,os,pickle,socket,sys,threading,time
from pathlib import Path
P=argparse.ArgumentParser();P.add_argument('--mode',choices=['native','manifest24'],default='native');P.add_argument('--timeout-seconds',type=int,default=900);P.add_argument('--rss-gib',type=int,default=4);P.add_argument('--min-os-available-gib',type=int,default=3);P.add_argument('--uid-rss-limit-gib',type=int,default=0);P.add_argument('--methods',nargs='*');A=P.parse_args()
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
import numpy as np,torch,torch_geometric,psutil
torch.set_num_threads(1);torch.set_num_interop_threads(1)
H=Path(__file__).resolve().parent;R=H.parents[1];STAMP=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ');OUT=H/f'effective-input-audit-{socket.gethostname()}-{A.mode}-{STAMP}';OUT.mkdir();START=time.monotonic();FINISHED=threading.Event()
SOURCE_SHA=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
METHODS=A.methods or ['GraphDTA-GIN','MGraphDTA','DGDTA-CL','DeepNC-GEN','GS-DTA'];VIEWS=['ppikb_kd_source_cold_scope_v2','ppikb_kd_target_cold_scope_v2','ppikb_effect_metadata_silver_source_cold']
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,x):Path(p).write_text(json.dumps(x,indent=2),encoding='utf-8')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024**2),b''):h.update(b)
 return h.hexdigest()
def shatext(s):return hashlib.sha256(str(s).encode()).hexdigest()
def guard():
 while not FINISHED.wait(.5):
  rss=psutil.Process().memory_info().rss;available=psutil.virtual_memory().available
  uidrss=0
  if A.uid_rss_limit_gib:
   for p in psutil.process_iter(['uids','memory_info']):
    try:
     if p.info['uids'].real==os.getuid():uidrss+=p.info['memory_info'].rss
    except (psutil.Error,KeyError,TypeError):pass
  if rss>A.rss_gib*1024**3 or available<A.min_os_available_gib*1024**3 or (A.uid_rss_limit_gib and uidrss>A.uid_rss_limit_gib*1024**3) or time.monotonic()-START>A.timeout_seconds:
   write(OUT/'bounded-stop.json',{'rss_bytes':rss,'available_bytes':available,'elapsed_seconds':time.monotonic()-START,'CPU_only':True,'fit_forward_encoder_calls':0});os._exit(143)
threading.Thread(target=guard,daemon=True).start()
def array(x,dtype=None,flatten=False):
 if torch.is_tensor(x):x=x.detach().cpu().numpy()
 x=np.asarray(x,dtype=dtype)
 return np.ascontiguousarray(x.reshape(-1) if flatten else x)
def tensorhash(parts):
 h=hashlib.sha256()
 for name,value in parts:
  h.update(name.encode()+b'\0')
  if value is None:h.update(b'ABSENT\0');continue
  h.update(value.dtype.str.encode()+b'\0'+str(value.shape).encode()+b'\0');h.update(value.tobytes(order='C'))
 return h.hexdigest()
def fingerprint(item):
 if 'graph' in item:
  g=item['graph'];x=array(g.x,np.float32);edge=array(g.edge_index,np.int64);target=array(g.target,np.int64,True);attr=getattr(g,'edge_attr',None);attr=array(attr) if attr is not None else None
 else:x=array(item['x'],np.float32);edge=array(item['edge_index'],np.int64);target=array(item['target'],np.int64,True);attr=None
 assert x.ndim==2 and edge.ndim==2 and edge.shape[0]==2 and np.isfinite(x).all()
 assert not edge.size or edge.min()>=0 and edge.max()<len(x)
 # Every frozen author forward uses x, edge_index and target. MGraph stores edge_attr but never consumes it.
 graph=tensorhash([('x',x),('edge_index',edge)]);targethash=tensorhash([('target',target)])
 effective=shatext(graph+'|'+targethash);container=tensorhash([('x',x),('edge_index',edge),('edge_attr',attr),('target',target)])
 return {'graph_hash':graph,'target_tokens_hash':targethash,'effective_pair_hash':effective,'graph_container_hash_including_unused_edge_attr':container,'target_token_count':len(target),'atoms':len(x),'directed_edges':edge.shape[1]}
def broad(s):return {'standard20_control':'standard','standard':'standard','PTM':'PTM','synthetic_D_backbone':'NC','other_NC':'NC','synthetic_and_PTM':'NC+PTM'}.get(s,'unknown:'+s)
def entities(item,row,effect):
 if effect:
  a=fingerprint(item[0]);b=fingerprint(item[1]);assert a['target_tokens_hash']==b['target_tokens_hash'];effective=shatext(a['effective_pair_hash']+'->'+b['effective_pair_hash']);unordered=shatext('|'.join(sorted([a['effective_pair_hash'],b['effective_pair_hash']])));graph=shatext(a['graph_hash']+'->'+b['graph_hash']);target=a['target_tokens_hash'];fullchem=shatext(row['smiles_wt']+'->'+row['smiles_mut']);atom=max(a['atoms'],b['atoms']);cap=a['target_token_count'];container=shatext(a['graph_container_hash_including_unused_edge_attr']+'->'+b['graph_container_hash_including_unused_edge_attr']);blind=a['effective_pair_hash']==b['effective_pair_hash']
 else:
  a=fingerprint(item);effective=a['effective_pair_hash'];unordered=effective;graph=a['graph_hash'];target=a['target_tokens_hash'];fullchem=shatext(row['peptide_smiles']);atom=a['atoms'];cap=a['target_token_count'];container=a['graph_container_hash_including_unused_edge_attr'];blind=False
 s=row.get('evaluation_stratum') or row.get('stratum') or 'unknown'
 return {'record_id':row['record_id'],'row_id':row.get('row_id'),'split':row['split'],'stratum':s,'broad_chemical_group':broad(s),'effective_pair_hash':effective,'effect_pair_or_reverse_hash':unordered,'graph_hash':graph,'target_tokens_hash':target,'container_hash_including_unused_edge_attr':container,'recorded_complete_chemistry_hash':fullchem,'complete_target_hash':shatext(row['target_sequence']),'effective_prefix_text_hash':shatext(row['target_sequence'][:cap]),'target_original_length':len(row['target_sequence']),'target_token_count':cap,'target_truncated':len(row['target_sequence'])>cap,'effect_WT_mutant_consumed_inputs_identical':blind,'atoms_max':atom}
runtime={'host':socket.gethostname(),'python':sys.version,'python_path':sys.executable,'torch':torch.__version__,'numpy':np.__version__,'pyg':torch_geometric.__version__,'CUDA_VISIBLE_DEVICES':os.environ['CUDA_VISIBLE_DEVICES'],'model_constructed':False,'encoder_called':False,'auditor_source_path':str(Path(__file__).resolve()),'auditor_source_sha256':SOURCE_SHA}
try:runtime['installed_RDKit_distribution_version']=importlib.metadata.version('rdkit')
except importlib.metadata.PackageNotFoundError:runtime['installed_RDKit_distribution_version']=None
manifest=load(H/'cache-reuse-v3/manifest-node23-with-effect.json') if A.mode=='manifest24' else None
results=[];missing=[]
for view in VIEWS:
 for method in METHODS:
  spec=load(H/'specs'/f'{view}--{method}--formal--seed0.json');effect=spec['task']=='effect';allrows=[];sources=[];parts={}
  for part in ['train','validation','test']:
   ref=spec['paths'][part];input_path=R/ref['path'];assert sha(input_path)==ref['sha256'];rows=[json.loads(x) for x in input_path.read_text(encoding='utf-8').splitlines() if x.strip()];assert len(rows)==ref['n']
   signature=hashlib.sha256(json.dumps({'rows':rows,'task':spec['task'],'method':method,'source_manifest_sha256':spec['source_manifest']['sha256']},sort_keys=True).encode()).hexdigest()
   if manifest and method=='MGraphDTA':entry=manifest['caches'][signature];path=Path(entry['path']);expected=entry['sha256'];origin='readonly fixed RDKit24 manifest numeric cache'
   else:
    path=H/'cache'/(signature+'.pkl');meta=path.with_suffix('.json')
    if not path.exists() or not meta.exists():missing.append({'view':view,'method':method,'part':part,'signature':signature,'reason':'existing cache absent; no new encoder invoked'});continue
    receipt=load(meta);assert receipt['signature']==signature;expected=receipt['sha256'];origin='owned native runtime cache, original byte receipt'
   assert sha(path)==expected
   if psutil.virtual_memory().available<(A.min_os_available_gib+A.rss_gib)*1024**3:raise MemoryError('Metadata cache read deferred to preserve OS RAM')
   with path.open('rb') as f:items=pickle.load(f)
   assert len(items)==len(rows)
   values=[]
   for item,row in zip(items,rows):
    if effect:assert item[0]['record_id']==item[1]['record_id']==row['record_id']
    else:assert item['record_id']==row['record_id']
    values.append(entities(item,row,effect))
   parts[part]=values;allrows+=values;sources.append({'part':part,'path':str(path),'sha256':expected,'signature':signature,'rows':len(values),'origin':origin});del items,rows;gc.collect()
  filename=f'{view}--{method}.jsonl.gz';index=OUT/filename
  with gzip.open(index,'wt',encoding='utf-8') as f:
   for row in allrows:f.write(json.dumps(row)+'\n')
  if len(parts)!=3:results.append({'view':view,'method':method,'complete_partitions':False,'parts_available':list(parts),'input_index':filename,'input_index_sha256':sha(index),'sources':sources});continue
  train={x['effective_pair_hash'] for x in parts['train']};val={x['effective_pair_hash'] for x in parts['validation']};reverse_train={x['effect_pair_or_reverse_hash'] for x in parts['train']}
  targets=collections.defaultdict(set)
  for x in parts['train']:targets[x['target_tokens_hash']].add(x['complete_target_hash'])
  groups=collections.defaultdict(list)
  for x in allrows:groups[x['effective_pair_hash']].append(x)
  duplicate=[]
  for key,group in groups.items():
   if len(group)>1:duplicate.append({'effective_pair_hash':key,'records':[x['record_id'] for x in group],'splits':dict(collections.Counter(x['split'] for x in group)),'strata':dict(collections.Counter(x['stratum'] for x in group)),'broad_chemical_groups':dict(collections.Counter(x['broad_chemical_group'] for x in group)),'recorded_complete_chemistry_count':len({x['recorded_complete_chemistry_hash'] for x in group}),'complete_target_count':len({x['complete_target_hash'] for x in group})})
  masks=[]
  for x in parts['test']:
   masks.append({'record_id':x['record_id'],'effective_pair_seen_train':x['effective_pair_hash'] in train,'effective_pair_seen_train_or_validation':x['effective_pair_hash'] in train|val,'effect_pair_or_reverse_seen_train':x['effect_pair_or_reverse_hash'] in reverse_train,'target_tokens_seen_train':x['target_tokens_hash'] in targets,'different_complete_target_same_tokens_in_train':any(z!=x['complete_target_hash'] for z in targets.get(x['target_tokens_hash'],set())),'target_truncated':x['target_truncated'],'effect_WT_mutant_consumed_inputs_identical':x['effect_WT_mutant_consumed_inputs_identical']})
  masks_path=OUT/(f'{view}--{method}.test-masks.json');write(masks_path,masks);dup_path=OUT/(f'{view}--{method}.duplicate-groups.json');write(dup_path,duplicate)
  results.append({'view':view,'method':method,'complete_partitions':True,'counts':{k:len(v) for k,v in parts.items()},'test_flags':{k:sum(x[k] for x in masks) for k in masks[0] if k!='record_id'},'validation_effective_pair_seen_train':sum(x['effective_pair_hash'] in train for x in parts['validation']),'duplicate_effective_input_groups':len(duplicate),'groups_with_different_recorded_chemistry':sum(x['recorded_complete_chemistry_count']>1 for x in duplicate),'groups_with_different_complete_targets':sum(x['complete_target_count']>1 for x in duplicate),'groups_with_multiple_broad_chemical_types':sum(len(x['broad_chemical_groups'])>1 for x in duplicate),'truncated_counts':{k:sum(x['target_truncated'] for x in v) for k,v in parts.items()},'input_index':filename,'input_index_sha256':sha(index),'test_masks_file':masks_path.name,'test_masks_sha256':sha(masks_path),'duplicate_groups_file':dup_path.name,'duplicate_groups_sha256':sha(dup_path),'sources':sources})
  write(OUT/'progress.json',{'completed_view_method_units':len(results),'missing_cache_parts':len(missing),'elapsed_seconds':time.monotonic()-START})
report={'schema':'fourtask.actual-cached-effective-input-audit.v3','at':STAMP,'runtime':runtime,'mode':A.mode,'broad_chemical_mapping':{'standard20_control':'standard','standard':'standard','PTM':'PTM','synthetic_D_backbone':'NC','other_NC':'NC','synthetic_and_PTM':'NC+PTM'},'model_consumed_fields':['x castfloat32','edge_index castint64','target tokens castint64'],'stored_but_unused_fields':['MGraph edge_attr is hashed separately and excluded from model-consumed key; author forward never reads it'],'results':results,'missing_caches':missing,'scope':'Exact ordered consumed tensor hashes, including dtype/shape/bytes; graph permutation/isomorphism collisions can be additional. Different recorded SMILES hashes are not automatically chemically distinct molecules. No feature/model call, resplit, row deletion, refit or primary-metric change.','elapsed_seconds':time.monotonic()-START}
write(OUT/'complete.json',report);FINISHED.set();print(json.dumps({'directory':str(OUT),'complete_view_method_units':sum(x['complete_partitions'] for x in results),'missing_cache_parts':len(missing),'elapsed_seconds':time.monotonic()-START}))
