"""Pre-fit asset/throughput revision: GS-DTA replaces unavailable MRBDTA.

No model, training, validation selection or test scoring is executed here.
"""
import copy
import hashlib
import json
from pathlib import Path

import prepare_campaign as pc

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent
SIDE = PROJECT / "model-audit" / "papers" / "primary-method-verification-sidecar-v3.json"
GS = PROJECT / "model-audit" / "replacement-gs-dta" / "candidate-audit.json"
GPU = PROJECT / "resources" / "local-gpu-route" / "route-summary.json"


if __name__ == "__main__":
    config = pc.read(BASE / "campaign-config.frozen-data-facts-v2.json")
    primary = {row["doi"].lower(): row for row in pc.read(SIDE)["models"]}
    gs = pc.read(GS)
    route = pc.read(GPU)
    retained = [method for method in config["methods"] if method["method_id"] != "MRBDTA"]
    for method in retained:
        paper = primary[method["paper_identity_key"]]
        method["identity"]["pdf"].update(path=paper["pdf_path"], sha256=paper["pdf_sha256"], version="version_of_record")
        method["identity"]["missing_pdf_note"] = None
        method["identity"]["eligibility"]["evidence_paths"].append(str(SIDE))
    new = copy.deepcopy(next(method for method in retained if method["method_id"] == "DeepNC-GEN"))
    new["method_id"] = "GS-DTA"
    new["paper_identity_key"] = gs["paper"]["doi"].lower()
    new["identity"].update(title=gs["paper"]["title"], doi=gs["paper"]["doi"], first_online_date="2025-02-04", publication_status="version_of_record", journal="BMC Genomics")
    new["identity"]["pdf"] = {"path": gs["paper"]["pdf_path"], "sha256": gs["paper"]["pdf_sha256"], "version": "version_of_record", "source_url": "https://doi.org/" + gs["paper"]["doi"]}
    new["identity"]["primary_document"] = {"path": gs["paper"]["pdf_path"], "sha256": gs["paper"]["pdf_sha256"], "format": "publisher_version_of_record_pdf", "source_url": "https://doi.org/" + gs["paper"]["doi"], "identity_doi_verified": True}
    new["identity"]["eligibility"]["evidence_paths"] = [str(GS)]
    new["input_encoding_audit"].update(status="pending_actual_adapter_GPU_verification", protein_prefix_length=1000, evidence_paths=[str(GS)])
    new["code"] = [{"role": "primary_author_source", "source_url": gs["code"]["repository"], "path": gs["code"]["source_root"], "commit": gs["code"]["commit"], "archive_sha256": None, "license": gs["code"]["license"], "checkout_status": gs["code"]["snapshot_kind"], "submodules_lfs": "Selected source snapshot15 files; complete Git/LFS checkout not claimed", "dependency_lock_path": None, "integrity": "partial", "patch_path": None, "evidence_paths": [str(GS), gs["code"]["source_manifest"]], "notes": "Published GS-DTA author class, not incorrect GraphDTA classes imported in author training_validation.py. Full atom graph omits chirality/bond-order; source CNN channel semantics retained. Task adapter pending real smoke/GPU verification; no author task weights."}]
    new["models"] = [{"name": "GS-DTA", "version": "from_scratch_author_GATv2_GCN_CNN_BiLSTM_Transformer", "source_url": gs["code"]["repository"], "path": None, "sha256": None, "configuration_path": str(GS), "configuration_sha256": pc.sha(GS), "coverage": "Full frozen9619 candidate roster; exact effective input verification pending", "license": gs["code"]["license"], "integrity": "not_applicable", "evidence_paths": [str(GS)], "notes": "No pretrained or prior-task supervised weights; native model instantiated from source and trained only in new fixed scope. Checkpoints are future outputs."}]
    retained.append(new)
    registered = []
    verified_gpu = {row["method_id"] for row in route["rows"]}
    for method in retained:
        doi = method["paper_identity_key"]
        task_id = "NC-PAPER-" + hashlib.sha256(doi.encode("utf-8")).hexdigest()[:12]
        method["task_id"] = task_id
        method["registration_status"] = "proposed_stable_id_pending_root_new_batch_registration"
        method["relation_to_prior_run"] += " This DOI-derived stable ID is proposed for a separate new benchmark batch; root must link duplicate historical identities without changing old62 expiry/status."
        pdf = method["identity"]["pdf"]
        pdf_path = Path(pdf["path"])
        if pc.sha(pdf_path) != pdf["sha256"] or not pdf_path.read_bytes()[:5] == b"%PDF-":
            raise ValueError("Real published PDF byte identity failed: " + method["method_id"])
        method["environment"].update(isolation="Task source/adapters/vendor dependencies isolated under current workspace; existing generic WSL Python virtual environment reused read-only; no shared package installation", environment_path=route["environment"].rsplit("/bin/python", 1)[0], lockfile_path=None, lockfile_sha256=None, runtime_versions=route["runtime"], shared_environment_modified=False)
        method["environment"]["numerical_policy"].update(determinism="Torch seeds and deterministic_algorithms(warn_only=True); exact CUDA bit determinism not claimed; MGraphDTA adaptive max pool nondeterminism warning retained", notes="Generic WSL GPU route is separate from restricted workflows; GPU canary does not establish full-fit feasibility or equality with Node23. Actual policy/launch snapshot pending.")
        method["environment"]["PYTHONPATH"] = route["PYTHONPATH"]
        method["resources"].update(expected_hostname="cihebi", cpu_threads=2, data_loader_workers=0, memory_limit_bytes=4294967296, gpu_devices=[0], gpu_memory_budget_bytes=3221225472, resource_probe_path=str(GPU), resource_probe_at=None, start_gate="Pending final root live GPU process/profile gate: at most1 physical GPU, at most3 owned concurrent processes only if profiled feasible; per-fit CPU2/RSS4GiB/GPUallocated3GiB", budget_basis="Pre-fit throughput-driven revision from Node23 CPU plan; no validation/test metric consulted; current route canary verifies original four retained methods, GS-DTA adapter/GPU gate still pending")
        method["execution"].update(command=None, working_directory=None, timeout_seconds=None, stdout_path=None, stderr_path=None, process_control={"platform": "Linux WSL", "mechanism": "Pending actual root launch/run_unit.py and process-group supervisor", "whole_tree_bounded": None})
        method["GPU_component_status"] = "verified_existing_GPU_canary" if method["method_id"] in verified_gpu else "pending_GS_DTA_actual_adapter_GPU_canary"
        method["GPU_component_evidence_path"] = str(GPU) if method["method_id"] in verified_gpu else str(GS)
        registered.append({"proposed_task_id": task_id, "method_id": method["method_id"], "doi": doi, "title": method["identity"]["title"], "published_pdf_path": pdf["path"], "published_pdf_sha256": pdf["sha256"], "code_commit": method["code"][0]["commit"], "code_source_path": method["code"][0]["path"], "registration_state": "proposed_only_root_to_register", "linked_task_ids": method["linked_task_ids"], "prior_run_ids": method["prior_run_ids"], "identity_dedup_rule": "Exact normalized DOI and version; no new scientific reset of linked historical tasks", "GPU_component_status": method["GPU_component_status"]})
    config["methods"] = retained
    for regime in config["training_regimes"]:
        regime["max_epochs"] = 20
        regime["patience"] = 5
    config["protocol_revision"] = {"revision": 3, "basis": "Before any formal fit, method replacement solely for actual PDF/source availability; runtime/budget revision solely for train-throughput feasibility; no validation/test metrics used", "replaced_method": "MRBDTA", "replacement_method": "GS-DTA", "retained_MRBDTA_history": "v1/v2 drafts, smoke and unavailable-PDF receipts unchanged; not one of current five", "previous_max_epochs": 30, "current_max_epochs": 20, "patience": 5, "LR_candidates": [0.001, 0.0003], "seed_list": list(range(10)), "hard_deadline_unchanged": "2026-10-22T01:45:00+00:00", "host_route": "generic local WSL GPU on cihebi; no installation or shared environment mutation", "GPU_evidence_path": str(GPU), "GS_static_evidence_path": str(GS), "actual_training_runs_at_revision": 0, "actual_test_scores_at_revision": 0, "root_decision_authority": "Direct parent message in same authorized campaign"}
    config["known_pending_fields"] = ["root new-batch stable-ID registration/linkage", "GS-DTA actual adapter/GPU component verification", "actual fit-spec and launch/run_unit.py paths/SHAs", "final process/profile gate and concurrency", "environment freeze and numerical receipt", "per-unit real command/log/timeout/process-tree control"]
    pc.write_new(BASE / "paper-registration-proposal-v3.json", {"schema": "peptide-binding.nc-benchmark.paper-registration-proposal.v1", "created_at": pc.now(), "proposed_new_batch": "peptide-binding-nc-benchmark-20261021", "actual_registry_changes": 0, "paper_count": len(registered), "papers": registered, "blocked_MRBDTA_history_preserved": True})
    path = BASE / "campaign-config.gpu-five-facts-v3.json"
    pc.write_new(path, config)
    index = pc.prepare(path, BASE / "drafts-gpu-five-facts-v3")
    pc.write_new(BASE / "protocol-revision-v3.json", config["protocol_revision"])
    print(json.dumps({"distinct_papers": index["verified_distinct_paper_count"], "draft_units": index["planned_run_rows"], "real_published_PDFs": len(registered), "max_epochs": 20, "actual_training_runs": 0, "GS_GPU_gate_pending": True}))
