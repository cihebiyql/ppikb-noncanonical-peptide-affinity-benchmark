"""Two bounded PDF attempts per method; inspect PDF magic, never rename HTML as PDF."""
import concurrent.futures,datetime,hashlib,json,pathlib,urllib.request
R=pathlib.Path(__file__).resolve().parent/'papers';R.mkdir(exist_ok=True)
SPECS=[
('GraphDTA','10.1093/bioinformatics/btaa921','GraphDTA: predicting drug–target binding affinity with graph neural networks','version_of_record',[
'https://academic.oup.com/bioinformatics/article-pdf/37/8/1140/50340643/btaa921.pdf',
'https://academic.oup.com/bioinformatics/advance-article-pdf/doi/10.1093/bioinformatics/btaa921/34053365/btaa921.pdf']),
('MGraphDTA','10.1039/d1sc05180f','MGraphDTA: deep multiscale graph neural network for explainable drug–target binding affinity prediction','version_of_record',[
'https://pubs.rsc.org/en/content/articlepdf/2022/SC/D1SC05180F',
'https://pmc.ncbi.nlm.nih.gov/articles/PMC8768884/pdf/sc-013-d1sc05180f.pdf']),
('DGDTA','10.1186/s12859-023-05497-5','DGDTA: dynamic graph attention network for predicting drug–target binding affinity','version_of_record',[
'https://link.springer.com/content/pdf/10.1186/s12859-023-05497-5.pdf',
'https://bmcbioinformatics.biomedcentral.com/counter/pdf/10.1186/s12859-023-05497-5']),
('DeepNC','10.7717/peerj.13163','DeepNC: a framework for drug-target interaction prediction with graph neural networks','version_of_record',[
'https://peerj.com/articles/13163.pdf',
'https://pmc.ncbi.nlm.nih.gov/articles/PMC9107302/pdf/peerj-10-13163.pdf']),
('MRBDTA','10.1093/bib/bbac468','Predicting drug–target binding affinity through molecule representation block based on multi-head attention and skip connection','version_of_record',[
'https://academic.oup.com/bib/article-pdf/23/6/bbac468/47144652/bbac468.pdf',
'https://academic.oup.com/bib/advance-article-pdf/doi/10.1093/bib/bbac468/47144652/bbac468.pdf'])]
def one(s):
 name,doi,title,version,urls=s; attempts=[]; out={'method':name,'doi':doi,'title':title,'version':version,'attempts':attempts,'pdf_status':'unknown_unavailable','pdf_path':None,'pdf_sha256':None}
 for url in urls:
  try:
   q=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; MethodReproductionAudit/1.0)','Accept':'application/pdf'})
   with urllib.request.urlopen(q,timeout=35) as p:
    b=p.read(18_000_001); final=p.url; typ=p.headers.get('Content-Type'); code=p.status
   a={'url':url,'final_url':final,'http_status':code,'content_type':typ,'bytes':len(b),'pdf_magic':b.startswith(b'%PDF-')};attempts.append(a)
   if not b.startswith(b'%PDF-') or len(b)>18_000_000:
    a['error']='response is not a bounded PDF; no PDF file written';continue
   path=R/(name+'.pdf');path.write_bytes(b)
   out.update(pdf_status='downloaded_pdf_magic_verified',pdf_path=str(path),pdf_sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),source_url=url);break
  except Exception as e:attempts.append({'url':url,'error':str(e)})
 (R/(name+'-receipt.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');return out
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=5) as p:rr=list(p.map(one,SPECS))
 out={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'new NC PPIKB common-data benchmark primary-method identity verification; no original-paper-score comparison','attempt_limit_per_paper':2,'papers':rr}
 (R/'PDF-manifest.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 for s in rr:print(json.dumps({k:v for k,v in s.items() if k!='attempts'},ensure_ascii=False))
