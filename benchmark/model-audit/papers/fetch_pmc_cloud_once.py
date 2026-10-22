"""One bounded current official archive attempt per known PMC version.
Legacy OA API 404 receipts remain preserved, not retried.
"""
import concurrent.futures,datetime,hashlib,json,pathlib,urllib.parse,urllib.request
R=pathlib.Path(__file__).resolve().parent
SPECS=[('MGraphDTA','PMC8768884.1','10.1039/d1sc05180f'),('DeepNC','PMC9107302.1','10.7717/peerj.13163')]
def get(u,limit):
 q=urllib.request.Request(u,headers={'User-Agent':'PPIKB-primary-method-archive-verification/1.0'})
 with urllib.request.urlopen(q,timeout=30) as z:
  b=z.read(limit+1)
  if len(b)>limit:raise ValueError('Bounded response limit exceeded')
  return b,z.url,dict(z.headers)
def one(s):
 n,i,doi=s;url='https://pmc-oa-opendata.s3.amazonaws.com/'+i+'/'+i+'.json';o={'method':n,'pmc_version':i,'doi':doi,'metadata_url':url,'channel':'current official PMC AWS Open Data; legacy OA API retired2026-08','status':'unknown_unavailable','pdf_path':None}
 try:
  b,final,h=get(url,500000);meta=json.loads(b);mp=R/(n+'-PMC-archive-metadata.json');mp.write_bytes(b);o.update(metadata_path=str(mp),metadata_sha256=hashlib.sha256(b).hexdigest(),metadata=meta)
  got=str(meta.get('doi','')).lower()
  if got!=doi.lower():raise ValueError('Archive DOI mismatch: '+got)
  if str(meta.get('is_manuscript','')).lower() in ['true','yes','1']:raise ValueError('Archive version is manuscript, not required published article')
  pu=meta.get('pdf_url')
  if not pu:raise ValueError('Archive metadata contains no licensed PDF object')
  if pu.startswith('s3://pmc-oa-opendata/'):pu='https://pmc-oa-opendata.s3.amazonaws.com/'+pu.split('s3://pmc-oa-opendata/',1)[1]
  if urllib.parse.urlparse(pu).hostname!='pmc-oa-opendata.s3.amazonaws.com':raise ValueError('Unexpected archive host')
  o['pdf_url']=pu
  pb,pfinal,ph=get(pu,20000000)
  if not pb.startswith(b'%PDF-'):raise ValueError('Archive object not PDF; not written')
  expected=urllib.parse.parse_qs(urllib.parse.urlparse(pu).query).get('md5',[None])[0];md5=hashlib.md5(pb).hexdigest()
  if expected and md5!=expected:raise ValueError('Archive PDF MD5 mismatch')
  pp=R/(n+'-PMC-published.pdf');pp.write_bytes(pb);o.update(status='downloaded_published_pdf_magic_md5_verified',pdf_path=str(pp),pdf_sha256=hashlib.sha256(pb).hexdigest(),pdf_md5=md5,archive_md5_expected=expected,bytes=len(pb),final_url=pfinal,pdf_magic=True)
 except Exception as e:o['error']=str(e)
 (R/(n+'-PMC-archive-once-receipt.json')).write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf-8');return o
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as p:rr=list(p.map(one,SPECS))
 out={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'official_docs':'https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/','official_readme':'https://pmc-oa-opendata.s3.amazonaws.com/README.txt','no_login_or_credentials':True,'one_archive_attempt_per_known_pmc_version':True,'results':rr}
 (R/'PMC-current-archive-addendum.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 for x in rr:print(json.dumps({k:v for k,v in x.items() if k!='metadata'},ensure_ascii=False))
