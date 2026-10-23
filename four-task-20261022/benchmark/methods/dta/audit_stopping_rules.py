"""Metadata-only stopping audit of accepted fitted models; no fit or forward."""
import datetime,hashlib,json
from pathlib import Path
from export_complete_dta_report import local
from stopping_rules import validate_stopping
H=Path(__file__).resolve().parent
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    p=load(H/'accepted-details-current.json');d=load(local(p['path']));assert sha(local(p['path']))==p['sha256'];rows=[];errors=[]
    for x in d['records']:
        unit=local(x['path']).parent;selection=load(unit/'selection.json')
        for c in selection['candidates']:
            ep=unit/('candidate-'+str(c['candidate_index']))/'epochs.jsonl';epochs=[json.loads(z) for z in ep.read_text(encoding='utf-8').splitlines() if z.strip()]
            try:
                info=validate_stopping(epochs,c['best_epoch'],x['n']['train'])
                rows.append({'logical_key':[x['view'],x['method'],x['seed']],'candidate':c['candidate_index'],'epochs_sha256':sha(ep),**info})
            except Exception as e:errors.append({'logical_key':[x['view'],x['method'],x['seed']],'candidate':c['candidate_index'],'error':repr(e)})
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');out=H/('stopping-rule-audit-'+stamp+'.json');r={'at':stamp,'accepted_details_sha256':p['sha256'],'accepted_units':len(d['records']),'candidate_count':len(rows),'epoch_bound_without_patience':sum(x['epoch_bound_without_patience'] for x in rows),'patience_exhausted':sum(x['patience_exhausted'] for x in rows),'rows':rows,'errors':errors,'scope':'frozen20epoch/pat5 metadata only; no model evaluation or fit'};out.write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps({'path':str(out),'accepted_units':r['accepted_units'],'candidate_count':r['candidate_count'],'epoch_bound_without_patience':r['epoch_bound_without_patience'],'errors':len(errors)}))
    if errors:raise SystemExit(2)
if __name__=='__main__':main()
