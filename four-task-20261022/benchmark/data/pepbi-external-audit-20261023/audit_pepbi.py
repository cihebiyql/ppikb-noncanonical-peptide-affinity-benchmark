"""Read-only raw-source and PEPBI grain/provenance audit; no ML execution."""
from pathlib import Path
import csv,json,math,hashlib,re,collections,xml.etree.ElementTree as ET,zipfile,io,datetime as dt
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
OLD=R.parent/'peptide-binding-benchmark-20261020';E=OLD/'ten-seed-external-20261021/external/pepbi_pdz'
AA=set('ACDEFGHIKLMNPQRSTVWY');pins=[]
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def pin(p,role):pins.append({'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size,'role':role});return p
def save(name,x):(O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
def writecsv(name,rows):
 if not rows:return
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:
  keys=list(dict.fromkeys(k for r in rows for k in r));w=csv.DictWriter(f,keys);w.writeheader();w.writerows([{k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rows])
def rd(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def doival(s):
 s=str(s or '').lower().strip();s=re.sub(r'^https?://(?:dx\.)?doi.org/','',s);return s.rstrip(' .;,')
def pdbvals(s):return sorted({z.lower() for z in re.findall(r'\b[0-9][A-Za-z0-9]{3}\b',str(s or '')) if not z.isdigit()})
def canon(s):s=str(s or '').strip();return s if s and set(s)<=AA else ''
def hid(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,separators=(',',':')).encode('utf8')).hexdigest()[:24]
# Exact primary descriptor citation table and all workbook cells retained.
p=pin(E/'pepbi.xml','existing legally acquired primary PEPBI JATS;Table1 ITC source mapping');b=p.read_bytes();(O/'raw/pepbi-primary.xml').write_bytes(b);j=ET.fromstring(b);assert '10.1038/s41597-025-05754-7' in [x.text for x in j.findall('.//article-id')]
refs={}
for ref in j.findall('.//ref'):
 text=' '.join(ref.itertext());doi=next((x.text for x in ref.findall('.//pub-id') if x.get('pub-id-type')=='doi'),None)
 if not doi:
  found=re.search(r'\b10\.\d{4,9}/[^\s<>]+',text);doi=found.group().rstrip('.,;)') if found else None
 refs[ref.get('id')]={'reference_id':ref.get('id'),'doi':doival(doi),'citation_text':text.strip()}
table=next(t for t in j.findall('.//table-wrap') if t.findtext('label')=='Table 1');(O/'raw/table1-primary.xml').write_text(ET.tostring(table,encoding='unicode'),encoding='utf8');carry={};groupmap={}
for tr in table.findall('.//tbody/tr'):
 cells=[None]*6
 for i,(v,n) in list(carry.items()):
  cells[i]=v
  if n<=1:del carry[i]
  else:carry[i]=(v,n-1)
 i=0
 for cell in tr:
  while i<6 and cells[i] is not None:i+=1
  v={'text':''.join(cell.itertext()).strip(),'refs':[x.get('rid') for x in cell.findall('.//xref')]};cells[i]=v;n=int(cell.get('rowspan','1'))
  if n>1:carry[i]=(v,n-1)
  i+=1
 name=cells[0]['text'];m=groupmap.setdefault(name,{'binding_group':name,'PDBs':[],'ITC_reference_ids':cells[3]['refs'],'ITC_sources':[refs[q] for q in cells[3]['refs']],'descriptor_ITC_complexes':int(cells[4]['text']),'descriptor_model_entries':int(cells[5]['text'])});m['PDBs']+=pdbvals(cells[1]['text'][:4])
assert len(groupmap)==32;save('binding-group-source-map.json',list(groupmap.values()))
import openpyxl
p=pin(O/'raw/PEPBI.xlsx','officialDryadSHA verified workbook');w=openpyxl.load_workbook(p,read_only=True,data_only=True);raw=list(w.worksheets[0].values);header=list(raw[1]);work=[dict(zip(header,row)) for row in raw[2:] if row[0]];w.close();assert len(work)==329
rows=[]
for i,x in enumerate(work,3):
 g=groupmap[x['Binding Group']];doi=';'.join(sorted({z['doi'] for z in g['ITC_sources'] if z['doi']}));pep=x['Peptide Sequence'];pro=x['Protein Sequence'];kd=x['KD (M)'];T=x['T (K)'];tag=str(x['Protein Tag']);expectedDG=.00198720425864083*T*math.log(kd);cDG=x['Calculated ΔG (kcal/mol)'];badDG=not isinstance(cDG,(int,float)) or abs(cDG-expectedDG)>.05
 scope='excluded_named_toxin_ligand' if x['Binding Group']=='TolB - ColE9' else 'quarantined_pathogen_secretion_context_owner_review' if x['Binding Group']=='ClpV-N - P-VipB' else 'not_explicitly_restricted_by_current_scope'
 tagstatus='not_declared_X_not_proof_absence' if tag=='X' else 'explicit_His_sequence_present' if 'his' in tag.lower() and 'HHHHH' in pro else 'explicit_GST_prefix_present' if 'gst' in tag.lower() and pro.startswith('MSPILGYWKIKGLVQ') else 'declared_tag_not_verified_in_sequence'
 ctx=[doi,pro,pep,x['Binding Site'],T,kd];row={'row_id':f'PEPBI:excel-row-{i:03d}','excel_row':i,**x,'source_ITC_DOI':doi,'source_ITC_reference_ids':g['ITC_reference_ids'],'source_context_evidence':'PEPBIprimaryTable1_and_workbook;individual_original_paper_cells_not_all_reverified','full_original_assay_buffer_verified':False,'source_workbook_sha256':sha(p),'sequence_pair_id':'pepbi-pair-'+hid([pro,pep]),'measurement_context_id':'pepbi-ctx-'+hid(ctx),'protein_sequence_sha256':hashlib.sha256(pro.encode()).hexdigest(),'peptide_sequence_sha256':hashlib.sha256(pep.encode()).hexdigest(),'protein_length_actual':len(pro),'peptide_length_actual':len(pep),'protein_length_conflict':len(pro)!=int(x['Protein Length']),'peptide_length_conflict':len(pep)!=int(x['Peptide Length']),'protein_AA20':bool(canon(pro)),'peptide_AA20':bool(canon(pep)),'Kd_unit_from_header':'M','pKd_from_recorded_Kd':-math.log10(kd),'thermodynamic_calculatedDG_expected_RTlnKd':expectedDG,'thermodynamic_calculatedDG_residual_kcal':cDG-expectedDG if isinstance(cDG,(int,float)) else None,'questionable_value_flag':bool(kd>=.1),'thermodynamic_identity_conflict':badDG,'tag_sequence_status':tagstatus,'assay_chemical_identity_status':'descriptor canonicalAA/noPTM selection;complete termini/chemistry not independently audited','noncanonical_core_certified':False,'PTM_certified':False,'scope_status':scope,'target_species_status':'Thermus thermophilus-derived_construct' if x['Protein Name'].startswith('TtSlyD') else 'not_independently_taxonomy_verified;not_excluded_for_nonhuman','original_source_row_cell_verified':False}
 rows.append(row)
writecsv('all329-row-audit.csv',rows);save('all329-row-audit.json',rows)
# Build compact exposure indexes without assigning new biological labels.
indexes={};coverage=[];restricted=[]
def newindex(name):
 z={k:collections.defaultdict(list) for k in ['pair','target','doi','pdb']};z['occurrences']=0;z['unique_records']=0;indexes[name]=z;return z
def add(z,rid,pep,pro,doi='',pdb='',meta=None):
 z['occurrences']+=1
 if pep and pro:z['pair'][(pep,pro)].append(rid)
 if pro:z['target'][pro].append(rid)
 if doi:z['doi'][doival(doi)].append(rid)
 for q in pdbvals(pdb):z['pdb'][q].append(rid)
pp=pin(R.parent/'peptide-binding-expanded-corpus-20261021/resources/PPIKB_all_endpoints/normalized-observations.jsonl','all original PPIKB endpoints normalized rows;raw workbook lineage retained');z=newindex('PPIKB_all_original_endpoints');count=0;nc=0
vs=re.compile('virus|viral|SARS|HIV',re.I);tx=re.compile(r'bungarotoxin|^enterotoxin\b|^botulinum neurotoxin\b|^ricin\b',re.I)
with pp.open(encoding='utf8') as f:
 for l in f:
  x=json.loads(l);count+=1;rid=x['record_id'];species=str(x.get('target_species') or '');name=str(x.get('target_name') or '')
  if vs.search(species) or tx.search(name):restricted.append({'source':'PPIKB','row_id':rid,'reason':'existing_explicit_viral_species_or_named_target_toxin','target_name':name,'target_species':species});continue
  pep=canon(x.get('peptide_sequence')) or canon(x.get('peptide_sequence_raw'));pro=canon(x.get('target_sequence'));nc+=not bool(pep);add(z,rid,pep,pro,x.get('study_id'),x.get('PDB'))
coverage.append({'source':'PPIKB_all_original_endpoints','raw_rows':count,'scope_registered_excluded':len(restricted),'comparison_rows':z['occurrences'],'rows_without_unambiguous_AA20_peptide':nc,'DOI_available':bool(z['doi']),'PDB_available':bool(z['pdb']),'construct_scope':'often UniProt/reference versus assay constructs;exact matching lower bound'})
# All 24 original supervised author CSV members, all folds; dedup only identical published row content excluding fold split.
p=pin(OLD/'assets/PepInter-paper-21717699/PepInter-PepInter.zip','original author archive all supervised affinity/classification CSVs');archive_members=[]
with zipfile.ZipFile(p) as archive:
 for typ,name in [('pepinter_aff','PepAffDB_all_author_records'),('pepinter_cls','PepInter_all_author_records')]:
  z=newindex(name);seen={};occur=0
  for member in sorted(n for n in archive.namelist() if '/dataset/'+typ+'/' in n and n.endswith('.csv')):
   b=archive.read(member);a=list(csv.DictReader(io.StringIO(b.decode('utf-8-sig'))));archive_members.append({'member':member,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'rows':len(a)})
   for k,x in enumerate(a,2):
    occur+=1;content={kk:vv for kk,vv in x.items() if kk!='split'};key=hid(content)
    if key in seen:continue
    rid=name+':'+key;seen[key]=rid;add(z,rid,canon(x.get('mobile_seq')),canon(x.get('target_seq')))
  coverage.append({'source':name,'raw_occurrences_all_fold_csvs':occur,'unique_published_row_content_excluding_split':len(seen),'raw_member_count':sum('/'+typ+'/' in x['member'] for x in archive_members),'DOI_field_available':False,'PDB_ID_field_available':False,'affinity_endpoint_per_record_resolved':False,'pretraining9M_source_index_not_available':True})
save('author-archive-member-pins.json',archive_members)
# Current actual model views are separate from all-source catalog exposure.
for name,rel in [('PPIKB_current_source_panel','data/ppikb_kd_source_cold_scope_v2.csv'),('PPIKB_current_target_panel','data/ppikb_kd_target_cold_scope_v2.csv'),('PepAffDB_current_view','data/pepaff_mixed_target_cold.csv'),('PepInter_current_view','data/pepinter_classification_target_cold.csv')]:
 p=pin(R/rel,'current frozen model-view exposure');a=rd(p);z=newindex(name)
 for x in a:add(z,x['row_id']+'|'+x['split'],canon(x.get('peptide_sequence')),canon(x.get('target_sequence')),x.get('study_id'))
 coverage.append({'source':name,'rows':len(a),'all_splits_included':True,'classification_source_species_metadata_unavailable':name=='PepInter_current_view'})
# All original ProfAff human-raw records; explicit backbone relation, not actual full biotin/TTDS chemistry.
p=pin(E/'pdzome2023-domain-construct-sequences.json','official-source isolated-domain sequence ancestry266;2022fullfusion not certified');domain={x['target_source_name']:x['domain_sequence'] for x in json.loads(p.read_text(encoding='utf8'))};p=pin(E/'pdz-human-raw-measurements.csv','all original ProfAff raw measurement rows including censored/missing');a=rd(p);z=newindex('ProfAff_all_raw_domain_backbone_relation');missing=0;amb=0
for x in a:
 pro=canon(domain.get(x['PDZ']));pep=canon(x['peptide_10mer']);missing+=not bool(pro);amb+=not bool(pep);add(z,'ProfAff:excel-row-'+x['source_excel_row'],pep,pro,'10.1038/s41467-022-33018-0')
coverage.append({'source':'ProfAff_all_raw_domain_backbone_relation','raw_rows':len(a),'PDZ_unique':len({x['PDZ'] for x in a}),'domain_sequence_missing_rows':missing,'unresolved_peptide10mer_rows':amb,'DOI_known_for_all':True,'structure_IDs_not_available':True,'input_role':'isolated-domain plus published peptide10mer;biotinTTDS/tag/PTM not full chemical identity;not new negative labels'})
for name,rel in [('ProfAff_current_FP162','data/profaff_pKd_domain_backbone_all162_external.csv'),('ProfAff_current_HU17136','data/profaff-expansion-20261023/holdup-all-explicit-backbone-projections-external.csv')]:
 p=pin(R/rel,'current fixed external inputs;all records');a=rd(p);z=newindex(name)
 for x in a:add(z,x['row_id'],canon(x.get('peptide_sequence')),canon(x.get('target_sequence')),x.get('study_id'))
 coverage.append({'source':name,'rows':len(a),'already_externally_used':True})
writecsv('comparison-source-coverage.csv',coverage);save('comparison-source-coverage.json',coverage);writecsv('comparison-scope-exclusions.csv',restricted)
# Primary-sequence exact and full-subsequence relation; never interpreted as homology-family proof.
comparisons=[];pair_cache={};pro_cache={}
for row in rows:
 pep=row['Peptide Sequence'];pro=row['Protein Sequence'];doi=row['source_ITC_DOI'];pdb=row['PDB ID']
 for name,z in indexes.items():
  pk=(name,pep,pro)
  if pk not in pair_cache:pair_cache[pk]=z['pair'].get((pep,pro),[])
  tk=(name,pro)
  if tk not in pro_cache:
   pro_cache[tk]=[{'target_sequence_sha256':hashlib.sha256(s.encode()).hexdigest(),'source_target_length':len(s),'relation':'exact' if s==pro else 'PEPBI_construct_contains_source_sequence' if s in pro else 'source_sequence_contains_PEPBI_construct','source_record_ids':ids} for s,ids in z['target'].items() if s==pro or s in pro or pro in s]
  direct=pair_cache[pk];dh=z['doi'].get(doi,[]);ph=[rid for q in pdbvals(pdb) for rid in z['pdb'].get(q,[])];com={'row_id':row['row_id'],'sequence_pair_id':row['sequence_pair_id'],'measurement_context_id':row['measurement_context_id'],'binding_group':row['Binding Group'],'source':name,'exact_pair_overlap_n':len(direct),'exact_pair_source_record_ids':direct,'target_exact_or_full_subsequence_overlap_n':sum(len(x['source_record_ids']) for x in pro_cache[tk]),'target_overlap_details':pro_cache[tk],'same_ITC_source_DOI_overlap_n':len(dh),'same_DOI_record_ids':dh,'PDB_overlap_n':len(ph),'PDB_source_record_ids':ph,'DOI_absence_interpretable':bool(z['doi']),'PDB_absence_interpretable':bool(z['pdb']),'homology_pretraining_independence_certified':False};comparisons.append(com)
writecsv('all329-cross-source-overlap.csv',comparisons);save('all329-cross-source-overlap.json',comparisons)
# Collapse only proven repeated descriptor contexts. Keep every raw row as lineage, never average labels.
ctx=collections.defaultdict(list);pairs=collections.defaultdict(list)
for x in rows:ctx[x['measurement_context_id']].append(x);pairs[x['sequence_pair_id']].append(x)
contexts=[]
for key,a in ctx.items():
 x=a[0];contexts.append({'context_id':key,'sequence_pair_id':x['sequence_pair_id'],'binding_group':x['Binding Group'],'source_ITC_DOI':x['source_ITC_DOI'],'source_rows':[r['row_id'] for r in a],'source_excel_rows':[r['excel_row'] for r in a],'copy_model_rows':len(a),'complex_names':sorted({r['PEPBI Complex Name'] for r in a}),'crystallographic_units':sorted({r['Crystallographic Unit'] for r in a}),'unit_copies':sorted({r['Unit Copy'] for r in a}),'temperature_K':x['T (K)'],'Kd_M':x['KD (M)'],'pKd':x['pKd_from_recorded_Kd'],'binding_site':x['Binding Site'],'protein_sequence':x['Protein Sequence'],'peptide_sequence':x['Peptide Sequence'],'reported_protein_tags':sorted({r['Protein Tag'] for r in a}),'same_sequence_pair_context_count':len({r['measurement_context_id'] for r in pairs[x['sequence_pair_id']]}),'same_sequence_pair_unique_Kd':len({r['KD (M)'] for r in pairs[x['sequence_pair_id']]}),'same_sequence_pair_unique_T':len({r['T (K)'] for r in pairs[x['sequence_pair_id']]}),'any_length_conflict':any(r['protein_length_conflict'] or r['peptide_length_conflict'] for r in a),'thermodynamic_identity_conflict':any(r['thermodynamic_identity_conflict'] for r in a),'scope_status':x['scope_status'],'tag_sequence_status':x['tag_sequence_status'],'source_context_status':'descriptor_Table1_linked;original_assay_buffer_and_original_cells_not_all_reverified','input_role':'full as-reported ITC construct sequence,including tags;not UniProt full reference;no chemical reconstruction'})
assert len(contexts)==188 and len(pairs)==147
writecsv('all188-measurement-contexts.csv',contexts);save('all188-measurement-contexts.json',contexts)
# Full source metadata/schema absence is not a zero-overlap certificate.
summary={'created_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'raw329':len(rows),'named_complexes':len({r['PEPBI Complex Name'] for r in rows}),'sequence_pairs':len(pairs),'measurement_contexts':len(contexts),'structural_copy_rows_collapsed':len(rows)-len(contexts),'binding_groups':len(groupmap),'ITC_primary_DOIs':len({x['source_ITC_DOI'] for x in rows}),'source_map_missing_DOI_rows':sum(not x['source_ITC_DOI'] for x in rows),'length_conflict_rows':[x['row_id'] for x in rows if x['protein_length_conflict'] or x['peptide_length_conflict']],'thermo_conflict_rows':[x['row_id'] for x in rows if x['thermodynamic_identity_conflict']],'multi_context_sequence_pairs':sum(len({x['measurement_context_id'] for x in a})>1 for a in pairs.values()),'different_Kd_same_input_pairs':sum(len({x['KD (M)'] for x in a})>1 for a in pairs.values()),'scope_counts_raw':dict(collections.Counter(x['scope_status'] for x in rows)),'cross_source_counts':{name:{'raw_rows_with_exactpair':sum(x['exact_pair_overlap_n']>0 for x in comparisons if x['source']==name),'raw_rows_with_target_contains':sum(x['target_exact_or_full_subsequence_overlap_n']>0 for x in comparisons if x['source']==name),'raw_rows_with_sourceDOI':sum(x['same_ITC_source_DOI_overlap_n']>0 for x in comparisons if x['source']==name),'raw_rows_with_PDB':sum(x['PDB_overlap_n']>0 for x in comparisons if x['source']==name)} for name in indexes},'fit_or_forward':False,'original_views_changed':False}
save('audit-summary.initial.json',summary);save('source-pins.json',pins);print(json.dumps(summary,ensure_ascii=False))
