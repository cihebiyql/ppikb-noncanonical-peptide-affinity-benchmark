"""Metadata-only CLM2 ring-digit tokenization audit. Never imports torch/models."""
from __future__ import annotations
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import socket
import sys
import time


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-csv', required=True, type=Path)
    parser.add_argument('--expected-input-sha256', required=True)
    parser.add_argument('--tokenizer-json', required=True, type=Path)
    parser.add_argument('--expected-tokenizer-sha256', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--cpu', type=int, default=28)
    args = parser.parse_args()
    started = time.monotonic()
    resource.setrlimit(resource.RLIMIT_AS, (2*1024**3, 2*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (85, 85))
    if os.sched_getaffinity(0) != {args.cpu} or os.nice(0) < 19:
        raise ValueError('Expected owner-selected single CPU and nice19')
    if args.output.exists():
        raise ValueError('Use a new metadata run directory')
    args.output.mkdir(parents=True)
    assert sha_file(args.input_csv) == args.expected_input_sha256
    assert sha_file(args.tokenizer_json) == args.expected_tokenizer_sha256
    from tokenizers import Tokenizer, Regex, pre_tokenizers
    import tokenizers
    source = json.loads(args.tokenizer_json.read_text())
    old_regex = source['pre_tokenizer']['pattern']['Regex']
    assert source['pre_tokenizer']['type'] == 'Split' and source['pre_tokenizer']['behavior'] == 'Isolated'
    assert source['pre_tokenizer']['invert'] is False and source['normalizer'] is None
    assert old_regex.startswith('(') and old_regex.endswith(')') and '[0-9]' not in old_regex
    assert source['model']['vocab']['1'] == 107 and source['model']['vocab']['2'] == 69
    assert '12' not in source['model']['vocab'] and '##2' not in source['model']['vocab']
    native = Tokenizer.from_file(str(args.tokenizer_json))
    fixed = Tokenizer.from_file(str(args.tokenizer_json))
    # Match complete percent ring tokens before individual digits; preserve native %12.
    new_regex = old_regex[:-1] + '|%[0-9]{2}|[0-9])'
    fixed.pre_tokenizer = pre_tokenizers.Split(Regex(new_regex), behavior='isolated', invert=False)
    fixed_json = json.loads(fixed.to_str())
    native_json = json.loads(native.to_str())
    core_old = dict(native_json)
    core_new = dict(fixed_json)
    core_old.pop('pre_tokenizer')
    core_new.pop('pre_tokenizer')
    assert core_old == core_new and native.get_vocab() == fixed.get_vocab()
    recipe = {'schema':'chemical-encoder.tokenizer-ringfix.v2',
        'base_tokenizer_sha256':args.expected_tokenizer_sha256,
        'old_regex_sha256':sha_bytes(old_regex.encode()), 'old_regex':old_regex,
        'new_regex_sha256':sha_bytes(new_regex.encode()), 'new_regex':new_regex,
        'change':'Append %[0-9]{2} then [0-9] isolated alternatives to existing pre_tokenizer.Split regex only; original alternatives retain priority',
        'vocabulary_unchanged':True, 'normalizer_unchanged':True, 'post_processor_unchanged':True,
        'weights_modified':False, 'smiles_modified':False,
        'qualification':'Versioned input adapter. Known percent-ring tokens remain intact; unknown percent-ring tokens/atoms remain rejected; no universal SMILES/atom support claim.'}
    recipe_blob=(json.dumps(recipe,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
    (args.output/'recipe.json').write_bytes(recipe_blob)
    (args.output/'tokenizer.ringfix.json').write_text(fixed.to_str(pretty=True)+'\n',encoding='utf-8')
    unique = {}
    with args.input_csv.open(encoding='utf-8-sig',newline='') as handle:
        reader=csv.DictReader(handle)
        if not set(reader.fieldnames).issubset({'smiles','smiles_sha256'}):
            raise ValueError('Pure SMILES input only; no labels or split fields')
        for row in reader:
            smiles=row['smiles'];key=sha_bytes(smiles.encode())
            if row.get('smiles_sha256') and row['smiles_sha256'] != key:
                raise ValueError('Input molecule key mismatch')
            unique[key]=smiles
    with (args.output/'input-only.csv').open('w',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=['smiles_sha256','smiles']);writer.writeheader()
        writer.writerows({'smiles_sha256':key,'smiles':smiles} for key,smiles in sorted(unique.items()))

    def inspect(tokenizer,smiles):
        encoded=tokenizer.encode(smiles,add_special_tokens=True)
        unknown=[];covered=[False]*len(smiles)
        for token_id,(a,b),special in zip(encoded.ids,encoded.offsets,encoded.special_tokens_mask):
            if not special:
                covered[a:b]=[True]*(b-a)
                if token_id==1:unknown.append({'span':[a,b],'text':smiles[a:b]})
        return {'ids':encoded.ids,'offsets':encoded.offsets,'unknown':unknown,
                'token_count':len(encoded.ids),'all_characters_covered':all(covered),
                'accepted':not unknown and len(encoded.ids)<=768 and all(covered)}

    totals=Counter();unknown_spans=Counter();new_unknown_spans=Counter();audit=[]
    for key,smiles in sorted(unique.items()):
        if time.monotonic()-started>80:raise TimeoutError('Metadata wall budget reached')
        old,new=inspect(native,smiles),inspect(fixed,smiles)
        totals['raw_inputs']+=1
        totals['native_unknown_inputs']+=bool(old['unknown'])
        totals['native_over_budget']+=old['token_count']>768
        totals['fixed_unknown_inputs']+=bool(new['unknown'])
        totals['fixed_over_budget']+=new['token_count']>768
        totals['native_accepted']+=old['accepted'];totals['fixed_accepted']+=new['accepted']
        totals['percent_nn_inputs']+=('%' in smiles)
        unknown_spans.update(x['text'] for x in old['unknown'])
        new_unknown_spans.update(x['text'] for x in new['unknown'])
        if old['accepted']:
            totals['native_accepted_ids_unchanged']+=old['ids']==new['ids']
        expected=[];ring_only=all(x['text']=='12' for x in old['unknown'])
        for value in old['ids']:
            expected.extend([107,69] if value==1 else [value])
        repaired=bool(old['unknown']) and ring_only and new['accepted'] and new['ids']==expected
        totals['ring12_only_repaired_inputs']+=repaired
        row={'smiles_sha256':key,'native':old,'fixed':new,'ring12_only_repaired':repaired,
             'input_byte_identity_unchanged':sha_bytes(smiles.encode())==key}
        audit.append(row)
    with (args.output/'per-input-token-audit.jsonl').open('w',encoding='utf-8') as handle:
        for row in audit:handle.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
    examples={
        'alanine_L':'N[C@@H](C)C(=O)O','alanine_D':'N[C@H](C)C(=O)O',
        'serine':'N[C@@H](CO)C(=O)O','phosphoserine':'N[C@@H](COP(=O)(O)O)C(=O)O',
        'Trp_fused12_L':'N[C@@H](Cc1c[nH]c2ccccc12)C(=O)O',
        'Trp_fused12_D':'N[C@H](Cc1c[nH]c2ccccc12)C(=O)O',
        'percent_ring':'C%12CCCCC%12','unknown_percent_ring':'C%99CCCCC%99',
        'unsupported_isotope_stereo':'N[13C@@H](C)C(=O)O',
    }
    canaries={name:{'native':inspect(native,s),'fixed':inspect(fixed,s)} for name,s in examples.items()}
    canary_checks={
        'native_L_D_preserved':canaries['alanine_L']['native']['ids']==canaries['alanine_L']['fixed']['ids'] and canaries['alanine_D']['native']['ids']==canaries['alanine_D']['fixed']['ids'],
        'fixed_L_D_distinct':canaries['alanine_L']['fixed']['ids']!=canaries['alanine_D']['fixed']['ids'],
        'PTM_tokens_preserved':canaries['serine']['native']['ids']==canaries['serine']['fixed']['ids'] and canaries['phosphoserine']['native']['ids']==canaries['phosphoserine']['fixed']['ids'],
        'PTM_distinct':canaries['serine']['fixed']['ids']!=canaries['phosphoserine']['fixed']['ids'],
        'fused_Trp12_recovered':not canaries['Trp_fused12_L']['native']['accepted'] and canaries['Trp_fused12_L']['fixed']['accepted'] and canaries['Trp_fused12_D']['fixed']['accepted'],
        'fused_Trp_stereo_preserved':canaries['Trp_fused12_L']['fixed']['ids']!=canaries['Trp_fused12_D']['fixed']['ids'],
        'known_percent_ring_preserved':canaries['percent_ring']['native']['accepted'] and canaries['percent_ring']['native']['ids']==canaries['percent_ring']['fixed']['ids'],
        'unknown_percent_ring_still_rejected':not canaries['unknown_percent_ring']['fixed']['accepted'],
        'other_unknown_still_rejected':not canaries['unsupported_isotope_stereo']['fixed']['accepted'],
    }
    go=(totals['raw_inputs']==1238 and totals['native_accepted']==921 and totals['native_unknown_inputs']==317
        and totals['native_over_budget']==0 and dict(unknown_spans)=={'12':438}
        and totals['native_accepted_ids_unchanged']==921 and totals['ring12_only_repaired_inputs']==317
        and totals['fixed_accepted']==1238 and totals['fixed_unknown_inputs']==0 and totals['fixed_over_budget']==0
        and all(canary_checks.values()))
    process={'host':socket.gethostname(),'pid':os.getpid(),'pgid':os.getpgid(0),'uid':os.getuid(),
             'cpu_affinity':sorted(os.sched_getaffinity(0)),'nice':os.nice(0),
             'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
    report={'schema':'chemical-encoder.ringfix-metadata-audit.v2','status':'GO' if go else 'NO_GO',
        'finished_at_utc':datetime.now(timezone.utc).isoformat(),'totals':dict(totals),
        'native_unknown_spans':dict(unknown_spans),'fixed_unknown_spans':dict(new_unknown_spans),
        'canary_checks':canary_checks,'canaries':canaries,'recipe_sha256':sha_bytes(recipe_blob),
        'fixed_tokenizer_json_sha256':sha_file(args.output/'tokenizer.ringfix.json'),
        'input_csv_sha256':args.expected_input_sha256,'original_tokenizer_sha256':args.expected_tokenizer_sha256,
        'code_sha256':sha_file(__file__),'tokenizers_version':tokenizers.__version__,
        'vocabulary_and_other_tokenizer_components_identical':core_old==core_new,
        'input_graph_preservation':'All complete original isomeric SMILES byte hashes unchanged; no molecular string canonicalization, graph rewrite, or chemistry substitution performed.',
        'scope':'Metadata tokenization only; no binding labels, embeddings, weights or model imported/read',
        'torch_imported':'torch' in sys.modules,'model_forwards':0,'fits':0,'weights_read':0,
        'process':process,'elapsed_seconds':time.monotonic()-started,
        'native_v1_preserved':True,'global_freeze_roles_modified':False,
        'percent_ring_note':'%nn branch precedes single digits: known %12 token is preserved; unknown %99 is still rejected. This adapter is versioned and does not establish universal SMILES support.'}
    write_json(args.output/'AUDIT.actual.json',report)
    print(json.dumps({k:report[k] for k in ['status','totals','native_unknown_spans','canary_checks','recipe_sha256','process','elapsed_seconds','torch_imported']},ensure_ascii=False))
    return 0 if go else 2


if __name__=='__main__':
    raise SystemExit(main())
