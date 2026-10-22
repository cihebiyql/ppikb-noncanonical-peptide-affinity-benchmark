"""Label-free representation alias counts; never changes the primary split."""
from collections import defaultdict
import common

def main():
    manifest=common.read(common.HERE/'X-final-manifest-v1.json')
    entry=[row for row in manifest['entries'] if row['dataset_id']=='PPIKB9619'][0]
    audits=common.jsonl(entry['audit_path']);fingerprints={row['record_id']:row['feature_sha256'] for row in audits}
    groups=defaultdict(list)
    for row in audits:groups[row['feature_sha256']].append(row['record_id'])
    results=[]
    for panel in common.PANELS:
        for regime in common.REGIMES:
            root=common.PROJECT/'data-protocol/frozen-v1/splits'/panel/regime
            parts={name:common.read(root/(name+'-ids.json')) for name in ('train','validation','test')}
            train_hash={fingerprints[rid] for rid in parts['train']}
            results.append(dict(panel=panel,regime=regime,
                validation_rows_aliasing_train=sum(fingerprints[rid] in train_hash for rid in parts['validation']),
                test_rows_aliasing_train=sum(fingerprints[rid] in train_hash for rid in parts['test']),
                validation_n=len(parts['validation']),test_n=len(parts['test'])))
    common.write(common.HERE/'representation-alias-audit-v1.json',dict(stage='label_free_diagnostic_only',
        feature_manifest_sha256=common.sha(common.HERE/'X-final-manifest-v1.json'),
        rows=len(audits),unique_feature_rows=len(groups),alias_groups=sum(len(ids)>1 for ids in groups.values()),
        per_panel_regime=results,actual_label_access=False,split_changed=False,rows_removed=0,
        interpretation='Exact descriptor aliases, not proof of identical chemistry or independent experiments; Morgan2048 collisions and coarse composition can alias. No performance used.'))
    print('Prepared label-free representation alias counts; no split or feature changes.')
if __name__=='__main__':main()
