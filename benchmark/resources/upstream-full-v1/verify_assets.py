"""Independently verify archive bytes/files against saved official git tree metadata."""
import hashlib
import json
from pathlib import Path
import zipfile

P=Path(__file__).resolve().parent
ROOT=P.parent.parent
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
SLUG={'GraphDTA-GIN':'thinng__GraphDTA','MGraphDTA':'guaguabujianle__MGraphDTA','DGDTA-CL':'luojunwei__DGDTA','DeepNC-GEN':'thntran__DeepNC','GS-DTA':'zhuziguang__GS-DTA'}
def main():
    manifest=read(P/'manifest.json');all_results=[]
    for r in manifest['repositories']:
        m=r['method_id'];folder=P/m
        if r['status']!='complete_exact_commit_file_archive':
            all_results.append({'method_id':m,'status':'failed_asset_no_false_completion'});continue
        assert sha(Path(r['archive_path']))==r['archive_sha256']
        with zipfile.ZipFile(r['archive_path']) as z:assert z.testzip() is None
        files=read(folder/'file-manifest.json');root=Path(r['extracted_root']);mapping={x['path']:x for x in files}
        assert len(files)==r['file_count'] and {q.relative_to(root).as_posix() for q in root.rglob('*') if q.is_file()}==set(mapping)
        for f in files:
            q=root/f['path'];assert q.stat().st_size==f['bytes'] and sha(q)==f['sha256']
        old=ROOT/'model-audit/author-source'/SLUG[m]
        tree_path=old/'git-tree.json';tree=read(tree_path)
        assert tree['sha']==r['commit'] and tree['truncated'] is False
        blobs={x['path']:x for x in tree['tree'] if x['type']=='blob'}
        assert set(blobs)==set(mapping)
        for rel,entry in blobs.items():
            q=root/rel;d=q.read_bytes();actual=hashlib.sha1(b'blob '+str(len(d)).encode()+b'\0'+d).hexdigest()
            assert actual==entry['sha'],rel
        selected=[]
        for q in (old/'source').rglob('*'):
            if not q.is_file():continue
            rel=q.relative_to(old/'source').as_posix()
            assert rel in mapping and sha(q)==mapping[rel]['sha256'],rel
            selected.append({'path':rel,'sha256':sha(q)})
        all_results.append({'method_id':m,'status':'verified','archive_sha256':r['archive_sha256'],'file_count':len(files),'git_tree_metadata_path':str(tree_path),'git_tree_metadata_sha256':sha(tree_path),'git_tree_commit':tree['sha'],'exact_git_blob_path_set_match':True,'git_blob_sha1_match_count':len(blobs),'selected_source_match_count':len(selected),'selected_source_matches':selected,'full_git_history_claimed':False})
    report={'status':'all_five_verified' if len(all_results)==5 and all(x['status']=='verified' for x in all_results) else 'incomplete','acquisition_manifest_sha256':sha(P/'manifest.json'),'repositories':all_results,'verification_script_sha256':sha(Path(__file__)),'upstream_code_executed':False,'project_gold_predictions_models_or_training_labels_opened':False}
    write(P/'asset-integrity-verification.json',report)
    licenses=[]
    for r in manifest['repositories']:
        if r['status']!='complete_exact_commit_file_archive':continue
        for rel in r['license_paths']:
            q=Path(r['extracted_root'])/rel;text=q.read_text(encoding='utf-8',errors='replace')
            licenses.append({'method_id':r['method_id'],'path':str(q),'sha256':sha(q),'opening_lines':text.splitlines()[:8],'file_scope':'Upstream license text retained; package/dependency redistribution licenses are separate.'})
    write(P/'license-evidence.json',licenses)
    delivery={'status':report['status'],'files_sha256':{n:sha(P/n) for n in ['manifest.json','asset-integrity-verification.json','license-evidence.json','README.md','acquisition-contract.json','acquire_upstream.py','verify_assets.py']},'total_archives':5,'total_archive_bytes':sum(r.get('archive_bytes',0) for r in manifest['repositories']),'total_source_files':sum(r.get('file_count',0) for r in manifest['repositories']),'source_execution':0,'scientific_training_or_scoring':0}
    write(P/'DELIVERY-MANIFEST.json',delivery)
    print(json.dumps({'status':report['status'],'files':delivery['total_source_files'],'archive_bytes':delivery['total_archive_bytes'],'delivery_manifest_sha256':sha(P/'DELIVERY-MANIFEST.json')}))

if __name__=='__main__':main()
