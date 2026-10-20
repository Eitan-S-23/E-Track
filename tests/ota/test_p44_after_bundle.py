"""Bounded C5 adapter tests: real C4 reads, synthetic writes, zero network."""
import base64
import copy
import contextlib
import gzip
import hashlib
import importlib.util
import json
import io
from pathlib import Path
import stat
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).absolute().parents[2]
SPEC = importlib.util.spec_from_file_location("p44_after_bundle", ROOT / "Tools/ota/p44-after-bundle.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)
DEV = ROOT / ".cache/p44-v5-development/python"
FUTURE_TREE = "e" * 40
ADDITIONS = ["Tools/ota/p44-after-bundle.py", "Tools/ota/p44-after-recovery.cjs",
             "tests/ota/test_p44_after_bundle.py", "tests/ota/test_p44_after_recovery.cjs"]


def formal_snapshot():
    files = ([m.CONTRACT] if m.CONTRACT.is_file() else [])
    directories = []
    if m.PACKAGE.exists():
        for file in m.PACKAGE.rglob("*"):
            m.b.guard(file)
            if file.is_file():
                files.append(file)
            elif file.is_dir():
                directories.append(file.relative_to(m.PACKAGE).as_posix())
    return {"contract_exists": m.CONTRACT.exists(), "package_exists": m.PACKAGE.exists(),
            "files": {str(file): m.sha(file) for file in files}, "directories": sorted(directories)}


class AfterBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.formal_before = formal_snapshot()
        cls.parent, cls.previous = m.source_identity()
        cls.copy_plan, cls.descriptor = m.source_plan()
        cls.original = m.INSPECT.Context(ROOT, m.PARENT / "evidence/manifest.json")
        for number in range(1, 100):
            candidate = m.b.guard(DEV / ("batch-" + str(number)))
            if not candidate.exists():
                cls.batch = candidate
                candidate.mkdir(parents=True)
                m.b.guard(candidate)
                break
        else:
            raise AssertionError("TEST_BATCH_BOUND")
        print(json.dumps({"development_only": True, "fixture_root": str(cls.batch),
                          "c4_source_files_verified": len(cls.descriptor["files"]), "network_requests": 0,
                          "source_sha256": m.sha(ROOT / m.PYTHON), "tests_sha256": m.sha(Path(__file__))}), flush=True)

    @classmethod
    def tearDownClass(cls):
        assert formal_snapshot() == cls.formal_before, "TEST_CHANGED_FORMAL_EVIDENCE"

    def directory(self):
        value = m.b.guard(self.batch / self._testMethodName)
        value.mkdir()
        return value

    def write(self, directory, name, data):
        file = m.b.guard(directory / name)
        m.b.write(file, data)
        return m.ref(file, directory)

    def contract(self):
        value = m.successor(self.parent, {"path": m.FIXTURE, "size_bytes": 2, "sha256": "a" * 64})
        value.update(freeze_commit="f" * 40, freeze_tree=FUTURE_TREE)
        return value

    def plan(self, contract):
        original = m.RULES._git_nul_paths
        original_config = m.RULES._profile_config_from_tree

        def prospective_paths(root, args, profile, operation):
            if args[0] == "diff-tree" and FUTURE_TREE in args:
                return ADDITIONS
            return original(root, args, profile, operation)

        digest = m.b.sha(json.dumps(contract, sort_keys=True).encode())
        with patch.object(m.RULES, "_git_nul_paths", prospective_paths), patch.object(m.RULES, "_profile_config_from_tree",
                lambda root, tree: original_config(root, self.parent["freeze_tree"] if tree == FUTURE_TREE else tree)):
            initial = m.initial_matrix(contract, digest)
            return initial, m.computed_plan(contract, initial, self.parent, self.previous, digest=digest)

    def mixed(self):
        contract = self.contract()
        initial, plan = self.plan(contract)
        hashes = copy.deepcopy(self.previous["evidence_hashes"])
        old_commands = {item["id"]: item for item in self.previous["commands"]}
        commands = []
        for item in contract["commands"]:
            if item["id"] in m.EXECUTED:
                name = "evidence/recovery-commands/" + item["id"]
                hashes[name + ".log"] = m.b.sha((name + ".log").encode())
                hashes[name + ".json"] = m.b.sha((name + ".json").encode())
                commands.append({"id": item["id"], "command": item["command"], "exit_code": 0, "output_evidence": name + ".log"})
            else:
                commands.append(copy.deepcopy(old_commands[item["id"]]))
        old_artifacts = {item["id"]: item for item in self.previous["artifacts"]}
        artifacts = []
        for item in contract["artifacts"]:
            if item["id"] in old_artifacts and item["path"] == old_artifacts[item["id"]]["path"]:
                artifacts.append(copy.deepcopy(old_artifacts[item["id"]]))
            else:
                artifacts.append({"id": item["id"], "path": item["path"], "sha256": m.b.sha(item["path"].encode()), "size": 1})
            hashes[item["path"]] = artifacts[-1]["sha256"]
        hashes["rerun-plan.json"] = m.b.sha(json.dumps(plan, sort_keys=True).encode())
        value = m.mixed_matrix(contract, initial, plan, self.previous, commands, artifacts, hashes)
        return value, contract, plan

    def test_actual_c4_inventory_is_bound_to_b4_and_all_bytes(self):
        self.assertEqual(set(self.descriptor), m.DESCRIPTOR_KEYS)
        self.assertEqual(len(self.copy_plan), len(self.descriptor["files"]) + 2)
        self.assertEqual(len(self.descriptor["after_complete"]), 31)
        self.assertEqual([item["path"] for item in self.descriptor["after_failed"]], [m.FAILED])
        self.assertEqual(m.sha(m.PARENT_MATRIX).upper(), m.PARENT_MATRIX_HASH)
        self.assertEqual(formal_snapshot(), self.formal_before)

    def test_four_reused_definitions_and_external_signatures_unchanged(self):
        current = self.contract()
        for identifier in m.REUSED:
            old = next(item for item in self.parent["criteria"] if item["id"] == identifier)
            new = next(item for item in current["criteria"] if item["id"] == identifier)
            self.assertEqual(new, old)
            for table, key in (("commands", "command_ids"), ("artifacts", "artifact_ids"), ("external_inputs", "external_inputs")):
                for name in old[key]:
                    self.assertEqual(next(item for item in self.parent[table] if item["id"] == name),
                                     next(item for item in current[table] if item["id"] == name))

    def test_stock_plan_filters_prospective_paths_without_new_profile(self):
        initial, plan = self.plan(self.contract())
        self.assertEqual(plan["changed_input_groups"], ["validation"])
        self.assertEqual(set(plan["reusable_criteria"]), m.REUSED)
        self.assertEqual(set(plan["required_commands"]), m.EXECUTED)
        self.assertEqual(plan["previous_matrix_sha256"], m.PARENT_MATRIX_HASH)
        m.admitted_plan(plan)
        self.assertEqual(initial["overall_result"], "NOT_RUN")

    def test_command_description_drift_requires_stop_not_replay(self):
        contract = self.contract()
        next(item for item in contract["commands"] if item["id"] == "formal-dispatch-b")["description"] += " changed"
        _, plan = self.plan(contract)
        self.assertIn("formal-dispatch-b", plan["required_commands"])
        with self.assertRaisesRegex(AssertionError, "RECOVERY_PLAN_DRIFT"):
            m.admitted_plan(plan)

    def test_external_description_drift_invalidates_reuse(self):
        contract = self.contract()
        next(item for item in contract["external_inputs"] if item["id"] == "host")["description"] += " changed"
        _, plan = self.plan(contract)
        self.assertIn("host", plan["changed_external_inputs"])
        self.assertNotIn("P44-RAW-RUNS", plan["reusable_criteria"])

    def test_transitive_runner_paths_registered(self):
        contract = self.contract()
        for command in contract["commands"]:
            if command["id"] in m.EXECUTED:
                self.assertTrue({m.NODE, m.PYTHON, "Tools/acceptance/p44/capture.cjs", "Tools/acceptance/p44/run.cjs",
                    "Tools/acceptance/p44/bundle.py", "Tools/acceptance/p44/inspect.py", "Tools/acceptance/validate_bundle.py"} <= set(command["runner_paths"]))
                self.assertIn("validation", command["input_groups"])
        self.assertFalse(m.RULES.validate_contract(contract))

    def test_product_target_remains_c4_while_tools_freeze_changes(self):
        contract = self.contract()
        self.assertEqual(contract["implementation_ref"], m.SOURCE)
        self.assertNotEqual(contract["freeze_commit"], m.SOURCE)
        self.assertEqual(self.original.document(self.descriptor["target"])["commitSha"], m.SOURCE)

    def test_mixed_matrix_has_direct_origins_and_unique_commands(self):
        value, contract, plan = self.mixed()
        self.assertEqual(value["overall_result"], "PASS")
        self.assertEqual(len(value["commands"]), 17)
        self.assertEqual(len({item["id"] for item in value["commands"]}), 17)
        self.assertEqual(value["previous_matrix_sha256"], m.PARENT_MATRIX_HASH)
        self.assertEqual(value["rerun_plan_sha256"], value["evidence_hashes"][value["rerun_plan_path"]])
        for item in value["criteria"]:
            if item["id"] in m.REUSED:
                self.assertEqual(item["execution"], "REUSED")
                self.assertEqual(item["origin_contract_sha256"], m.PARENT_HASH)
                self.assertEqual(item["origin_matrix_sha256"], m.PARENT_MATRIX_HASH)
        self.assertFalse(m.RULES.validate_reuse(value, contract, self.previous, plan))

    def test_reused_evidence_and_command_tampering_rejected(self):
        value, contract, plan = self.mixed()
        next(item for item in value["criteria"] if item["id"] == "P44-RAW-RUNS")["evidence"].append("rerun-plan.json")
        self.assertTrue(m.RULES.validate_reuse(value, contract, self.previous, plan))
        value, contract, plan = self.mixed()
        next(item for item in value["commands"] if item["id"] == "formal-dispatch-b")["output_evidence"] = "rerun-plan.json"
        self.assertTrue(m.RULES.validate_reuse(value, contract, self.previous, plan))

    def test_missing_result_or_duplicate_command_cannot_pass(self):
        value, contract, _ = self.mixed()
        next(item for item in value["criteria"] if item["id"] == "P44-ISOLATION").update(result="NOT_OBSERVED", observed=None)
        self.assertTrue(m.RULES.validate_matrix(value, contract, value["contract_sha256"]))
        value, contract, _ = self.mixed()
        value["commands"].append(copy.deepcopy(value["commands"][0]))
        self.assertTrue(m.RULES.validate_matrix(value, contract, value["contract_sha256"]))

    def test_c4_after_failure_cannot_replace_new_command_receipt(self):
        definition = next(item for item in self.contract()["commands"] if item["id"] == "formal-after")
        old = m.read(m.PARENT / "evidence/commands/formal-after.json")
        with patch.object(m, "read", return_value=old), self.assertRaisesRegex(AssertionError, "RECOVERY_COMMAND_FAILED"):
            m.new_receipt("formal-after", definition, self.original)

    def test_actual_before_and_negatives_evaluated_without_network(self):
        with patch.object(m.subprocess, "run", side_effect=AssertionError("NETWORK_OR_SUBPROCESS_FORBIDDEN")):
            for kind in ("before", "negatives"):
                result = m.verify_existing_bytes(kind, self.descriptor, self.original)
                self.assertTrue(result["ok"])
                self.assertEqual(result["platform_operations"], 0)
                self.assertEqual(result["source"], self.descriptor[kind])

    def test_actual_system_schema_is_preserved_for_all_three_roles(self):
        before = self.original.document(self.descriptor["before"])
        for role, item in before["databases"].items():
            parsed = m.database_snapshot(self.original, item, role)
            raw_schema = m.INSPECT.d1_rows(self.original, item["schema"], m.INSPECT.RESOURCES[role][0], m.INSPECT.SCHEMA_SQL)
            self.assertEqual(parsed["schema"], raw_schema)
            self.assertTrue(any(row["name"] == "_cf_KV" and "WITHOUT ROWID" in row["sql"] for row in parsed["schema"]))
            self.assertNotIn("_cf_KV", parsed["tables"])

    def test_business_without_rowid_remains_rejected(self):
        rows = [{"name": "business", "type": "table", "sql": "CREATE TABLE business(k TEXT PRIMARY KEY) WITHOUT ROWID"}]
        with patch.object(m.INSPECT, "d1_rows", return_value=rows), self.assertRaisesRegex(m.INSPECT.EvidenceError, "D1_WITHOUT_ROWID_UNSUPPORTED"):
            m.database_snapshot(self.original, {"schema": {}}, "staging")

    def test_internal_schema_change_still_fails_original_state_delta(self):
        before = {"databases": {role: {"schema": [{"name": "_cf_KV", "type": "table", "sql": "unchanged WITHOUT ROWID"}], "tables": {}}
                                for role in m.INSPECT.RESOURCES}}
        after = copy.deepcopy(before)
        after["databases"]["production"]["schema"][0]["sql"] = "changed WITHOUT ROWID"
        with self.assertRaisesRegex(m.INSPECT.EvidenceError, "D1_SCHEMA_CHANGED"):
            m.INSPECT.state_delta(before, after, {}, {})

    def test_snapshot_adapter_restores_original_after_error(self):
        original = m.INSPECT.database_snapshot
        with self.assertRaisesRegex(ValueError, "synthetic"):
            with m.compatible_snapshots():
                self.assertIs(m.INSPECT.database_snapshot, m.database_snapshot)
                raise ValueError("synthetic")
        self.assertIs(m.INSPECT.database_snapshot, original)

    def test_snapshot_page_route_and_offset_checks_retained(self):
        original = self.original.document(self.descriptor["before"])["databases"]["staging"]
        table = next(name for name, value in original["tables"].items() if value["pages"])
        item = copy.deepcopy(original)
        item["tables"][table]["pages"][0]["path"] = "/wrong-database/query"
        with self.assertRaisesRegex(m.INSPECT.EvidenceError, "HTTP_BINDING_MISMATCH"):
            m.database_snapshot(self.original, item, "staging")
        request = original["tables"][table]["pages"][0]["request"]
        document = self.original.document
        wrong = {"sql": document(request)["sql"].replace("OFFSET 0", "OFFSET 8")}
        with patch.object(self.original, "document", lambda reference: wrong if reference == request else document(reference)):
            with self.assertRaisesRegex(m.INSPECT.EvidenceError, "D1_PAGE_OFFSET_MISMATCH"):
                m.database_snapshot(self.original, original, "staging")

    def test_negative_worker_and_s3_body_codes_are_required(self):
        original = self.original.response
        for index, replacement, code in ((0, b'{"errorCode":"OTHER"}', "NEGATIVE_WORKER_CODE"),
                                          (3, b"<Error><Code>Other</Code></Error>", "NEGATIVE_S3_CODE")):
            records = self.original.document(self.descriptor["negatives"])["requests"]

            def response(record, *args):
                return replacement if record == records[index] else original(record, *args)

            with self.subTest(index=index), patch.object(self.original, "response", response), self.assertRaisesRegex(AssertionError, code):
                m.verify_existing_bytes("negatives", self.descriptor, self.original)

    def test_negative_success_status_cannot_hide_denial_body(self):
        value = self.original.document(self.descriptor["negatives"])
        value["requests"][0]["status"] = 200
        original = self.original.document
        with patch.object(self.original, "document", lambda item: value if item == self.descriptor["negatives"] else original(item)):
            with self.assertRaisesRegex(m.INSPECT.EvidenceError, "HTTP_BINDING_MISMATCH"):
                m.verify_existing_bytes("negatives", self.descriptor, self.original)

    def test_all_copy_targets_checked_before_any_write(self):
        directory = self.directory()
        source = directory / "source.bin"
        self.write(directory, "source.bin", b"source")
        self.write(directory, "present.bin", b"preserved")
        absent = directory / "must-not-exist.bin"
        with patch.object(m, "source_plan", return_value=([(source, absent), (source, directory / "present.bin")], {})):
            with self.assertRaisesRegex(AssertionError, "OUTPUT_ALREADY_EXISTS"):
                m.prepare()
        self.assertFalse(absent.exists())
        self.assertEqual((directory / "present.bin").read_bytes(), b"preserved")

    def test_reparse_and_sibling_paths_rejected_without_output(self):
        directory = self.directory()
        original = Path.lstat
        suspect = directory / "junction"

        def lstat(file, *args, **kwargs):
            if file == suspect:
                return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
            return original(file, *args, **kwargs)

        with patch.object(Path, "lstat", lstat), self.assertRaisesRegex(AssertionError, "REPARSE_PATH"):
            m.outputs_absent([suspect / "out.json"])
        with self.assertRaises(ValueError):
            m.outputs_absent([ROOT.parent / (ROOT.name + "-other/out.json")])
        self.assertFalse(suspect.exists())

    def test_old_privacy_outputs_scanned_new_self_outputs_excluded(self):
        directory = self.directory()
        sentinel = b"synthetic-private-needle"
        for name in ("privacy-result.json", "commands/formal-privacy.log", "commands/formal-privacy.json",
                     "recovery/privacy-result.json", "recovery-commands/formal-privacy.log", "recovery-commands/formal-privacy.json"):
            self.write(directory, name, sentinel)
        result = m.scan_public(directory, {directory: m.INSPECT.Context(ROOT, directory / "manifest.json")}, {sentinel})
        self.assertEqual(result["files_scanned"], 3)
        self.assertEqual(set(result["failed_paths"]), {"privacy-result.json", "commands/formal-privacy.log", "commands/formal-privacy.json"})

    def test_derived_s3_secret_and_base64_are_scanned(self):
        directory = self.directory()
        token = b"synthetic-local-token-input"
        derived = hashlib.sha256(token).hexdigest().encode()
        needles = m.secret_forms({b"other-private-fixture"}, token)
        self.write(directory, "plain.txt", derived)
        self.write(directory, "encoded.txt", base64.b64encode(derived))
        result = m.scan_public(directory, {}, needles)
        self.assertFalse(result["ok"])
        self.assertEqual(set(result["failed_paths"]), {"plain.txt", "encoded.txt"})
        self.assertNotIn(derived.decode(), json.dumps(result))

    def test_historical_gzip_context_and_wrong_sidecar_rejected(self):
        directory = self.directory()
        history = m.b.guard(directory / "p")
        sentinel = b"synthetic-decoded-secret"
        raw = json.dumps({"message": sentinel.decode()}).encode()
        wire = gzip.compress(raw)
        body = self.write(history, "wire.body", wire)
        decoded = self.write(history, "decoded.body", raw)
        envelope = {"completed": True, "method": "POST", "path": "/accounts/[ACCOUNT]/d1/database/" + m.INSPECT.RESOURCES["protected"][0] + "/query",
            "status": 200, "started": "2026-10-20T00:00:00Z", "ended": "2026-10-20T00:00:01Z",
            "response_headers": {"content-length": str(len(wire)), "content-encoding": "gzip"}, "body": body, "decoded_body": decoded}
        self.write(history, "good.http.json", envelope)
        contexts = {root: m.INSPECT.Context(ROOT, root / "manifest.json") for root in (directory, history)}
        result = m.scan_public(directory, contexts, {sentinel})
        self.assertEqual(result["decoded_d1_scanned"], 1)
        self.assertIn("p/good.http.json::decoded_body", result["failed_paths"])
        envelope["decoded_body"] = self.write(history, "wrong.body", b"wrong")
        self.write(history, "bad.http.json", envelope)
        with self.assertRaisesRegex(m.INSPECT.EvidenceError, "HTTP_DECODED_MISMATCH"):
            m.scan_public(directory, contexts, set())

    def test_three_original_history_contexts_remain_bound(self):
        contexts = m.b.privacy_contexts(m.INSPECT, self.parent, m.PARENT / "evidence")
        self.assertEqual(len(contexts), 4)
        expected = m.PARENT / "evidence/p/inputs/predecessor-before/inputs/predecessor-before"
        self.assertIs(m.b.select_privacy_context(expected / "input.body", contexts), contexts[expected])

    def test_admission_is_readonly_and_reports_exact_source_identity(self):
        output = io.StringIO()
        with patch.object(m, "ready", return_value=({"freeze_commit": "f" * 40}, None, None, None, None, None)), \
                patch.object(m, "sha", return_value="a" * 64), patch.object(m.b, "write", side_effect=AssertionError("WRITE_FORBIDDEN")), \
                contextlib.redirect_stdout(output):
            m.admit()
        result = json.loads(output.getvalue())
        self.assertEqual(result, {"schema": "p44-after-admission-v1", "ok": True, "freeze_commit": "f" * 40,
            "source_commit": m.SOURCE, "source_bundle_commit": m.BUNDLE, "contract_sha256": "a" * 64})

    def result_fixture(self, mismatched_after=False):
        directory = self.directory()
        before = {"original": "before"}
        after = {"original": "after"}
        descriptor = {"before": self.write(directory, "snapshots/before.json", before), "after_complete": []}
        after_ref = self.write(directory, "snapshots/after.json", after)
        original = {"run_a": {}, "run_b": {}, "target": {}, "artifact": {}}
        self.write(directory, "rehearsal-manifest.json", original)
        manifest = {**original, "snapshots": {"before": before, "after": {} if mismatched_after else after}}
        manifest_ref = self.write(directory, "manifest.json", manifest)
        identity = {"ok": True, "source_commit": m.SOURCE, "source_bundle_commit": m.BUNDLE, "freeze_commit": "f" * 40}
        self.write(directory, "recovery/after-result.json", {**identity, "snapshot": after_ref})
        self.write(directory, "recovery/assemble-result.json", {**identity, "manifest": manifest_ref})
        return directory, descriptor, m.INSPECT.Context(ROOT, directory / "manifest.json")

    def test_after_and_assembly_results_bind_exact_files(self):
        directory, descriptor, ctx = self.result_fixture()
        with patch.object(m, "DATA", directory):
            m.capture_results({"freeze_commit": "f" * 40}, descriptor, ctx)
        original = m.read
        for change in (lambda reference: reference.update(sha256="a" * 64), lambda reference: reference.update(path="other.json")):
            altered = original(directory / "recovery/after-result.json")
            change(altered["snapshot"])
            with patch.object(m, "DATA", directory), patch.object(m, "read", lambda file: altered if file == directory / "recovery/after-result.json" else original(file)):
                with self.assertRaisesRegex(AssertionError, "CAPTURE_RESULT_REFERENCE"):
                    m.capture_results({"freeze_commit": "f" * 40}, descriptor, ctx)

    def test_manifest_cannot_substitute_different_after_content(self):
        directory, descriptor, ctx = self.result_fixture(mismatched_after=True)
        with patch.object(m, "DATA", directory), self.assertRaisesRegex(AssertionError, "MANIFEST_AFTER_BINDING"):
            m.capture_results({"freeze_commit": "f" * 40}, descriptor, ctx)

    def test_cli_failure_does_not_echo_supplied_values(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = m.main(["SYNTHETIC_PRIVATE_VALUE"])
        self.assertEqual(code, 1)
        self.assertNotIn("SYNTHETIC_PRIVATE_VALUE", output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["error_code"], "INVALID_ARGUMENTS")

    @contextlib.contextmanager
    def admission_fixture(self):
        contract = self.contract()
        initial, plan = self.plan(contract)
        documents = {m.CONTRACT: contract, m.PACKAGE / "evidence-matrix.json": initial,
                     m.PACKAGE / "rerun-plan.json": copy.deepcopy(plan)}
        outputs = []
        for name, key in (("formal-precheck", "precheck"), ("formal-rerun-plan", "plan")):
            command, *args = m.validation_commands()[key].split(" ")
            output = {"path": "recovery-commands/" + name + ".log", "size_bytes": 2, "sha256": "b" * 64}
            outputs.append(copy.deepcopy(output))
            documents[m.DATA / "recovery-commands" / (name + ".json")] = {"label": name, "command": command, "args": args,
                "cwd": str(ROOT), "process_closed": True, "exitCode": 0, "signal": None, "output": output}

        def checked_output(reference):
            if reference not in outputs:
                raise AssertionError("RECEIPT_OUTPUT_CHANGED")
            return b"ok"

        ctx = SimpleNamespace(read=checked_output)
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(m, "verify_import", return_value=(self.descriptor, self.parent, self.previous, ctx)))
            stack.enter_context(patch.object(m, "read", side_effect=lambda path: copy.deepcopy(documents[path])))
            stack.enter_context(patch.object(m, "sha", return_value=initial["contract_sha256"].lower()))
            stack.enter_context(patch.object(m, "computed_plan", return_value=plan))
            stack.enter_context(patch.object(m.b, "git", side_effect=lambda *args: FUTURE_TREE if args == ("rev-parse", "HEAD^{tree}") else "f" * 40))
            dirty = stack.enter_context(patch.object(m.RULES, "validate_execution_worktree", return_value=[]))
            stack.enter_context(patch.object(m.RULES, "validate_external_inputs", return_value=[]))
            stack.enter_context(patch.object(m.b, "write", side_effect=AssertionError("WRITE_FORBIDDEN")))
            yield documents, dirty

    def test_admission_rejects_forged_or_unclosed_precheck(self):
        with self.admission_fixture() as (documents, _):
            m.ready()
            receipt = documents[m.DATA / "recovery-commands/formal-precheck.json"]
            receipt["process_closed"] = False
            with self.assertRaises(AssertionError):
                m.ready()
            receipt["process_closed"] = True
            receipt["output"]["sha256"] = "c" * 64
            with self.assertRaisesRegex(AssertionError, "RECEIPT_OUTPUT_CHANGED"):
                m.ready()

    def test_admission_rejects_plan_or_initial_hash_change(self):
        with self.admission_fixture() as (documents, _):
            documents[m.PACKAGE / "rerun-plan.json"]["required_commands"].pop()
            with self.assertRaisesRegex(AssertionError, "RERUN_PLAN_CHANGED"):
                m.ready()
        with self.admission_fixture() as (documents, _):
            documents[m.PACKAGE / "evidence-matrix.json"]["contract_sha256"] = "d" * 64
            with self.assertRaises(AssertionError):
                m.ready()

    def test_admission_rejects_dirty_frozen_inputs(self):
        with self.admission_fixture() as (_, dirty):
            dirty.return_value = ["dirty Validation input"]
            with self.assertRaisesRegex(AssertionError, "DIRTY_RECOVERY_INPUTS"):
                m.ready()

    def test_import_rejects_nonprefix_file_byte_tampering(self):
        original_read = Path.read_bytes
        target = m.PARENT / "evidence/inputs/host.json"
        ctx_original = self.original
        descriptor = self.descriptor

        class CopiedContext:
            def read(self, reference):
                if reference == descriptor["source_contract"]:
                    return original_read(m.PARENT_CONTRACT)
                if reference == descriptor["source_matrix"]:
                    return original_read(m.PARENT_MATRIX)
                return ctx_original.read(reference)

            def document(self, reference):
                return m.INSPECT.json_bytes(self.read(reference))

        with patch.object(m, "read", return_value=descriptor), patch.object(m.INSPECT, "Context", return_value=CopiedContext()), \
                patch.object(Path, "read_bytes", lambda path: b"tampered-nonprefix" if path == target else original_read(path)):
            with self.assertRaisesRegex(m.INSPECT.EvidenceError, "FILE_DIGEST_MISMATCH"):
                m.verify_import()

    def test_existing_formal_contract_is_allowed_but_snapshot_is_immutable(self):
        directory = self.directory()
        self.write(directory, "existing.contract.json", {"status": "FROZEN"})
        self.write(directory, "existing/evidence/original.json", {"value": "preserved"})
        with patch.object(m, "CONTRACT", directory / "existing.contract.json"), patch.object(m, "PACKAGE", directory / "existing"):
            snapshot = formal_snapshot()
            self.assertTrue(snapshot["contract_exists"])
            self.assertTrue(snapshot["package_exists"])
            self.assertEqual(formal_snapshot(), snapshot)


if __name__ == "__main__":
    unittest.main(verbosity=2)
