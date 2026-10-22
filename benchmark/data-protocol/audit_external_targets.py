import json,hashlib
from pathlib import Path
from collections import defaultdict,Counter
P=Path(__file__).resolve().parent
def read(p):
 with p.open(encoding='utf-8') as f:return list(map(json.loads,f))
main=read(P/'label-free-grouping-input.jsonl');external=read(P/'external-blind-chemical-inputs.jsonl');edges=read(P/'target-homology-pairs.jsonl')
mainids=defaultdict(list);adj=defaultdict(set)
for r in main:mainids[hashlib.sha256(r['target_sequence'].encode()).hexdigest()[:20]].append(r['record_id'])
for e in edges:adj[e['a']].add(e['b']);adj[e['b']].add(e['a'])
output=[]
for r in external:
 key=hashlib.sha256(r['target_sequence_view'].encode()).hexdigest()[:20]
 hits=sorted((adj[key]|{key})&set(mainids))
 output.append({'external_id':r['external_id'],'resource_id':r['resource_id'],'target_reference_hash':key,'same_reference_as_main':key in mainids,'related_main_reference_hashes':hits,'related_main_observation_ids':sorted({rid for k in hits for rid in mainids[k]}),'target_cold_against_all_main_declared_rule':not hits,'scope':'all main references using declared local alignment plus exact domain containment; not actual assay construct certification'})
with (P/'external-target-overlap.jsonl').open('w',encoding='utf-8') as f:
 for r in output:f.write(json.dumps(r,ensure_ascii=False)+'\n')
summary={s:{'rows':len(a),'same_reference_rows':sum(x['same_reference_as_main'] for x in a),'related_reference_rows':sum(bool(x['related_main_reference_hashes']) for x in a),'target_cold_rows':sum(x['target_cold_against_all_main_declared_rule'] for x in a)} for s in sorted({r['resource_id'] for r in output}) for a in [[r for r in output if r['resource_id']==s]]}
(P/'external-target-overlap-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False,indent=2))
