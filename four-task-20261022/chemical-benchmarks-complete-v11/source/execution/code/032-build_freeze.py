"""Metadata-only cross-task firewall; preserve legacy heldout anchors and raw labels."""
from __future__ import annotations
import csv, hashlib, json, re, time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
OLD=ROOT.parent/'peptide-binding-nc-benchmark-20261021/data-protocol'
VERSION='global-freeze-20261024-v1'

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def hs(x):return hashlib.sha256(x.encode()).hexdigest()
def js(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def readcsv(p):
 with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def readjl(p):
 with Path(p).open(encoding='utf-8-sig') as f:
  for line in f:
   if line.strip():yield json.loads(line)
def writecsv(p,rows,fields=None):
 fields=fields or list(dict.fromkeys(k for r in rows for k in r))
 with Path(p).open('w',encoding='utf8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
class UF:
 def __init__(self,n):self.p=list(range(n))
 def find(self,a):
  while self.p[a]!=a:self.p[a]=self.p[self.p[a]];a=self.p[a]
  return a
 def union(self,a,b):
  a,b=self.find(a),self.find(b)
  if a!=b:self.p[max(a,b)]=min(a,b)
def source_aliases(row,old=None):
 result=set()
 for value in (old or []):
  v=value.lower().strip()
  tail=v.split(':',1)[-1]
  if v.startswith(('doi:','pmid:','title:')) and len(tail)>=3 and tail not in ('unknown','none','null','nan','notreported','n/a'):result.add(v)
 for field in ('study_id','source_ITC_DOI'):
  v=str(row.get(field) or '').lower().strip()
  v=re.sub(r'^https?://(?:dx\.)?doi\.org/','',v)
  if v.startswith('doi:'):v=v[4:]
  if re.match(r'^10\.\d{4,9}/\S+$',v):result.add('doi:'+v)
 return result
def pdbs(value):return sorted(set(x.lower() for x in re.findall(r'(?<![A-Za-z0-9])([0-9][A-Za-z0-9]{3})(?![A-Za-z0-9])',str(value))))
def lst(x):
 if not x:return []
 try:v=json.loads(x);return v if isinstance(v,list) else [v]
 except (ValueError,TypeError):return [x]

def prepare():
 inputs={}
 def load(rel):
  p=ROOT/rel;inputs[str(p)]=sha(p);return readcsv(p)
 aliases={r['record_id']:r['source_aliases'] for r in readjl(OLD/'label-free-study-aliases.jsonl')}
 meta={r['record_id']:r for r in readjl(ROOT/'data/ppikb_preserved_input_metadata.jsonl')}
 kdsource=load('data/ppikb_kd_source_cold_scope_v2.csv');kdtarget=load('data/ppikb_kd_target_cold_scope_v2.csv')
 sourceby={r['row_id']:r for r in kdsource};targetby={r['row_id']:r for r in kdtarget}
 rawp=ROOT.parent/'peptide-binding-expanded-corpus-20261021/resources/PPIKB_all_endpoints/normalized-observations.jsonl'
 rawpdb={r['record_id']:r.get('PDB') for r in readjl(rawp) if r['record_id'] in sourceby}
 nodes=[]
 def node(dataset,row,external=False,raw=None):
  q=dict(row);rid=q.get('row_id') or q.get('record_id');peptide=q.get('peptide_sequence') or q.get('Peptide Sequence') or '';target=q.get('target_sequence') or q.get('Protein Sequence') or ''
  a=source_aliases(q,aliases.get(rid,[]));m=meta.get(rid,{})
  toks={f'obs:{rid}'}
  for alias in a:toks.add('source:'+alias)
  if peptide:toks.add('peptide_raw:'+hs(peptide))
  if peptide and target:toks.add('sequence_pair:'+hs(peptide+'\n'+target))
  for name,val in [('chemical_iso',q.get('chemical_entity_id') or m.get('chemical_entity_id')),('chemical_achiral',m.get('achiral_entity_id'))]:
   if val:toks.add(name+':'+str(val))
  for value in (q.get('pdb_id'),q.get('pdb_id'.upper()),q.get('PDB ID'),rawpdb.get(rid)):
   for pid in pdbs(value):toks.add('pdb:'+pid)
  for k in ('reference_row_id','variant_row_id'):
   if q.get(k):toks.add('obs:'+q[k])
  for dep in lst(q.get('source_row_ids')):toks.add('obs:'+str(dep))
  for k in ('peptide_wt_sequence','peptide_mut_sequence'):
   if q.get(k):toks.add('peptide_raw:'+hs(q[k]))
  if dataset=='ppikb_contact':
   for study in lst(q.get('source_studies')):
    for alias in source_aliases({'study_id':str(study)}):toks.add('source:'+alias);a.add(alias)
   for dep in lst(q.get('source_row_ids')):
    for alias in source_aliases({},aliases.get(str(dep),[])):toks.add('source:'+alias);a.add(alias)
  split=q.get('split','external_test' if external else 'unknown')
  nodes.append({'dataset':dataset,'row_id':rid,'legacy_split':split,'external':external,'source_known':bool(a),'source_aliases':sorted(a),'tokens':toks,'target':target,'peptide':peptide,'raw':raw or q,'chemical_flag':bool(m.get('residue_class_graph_discordance'))})
 for q in kdsource:node('ppikb_kd',q)
 for dataset,rel in [('pepinter','data/pepinter_classification_target_cold.csv'),('pepaff','data/pepaff_mixed_target_cold.csv'),('ppikb_effect','data/ppikb_effect_metadata_silver_source_cold.csv')]:
  for q in load(rel):node(dataset,q)
 contacts=load('data/ppikb_contact_experimental_64complex_dependency_cold_v2.csv')
 seen=set()
 for q in contacts:
  if q['structure_id'] in seen:continue
  seen.add(q['structure_id']);node('ppikb_contact',dict(q,row_id='contact:'+q['structure_id']))
 for dataset,rel in [('profaff_fp','data/profaff_pKd_domain_backbone_all162_external.csv'),('profaff_effect','data/profaff_PTM_delta_pKd_external.csv'),('profaff_holdup','data/profaff-expansion-20261023/holdup-standard-core-no-FP-no-PPIKB-overlap-external.csv')]:
  for q in load(rel):node(dataset,q,True)
 pepbi=load('data/pepbi-external-audit-20261023/all329-row-audit.csv')
 for q in pepbi:node('pepbi_background',q,True)
 for q in load('data/pepbi-external-audit-20261023/conditional-sequence-external-candidates.csv'):node('pepbi_candidate',q,True)
 her2={r['row_id']:r for r in load('methods/uniair/continuation-20261023/local-training-protocol-v1/native-training-input.csv')}
 for q in load('data/uniair_her2_effect_local_variant_diagnostic.csv'):
  q=dict(q);q['split']=her2[q['row_id']]['split'];q['pdb_id']=her2[q['row_id']]['pdb_id'];q['strict_variant_component_id']=her2[q['row_id']]['variant_component_id'];node('her2',q)
 for p in [OLD/'label-free-study-aliases.jsonl',ROOT/'data/ppikb_preserved_input_metadata.jsonl',rawp,OLD/'target-homology-pairs.jsonl',OLD/'chemical-neighbor-edges.jsonl',ROOT/'publication/github-checkout/four-task-20261022/pepbi-input-erratum-v1/frozen-panel-rules.json']:
  inputs[str(p)]=sha(p)
 return nodes,sourceby,targetby,inputs

def build_panel(panel,nodes,sourceby,targetby,inputs):
 d=OUT/panel;d.mkdir(exist_ok=True)
 u=UF(len(nodes));seen={};edge_counts=Counter();token_owners=defaultdict(list)
 def connect(token,i,kind):
  if token in seen:u.union(i,seen[token]);edge_counts[kind]+=1
  else:seen[token]=i
 for i,n in enumerate(nodes):
  for token in sorted(n['tokens']):connect(token,i,token.split(':',1)[0]);token_owners[token].append(i)
  # Preserve declared legacy biological components only in the matching task/panel.
  q=n['raw']
  if n['dataset']=='ppikb_kd':
   g=(sourceby if panel=='source' else targetby)[n['row_id']]['group_id']
   connect('component:ppikb:'+g,i,'legacy_component')
  elif n['dataset']=='ppikb_contact' and q.get('group_id'):
   connect('component:contact:'+q['group_id'],i,'legacy_component')
  elif n['dataset']=='her2' and q.get('strict_variant_component_id'):
   connect('component:her2:'+q['strict_variant_component_id'],i,'legacy_component')
  if panel=='target':
   if n['target']:
    connect('target:'+hs(n['target']),i,'target_exact')
    connect('target_prefix1000:'+hs(n['target'][:1000]),i,'target_effective_prefix')
   if n['dataset'] in ('pepinter','pepaff') and q.get('group_id'):connect('component:'+n['dataset']+':'+q['group_id'],i,'author_target_cluster')
 # The source-panel graph explicitly omits isolated target edges; target panel retains source/chemistry guards.
 if panel=='source':
  bychem={}
  for i,n in enumerate(nodes):
   for t in n['tokens']:
    if t.startswith('chemical_iso:'):bychem[t.split(':',1)[1]]=i
  for e in readjl(OLD/'chemical-neighbor-edges.jsonl'):
   if e['a'] in bychem and e['b'] in bychem:u.union(bychem[e['a']],bychem[e['b']]);edge_counts['chemical_neighbor_known']+=1
 targets={}
 if panel=='target':
  for i,n in enumerate(nodes):
   if n['target']:targets.setdefault(hs(n['target'])[:20],i)
  for e in readjl(OLD/'target-homology-pairs.jsonl'):
   if e['a'] in targets and e['b'] in targets:u.union(targets[e['a']],targets[e['b']]);edge_counts['target_homology_preexisting']+=1
  # Exact containment examined for all cross-source targets with shorter >=40aa.
  seqs={n['target']:i for i,n in enumerate(nodes) if n['target']}
  seqitems=sorted(seqs.items(),key=lambda kv:(len(kv[0]),hs(kv[0])))
  count=0
  for pos,(a,ia) in enumerate(seqitems):
   if len(a)<40:continue
   for b,ib in seqitems[pos+1:]:
    if len(b)==len(a):continue
    count+=1
    if a in b:u.union(ia,ib);edge_counts['target_exact_containment']+=1
  edge_counts['target_containment_comparisons']=count
 comps=defaultdict(list)
 for i in range(len(nodes)):comps[u.find(i)].append(i)
 assignments=[];fine=[];blocked=[];protected=[];pretrain=[];component_rows=[];external=[]
 category_counts=Counter()
 for root,ids in sorted(comps.items()):
  gid=hs('\n'.join(sorted(nodes[i]['dataset']+':'+nodes[i]['row_id'] for i in ids)))
  external_component=any(nodes[i]['external'] for i in ids)
  kd_splits={(sourceby if panel=='source' else targetby)[nodes[i]['row_id']]['split'] for i in ids if nodes[i]['dataset']=='ppikb_kd'}
  otherheld=any(nodes[i]['legacy_split'] in ('validation','test') and nodes[i]['dataset']!='ppikb_kd' for i in ids)
  # Anchor priority external > Kd test > Kd validation; other task heldout protects the component too.
  anchor=('external' if external_component else 'test' if 'test' in kd_splits else 'validation' if 'validation' in kd_splits else 'other_task_heldout' if otherheld else 'development')
  component_rows.append({'global_group_id':gid,'rows':len(ids),'anchor':anchor,'datasets':json.dumps(dict(Counter(nodes[i]['dataset'] for i in ids)),sort_keys=True),'kd_legacy_splits':json.dumps(sorted(kd_splits))})
  for i in ids:
   n=nodes[i];q=n['raw'];legacy=(sourceby if panel=='source' else targetby)[n['row_id']]['split'] if n['dataset']=='ppikb_kd' else n['legacy_split']
   if n['external']:role='external_background' if n['dataset']=='pepbi_background' else 'external';reason='reserved_external_source_entity_structure_background'
   elif n['dataset']=='ppikb_kd' and anchor in ('test','validation') and legacy==anchor:role=anchor;reason='locked_legacy_kd_'+anchor
   elif n['dataset']=='ppikb_kd' and panel=='source' and not n['source_known']:role='quarantine';reason='source_identity_unresolved'
   elif n['dataset']=='ppikb_kd' and anchor=='development' and legacy=='train' and not n['source_known']:role='quarantine';reason='source_identity_unresolved'
   elif n['dataset']=='ppikb_kd' and anchor=='development' and legacy=='train':role='fine_train';reason='legacy_train_no_declared_protected_dependency'
   elif anchor!='development':role='quarantine';reason='dependency_to_'+anchor
   elif not n['source_known']:role='quarantine';reason='source_identity_unresolved'
   elif n['dataset']=='her2':role='quarantine';reason='antibody_local_track_not_short_peptide_pretrain'
   elif 'train' in kd_splits:role='quarantine';reason='reserved_for_fine_train_component_not_independent_pretrain'
   else:role='pretrain';reason='legacy_train_no_declared_protected_dependency'
   a={'dataset':n['dataset'],'row_id':n['row_id'],'legacy_split':legacy,'role':role,'global_group_id':gid,'anchor':anchor,'role_reason':reason,'source_known':n['source_known'],'chemical_discordance_flag':n['chemical_flag'],'source_alias_count':len(n['source_aliases'])}
   assignments.append(a);category_counts[(n['dataset'],role)]+=1
   if role=='fine_train' or (n['dataset']=='ppikb_kd' and role in ('validation','test')):
    z=dict((sourceby if panel=='source' else targetby)[n['row_id']]);z.update(split=role,global_group_id=gid,legacy_split=legacy,freeze_panel=panel,role_reason=reason,residue_class_graph_discordance=str(n['chemical_flag']).lower());fine.append(z)
   elif role=='pretrain':pretrain.append(a)
   elif role=='quarantine':blocked.append(a)
   else:protected.append(a)
   if role=='external' and n['dataset'] in ('profaff_fp','profaff_effect','profaff_holdup','pepbi_candidate'):external.append(dict(q,global_group_id=gid,freeze_panel=panel,split='external_test',freeze_dataset=n['dataset'],external_qualification='declared_source_entity_structure_supervised_firewall; assay_chemistry_and_foundation_pretraining_not_certified'))
 writecsv(d/'fine_affinity.csv',fine,list(dict.fromkeys(list(next(iter(sourceby.values())))+['global_group_id','legacy_split','freeze_panel','role_reason','residue_class_graph_discordance'])))
 writecsv(d/'role_assignments.csv',assignments)
 writecsv(d/'pretrain_ids.csv',pretrain,list(assignments[0]))
 writecsv(d/'quarantine.csv',blocked,list(assignments[0]))
 writecsv(d/'protected_ids.csv',protected,list(assignments[0]))
 writecsv(d/'components.csv',component_rows)
 external_views=[]
 pepbi_rules=json.loads((ROOT/'publication/github-checkout/four-task-20261022/pepbi-input-erratum-v1/frozen-panel-rules.json').read_text(encoding='utf-8-sig'))
 for dataset in ('profaff_fp','profaff_effect','profaff_holdup','pepbi_candidate'):
  z=[r for r in external if r.get('freeze_dataset')==dataset]
  if dataset=='pepbi_candidate':
   oldp=d/'external_pepbi_candidate_original27.csv';writecsv(oldp,z)
   ptpa=[r for r in z if r['row_id'] in pepbi_rules['panels']['PTPA4_primary_identity_candidates']]
   pp=d/'external_pepbi_ptpa4.csv';writecsv(pp,ptpa)
   external_views.append({'id':panel+'_external_pepbi_ptpa4','path':pp.relative_to(OUT).as_posix(),'sha256':sha(pp),'rows':len(ptpa),'status':'frozen_conditional_external','dataset':'pepbi_ptpa4','is_subset_of':'pepbi_candidate','qualification':'Four previously evaluated points, one study/protein; not new blind test.'})
   z=[r for r in z if r['row_id'] in pepbi_rules['panels']['exclude3_wrong_input24']]
  p=d/('external_'+dataset+'.csv');writecsv(p,z)
  external_views.append({'id':panel+'_external_'+dataset,'path':p.relative_to(OUT).as_posix(),'sha256':sha(p),'rows':len(z),'status':'frozen_conditional_external','dataset':dataset,'qualification':'External role frozen; no claim of assay-chemical identity or foundation-pretraining independence.'})
 finecounts=dict(Counter(r['split'] for r in fine))
 ready=all(finecounts.get(k,0)>0 for k in ('fine_train','validation','test'))
 fineids={r['row_id'] for r in fine if r['split']=='fine_train'}
 summary={'panel':panel,'training_ready':ready,'role_counts':{f'{ds}/{role}':v for (ds,role),v in sorted(category_counts.items())},'fine_split_counts':finecounts,'fine_source_known_counts':dict(Counter(str(n['source_known']) for n in nodes if n['dataset']=='ppikb_kd' and n['row_id'] in fineids)),'fine_chemical_strata':{s:dict(Counter(r['evaluation_stratum'] for r in fine if r['split']==s)) for s in ('fine_train','validation','test')},'components':len(comps),'largest_component_rows':max(map(len,comps.values())),'edge_counts':dict(edge_counts),'target_similarity_coverage':'Existing PPIKB target alignments plus all exact containment; novel cross-source local alignments are not certified. Morgan-neighbor edges are source-panel only; this panel does not claim peptide-neighbor-cold.' if panel=='target' else 'Target similarity measured in separate panel; no target-cold claim.'}
 js(d/'summary.json',summary)
 views={'id':'ppikb_kd_'+panel+'_global_firewall_v1','path':(d/'fine_affinity.csv').relative_to(OUT).as_posix(),'sha256':sha(d/'fine_affinity.csv'),'rows':len(fine),'task':'affinity','endpoint':'pKd','split_column':'split','group_column':'global_group_id','status':'frozen' if ready else 'blocked_no_training_rows','training_ready':ready,'qualification':'Conservative declared dependency firewall, legacy heldout preserved or quarantined; historical seen tests are not new blind tests. Source and target edge sets differ; inspect summary.'}
 return summary,views,external_views

def main():
 existing=OUT/'frozen-manifest.json'
 if existing.exists() and json.loads(existing.read_text(encoding='utf8')).get('revision',0)>=2:
  raise SystemExit('Immutable final revision already exists; create a new version directory instead of overwriting.')
 start=time.time();nodes,sourceby,targetby,inputs=prepare()
 js(OUT/'input-manifest.json',{'inputs':[{'path':p,'sha256':h} for p,h in inputs.items()],'numeric_labels_used_to_assign_roles':False,'assignment_fields':['row_id','split','source_aliases','chemical_entity_id','achiral_entity_id','sequence_hashes','PDB','legacy_components','preexisting_neighbor_edges']})
 summaries=[];views=[];external=[]
 for panel in ('source','target'):
  summary,view,ext=build_panel(panel,nodes,sourceby,targetby,inputs);summaries.append(summary);views.append(view);external.extend(ext)
  print(json.dumps(summary,ensure_ascii=False),flush=True)
 outputs=[{'path':p.relative_to(OUT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for panel in ('source','target') for p in sorted((OUT/panel).iterdir()) if p.is_file()]
 manifest={'schema':'peptide.cross-task-firewall.v1','version':VERSION,'revision':2,'status':'frozen','frozen':True,'producer_path':Path(__file__).relative_to(OUT).as_posix(),'producer_sha256':sha(__file__),'input_manifest_path':'input-manifest.json','input_manifest_sha256':sha(OUT/'input-manifest.json'),'outputs':outputs,'frozen_at_utc':datetime.now(timezone.utc).isoformat(),'split_is_new_blind_test':False,'numeric_labels_used_to_assign_roles':False,'views':views,'external_views':external,'summaries':summaries,'old_inputs_changed':False,'source_unknown_policy':'No pretraining or fine_train for absent DOI/PMID/title; sentinel study aliases not evidence. Unknown source evaluation records retained with qualification.','remaining_qualification_gaps':['Foundation model unsupervised pretraining members unknown','Complete chemical identity and assay construct unresolved for external resources','Novel cross-source target local alignment coverage incomplete; not universal family-cold','PEPBI formal external24, historical27 and nestedPTPA4; original329 is protection background only'],'seconds':time.time()-start}
 js(OUT/'frozen-manifest.json',manifest)
 print(json.dumps({'manifest':str(OUT/'frozen-manifest.json'),'sha256':sha(OUT/'frozen-manifest.json'),'seconds':time.time()-start}),flush=True)

if __name__=='__main__':main()
