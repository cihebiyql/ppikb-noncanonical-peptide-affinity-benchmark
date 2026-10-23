from pathlib import Path
import json,csv,re,hashlib,datetime,subprocess,collections,ast,shutil
R=Path(__file__).resolve().parents[2];P=Path(__file__).resolve().parent;C=R/'publication/github-checkout';N=C/'four-task-20261022'
def sha(b):return hashlib.sha256(b).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,x):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def git(*args):return subprocess.run(['git','-C',str(C),*args],check=True,capture_output=True).stdout.decode('utf-8',errors='replace').strip()
assert not N.exists(),'New namespace must not overwrite an existing directory'
oldpaths=['benchmark','datasets','docs','manifest','permissions','scripts','support','README.md','LICENSES','.gitattributes','.gitignore']
base={'head':git('rev-parse','HEAD'),'head_tree':git('rev-parse','HEAD^{tree}'),'old_root_tree_entries':git('ls-tree','HEAD','--',*oldpaths),'status_before':git('status','--porcelain=v1')}
assert not base['status_before'];save(P/'base-before.json',base)
selected={};skipped=[]
def add(p,reason):
 p=Path(p)
 if not p.is_file():return
 rel=p.relative_to(R).as_posix()
 if any(s in rel.lower() for s in ['__pycache__','authorization','user_request','user-request','delegated-task-authority']):skipped.append({'path':rel,'reason':'private authorization/runtime text omitted'});return
 if p.suffix.lower() not in ['.py','.md','.json','.csv','.log','.png','.jpg','.pdf','.txt']:return
 if p.stat().st_size>=50_000_000:skipped.append({'path':rel,'reason':'single-file budget; deferred Release'});return
 if p.suffix.lower()=='.pdf' and not rel.startswith('reports/contact-site-gallery-v3/'):return
 selected[rel]={'path':p,'reason':reason,'dest':'benchmark/'+rel}
def named(directory,names,reason):
 for n in names:add(R/directory/n,reason)
def patterns(directory,patterns,reason):
 d=R/directory
 if d.exists():
  for g in patterns:
   for p in d.glob(g):add(p,reason)
named('protocol',['data_protocol.md','DATA_SCOPE_ADDENDUM-20261023.md','EXECUTION_PLAN.md','method_registry.json','task_definitions.json','UNIAIR_SEQUENCE_SCOPE_ADDENDUM-20261023.md'],'self-authored task definitions, scope and split rules')
patterns('protocol',['*.py'],'self-authored orchestration helpers; imports/dependencies not executed')
patterns('baselines',['*.py','README.md','RESULTS.md','all-formal-mean-sd-metrics.csv','*comparison*.md','DELIVERY-AUDIT.json'],'self-authored manual baseline implementation, results and audit')
patterns('baselines/frozen-code',['*.py'],'self-authored frozen manual baseline implementation; upstream vendor omitted')
for d in ['baselines/molecular','baselines/plm-simple-v1','baselines/plm-simple-v1/controls','baselines/plm-classification-contact-v1']:
 patterns(d,['*.py','README.md','RESULTS.md','DELIVERY*.json','DELIVERY*.md','FINAL-LOCAL-RECEIPT.json','coverage-manifest.json','local-*-index.json','*mirror-receipt.json','*cache-binding.json','*protocol-tests*.log','*interface-tests*.log'],'self-authored sequence/molecular/ESM wrappers and tests, aggregate reports and asset receipts; no official-source files or caches')
patterns('reports',['*.py','*.md','dgdta-identity-correction.json','frozen-author-sources-recheck.json','independent-data-readback.json'],'self-authored root analysis/report builders and scope corrections')
for d in ['reports/delivery-20261023','reports/root-generic-aggregation-independent-v1','reports/profaff-HU-external','reports/pepbi-conditional-external-v1','reports/source-species-audit-v1']:
 patterns(d,['*.md','*.py','*.csv','DELIVERY*.json','STATUS.json','*independent*.json','*supplement*.json','*audit-index.json','view-endpoint-map.json'],'self-authored aggregate results, endpoint audit and conditional external-validation documentation; no original data')
named('reports/her2-strict-local',['all-seeds-metrics.csv','ten-seed-mean-sd.csv','REPORT.zh-CN.md','STATUS.json'],'own HER2 summary/per-seed metrics only; no source labels, reference table or complete sequences')
named('reports/goal-acceptance-ledger-v2',['REPORT.zh-CN.md','INDEX.md','data-task-matrix.csv','method-scope-matrix.csv','requirements.csv','traditional-seed-coverage.csv','superseded-notes.json'],'dated independent goal ledger; snapshot status may be older than current owner receipts')
patterns('reports/contact-site-gallery-v3',['*.md','gallery-receipt.json','independent-audit.json','report.pdf'],'self-generated contact figures/report/audit; not original paper graphics')
patterns('reports/contact-site-gallery-v3/figures',['*.png','*.jpg','*.pdf'],'self-generated contact visualization exports with source attribution')
patterns('methods/dta',['*.py','README.md','RUN_STRATA_REPORT.md'],'self-authored training/evaluation/coordinator wrappers; frozen author architectures fetched separately')
for ptr in ['accepted-census-current.json','accepted-details-current.json']:
 p=R/'methods/dta'/ptr
 if p.exists():
  add(p,'timestamped live pointer snapshot, not overall completion proof')
  j=load(p)
  for k in ['path','details_path','source_path']:
   q=Path(j[k]) if j.get(k) else None
   if q and q.is_file() and q.is_relative_to(R):add(q,'owner accepted-unit snapshot linked by exact SHA')
