"""Populate known method/data facts into drafts; unknown launch facts stay unknown."""
from __future__ import annotations

import json
from pathlib import Path

import prepare_campaign as pc

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent
ROUTES = PROJECT / "model-audit" / "model-routes.json"
PRIMARY = PROJECT / "model-audit" / "papers" / "primary-method-verification-sidecar.json"
PROBE = PROJECT / "resources" / "live-probe.json"
MODEL_VIEW = PROJECT / "data-protocol" / "model-view-manifest.json"
PROTOCOL = PROJECT / "data-protocol" / "protocol-v1.json"


def make_config():
    config = pc.read(BASE / "campaign-config.skeleton.json")
    routes = pc.read(ROUTES)
    primary = {item["method"]: item for item in pc.read(PRIMARY)["models"]}
    view = pc.read(MODEL_VIEW)
    data = PROJECT / "data-protocol" / view["file"]
    if pc.sha(data) != view["sha256"]:
        raise ValueError("Model view differs from existing manifest; freeze must be resolved by data owner")
    methods = []
    for route in routes["models"]:
        paper = primary[route["name"]]
        model_id = "MRBDTA" if route["name"].startswith("MRBDTA-") else route["name"]
        differences = route["risks"] + paper["differences"]
        method = {
            "method_id": model_id, "task_id": None, "paper_identity_key": route["doi"].lower(),
            "identity": {
                "title": paper["paper_title"], "doi": paper["doi"], "publication_status": paper["published_version"],
                "first_online_date": paper["publication_dates"]["first_online"], "journal": None,
                "paper_type": "published_method_article",
                "pdf": {"path": paper["pdf_path"], "sha256": paper["pdf_sha256"], "version": "version_of_record" if paper["pdf_path"] else "missing", "source_url": paper["source_url"] if paper["pdf_path"] else None},
                "primary_document": {"path": paper["primary_fulltext_path"], "sha256": paper["primary_fulltext_sha256"], "format": paper["primary_fulltext_format"], "source_url": paper["source_url"], "identity_doi_verified": paper["identity_doi_present"]},
                "related_versions": [],
                "eligibility": {"scope": "Prior published model transferred to the newly authorized NC2099 affinity benchmark", "assessment": "allowed_for_scoped_model_comparison", "evidence_paths": [str(PRIMARY), str(ROUTES)]},
                "missing_pdf_note": "Genuine HTML/XML primary article is verified and retained; it is not renamed or represented as a PDF. Central validator PDF-only gate requires an explicit authoritative compatibility decision." if not paper["pdf_path"] else None,
            },
            "prior_run_ids": [], "linked_task_ids": [],
            "relation_to_prior_run": "New direct-user-authorized scientific target: common NC2099 plus standard-residue controls, not a continuation or deadline reset of legacy3354/11250/legacy62 runs. Root must attach matching historic task/run IDs once registered. Existing expired clocks/restrictions remain intact.",
            "restriction_check": {"prior_platform_restriction": False, "reason": "This scoped benchmark excludes PepLand, Twin Peaks, previously denied primary-source unit investigations, sequence design/optimization and metadata-only train exclusions. Old restricted work is not restarted.", "evidence_paths": [str(ROUTES), str(PROTOCOL)]},
            "timing": {"first_substantive_started_at": "2026-10-21T15:59:53+00:00", "earliest_associated_preparation_at": None, "wall_clock_cap_hours": 10, "original_deadline_at": "2026-10-22T01:59:53+00:00", "additional_deadlines_at": ["2026-10-22T01:45:00+00:00"], "effective_deadline_at": "2026-10-22T01:45:00+00:00", "prior_window_expired": False, "retry_resets_clock": False, "timing_evidence_paths": [str(PROBE)], "clock_notes": "15:59:53Z is first persisted campaign clock as provided by leader; early skill reading may precede this. Conservative hard cutoff01:45Z applies to all papers/panels/seeds. prior_window_expired=false describes the newly authorized scope only; no historical expired task is revived."},
            "input_encoding_audit": {"status": "verified", "non_natural_residue_supported": True, "PTM_supported": True, "mixed_supported": True, "peptide_sequence_projection_used": False, "chemical_information_loss": "Author graph inputs are stereochemistry-blind; full raw isomeric SMILES retained as provenance and evaluated for blind equivalence sensitivity." if not route["chirality"] else "Author isomeric SMILES alternative vocabulary selected; compatibility fixes disclosed.", "unrecognized_tokens_handling": "Block with explicit failed coverage; no silent standard-AA substitution", "protein_prefix_length": route["cap"], "full_peptide_smiles_no_cap": True, "evidence_paths": [str(ROUTES), str(PRIMARY)]},
            "code": [{"role": "primary_author_source", "source_url": "https://github.com/" + route["repo"], "path": route["source_root"], "commit": route["source_commit"], "archive_sha256": None, "license": route["license"], "checkout_status": "frozen_selected_author_source", "submodules_lfs": "Not asserted complete; selected source tree and manifest retained", "dependency_lock_path": None, "integrity": "partial", "patch_path": None, "evidence_paths": [route["source_manifest"], str(ROUTES)], "notes": "Selected author implementation used through isolated adapter. " + " | ".join(differences)}],
            "models": [{"name": model_id, "version": "from_scratch_author_architecture_adapted_input", "source_url": "https://github.com/" + route["repo"], "path": None, "sha256": None, "configuration_path": str(ROUTES), "configuration_sha256": pc.sha(ROUTES), "coverage": "NC2099+standard control candidates; exact frozen per-panel/train scope pending", "license": route["license"], "integrity": "not_applicable", "evidence_paths": [str(ROUTES)], "notes": "No pretrained or prior-task supervised weights loaded; checkpoints are outputs of the planned training rather than missing input weights."}],
            "environment": {"isolation": "Existing Node23 task-specific virtual environment, no shared-environment change", "environment_path": "/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/.venv", "lockfile_path": None, "lockfile_sha256": None, "runtime_versions": {}, "shared_environment_modified": False,
                "numerical_policy": {"author_entrypoint_evidence_paths": [str(ROUTES)], "parameter_dtype": "float32", "input_dtype": "float32 graph features and int64 token/edge indices", "autocast": False, "float32_matmul_precision": None, "cuda_matmul_allow_tf32": False, "cudnn_allow_tf32": False, "determinism": "torch.use_deterministic_algorithms(True,warn_only=True); seeds Python/NumPy/Torch; CPU; exact policy probe pending", "applied_before_model_instantiation": True, "actual_policy_receipt_path": None, "notes": "Known from new execution/runner.py; executable environment snapshot and numerical receipt still required before freeze."}},
            "resources": {"expected_hostname": "node23", "cpu_threads": 1, "data_loader_workers": 0, "memory_limit_bytes": 6442450944, "gpu_devices": [], "gpu_memory_budget_bytes": None, "resource_probe_path": str(PROBE), "resource_probe_at": pc.read(PROBE)["generated_at"], "start_gate": "Pending task-specific execution-time Node23 probe; maximum16 simultaneous CPU1 fits,6GiB each,pool96GiB; no GPU; no preemption", "budget_basis": "Leader proposal based on real Node23 capacity probe; not yet an execution launch gate", "no_preemption": True},
            "execution": {"command": None, "working_directory": None, "seed_policy": "seeds0–9, same fixed partitions; two LR candidates per seed; validation only", "seeds": [], "timeout_seconds": None, "process_control": {"platform": "Linux", "mechanism": "Pending root process-group or cgroup bounded pool supervisor", "whole_tree_bounded": None}, "stdout_path": None, "stderr_path": None},
        }
        methods.append(method)
    config["methods"] = methods
    config["splits"] = [{"split_id": split_id, "datasets": [{"name": "PPIKB_NC2099_standard7520_Kd_model_view", "version": "prepared_model_view_pending_frozen_v1_adoption", "source_url": "https://www.nature.com/articles/s41597-026-07962-1", "license": None, "path": str(data), "manifest_sha256": pc.sha(MODEL_VIEW), "sample_count": view["rows"], "statistical_unit": "original measurement record; dependent records grouped in the frozen partition", "splits": {"train": None, "validation": None, "test": None, "split_manifest_sha256": None}, "preprocessing": "Full raw isomeric SMILES and reference protein sequence; no peptide atom cap; same original pKd, no value repair; residue strata audit metadata excluded as model features", "leakage_check": {"status": "pending_frozen_v1", "method": split_id, "evidence_paths": [str(PROTOCOL)]}, "integrity": "partial", "notes": "Full roster9619 =NC2099+standard7520. Final split manifest/partition counts and hashes pending. This is not a frozen split claim."}]} for split_id in ("source_chemical_cold", "target_reference_homology_cold")]
    config["training_regimes"] = [{"regime_id": regime, "train_scope": regime, "validation_scope": "same_as_regime", "selection": "lowest validation MAE by epoch and LR; ties lower candidate index", "candidates": [{"learning_rate": 0.001, "weight_decay": 0.0}, {"learning_rate": 0.0003, "weight_decay": 0.0}], "max_epochs": 30, "patience": 5, "holdout_scope": "all retained test records, mutually exclusive chemistry strata plus608 annotation-discordance sensitivity flags; score only after selection frozen"} for regime in ("NC_only", "standard_only")]
    config["evaluation_strata"] = ["synthetic_D_backbone", "PTM", "synthetic_and_PTM", "other_NC", "standard20_control"]
    config["targets"] = [{"target_id": "pKd_MAE", "paper_endpoint": "New common PPIKB peptide–protein Kd benchmark using the published architecture", "required": True, "dataset_reference": "PPIKB_NC2099_standard7520", "comparison_endpoint": "held-out exact experimental pKd", "metric": "MAE", "metric_definition": "mean(abs(predicted_pKd-observed_pKd)); stratified and whole-test denominators retained", "statistical_unit": "measurement record; fixed source/chemical or reference-homology groups define partitions", "denominator": None, "unit": "pKd (-log10 molar Kd)", "paper_value": None, "paper_value_source": None, "baseline": "standard-only control with same model and search budget", "checkpoint_selection": "validation MAE only; minimum epoch then LR candidate0/1 with fixed tie rule", "repetitions": 10, "tolerance": {"kind": "not_comparable", "absolute": None, "relative": None, "rule": None, "reason": "Changed dataset, endpoint scope, tuning budget and disclosed source repairs; no original-paper table replication claimed."}, "evidence_paths": [str(ROUTES), str(PRIMARY), str(PROTOCOL)]}]
    config["planned_candidates_per_selected_run"] = 2
    config["planned_final_selections"] = 200
    config["planned_candidate_fits"] = 400
    config["known_pending_fields"] = ["stable task/linked historic IDs", "frozen-v1 split and train/validation input SHA", "execution host-specific env snapshot", "training wrapper command and process control", "launch timeout and stdout/stderr paths", "central fulltext compatibility rule for4 missing PDFs", "actual608 discordance sensitive-score input manifest"]
    return config


if __name__ == "__main__":
    target = BASE / "campaign-config.current-facts-v1.json"
    pc.write_new(target, make_config())
    index = pc.prepare(target, BASE / "drafts-current-facts-v1")
    print(json.dumps({"method_count": index["method_count"], "distinct_papers": index["verified_distinct_paper_count"], "drafts": index["planned_run_rows"], "actual_runs": index["actual_runs"], "executable": index["executable"]}))
