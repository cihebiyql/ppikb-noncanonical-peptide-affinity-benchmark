"""Read-only external holdout preparation; no model training or source correction.

Gold was inspected in earlier projects: these are retrospective, independently
sourced candidate holdouts, not prospective blinded measurements. Inputs carry no
affinity outcomes. Chemistry is never reduced to a standard backbone as a substitute
for the measured chemical entity.
"""
from pathlib import Path
from collections import Counter, defaultdict
import csv, hashlib, json, math, re, xml.etree.ElementTree as ET
import openpyxl

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1] / 'peptide-binding-expanded-corpus-20261021'
OLD = HERE.parents[1] / 'peptide-binding-benchmark-20261020/ten-seed-external-20261021/external/pepbi_pdz'
RESCREEN = BASE / 'rescreen-noncanonical-priority-20261021/other-resources'
AA = set('ACDEFGHIKLMNPQRSTVWY')
SOURCES = []

def loadl(path):
    return [json.loads(l) for l in path.open(encoding='utf-8') if l.strip()]

def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

def jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        for row in rows: f.write(json.dumps(row, ensure_ascii=False) + '\n')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def doi(v):
    return re.sub(r'^https?://(?:dx\.)?doi\.org/', '', str(v or '').strip().lower()).rstrip(' .')

def normtitle(v):
    return re.sub(r'[^a-z0-9]', '', str(v or '').lower())

def meta(resource, study):
    """Metadata only from existing local XML; no experimental body interpretation."""
    p = BASE / 'resources' / resource / 'article.xml'
    d = {'doi': study, 'title': None, 'pmid': None}
    if p.exists():
        am = ET.parse(p).find('./front/article-meta')
        if am is not None:
            for el in am.findall('article-id'):
                k = el.get('pub-id-type')
                if k in ('doi', 'pmid'): d[k] = (el.text or '').strip()
            el = am.find('./title-group/article-title')
            if el is not None: d['title'] = ''.join(el.itertext())
    return d

def finite(v):
    try: return math.isfinite(float(v))
    except (TypeError, ValueError): return False

