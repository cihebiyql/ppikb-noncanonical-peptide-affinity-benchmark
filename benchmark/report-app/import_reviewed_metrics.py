"""Import only root-reviewed aggregate CSV/JSON; never generate performance rows.

Does not read JSONL, labels, per-record predictions or checkpoints, and does not
build, infer, score or publish. Keep artifact identity and unrelated evidence.
"""
from pathlib import Path
import argparse,json,csv,hashlib,math,datetime
P=Path(__file__).resolve().parent
REQUIRED=['method_id','panel_id','regime_id','chemistry_id','evaluation_set_id','metric_id','mean','sd','n','seed_count']
PANELS={'source_peptide_dependency_cold':'来源＋肽依赖冷','target_reference_homology_cold':'参考蛋白同源冷'}
REGIMES={'NC_only':'只用非标准肽训练','standard_only':'只用标准肽训练'}
CHEMISTRY={'synthetic_D_backbone':'非蛋白源／D型／骨架改变','PTM':'PTM残基修饰','synthetic_and_PTM':'两类同时出现','other_NC':'其他非标准残基','standard20_control':'标准20残基对照','NC_all':'全部非标准肽','all':'全部化学组'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--summary',required=True);ap.add_argument('--review-manifest',required=True);a=ap.parse_args()
 summary=Path(a.summary);reviewpath=Path(a.review_manifest)
 if summary.suffix.lower() not in {'.csv','.json'} or any(t in summary.name.lower() for t in ['prediction','checkpoint','gold','label']):raise ValueError('Only reviewed aggregate CSV/JSON allowed; labels, predictions and checkpoints excluded')
 review=json.loads(reviewpath.read_text(encoding='utf-8-sig'))
 if review.get('kind')!='reviewed_aggregate_performance' or review.get('reviewed') is not True or review.get('independently_recomputed') is not True or review.get('all_required_selections_frozen') is not True:raise ValueError('Root review, independent arithmetic and selection barrier must be complete')
 if review.get('summary_sha256')!=sha(summary):raise ValueError('Summary SHA not bound to root review')
 if summary.suffix.lower()=='.csv':
  with summary.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
 else:
  loaded=json.loads(summary.read_text(encoding='utf-8-sig'));rows=loaded.get('rows') if isinstance(loaded,dict) else loaded
 if not isinstance(rows,list):raise ValueError('Summary must contain rows')
 normalized=[];seen=set()
 for source in rows:
  if not isinstance(source,dict) or not set(REQUIRED)<=set(source):raise ValueError('Missing required aggregate fields')
  row={k:source[k] for k in REQUIRED}
  if row['panel_id'] not in PANELS or row['regime_id'] not in REGIMES or row['chemistry_id'] not in CHEMISTRY:raise ValueError('Unknown evaluation scope; revise reviewed schema explicitly')
  if row['metric_id'] not in {'MAE','RMSE','Pearson','Spearman','R2'}:raise ValueError('Unknown metric')
  if not str(row['method_id']).strip() or not str(row['evaluation_set_id']).strip():raise ValueError('Method and evaluation set IDs required')
  for k in ['mean','sd']:
   if row[k] in [None,'','null','NA','undefined']:row[k]=None
   else:
    row[k]=float(row[k])
    if not math.isfinite(row[k]):raise ValueError('Use null for undefined metrics')
  if row['sd'] is not None and row['sd']<0:raise ValueError('Negative SD')
  for k in ['n','seed_count']:
   value=float(row[k])
   if not value.is_integer() or value<0:raise ValueError('Invalid denominator')
   row[k]=int(value)
  if row['seed_count']>10:raise ValueError('This contract has 10 seeds')
  key=tuple(row[k] for k in REQUIRED[:6])
  if key in seen:raise ValueError('Duplicate summary key')
  seen.add(key);row.update(panel_label=PANELS[row['panel_id']],regime_label=REGIMES[row['regime_id']],chemistry_label=CHEMISTRY[row['chemistry_id']]);normalized.append(row)
 datafile=P/'app/src/data.json';snapshot=json.loads(datafile.read_text(encoding='utf-8'))
 history=P/'reviewed-import-history';history.mkdir(exist_ok=True);stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
 (history/(stamp+'-previous-data.json')).write_bytes(datafile.read_bytes())
 query=snapshot['queries']['metrics'];query['rows']=normalized;query['source']={'label':'root独立核算并审阅的性能汇总','files':[{'name':summary.name,'sha256':sha(summary)},{'name':reviewpath.name,'sha256':sha(reviewpath)}],'metricDefinitions':[{'label':'聚合性能指标','definition':'预声明评价scope内10训练种子的指标均值和样本标准差；n为当前行测试分母，seed_count如实保留实际可用种子数量。空值不变成0。','componentIds':['metrics-table']}],'evidenceFlow':[{'title':'独立核算与选择冻结','detail':'review-manifest验证reviewed、independently_recomputed、all_required_selections_frozen均为true，SHA与汇总一致。'},{'title':'导入边界','detail':'只读聚合CSV/JSON；没有加载原始金标、逐样本预测或模型权重。'}]}
 snapshot['researchMetadata']['performanceRows']=len(normalized);snapshot['buildStatus']='updating';snapshot['generatedAt']=datetime.datetime.now(datetime.timezone.utc).isoformat()
 datafile.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'imported_rows':len(normalized),'app_id_preserved':snapshot['id'],'build_required':True,'published':False},ensure_ascii=False))
if __name__=='__main__':main()
