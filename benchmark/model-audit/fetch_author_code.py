"""Bounded, read-only HTTP code snapshots. Never imports or executes author code."""
import concurrent.futures, datetime, hashlib, json, pathlib, urllib.request
ROOT=pathlib.Path(__file__).resolve().parent
REPOS=['thinng/GraphDTA','guaguabujianle/MGraphDTA','luojunwei/DGDTA','JK-Liu7/AttentionMGT-DTA','CellNest/GEFormerDTA']
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'PPIKB-method-static-audit','Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(req,timeout=35) as r:return r.read()
def one(repo):
    dest=ROOT/'author-source'/repo.replace('/','__');dest.mkdir(parents=True,exist_ok=True)
    meta=json.loads(get('https://api.github.com/repos/'+repo));branch=meta['default_branch']
    commit=json.loads(get('https://api.github.com/repos/'+repo+'/commits/'+branch))['sha']
    tree=json.loads(get('https://api.github.com/repos/'+repo+'/git/trees/'+commit+'?recursive=1'))
    (dest/'git-tree.json').write_text(json.dumps(tree,indent=2),encoding='utf-8')
    files=[];errors=[]
    wanted=[x for x in tree['tree'] if x['type']=='blob' and x.get('size',0)<2_000_000 and (x['path'].lower().endswith(('.py','.md','.yml','.yaml','.txt','.toml')) or x['path'].split('/')[-1].lower().startswith('license')) and not any(p in x['path'].lower() for p in ['/data/','/dataset/','.egg-info'])][:120]
    def download(x):
        p=x['path'];url='https://raw.githubusercontent.com/'+repo+'/'+commit+'/'+urllib.parse.quote(p)
        try:
            b=get(url);out=dest/'source'/p;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(b)
            return {'path':p,'local':str(out),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'url':url}
        except Exception as e:return {'path':p,'error':str(e)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for r in pool.map(download,wanted):
            (errors if 'error' in r else files).append(r)
    result={'repository':repo,'repository_url':'https://github.com/'+repo,'commit':commit,'branch':branch,'license':meta.get('license'),'files':files,'errors':errors,'mode':'bounded source snapshot, not full Git checkout','executed_author_code':False,'installed_packages':False}
    (dest/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return {'repository':repo,'commit':commit,'files':len(files),'errors':len(errors),'manifest':str(dest/'manifest.json')}
if __name__=='__main__':
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for r in pool.map(one,REPOS):results.append(r);print(json.dumps(r))
    (ROOT/'source-fetch-index.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'repositories':results},indent=2),encoding='utf-8')
