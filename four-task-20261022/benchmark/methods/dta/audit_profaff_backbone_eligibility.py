"""Metadata-only eligibility for a conditional unmodified-L-core ablation. No forward or new chemistry."""
from pathlib import Path
import collections,csv,hashlib,json
R=Path(__file__).resolve().parents[2];H=R/'methods/dta/profaff-backbone-ablation-eligibility';H.mkdir(exist_ok=True)
source=R/'data/profaff-expansion-20261023/holdup-standard-core-no-FP-no-PPIKB-overlap-external.csv';side=R/'runs/profaff-HU-external-v1/backbone-ablation-preparation/backbone-ablation-sidecar.csv'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
source_sha=sha(source)
assert source_sha=='9f9a82b460e690a8b32afbe7da0170c0c80c21a9f8a38c5a715c642c7253b314'
assert sha(side)=='6ead4146caba912be28508d62404d5c81b4387277e1d3214e5acbfb5c91b8893'
with source.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
with side.open(encoding='utf-8-sig',newline='') as f:ab=list(csv.DictReader(f))
original={x['row_id']:x for x in rows};assert len(original)==len(rows)==len(ab)==16806
assert len({x['parent_row_id'] for x in ab})==len(ab)
alphabet=set('ACDEFGHIKLMNPQRSTVWY');invalid=[];joined=[]
for x in ab:
 a=original[x['parent_row_id']]
 assert x['peptide_sequence']==a['peptide_sequence'] and x['smiles_role']=='unmodified_L_backbone_ablation_not_actual_assay_chemical_identity'
 assert not x['actual_assay_smiles'] and x['original_SMILES_reconstructed']=='False'
 assert x['source_HU_view_sha256']==source_sha
 if not a['target_sequence'] or set(a['target_sequence'])-alphabet:invalid.append(a['row_id'])
 joined.append({'row_id':a['row_id'],'target_sequence_sha256':hashlib.sha256(a['target_sequence'].encode()).hexdigest(),'target_length':len(a['target_sequence']),'peptide_sequence_sha256':x['sequence_sha256'],'ablation_smiles_sha256':hashlib.sha256(x['backbone_ablation_smiles'].encode()).hexdigest(),'label_kind':a['label_kind'],'smiles_role':x['smiles_role']})
methods=[]
for method in ['GraphDTA-GIN','MGraphDTA','DGDTA-CL','DeepNC-GEN','GS-DTA']:
 limit=1200 if method=='MGraphDTA' else 1000
 methods.append({'method_id':method,'candidate_rows':len(joined)-len(invalid),'invalid_target_rows':len(invalid),'protein_limit':limit,'target_rows_over_limit':sum(x['target_length']>limit for x in joined),'role':'conditional unmodified L-backbone ablation only','fit_executed':False,'forward_executed':False,'native_full_assay_chemistry_external_validation_eligible':False,'required_before_forward':['new explicitly conditional scope standard contract','frozen selected checkpoint/validation selection identity','author feature smoke in same RDKit runtime','never fill actual_assay_smiles with backbone ablation']})
report={'schema':'fourtask.profaff-L-backbone-metadata-eligibility.v1','source_sha256':sha(source),'sidecar_sha256':sha(side),'rows':len(rows),'unique_peptide_backbones':len({x['peptide_sequence'] for x in ab}),'unique_targets':len({x['target_sequence'] for x in rows}),'unique_source_groups':len({x['group_id'] for x in rows}),'target_lengths':{'minimum':min(x['target_length'] for x in joined),'maximum':max(x['target_length'] for x in joined)},'invalid_target_ids':invalid,'methods':methods,'endpoint_counts':dict(collections.Counter(x['endpoint'] for x in rows)),'limitations':['actual biotin/nonpeptide linker/terminal amide chemistry is omitted','target represents isolated domain source ancestry; original 2022 full fusion unverified','holdup-derived calibrated composite pKd is a distinct observation process','not evidence of nonnatural residue or PTM generalization','family independence and absence of pretrained target exposure are not asserted'],'scope':'metadata joins and hash/identity checks only; zero molecular feature encoding, zero model forward or fit'}
(H/'eligibility.json').write_text(json.dumps(report,indent=2),encoding='utf-8');(H/'joined-input-hash-index.json').write_text(json.dumps(joined),encoding='utf-8');print(json.dumps(report,indent=2))
