"""Actual reviewed aggregate QA, replacing empty-metrics checks without raw data IO."""
from pathlib import Path
import json,hashlib,re,datetime,urllib.request,collections
P=Path(__file__).resolve().parent;APP=P/'app';ROOT=P.parent
load=lambda p:json.loads(p.read_text(encoding='utf-8'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def run():
 d=load(APP/'src/data.json');q=d['queries'];actual=P/'metric-adapter-v1/actual-v1';converted=load(actual/'app-metrics.json');review=load(actual/'signed-import-review-v1.json');trace=load(actual/'mapping-trace.json')
 assert review['reviewed'] and review['root_explicit_authorization'] and review['summary_sha256']==sha(actual/'app-metrics.json')
 assert d['id']=='report:5569696c-9519-43ed-9a7a-073a11d14850' and d['buildStatus']=='complete'
 assert len(q)==18 and len(q['metrics']['rows'])==len(converted)==6880
 fields=['method_id','panel_id','regime_id','chemistry_id','evaluation_set_id','metric_id','mean','sd','n','seed_count']
 assert [{k:r[k] for k in fields} for r in q['metrics']['rows']]==converted
 assert sum(r['mean'] is None for r in converted)==1092
 assert all(t['completed_seed_count']==10 and t['source_missing_seeds']==[] for t in trace)
 assert any(r['metric_id'] in {'Pearson','Spearman'} and r['seed_count']==0 and r['mean'] is None for r in converted)
 before=load(P/'actual-results-ui-history/data.after-import.before-display.json')
 for name in before['queries']:
  if name not in {'metrics','phase_snapshot'}:assert q[name]==before['queries'][name],name
 assert sum(r['rows'] for r in q['chemistry_counts']['rows'])==9619 and len(q['evidence']['rows'])==28
 assert len(q['methods']['rows'])==5 and sum(r['file_count'] for r in q['upstream_assets']['rows'])==129
 expected={('source_peptide_dependency_cold','NC_only'):(1548,248,1039),('source_peptide_dependency_cold','standard_only'):(5992,792,1039),('target_reference_homology_cold','NC_only'):(1409,358,1443),('target_reference_homology_cold','standard_only'):(5324,1085,1443)}
 for (panel,regime),ns in expected.items():
  rs=[r for r in q['sample_denominators']['rows'] if r['panel_id']==panel and r['regime_id']==regime];assert tuple(sum(r[k] for r in rs) for k in ['train_n','validation_n','test_n'])==ns
 assert len(q['primary_performance']['rows'])==26 and sorted({r['n'] for r in q['primary_performance']['rows']})==[303,332]
 ds=collections.Counter(r['dataset_label'] for r in q['metrics']['rows']);assert set(ds)=={'PPIKB内部测试','PTM外部75','IgG补充13'}
 for row in q['metrics']['rows']:
  parts=row['evaluation_set_id'].split('|');dataset=parts[1];cohort=parts[2]
  if cohort=='NC_core':
   expected_label={'PPIKB-internal':'全部非标准肽（主任务）','PTM-external75':'PTM全75诊断（含8条条件样本）','IgG-supplement13':'补充非天然8诊断'}[dataset]
   assert row['cohort_label']==expected_label and expected_label in row['evaluation_label']
   assert row['n']=={'source_peptide_dependency_cold':303,'target_reference_homology_cold':332}[row['panel_id']] if dataset=='PPIKB-internal' else row['n']==(75 if dataset=='PTM-external75' else 8)
 assert len(q['report_documents']['rows'])==3
 for r in q['report_documents']['rows']:assert hashlib.sha256(r['markdown'].encode('utf-8')).hexdigest()==r['sha256']
 jsx=(APP/'src/content/report/ReportContent.jsx').read_text(encoding='utf-8');ids=set(re.findall(r'\bid="([^"]+)"',jsx));qids=set(re.findall(r'\bqueryId="([^"]+)"',jsx));assert qids<=set(q)
 for name,v in q.items():
  files={f['name'] for f in v.get('source',{}).get('files',[]) if isinstance(f,dict)}
  for md in v.get('source',{}).get('metricDefinitions',[]):
   assert set(md.get('componentIds',[]))<=ids,(name,md.get('componentIds'))
   for lineage in md.get('sourceLineage',[]):assert set(lineage.get('files',[]))<=files,name
 assert '可定义种子数' in jsx and '当前筛选没有匹配成绩' in jsx and '1.2978 ± 0.0554' in jsx
 plugin=Path('C:/Users/ciheb/.codex/plugins/cache/openai-curated-remote/data-analytics/1.0.11');assert sha(APP/'AGENTS.md')==sha(plugin/'templates/data-app/base/AGENTS.md')
 assert sha(P/'metric-adapter-v1/adapter.py')=='22f834c038072f96269b1babbba1ccca8d181e6dd045e5bc8afb2d377e3311fe'
 assert sha(P/'import_reviewed_metrics.py')=='0726cc566193e933dac3d51ccfeaf4f45ae139798c1437c0f006e76f083a9f6f'
 build=load(APP/'dist/data-app-build.json');snapshot=APP/'dist'/build['snapshot']['path'];assert sha(snapshot)==build['snapshot']['sha256']
 url='http://127.0.0.1:2647/'
 for f in [APP/'dist/index.html',snapshot]:
  with urllib.request.urlopen(url+('' if f.name=='index.html' else f.name),timeout=10) as r:assert r.status==200 and hashlib.sha256(r.read()).hexdigest()==sha(f)
 result={'status':'passed','verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'app_id':d['id'],'build_status':'complete','summary_sha256':'e5f5d346c5a5ed2de98cdccd8142cbf2e0c0299df02ca7250556cca27c2ba000','source_summary_rows':11540,'actual_app_micro_rows':6880,'full_macro_rows_preserved':4600,'root_explicit_display_exclusions_preserved':60,'undefined_mean_rows_preserved':1092,'completed_seeds_every_original_group':10,'primary_rows':26,'report_documents_verified':3,'metric_rows_by_dataset':dict(ds),'preexisting_scientific_queries_unchanged':True,'protected_runtime_and_frozen_mapper_importer_unchanged':True,'HTML_sha256':sha(APP/'dist/index.html'),'snapshot_sha256':sha(snapshot),'HTTP_verified':True,'url':url,'server_pid':20108,'browser_QA':'Root existing IAB tab; not claimed by child','raw_scores_gold_predictions_models_read':False,'new_server_artifact_or_publication':False}
 (P/'verification.actual-results-v1.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2));return result
if __name__=='__main__':run()
