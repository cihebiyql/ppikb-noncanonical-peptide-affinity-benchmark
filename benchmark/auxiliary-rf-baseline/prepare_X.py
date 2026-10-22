"""One CPU label-free feature preparation stage, no label/weights/model access."""
from pathlib import Path
import json
import os
import resource
import time
import numpy as np
import features

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parent
SOURCES={'PPIKB9619':'data-protocol/frozen-v1/inputs.jsonl',
         'external75':'external-validation/scoring-views-v1/inputs75.jsonl',
         'supplement13':'external-validation/scoring-supplement13-v1/inputs/input13.jsonl'}
def main():
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    root=HERE/'fixed-X-v1';root.mkdir(exist_ok=False)
    entries=[];started=time.time()
    for name,relative in SOURCES.items():
        path=PROJECT/relative;rows=features.read_label_free(path)
        matrix=np.empty((len(rows),features.DIMENSION),dtype=np.float32)
        audits=[]
        for index,row in enumerate(rows):matrix[index],audit=features.encode_record(row);audits.append(audit)
        np.save(root/(name+'.npy'),matrix,allow_pickle=False)
        (root/(name+'.ids.json')).write_text(json.dumps([row['record_id'] for row in rows]),encoding='utf-8')
        with (root/(name+'.audit.jsonl')).open('w',encoding='utf-8') as handle:
            for row in audits:handle.write(json.dumps(row)+'\n')
        entries.append(dict(dataset_id=name,input_relative=relative,input_sha256=features.sha(path),n=len(rows),
            matrix_path=str(root/(name+'.npy')),matrix_sha256=features.sha(root/(name+'.npy')),
            record_ids_path=str(root/(name+'.ids.json')),record_ids_sha256=features.sha(root/(name+'.ids.json')),
            audit_path=str(root/(name+'.audit.jsonl')),audit_sha256=features.sha(root/(name+'.audit.jsonl')),
            dimensions=features.DIMENSION,dtype='float32',actual_label_access=False))
        del matrix,rows,audits
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>2*1024**3:raise MemoryError('Feature stage exceeded2GiB RSS')
    manifest=dict(status='label_free_fixed_RF_X_prepared',entries=entries,dimensions=features.DIMENSION,
        feature_spec_sha256=features.sha(HERE/'feature-spec-v1.json'),feature_code_sha256=features.sha(HERE/'features.py'),
        installed_assets_sha256=features.sha(HERE/'installed-assets-v1.json'),cpu_threads=1,CUDA_VISIBLE_DEVICES='',
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,elapsed_seconds=time.time()-started,
        real_fits=0,gold_reads=0,trained_model_reads=0,learned_transform_fits=0)
    (HERE/'X-final-manifest-v1.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
