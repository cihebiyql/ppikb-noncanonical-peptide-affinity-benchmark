import csv,json,statistics,hashlib,datetime
from pathlib import Path
r=Path('reports/expanded-completion-20261025-v1')
p=Path('publication/chemical-benchmarks-complete-v11/data-component-v1/expanded-frozen.csv')
raw=p.read_bytes(); rows=list(csv.DictReader(raw.decode('utf-8').splitlines()))
assert hashlib.sha256(raw).hexdigest()=='c3d8f4e42600f0c762bb9d2d24595a32c8f13de7a1f5018d59047d241dd8525a'
out=[]
for split in ['fine_train','validation','test']:
 for st in ['overall','standard20_control','synthetic_D_backbone','PTM','synthetic_and_PTM','other_NC']:
  ys=[float(x['label']) for x in rows if x['split']==split and (st=='overall' or x['evaluation_stratum']==st)]
  out.append({'split':split,'stratum':st,'n':len(ys),'mean':statistics.mean(ys) if ys else None,'sample_SD':statistics.stdev(ys) if len(ys)>1 else None,'median':statistics.median(ys) if ys else None,'min':min(ys) if ys else None,'max':max(ys) if ys else None})
obj={'schema':'expanded-cohort-label-description.v1','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'csv_sha256':hashlib.sha256(raw).hexdigest(),'rows':out,'analysis_uses_labels_for_description_only':True,'new_fits':0,'no_model_or_HPO_selection':True}
(r/'DATASET-LABEL-DISTRIBUTIONS.actual.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2)+chr(10),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False))
