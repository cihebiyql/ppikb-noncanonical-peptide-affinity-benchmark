"""Read owned receipts, preserve originals, and emit only sanitized summaries."""
from pathlib import Path
import json,hashlib,datetime,re
P=Path(__file__).resolve().parent;ROOT=P.parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
initial=read(P/'initial-evidence-summary.json');index=read(ROOT/'control/unit-index-v4-nc-all-seeds.json')
unit=next(u for u in index['units'] if 'MGraphDTA' in u['unit_id'] and 'target_reference' in u['unit_id'] and 'seed08' in u['unit_id'])
pool=Path(initial['pool_root']);metadata=[]
for suffix in ['stdout.log','stderr.log']:
 source=pool/(unit['unit_id']+'.'+suffix)
 if source.exists():
  dest=P/('original-failed-unit.'+suffix);dest.write_bytes(source.read_bytes());text=dest.read_text(encoding='utf-8',errors='replace')
  metadata.append({'source':str(source),'snapshot':str(dest),'sha256':sha(dest),'bytes':dest.stat().st_size,'CUDA_OOM_text_present':bool(re.search(r'CUDA.{0,30}out of memory|CUDAOutOfMemoryError',text,re.I)),'MemoryError_text_present':'MemoryError' in text})
source_index=[]
for name in ['launch/common.py','launch/pool_supervisor.py']:
 for i,line in enumerate((ROOT/name).read_text(encoding='utf-8').splitlines(),1):
  if any(k in line for k in ['def write(','.write_text(','.replace(',"write(root/'progress.json'",'watchdog_failed','except BaseException as error','stop_owned_group(state','os.killpg','SIGTERM','SIGKILL']):source_index.append({'file':name,'line':i,'source':line})
(P/'source-causal-chain.json').write_text(json.dumps(source_index,ensure_ascii=False,indent=2),encoding='utf-8')
terminal=read(P/(unit['unit_id']+'.terminal.json'));started=read(P/(unit['unit_id']+'.started.json'))
cases=[read(p) for p in sorted(P.glob('*.receipt.json')) if p.name not in ['original-progress.snapshot.json']]
summary={'diagnosis_started_utc':initial['diagnosis_started_utc'],'diagnosis_finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'read-only original receipts plus owned synthetic JSON/short reader-writer processes; no training','original_failure':{'progress_class':initial['reason_class'],'progress_errno':initial['reason_errno'],'original_repr_includes_filename':initial['reason_has_path'],'worker_exit':terminal['exit_code'],'worker_started_at':started.get('started_at'),'worker_terminal_at':terminal.get('finished_at'),'global_deadline':initial['source_clock_deadline'],'original_unit_deadline_epoch':started.get('unit_effective_deadline_epoch'),'complete_units':initial['complete_count'],'failed_units':initial['failed_count']},'synthetic_cases':cases,'failure_log_scan':metadata,'inference':{'Windows_reader_without_delete_share_can_block_DrvFs_atomic_replace':'high_confidence_reproduced','ordinary_Windows_Python_Path_open_default_sharing_can_reproduce':'high_confidence_reproduced','this_specific_original_fault_was_a_telemetry_file_IO_failure':'moderate_to_high_source_path_inference_no_original_traceback','the_original_exact_lock_owner_or_filename':'unknown; original exception repr omits them','Get_Content_as_unique_cause':'not_established; actual current PowerShell7.6.5 Get-Content -Wait was a successful negative-control','model_OOM_as_recorded_stop_reason':False},'frozen_scripts_unchanged':{name:sha(ROOT/'launch'/name)==expected for name,expected in initial['frozen_script_sha256'].items()},'original_progress_unchanged_by_diagnosis':sha(Path(initial['progress_source']))==initial['progress_sha256'],'original_checkpoints_opened_or_modified':False,'original_training_restarted':False,'deadline_extended':False,'new_models_started':0}
(P/'diagnosis-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'original_class':initial['reason_class'],'original_errno':initial['reason_errno'],'worker_exit':terminal['exit_code'],'synthetic_case_count':len(cases),'frozen_scripts_unchanged':summary['frozen_scripts_unchanged'],'original_progress_unchanged':summary['original_progress_unchanged_by_diagnosis'],'new_models_started':0,'finished_utc':summary['diagnosis_finished_utc']},ensure_ascii=False,indent=2))
