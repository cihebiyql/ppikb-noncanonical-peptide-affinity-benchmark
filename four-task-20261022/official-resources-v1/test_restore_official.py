import hashlib,io,json,stat,tarfile,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
import restore_official as r
class Response(io.BytesIO):
 def geturl(self):return 'https://raw.githubusercontent.com/owner/repo/fixed/a.txt'
class Opener:
 def __init__(self,data):self.data=data;self.calls=0
 def open(self,*a,**k):self.calls+=1;return Response(self.data)
class RestoreTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.data=b'synthetic exact resource\n'
 def tearDown(self):self.tmp.cleanup()
 def entry(self):return {'id':'x','kind':'file','restore_status':'ready_exact_bytes','url':'https://raw.githubusercontent.com/owner/repo/'+'a'*40+'/a.txt','bytes':len(self.data),'sha256':hashlib.sha256(self.data).hexdigest(),'destination':'x/a.txt'}
 def z(self,name='a.zip',members=None):
  p=self.root/name
  with zipfile.ZipFile(p,'w') as z:
   for n,b in members or [('top/a.txt',self.data)]:z.writestr(n,b)
  return p
 def test_fetch_normal(self):
  o=Opener(self.data);p=r.fetch_file(self.entry(),self.root/'out',opener=o);self.assertEqual(p.read_bytes(),self.data);self.assertEqual(o.calls,1)
 def test_fetch_bad_sha_no_final(self):
  e=self.entry();e['sha256']='0'*64
  with self.assertRaises(r.RestoreError):r.fetch_file(e,self.root/'out',opener=Opener(self.data))
  self.assertFalse((self.root/'out/x/a.txt').exists());self.assertFalse(list((self.root/'out/x').glob('.official-part-*')))
 def test_fetch_oversize(self):
  with self.assertRaises(r.RestoreError):r.fetch_file(self.entry(),self.root/'out',opener=Opener(self.data+b'x'))
 def test_fetch_truncated(self):
  with self.assertRaises(r.RestoreError):r.fetch_file(self.entry(),self.root/'out',opener=Opener(self.data[:-1]))
 def test_existing_identical_no_network(self):
  o=Opener(self.data);r.fetch_file(self.entry(),self.root/'out',opener=o);r.fetch_file(self.entry(),self.root/'out',opener=o);self.assertEqual(o.calls,1)
 def test_existing_different_not_overwritten(self):
  p=self.root/'out/x/a.txt';p.parent.mkdir(parents=True);p.write_bytes(b'KEEP')
  with self.assertRaises(r.RestoreError):r.fetch_file(self.entry(),self.root/'out',opener=Opener(self.data))
  self.assertEqual(p.read_bytes(),b'KEEP')
 def test_offline_verification(self):
  p=self.root/'offline';p.write_bytes(self.data);self.assertTrue(r.verify_file(p,len(self.data),self.entry()['sha256']))
 def test_offline_bad_SHA(self):
  p=self.root/'offline';p.write_bytes(self.data)
  with self.assertRaises(r.RestoreError):r.verify_file(p,len(self.data),'0'*64)
 def test_url_origins(self):
  for u in ['http://raw.githubusercontent.com/x','https://evil.example/a','https://github.com.evil.example/a','https'+chr(58)+chr(47)*2+'user'+chr(58)+'pass'+chr(64)+'github.com/a','https://127.0.0.1/a','https://github.com:444/a']:
   with self.subTest(u=u),self.assertRaises(r.RestoreError):r.validate_url(u)
 def test_redirect_origin(self):
  with self.assertRaises(r.RestoreError):r.OfficialRedirect().redirect_request(None,None,302,'',{},'https://evil.example/a')
 def test_pending_rejected(self):
  e=self.entry();e['restore_status']='pending'
  with self.assertRaises(r.RestoreError):r.fetch_file(e,self.root/'out',opener=Opener(self.data))
 def test_path_names(self):
  for name in ['../escape','/absolute','C'+':/drive','a/../../b','a\\evil',chr(0)+'bad','CON.txt','a/.git/config','a/space.']:
   with self.subTest(name=repr(name)),self.assertRaises(r.RestoreError):r.safe_path(self.root,name)
 def test_zip_normal(self):
  p=self.z();out=r.safe_extract(p,self.root/'out');self.assertEqual(len(out),1);self.assertEqual((self.root/'out/top/a.txt').read_bytes(),self.data)
 def test_zip_traversal_preflight(self):
  p=self.z(members=[('top/good',self.data),('../escape',b'bad')])
  with self.assertRaises(r.RestoreError):r.safe_extract(p,self.root/'out')
  self.assertFalse((self.root/'out/top/good').exists())
 def test_zip_symlink_rejected(self):
  p=self.root/'link.zip'
  with zipfile.ZipFile(p,'w') as z:
   a=zipfile.ZipInfo('link');a.create_system=3;a.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(a,'../x')
  with self.assertRaises(r.RestoreError):r.safe_extract(p,self.root/'out')
 def test_zip_duplicate_case(self):
  p=self.z(members=[('A.txt',b'1'),('a.txt',b'2')])
  with self.assertRaises(r.RestoreError):r.safe_extract(p,self.root/'out')
 def test_zip_expansion_limit(self):
  p=self.z()
  with self.assertRaises(r.RestoreError):r.safe_extract(p,self.root/'out',max_bytes=1)
 def test_zip_existing_different(self):
  p=self.z();q=self.root/'out/top/a.txt';q.parent.mkdir(parents=True);q.write_bytes(b'KEEP')
  with self.assertRaises(r.RestoreError):r.safe_extract(p,self.root/'out')
  self.assertEqual(q.read_bytes(),b'KEEP')
 def test_tar_link_types_rejected(self):
  for typ in [tarfile.SYMTYPE,tarfile.LNKTYPE,tarfile.CHRTYPE]:
   p=self.root/'bad.tar'
   with tarfile.open(p,'w') as t:a=tarfile.TarInfo('link');a.type=typ;a.linkname='../x';t.addfile(a)
   with self.subTest(typ=typ),self.assertRaises(r.RestoreError):r.safe_extract(p,self.root/'out')
 def test_tar_normal(self):
  p=self.root/'good.tar'
  with tarfile.open(p,'w') as t:a=tarfile.TarInfo('a.txt');a.size=len(self.data);t.addfile(a,io.BytesIO(self.data))
  self.assertEqual(len(r.safe_extract(p,self.root/'out')),1)
 def test_member_restore_parent_bound(self):
  p=self.z();parent=self.entry();parent.update(id='parent',bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),destination='parent/a.zip',archive={'max_members':10,'max_expanded_bytes':10000})
  member={'id':'m','kind':'archive_member','restore_status':'ready_exact_archive_member','parent_asset_id':'parent','archive_member':'top/a.txt','destination':'selected/a.txt','bytes':len(self.data),'sha256':hashlib.sha256(self.data).hexdigest()}
  lock={'assets':[parent,member]};r.restore_one(lock,'m',self.root/'out',opener=Opener(p.read_bytes()));self.assertEqual((self.root/'out/selected/a.txt').read_bytes(),self.data)
 def test_member_bad_SHA(self):
  p=self.z()
  with self.assertRaises(r.RestoreError):r.safe_extract(p,self.root/'out',only={'top/a.txt':{'destination':'selected/a.txt','bytes':len(self.data),'sha256':'0'*64}})
  self.assertFalse((self.root/'out/selected/a.txt').exists())
 def test_parent_cycle(self):
  a={'id':'a','kind':'archive_member','restore_status':'ready_exact_archive_member','parent_asset_id':'b'};b=dict(a,id='b',parent_asset_id='a')
  with self.assertRaises(r.RestoreError):r.restore_one({'assets':[a,b]},'a',self.root/'out')
 def test_duplicate_ID(self):
  a=self.entry()
  with self.assertRaises(r.RestoreError):r.restore_one({'assets':[a,a]},'x',self.root/'out')
 def test_long_destination(self):
  e=self.entry();e['destination']='/'.join(['longsafe0123456789']*16)+'/a.txt';p=r.fetch_file(e,self.root/'out',opener=Opener(self.data));self.assertEqual(p.read_bytes(),self.data)
  p.unlink();q=p.parent;stop=r.fs_path(self.root/'out')
  while True:
   q.rmdir()
   if q==stop:break
   q=q.parent
 def test_nested_member_restore(self):
  inner=io.BytesIO()
  with zipfile.ZipFile(inner,'w') as z:z.writestr('a.txt',self.data)
  outer=io.BytesIO()
  with zipfile.ZipFile(outer,'w') as z:z.writestr('nested.zip',inner.getvalue())
  parent=self.entry();parent.update(id='outer',destination='outer.zip',bytes=len(outer.getvalue()),sha256=hashlib.sha256(outer.getvalue()).hexdigest(),archive={'max_members':10,'max_expanded_bytes':10000})
  middle=dict(id='middle',kind='archive_member',restore_status='ready_exact_archive_member',parent_asset_id='outer',archive_member='nested.zip',destination='nested.zip',bytes=len(inner.getvalue()),sha256=hashlib.sha256(inner.getvalue()).hexdigest(),archive={'max_members':10,'max_expanded_bytes':10000})
  leaf=dict(id='leaf',kind='archive_member',restore_status='ready_exact_archive_member',parent_asset_id='middle',archive_member='a.txt',destination='result/a.txt',bytes=len(self.data),sha256=hashlib.sha256(self.data).hexdigest())
  p=r.restore_one({'assets':[parent,middle,leaf]},'leaf',self.root/'out',opener=Opener(outer.getvalue()));self.assertEqual(Path(p).read_bytes(),self.data)
if __name__=='__main__':unittest.main(verbosity=2)
