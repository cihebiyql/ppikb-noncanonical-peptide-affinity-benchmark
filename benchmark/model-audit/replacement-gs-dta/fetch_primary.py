import hashlib,json,pathlib,re,urllib.request,xml.etree.ElementTree as ET
R=pathlib.Path(__file__).resolve().parent
u='https://pmc-oa-opendata.s3.amazonaws.com/PMC11792192.1/PMC11792192.1.json'
b=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'PPIKB-generic-method-static-audit/1.0'}),timeout=25).read(1000000)
m=json.loads(b);(R/'official-PMC-metadata.json').write_bytes(b)
def https(url):
 return url.replace('s3://pmc-oa-opendata/','https://pmc-oa-opendata.s3.amazonaws.com/')
x=urllib.request.urlopen(https(m['xml_url']),timeout=25).read(2500000);(R/'official-fulltext.xml').write_bytes(x)
root=ET.fromstring(x);t=[];links=[]
for e in root.iter():
 if e.tag in ['article-title','title','p','table-wrap']:
  s=' '.join(''.join(e.itertext()).split())
  if s:t.append(s)
 if e.tag=='ext-link':links.append(''.join(e.itertext()))
(R/'official-fulltext.txt').write_text('\n'.join(t)+'\n',encoding='utf-8')
print(json.dumps({k:m.get(k) for k in ['doi','title','is_manuscript','license_code','pdf_url','xml_url']},ensure_ascii=False))
print(json.dumps({'github_links':[x for x in links if 'github' in x]},ensure_ascii=False))
if not m.get('is_manuscript') and m.get('pdf_url'):
 p=urllib.request.urlopen(https(m['pdf_url']),timeout=30).read(15000001)
 if not p.startswith(b'%PDF-') or len(p)>15000000:raise ValueError('Not bounded PDF')
 (R/'GS-DTA-published.pdf').write_bytes(p)
 o={'doi':m['doi'],'title':m['title'],'pdf_path':str(R/'GS-DTA-published.pdf'),'pdf_sha256':hashlib.sha256(p).hexdigest(),'pdf_md5':hashlib.md5(p).hexdigest(),'bytes':len(p),'official_metadata':str(R/'official-PMC-metadata.json'),'source_url':m['pdf_url'],'license':m['license_code'],'is_manuscript':m['is_manuscript']}
 (R/'primary-receipt.json').write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(o,ensure_ascii=False))
