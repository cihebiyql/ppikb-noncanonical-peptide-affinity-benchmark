"""Deterministic group splits. Uses no affinity labels for assignment."""
import json,hashlib,csv,re
from pathlib import Path
from collections import Counter,defaultdict
P=Path(__file__).resolve().parent
SPLIT_SEED='nc-protocol-20261021-v1'
class UF:
 def __init__(self,n):self.p=list(range(n))
 def find(self,x):
  while self.p[x]!=x:self.p[x]=self.p[self.p[x]];x=self.p[x]
  return x
 def union(self,a,b):
  a,b=self.find(a),self.find(b)
  if a!=b:self.p[max(a,b)]=min(a,b)
def load(name):
 with (P/name).open(encoding='utf-8') as f:return list(map(json.loads,f))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def group_key(ids):return hashlib.sha256('\n'.join(sorted(ids)).encode()).hexdigest()
def source_components(rows,chem):
 u=UF(len(rows));seen={};counts=Counter()
 aliases={r['record_id']:r['source_aliases'] for r in load('label-free-study-aliases.jsonl')}
 def connect(k,i,kind):
  if k in seen:u.union(i,seen[k]);counts[kind]+=1
  else:seen[k]=i
 for i,r in enumerate(rows):
  c=chem[r['record_id']]
  for alias in aliases[r['record_id']]:connect(('source_alias',alias),i,'source_alias')
  for kind,k in [('study',r['study_group']),('chemical',c['chemical_entity_id']),('achiral',c['achiral_entity_id']),('raw_parent',r.get('peptide_sequence_raw')),('parent_series',r.get('parent_series_id'))]:
   if k:connect((kind,k),i,kind)
  # Conservative one-substitution mother groups, including explicit X tokens.
  seq=r.get('peptide_sequence_raw') or ''
  if len(seq)>=5 and re.fullmatch('[ACDEFGHIKLMNPQRSTVWYX]+',seq):
   for j in range(len(seq)):connect(('one_substitution',len(seq),j,seq[:j]+'*'+seq[j+1:]),i,'one_substitution')
 bychemical={}
 for i,r in enumerate(rows):bychemical.setdefault(chem[r['record_id']]['chemical_entity_id'],i)
 with (P/'chemical-neighbor-edges.jsonl').open() as f:
  for edge in map(json.loads,f):u.union(bychemical[edge['a']],bychemical[edge['b']]);counts['chemical_neighbor']+=1
 return u,dict(counts)
def components(rows,u):
 result=defaultdict(list)
 for i,r in enumerate(rows):result[u.find(i)].append(r['record_id'])
 return sorted(result.values(),key=lambda ids:(-len(ids),group_key(ids)))
def assign(comps):
 sizes={'train':0,'validation':0,'test':0};n=sum(map(len,comps));ratios={'train':.7,'validation':.15,'test':.15};assignment={};groups={}
 # Count-only greedy deficit allocation. No stratum or affinity balancing.
 for ids in sorted(comps,key=lambda ids:(-len(ids),hashlib.sha256((SPLIT_SEED+group_key(ids)).encode()).hexdigest())):
  split=max(sizes,key=lambda s:(ratios[s]*n-sizes[s],s=='train',s=='validation'))
  gid=group_key(ids)
  for rid in ids:assignment[rid]=split;groups[rid]=gid
  sizes[split]+=len(ids)
 return assignment,groups,sizes
def target_components(rows):
 p=P/'target-homology-pairs.jsonl'
 if not p.exists():return None
 byseq={};byprefix={};u=UF(len(rows))
 for i,r in enumerate(rows):
  seq=r['target_sequence'];key=hashlib.sha256(seq.encode()).hexdigest()[:20]
  if key in byseq:u.union(i,byseq[key])
  else:byseq[key]=i
  prefix=seq[:1000]
  if prefix in byprefix:u.union(i,byprefix[prefix])
  else:byprefix[prefix]=i
 with p.open() as f:
  for edge in map(json.loads,f):
   if edge['a'] in byseq and edge['b'] in byseq:u.union(byseq[edge['a']],byseq[edge['b']])
 return u
def main():
 rows=sorted(load('label-free-grouping-input.jsonl'),key=lambda r:r['record_id']);chem={r['record_id']:r for r in load('chemical-entity-mapping.jsonl')}
 src,edgecounts=source_components(rows,chem);panels={'source_peptide_dependency_cold':src};target=target_components(rows)
 if target:panels['target_reference_homology_cold']=target
 if target:
  dual=UF(len(rows))
  for unit in [src,target]:
   seen={}
   for i in range(len(rows)):
    key=unit.find(i)
    if key in seen:dual.union(i,seen[key])
    else:seen[key]=i
  panels['dual_source_peptide_target_diagnostic']=dual
 report={'status':'proposal_not_training_authorization','split_seed':SPLIT_SEED,'training_seeds':list(range(10)),'input_label_access':'none; grouping input contains no numeric affinity','rows':len(rows),'source_dependency_edge_counts':edgecounts,'panels':{}}
 for name,u in panels.items():
  comps=components(rows,u);a,g,sizes=assign(comps)
  feasible=max(map(len,comps))<=.7*len(rows) and min(sizes.values())>=.05*len(rows)
  d=P/'split-proposals'/name;d.mkdir(parents=True,exist_ok=True)
  with (d/'assignments.csv').open('w',newline='',encoding='utf-8-sig') as f:
   w=csv.DictWriter(f,fieldnames=['record_id','split','dependency_component','evaluation_stratum']);w.writeheader()
   for r in rows:w.writerow({'record_id':r['record_id'],'split':a[r['record_id']],'dependency_component':g[r['record_id']],'evaluation_stratum':r['evaluation_stratum']})
  for split in sizes:dump(d/(split+'-ids.json'),sorted(rid for rid in a if a[rid]==split))
  summary={'components':len(comps),'largest_component_rows':len(comps[0]),'largest_component_fraction':len(comps[0])/len(rows),'largest_10_component_sizes':list(map(len,comps[:10])),'split_sizes':sizes,'strata_by_split':{s:dict(Counter(r['evaluation_stratum'] for r in rows if a[r['record_id']]==s)) for s in sizes},'70_15_15_group_split_feasible':feasible,'zero_component_overlap':all(len({a[rid] for rid in ids})==1 for ids in comps),'assignment_sha256':hashlib.sha256((d/'assignments.csv').read_bytes()).hexdigest()}
  dump(d/'summary.json',summary);report['panels'][name]=summary
 dump(P/'split-feasibility-report.json',report);print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
