"""Freeze validation-only HPO selection after two completed candidate jobs."""
import argparse
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def rows(path):
    with Path(path).open(encoding='utf-8',newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,choices=range(10),required=True)
    parser.add_argument('--candidate0',type=Path,required=True)
    parser.add_argument('--candidate1',type=Path,required=True)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--input-sha',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    assert sha(args.input)==args.input_sha and not args.output.exists()
    validation=[row for row in rows(args.input) if row['split']=='validation']
    assert len(validation)==63
    candidates=[]
    for candidate,folder in enumerate((args.candidate0,args.candidate1)):
        result=json.loads((folder/'result.json').read_text())
        fit=json.loads((folder/'fit-receipt.json').read_text())
        history=json.loads((folder/'history.json').read_text())
        assert result['phase']=='candidate_train' and result['real_candidate_fits_completed']==1
        assert not result['test_evaluated'] and not fit['test_evaluated']
        assert fit['seed']==args.seed and fit['candidate']==candidate
        assert fit['initial_lr']==(3e-4,1e-4)[candidate]
        assert fit['input_sha256']==args.input_sha
        assert len(history)==fit['epochs_ran'] and 1<=len(history)<=30
        assert len(history)==30 or len(history)-fit['best_epoch']==5
        best=min(history,key=lambda row:(row['validation_native_MSE'],row['epoch']))
        assert best['epoch']==fit['best_epoch']
        assert fit['optimizer_steps']==37*len(history)
        path=Path(fit['checkpoint_path']);assert sha(path)==fit['checkpoint_sha256']
        predictions=rows(folder/'validation-predictions.csv')
        assert [row['row_id'] for row in predictions]==[row['row_id'] for row in validation]
        assert all(abs(float(row['label'])-float(ref['DDG']))<1e-12 for row,ref in zip(predictions,validation))
        assert all(math.isfinite(float(row['prediction'])) for row in predictions)
        mae=sum(abs(float(row['label'])-float(row['prediction'])) for row in predictions)/63
        assert abs(mae-fit['validation_forward_MAE'])<1e-10
        candidates.append({'candidate':candidate,'fit_receipt_path':str(folder/'fit-receipt.json'),
            'fit_receipt_sha256':sha(folder/'fit-receipt.json'),
            'checkpoint_path':str(path),'checkpoint_sha256':fit['checkpoint_sha256'],
            'validation_forward_MAE':mae,'validation_predictions_sha256':sha(folder/'validation-predictions.csv'),
            'initial_trainable_state_sha256':fit['initial_trainable_state_sha256'],
            'initial_buffers_sha256':fit['initial_buffers_sha256'],
            'source_manifest_sha256':fit['source_manifest_sha256'],
            'protocol_sha256':fit['protocol_sha256'],'execution_protocol_sha256':fit['execution_protocol_sha256'],
            'best_epoch':fit['best_epoch'],'epochs_ran':len(history)})
    for key in ('initial_trainable_state_sha256','initial_buffers_sha256','source_manifest_sha256',
                'protocol_sha256','execution_protocol_sha256'):
        assert candidates[0][key]==candidates[1][key],key
    winner=min(candidates,key=lambda row:(row['validation_forward_MAE'],row['candidate']))
    selection={'schema':'fourtask.uniair.MoFPE.frozen-validation-HPO.v3',
        'frozen_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'seed':args.seed,'winner':winner['candidate'],'candidates':candidates,
        'selected_checkpoint_path':winner['checkpoint_path'],
        'selected_checkpoint_sha256':winner['checkpoint_sha256'],
        'selected_epoch':winner['best_epoch'],'test_used_for_selection':False,
        'input_sha256':args.input_sha,'validation_IDs':[row['row_id'] for row in validation],
        'rule':'Each candidate best-native-MSE checkpoint, then minimum validation-forward-MAE;tie prefer3e-4',
        'model_instances':0,'new_forward_calls':0}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(selection,indent=2)+'\n')
    print(json.dumps({'selection_path':str(args.output),'sha256':sha(args.output),'winner':winner['candidate']}))


if __name__=='__main__':main()
