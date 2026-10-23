"""JSON-only diagnostics. No tensor/framework imports, RNG or model mutation."""
import json,os,time
from pathlib import Path

class TraceJournal:
    def __init__(self,directory):
        self.directory=Path(directory);self.handle=(self.directory/'partial-tensor-hook-trace.jsonl').open('x',encoding='utf-8')
        self.branch=None;self.phase=None;self.names=[];self.ordinal=0;self.events=[];self.count=0;self.closed=False
    def emit(self,kind,payload):
        if self.closed:return
        item={'trace_event':self.count,'time_ns':time.time_ns(),'branch':self.branch,'table_phase':self.phase,'kind':kind,'payload':payload}
        if kind=='tensor_digest':
            item['tensor_name']=self.names[self.ordinal] if self.ordinal<len(self.names) else None
            item['tensor_ordinal_in_table']=self.ordinal;self.ordinal+=1
        self.handle.write(json.dumps(item,allow_nan=False,ensure_ascii=False)+'\n');self.count+=1
        if self.count%32==0:self.handle.flush()
    def start_branch(self,name):
        self.branch=name;self.phase=None;self.names=[];self.ordinal=0;self.events=[];self.emit('branch_start',{})
    def begin_table(self,kind,names):
        self.phase=kind;self.names=names;self.ordinal=0;self.emit('table_start',{'expected_names':names})
    def end_table(self):
        self.emit('table_end_or_exception',{'completed_tensor_count':self.ordinal});self.phase=None;self.names=[];self.ordinal=0
    def finish(self,record):
        if self.closed:return
        self.emit('python_finally',{'last_branch_record_matches_active':bool(record and record.get('branch')==self.branch)})
        self.handle.flush();os.fsync(self.handle.fileno());self.handle.close();self.closed=True
        payload={'active_branch':self.branch,'partial_record':record if record and record.get('branch')==self.branch else None,'completed_hook_events':self.events,'journal_events':self.count,'scope':'Completed digest entries and hook metadata retained on normal Python return/exception; uncomputed tensors unavailable. SIGKILL/hostfailure/diskfailure may bypass finally; not guaranteed full partial state.'}
        target=self.directory/'finally-partial-diagnostics.json'
        with target.open('x',encoding='utf-8') as f:json.dump(payload,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())

def finish_without_masking_original(journal,record):
    if journal is None:return
    try:journal.finish(record)
    except Exception as exc:
        # Diagnostics must not turn a scientific mismatch into successful execution.
        try:(journal.directory/'logging-failure.txt').write_text(type(exc).__name__+': '+str(exc),encoding='utf-8')
        except Exception:pass
