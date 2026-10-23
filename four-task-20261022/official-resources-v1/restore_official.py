"""Restore exact official resources; standard library only. Never import/execute artifacts."""
from __future__ import annotations
import argparse,hashlib,json,os,re,stat,tarfile,tempfile,time,urllib.parse,urllib.request,zipfile
from pathlib import Path,PurePosixPath
ALLOWED_HOSTS=frozenset({'raw.githubusercontent.com','codeload.github.com','github.com','api.github.com','huggingface.co','cdn-lfs.huggingface.co','cdn-lfs-us-1.huggingface.co','cas-bridge.xethub.hf.co','us.aws.cdn.hf.co','eu.aws.cdn.hf.co','zenodo.org','ndownloader.figshare.com','api.figshare.com','figshare.com','static-content.springer-cdn.com','static-content.springer.com','dl.fbaipublicfiles.com','www.ebi.ac.uk'})
class RestoreError(Exception):pass
def validate_url(url):
 u=urllib.parse.urlsplit(url)
 if u.scheme!='https' or u.hostname not in ALLOWED_HOSTS or u.username is not None or u.password is not None or u.port not in (None,443):raise RestoreError('URL is not an approved public official HTTPS origin')
 if u.fragment:raise RestoreError('URL fragments are not accepted')
 return url
class OfficialRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  validate_url(newurl)
  return super().redirect_request(req,fp,code,msg,headers,newurl)
def fs_path(path):
 p=Path(path).absolute()
 if os.name!='nt':return p
 text=str(p);prefix=chr(92)*2+'?'+chr(92)
 if text.startswith(prefix):return p
 if text.startswith(chr(92)*2):return Path(prefix+'UNC'+chr(92)+text[2:])
 return Path(prefix+text)
def hash_file(path):
 h=hashlib.sha256()
 with fs_path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def verify_file(path,expected_bytes,expected_sha):
 p=fs_path(path)
 if p.is_symlink() or not p.is_file():raise RestoreError('Expected a regular existing artifact')
 if p.stat().st_size!=expected_bytes or hash_file(p)!=expected_sha:raise RestoreError('Artifact byte count or SHA256 mismatch')
 return True
