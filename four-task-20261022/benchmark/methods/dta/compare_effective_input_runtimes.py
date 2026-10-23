"""Compare actual cached feature fingerprints across two audited consumers, with explicit overlap denominators."""
from pathlib import Path
import argparse,datetime as dt,gzip,hashlib,json
P=argparse.ArgumentParser();P.add_argument('--native-report',required=True);P.add_argument('--manifest24-report',required=True);A=P.parse_args();H=Path(__file__).resolve().parent
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(report_path,entry):
 p=Path(report_path).parent/entry['input_index'];assert sha(p)==entry['input_index_sha256']
 with gzip.open(p,'rt',encoding='utf-8') as f:return {(x['record_id'],x['split']):x for x in map(json.loads,f) if x}
left=load(A.native_report);right=load(A.manifest24_report);assert left['runtime']['auditor_source_sha256']==right['runtime']['auditor_source_sha256']=='5c77fdbe679f1213e04d38109db40d45b6a0d9f32408f7078290997a32b25916'
R={(r['view'],r['method']):r for r in right['results']};result=[];total=equal=0
for entry in left['results']:
 key=entry['view'],entry['method'];other=R[key];a=rows(A.native_report,entry);b=rows(A.manifest24_report,other);keys=set(a)&set(b);fields=['effective_pair_hash','graph_hash','target_tokens_hash','container_hash_including_unused_edge_attr','recorded_complete_chemistry_hash','complete_target_hash']
 count={field:sum(a[k][field]==b[k][field] for k in keys) for field in fields};bad=[{'record_id':k[0],'split':k[1],'left_effective_hash':a[k]['effective_pair_hash'],'right_effective_hash':b[k]['effective_pair_hash']} for k in sorted(keys) if a[k]['effective_pair_hash']!=b[k]['effective_pair_hash']]
 result.append({'view':key[0],'method':key[1],'native_rows':len(a),'manifest24_rows':len(b),'compared_overlap_rows':len(keys),'equal_field_counts':count,'consumed_tensor_difference_rows':bad,'native_complete_partitions':entry['complete_partitions'],'manifest24_complete_partitions':other['complete_partitions']});total+=len(keys);equal+=count['effective_pair_hash']
stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ');out=H/('cross-runtime-effective-input-comparison-'+stamp+'.json');out.write_text(json.dumps({'at':stamp,'left_report_path':A.native_report,'left_report_sha256':sha(A.native_report),'right_report_path':A.manifest24_report,'right_report_sha256':sha(A.manifest24_report),'left_runtime':left['runtime'],'right_runtime':right['runtime'],'total_compared_overlap_rows_across_method_views':total,'equal_consumed_input_fingerprint_rows':equal,'records':result,'scope':'Measured canonical consumed tensor dtype/shape/bytes hashes on overlap of existing caches. Counts repeat biological observations across methods/views. Missing partitions remain unverified. No claim about model initialization, gradients, prediction or backend bitwise equivalence; no new encoder/model/fit/forward.'},indent=2),encoding='utf-8');print(json.dumps({'path':str(out),'compared':total,'consumed_input_hash_equal':equal,'different':total-equal}))
