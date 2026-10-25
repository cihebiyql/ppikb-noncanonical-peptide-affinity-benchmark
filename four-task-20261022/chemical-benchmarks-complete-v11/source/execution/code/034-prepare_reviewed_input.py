"""Lossless metadata adapter for the independently verified homology-edge evidence."""
from pathlib import Path
import hashlib,json
H=Path(__file__).resolve().parent;R=H.parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def main():
    source=R/'reports/global-target-homology-role-extension-v1/REVIEWED-POSITIVE-EDGES.actual.json'
    assert sha(source)=='cd747503ba488e66d4d9d5106860353a8870be4e15d91ce61bfe7478d32d9a5a'
    original=read(source)
    assert original['schema']=='target-homology.reviewed-positive-edges.v1' and original['status']=='independently_verified' and original['positive_edge_count']==2
    assert original['parent_global_manifest_sha256']=='8825563afe9eedec17e940d06ba0f36ae6ddf1e5337ca1c1bdd4265f62a52582'
    review=read(original['review_path']);assert review['evidence_valid'] and not review['errors'] and review['checks']==56311 and review['actual_new_positive_edges']==2
    inputs={str(source):sha(source),str(Path(__file__)):sha(__file__)}
    def collect(value):
        if isinstance(value,dict):
            for k,p in value.items():
                if k.endswith('_path') and isinstance(p,str):
                    key=k[:-5]+'_sha256'
                    if key in value:
                        assert sha(p)==value[key],p;inputs[str(Path(p))]=value[key]
                collect(p)
        elif isinstance(value,list):
            for x in value:collect(x)
    collect(original);collect(review)
    pairs=[{'target_a_sha256':e['a'],'target_b_sha256':e['b'],'source_pair_id':e['pair_id'],'left_role':e['left_role'],'right_role':e['right_role'],'alignment':e['alignment']} for e in original['positive_edges']]
    assert all(x['left_role']=='validation' and x['right_role']=='external' for x in pairs)
    result={'schema':'peptide.reviewed-positive-target-edges.v1','source_reviewed_manifest_sha256':sha(source),'parent_global_manifest_sha256':original['parent_global_manifest_sha256'],'numeric_labels_used_for_edges':False,'positive_pairs':pairs,'alignment_definition':original['alignment_definition'],'candidate_scope':review['scientific_scope'],'actual_screened_unique_pairs':review['actual_new_unique_pairs'],'evidence_inputs':[{'path':p,'sha256':v} for p,v in sorted(inputs.items())]}
    destination=H/'reviewed-positive-edges.json'
    with destination.open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'path':str(destination),'sha256':sha(destination),'evidence_input_count':len(inputs)}))
if __name__=='__main__':main()