def safe_path(root,relative):
 if not isinstance(relative,str) or not relative or chr(92) in relative or chr(0) in relative:raise RestoreError('Unsafe path spelling')
 p=PurePosixPath(relative)
 if p.is_absolute() or any(x in ('','..','.') or ':' in x or x.endswith((' ','.')) or x.lower() in ('.git','.ssh') or re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?',x) for x in p.parts):raise RestoreError('Unsafe archive/destination path')
 root=fs_path(root)
 # Check both destination tree and ancestors for links/reparse points before writes.
 target=root.joinpath(*p.parts)
 for q in [target,*target.parents]:
  if q.exists() or q.is_symlink():
   info=q.lstat()
   if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&1024:raise RestoreError('Link or reparse point in destination path')
 if not target.resolve(strict=False).is_relative_to(root.resolve(strict=False)):raise RestoreError('Path escapes destination')
 return target
def entry_check(e):
 if e.get('kind','file')!='file' or e.get('restore_status')!='ready_exact_bytes':raise RestoreError('Entry is pending or requires its exact parent archive')
 if not isinstance(e.get('bytes'),int) or e['bytes']<0 or not re.fullmatch('[a-f0-9]{64}',e.get('sha256','')):raise RestoreError('Entry lacks exact size/SHA256')
 validate_url(e['url'])
def _commit_temp(temp,dest,bytes,sha):
 if dest.exists():verify_file(dest,bytes,sha);return
 # Both live on the same filesystem. link() is atomic and refuses overwrites.
 try:os.link(temp,dest)
 except FileExistsError:verify_file(dest,bytes,sha)
 except OSError as error:raise RestoreError('Atomic no-overwrite finalization unavailable') from error
 verify_file(dest,bytes,sha)
def fetch_file(e,root,*,timeout=30,max_seconds=3600,opener=None):
 entry_check(e);dest=safe_path(root,e['destination'])
 if dest.exists():verify_file(dest,e['bytes'],e['sha256']);return dest
 dest.parent.mkdir(parents=True,exist_ok=True);safe_path(root,e['destination'])
 opener=opener or urllib.request.build_opener(OfficialRedirect())
 start=time.monotonic();h=hashlib.sha256();n=0;temp=None
 try:
  with tempfile.NamedTemporaryFile(prefix='.official-part-',suffix='.tmp',dir=dest.parent,delete=False) as f:
   temp=Path(f.name)
   req=urllib.request.Request(e['url'],headers={'User-Agent':'ExactOfficialResourceRestore/1.0'})
   with opener.open(req,timeout=timeout) as response:
    validate_url(response.geturl())
    while True:
     if time.monotonic()-start>max_seconds:raise RestoreError('Bounded download time exceeded')
     b=response.read(min(1024*1024,e['bytes']-n+1))
     if not b:break
     n+=len(b)
     if n>e['bytes']:raise RestoreError('Response exceeds exact locked byte limit')
     h.update(b);f.write(b)
   f.flush();os.fsync(f.fileno())
  if n!=e['bytes'] or h.hexdigest()!=e['sha256']:raise RestoreError('Downloaded byte count or SHA256 mismatch')
  _commit_temp(temp,dest,e['bytes'],e['sha256']);return dest
 finally:
  if temp and temp.exists():temp.unlink()
def _members(archive,max_members,max_bytes):
 result=[];seen=set();total=0
 if zipfile.is_zipfile(archive):
  z=zipfile.ZipFile(archive)
  for m in z.infolist():
   mode=m.external_attr>>16
   if stat.S_ISLNK(mode) or (mode and stat.S_IFMT(mode) not in (0,stat.S_IFREG,stat.S_IFDIR)):z.close();raise RestoreError('Archive links or special files are rejected')
   result.append((m.filename,m.file_size,m.is_dir(),m))
  typ='zip'
 else:
  z=tarfile.open(archive,'r:*');typ='tar'
  for m in z.getmembers():
   if not (m.isfile() or m.isdir()):z.close();raise RestoreError('Archive links or special files are rejected')
   result.append((m.name,m.size,m.isdir(),m))
 try:
  for name,size,isdir,m in result:
   if size<0:raise RestoreError('Negative archive member size')
   clean=name.rstrip('/')
   safe_path(Path(tempfile.gettempdir())/'official-path-preflight',clean)
   key=clean.casefold()
   if key in seen:raise RestoreError('Duplicate/case-colliding archive path')
   seen.add(key);total+=size
  if len(result)>max_members or total>max_bytes:raise RestoreError('Archive expansion budget exceeded')
  return z,typ,result
 except Exception:z.close();raise
def _write_member(stream,dest,expected_bytes,expected_sha=None):
 dest.parent.mkdir(parents=True,exist_ok=True);h=hashlib.sha256();n=0;temp=None
 try:
  with tempfile.NamedTemporaryFile(prefix='.official-extract-',dir=dest.parent,delete=False) as f:
   temp=Path(f.name)
   while True:
    b=stream.read(min(1024*1024,expected_bytes-n+1))
    if not b:break
    n+=len(b)
    if n>expected_bytes:raise RestoreError('Member exceeds declared byte size')
    h.update(b);f.write(b)
  if n!=expected_bytes or (expected_sha and h.hexdigest()!=expected_sha):raise RestoreError('Member size or SHA mismatch')
  _commit_temp(temp,dest,n,h.hexdigest())
 finally:
  if temp and temp.exists():temp.unlink()
def safe_extract(archive,dest,*,max_members=30000,max_bytes=1000000000,only=None):
 z,typ,members=_members(archive,max_members,max_bytes);out=[]
 try:
  # Preflight destination paths before any member extraction.
  for name,size,isdir,m in members:
   safe_path(dest,name.rstrip('/'))
  if only and not set(only).issubset({a[0] for a in members}):raise RestoreError('Locked member is absent from archive')
  for name,size,isdir,m in members:
   if only is not None and name not in only:continue
   if isdir:continue
   target_rel=only[name]['destination'] if only else name
   target=safe_path(dest,target_rel)
   if only and size!=only[name]['bytes']:raise RestoreError('Member declared size differs from lock')
   with (z.open(m) if typ=='zip' else z.extractfile(m)) as stream:_write_member(stream,target,size,only[name]['sha256'] if only else None)
   out.append(str(target))
  return out
 finally:z.close()
def restore_one(lock,id,root,_visited=None,**kwargs):
 seen=set(_visited or ())
 if id in seen or len(seen)>32:raise RestoreError('Archive parent cycle/depth rejected')
 seen.add(id)
 entries={a['id']:a for a in lock['assets']}
 if len(entries)!=len(lock['assets']):raise RestoreError('Duplicate resource IDs in lock')
 if id not in entries:raise RestoreError('Unknown locked resource ID')
 e=entries[id]
 if e.get('kind')=='archive_member':
  if e.get('restore_status')!='ready_exact_archive_member':raise RestoreError('Archive member is pending')
  if e['parent_asset_id'] not in entries:raise RestoreError('Parent archive is not locked')
  parent=entries[e['parent_asset_id']];archive=Path(restore_one(lock,parent['id'],root,_visited=seen,**kwargs));verify_file(archive,parent['bytes'],parent['sha256']);budget=parent.get('archive',{})
  out=safe_extract(archive,root,max_members=budget.get('max_members',30000),max_bytes=budget.get('max_expanded_bytes',1000000000),only={e['archive_member']:e})
  if len(out)!=1:raise RestoreError('Expected exactly one locked archive member')
  return out[0]
 return str(fetch_file(e,root,**kwargs))
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--lock',default=str(Path(__file__).with_name('fetch-lock.json')));ap.add_argument('--expect-lock-sha256');sub=ap.add_subparsers(dest='command',required=True)
 sub.add_parser('list');p=sub.add_parser('verify');p.add_argument('--id',required=True);p.add_argument('--path',required=True)
 p=sub.add_parser('fetch');p.add_argument('--id',required=True);p.add_argument('--dest',required=True);p.add_argument('--timeout',type=int,default=30);p.add_argument('--max-seconds',type=int,default=3600)
 p=sub.add_parser('extract');p.add_argument('--id',required=True);p.add_argument('--archive',required=True);p.add_argument('--dest',required=True)
 a=ap.parse_args()
 if a.command in ('fetch','extract') and not a.expect_lock_sha256:ap.error('fetch/extract requires --expect-lock-sha256 from the published manifest')
 if a.expect_lock_sha256 and hash_file(a.lock)!=a.expect_lock_sha256:ap.error('Lock SHA256 differs from the explicit pin')
 lock=json.loads(Path(a.lock).read_text(encoding='utf-8'));entries={x['id']:x for x in lock['assets']}
 try:
  if a.command=='list':print(json.dumps([{'id':x['id'],'kind':x['kind'],'status':x['restore_status'],'bytes':x['bytes']} for x in lock['assets']],indent=2));return
  e=entries[a.id]
  if a.command=='verify':verify_file(a.path,e['bytes'],e['sha256']);out={'verified':True,'id':a.id}
  elif a.command=='fetch':
   if not 1<=a.timeout<=300 or not 1<=a.max_seconds<=86400:raise RestoreError('Time bound outside allowed range')
   out={'id':a.id,'restored':restore_one(lock,a.id,a.dest,timeout=a.timeout,max_seconds=a.max_seconds)}
  else:
   entry_check(e);verify_file(a.archive,e['bytes'],e['sha256']);budget=e.get('archive')
   if not budget:raise RestoreError('Entry has no approved archive expansion plan')
   out={'id':a.id,'extracted_files':len(safe_extract(a.archive,a.dest,max_members=budget['max_members'],max_bytes=budget['max_expanded_bytes']))}
  print(json.dumps(out,ensure_ascii=False))
 except (RestoreError,KeyError,ValueError,OSError,zipfile.BadZipFile,tarfile.TarError) as error:
  # Do not print redirected URLs, bearer query values or artifact payloads.
  print(json.dumps({'ok':False,'error_type':type(error).__name__,'message':str(error) if isinstance(error,RestoreError) else 'Restore stopped; inspect official resource availability or local path'}));raise SystemExit(1)
if __name__=='__main__':main()
