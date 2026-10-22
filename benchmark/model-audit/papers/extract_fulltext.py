from html.parser import HTMLParser
from pathlib import Path
import xml.etree.ElementTree as ET
R=Path(__file__).resolve().parent
class Text(HTMLParser):
 def __init__(self):super().__init__();self.parts=[];self.skip=0
 def handle_starttag(self,t,a):
  if t in ['script','style','svg']:self.skip+=1
  if t in ['p','div','h1','h2','h3','h4','tr','li','section']:self.parts.append('\n')
 def handle_endtag(self,t):
  if t in ['script','style','svg']:self.skip=max(0,self.skip-1)
  if t in ['p','div','h1','h2','h3','h4','tr','li','section']:self.parts.append('\n')
 def handle_data(self,d):
  if not self.skip:self.parts.append(d)
for p in R.glob('*-official.html'):
 h=Text();h.feed(p.read_text(encoding='utf-8',errors='replace'));out='\n'.join(' '.join(s.split()) for s in ''.join(h.parts).splitlines() if s.strip());p.with_suffix('.txt').write_text(out,encoding='utf-8')
for p in R.glob('*-EuropePMC.xml'):
 root=ET.fromstring(p.read_bytes());out=[]
 for e in root.iter():
  if e.tag in ['article-title','title','p','table-wrap']:
   s=' '.join(''.join(e.itertext()).split())
   if s:out.append(s)
 p.with_suffix('.txt').write_text('\n'.join(out)+'\n',encoding='utf-8')
