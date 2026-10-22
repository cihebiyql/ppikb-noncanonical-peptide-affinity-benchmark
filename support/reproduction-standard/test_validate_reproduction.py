"""Behavior checks use synthetic metadata and temporary files only."""
import hashlib
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from validate_reproduction import file_sha256, validate

ROOT = Path(__file__).parent
AT = "2026-10-20T02:00:00Z"


def fixture():
    contract = json.loads((ROOT / "task-contract.template.json").read_text(encoding="utf-8"))
    contract.update(is_template=False, task_id="TEST001", run_id="run01", contract_status="frozen", frozen_at="2026-10-20T01:00:00Z")
    contract["identity"].update(title="Synthetic administrative fixture", doi="10.0000/test", publication_status="published")
    contract["identity"]["pdf"].update(path="paper.pdf", sha256="a" * 64)
    contract["execution_scope"].update(objective="Validate fixed numeric fixture", authorization_reference="user request fixture", safety_assessment="allowed", scope_coverage="component_only", intended_level="component")
    contract["execution_scope"]["restriction_check"]["prior_platform_restriction"] = False
    contract["timing"].update(first_substantive_started_at="2026-10-20T00:00:00Z", original_deadline_at="2026-10-20T10:00:00Z", effective_deadline_at="2026-10-20T10:00:00Z", prior_window_expired=False)
    contract["resources"].update(expected_hostname="fixture-host", cpu_threads=1, memory_limit_bytes=1024, resource_probe_path="probe.json", resource_probe_at="2026-10-20T01:00:00Z", start_gate="fixture", budget_basis="fixture")
    contract["execution"].update(command="fixture command, never executed", working_directory="fixture", seed_policy="deterministic fixture", timeout_seconds=60, stdout_path="out.log", stderr_path="err.log")
    contract["execution"]["process_control"]["whole_tree_bounded"] = True
    contract["environment"].update(isolation="temporary fixture", environment_path="env", lockfile_path="lock.json")
    contract["assets"]["datasets"][0]["notes"] = "Dataset unknown; no scientific execution by validator"
    contract["assets"]["models"][0].update(integrity="not_applicable", notes="Arithmetic fixture has no model")
    contract["assets"]["code"][0].update(integrity="complete", commit="b" * 40)
    contract["targets"][0].update(target_id="endpoint1", paper_endpoint="Table fixture", metric="count", metric_definition="integer fixture count", statistical_unit="item", denominator=5, unit="count", paper_value=5, paper_value_source="fixture")
    contract["targets"][0]["tolerance"] = {"kind": "exact", "absolute": 0, "relative": 0, "rule": "equal", "reason": None}
    return contract


def record(contract, performed=False):
    result = json.loads((ROOT / "result-record.template.json").read_text(encoding="utf-8"))
    raw = json.dumps(contract).encode()
    result.update(is_template=False, task_id=contract["task_id"], run_id=contract["run_id"], contract_sha256=hashlib.sha256(raw).hexdigest(), lifecycle_status="blocked", reproduction_level="static_audit")
    target = contract["targets"][0]
    result["metric_comparisons"][0].update({key: target[key] for key in ("target_id", "paper_endpoint", "metric", "metric_definition", "statistical_unit", "denominator", "unit", "paper_value")})
    result["incomplete_reasons"] = [{"code": "fixture_block", "description": "No scientific process was started", "affected_targets": ["endpoint1"], "evidence_paths": []}]
    if performed:
        result["execution"].update(performed=True, hostname="fixture-host", command="fixture", working_directory="fixture", environment_path="env", stdout_path="out.log", stderr_path="err.log", receipt_path="receipt.json", exit_verification_path="exit.json", handles_absent_verified_at="2026-10-20T01:04:00Z", pid=12, exit_code=0, started_at="2026-10-20T01:02:00Z", ended_at="2026-10-20T01:03:00Z", effective_deadline_at=contract["timing"]["effective_deadline_at"])
    return result, raw


