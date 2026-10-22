"""Controller-only train-ID extraction; explicitly discloses shared-label staging."""
from pathlib import Path
import hashlib
import json

HERE=Path(__file__).resolve().parent
FROZEN=HERE.parent/'data-protocol/frozen-v1'
OUTPUT=HERE/'canary-staging-v1'
EXPECTED='cc9575e305f9c9747e472407efe1e13a908b6ebba700990ca6b22d086c268fa2'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    if digest(FROZEN/'manifest.json')!=EXPECTED:raise ValueError('Frozen manifest changed')
    manifest=json.loads((FROZEN/'manifest.json').read_text(encoding='utf-8'))
    panel=manifest['primary_panels'][0]
    relative=f'splits/{panel}/NC_only/train-ids.json'
    if digest(FROZEN/relative)!=manifest['files'][relative]['sha256']:raise ValueError('Train IDs changed')
    train_ids=set(json.loads((FROZEN/relative).read_text(encoding='utf-8')))
    rows=[]
    for line in (FROZEN/'inputs.jsonl').open(encoding='utf-8'):
        row=json.loads(line)
        if row['record_id'] in train_ids:rows.append(row)
    rows.sort(key=lambda row:(len(row['canonical_isomeric_smiles']),row['record_id']))
    sample=[rows[(index*(len(rows)-1))//31] for index in range(32)]
    selected={row['record_id'] for row in sample}
    labels={}
    for line in (FROZEN/'labels.jsonl').open(encoding='utf-8'):
        row=json.loads(line)
        if row['record_id'] in selected:labels[row['record_id']]=row['pKd']
    OUTPUT.mkdir(exist_ok=False)
    path=OUTPUT/'train-only-32.jsonl'
    with path.open('w',encoding='utf-8',newline='\n') as handle:
        for row in sample:handle.write(json.dumps(dict(row,pKd=labels[row['record_id']]),ensure_ascii=False)+'\n')
    metadata=dict(panel=panel,regime='NC_only',n=32,train_sample_sha256=digest(path),allowed_train_ids=sorted(train_ids),
                  sample_ids=sorted(selected),smiles_lengths=[len(row['canonical_isomeric_smiles']) for row in sample],
                  protein_lengths=[len(row['target_sequence']) for row in sample],
                  sampling='32 empirical SMILES length quantiles, including min/max; label-free sampling',
                  frozen_manifest_sha256=EXPECTED,controller_opened_shared_label_container=True,
                  controller_pKd_values_used_only_for_32_train_ids=True,
                  fit_and_canary_receive_only_train_sample=True,
                  boundary='shared-container staging is disclosed; this is procedural separation, not OS security isolation')
    (OUTPUT/'sample-manifest.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in metadata.items() if k not in ['allowed_train_ids','sample_ids']}))

if __name__=='__main__':main()
