"""Metadata-only, append-only frozen ESM cache extension and four-way input freeze."""
from __future__ import annotations
import argparse,csv,hashlib,json,re,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
import numpy as np

MODEL_SHA='46f002a9870c9bdecd0ea887acb1f9a38a6b561e8f8bf8a6990b679b9d31b928'
GLOBAL_SHA='971a1feaafeae45e0e4f29092b80405419d8d47100b0a3e5e936c82ecc0e44c0'
OLD_NPZ_SHA='a097ddfc203868fa299e4f25dcf01570f0f189de7d5ba4fcc054923417b3179f'
DELTA_NPZ_SHA='eaa5f05a1278fe04832298bd56ae1604763ca4ee315bfbd9c881f880f23ff915'
DELTA_GO_SHA='3e08f33e17cae68b49bba4f0a25330270ab4da2ca3a720921d50869d4b615a73'
COHORT_PRODUCER_SHA='44f9aaeaa2821621555aad3b776740527703f5d966fc580239765326b4401413'
EXTRACTOR_SHA='a2d38483e8b3cc9bd06a2b51543e741c91ea86331bbf77a7f54b9a3936de69f9'
AA=set('ACDEFGHIKLMNPQRSTVWY')
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,v):
    with Path(p).open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def rows(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def csvout(p,rr,keys):
    with Path(p).open('x',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rr)
def load_arrays(p):
    with np.load(p,allow_pickle=False) as obj:
        if set(obj.files)!={'sequence_ids','embeddings'}:raise ValueError('Only reviewed original ESM NPZ fields are permitted')
        ids=obj['sequence_ids'].copy();matrix=obj['embeddings'].copy()
    if ids.ndim!=1 or ids.dtype.kind!='U' or matrix.dtype!=np.dtype('float32') or matrix.ndim!=2 or matrix.shape!=(len(ids),320):raise ValueError('Unexpected ESM key/dtype/shape')
    if not np.isfinite(matrix).all() or len(set(map(str,ids)))!=len(ids):raise ValueError('Nonfinite or duplicate ESM rows')
    if any(re.fullmatch('[0-9a-f]{64}',str(k)) is None for k in ids):raise ValueError('Sequence keys must be full raw sequence SHA256')
    return ids,matrix
def merge_arrays(old_ids,old,delta_ids,delta):
    if old.dtype!=np.float32 or delta.dtype!=np.float32 or old.shape!=(len(old_ids),320) or delta.shape!=(len(delta_ids),320):raise ValueError('Invalid synthetic/actual merge matrix')
    if not np.isfinite(old).all() or not np.isfinite(delta).all():raise ValueError('Nonfinite vector')
    if len(set(map(str,old_ids)))!=len(old_ids) or len(set(map(str,delta_ids)))!=len(delta_ids):raise ValueError('Duplicate key')
    if set(map(str,old_ids))&set(map(str,delta_ids)):raise ValueError('New keys overlap the immutable old cache')
    ids=np.concatenate([old_ids,delta_ids]);vectors=np.concatenate([old,delta],axis=0)
    if ids[:len(old_ids)].tobytes()!=old_ids.tobytes() or vectors[:len(old_ids)].tobytes()!=old.tobytes():raise ValueError('Old prefix changed at the bit level')
    if vectors[len(old_ids):].tobytes()!=delta.tobytes():raise ValueError('Delta tail changed at the bit level')
    return ids,vectors
def clone_spec(spec,binding_path,binding_sha):
    if spec.get('is_template') is not False or spec.get('protein_mode')!='frozen_esm2':raise ValueError('Only actual frozen ESM2 feature specifications accepted')
    new=dict(spec,protein_cache_binding=str(binding_path),protein_cache_binding_sha256=binding_sha)
    keys={'protein_cache_binding','protein_cache_binding_sha256'}
    if {k:v for k,v in spec.items() if k not in keys}!={k:v for k,v in new.items() if k not in keys}:raise ValueError('Chemical definition changed')
    return new
def validate_exclusions(parent,cohort,out,old_keys,new_keys):
    source={r['row_id']:r for r in rows(parent)};retained=rows(cohort);retained_ids={r['row_id'] for r in retained}
    added=[];excluded=[]
    for rid,r in source.items():
        key=hashlib.sha256(r['target_sequence'].encode()).hexdigest()
        if rid in retained_ids:
            if key not in old_keys and key in new_keys:
                if r['evaluation_stratum']=='standard20_control':raise ValueError('Unexpected standard-control addition; old paired-AA coverage lineage differs')
                added.append({'row_id':rid,'split':r['split'],'evaluation_stratum':r['evaluation_stratum'],'target_sha256':key})
        else:
            if len(r['target_sequence'])<=2048 or key in new_keys or not set(r['target_sequence']).issubset(AA):raise ValueError('Unexpected expanded-cohort exclusion')
            excluded.append({'row_id':rid,'split':r['split'],'evaluation_stratum':r['evaluation_stratum'],'target_sha256':key,'target_residues':len(r['target_sequence']),'reason':'target_exceeds_original_2048_residue_limit_not_encoded_no_truncation'})
    # Reuse reviewed metadata filtering and verify every retained ID/role/group/label pointwise.
    for r in retained:
        original=source[r['row_id']]
        if r['split']!=original['split'] or r['global_group_id']!=original['global_group_id'] or float(r['label'])!=float(original['label']):raise ValueError('Retained role/group/label changed')
    csvout(out/'ADDED-OBSERVATIONS.metadata.csv',added,['row_id','split','evaluation_stratum','target_sha256'])
    csvout(out/'UNENCODED-TARGET-EXCLUSIONS.metadata.csv',excluded,['row_id','split','evaluation_stratum','target_sha256','target_residues','reason'])
    return {'parent_rows':len(source),'retained_rows':len(retained),'added_observations':len(added),'excluded_rows':len(excluded),'excluded_unique_targets':len({r['target_sha256'] for r in excluded}),'numeric_labels_used_for_filtering':False,'retained_ID_role_group_labels_unchanged':True}

def main():
    p=argparse.ArgumentParser();p.add_argument('--contract',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--spec-output',type=Path,required=True);p.add_argument('--max-seconds',type=int,default=180);a=p.parse_args();start=time.monotonic();contract=read(a.contract)
    if contract.get('schema')!='peptide.protein-cache-expanded.metadata-contract.v1' or contract.get('is_template') is not False:raise ValueError('Actual frozen metadata contract required')
    if contract.get('producer_sha256')!=sha(__file__):raise ValueError('Metadata producer bytes differ from frozen contract')
    paths={}
    for key,item in contract['inputs'].items():
        path=Path(item['path'])
        if sha(path)!=item['sha256']:raise ValueError('Input changed: '+key)
        paths[key]=path
    if sha(paths['delta_review'])!=DELTA_GO_SHA or sha(paths['old_npz'])!=OLD_NPZ_SHA or sha(paths['delta_npz'])!=DELTA_NPZ_SHA or sha(paths['parent_global_manifest'])!=GLOBAL_SHA or sha(paths['cohort_producer'])!=COHORT_PRODUCER_SHA:raise ValueError('Actual scientific source identities differ')
    go=read(paths['delta_review']);old_receipt=read(paths['old_receipt']);delta_receipt=read(paths['delta_receipt']);old_binding=read(paths['old_binding'])
    if go.get('valid') is not True or go.get('errors') or go['new_key_overlap_old']!=0 or go['new_delta_shape']!=[47,320]:raise ValueError('Delta independent acceptance missing')
    for receipt in (old_receipt,delta_receipt):
        if receipt.get('status')!='succeeded' or receipt.get('canary') or receipt.get('model_sha256')!=MODEL_SHA or receipt.get('layer')!=6 or receipt.get('no_truncation') is not True:raise ValueError('ESM extraction identity differs')
    for key in ('pooling','esm_source_hashes','frozen_parameter_count'):
        if old_receipt.get(key)!=delta_receipt.get(key):raise ValueError('Original layer/pool/source identity changed: '+key)
    if old_receipt['pooling']!='mean exact residue positions1..L; excludes BOS/EOS/pad' or any(r.get('max_residues',0)>2048 for r in (old_receipt,delta_receipt)):raise ValueError('Original full-sequence residue limit/pool policy changed')
    if sha(paths['extractor_source'])!=EXTRACTOR_SHA:raise ValueError('Original ESM extraction code identity changed')
    if old_binding['embedding_sha256']!=OLD_NPZ_SHA or old_binding['receipt_sha256']!=sha(paths['old_receipt']) or old_binding['shape']!=[5159,320]:raise ValueError('Original cache binding differs')
    old_ids,old=load_arrays(paths['old_npz']);new_ids,delta=load_arrays(paths['delta_npz'])
    if old.shape!= (5159,320) or delta.shape!=(47,320) or set(map(str,new_ids))!=set(go['new_keys']):raise ValueError('Actual old/delta coverage differs')
    ids,matrix=merge_arrays(old_ids,old,new_ids,delta)
    for d in (a.output,a.spec_output):
        if d.exists():raise ValueError('Use new output/spec directories; preserve partial outputs')
    a.output.mkdir(parents=True);a.spec_output.mkdir(parents=True);cache=a.output/'merged-cache';cache.mkdir();np.savez_compressed(cache/'embeddings.npz',sequence_ids=ids,embeddings=matrix)
    read_ids,read_matrix=load_arrays(cache/'embeddings.npz')
    if read_ids.tobytes()!=ids.tobytes() or read_matrix.tobytes()!=matrix.tobytes():raise ValueError('Saved merged vectors changed')
    receipt={'status':'succeeded','canary':False,'cache_origin':'immutable5159_append_actual47_metadata_merge','sequence_count':len(ids),'shape':list(matrix.shape),'dtype':'float32','fit_count':0,'label_files_opened_during_merge':0,'label_values_used_for_merge_or_filtering':False,'no_truncation':True,'max_allowed_residues':2048,'chemical_identity_encoded':False,'model_sha256':MODEL_SHA,'layer':6,'pooling':old_receipt['pooling'],'esm_source_hashes':old_receipt['esm_source_hashes'],'frozen_parameter_count':old_receipt['frozen_parameter_count'],'extraction_contract_sha256':old_binding['extraction_contract_sha256'],'merge_contract_sha256':sha(a.contract),'merge_producer_sha256':sha(__file__),'embedding_sha256':sha(cache/'embeddings.npz'),'old_prefix_bitwise_equal':True,'old_prefix_FP32_cells_checked':int(old.size),'delta_tail_bitwise_equal':True,'old_npz_sha256':OLD_NPZ_SHA,'delta_npz_sha256':DELTA_NPZ_SHA,'delta_receipt_sha256':sha(paths['delta_receipt']),'delta_review_sha256':DELTA_GO_SHA,'pure_delta_input_sha256':go['pure_input_sha256'],'new_NN_forwards':0,'gpu_used_for_merge':False}
    receipt.update(original_extractor_source_sha256=EXTRACTOR_SHA,old_receipt_sha256=sha(paths['old_receipt']),delta_extraction_contract_sha256=delta_receipt.get('contract_sha256'),runtime_lineage={'old':{k:old_receipt.get(k) for k in ('python','torch','esm_version')},'delta':{k:delta_receipt.get(k) for k in ('python','torch','esm_version')}},max_residues=max(old_receipt.get('max_residues',0),delta_receipt.get('max_residues',0)))
    write(cache/'receipt.json',receipt)
    binding=dict(old_binding,directory='merged-cache',embedding_sha256=receipt['embedding_sha256'],receipt_sha256=sha(cache/'receipt.json'),shape=list(matrix.shape),head_fit_count_at_binding=0,merge_contract_sha256=sha(a.contract),merge_producer_sha256=sha(__file__),delta_independent_review_sha256=DELTA_GO_SHA)
    write(a.output/'feature-cache-binding.json',binding);specs=[];spec_proof=[]
    for item in contract['feature_specs']:
        original=Path(item['path'])
        if sha(original)!=item['sha256']:raise ValueError('Original chemical feature spec changed')
        target=a.spec_output/original.name;new=clone_spec(read(original),(a.output/'feature-cache-binding.json').resolve(),sha(a.output/'feature-cache-binding.json'));write(target,new);specs.append(target);spec_proof.append({'old_path':str(original),'old_sha256':item['sha256'],'new_path':str(target),'new_sha256':sha(target),'only_changed_keys':['protein_cache_binding','protein_cache_binding_sha256']})
    if len(specs)!=4 or len({p.name for p in specs})!=4:raise ValueError('Four distinct frozen representations required')
    write(a.output/'SPEC-CLONE-PROOF.actual.json',{'chemical_definitions_unchanged':True,'specs':spec_proof})
    if time.monotonic()-start>=a.max_seconds:raise TimeoutError('Metadata budget exhausted before cohort freeze')
    argv=[sys.executable,'-B',str(paths['cohort_producer']),'--manifest',str(paths['parent_global_manifest']),'--output',str(a.output/'cohort'),'--max-seconds',str(max(1,int(a.max_seconds-(time.monotonic()-start))))]
    for spec in specs:argv+=['--feature-spec',str(spec)]
    with (a.output/'cohort.stdout.log').open('xb') as stdout,(a.output/'cohort.stderr.log').open('xb') as stderr:
        subprocess.run(argv,stdout=stdout,stderr=stderr,check=True,timeout=max(1,a.max_seconds-(time.monotonic()-start)))
    frozen=read(a.output/'cohort/frozen-manifest.json');views=frozen['views'];ready=[v for v in views if v.get('training_ready') and v.get('status')=='frozen'];blocked=[v for v in views if not v.get('training_ready')]
    if len(ready)!=1 or not blocked or any(v.get('training_ready') for v in blocked):raise ValueError('Source blocked/one target boundary changed')
    source=Path(paths['parent_global_manifest']).parent/'target/fine_affinity.csv';frozen_csv=Path(ready[0]['path']);extra=validate_exclusions(source,frozen_csv,a.output,set(map(str,old_ids)),set(map(str,ids)))
    if extra['added_observations']!=go['added_rows'] or extra['excluded_rows']!=go['excluded_long_rows'] or extra['excluded_unique_targets']!=go['excluded_long_unique_targets'] or ready[0]['split_counts']!=go['potential_expanded_counts_from_actual_keys']:raise ValueError('Computed actual cohort differs from the accepted delta input-only coverage proof')
    old_unchanged=sha(paths['old_npz'])==OLD_NPZ_SHA
    if not old_unchanged:raise ValueError('Original cache unexpectedly changed')
    result={'schema':'peptide.protein-cache-expanded.actual-build.v1','status':'metadata_frozen_pending_independent_review','at_utc':datetime.now(timezone.utc).isoformat(),'producer_sha256':sha(__file__),'contract_sha256':sha(a.contract),'merged_shape':list(matrix.shape),'merged_npz_sha256':receipt['embedding_sha256'],'new_binding_sha256':sha(a.output/'feature-cache-binding.json'),'old_prefix_bitwise_equal':True,'old_prefix_FP32_cells_checked':int(old.size),'old_source_bytes_unchanged':old_unchanged,'delta_review_sha256':DELTA_GO_SHA,'specs':spec_proof,'parent_global_manifest_sha256':GLOBAL_SHA,'new_cohort_manifest_sha256':sha(a.output/'cohort/frozen-manifest.json'),'new_cohort_csv_sha256':sha(frozen_csv),'actual_split_counts':ready[0]['split_counts'],'coverage':extra,'new_fits':0,'new_predictions':0,'new_NN_forwards':0,'seconds':time.monotonic()-start}
    write(a.output/'BUILD-RESULT.actual.json',result);print(json.dumps(result,ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