def main():
    ppipath = BASE / 'resources/PPIKB_all_endpoints/normalized-observations.jsonl'
    pp = loadl(ppipath)
    aliases = {
        'SH2_ProBound': meta('SH2_ProBound', '10.1002/pro.70317'),
        'Kliche2023_phosphomimetic': meta('Kliche2023_phosphomimetic', '10.15252/msb.202211164'),
        'ProfAff2022': {'doi':'10.1038/s41467-022-33018-0', 'pmid':None, 'title':None},
    }
    # ProfAff title/PMID are read back from the local original metadata below;
    # no manually supplied title/PMID is accepted as source authority.
    pxml = OLD / 'pdz.xml'
    if pxml.exists():
        am = ET.parse(pxml).find('./front/article-meta')
        if am is not None:
            for el in am.findall('article-id'):
                if el.get('pub-id-type') in ('doi','pmid'): aliases['ProfAff2022'][el.get('pub-id-type')] = (el.text or '').strip()
            el = am.find('./title-group/article-title')
            if el is not None: aliases['ProfAff2022']['title'] = ''.join(el.itertext())
    genes = {'c-Src SH2':('SRC','P12931'), 'Fyn SH2':('FYN','P06241'), 'Lyn SH2':('LYN','P07948'), 'Grb2 SH2':('GRB2','P62993')}
    refs = {}
    for name, (gene, accession) in genes.items():
        rows = [r for r in pp if r['target_id']==accession and gene in str(r.get('row_raw',{}).get('Gene_Names','')).split(';')]
        if not rows: rows=[r for r in pp if r['target_id']==accession and r.get('row_raw',{}).get('Gene')==gene]
        unique = {r['target_sequence'] for r in rows if r.get('target_sequence')}
        assert len(unique)==1, (name, len(unique))
        refs[name] = (accession, unique.pop(), [r['record_id'] for r in rows])
    inputs=[]; gold=[]; preserved=[]; excluded=[]
    for resource in ('SH2_ProBound','Kliche2023_phosphomimetic'):
        source=BASE/'resources'/resource/'normalized-observations.jsonl'
        SOURCES.append(source)
        for r in loadl(source):
            mods=r.get('modifications') or []
            if not mods: continue
            if r.get('endpoint')!='Kd' or r.get('qualifier')!='=' or not finite(r.get('p_value')):
                excluded.append({'record_id':r['record_id'],'reason':'not_exact_point_Kd','original_observation':r});continue
            if resource=='SH2_ProBound':
                access, seq, evidence=refs[r['target_id']]
                ref_evidence={'source':'PPIKB existing accession/gene metadata match; not original SH2 clone','accession':access,'supporting_record_ids':evidence,'sequence_view':'full_reference_not_assay_clone'}
            else:
                access=r.get('target_reference_accession'); seq=r.get('target_reference_sequence')
                ref_evidence=r.get('target_reference_provenance')
            subtype=sorted({str(m.get('type')) for m in mods})
            inp={
                'external_id':r['record_id'],'resource_id':resource,'study_id':r['study_id'],
                'target_id':r['target_id'],'target_accession':access,'target_sequence_view':seq,
                'target_sequence_status':'reference_not_verified_assay_clone','target_reference_provenance':ref_evidence,
                'target_reported_domain_boundary':r.get('target_reported_domain_boundary'),
                'peptide_sequence':r['peptide_sequence'],'peptide_sequence_raw':r['peptide_sequence_raw'],
                'peptide_chemical_id':r['peptide_chemical_id'],'peptide_smiles':None,
                'residue_modifications':mods,'residue_group':'PTM_only','nc_subtypes':subtype,
                'n_terminal':r.get('n_terminal'),'c_terminal':r.get('c_terminal'),
                'source_record_id':r['source_record_id'],'source_file':r['source_file'],'source_sha256':r['source_sha256'],
                'source_location':r['source_location'],'source_flags':{k:v for k,v in (r.get('flags')or{}).items() if not any(term in k.lower() for term in ('kd','sem','mean','value','magnitude','fit'))},
                'chemical_source_file':r.get('chemical_source_file'),'chemical_source_sha256':r.get('chemical_source_sha256'),
                'chemical_source_location':r.get('chemical_source_location'),
                'input_status':'exact_annotation_target_reference_pending_structure_format_conversion',
                'gold_usage':'posttraining_evaluation_only_retrospective_previously_inspected',
            }
            inputs.append(inp);preserved.append({'external_id':r['record_id'],'original_observation':r})
            gold.append({'external_id':r['record_id'],'endpoint':'Kd','pKd':r['p_value'],'Kd_M':r['value_molar'],'reported_value':r['value'],'reported_unit':r['unit'],'uncertainty':r.get('uncertainty'),'affinity_derived_QC_flags':{k:v for k,v in (r.get('flags')or{}).items() if any(term in k.lower() for term in ('kd','sem','mean','value','magnitude','fit'))},'label_exposure':'previously_inspected_retrospective'})
    # Original ProfAff measured FP Kd only. Calibrated holdup/predictions are excluded.
    pclass=RESCREEN/'ProfAff2022-original-workbook--row-classification.csv'
    wanted={int(r['source_excel_row']):r for r in csv.DictReader(pclass.open(encoding='utf-8-sig')) if 'PTM_' in r['nc_subtypes'] and r['FP_positive_Kd']=='True'}
    workbook=OLD/'pdz-raw/41467_2022_33018_MOESM4_ESM.xlsx';SOURCES.extend([pclass,workbook])
    domains={r['target_source_name']:r for r in json.loads((OLD/'pdzome2023-domain-construct-sequences.json').read_text(encoding='utf-8'))}
    wb=openpyxl.load_workbook(workbook,read_only=True,data_only=True);it=wb['PDZ-PBM interactome'].iter_rows(max_col=39,values_only=True);headers=next(it)
    for ix, values in enumerate(it,2):
        if ix not in wanted:continue
        r=dict(zip(headers,values));domain=domains.get(r['PDZ']);eid='ProfAff2022:original:row'+str(ix)
        inp={
            'external_id':eid,'resource_id':'ProfAff2022','study_id':aliases['ProfAff2022']['doi'],
            'target_id':r['PDZ'],'target_accession':None,
            'target_sequence_view':domain['domain_sequence'] if domain else None,
            'target_sequence_status':'source_linked_isolated_domain_not_verified_2022_full_fusion' if domain else 'missing',
            'target_reference_provenance':domain,
            'peptide_sequence':None,'peptide_sequence_raw':r['peptide'],
            'peptide_reported_10mer':r['peptide_10mer'],'peptide_natural_10mer_not_assay_ligand':r['natural_10mer'],
            'peptide_chemical_id':'reported-chemistry:'+hashlib.sha256(str(r['peptide']).encode()).hexdigest(),
            'peptide_smiles':None,'residue_group':'PTM_only','nc_subtypes':wanted[ix]['nc_subtypes'].split(';'),
            'other_chemistry':wanted[ix]['other_chemistry'].split(';'),
            'source_file':str(workbook),'source_sha256':sha(workbook),'source_location':'PDZ-PBM interactome!row'+str(ix),
            'input_status':'real_ligand_linker_and_fusion_identity_unresolved_no_simplified_SMILES',
            'gold_usage':'posttraining_evaluation_only_retrospective_previously_inspected',
        }
        # Parse only explicit core residues; biotin/linkers remain part of the entity.
        chem=r['peptide'];tail=re.sub(r'^biotin-', '',chem,flags=re.I)
        for prefix in ['ttds-','ado-ado-','(PEG)3-','Ahx-','GSGSGS-']:
            if tail.lower().startswith(prefix.lower()): tail=tail[len(prefix):];break
        tail=re.sub(r'-CONH2$', '',tail)
        core=re.sub(r'p([STY])',r'\1',tail).replace('Kac','K')
        if core and set(core)<=AA:inp['peptide_sequence']=core
        inputs.append(inp);preserved.append({'external_id':eid,'original_workbook_row':{str(k):v for k,v in r.items()}})
        val=float(r['FP_aver_uM']);gold.append({'external_id':eid,'endpoint':'Kd','pKd':-math.log10(val*1e-6),'Kd_M':val*1e-6,'reported_value':val,'reported_unit':'uM','uncertainty':{'value':r['FP_stdev_uM'],'unit':'uM','type':'author_FP_stdev'},'label_exposure':'previously_inspected_retrospective'})
    wb.close()
    assert Counter(r['resource_id'] for r in inputs)=={'SH2_ProBound':45,'Kliche2023_phosphomimetic':30,'ProfAff2022':52}
    assert len(gold)==len(inputs)==len({r['external_id'] for r in inputs})==127
    # Source-level audit: DOI, PMID and normalized full title across every PPIKB row.
    sourcehits=[]
    for r in pp:
        raw=r.get('row_raw')or{}
        for resource,a in aliases.items():
            reasons=[]
            if doi(a['doi']) in {doi(r.get('study_id')),doi(raw.get('DOI'))}:reasons.append('DOI')
            if a.get('pmid') and str(raw.get('PMID','')).strip()==str(a['pmid']):reasons.append('PMID')
            if a.get('title') and normtitle(a['title'])==normtitle(raw.get('Title')):reasons.append('title')
            if reasons:sourcehits.append({'record_id':r['record_id'],'external_resource':resource,'reasons':reasons,'study_id':r['study_id']})
    # Exact reference/isolated-domain containment is a positive related-target test,
    # not a homology-negative certificate. Proteins absent from this list remain
    # pending the main protocol's alignment-based homolog grouping.
    targetlinks=[];possiblepairs=[]
    for e in inputs:
        seq=e.get('target_sequence_view')or'';access=e.get('target_accession');pep=e.get('peptide_sequence')
        for r in pp:
            t=r.get('target_sequence')or'';rel=[]
            if access and access==r.get('target_id'):rel.append('same_accession')
            if seq and t and (seq in t or t in seq):rel.append('reference_or_domain_exact_containment')
            if not rel:continue
            targetlinks.append({'external_id':e['external_id'],'ppikb_record_id':r['record_id'],'ppikb_study_id':r['study_id'],'reasons':rel})
            # Uppercase only without deleting arbitrary tokens. This is expressly
            # a conservative backbone warning, not proof of chemical identity.
            rawpep=r.get('peptide_sequence_raw')or''
            backbone=r.get('peptide_sequence')
            if not backbone and rawpep and set(rawpep.upper())<=AA:backbone=rawpep.upper()
            if pep and backbone==pep:
                possiblepairs.append({'external_id':e['external_id'],'ppikb_record_id':r['record_id'],'study_id':r['study_id'],'status':'same_backbone_related_target_chemical_identity_not_certified','reasons':rel})
    sourceblack={r['record_id'] for r in sourcehits}
    pairstudies={r['study_id'] for r in possiblepairs}
    conservative={r['record_id'] for r in pp if r['study_id'] in pairstudies}|sourceblack
    blacklist={'policy':'Apply before splitting both NC and standard pools; do not force all 2099 into training. Conservatively withhold entire original study for any related-target same-backbone ambiguity.',
        'external_original_study_aliases':aliases,'source_match_rows':sourcehits,
        'source_blacklist_record_ids':sorted(sourceblack),
        'conservative_related_entity_blacklist_record_ids':sorted(conservative),
        'conservative_related_entity_blacklist_study_ids':sorted(pairstudies),
        'homology_status':'exact-positive related-target links only; comprehensive homolog audit is a separate required gate',
        'external_target_related_record_ids_for_optional_target_cold_protocol':sorted({r['ppikb_record_id'] for r in targetlinks}),
        'label_values_used_for_overlap_or_blacklist':False}
    dump(HERE/'training-blacklist.json',blacklist)
    jsonl(HERE/'inputs/blind-inputs.jsonl',inputs)
    jsonl(HERE/'gold/posttraining-gold.jsonl',gold)
    jsonl(HERE/'provenance/full-preserved-external-records.jsonl',preserved)
    jsonl(HERE/'provenance/excluded-nonpoint-records.jsonl',excluded)
    jsonl(HERE/'audit/related-target-positive-links.jsonl',targetlinks)
    jsonl(HERE/'audit/same-backbone-related-target-warnings.jsonl',possiblepairs)
    targets={hashlib.sha256(r['target_sequence_view'].encode()).hexdigest()[:20]:r['target_sequence_view'] for r in inputs if r.get('target_sequence_view')}
    with (HERE/'inputs/external-targets.fasta').open('w',encoding='utf-8') as f:
        for key,seq in sorted(targets.items()):f.write('>'+key+'\n'+seq+'\n')
    summary={'status':'retrospective_external_candidates_prepared_with_explicit_chemistry_and_construct_gates',
        'rows':len(inputs),'resource_counts':dict(Counter(r['resource_id'] for r in inputs)),
        'residue_group_counts':dict(Counter(r['residue_group'] for r in inputs)),
        'nonproteinogenic_D_backbone_external_rows':0,
        'target_reference_or_domain_view_present':sum(bool(r.get('target_sequence_view')) for r in inputs),
        'original_assay_clone_sequence_verified':0,'original_SMILES_available':0,
        'source_overlap_rows':len(sourcehits),'same_backbone_related_target_warnings':len(possiblepairs),
        'conservative_blacklist_records':len(conservative),'conservative_blacklist_studies':len(pairstudies),
        'strict_homology_cold_certified_rows':0,
        'sources':[{'path':str(p),'sha256':sha(p)} for p in SOURCES],
        'raw_inputs_mutated':False,'training_executed':False,
        'gold_isolation':'Programmatic/separate directory only on one shared account; previously inspected labels are not a new prospective blind set.',
        'source_cold_claim':'May be evaluated only after whole-source blacklist AND entity/homology protocol checks; distinct source does not guarantee independent entity.'}
    dump(HERE/'external-preparation-summary.json',summary)
    assert not any(k in r for r in inputs for k in ('p_value','pKd','Kd_M','value','value_molar','reported_value','uncertainty'))
    dump(HERE/'verification.json',{'input_has_no_affinity_gold_columns':True,'rows_conserved':True,'point_only':True,'source_readonly':True,'PepLand_IBM_excluded':True,'PTM_and_other_nc_separate':True,'summary_sha256':sha(HERE/'external-preparation-summary.json')})
    print(json.dumps({k:v for k,v in summary.items() if k not in ('sources',)},ensure_ascii=False))

if __name__=='__main__':main()