named('methods/interaction',['REPORT.interaction.md','status.interaction.v3.json','status.interaction.continuation.v1.json','local-model-delivery-index.json'],'own component-scope reports and asset-delivery metadata, no weights or raw inputs')
named('methods/interaction/continuation-20261023',['REPORT.classification-10seeds.md','classification-common-mean-sd.csv','classification-common-per-seed.csv','classification-summary-export.receipt.json','swing-classification-independent-audit.local-latest.json'],'own genuine10-seed classification metrics and independent recomputation')
named('methods/interaction/continuation-20261023/pepinter-classification',['native-Focal-tenseed-independent-audit.local.json','native-Focal-tenseed.actual-local-SHA-audit.json','native-Focal-tenseed.result.json','native-head-fidelity.json','native-fulltraining-route.md','native-GPU-gradient-gates.latest.json'],'own native-head component results/proofs; not full author training chain')
named('methods/uniair/continuation-20261023/rde-ten-seed-report-v1',['README.zh-CN.md','summary.json','all-model-seed-metrics.csv','mean-and-sample-SD.csv','paired-seed-MAE-differences.csv'],'own ten-genuine-seed RDE-component metrics; no source labels, author table or sequence inputs')
named('methods/uniair/continuation-20261023',['continuation-status-v2.json','local-GPU-log-export-verification-v1.json'],'own status and local model/log provenance index; original/mixed weights deferred')
for d in ['data/pepbi-external-audit-20261023','data/profaff-expansion-20261023']:
 patterns(d,['*.py','*.md','FINAL-SUMMARY.json','SUMMARY.json','DELIVERY-SUMMARY.json','VALIDATION.json','protocol.json'],'own dataset-quality analyses and code; raw source data and original PDFs omitted')
patterns('data/pepbi-primary-context-20261023',['*.py','REPORT.zh-CN.md','audit_protocol.json','primary-context-index.csv','ptpa-ap2-summary.json'],'own all27 primary-context audit/code; no raw publisher PDFs or extracted fulltext')
patterns('data/pepbi-primary-context-20261023/stac-profilin',['audit_primary.py','REPORT.zh-CN.md','SUMMARY.json','VALIDATION.json','manual-source-independence.json'],'own nine-candidate primary-context audit/code; public author fulltext itself omitted')
named('literature/systematic-2021-2026',['REPORT.zh-CN.md','INDEX.md','protocol.json','curated-registry.psv','current-four-source-task-matrix.csv','four-source-method-routing.csv','new-method-evidence-cards.zh-CN.md','provided-reference-reconciliation.zh-CN.md','provided-reference-checklist.csv','DELIVERY-SUMMARY.json','VALIDATION.json'],'self-authored systematic related-work catalog and source routing; no pasted user text or original papers/repositories')
# Freeze byte identity before copy. No data/model execution.
entries=[];total=0
for rel,item in sorted(selected.items()):
 p=item['path'];a=p.stat();b=p.read_bytes();z=p.stat()
 if a.st_mtime_ns!=z.st_mtime_ns or a.st_size!=z.st_size:skipped.append({'path':rel,'reason':'changed during read; deferred next snapshot'});continue
 entries.append({'source_relative':rel,'source_path':str(p),'public_path':'four-task-20261022/'+item['dest'],'destination_relative':item['dest'],'bytes':len(b),'sha256':sha(b),'source_mtime_ns':z.st_mtime_ns,'source_kind':item['reason'],'permission_basis':'self-authored code/results/protocol/documentation, or own visualization; third-party originals omitted','selection':'explicit allowlist first public snapshot, no result-performance filter'})
 total+=len(b)
assert total<=250_000_000
freeze={'schema':'fourtask.first-public-snapshot.copy-freeze.v1','frozen_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'base_head':base['head'],'namespace':'four-task-20261022','total_files':len(entries),'total_bytes':total,'entries':entries,'not_full_108GB_delivery':True,'no_commit_or_push':True}
save(P/'copy-manifest.frozen.json',freeze);save(P/'excluded-or-deferred-selection.json',skipped)
N.mkdir()
for x in entries:
 b=Path(x['source_path']).read_bytes();assert sha(b)==x['sha256'],'Source changed after freeze: '+x['source_relative']
 out=N/x['destination_relative'];out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(b);assert sha(out.read_bytes())==x['sha256']
print(json.dumps({'files':len(entries),'bytes':total,'base_head':base['head'],'namespace':str(N)},ensure_ascii=False))
