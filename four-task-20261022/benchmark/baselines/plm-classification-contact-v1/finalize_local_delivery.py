"""Final local inventory including post-archive fixed-prediction reports; no scientific execution."""
import csv
import datetime as dt
import json
from pathlib import Path
from mirror_artifacts import HERE,ROOT,RUN,sha,write

def load(path):return json.loads(path.read_text(encoding='utf-8'))
def main():
    source=load(HERE/'source-artifact-manifest.json')
    for item in source['files']:
        path=ROOT/item['path'];assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256']
    common=load(RUN/'common-classification-v2/independent-audit.json')
    primary=load(HERE/'DELIVERY-RECEIPT.json')
    assert common['passed'] and primary['passed']
    models=list((RUN/'heads').glob('*/*/seed-*/candidate-*.joblib'))
    results=list((RUN/'heads').glob('*/*/seed-*/result.json'))
    predictions=list((RUN/'heads').glob('*/*/seed-*/*-predictions.csv'))
    predictions+=list((RUN/'heads').glob('*/*/seed-*/candidate-*-validation.csv'))
    assert len(models)==200 and len(results)==100 and len(predictions)==400
    count=0
    for path in predictions:
        with path.open(encoding='utf-8',newline='') as stream:count+=sum(1 for _ in csv.DictReader(stream))
    assert count==803450
    supplement='''# 本地交付补充与共同测试子集

正式训练为两个任务×五类头×十种子：100个选中条件、200个候选权重。400份正式候选/选中验证与测试预测共803,450行；重复种子/候选共享原观测，这个行数是计算产物量。

共同分类2349/2290的权威结果在 `runs/plm-classification-contact-v1/common-classification-v2/`。100次固定预测应用完成231,950行ID/标签/端点/预测核对和720项sklearn及汇总数值核对，全部通过；主测试2362行及原验证阈值保持不变。这些是相同原测试记录的子集。

第一次共同子集写出在265字符Windows路径处遇到setup/path失败，保留90份已完成预测。revision2只缩短输出目录名，原90份与新版本逐SHA完全相同；原阈值、权重和主预测未改。历史文件不增加正式应用数。完整适配记录见 `common-windows-path-revision2.json`。

原1874个远端源文件/650,554,850字节在本地再次逐SHA通过。`local-final-delivery-index.json`另登记本地独立复算、共同子集、历史产物与报告的完整文件索引。原远端记录及已冻结CSV均保持原样。

分类的ESM+HistGB测试AUROC为0.9325、AUPRC为0.9301。接触任务的表现更弱：线性头总体AUROC为0.6777、AUPRC为0.2354；其12复合物宏AUROC为0.5798。逐残基总体与复合物宏结果应并列解读。十种子完整指标见RESULTS.md及CSV，不将不同训练覆盖的方法差异解释为纯表示贡献。

服务器特征、训练及只读核验进程均正常退出且无残留；core25/26及受保护siblings57/58已通知DTA owner释放。整分支GPU使用为0。归档、本地重复复算和本补充新增拟合/表示forward均为0。
'''
    (HERE/'DELIVERY-SUPPLEMENT.md').write_text(supplement,encoding='utf-8')
    excluded={'local-final-delivery-index.json','FINAL-LOCAL-RECEIPT.json'}
    files=sorted(p for base in [HERE,RUN] for p in base.rglob('*') if p.is_file() and p.name not in excluded and '__pycache__' not in p.parts)
    rows=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files]
    index={'schema':'frozen-esm2.binary-all-local-artifacts.v1','recorded_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'files':rows,'file_count':len(rows),'bytes':sum(r['bytes'] for r in rows),
        'remote_source_files_reverified':len(source['files']),'candidate_model_weights':len(models),
        'selected_conditions':len(results),'formal_prediction_csv_files':len(predictions),'formal_prediction_rows':count,
        'common_fixed_applications':100,'common_calculation_rows':231950,'diagnostic_partial_applications':90,
        'new_fit_count':0,'new_forward_count':0,'code_sha256':sha(__file__)}
    write(HERE/'local-final-delivery-index.json',index)
    receipt={'passed':True,'completed_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'selected_conditions':100,'candidate_fits':200,'all_local_files_indexed':len(rows),
        'remote_source_files_reverified':len(source['files']),'formal_prediction_rows':count,
        'numeric_checks_remote_and_local_each':1231350,'numeric_errors':0,
        'common_row_checks':231950,'common_numeric_checks':720,'common_numeric_errors':0,
        'gpu_jobs':0,'scientific_workers_still_running':False,'cpu_lease_released':True,
        'new_fit_count_for_finalization':0,'new_forward_count_for_finalization':0,
        'primary_delivery_receipt_sha256':sha(HERE/'DELIVERY-RECEIPT.json'),
        'local_final_index_sha256':sha(HERE/'local-final-delivery-index.json'),
        'supplement_sha256':sha(HERE/'DELIVERY-SUPPLEMENT.md'),
        'common_independent_audit_sha256':sha(RUN/'common-classification-v2/independent-audit.json'),
        'code_sha256':sha(__file__)}
    write(HERE/'FINAL-LOCAL-RECEIPT.json',receipt);print(json.dumps(receipt))

if __name__=='__main__':main()
