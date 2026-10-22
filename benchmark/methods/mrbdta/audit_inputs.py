"""Label-free vocabulary/length coverage plus model-view IDs and hashes."""
import hashlib
import json
from collections import Counter
from pathlib import Path
HERE=Path(__file__).resolve().parent
v=json.loads((HERE/'vocabularies.json').read_text())
source=HERE.parents[1]/'data-protocol/model-observations.jsonl'
counts=Counter(); lengths=[]; examples=[]; collisions={}
with source.open(encoding='utf-8') as inp,(HERE/'input-audit.jsonl').open('w',encoding='utf-8') as out:
 for line in inp:
  r=json.loads(line); s=r.get('canonical_isomeric_smiles') or r.get('peptide_smiles') or ''; t=r.get('target_sequence') or ''; eff=t[:1000]
  u_s=sorted(set(s)-v['drug'].keys()); u_t=sorted(set(t)-v['target'].keys())
  reasons=[]
  if not s or not t: reasons.append('missing_input')
  if len(s)>5000: reasons.append('smiles_native_position_capacity')
  if u_s:reasons.append('unknown_smiles_tokens')
  if u_t:reasons.append('unknown_protein_tokens')
  h=hashlib.sha256((s+'\0'+eff).encode()).hexdigest()
  a={'record_id':r['record_id'],'smiles_length':len(s),'protein_length':len(t),'effective_protein_length':len(eff),'protein_truncated':len(t)>1000,'unknown_smiles_tokens':u_s,'unknown_protein_tokens':u_t,'blocked_reasons':reasons,'effective_input_sha256':h,
     'full_protein_sha256':hashlib.sha256(t.encode()).hexdigest(),'effective_protein_sha256':hashlib.sha256(eff.encode()).hexdigest(),
     'three_streams_retained_attention_float32_bytes':3*4*4*(len(s)**2+len(eff)**2)}
  out.write(json.dumps(a)+'\n');counts['rows']+=1;counts['protein_truncated']+=len(t)>1000
  counts['eligible']+=not reasons
  for reason in reasons:counts[reason]+=1
  lengths.append(a);collisions.setdefault(h,[]).append(r['record_id'])
  # Small real-input smoke selection uses only lengths, never observed affinity.
  if not reasons and len(s)<=250 and len(t)<=300 and len(examples)<2:examples.append(r)
(HERE/'smoke-inputs.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in examples),encoding='utf-8')
stats={'source_path':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'counts':dict(counts),'max_smiles_length':max(x['smiles_length'] for x in lengths),'max_protein_length':max(x['protein_length'] for x in lengths),
 'longest_smiles':sorted(lengths,key=lambda x:x['smiles_length'],reverse=True)[:10],
 'effective_input_duplicate_groups':[{'hash':h,'ids':ids} for h,ids in collisions.items() if len(ids)>1],
 'smoke_count':len(examples),'memory_estimate_scope':'Three retained attention matrices per modality only; excludes scores, backward saved tensors, parameters, gradients and optimizer. Not measured peak.'}
(HERE/'input-audit-summary.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
print(json.dumps({'counts':stats['counts'],'max_smiles_length':stats['max_smiles_length'],'max_protein_length':stats['max_protein_length'],'smoke_count':len(examples)}))
