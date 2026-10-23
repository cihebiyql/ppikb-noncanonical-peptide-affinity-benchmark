"""Administrative actual-PID validation, independent of calling model script."""
import hashlib,json,os,sys,time
from pathlib import Path

def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def current_validation(args):
    if str(args.validation)!="owner-current-dispatch":
        validation=json.loads(args.validation.read_text())
        if validation.get("valid_for_execution") is not True:
            raise ValueError("Actual current passed contract required")
        return {"validation_path":str(args.validation),"validation_sha256":sha(args.validation)}
    root=args.method_root.parents[1]
    cutoff=time.monotonic()+5
    while time.monotonic()<cutoff:
        for path in (root/"resources/leases").glob("*.json"):
            lease=json.loads(path.read_text())
            if lease.get("pid")!=os.getpid() or lease.get("pgid")!=os.getpgrp():
                continue
            jobpath=Path(lease["job_path"])
            assert sha(jobpath)==lease["job_sha256"]
            job=json.loads(jobpath.read_text())
            contract_path=Path(job["contract_path"])
            assert sha(contract_path)==job["contract_sha256"]
            contract=json.loads(contract_path.read_text())
            assert contract["execution"]["command"]==job["argv"]
            assert job["argv"][job["argv"].index(str(Path(sys.argv[0]).resolve()))+1:]==sys.argv[1:]
            assert contract["resources"]["gpu_devices"]==[os.environ["CUDA_VISIBLE_DEVICES"]]
            validation_path=Path(job["run_dir"])/"validation.stdout.json"
            validation=json.loads(validation_path.read_text())
            assert validation["valid_for_execution"] is True
            return {"own_pid":os.getpid(),"own_pgid":os.getpgrp(),"lease_path":str(path),"job_path":str(jobpath),"contract_path":str(contract_path),"contract_sha256":sha(contract_path),"validation_path":str(validation_path),"validation_sha256":sha(validation_path),"actual_frozen_argv_equal":True}
        time.sleep(.1)
    raise ValueError("No current owner-issued validated lease for this actual worker PID")
