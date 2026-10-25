import ast,json,runpy,sys
from pathlib import Path
base=Path(__file__).parent
u=runpy.run_path(str(base/'audit_training60_expanded_local_v4.py'))
job,proc=u['guard']()
checks=[]
for m,ident in u['IDENTITIES'].items():
 field='model' if m=='2025' else 'repository'
 assert u['model_identifier_matches'](m,ident);checks.append(m+': exact identifier accepted')
 wrong=dict(ident);wrong[field]=ident[field]+'-wrong'
 assert not u['model_identifier_matches'](m,wrong);checks.append(m+': wrong identifier rejected')
 wrong=dict(ident);del wrong[field];wrong['repository' if field=='model' else 'model']=ident[field]
 assert not u['model_identifier_matches'](m,wrong);checks.append(m+': wrong field rejected')
 assert not u['model_identifier_matches'](m,{});checks.append(m+': missing identifier rejected')
assert not u['model_identifier_matches']('unknown',{});checks.append('unknown encoder rejected')
source=(base/'audit_training60_expanded_local_v4.py').read_text()
assert "check(contract['model_identity']==IDENTITIES[m],key+': exact scientific model identity')" in source
ast.parse(source);ast.parse((base/'audit_selected30_expanded_local_v3.py').read_text())
assert not 'torch' in sys.modules
print(json.dumps({'status':'PASS','checks':checks,'count':len(checks),'process':proc,'NN':0,'fit':0,'full_exact_identity_check_retained':True}))
