"""Adapt the data team's frozen ID manifests without changing their contents.

Controller staging reads the shared label container but only materializes train /
validation labels. Fit/canary processes never access the shared label container.
"""
import argparse
from pathlib import Path
import runner

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--frozen',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    frozen=Path(args.frozen).resolve()
    manifest=runner.read_json(frozen/'manifest.json')
    if manifest['status']!='frozen_for_authorized_baseline_execution':raise ValueError('Not frozen')
    for name in ('inputs.jsonl','labels.jsonl','quality-flags.jsonl'):
        runner.require_hash(frozen/name,manifest['files'][name]['sha256'])
    inputs={row['record_id']:row for row in runner.read_jsonl(frozen/'inputs.jsonl')}
    flags={row['record_id']:row for row in runner.read_jsonl(frozen/'quality-flags.jsonl')}
    output=Path(args.output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    plans=[]
    trainval_ids=set()
    for panel in manifest['primary_panels']:
        parts={}
        for part in ('train','validation','test'):
            ids=[]
            for regime in ('NC_only','standard_only'):
                relative=f'splits/{panel}/{regime}/{part}-ids.json'
                runner.require_hash(frozen/relative,manifest['files'][relative]['sha256'])
                ids.extend(runner.read_json(frozen/relative))
            if len(ids)!=len(set(ids)):raise ValueError('Repeated IDs across residue regimes')
            parts[part]=ids
        if set(parts['train'])&set(parts['validation']) or set(parts['train'])&set(parts['test']) or set(parts['validation'])&set(parts['test']):
            raise ValueError('Partition leakage')
        trainval_ids.update(parts['train']+parts['validation'])
        plans.append((panel,parts))
    # Shared label container is an explicitly disclosed controller input, never a worker input.
    selected_labels={}
    with (frozen/'labels.jsonl').open(encoding='utf-8') as handle:
        import json
        for line in handle:
            item=json.loads(line)
            if item['record_id'] in trainval_ids:
                selected_labels[item['record_id']]=item['pKd']
    panels=[]
    for panel,parts in plans:
        directory=output/panel
        directory.mkdir()
        for part in ('train','validation'):
            rows=[dict(inputs[rid],**{key:value for key,value in flags[rid].items() if key!='record_id'},
                       pKd=selected_labels[rid]) for rid in parts[part]]
            runner.write_jsonl(directory/(part+'.jsonl'),rows)
        runner.write_jsonl(directory/'test-inputs.jsonl',[dict(inputs[rid],**{key:value for key,value in flags[rid].items() if key!='record_id'}) for rid in parts['test']])
        panel_manifest=dict(split_id=panel,original_frozen_manifest_sha256=runner.sha_file(frozen/'manifest.json'),
                            counts={key:len(value) for key,value in parts.items()},
                            files={name:runner.sha_file(directory/name) for name in ('train.jsonl','validation.jsonl','test-inputs.jsonl')},
                            sealed_label_source=str(frozen/'labels.jsonl'),sealed_label_source_sha256=manifest['files']['labels.jsonl']['sha256'],
                            staging_boundary='controller opened shared label container; only train/validation labels materialized; workers never receive container path')
        runner.write_json(directory/'panel-manifest.json',panel_manifest)
        panels.append(dict(split_id=panel,directory=str(directory)))
    runner.write_json(output/'panels.json',panels)
    # Quantile sample across peptide SMILES lengths from first panel NC training IDs.
    first,parts=plans[0]
    train=[dict(inputs[rid],pKd=selected_labels[rid]) for rid in parts['train'] if inputs[rid]['NC_core']]
    train.sort(key=lambda row:(len(row['canonical_isomeric_smiles']),row['record_id']))
    import numpy as np
    indices=np.linspace(0,len(train)-1,32,dtype=int).tolist()
    sample=[train[index] for index in indices]
    runner.write_jsonl(output/'canary-train-32.jsonl',sample)
    runner.write_json(output/'canary-sample-manifest.json',dict(panel=first,regime='NC_only',n=32,
        sample_sha256=runner.sha_file(output/'canary-train-32.jsonl'),record_ids=[row['record_id'] for row in sample],
        allowed_train_ids=[row['record_id'] for row in train],
        sampling='32 evenly spaced empirical SMILES-length quantiles including min and max; no labels used for sampling',
        controller_opened_full_label_container=True,canary_or_fit_opened_full_label_container=False))
    print('Prepared '+str(len(panels))+' frozen panels and 32 train-only canary rows; no models executed.')

if __name__=='__main__':main()
