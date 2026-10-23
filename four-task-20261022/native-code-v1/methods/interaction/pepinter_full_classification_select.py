"""Validation-only twoLR selection after both fullnative candidates finish; no model load."""
import argparse,csv,json,math
from pathlib import Path
from common import now,save,sha,read_view
from pepinter_full_classification_utils import batch_equal_mean_fp32
p=argparse.ArgumentParser();p.add_argument('--candidate0-summary',required=True);p.add_argument('--candidate1-summary',required=True);p.add_argument('--fit-data',required=True);p.add_argument('--seed',type=int,required=True);p.add_argument('--test-view-sha256',required=True);p.add_argument('--output',required=True);a=p.parse_args()
rows,excluded=read_view(a.fit_data);assert not excluded and set(r['split'] for r in rows)=={'train','validation'}
validation=[r for r in rows if r['split']=='validation'];assert len(validation)==2158
candidates=[]
for index,path in enumerate([a.candidate0_summary,a.candidate1_summary]):
 path=Path(path);s=json.loads(path.read_text());out=path.parent;config=json.loads((out/'frozen-configuration.json').read_text())
 assert s['status']=='succeeded' and s['mode']=='fit_candidate' and s['seed']==a.seed and s['candidate']==index and s['learning_rate']==[1e-4,1e-5][index]
 assert s['epochs_completed']==5 and s['optimizer_steps']==2270 and s['training_rows_each_epoch']==10882 and s['validation_rows']==2158 and s['test_rows_processed']==0
 assert s['parameters']==s['trainable_parameters']==576293761 and config['identity']['data_sha256']==sha(a.fit_data)
 with (out/'validation-batch-Focal.csv').open(newline='') as f:batch=list(csv.DictReader(f))
 with (out/'validation-predictions.csv').open(newline='') as f:pred=list(csv.DictReader(f))
 assert len(batch)==math.ceil(2158/24) and sum(int(r['rows']) for r in batch)==2158
 assert [r['row_id'] for r in pred]==[r['row_id'] for r in validation] and all(float(r['label'])==v['label'] and int(r['seed'])==a.seed and math.isfinite(float(r['prediction'])) for r,v in zip(pred,validation))
 recomputed=batch_equal_mean_fp32([float(r['native_batch_mean_Focal']) for r in batch]);monitor=s['native_validation_equal_batch_Focal']
 assert math.isclose(recomputed,monitor,abs_tol=1e-7,rel_tol=1e-7),'Exact native FP32 batch-equal monitor mechanism must match; no sample-weighted substitution'
 checkpoint=s['full_checkpoint'];assert Path(checkpoint['path']).is_file() and Path(checkpoint['path']).stat().st_size==checkpoint['bytes']
 assert sha(out/'validation-predictions.csv')==s['validation']['prediction_sha256']
 candidates.append({'candidate':index,'learning_rate':s['learning_rate'],'native_validation_Focal_monitor':monitor,'independent_FP32_batch_equal_recomputation':recomputed,'summary_path':str(path),'summary_sha256':sha(path),'checkpoint':checkpoint,'fit_identity':config['identity'],'validation_prediction_sha256':sha(out/'validation-predictions.csv'),'full_checkpoint_actual_rehash_deferred_to_required_preTEST_standard_contract':True})
selected=min(candidates,key=lambda x:(x['native_validation_Focal_monitor'],x['candidate']))
output=Path(a.output);assert not output.exists(),'Selection must be frozen once before TEST evaluation'
record={'schema':'fourtask.pepinter-full-native-selection.v1','selected_at':now(),'seed':a.seed,'candidate':selected['candidate'],'learning_rate':selected['learning_rate'],'selection_metric':'Author-style FP32 equalbatchmean nativeFocal at epoch5','tie_rule':'candidate0 original1e-4 beforecandidate1','selected_before_test':True,'test_view_sha256':a.test_view_sha256,'test_rows_read_or_evaluated':0,'checkpoint_path':selected['checkpoint']['path'],'checkpoint_sha256':selected['checkpoint']['sha256'],'fit_identity':selected['fit_identity'],'candidates':candidates,'new_fit_or_model_forward':0,'monitor_scope':'2LR grid is this task HPO adaptation; both retain full5epochs/native24batch, no each-epochvalidation/earlystop'}
save(output,record);print(json.dumps({'selection_path':str(output),'sha256':sha(output),'candidate':selected['candidate'],'new_fit_or_model_forward':0}))
