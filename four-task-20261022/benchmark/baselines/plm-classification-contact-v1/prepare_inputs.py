"""Freeze raw20 coverage and contact sequence-index proof before any model execution."""
import collections
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OLD=ROOT/'baselines/plm-simple-v1'
AA=frozenset('ACDEFGHIKLMNPQRSTVWY')
MAX_RESIDUES=2048

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def seqid(sequence):return hashlib.sha256(sequence.encode('ascii')).hexdigest()
def read(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(path,obj):Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def csv_write(path,rows):
    with Path(path).open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
def reject(sequence):
    if not sequence:return 'empty_sequence'
    if set(sequence)-AA:return 'non_AA20_raw_symbol'
    if len(sequence)>MAX_RESIDUES:return 'exceeds_declared_2048_compute_budget'
    return None

def main():
    inputs=HERE/'inputs';inputs.mkdir(exist_ok=True)
    source_manifest=ROOT/'data/view_manifest.json';manifest=json.loads(source_manifest.read_text(encoding='utf-8'))
    lookup={v['id']:v for v in manifest['views']}
    old_cache=OLD/'feature-cache-cpu-v3/embeddings.npz';old_receipt=OLD/'feature-cache-cpu-v3/receipt.json'
    prior=json.loads(old_receipt.read_text());assert sha(old_cache)==prior['embedding_sha256']
    cached=np.load(old_cache,allow_pickle=False);old_ids={key:i for i,key in enumerate(cached['sequence_ids'])}
    old_sequences={r['sequence_id']:r['sequence'] for r in map(json.loads,(OLD/'inputs/unique-sequences.jsonl').read_text().splitlines())}
    assert len(old_ids)==len(old_sequences)==5159
    means={};residues={};views=[];reports=[]
    cls=lookup['pepinter_classification_target_cold'];path=Path(cls['path']);assert sha(path)==cls['sha256']
    original=read(path);retained=[];coverage=[]
    for row in original:
        peptide,target=row['peptide_sequence_raw'],row['target_sequence']
        reasons=[field+':'+error for field,seq in [('peptide',peptide),('target',target)] if (error:=reject(seq))]
        coverage.append({'row_id':row['row_id'],'split':row['split'],'covered':not reasons,'reasons':reasons})
        if reasons:continue
        new=dict(row);new.update(embedding_peptide=peptide,embedding_target=target,chemical_identity_encoded='false')
        retained.append(new)
        means[seqid(peptide)]=peptide;means[seqid(target)]=target
    cls_id=cls['id']+'_esm2_raw20_len2048';destination=inputs/(cls_id+'.csv');assert not destination.exists();csv_write(destination,retained)
    write(inputs/(cls_id+'.coverage.json'),coverage)
    cls_view={**cls,'id':cls_id,'parent_view_id':cls['id'],'path':str(destination),'sha256':sha(destination),
        'rows':len(retained),'split_counts':dict(collections.Counter(r['split'] for r in retained)),
        'class_counts':{s:dict(collections.Counter(r['label'] for r in retained if r['split']==s)) for s in ['train','validation','test']},
        'parent_input_sha256':cls['sha256'],'chemical_identity_encoded':False,'label_meaning':'author positives and constructed negatives; not all measured nonbinding',
        'coverage_rule':'Exact supplied raw uppercase20AA, no normalization/projection/truncation;2048residues compute budget'}
    views.append(cls_view)
    classification_sequence_ids=set(means)
    reports.append({'id':cls_id,'original_rows':len(original),'eligible_rows':len(retained),'split_counts':cls_view['split_counts'],
        'class_counts':cls_view['class_counts'],'excluded_reasons':dict(collections.Counter(x for r in coverage for x in r['reasons']))})
    # Frozen sequence-only mapping provenance; no coordinates or geometry values are consumed.
    cview=lookup['ppikb_contact_experimental_64complex_dependency_cold_v2'];cpath=Path(cview['path']);assert sha(cpath)==cview['sha256']
    crows=read(cpath);complex_path=ROOT/'data/contact_expansion_v2/complexes.json'
    complexes={'pepbdb_'+r['directory']:r for r in json.loads(complex_path.read_text(encoding='utf-8'))}
    by_complex=collections.defaultdict(list)
    for row in crows:by_complex[row['structure_id']].append(row)
    proof=[];contact_rows=[];contact_coverage=[];complex_checks=[]
    for structure,group in sorted(by_complex.items()):
        errors=[];proven=[];meta=complexes.get(structure)
        if meta is None:errors.append('frozen_complex_sequence_provenance_missing')
        if meta:
            target,peptide,observed=meta['target_sequence'],meta['peptide_sequence'],meta['observed_target']
            count=target.count(observed);offset=target.find(observed)+1
            if count!=1:errors.append('observed_chain_not_unique_exact_substring')
            if offset!=meta['target_offset']:errors.append('frozen_target_offset_disagrees')
            indices=[int(r['residue_index']) for r in group]
            if sorted(indices)!=list(range(offset,offset+len(observed))):errors.append('observed_residue_coverage_not_exact')
            if len({r['split'] for r in group})!=1:errors.append('complex_crosses_frozen_split')
            for row in group:
                index=int(row['residue_index']);local=index-offset
                reasons=[field+':'+error for field,seq in [('peptide',row['peptide_sequence']),('target',row['target_sequence'])] if (error:=reject(seq))]
                if row['target_sequence']!=target or row['peptide_sequence']!=peptide or row['observed_target']!=observed:
                    reasons.append('row_and_frozen_complex_sequences_disagree')
                if not 1<=index<=len(target) or not 0<=local<len(observed):reasons.append('residue_index_out_of_frozen_sequence')
                if 1<=index<=len(target) and 0<=local<len(observed) and target[index-1]!=observed[local]:reasons.append('target_and_observed_residue_AA_disagree')
                if row['row_id']!='PPIKB_'+structure+':'+meta['target_chain']+':'+str(index):reasons.append('original_row_identity_or_index_disagrees')
                errors.extend(reasons)
                if not reasons:
                    proven.append({'row_id':row['row_id'],'structure_id':structure,'split':row['split'],'group_id':row['group_id'],
                        'target_sequence_id':seqid(target),'peptide_sequence_id':seqid(peptide),'residue_index1':index,
                        'target_residue_aa':target[index-1],'observed_chain_residue_aa':observed[local],
                        'observed_index1':local+1,'unique_observed_offset1':offset,'substring_occurrences':count,
                        'sequence_index_AA_equal':True})
        passed=not errors and len(proven)==len(group)
        complex_checks.append({'structure_id':structure,'rows':len(group),'passed':passed,'reasons':sorted(set(errors))})
        for row in group:
            contact_coverage.append({'row_id':row['row_id'],'structure_id':structure,'split':row['split'],'covered':passed,'reasons':sorted(set(errors))})
        if not passed:continue
        proof.extend(proven)
        for row,proven_row in zip(group,proven):
            # Deliberately omit all coordinates/distances and observed-region masks from the training view.
            columns=['row_id','source','split','peptide_sequence','target_sequence','label','endpoint','group_id','residue_index',
                     'structure_id','pdb_id','target_id','source_row_ids','source_studies','label_kind','evaluation_stratum']
            new={key:row[key] for key in columns}
            new.update(embedding_peptide=row['peptide_sequence'],embedding_target=row['target_sequence'],
                       target_residue_aa=proven_row['target_residue_aa'],sequence_index_mapping_verified='true',chemical_identity_encoded='false')
            contact_rows.append(new);means[seqid(row['peptide_sequence'])]=row['peptide_sequence']
            residues[seqid(row['target_sequence'])]=row['target_sequence']
    cid=cview['id']+'_esm2_residue_raw20_len2048';contact_destination=inputs/(cid+'.csv')
    assert not contact_destination.exists();csv_write(contact_destination,contact_rows)
    proof_path=inputs/'contact-sequence-index-proof.json';write(proof_path,proof)
    write(inputs/(cid+'.coverage.json'),contact_coverage)
    write(inputs/'contact-complex-index-checks.json',complex_checks)
    contact_view={**cview,'id':cid,'parent_view_id':cview['id'],'path':str(contact_destination),'sha256':sha(contact_destination),
        'rows':len(contact_rows),'complexes':len({r['structure_id'] for r in contact_rows}),
        'split_counts':dict(collections.Counter(r['split'] for r in contact_rows)),
        'complex_split_counts':{s:len({r['structure_id'] for r in contact_rows if r['split']==s}) for s in ['train','validation','test']},
        'parent_input_sha256':cview['sha256'],'index_proof_sha256':sha(proof_path),
        'index_proof_path':str(proof_path),'complex_sequence_provenance_path':str(complex_path),'complex_sequence_provenance_sha256':sha(complex_path),
        'feature_specification':'target layer6 residue at original1basedindex; peptide layer6 residue mean. No coordinates, distances, labels or observed-region masks as features.',
        'chemical_identity_encoded':False,'unmapped_rows':len(crows)-len(contact_rows)}
    views.append(contact_view);reports.append({'id':cid,'original_rows':len(crows),'eligible_rows':len(contact_rows),
        'complexes_eligible':contact_view['complexes'],'split_counts':contact_view['split_counts'],
        'mapping_failures':sum(not r['passed'] for r in complex_checks),'proof_rows':len(proof)})
    reused=[];jobs=[]
    for key,sequence in sorted({**means,**residues}.items()):
        existing=key in old_ids and key in means
        if existing:
            assert old_sequences[key]==sequence
            vector=np.asarray(cached['embeddings'][old_ids[key]],dtype=np.float32)
            reused.append({'sequence_id':key,'source_row_index':old_ids[key],
                'source_vector_sha256':hashlib.sha256(vector.tobytes()).hexdigest(),'length':len(sequence)})
        need_mean=key in means and not existing;need_residue=key in residues
        if need_mean or need_residue:
            jobs.append({'sequence_id':key,'sequence':sequence,'length':len(sequence),
                'need_mean':need_mean,'need_residue':need_residue,'existing_mean_preserved':existing,
                'priority':0 if key in classification_sequence_ids else 1})
    jobs.sort(key=lambda r:(r['priority'],r['sequence_id']))
    sequence_path=inputs/'missing-representations.jsonl'
    with sequence_path.open('w',encoding='utf-8',newline='\n') as f:
        for row in jobs:f.write(json.dumps(row)+'\n')
    requested_means=inputs/'requested-mean-sequences.jsonl'
    with requested_means.open('w',encoding='utf-8',newline='\n') as f:
        for key,sequence in sorted(means.items()):f.write(json.dumps({'sequence_id':key,'sequence':sequence,'length':len(sequence)})+'\n')
    write(inputs/'old-cache-reuse.json',{'old_cache_path':str(old_cache),'old_cache_sha256':sha(old_cache),
        'old_receipt_sha256':sha(old_receipt),'old_model_sha256':prior['model_sha256'],'vectors':reused,
        'old_cache_rows':5159,'reused_mean_vectors':len(reused),'source_cache_not_modified':True})
    result={'schema':'frozen-esm2.classification-contact.coverage.v1','parent_view_manifest_sha256':sha(source_manifest),
        'views':views,'reports':reports,'max_residues_compute_budget':2048,'model_api_hard_limit_claimed':False,
        'requested_mean_unique':len(means),'reused_mean_unique':len(reused),'missing_mean_unique':sum(r['need_mean'] for r in jobs),
        'required_residue_unique':len(residues),'missing_representation_forward_jobs':len(jobs),
        'missing_job_residues':sum(r['length'] for r in jobs),'missing_sequence_manifest_sha256':sha(sequence_path),
        'old_cache_sha256':sha(old_cache),'classification_and_contact_heads_separate':True,
        'labels_or_coordinates_in_extraction_manifest':False,'original_data_and_prior_results_modified':False}
    write(HERE/'coverage-manifest.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='views'},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
