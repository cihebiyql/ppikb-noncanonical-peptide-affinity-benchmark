"""Fixed local-alignment grouping, including exact domain containment edges.

Coverage is nongap residue-pair count / each full sequence length.
Length filtering is mathematically necessary for that declared coverage definition.
This is reference-sequence similarity, not a universal family annotation.
"""
import os,json,time,hashlib,argparse,resource,signal,socket
from pathlib import Path
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from Bio import Align,__version__ as bioversion
from Bio.Align import substitution_matrices
P=Path(__file__).resolve().parent
SEQ=[];ALIGNER=None
def init(sequences):
 global SEQ,ALIGNER
 SEQ=sequences;ALIGNER=Align.PairwiseAligner();ALIGNER.mode='local';ALIGNER.substitution_matrix=substitution_matrices.load('BLOSUM62');ALIGNER.open_gap_score=-10;ALIGNER.extend_gap_score=-.5
 os.nice(15);resource.setrlimit(resource.RLIMIT_CPU,(900,900))
def pair(job):
 i,j=job;a,b=SEQ[i],SEQ[j];aid=hashlib.sha256(a.encode()).hexdigest()[:20];bid=hashlib.sha256(b.encode()).hexdigest()[:20]
 if min(len(a),len(b))>=40 and (a in b or b in a):return {'a':aid,'b':bid,'link_type':'exact_sequence_or_domain_containment','identity':1.,'short_coverage':1.}
 if min(len(a),len(b)) < .8*max(len(a),len(b)):return None
 # Upper bound on exact matches in any alignment: residue-composition intersection.
 ac,bc=Counter(a),Counter(b)
 if sum(min(ac[k],bc[k]) for k in ac) < .24*max(len(a),len(b)):return None
 alignment=ALIGNER.align(a,b)[0];blocks=alignment.aligned
 paired=sum(int(y-x) for x,y in blocks[0])
 if not paired or paired/len(a)<.8 or paired/len(b)<.8:return None
 matches=sum(sum(x==y for x,y in zip(a[int(sa):int(ea)],b[int(sb):int(eb)])) for (sa,ea),(sb,eb) in zip(*blocks))
 identity=matches/paired
 if identity<.3:return None
 return {'a':aid,'b':bid,'link_type':'BLOSUM62_optimal_local','identity':identity,'paired_columns':paired,'query_coverage':paired/len(a),'target_coverage':paired/len(b),'score':alignment.score}
def readfasta(path):
 seq=[];s=''
 for line in path.read_text().splitlines():
  if line.startswith('>'):
   if s:seq.append(s);s=''
  else:s+=line.strip()
 if s:seq.append(s)
 return seq
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--canary',action='store_true');ap.add_argument('--workers',type=int,default=8);args=ap.parse_args()
 allseq=readfasta(P/'targets.fasta');mainset=set(allseq)
 if (P/'external-targets.fasta').exists():allseq+=readfasta(P/'external-targets.fasta')
 allseq=sorted(set(allseq));jobs=[];externaljobs=[]
 for i in range(len(allseq)):
  for j in range(i):
   a,b=allseq[i],allseq[j]
   if a not in mainset and b not in mainset:continue
   jobs.append((i,j))
 if args.canary:
  # Include worst length-product cases and a deterministic distributed sample.
  eligible=[x for x in jobs if min(map(len,(allseq[x[0]],allseq[x[1]])))>=.8*max(map(len,(allseq[x[0]],allseq[x[1]])))]
  ordered=sorted(eligible,key=lambda x:len(allseq[x[0]])*len(allseq[x[1]]),reverse=True)
  jobs=list(dict.fromkeys(ordered[:8]+[ordered[k*len(ordered)//40] for k in range(40)]))
 start=time.time();signal.alarm(960);resource.setrlimit(resource.RLIMIT_CPU,(920,920))
 filename='target-alignment-canary-pairs.jsonl' if args.canary else 'target-homology-pairs.jsonl';edges=0
 with (P/filename).open('w') as f,ProcessPoolExecutor(max_workers=args.workers,initializer=init,initargs=(allseq,)) as pool:
  for edge in pool.map(pair,jobs,chunksize=2 if args.canary else 32):
   if edge:f.write(json.dumps(edge)+'\n');edges+=1
 receipt={'host':socket.gethostname(),'Bio_version':bioversion,'workers':args.workers,'pairs_examined_or_mathematically_excluded':len(jobs),'positive_edges':edges,'main_sequences':len(mainset),'union_sequences':len(allseq),'wall_seconds':time.time()-start,'gpu_used':False,'labels_read':False,'mode':'canary' if args.canary else 'all_pairs','identity_definition':'exact matched residues / nongap paired columns','coverage_definition':'nongap paired columns / each full reference sequence length','threshold_identity':.3,'threshold_both_coverage':.8,'extra_positive_links':'exact sequence containment, shorter length >=40 aa','length_ratio_skip':'minimum_length / maximum_length <0.8 proves impossible for paired-column both coverage','composition_skip':'sum min amino acid counts <0.24*max length proves impossible','scoring':{'substitution_matrix':'BLOSUM62','local_open_gap':-10,'local_extend_gap':-.5,'alignment_selection':'first optimal alignment returned by frozen Bio version'},'claim_boundary':'declared full-reference similarity and exact domain containment; not a certified universal protein-family holdout'}
 (P/('target-alignment-canary-receipt.json' if args.canary else 'target-homology-runtime-receipt.json')).write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
