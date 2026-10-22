"""Add the five current papers to a new batch; start no scientific process."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import re

PROJECT=Path(__file__).resolve().parent.parent
LIBRARY=PROJECT.parents[1]/'复现'
BATCH='peptide-binding-nc-benchmark-20261022'

def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    out=PROJECT/'control'
    existing=LIBRARY/'batches'/BATCH
    if existing.exists():
        raise FileExistsError('Already registered; preserve stable IDs and use registration-receipt.json')
    before=digest(LIBRARY/'campaign.json')
    indexpath=LIBRARY/'batches/index.json'
    index=load(indexpath)
    index_before=digest(indexpath)
    catalogs=[LIBRARY/'campaign.json',*list((LIBRARY/'batches').glob('*/campaign.json'))]
    number=max(int(x) for p in catalogs for x in re.findall(r'S(\d{3,})[_"]',p.read_text(encoding='utf-8')))
    side=load(PROJECT/'model-audit/papers/primary-method-verification-sidecar-v3.json')
    source={m['method']:m for m in side['models']}
    source['GS-DTA']=load(PROJECT/'model-audit/replacement-gs-dta/candidate-audit.json')['paper']
    methods=['GraphDTA-GIN','MGraphDTA','DGDTA-CL','DeepNC-GEN','GS-DTA']
    folders={'GraphDTA-GIN':'graphdta-deepnc','MGraphDTA':'mgraph-dgdta','DGDTA-CL':'mgraph-dgdta','DeepNC-GEN':'graphdta-deepnc','GS-DTA':'gs-dta'}
    tasks=[];summaries=[];mapping={}
    for method in methods:
        paper=source[method]
        pdf=Path(paper['pdf_path']);sha=digest(pdf)
        assert sha==paper['pdf_sha256'] and pdf.read_bytes().startswith(b'%PDF-')
        number+=1
        task_id=f'S{number}_{sha[:12]}'
        title=paper.get('paper_title',paper.get('title'))
        date=paper.get('publication_dates',{}).get('first_online')
        task=dict(task_id=task_id,priority_rank=number,title=title,doi=paper['doi'],
                  publication_date=date,publication_date_source=str(PROJECT/'model-audit'),
                  journal=None,publication_status='published',pdf_path=str(pdf),source_sha256=sha,
                  paper_id=None,source_url='https://doi.org/'+paper['doi'],linked_task_ids=[],
                  registration_type='new_paper',intended_level='training',scope_coverage='partial_subset',
                  administrative_registration_only=True,scientific_execution_authorization='latest direct user message: PPIKB NC2099 affinity benchmark, standard controls, five prior methods, seeds0-9; no novel model',clock_started_by_registration=False,clock_reset=False,
                  resource_roots=[dict(group='documents',name='论文与来源审计',path=str(PROJECT/'model-audit'),kind='directory'),dict(group='code',name='作者方法与隔离适配',path=str(PROJECT/'methods'/folders[method]),kind='directory'),dict(group='materials',name='真实原出版PDF',path=str(pdf),kind='file'),dict(group='results',name='本轮合同与结果',path=str(PROJECT),kind='directory')])
        tasks.append(task)
        mapping[method]=dict(task_id=task_id,doi=paper['doi'],pdf_path=str(pdf),pdf_sha256=sha,linked_task_ids=[])
        summaries.append(dict(task_id=task_id,title=title,doi=paper['doi'],status='registered',lifecycle_status='ready',reproduction_level='smoke',scope_coverage='component_only',summary='本轮新NC亲和力共同基准：作者实现与CPU/GPU训练步已验证，正式十种子训练待启动。',pdf_path=str(pdf),source_sha256=sha,linked_task_ids=[],publication_status='published',dataset='PPIKB NC2099＋标准7520；来源/肽依赖冷与参考序列同源冷，原数据及身份冲突旗标保留。',innovation='无创新模型；五篇已发表方法共同数据适配比较。',actual_results='仅模型与训练步smoke；没有正式模型性能指标。',differences='非原论文数据/主表；完整分子图、作者蛋白前缀、统一有限调参预算。',incomplete_reason='等待冻结真实运行合同及启动；原始PDF和作者代码已齐。',execution_location='本地WSL RTX5080通用现有runtime；Node23仅预处理，Node1忙碌GPU不使用。'))
    # Campaign registration precedes new per-paper directories.
    write(existing/'campaign.json',dict(schema='paper-lumen.supplemental-reproduction-campaign.v1',batch_id=BATCH,label='PPIKB非标准肽亲和力五方法十种子基准',registration_date=dt.datetime.now(dt.timezone.utc).isoformat(),administrative_registration_only=True,scientific_execution_by_registration=False,source_run=str(PROJECT),authorization_reference=str(PROJECT/'control/user-authorization.json'),clock_policy='new explicit NC benchmark objective; hard deadline2026-10-22T01:45Z, no clock reset',tasks=tasks,task_count=5,new_paper_count=5,linked_existing_paper_count=0))
    write(existing/'summary-rows.json',summaries)
    for task in tasks:
        p=LIBRARY/'papers'/task['task_id']
        p.mkdir(exist_ok=False)
        write(p/'metadata.json',task)
        write(p/'status.json',dict(lifecycle_status='ready',reproduction_level='smoke',scope_coverage='component_only',project=str(PROJECT),formal_training_started=False,old_campaign_unmodified=True))
    index['batches'].append(dict(id=BATCH,label='PPIKB非标准肽亲和力五方法十种子基准（2026-10-22）',campaign=BATCH+'/campaign.json',summaries=BATCH+'/summary-rows.json'))
    write(indexpath,index)
    assert digest(LIBRARY/'campaign.json')==before
    write(out/'registered-paper-map.json',mapping)
    write(out/'registration-receipt.json',dict(batch_id=BATCH,task_count=5,paper_map=mapping,old_main_campaign_sha256=before,old_main_campaign_unchanged=True,batch_index_before_sha256=index_before,batch_index_after_sha256=digest(indexpath),new_batch_campaign_sha256=digest(existing/'campaign.json'),scientific_processes_started=0))
    print(json.dumps(mapping,ensure_ascii=False))

if __name__=='__main__':main()
