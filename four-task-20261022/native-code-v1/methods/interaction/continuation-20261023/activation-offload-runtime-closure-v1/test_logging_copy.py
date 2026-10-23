"""Synthetic CPU-only math/RNG and failure-journal evidence; no biological NN."""
import os,sys,tempfile,json,unittest
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']=''
for key in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[key]='1'
H=Path(__file__).resolve().parents[2];sys.path.insert(0,str(H))
import torch
torch.set_num_threads(1);torch.set_num_interop_threads(1)
import pepinter_activation_offload_strict_gate as original
import pepinter_activation_offload_strict_gate_logging_v2 as revised
from trace_logging import TraceJournal,finish_without_masking_original
from common import save,now,sha

def tiny_run(module,journal=None):
    if module is revised:revised._trace_v2_journal=journal
    torch.manual_seed(82)
    model=torch.nn.Sequential(torch.nn.Linear(4,5),torch.nn.Dropout(.2),torch.nn.Linear(5,1)).train()
    optimizer=torch.optim.AdamW(model.parameters(),lr=1e-4,weight_decay=.01)
    x=torch.randn(3,4);loss=model(x).square().mean();loss.backward()
    result={'loss':module.tensor_record(loss),'preclip':module.table(model,'gradients')}
    norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.,error_if_nonfinite=True)
    result['norm']=module.tensor_record(norm);result['postclip']=module.table(model,'gradients')
    optimizer.step()
    result['parameters']=module.table(model,'parameters')
    # Native table(optimizer) intentionally enforces1107states, so tiny optimizer is read by the same tensor digest function directly.
    result['optimizer']={name+'.'+key:module.tensor_record(value) for name,p in model.named_parameters() for key,value in optimizer.state[p].items()}
    result['rng']=module.rng_record()
    return result

class LoggingTests(unittest.TestCase):
    def test_exact_cpu_math_and_rng(self):
        baseline=tiny_run(original)
        self.assertEqual(baseline,tiny_run(revised))
        with tempfile.TemporaryDirectory() as tmp:
            journal=TraceJournal(tmp);journal.start_branch('synthetic')
            try:self.assertEqual(baseline,tiny_run(revised,journal))
            finally:finish_without_masking_original(journal,{'branch':'synthetic'});revised._trace_v2_journal=None
            rows=[json.loads(x) for x in (Path(tmp)/'partial-tensor-hook-trace.jsonl').read_text().splitlines()]
            self.assertTrue(any(x.get('tensor_name')=='0.weight' for x in rows))
            self.assertTrue((Path(tmp)/'finally-partial-diagnostics.json').is_file())
    def test_mid_table_failure_keeps_completed_digest_and_original_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal=TraceJournal(tmp);journal.start_branch('reference');revised._trace_v2_journal=journal
            model=torch.nn.Linear(2,2);function=revised._trace_v2_original_tensor_record;counter=[0]
            def failure(t):
                counter[0]+=1
                if counter[0]==2:raise RuntimeError('synthetic mid-table failure')
                return function(t)
            revised._trace_v2_original_tensor_record=failure
            try:
                with self.assertRaisesRegex(RuntimeError,'synthetic mid-table failure'):revised.table(model,'parameters')
            finally:
                finish_without_masking_original(journal,{'branch':'reference','already_completed':'retained'})
                revised._trace_v2_original_tensor_record=function;revised._trace_v2_journal=None
            rows=[json.loads(x) for x in (Path(tmp)/'partial-tensor-hook-trace.jsonl').read_text().splitlines()]
            digests=[x for x in rows if x['kind']=='tensor_digest']
            self.assertEqual(len(digests),1);self.assertEqual(digests[0]['tensor_name'],'weight')
            self.assertEqual(json.loads((Path(tmp)/'finally-partial-diagnostics.json').read_text())['partial_record']['already_completed'],'retained')
    def test_pack_attempt_failure_metadata_survives_finally(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal=TraceJournal(tmp);journal.start_branch('save-on-cpu')
            try:
                journal.emit('pack_attempt',{'shape':[3,4],'stride':[4,1],'dtype':'torch.float32','device':'cpu','bytes':48})
                raise ValueError('synthetic pack layout failure')
            except ValueError:pass
            finally:finish_without_masking_original(journal,None)
            rows=[json.loads(x) for x in (Path(tmp)/'partial-tensor-hook-trace.jsonl').read_text().splitlines()]
            self.assertTrue(any(x['kind']=='pack_attempt' for x in rows))
            self.assertIsNone(json.loads((Path(tmp)/'finally-partial-diagnostics.json').read_text())['partial_record'])

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(LoggingTests))
    save(Path(__file__).with_name('logging-copy-CPU-fixture.actual.json'),{'at':now(),'status':'passed' if result.wasSuccessful() else 'failed','tests_run':result.testsRun,'errors':len(result.errors),'failures':len(result.failures),'CVD':os.environ['CUDA_VISIBLE_DEVICES'],'cuda_initialized':torch.cuda.is_initialized(),'biological_NN_forwards':0,'GPU_calls':0,'synthetic_tiny_CPU_NN_only':True,'original_source_sha256':sha(H/'pepinter_activation_offload_strict_gate.py'),'logging_copy_sha256':sha(H/'pepinter_activation_offload_strict_gate_logging_v2.py'),'logging_helper_sha256':sha(Path(__file__).with_name('trace_logging.py')),'test_source_sha256':sha(__file__)})
    raise SystemExit(0 if result.wasSuccessful() else 1)
