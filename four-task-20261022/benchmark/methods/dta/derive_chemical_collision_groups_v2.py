"""Correct broad group labels from frozen raw stratum text; reuse all tensor hashes, never re-encode."""
from pathlib import Path
import argparse,collections,datetime as dt,gzip,hashlib,json
P=argparse.ArgumentParser();P.add_argument('report');A=P.parse_args();SOURCE=Path(A.report);D=SOURCE.parent/('chemical-groups-v2-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));D.mkdir()
MAP={'standard20_control':'standard','standard':'standard','PTM':'PTM','synthetic_D_backbone':'NC','other_NC':'NC','synthetic_and_PTM':'NC+PTM'}
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,indent=2),encoding='utf-8')
report=load(SOURCE);new=[]
for result in report['results']:
 r=dict(result);source=SOURCE.parent/r['input_index'];assert sha(source)==r['input_index_sha256']
 with gzip.open(source,'rt',encoding='utf-8') as f:rows=[json.loads(x) for x in f if x.strip()]
 for x in rows:x['broad_chemical_group']=MAP.get(x['stratum'],'unknown:'+x['stratum'])
 index=D/r['input_index']
 with gzip.open(index,'wt',encoding='utf-8') as f:
  for x in rows:f.write(json.dumps(x)+'\n')
 r.update(input_index_sha256=sha(index),broad_chemical_counts=dict(collections.Counter(x['broad_chemical_group'] for x in rows)))
 if r['complete_partitions']:
  groups=collections.defaultdict(list)
  for x in rows:groups[x['effective_pair_hash']].append(x)
  duplicate=[]
  for key,g in groups.items():
   if len(g)>1:duplicate.append({'effective_pair_hash':key,'records':[x['record_id'] for x in g],'splits':dict(collections.Counter(x['split'] for x in g)),'strata':dict(collections.Counter(x['stratum'] for x in g)),'broad_chemical_groups':dict(collections.Counter(x['broad_chemical_group'] for x in g)),'recorded_complete_chemistry_count':len({x['recorded_complete_chemistry_hash'] for x in g}),'complete_target_count':len({x['complete_target_hash'] for x in g})})
  ambiguous={k for k,g in groups.items() if len({x['stratum'] for x in g})>1};chem_alias={k for k,g in groups.items() if len({x['recorded_complete_chemistry_hash'] for x in g})>1}
  masks=load(SOURCE.parent/r['test_masks_file']);lookup={x['record_id']:x for x in rows if x['split']=='test'}
  for mask in masks:
   x=lookup[mask['record_id']];mask.update(same_effective_input_has_multiple_raw_strata=x['effective_pair_hash'] in ambiguous,same_effective_input_has_different_recorded_chemistry=x['effective_pair_hash'] in chem_alias,broad_chemical_group=x['broad_chemical_group'],raw_stratum=x['stratum'])
  write(D/r['duplicate_groups_file'],duplicate);write(D/r['test_masks_file'],masks)
  r.update(duplicate_groups_sha256=sha(D/r['duplicate_groups_file']),test_masks_sha256=sha(D/r['test_masks_file']),groups_with_multiple_broad_chemical_types=sum(len(x['broad_chemical_groups'])>1 for x in duplicate),groups_with_multiple_raw_strata=sum(len(x['strata'])>1 for x in duplicate),test_cross_raw_stratum_input_annotation=sum(x['same_effective_input_has_multiple_raw_strata'] for x in masks),test_cross_recorded_chemistry_input=sum(x['same_effective_input_has_different_recorded_chemistry'] for x in masks))
 new.append(r)
report.update(schema='fourtask.actual-cached-effective-input-audit.v2',results=new,parent_report_path=str(SOURCE),parent_report_sha256=sha(SOURCE),broad_chemical_mapping=MAP,correction='v1 broad grouping failed to recognize standard20_control and grouped synthetic_and_PTM intoPTM. Raw strata, every actual tensor hash, split counts and collision membership are unchanged. Parent report preserved.',no_feature_or_model_call=True)
write(D/'complete.json',report);print(json.dumps({'directory':str(D),'complete_view_method_units':sum(x['complete_partitions'] for x in new),'summary':[{'view':x['view'],'method':x['method'],'mixed_raw_strata_test':x.get('test_cross_raw_stratum_input_annotation'),'mixed_broad_groups':x.get('groups_with_multiple_broad_chemical_types')} for x in new]}))
