"""Declared reference-similarity plus explicit shared-domain warnings only."""
from pathlib import Path
from collections import Counter
from difflib import SequenceMatcher
import json,hashlib,os,resource,time
from Bio import Align,__version__ as bioversion
from Bio.Align import substitution_matrices
HERE=Path(__file__).resolve().parent
def main():
 resource.setrlimit(resource.RLIMIT_CPU,(120,120));resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3));os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});os.nice(19)
 start=time.time();d=json.loads((HERE/'target-reference-and-main-inputs.json').read_text());q=d['query_heavy_reference'];targets=d['main_reference_targets'];al=Align.PairwiseAligner();al.mode='local';al.substitution_matrix=substitution_matrices.load('BLOSUM62');al.open_gap_score=-10;al.extend_gap_score=-.5
 related=[];shared=[]
 for t in targets:
  key=hashlib.sha256(t.encode()).hexdigest()[:20]
  exact=len(t)>=40 and (q in t or t in q)
  if exact:related.append({'target_ref_hash':key,'reason':'exact_sequence_or_domain_containment','identity':1.});continue
  longest=SequenceMatcher(None,q,t,autojunk=False).find_longest_match();
  if longest.size>=80:shared.append({'target_ref_hash':key,'reason':'long_exact_shared_domain_warning_separate_from_frozen_full_reference_rule','shared_exact_segment_length':longest.size})
  if min(len(q),len(t))<.8*max(len(q),len(t)):continue
  ac,bc=Counter(q),Counter(t)
  if sum(min(ac[k],bc[k]) for k in ac)<.24*max(len(q),len(t)):continue
  best=al.align(q,t)[0];blocks=best.aligned;paired=sum(int(y-x) for x,y in blocks[0]);
  if not paired or paired/len(q)<.8 or paired/len(t)<.8:continue
  matches=sum(sum(x==y for x,y in zip(q[int(sa):int(ea)],t[int(sb):int(eb)])) for (sa,ea),(sb,eb) in zip(*blocks));identity=matches/paired
  if identity>=.3:related.append({'target_ref_hash':key,'reason':'declared_BLOSUM62_local','identity':identity,'query_coverage':paired/len(q),'target_coverage':paired/len(t)})
 report={'query_heavy_reference_sha256':d['query_reference_sha256'],'main_reference_targets_checked':len(targets),'Bio_version':bioversion,'threshold_identity':.3,'threshold_both_coverage':.8,'local_gap_open':-10,'local_gap_extend':-.5,'related_main_target_refs':related,'additional_shared_domain_warnings':shared,'reference_cold_under_frozen_rule':not related,'family_cold_certified':False,'shared_Fc_domain_must_not_be_called_unseen_if_shared_segment_present':True,'wall_seconds':time.time()-start,'labels_read':False,'GPU_used':False,'PID':os.getpid()}
 (HERE/'supplement-target-reference-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ('related_main_target_refs','additional_shared_domain_warnings')},ensure_ascii=False))
if __name__=='__main__':main()