class ValidatorTests(unittest.TestCase):
    def override_fixture(self, directory):
        contract = fixture()
        contract["timing"].update(first_substantive_started_at="2026-10-19T13:59:00Z",
                                  earliest_associated_preparation_at="2026-10-19T13:58:00Z",
                                  original_deadline_at="2026-10-19T23:59:00Z",
                                  effective_deadline_at="2026-10-20T03:00:00Z", prior_window_expired=True)
        override = {"run_id": contract["run_id"], "authorization_path": "authorization.json",
                    "started_at": "2026-10-20T01:00:00Z", "deadline_at": "2026-10-20T03:00:00Z",
                    "wall_clock_cap_hours": 2}
        receipt = {"schema": "paper-reproduction.explicit-user-window-override.v1",
                   "task_id": contract["task_id"], "run_id": contract["run_id"],
                   "authority": "direct_user_message", "user_message": "允许新增2小时预算并继续运行",
                   "authorized_at": "2026-10-20T01:00:00Z", "wall_clock_cap_hours": 2,
                   "previous_deadline_at": contract["timing"]["original_deadline_at"],
                   "started_at": override["started_at"], "deadline_at": override["deadline_at"]}
        contract["timing"]["user_authorized_execution_window"] = override
        self.write_authorization(contract, receipt, directory)
        return contract, receipt

    @staticmethod
    def write_authorization(contract, receipt, directory):
        raw = json.dumps(receipt).encode()
        (Path(directory) / "authorization.json").write_bytes(raw)
        contract["timing"]["user_authorized_execution_window"]["authorization_sha256"] = hashlib.sha256(raw).hexdigest()

    def test_explicit_override_preserves_expired_history_and_reads_receipt_without_check_files(self):
        with tempfile.TemporaryDirectory() as directory:
            contract, _ = self.override_fixture(directory)
            answer = validate(contract, at=AT, contract_directory=directory)
            self.assertTrue(answer["valid_for_execution"], answer)
            self.assertTrue(answer["files_checked"][0]["hash_verified"])
            self.assertTrue(contract["timing"]["prior_window_expired"])
            self.assertEqual(contract["timing"]["first_substantive_started_at"], "2026-10-19T13:59:00Z")
            self.assertEqual(contract["timing"]["earliest_associated_preparation_at"], "2026-10-19T13:58:00Z")

    def test_override_missing_modified_or_remote_receipt_is_rejected(self):
        for change in ("missing", "modified", "remote", "sha_missing", "json_list", "malformed"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                contract, _ = self.override_fixture(directory)
                override = contract["timing"]["user_authorized_execution_window"]
                path = Path(directory) / "authorization.json"
                if change == "missing":
                    path.unlink()
                elif change == "modified":
                    path.write_text("{}")
                elif change == "remote":
                    override["authorization_path"] = "ssh://fixture/authorization.json"
                elif change == "sha_missing":
                    override.pop("authorization_sha256")
                else:
                    raw = b"[]" if change == "json_list" else b"{invalid"
                    path.write_bytes(raw)
                    override["authorization_sha256"] = hashlib.sha256(raw).hexdigest()
                self.assertFalse(validate(contract, at=AT, contract_directory=directory)["valid_for_execution"])

    def test_override_receipt_identity_and_human_authority_are_required(self):
        changes = {"schema": "wrong", "task_id": "OTHER", "run_id": "old-run",
                   "authority": "agent_inference", "user_message": "continue",
                   "previous_deadline_at": "2026-10-19T23:58:00Z",
                   "started_at": "2026-10-20T01:01:00Z", "deadline_at": "2026-10-20T03:01:00Z",
                   "wall_clock_cap_hours": 3, "authorized_at": "2026-10-19T20:00:00Z"}
        for key, value in changes.items():
            with self.subTest(field=key), tempfile.TemporaryDirectory() as directory:
                contract, receipt = self.override_fixture(directory)
                receipt[key] = value
                self.write_authorization(contract, receipt, directory)
                self.assertFalse(validate(contract, at=AT, contract_directory=directory)["valid_for_execution"])

    def test_override_cannot_reset_started_at_or_change_run_reusing_authorization(self):
        with tempfile.TemporaryDirectory() as directory:
            contract, _ = self.override_fixture(directory)
            contract["timing"]["user_authorized_execution_window"]["started_at"] = "2026-10-20T02:00:00Z"
            contract["timing"]["effective_deadline_at"] = "2026-10-20T04:00:00Z"
            self.assertFalse(validate(contract, at=AT, contract_directory=directory)["valid_for_execution"])
        with tempfile.TemporaryDirectory() as directory:
            contract, _ = self.override_fixture(directory)
            contract["run_id"] = "another-stage"
            self.assertFalse(validate(contract, at=AT, contract_directory=directory)["valid_for_execution"])

    def test_override_does_not_bypass_safety_restriction_retry_or_expired_fact(self):
        for change in ("safety", "platform", "retry", "expired_fact", "override_cap"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                contract, _ = self.override_fixture(directory)
                if change == "safety":
                    contract["execution_scope"]["safety_assessment"] = "unverified"
                elif change == "platform":
                    contract["execution_scope"]["restriction_check"]["prior_platform_restriction"] = True
                elif change == "retry":
                    contract["timing"]["retry_resets_clock"] = True
                elif change == "expired_fact":
                    contract["timing"]["prior_window_expired"] = False
                else:
                    contract["timing"]["user_authorized_execution_window"]["wall_clock_cap_hours"] = True
                self.assertFalse(validate(contract, at=AT, contract_directory=directory)["valid_for_execution"])

    def test_override_effective_deadline_is_bounded_and_old_authorization_expires(self):
        with tempfile.TemporaryDirectory() as directory:
            contract, receipt = self.override_fixture(directory)
            self.assertFalse(validate(contract, at="2026-10-20T03:00:00Z", contract_directory=directory)["valid_for_execution"])
            contract["timing"]["effective_deadline_at"] = "2026-10-20T03:01:00Z"
            self.assertFalse(validate(contract, at=AT, contract_directory=directory)["valid_for_execution"])
            contract["timing"]["effective_deadline_at"] = "2026-10-20T02:30:00Z"
            receipt["deadline_at"] = "2026-10-20T02:30:00Z"
            contract["timing"]["user_authorized_execution_window"]["deadline_at"] = receipt["deadline_at"]
            self.write_authorization(contract, receipt, directory)
            self.assertTrue(validate(contract, at=AT, contract_directory=directory)["valid_for_execution"])

    def test_override_rejects_future_start_and_retroactive_authorization(self):
        for change in ("future", "retroactive", "old_frozen", "end_before_start"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                contract, receipt = self.override_fixture(directory)
                if change == "future":
                    receipt["started_at"] = "2026-10-20T02:01:00Z"
                elif change == "retroactive":
                    receipt["authorized_at"] = "2026-10-20T01:01:00Z"
                elif change == "old_frozen":
                    contract["frozen_at"] = "2026-10-20T00:59:00Z"
                else:
                    receipt["deadline_at"] = "2026-10-20T00:59:00Z"
                for key in ("started_at", "deadline_at"):
                    contract["timing"]["user_authorized_execution_window"][key] = receipt[key]
                self.write_authorization(contract, receipt, directory)
                self.assertFalse(validate(contract, at=AT, contract_directory=directory)["valid_for_execution"])

    def test_override_result_cannot_precede_window_or_exceed_it(self):
        with tempfile.TemporaryDirectory() as directory:
            contract, receipt = self.override_fixture(directory)
            contract["frozen_at"] = "2026-10-20T01:00:00Z"
            receipt["started_at"] = "2026-10-20T01:01:00Z"
            contract["timing"]["user_authorized_execution_window"]["started_at"] = receipt["started_at"]
            self.write_authorization(contract, receipt, directory)
            result, raw = record(contract, performed=True)
            self.assertTrue(validate(contract, result, contract_bytes=raw, at=AT, contract_directory=directory)["valid"])
            result["execution"]["started_at"] = "2026-10-20T01:00:30Z"
            self.assertFalse(validate(contract, result, contract_bytes=raw, at=AT, contract_directory=directory)["valid"])
            result["execution"].update(started_at="2026-10-20T01:02:00Z", ended_at="2026-10-20T03:00:01Z")
            self.assertFalse(validate(contract, result, contract_bytes=raw, at=AT, contract_directory=directory)["valid"])

    def test_override_uses_two_hour_cap_even_if_receipt_deadline_is_later(self):
        with tempfile.TemporaryDirectory() as directory:
            contract, receipt = self.override_fixture(directory)
            receipt["deadline_at"] = "2026-10-20T04:00:00Z"
            contract["timing"]["user_authorized_execution_window"]["deadline_at"] = receipt["deadline_at"]
            self.write_authorization(contract, receipt, directory)
            self.assertTrue(validate(contract, at=AT, contract_directory=directory)["valid_for_execution"])
            contract["timing"]["effective_deadline_at"] = receipt["deadline_at"]
            self.assertFalse(validate(contract, at=AT, contract_directory=directory)["valid_for_execution"])

    def test_override_receipt_is_checked_with_general_file_checks_enabled_too(self):
        with tempfile.TemporaryDirectory() as directory:
            contract, _ = self.override_fixture(directory)
            answer = validate(contract, at=AT, contract_directory=directory, check_files=True)
            # Other fixture paths deliberately do not exist, but authorization is locally verified.
            self.assertTrue(any(item["field"].endswith("user_authorized_execution_window.authorization_path")
                                and item["hash_verified"] for item in answer["files_checked"]))
            (Path(directory) / "authorization.json").unlink()
            answer = validate(contract, at=AT, contract_directory=directory, check_files=True)
            self.assertFalse(answer["valid_for_execution"])

    def test_override_keeps_template_nonexecutable_and_actual_timeout_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            contract, _ = self.override_fixture(directory)
            contract["is_template"] = True
            self.assertFalse(validate(contract, at=AT, contract_directory=directory, allow_template=True)["valid_for_execution"])
            contract["is_template"] = False
            result, raw = record(contract, performed=True)
            result["execution"].update(started_at="2026-10-20T02:59:30Z", ended_at="2026-10-20T02:59:40Z")
            self.assertFalse(validate(contract, result, contract_bytes=raw, at=AT, contract_directory=directory)["valid"])

    def test_template_structure_never_executes(self):
        template = json.loads((ROOT / "task-contract.template.json").read_text(encoding="utf-8"))
        self.assertFalse(validate(template, at=AT)["valid"])
        answer = validate(template, at=AT, allow_template=True)
        self.assertTrue(answer["valid"])
        self.assertFalse(answer["valid_for_execution"])

    def test_valid_contract(self):
        self.assertTrue(validate(fixture(), at=AT)["valid_for_execution"])

    def test_shortened_preparation_deadline(self):
        contract = fixture()
        contract["timing"]["earliest_associated_preparation_at"] = "2026-10-19T23:00:00Z"
        self.assertFalse(validate(contract, at=AT)["valid"])
        contract["timing"]["effective_deadline_at"] = "2026-10-20T09:00:00Z"
        self.assertTrue(validate(contract, at=AT)["valid"])

    def test_expiry_and_retry_reset_refused(self):
        contract = fixture()
        self.assertFalse(validate(contract, at="2026-10-20T10:00:00Z")["valid"])
        contract["timing"]["retry_resets_clock"] = True
        self.assertFalse(validate(contract, at=AT)["valid"])

    def test_prior_window_or_platform_restriction_blocks_execution(self):
        for field in ("prior_window_expired", "prior_platform_restriction"):
            contract = fixture()
            target = contract["timing"] if field == "prior_window_expired" else contract["execution_scope"]["restriction_check"]
            target[field] = True
            self.assertFalse(validate(contract, at=AT)["valid_for_execution"])

    def test_timeout_bounded(self):
        self.assertFalse(validate(fixture(), at="2026-10-20T09:59:30Z")["valid"])

    def test_contract_hash_mismatch(self):
        contract = fixture()
        result, raw = record(contract)
        result["contract_sha256"] = "f" * 64
        self.assertFalse(validate(contract, result, contract_bytes=raw, at=AT)["valid"])

    def test_blocked_unrun_expired_record_can_archive(self):
        contract = fixture()
        result, raw = record(contract)
        answer = validate(contract, result, contract_bytes=raw, at="2026-10-21T00:00:00Z")
        self.assertTrue(answer["valid"])
        self.assertFalse(answer["valid_for_execution"])
        self.assertIsNone(result["metric_comparisons"][0]["actual_value"])

    def test_failed_full_paper_refused(self):
        contract = fixture()
        result, raw = record(contract, performed=True)
        result.update(lifecycle_status="failed", reproduction_level="full_paper", scope_coverage="full")
        self.assertFalse(validate(contract, result, contract_bytes=raw, at=AT)["valid"])

    def test_claimed_pass_outside_tolerance_rejected(self):
        contract = fixture()
        result, raw = record(contract, performed=True)
        result["metric_comparisons"][0].update(actual_value=6, comparability="comparable", passed=True)
        self.assertFalse(validate(contract, result, contract_bytes=raw, at=AT)["valid"])

    def test_boolean_true_exact_accepted_without_arithmetic(self):
        contract = fixture()
        contract["targets"][0]["paper_value"] = True
        result, raw = record(contract, performed=True)
        result["metric_comparisons"][0].update(actual_value=True, comparability="comparable", passed=True, absolute_difference=0, relative_difference=None)
        self.assertTrue(validate(contract, result, contract_bytes=raw, at=AT)["valid"])
        result["metric_comparisons"][0]["absolute_difference"] = None
        self.assertTrue(validate(contract, result, contract_bytes=raw, at=AT)["valid"])

    def test_boolean_false_cannot_claim_exact_true_pass(self):
        contract = fixture()
        contract["targets"][0]["paper_value"] = True
        result, raw = record(contract, performed=True)
        result["metric_comparisons"][0].update(actual_value=False, comparability="comparable", passed=True)
        self.assertFalse(validate(contract, result, contract_bytes=raw, at=AT)["valid"])

    def test_boolean_unknown_actual_remains_unknown_in_unrun_archive(self):
        contract = fixture()
        contract["targets"][0]["paper_value"] = True
        result, raw = record(contract)
        self.assertIsNone(result["metric_comparisons"][0]["actual_value"])
        self.assertTrue(validate(contract, result, contract_bytes=raw, at=AT)["valid"])

    def test_boolean_numeric_mix_rejected_even_for_one(self):
        for contract_paper, paper, actual in ((True, True, 1), (True, 1, True), (1, True, True), (1, 1, True)):
            with self.subTest(contract_paper=contract_paper, paper=paper, actual=actual):
                contract = fixture()
                contract["targets"][0]["paper_value"] = contract_paper
                result, raw = record(contract, performed=True)
                result["metric_comparisons"][0].update(paper_value=paper, actual_value=actual, comparability="comparable", passed=True)
                self.assertFalse(validate(contract, result, contract_bytes=raw, at=AT)["valid"])

    def test_boolean_requires_exact_and_no_relative_difference(self):
        contract = fixture()
        contract["targets"][0]["paper_value"] = True
        result, raw = record(contract, performed=True)
        result["metric_comparisons"][0].update(actual_value=True, comparability="comparable", passed=True, relative_difference=0)
        self.assertFalse(validate(contract, result, contract_bytes=raw, at=AT)["valid"])
        contract["targets"][0]["tolerance"] = {"kind": "absolute", "absolute": 0}
        result, raw = record(contract, performed=True)
        result["metric_comparisons"][0].update(actual_value=True, comparability="comparable", passed=True)
        self.assertFalse(validate(contract, result, contract_bytes=raw, at=AT)["valid"])

    def test_full_paper_positive_case_requires_all_evidence(self):
        contract = fixture()
        contract["execution_scope"].update(intended_level="full_paper", scope_coverage="full")
        contract["assets"]["datasets"][0].update(integrity="complete", name="Synthetic fixture", path="fixture.json", manifest_sha256="c" * 64)
        result, raw = record(contract, performed=True)
        result.update(lifecycle_status="succeeded", reproduction_level="full_paper", scope_coverage="full", incomplete_reasons=[])
        result["review"]["status"] = "accepted"
        for check in result["review"]["checks"]:
            check["passed"] = True
        for category in ("datasets", "code", "models", "environment"):
            result["assets_integrity"][category]["status"] = "complete"
        result["metric_comparisons"][0].update(actual_value=5, comparability="comparable", passed=True)
        self.assertTrue(validate(contract, result, contract_bytes=raw, at=AT)["valid_for_acceptance"])
        result["assets_integrity"]["models"]["status"] = "unknown"
        self.assertFalse(validate(contract, result, contract_bytes=raw, at=AT)["valid_for_acceptance"])

    def test_published_outputs_cannot_claim_inference(self):
        contract = fixture()
        contract["execution_scope"].update(intended_level="published_output_reanalysis", scope_coverage="published_outputs_only")
        result, raw = record(contract, performed=True)
        result.update(reproduction_level="independent_inference", scope_coverage="full")
        self.assertFalse(validate(contract, result, contract_bytes=raw, at=AT)["valid"])

    def test_endpoint_denominator_mismatch(self):
        contract = fixture()
        result, raw = record(contract)
        result["metric_comparisons"][0]["denominator"] = 6
        self.assertFalse(validate(contract, result, contract_bytes=raw, at=AT)["valid"])

    def test_nonfinite_numeric_rejected(self):
        contract = fixture()
        result, raw = record(contract)
        result["metric_comparisons"][0]["actual_value"] = float("nan")
        self.assertFalse(validate(contract, result, contract_bytes=raw, at=AT)["valid"])

    def test_file_hash_and_remote_skip(self):
        contract = json.loads((ROOT / "task-contract.template.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.pdf"
            path.write_bytes(b"administrative fixture")
            contract["identity"]["pdf"].update(path=str(path), sha256="0" * 64)
            contract["assets"]["models"][0].update(path="ssh://fixture/model", sha256="a" * 64)
            answer = validate(contract, at=AT, allow_template=True, check_files=True)
            self.assertFalse(answer["valid"])
            self.assertTrue(answer["files_skipped"])
            contract["identity"]["pdf"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            answer = validate(contract, at=AT, allow_template=True, check_files=True)
            self.assertTrue(answer["valid"])

    def test_chunked_hash_without_python311_file_digest(self):
        content = b"administrative compatibility fixture\n" * 70000
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large-fixture.bin"
            path.write_bytes(content)
            with mock.patch.object(hashlib, "file_digest", create=True, side_effect=AssertionError("Python 3.11 API must not be called")):
                self.assertEqual(file_sha256(path), hashlib.sha256(content).hexdigest())

    def test_performed_result_needs_exit_and_respects_deadline(self):
        contract = fixture()
        result, raw = record(contract, performed=True)
        result["execution"]["exit_code"] = None
        self.assertFalse(validate(contract, result, contract_bytes=raw, at=AT)["valid"])
        result["execution"].update(exit_code=0, ended_at="2026-10-20T10:01:00Z")
        self.assertFalse(validate(contract, result, contract_bytes=raw, at=AT)["valid"])


if __name__ == "__main__":
    unittest.main()
