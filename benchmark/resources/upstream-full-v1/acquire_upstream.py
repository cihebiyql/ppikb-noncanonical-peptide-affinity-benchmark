"""Bounded public exact-commit archive acquisition; never imports upstream code."""
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import time
import zipfile

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parent.parent
CSV=PROJECT/'report-preparation/predecessor-models.csv'
PAPER_MAP=PROJECT/'control/registered-paper-map.json'
def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for x in iter(lambda:f.read(1024*1024),b''):h.update(x)
    return h.hexdigest()
def write(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def verify_extract(archive,dest,expected_prefix):
    files=[]
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        if not names or any(not n.startswith(expected_prefix+'/') for n in names):raise ValueError('Archive root not exact requested repository/commit')
        if len(names)!=len(set(names)):raise ValueError('Duplicate archive paths')
        for info in z.infolist():
            rel=PurePosixPath(info.filename)
            if rel.is_absolute() or '..' in rel.parts or '\\' in info.filename or ':' in info.filename:raise ValueError('Unsafe archive path')
            mode=info.external_attr>>16
            if stat.S_ISLNK(mode):raise ValueError('Symlink requires separate review; extraction stopped')
        bad=z.testzip()
        if bad:raise ValueError('Archive CRC failed: '+bad)
        dest.mkdir(exist_ok=False)
        z.extractall(dest)
        for info in z.infolist():
            if info.is_dir():continue
            p=dest/info.filename
            if p.stat().st_size!=info.file_size:raise ValueError('Extracted size mismatch')
            files.append({'path':p.relative_to(dest/expected_prefix).as_posix(),'bytes':info.file_size,'sha256':sha(p),'archive_crc32':f'{info.CRC:08x}'})
    return dest/expected_prefix,files

def inventory(root,files):
    scripts=[];licenses=[];lfs=[]
    patterns={'evaluation_metrics':r'\b(?:mse|rmse|mae|r2_score|pearsonr|spearmanr|concordance|cindex|c_index|ci|roc_auc_score)\b',
              'split_or_validation':r'\b(?:train_test_split|KFold|StratifiedKFold|GroupKFold|cross_val|folds?|split|valid|validation|test)\b',
              'checkpoint_selection':r'\b(?:best_mse|best_ci|best_model|save_checkpoint|torch\.save|best_loss|best_epoch)\b'}
    for entry in files:
        rel=entry['path'];p=root/rel;name=p.name.lower()
        if name.startswith(('license','licence','copying','notice')):licenses.append(dict(entry))
        if p.suffix.lower() in ('.py','.sh','.ipynb') and entry['bytes']<=4*1024*1024:
            text=p.read_text(encoding='utf-8',errors='replace');evidence={}
            for category,pat in patterns.items():
                matches=[{'line':i,'text':line.strip()[:260]} for i,line in enumerate(text.splitlines(),1) if re.search(pat,line,re.I)]
                if matches:evidence[category]=matches[:40]
            if evidence:scripts.append({'path':rel,'sha256':entry['sha256'],'evidence':evidence,'inspection':'static string/line inventory, not executed behavior verification'})
        if entry['bytes']<2048:
            head=p.read_bytes()[:200]
            if head.startswith(b'version https://git-lfs.github.com/spec/v1'):lfs.append(rel)
    return {'evaluation_split_training_script_candidates':scripts,'license_files':licenses,'license_status':'file_present_text_not_legally_interpreted' if licenses else 'no_explicit_license_file_found',
            'gitmodules_present':any(x['path']=='.gitmodules' for x in files),'git_lfs_pointer_paths':lfs,'submodules_or_LFS_payloads_fetched':False}

def main():
    existing=sorted(p.relative_to(PROJECT/'resources').as_posix() for p in (PROJECT/'resources').glob('*') if p.resolve()!=HERE.resolve())
    paper=json.loads(PAPER_MAP.read_text(encoding='utf-8-sig'))
    with CSV.open(encoding='utf-8-sig',newline='') as f:targets=list(csv.DictReader(f))
    if {t['method'] for t in targets}!={'GraphDTA-GIN','MGraphDTA','DGDTA-CL','DeepNC-GEN','GS-DTA'}:raise ValueError('Frozen five-method map mismatch')
    started=now();results=[]
    write(HERE/'acquisition-contract.json',{'scope':'public upstream exact commit file archives only; assets_only/static inventory', 'started_utc':started,'network_timeout_seconds_per_repo':179,'attempts_per_repo':1,'max_download_bytes_per_repo':1073741824,'upstream_code_executed':False,'dependency_installation':False,'training_scoring_or_model_calls':0,'existing_resources_top_level':existing,'existing_resources_relevant_full_archives_found':False,'identity_csv_sha256':sha(CSV),'registered_paper_map_sha256':sha(PAPER_MAP)})
    for t in targets:
        method=t['method'];repo=t['repository'];commit=t['commit']
        if not re.fullmatch('[0-9a-f]{40}',commit) or not repo.startswith('https://github.com/'):raise ValueError('Invalid frozen target')
        if t['registered_task_id']!=paper[method]['task_id'] or t['doi']!=paper[method]['doi']:raise ValueError('Paper identity mismatch')
        slug=repo.removeprefix('https://github.com/');folder=HERE/method;folder.mkdir(exist_ok=False)
        url='https://codeload.github.com/'+slug+'/zip/'+commit
        archive=folder/(slug.split('/')[1]+'-'+commit+'.zip');part=archive.with_suffix('.zip.partial')
        row=dict(method_id=method,registered_task_id=t['registered_task_id'],doi=t['doi'],repository_url=repo,commit=commit,official_archive_url=url,started_utc=now(),attempts=1,reused_existing_archive=False)
        cmd=['curl.exe','--location','--fail','--show-error','--connect-timeout','20','--max-time','179','--max-filesize','1073741824','--retry','0','--dump-header',str(folder/'response-headers.txt'),'--output',str(part),url]
        begin=time.monotonic()
        try:
            p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=183,check=False)
            (folder/'curl.stdout.txt').write_bytes(p.stdout);(folder/'curl.stderr.txt').write_bytes(p.stderr)
            row.update(download_exit_code=p.returncode,download_seconds=time.monotonic()-begin,download_finished_utc=now())
            if p.returncode:raise RuntimeError('Bounded public archive request failed; no retry')
            part.rename(archive);row.update(archive_path=str(archive),archive_bytes=archive.stat().st_size,archive_sha256=sha(archive))
            extract_start=time.monotonic();root,files=verify_extract(archive,folder/'extracted',slug.split('/')[1]+'-'+commit)
            row.update(extraction_finished_utc=now(),extraction_seconds=time.monotonic()-extract_start,extracted_root=str(root),file_count=len(files),uncompressed_bytes=sum(f['bytes'] for f in files),archive_crc_verified=True)
            write(folder/'file-manifest.json',files);inv=inventory(root,files);write(folder/'author-evaluation-split-license-inventory.json',inv)
            row.update(status='complete_exact_commit_file_archive',file_manifest_sha256=sha(folder/'file-manifest.json'),inventory_sha256=sha(folder/'author-evaluation-split-license-inventory.json'),license_status=inv['license_status'],license_paths=[x['path'] for x in inv['license_files']],evaluation_split_script_candidate_count=len(inv['evaluation_split_training_script_candidates']),lfs_pointer_count=len(inv['git_lfs_pointer_paths']),gitmodules_present=inv['gitmodules_present'],complete_git_history=False)
        except Exception as e:
            row.update(status='asset_acquisition_failed',error=repr(e),elapsed_seconds=time.monotonic()-begin,finished_utc=now())
            if part.exists():row.update(partial_path=str(part),partial_bytes=part.stat().st_size,partial_sha256=sha(part))
        write(folder/'receipt.json',row);results.append(row);write(HERE/'progress.json',results)
        print(json.dumps({k:row[k] for k in ('method_id','status','archive_bytes','file_count','download_seconds','error') if k in row}),flush=True)
    manifest=dict(status='complete_five_assets' if all(r['status']=='complete_exact_commit_file_archive' for r in results) else 'partial_public_assets',started_utc=started,finished_utc=now(),script_sha256=sha(Path(__file__)),identity_csv_sha256=sha(CSV),registered_paper_map_sha256=sha(PAPER_MAP),repositories=results,upstream_code_executed=False,installed_dependencies=False,project_gold_predictions_models_or_training_labels_read=False,scientific_runs_started=0,asset_scope='Complete published file archive at exact commit; no git object history, no independently fetched LFS/submodules/external datasets.')
    write(HERE/'manifest.json',manifest)
    lines=['# 五方法官方完整文件快照','', '本目录保存冻结确切commit的官方GitHub文件归档及解压副本；没有执行作者代码、安装依赖或改变训练源码。完整文件归档与完整Git历史分别记账；LFS／子模块／外链数据未额外拉取。','', '| 方法 | commit | 状态 | 归档字节 | 文件数 | 许可文件 |','| --- | --- | --- | --- | --- | --- |']
    for r in results:lines.append('| '+' | '.join((r['method_id'],r['commit'],r['status'],str(r.get('archive_bytes','unknown')),str(r.get('file_count','unknown')),', '.join(r.get('license_paths',[])) or '未发现／未知'))+' |')
    lines+=['','每方法 receipt.json 记录官方URL、时间、退出与SHA；file-manifest.json记录所有归档文件的大小、CRC32、SHA；author-evaluation-split-license-inventory.json给出评价、划分、验证与checkpoint选择脚本的静态行线索。候选脚本出现关键词不证明执行正确或原实验协议已复现。','', '来源身份：control/registered-paper-map.json 与 report-preparation/predecessor-models.csv。既有resources只有本地依赖等资产；既有model-audit/author-source为selected-source，原件均保留。','', '如网络／CRC／解压失败，原失败和partial文件保留，当前任务每repo只进行一次有界网络请求。']
    (HERE/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'status':manifest['status'],'manifest_sha256':sha(HERE/'manifest.json'),'finished_utc':manifest['finished_utc']}),flush=True)

if __name__=='__main__':main()
