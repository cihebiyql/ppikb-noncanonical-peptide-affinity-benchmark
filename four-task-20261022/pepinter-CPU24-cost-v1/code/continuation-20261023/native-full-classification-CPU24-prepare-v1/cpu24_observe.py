"""CPU cost metadata only, no model or GPU imports."""
import contextlib,json,os,resource,time
from pathlib import Path
PHASE_PATH=None
def rss():
    data=Path('/proc/self/status').read_text()
    return int(next(x for x in data.splitlines() if x.startswith('VmRSS:')).split()[1])*1024
@contextlib.contextmanager
def phase(name):
    before=time.monotonic();cpu=time.process_time();record={'phase':name,'started_monotonic':before,'RSS_before_bytes':rss(),'status':'started'}
    if PHASE_PATH:
        with Path(PHASE_PATH).open('a',encoding='utf-8') as f:f.write(json.dumps(record)+'\n');f.flush()
    try:yield
    except Exception as exc:record.update(status='failed',error_type=type(exc).__name__,error=str(exc));raise
    else:record['status']='completed'
    finally:
        record.update(elapsed_seconds=time.monotonic()-before,process_CPU_seconds=time.process_time()-cpu,RSS_after_bytes=rss(),process_peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
        if PHASE_PATH:
            with Path(PHASE_PATH).open('a',encoding='utf-8') as f:f.write(json.dumps(record)+'\n');f.flush();os.fsync(f.fileno())

def admission_requirement(available,protected_tree_RSS,protected_alive=True):
    unused=max(0,20*2**30-protected_tree_RSS) if protected_alive else 0
    required=32*2**30+36*2**30+unused
    return {'available_bytes':available,'protected_tree_RSS_bytes':protected_tree_RSS,'protected_alive':protected_alive,'protected_unspent_reserved_bytes':unused,'required_available_bytes':required,'passed':available>=required}
