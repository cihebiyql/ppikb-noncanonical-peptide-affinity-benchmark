"""Label-free all-PPIKB chemical graph audit against existing external entities."""
from pathlib import Path
from collections import defaultdict
import hashlib,json,os,resource,socket,time
from rdkit import Chem,DataStructs,rdBase
from rdkit.Chem import rdFingerprintGenerator

HERE=Path(__file__).resolve().parent
def read(p):return [json.loads(l) for l in p.open(encoding='utf-8') if l.strip()]
def main():
    resource.setrlimit(resource.RLIMIT_CPU,(180,180));resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});os.nice(19)
    start=time.time();src=HERE/'all-PPIKB-label-free-molecules.jsonl';ext=HERE/'blind-inputs-with-certified-format-conversion.jsonl'
    main=read(src);external=read(ext);assert len(main)==21845
    cache={};byiso=defaultdict(list);byachiral=defaultdict(list);fg=rdFingerprintGenerator.GetMorganGenerator(radius=2,fpSize=2048,includeChirality=False)
    fps={};errors=[]
    for r in main:
        s=r['peptide_smiles']
        if s not in cache:
            m=Chem.MolFromSmiles(s)
            if m is None:errors.append(r['record_id']);continue
            iso=Chem.MolToSmiles(m,canonical=True,isomericSmiles=True);ach=Chem.MolToSmiles(m,canonical=True,isomericSmiles=False)
            cache[s]=(iso,ach);fps.setdefault(iso,fg.GetFingerprint(m))
        iso,ach=cache[s];byiso[iso].append(r['record_id']);byachiral[ach].append(r['record_id'])
    keys=sorted(fps);vectors=[fps[k] for k in keys];results=[]
    for r in external:
        if not r.get('peptide_smiles'):continue
        m=Chem.MolFromSmiles(r['peptide_smiles']);assert m is not None
        iso=Chem.MolToSmiles(m,canonical=True,isomericSmiles=True);ach=Chem.MolToSmiles(m,canonical=True,isomericSmiles=False)
        sims=DataStructs.BulkTanimotoSimilarity(fg.GetFingerprint(m),vectors)
        neighbors=[{'isomeric_graph_sha256':hashlib.sha256(keys[i].encode()).hexdigest(),'tanimoto':v,'record_ids':byiso[keys[i]]} for i,v in enumerate(sims) if v>=.8]
        results.append({'external_id':r['external_id'],'same_isomeric_graph_records':byiso.get(iso,[]),'same_achiral_graph_records':byachiral.get(ach,[]),'maximum_tanimoto':max(sims),'neighbors_ge_0_8':neighbors,'chemical_cold_against_entire_PPIKB_declared_rule':not neighbors and not byachiral.get(ach) and not byiso.get(iso)})
    with (HERE/'external-versus-all-PPIKB-chemical-overlap.jsonl').open('w',encoding='utf-8') as f:
        for r in results:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    summary={'host':socket.gethostname(),'rdkit':rdBase.rdkitVersion,'full_PPIKB_rows':len(main),'unique_raw_SMILES':len(cache),'unique_isomeric_graphs':len(keys),'parse_failures':errors,'external_graphs_tested':len(results),'external_exact_stereo_overlap_rows':sum(bool(r['same_isomeric_graph_records']) for r in results),'external_exact_achiral_overlap_rows':sum(bool(r['same_achiral_graph_records']) for r in results),'external_Morgan_neighbor_rows':sum(bool(r['neighbors_ge_0_8']) for r in results),'external_full_database_chemically_cold_rows':sum(r['chemical_cold_against_entire_PPIKB_declared_rule'] for r in results),'fingerprint':'Morgan radius2 2048bits achiral','threshold':.8,'input_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'external_sha256':hashlib.sha256(ext.read_bytes()).hexdigest(),'labels_read':False,'training':False,'GPU_used':False,'CPU_budget':1,'wall_seconds':time.time()-start,'process_id':os.getpid()}
    (HERE/'full-PPIKB-chemical-runtime-receipt.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary))
if __name__=='__main__':main()
