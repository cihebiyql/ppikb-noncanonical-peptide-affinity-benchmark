"""Evidence/build checks for the aggregate-only application; no browser control."""
from pathlib import Path
import json,hashlib,re,urllib.request,datetime,subprocess,sys
P=Path(__file__).resolve().parent;APP=P/'app'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 data=json.loads((APP/'src/data.json').read_text(encoding='utf-8'));q=data['queries'];jsx=(APP/'src/content/report/ReportContent.jsx').read_text(encoding='utf-8')
 assert data['surface']=='report' and data['id']=='report:5569696c-9519-43ed-9a7a-073a11d14850'
 assert q['metrics']['rows']==[] and data['researchMetadata']['performanceRows']==0
 assert sum(r['rows'] for r in q['chemistry_counts']['rows'])==9619
 assert sum(r['rows'] for r in q['chemistry_counts']['rows'] if r['category']!='standard20_control')==2099
 assert len(q['methods']['rows'])==len({r['doi'] for r in q['methods']['rows']})==5
 expected={('source_peptide_dependency_cold','NC_only'):(1548,248,1039),('source_peptide_dependency_cold','standard_only'):(5992,792,1039),('target_reference_homology_cold','NC_only'):(1409,358,1443),('target_reference_homology_cold','standard_only'):(5324,1085,1443)}
 for (panel,regime),totals in expected.items():
  rs=[r for r in q['sample_denominators']['rows'] if r['panel_id']==panel and r['regime_id']==regime]
  assert tuple(sum(r[k] for r in rs) for k in ['train_n','validation_n','test_n'])==totals
 ids=set(re.findall(r'\bid="([^"]+)"',jsx));queryids=set(re.findall(r'\bqueryId="([^"]+)"',jsx))
 assert queryids<=set(q)
 for key,query in q.items():
  files={f['name'] if isinstance(f,dict) else f for f in query.get('source',{}).get('files',[])}
  for definition in query.get('source',{}).get('metricDefinitions',[]):
   assert set(definition.get('componentIds',[]))<=ids,(key,definition.get('componentIds'))
   for lineage in definition.get('sourceLineage',[]):assert set(lineage.get('files',[]))<=files
 assert len(q['evidence']['rows'])==28
 rf=q['rf_reference']['rows'][0];assert (rf['feature_dimension'],rf['n_estimators'],rf['selected_units'],rf['candidate_fits'],rf['n_jobs'])==(2469,200,40,80,1)
 text=json.dumps(data,ensure_ascii=False)
 assert not re.search(r'[A-Z]:\\|/root/|/mnt/|/data/qlyu/',text)
 plugin=Path(r'C:/Users/ciheb/.codex/plugins/cache/openai-curated-remote/data-analytics/1.0.11')
 assert sha(APP/'AGENTS.md')==sha(plugin/'templates/data-app/base/AGENTS.md')
 server=json.loads((P/'server-receipt.json').read_text(encoding='utf-8-sig'));url=server['url']
 with urllib.request.urlopen(url,timeout=5) as response:html=response.read();assert response.status==200
 assert hashlib.sha256(html).hexdigest()==sha(APP/'dist/index.html')
 build=json.loads((APP/'dist/data-app-build.json').read_text(encoding='utf-8'))
 latest=APP/'dist'/build['snapshot']['path'];assert sha(latest)==build['snapshot']['sha256']
 with urllib.request.urlopen(url+latest.name,timeout=5) as response:served=response.read();assert response.status==200
 assert hashlib.sha256(served).hexdigest()==sha(latest)
 # Unreviewed input must be refused before reading any actual summary.
 fixtures=P/'validation-fixtures';fixtures.mkdir(exist_ok=True);(fixtures/'unreviewed.json').write_text('{"kind":"reviewed_aggregate_performance","reviewed":false}',encoding='utf-8')
 before=sha(APP/'src/data.json');rejected=subprocess.run([sys.executable,str(P/'import_reviewed_metrics.py'),'--summary',str(fixtures/'not-present.csv'),'--review-manifest',str(fixtures/'unreviewed.json')],capture_output=True,text=True)
 assert rejected.returncode!=0 and sha(APP/'src/data.json')==before
 (fixtures/'unreviewed-import.stderr.txt').write_text(rejected.stderr,encoding='utf-8')
 receipt={'verified_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'all_data_and_build_checks_passed':True,'app_id':data['id'],'query_count':len(q),'source_evidence_rows':28,'performance_rows':0,'raw_labels_or_predictions_or_checkpoints_opened':False,'unreviewed_import_rejected_without_data_change':True,'protected_AGENTS_unchanged':True,'shared_runtime_build_kind':build.get('buildKind',build.get('kind','see data-app-build.json')),'served_html_sha256':sha(APP/'dist/index.html'),'snapshot_sha256':sha(latest),'url':url,'server_pid':server['pid'],'publication':False,'browser_checks':{'first_build':'root confirmed首屏/真实条形图/panel与regime切换，数字正确无明显遮挡','latest_changes':'RF元信息和图tooltip绑定已更新，最终浏览器复核由root在同tab进行','not_claimed':'未自行控制浏览器；窄屏、来源侧栏、chemistry切换及最终回All由root后续复核'}}
 (P/'verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(receipt,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
