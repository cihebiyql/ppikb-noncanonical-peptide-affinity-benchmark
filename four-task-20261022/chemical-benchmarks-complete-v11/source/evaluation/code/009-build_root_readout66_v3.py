"""Direct Root readout from accepted expanded230 aggregate, no selection/fits."""
import argparse,csv,hashlib,json,runpy
from pathlib import Path
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--utility',required=True);ap.add_argument('--comparison',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();u=runpy.run_path(a.utility);j,proc=u['guard']();proof=json.loads(a.comparison.read_text(encoding='utf-8-sig'));assert proof['status']=='passed' and proof['model_configurations']==23 and proof['model_seed_units']==230 and proof['groups']==155 and proof['csv_sha256']==u['LABELS'];src=a.comparison.parent/'COMBINED-230-ten-seed-summary.actual.csv';assert sha(src)==proof['metric_file_hashes'][src.name]
 with src.open(encoding='utf-8-sig',newline='') as f:rr=list(csv.DictReader(f))
 assert len(rr)==230;idx={(q['method'],q['stratum']):q for q in rr};assert len(idx)==230
 full=['fullfine_hybrid','fullfine_mlm','fullfine_peptideclm2025'];et=[x+'__extra_trees' for x in ['hybrid','mlm','peptideclm2025','morgan']];mg=['morgan__'+x for x in ['constant','ridge','random_forest','extra_trees','hist_gradient_boosting']];methods=list(dict.fromkeys(full+et+mg));assert len(methods)==11;layers=[('all',685),('standard20_control',572),('synthetic_D_backbone',45),('PTM',41),('synthetic_and_PTM',20),('other_NC',7)];out=[]
 for method in methods:
  roles=';'.join([role for role,allowed in [('full_finetuning',full),('same_ExtraTrees',et),('all_five_Morgan',mg)] if method in allowed])
  for layer,n in layers:
   q=idx[(method,layer)];assert int(q['n'])==n and int(q['seeds'])==10;item={'comparison_groups':roles,**q};item['MAE_mean_plus_sampleSD']=f"{float(q['mae_mean']):.5f} ± {float(q['mae_sampleSD']):.5f}";out.append(item)
 assert len(out)==66 and len({(q['method'],q['stratum']) for q in out})==66;assert not a.output.exists();a.output.mkdir(parents=True);p=a.output/'ROOT-REVIEW-66-config-stratum.actual.csv'
 with p.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
 receipt={'schema':'expanded230.Root-readable66-subset.v1','status':'PASS','comparison_sha256':sha(a.comparison),'source_summary_sha256':sha(src),'source_sha256':sha(__file__),'readout_sha256':sha(p),'unique_configurations':11,'chemical_layers':6,'rows':66,'seeds_per_row':10,'Morgan_ExtraTrees_shared_between_two_comparison_groups':True,'TEST_used_for_configuration_selection':False,'complete23_config10layer_tables_retained_in_parent_comparison':True,'limitations':['Fullfine and frozen heads have different computation and capacity.','Ten seed SD is computational repetition, not biological replication.'],'NN':0,'fit':0,'process':proc};r=a.output/'ROOT-REVIEW-66-INDEPENDENT.actual.json';r.write_text(json.dumps(receipt,indent=2)+chr(10));print(json.dumps({'csv':str(p),'csv_sha256':sha(p),'receipt':str(r),'receipt_sha256':sha(r)}))
if __name__=='__main__':main()
