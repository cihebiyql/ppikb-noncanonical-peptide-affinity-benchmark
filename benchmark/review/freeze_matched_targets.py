"""Freeze a label-free shared-reference-target diagnostic, before performance.
This never reads sealed affinity labels, model predictions or checkpoints.
"""
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
import json
import recompute_metrics as audit

R=Path(__file__).resolve().parent;P=R.parent;F=P/'data-protocol/frozen-v1'
OUT=R/'matched-target-diagnostics-v1'

def main():
 OUT.mkdir(exist_ok=False)
 rows=audit.read_jsonl(F/'inputs.jsonl')
 if any(any(k in r for k in ['pKd','pKd_true','pKd_pred','value_molar','reported_value']) for r in rows):raise ValueError('Not label-free')
 byid=audit.unique_by_id(rows,'label-free metadata');sources=[F/'inputs.jsonl',F/'manifest.json']
 datasets=[]
 for panel in sorted(audit.PANELS):
  d=OUT/panel;d.mkdir()
  raw={}
  for regime in ['NC_only','standard_only']:
   p=F/'splits'/panel/regime/'test-ids.json';sources.append(p)
   raw[regime]=set(audit.read_json(p))
  target={rid:audit.hashlib.sha256(byid[rid]['target_sequence'].encode('utf-8')).hexdigest() for rid in raw['NC_only']|raw['standard_only']}
  common={target[rid] for rid in raw['NC_only']} & {target[rid] for rid in raw['standard_only']}
  if not common:raise ValueError('No shared reference targets; preserve explicit empty diagnostic rather than fabricate')
  matched={regime:sorted(rid for rid in ids if target[rid] in common) for regime,ids in raw.items()}
  for name,ids in matched.items():audit.write_json(d/(name+'-matched-test-ids.json'),ids)
  audit.write_json(d/'common-target-reference-sequence-sha256.json',sorted(common))
  mapping=[]
  for regime in ['NC_only','standard_only']:
   for rid in matched[regime]:mapping.append({'record_id':rid,'target_reference_sequence_sha':target[rid],'NC_core':byid[rid]['NC_core'],'evaluation_stratum':byid[rid]['evaluation_stratum'],'study_id':byid[rid].get('study_id')})
  with (d/'record-target-map.jsonl').open('w',encoding='utf-8') as f:
   for row in mapping:f.write(json.dumps(row,ensure_ascii=False)+'\n')
  per_target=[]
  for t in sorted(common):
   rr=[r for r in mapping if r['target_reference_sequence_sha']==t]
   per_target.append({'target_reference_sequence_sha':t,'NC_test_n':sum(r['NC_core'] is True for r in rr),'standard_test_n':sum(r['NC_core'] is False for r in rr)})
  audit.write_json(d/'per-target-label-free-counts.json',per_target)
  datasets.append({'panel':panel,'shared_target_reference_count':len(common),'NC_main_test_n':len(raw['NC_only']),'standard_main_test_n':len(raw['standard_only']),
   'NC_matched_test_n':len(matched['NC_only']),'standard_matched_test_n':len(matched['standard_only']),
   'NC_matched_strata':dict(Counter(byid[rid]['evaluation_stratum'] for rid in matched['NC_only'])),
   'standard_matched_strata':dict(Counter(byid[rid]['evaluation_stratum'] for rid in matched['standard_only'])),
   'NC_ids':str(d/'NC_only-matched-test-ids.json'),'standard_ids':str(d/'standard_only-matched-test-ids.json'),
   'target_reference_shas':str(d/'common-target-reference-sequence-sha256.json'),'mapping':str(d/'record-target-map.jsonl')})
 files=[{'path':str(p),'bytes':p.stat().st_size,'sha256':audit.sha(p)} for p in sorted(OUT.rglob('*')) if p.is_file()]
 manifest={'schema':'label-free-matched-target-diagnostics.v1','status':'frozen_metadata_only_not_scored','created_utc':datetime.now(timezone.utc).isoformat(),
  'decision_rule':'Within each unchanged main test panel, intersect exact full database-reference protein sequence SHA256 between NC and standard records; retain all records for those shared targets; no performance or affinity values used.',
  'target_key':'SHA256 exact UTF8 target_sequence in immutable frozen inputs, not target_id and not experimental clone/family',
  'evaluation_rule':'Reuse the same saved full-test predictions. On each training regime separately evaluate matched NC and matched standard rows, compute per-reference-target metrics, then equal-weight macro across the same fixed common reference targets. Also report n observations, n targets and metric-defined-target counts.',
  'no_fit_or_resplit_or_model_selection':True,'original_main_test_unchanged':True,'gold_reads':0,'prediction_reads':0,
  'dependency_limits':['Same peptides/chemical entities and sources can repeat within a test panel; these are not independent biological samples.','Matching target references does not match peptide scaffolds, affinity distributions, assays or actual constructs.','The source-cold and target-reference-homology-cold panels isolate their own axes, not all dependencies simultaneously.','Ten training-seed SD is not biological confidence interval.'],
  'panels':datasets,'source_files':[{'path':str(p),'sha256':audit.sha(p)} for p in sources],'artifacts':files}
 audit.write_json(OUT/'manifest.json',manifest)
 print(json.dumps({'matched_panels':datasets,'manifest_sha256':audit.sha(OUT/'manifest.json'),'gold_reads':0,'prediction_reads':0},ensure_ascii=False))

if __name__=='__main__':main()
