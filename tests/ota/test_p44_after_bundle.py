"""Bounded C6 adapter tests: real C5/C4 reads, synthetic writes, zero network."""
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
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).absolute().parents[2]
SPEC = importlib.util.spec_from_file_location("p44_after_bundle", ROOT / "Tools/ota/p44-after-bundle.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)
DEV = ROOT / ".cache/p44-v6-development/python"
NODE_INTEROP = None
if "--node-fixture" in sys.argv:
    index = sys.argv.index("--node-fixture")
    NODE_INTEROP = m.b.guard(ROOT / sys.argv[index + 1])
    assert any(NODE_INTEROP.is_relative_to(ROOT / ".cache" / name) for name in ("p44-v6-development", "p44-v7-development"))
    if NODE_INTEROP.is_relative_to(ROOT / ".cache/p44-v7-development"):
        DEV = ROOT / ".cache/p44-v7-development/python"
    del sys.argv[index:index + 2]
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
        cls.sources = m.reuse_sources()
        cls.origin = cls.sources[m.SOURCE_MATRIX_HASH]
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
        cls.interop = {}
        cls.private_originals = {}
        if NODE_INTEROP is not None:
            for name in ("interop", "interop-resumed", "native-transport", "interop-body", "successor-cli"):
                if not (NODE_INTEROP / (name + ".json")).exists():
                    continue
                packet = m.read(NODE_INTEROP / (name + ".json"))
                assert packet["scope"] == "OFFLINE_CROSS_LANGUAGE_SYNTHETIC" and packet["network_requests"] == 0
                for source in packet["source"]:
                    raw = m.b.guard(ROOT / source["path"]).read_bytes()
                    assert len(raw) == source["size_bytes"] and m.b.sha(raw) == source["sha256"], "STALE_NODE_FIXTURE"
                directory = m.b.guard(cls.batch / name)
                names = [entry["path"] for entry in packet["files"]]
                assert len(names) == len(set(names)), "DUPLICATE_NODE_FIXTURE_FILE"
                for entry in packet["files"]:
                    target = m.b.guard(directory / entry["path"])
                    target.relative_to(directory)
                    raw = base64.b64decode(entry["base64"], validate=True)
                    assert len(raw) == entry["size_bytes"] and m.b.sha(raw) == entry["sha256"], "NODE_FIXTURE_BYTES"
                    m.b.write(target, raw)
                for entry in packet.get("private_files", []):
                    raw = base64.b64decode(entry["base64"], validate=True)
                    assert len(raw) == entry["size_bytes"] and m.b.sha(raw) == entry["sha256"], "PRIVATE_FIXTURE_BYTES"
                    assert entry["path"] not in cls.private_originals, "DUPLICATE_PRIVATE_FIXTURE"
                    cls.private_originals[entry["path"]] = raw
                cls.interop[name] = (directory, packet.get("contract"), packet.get("descriptor"), packet)
        print(json.dumps({"development_only": True, "fixture_root": str(cls.batch),
                          "c5_source_files_verified": len(cls.descriptor["files"]), "network_requests": 0,
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
        old_commands = {item["id"]: item for item in self.origin["matrix"]["commands"]}
        commands = []
        for item in contract["commands"]:
            if item["id"] in m.EXECUTED:
                name = "evidence/" + m.COMMANDS + "/" + item["id"]
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

    def test_actual_c5_inventory_is_bound_to_b5_and_all_bytes(self):
        self.assertEqual(set(self.descriptor), m.DESCRIPTOR_KEYS)
        self.assertEqual(self.descriptor["schema"], "p44-after-recovery-v2")
        self.assertEqual(len(self.descriptor["files"]), 1185)
        self.assertEqual(len(self.copy_plan), len(self.descriptor["files"]) + 2)
        self.assertEqual(len({target for _, target in self.copy_plan}), len(self.copy_plan))
        self.assertEqual(self.descriptor["offline_identity"], m.OFFLINE_IDENTITY)
        for key, value in m.lineage_fields().items():
            self.assertEqual(self.descriptor[key], value)
        self.assertEqual(self.descriptor["source_index_commit"], m.SOURCE_INDEX)
        self.assertEqual(self.parent["freeze_commit"], m.PREDECESSOR_COMMIT)
        self.assertEqual(self.origin["contract"]["freeze_commit"], m.SOURCE_COMMIT)
        copied_sources = {target.relative_to(m.DATA).as_posix(): source for source, target in self.copy_plan}
        self.assertEqual(copied_sources["recovery/c4.contract.json"], m.PARENT / "evidence/recovery/c4.contract.json")
        self.assertEqual(copied_sources["recovery/c4.final-evidence-matrix.json"], m.PARENT / "evidence/recovery/c4.final-evidence-matrix.json")
        self.assertEqual(copied_sources[m.RECOVERY + "/c5.contract.json"], m.PARENT_CONTRACT)
        self.assertEqual(copied_sources[m.RECOVERY + "/c5.final-evidence-matrix.json"], m.PARENT_MATRIX)
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

    def test_missing_or_invalid_c4_source_map_fails_closed(self):
        with patch.object(m, "reuse_sources", return_value={}):
            with self.assertRaisesRegex(ValueError, "missing original EXECUTED bundle"):
                self.plan(self.contract())
        for field, value in (("contract_sha256", "0" * 64), ("original_execution", "REUSED")):
            sources = copy.deepcopy(self.sources)
            source = sources[m.SOURCE_MATRIX_HASH]
            if field == "original_execution":
                for item in source["matrix"]["criteria"]:
                    if item["id"] in m.REUSED:
                        item["execution"] = value
            else:
                source[field] = value
            with self.subTest(field=field), patch.object(m, "reuse_sources", return_value=sources):
                with self.assertRaisesRegex(ValueError, "invalid original EXECUTED PASS binding"):
                    self.plan(self.contract())

    def test_skipping_c5_predecessor_is_rejected(self):
        contract = self.contract()
        initial = m.initial_matrix(contract, "a" * 64)
        with self.assertRaisesRegex(ValueError, "next contract version"):
            m.computed_plan(contract, initial, self.origin["contract"], self.origin["matrix"], digest="a" * 64)

    def test_actual_c5_reuse_history_resolves_only_to_c4(self):
        previous = {"contract": self.parent, "matrix": self.previous, "contract_sha256": m.PARENT_HASH,
                    "matrix_sha256": m.PARENT_MATRIX_HASH, "bundle_directory": m.PARENT}
        self.assertFalse(m.RULES._validate_reuse_history(previous, self.sources, ROOT, set(), set()))
        self.assertTrue(m.RULES._validate_reuse_history(previous, {}, ROOT, set(), set()))
        for item in self.previous["criteria"]:
            if item["id"] in m.REUSED:
                self.assertEqual(item["execution"], "REUSED")
                self.assertEqual(item["origin_contract_sha256"], m.SOURCE_HASH)
                self.assertEqual(item["origin_matrix_sha256"], m.SOURCE_MATRIX_HASH)
                original = next(row for row in self.origin["matrix"]["criteria"] if row["id"] == item["id"])
                self.assertEqual((original["execution"], original["result"]), ("EXECUTED", "PASS"))
        altered = copy.deepcopy(previous)
        next(item for item in altered["matrix"]["criteria"] if item["id"] == "P44-RAW-RUNS").update(
            execution="EXECUTED", reused_from_round=None, origin_contract_sha256=None, origin_matrix_sha256=None)
        self.assertTrue(m.RULES._validate_reuse_history(altered, self.sources, ROOT, set(), set()))

    def test_validation_commands_always_bind_c5_and_explicit_c4_source(self):
        for key, command in m.validation_commands().items():
            args = command.split()
            with self.subTest(mode=key):
                self.assertEqual(args[args.index("--previous-contract") + 1], m.PARENT_CONTRACT.relative_to(ROOT).as_posix())
                self.assertEqual(args[args.index("--previous-matrix") + 1], m.PARENT_MATRIX.relative_to(ROOT).as_posix())
                self.assertEqual(args.count("--reuse-source"), 1)
                offset = args.index("--reuse-source")
                self.assertEqual(args[offset + 1:offset + 3], [m.SOURCE_CONTRACT.relative_to(ROOT).as_posix(),
                                                              m.SOURCE_MATRIX.relative_to(ROOT).as_posix()])

    def successor_module(self):
        spec = importlib.util.spec_from_file_location("p44_successor_v7", ROOT / m.PYTHON)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.configure_package("docs/acceptance-contracts/P4-4-v7.package.json")
        return module

    def test_successor_v7_reuses_actual_c5_and_keeps_c4_as_origin(self):
        next_module = self.successor_module()
        sources = next_module.reuse_sources()
        by_version = {source["contract"]["version"]: source for source in sources.values()}
        self.assertEqual(set(by_version), {4, 5})
        self.assertEqual(by_version[4]["matrix_sha256"], next_module.SOURCE_MATRIX_HASH)
        self.assertEqual(by_version[4]["contract"]["freeze_commit"], next_module.SOURCE_COMMIT)
        self.assertEqual(by_version[5]["matrix"]["previous_matrix_sha256"], next_module.SOURCE_MATRIX_HASH)
        self.assertEqual(by_version[5]["contract"]["freeze_commit"], next_module.LEGACY_PREDECESSOR[0])
        parent = {"contract": m.read(next_module.PARENT_CONTRACT), "matrix": m.read(next_module.PARENT_MATRIX),
                  "contract_sha256": next_module.PARENT_HASH, "matrix_sha256": next_module.PARENT_MATRIX_HASH,
                  "bundle_directory": next_module.PARENT}
        self.assertFalse(next_module.RULES._validate_reuse_history(parent, sources, ROOT, set(), set()))
        missing = {key: value for key, value in sources.items() if value["contract"]["version"] != 5}
        errors = next_module.RULES._validate_reuse_history(parent, missing, ROOT, set(), set())
        self.assertEqual(len(errors), 1)
        self.assertIn("missing previous round", errors[0])
        plan, descriptor = next_module.source_plan()
        self.assertEqual(len(plan), 1416)
        self.assertEqual(len(descriptor["files"]) + 2, len(plan))

    def test_successor_validator_arguments_include_c5_in_python_and_node(self):
        next_module = self.successor_module()
        commands = next_module.validation_commands()
        expected = [
            ["docs/acceptance-contracts/P4-4-v4.contract.json", "docs/acceptance-contracts/P4-4-v4/final-evidence-matrix.json"],
            ["docs/acceptance-contracts/P4-4-v5.contract.json", "docs/acceptance-contracts/P4-4-v5/final-evidence-matrix.json"]]
        for key, command in commands.items():
            args = command.split()
            with self.subTest(mode=key):
                self.assertEqual(args[args.index("--previous-contract") + 1], "docs/acceptance-contracts/P4-4-v6.contract.json")
                self.assertEqual(args[args.index("--previous-matrix") + 1], "docs/acceptance-contracts/P4-4-v6/final-evidence-matrix.json")
                pairs = [args[index + 1:index + 3] for index, value in enumerate(args) if value == "--reuse-source"]
                self.assertEqual(pairs, expected)
        script = ("const path=require('node:path');"
                  "const r=require(path.join(process.cwd(),'Tools/ota/p44-after-recovery.cjs'));"
                  "r.configurePackage('docs/acceptance-contracts/P4-4-v7.package.json');"
                  "process.stdout.write(JSON.stringify(r.validatorArgs('formal-precheck')));")
        result = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), commands["precheck"].split()[1:])

    def test_successor_reuse_source_rejects_missing_tampered_and_wrong_lineage(self):
        next_module = self.successor_module()
        sources = next_module.reuse_sources()
        c5 = next(source for source in sources.values() if source["contract"]["version"] == 5)
        with self.assertRaisesRegex(AssertionError, "REUSE_SOURCE_MISSING"):
            next_module._find_reuse_source("0" * 64)
        with self.assertRaisesRegex(AssertionError, "REUSE_SOURCE_HASH"):
            next_module._load_reuse_source(next_module.PARENT, "0" * 64)

        workspace = self.directory()
        wrong_name = workspace / "P4-4-v9"
        wrong_name.mkdir()
        real_c5 = ROOT / "docs/acceptance-contracts/P4-4-v5"
        for source, target in ((real_c5.with_suffix(".contract.json"), wrong_name.with_suffix(".contract.json")),
                               (real_c5 / "final-evidence-matrix.json", wrong_name / "final-evidence-matrix.json")):
            m.b.write(target, m.b.guard(source).read_bytes())
        with self.assertRaisesRegex(AssertionError, "REUSE_SOURCE_IDENTITY"):
            next_module._load_reuse_source(wrong_name, c5["matrix_sha256"])

        tampered = workspace / "P4-4-v5"
        tampered.mkdir()
        m.b.write(tampered / "final-evidence-matrix.json",
                  m.b.guard(real_c5 / "final-evidence-matrix.json").read_bytes() + b"\n")
        m.b.write(tampered.with_suffix(".contract.json"), m.b.guard(real_c5.with_suffix(".contract.json")).read_bytes())
        with self.assertRaisesRegex(AssertionError, "REUSE_SOURCE_HASH"):
            next_module._load_reuse_source(tampered, c5["matrix_sha256"])

        original = next_module._load_reuse_source

        def wrong_lineage(package, expected):
            value = original(package, expected)
            if value["contract"]["version"] == 5:
                value = copy.deepcopy(value)
                value["contract"]["version"] = 6
            return value

        with patch.object(next_module, "_load_reuse_source", side_effect=wrong_lineage):
            with self.assertRaisesRegex(AssertionError, "REUSE_SOURCE_LINEAGE"):
                next_module.reuse_sources()

        def cyclic(package, expected):
            value = original(package, expected)
            if value["contract"]["version"] == 5:
                value = copy.deepcopy(value)
                value["matrix"]["previous_matrix_sha256"] = value["matrix_sha256"]
            return value

        with patch.object(next_module, "_load_reuse_source", side_effect=cyclic):
            with self.assertRaisesRegex(AssertionError, "REUSE_SOURCE_CYCLE"):
                next_module.reuse_sources()

    def test_c6_paths_and_fixture_id_do_not_collide_with_c4_or_c5(self):
        contract = self.contract()
        self.assertEqual((contract["contract_id"], contract["version"]), ("P4-4-v6", 6))
        ids = [item["id"] for item in contract["external_inputs"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids.count("after-recovery"), 1)
        self.assertEqual(ids.count(m.FIXTURE_ID), 1)
        for previous in self.parent["external_inputs"]:
            self.assertEqual(previous, next(item for item in contract["external_inputs"] if item["id"] == previous["id"]))
        inherited = {item["path"] for item in self.descriptor["files"]}
        outputs = {m.FIXTURE, "snapshots/after.json", "manifest.json", "approvals-result.json", "states-result.json"}
        outputs.update(m.RECOVERY + "/" + name + "-result.json" for name in ("history", "before", "negatives", "after", "assemble", "privacy"))
        outputs.update(m.COMMANDS + "/" + name + suffix for name in m.EXECUTED | {"formal-precheck", "formal-rerun-plan"}
                       for suffix in (".json", ".log"))
        self.assertFalse(inherited & outputs)

    def test_c5_private_failure_retains_unknown_http_receive_stage(self):
        reference = self.descriptor["private_verify_failure"]
        self.assertEqual(reference, next(item for item in self.descriptor["files"] if item["path"] == "recovery/private-verify-failure.json"))
        self.assertEqual(self.original.document(reference), {"ok": False, "started": "2026-10-20T04:54:35.600Z",
            "ended": "2026-10-20T04:54:40.458Z", "attempts": 1, "error_code": "ECONNRESET"})

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
        self.assertEqual(contract["implementation_ref"], m.SOURCE_COMMIT)
        self.assertNotEqual(contract["freeze_commit"], m.SOURCE_COMMIT)
        self.assertEqual(self.original.document(self.descriptor["target"])["commitSha"], m.SOURCE_COMMIT)

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
                self.assertEqual(item["origin_contract_sha256"], m.SOURCE_HASH)
                self.assertEqual(item["origin_matrix_sha256"], m.SOURCE_MATRIX_HASH)
        self.assertFalse(m.RULES.validate_reuse(value, contract, self.previous, plan, self.sources))

    def test_reused_evidence_and_command_tampering_rejected(self):
        value, contract, plan = self.mixed()
        next(item for item in value["criteria"] if item["id"] == "P44-RAW-RUNS")["evidence"].append("rerun-plan.json")
        self.assertTrue(m.RULES.validate_reuse(value, contract, self.previous, plan, self.sources))
        value, contract, plan = self.mixed()
        next(item for item in value["commands"] if item["id"] == "formal-dispatch-b")["output_evidence"] = "rerun-plan.json"
        self.assertTrue(m.RULES.validate_reuse(value, contract, self.previous, plan, self.sources))

    def test_reused_c4_pass_cannot_be_laundered_to_new_execution(self):
        value, contract, plan = self.mixed()
        next(item for item in value["criteria"] if item["id"] == "P44-RAW-RUNS").update(
            execution="EXECUTED", reused_from_round=None, origin_contract_sha256=None, origin_matrix_sha256=None)
        self.assertTrue(m.RULES.validate_planned_execution(value, contract, plan))

    def test_admission_rejects_non_c4_reuse_origins(self):
        _, plan = self.plan(self.contract())
        plan["reuse_origins"]["P44-RAW-RUNS"]["matrix_sha256"] = m.PARENT_MATRIX_HASH
        with self.assertRaisesRegex(AssertionError, "ORIGIN_PLAN_DRIFT"):
            m.admitted_plan(plan)
        plan["reuse_origins"].clear()
        with self.assertRaisesRegex(AssertionError, "ORIGIN_PLAN_DRIFT"):
            m.admitted_plan(plan)

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

    def test_duplicate_copy_target_is_rejected_before_any_write(self):
        directory = self.directory()
        source = directory / "source.bin"
        self.write(directory, source.name, b"source")
        absent = directory / "must-not-exist.bin"
        with patch.object(m, "source_plan", return_value=([(source, absent), (source, absent)], {})), \
                patch.object(m.b, "write", side_effect=AssertionError("WRITE_FORBIDDEN")) as writer:
            with self.assertRaisesRegex(AssertionError, "DUPLICATE_OUTPUT_TARGET"):
                m.prepare()
        writer.assert_not_called()
        self.assertFalse(absent.exists())

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
                     "recovery/privacy-result.json", "recovery-commands/formal-privacy.log", "recovery-commands/formal-privacy.json",
                     m.RECOVERY + "/privacy-result.json", m.COMMANDS + "/formal-privacy.log", m.COMMANDS + "/formal-privacy.json"):
            self.write(directory, name, sentinel)
        result = m.scan_public(directory, {directory: m.INSPECT.Context(ROOT, directory / "manifest.json")}, {sentinel})
        self.assertEqual(result["files_scanned"], 6)
        self.assertEqual(set(result["failed_paths"]), {"privacy-result.json", "commands/formal-privacy.log", "commands/formal-privacy.json",
            "recovery/privacy-result.json", "recovery-commands/formal-privacy.log", "recovery-commands/formal-privacy.json"})

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

    def synthetic_identity(self, document=None):
        identifier = "1" * 32
        raw = json.dumps(document if document is not None else {"body": {"result": {"id": identifier}}}).encode()
        expected = {**m.OFFLINE_IDENTITY, "size_bytes": len(raw), "sha256": m.b.sha(raw), "id_sha256": m.b.sha(identifier.encode())}
        return identifier, raw, expected

    def test_offline_identity_reads_fixed_file_with_no_subprocess(self):
        identifier, raw, expected = self.synthetic_identity()
        target = ROOT.parents[1] / expected["source_path"]
        requested = []

        def read(path):
            self.assertEqual(path, target)
            requested.append(path)
            return raw

        with patch.object(m, "OFFLINE_IDENTITY", expected), patch.object(Path, "read_bytes", read), \
                patch.object(m.subprocess, "run", side_effect=AssertionError("SUBPROCESS_FORBIDDEN")):
            self.assertEqual(m.offline_identifier(), identifier)
        self.assertEqual(requested, [target])

    def test_offline_identity_failures_are_redacted_without_fallback(self):
        identifier, raw, expected = self.synthetic_identity()
        cases = [(raw + b" ", expected, "OFFLINE_IDENTITY_BYTES"),
                 (raw.replace(identifier.encode(), b"2" * 32), expected, "OFFLINE_IDENTITY_BYTES"),
                 (raw, {**expected, "id_sha256": "0" * 64}, "OFFLINE_IDENTITY_ID")]
        for document, code in (({"body": {"result": {"other": identifier}}}, "OFFLINE_IDENTITY_POINTER"),
                               ({"body": None}, "OFFLINE_IDENTITY_POINTER"),
                               ({"body": {"result": {"id": "A" * 32}}}, "OFFLINE_IDENTITY_FORMAT"),
                               ({"body": {"result": {"id": 123}}}, "OFFLINE_IDENTITY_FORMAT"),
                               ({"body": {"result": {"id": "1" * 31}}}, "OFFLINE_IDENTITY_FORMAT")):
            _, altered, pin = self.synthetic_identity(document)
            cases.append((altered, pin, code))
        for number, (content, pin, expected_code) in enumerate(cases):
            output = io.StringIO()
            with self.subTest(case=number), patch.object(m, "OFFLINE_IDENTITY", pin), \
                    patch.object(m.subprocess, "run", side_effect=AssertionError("SUBPROCESS_FORBIDDEN")), \
                    patch.object(m, "privacy", side_effect=lambda: m.offline_id_bytes(content)), contextlib.redirect_stdout(output):
                self.assertEqual(m.main(["privacy"]), 1)
            self.assertEqual(json.loads(output.getvalue()), {"ok": False, "error_code": expected_code})
            self.assertNotIn(identifier, output.getvalue())

    def test_missing_offline_identity_cannot_fall_back_to_verify(self):
        requested = []

        def missing(path):
            requested.append(path)
            raise FileNotFoundError(2, "No such file or directory", str(path))

        output = io.StringIO()
        with patch.object(Path, "read_bytes", missing), patch.object(m, "privacy", side_effect=m.offline_identifier), \
                patch.object(m.subprocess, "run", side_effect=AssertionError("SUBPROCESS_FORBIDDEN")), contextlib.redirect_stdout(output):
            self.assertEqual(m.main(["privacy"]), 1)
        self.assertEqual(requested, [ROOT.parents[1] / m.OFFLINE_IDENTITY["source_path"]])
        self.assertEqual(json.loads(output.getvalue()), {"ok": False, "error_code": "P44_AFTER_FAILED"})
        self.assertNotIn(str(requested[0]), output.getvalue())

    def test_known_needles_expands_offline_id_before_base64(self):
        identifier, token = "1" * 32, b"synthetic-local-token-input"

        def inputs(path):
            if path.name == "token.txt":
                return token
            if path.name == "p41-ci-token.txt":
                return b"synthetic-ci-token-input"
            if path.name == "03.json":
                return json.dumps({"result": [{"id": "2" * 32}]}).encode()
            return b'{"cloudflare_api_token":"synthetic-other-secret"}'

        auth = SimpleNamespace(returncode=0, stdout=b"synthetic-github-token")
        with patch.object(Path, "read_bytes", inputs), patch.object(m, "offline_identifier", return_value=identifier), \
                patch.object(m.subprocess, "run", return_value=auth):
            needles = m.known_needles()
        derived = hashlib.sha256(token).hexdigest().encode()
        for value in (identifier.encode(), token, derived):
            self.assertIn(value, needles)
            self.assertIn(base64.b64encode(value), needles)

    def test_raw_id_derived_key_and_encoded_forms_never_escape_privacy_results(self):
        directory = self.directory()
        identifier, token = b"1" * 32, b"synthetic-local-token-input"
        derived = hashlib.sha256(token).hexdigest().encode()
        values = {"id.txt": identifier, "token.txt": token, "derived.txt": derived}
        values.update({"encoded-" + name: base64.b64encode(value) for name, value in list(values.items())})
        for name, value in values.items():
            self.write(directory, name, value)
        result = m.scan_public(directory, {}, m.secret_forms({identifier}, token))
        self.assertFalse(result["ok"])
        self.assertEqual(result["files_scanned"], len(values))
        self.assertEqual(set(result["failed_paths"]), set(values))
        for value in values.values():
            self.assertNotIn(value.decode(), json.dumps(result))

    def test_clean_privacy_result_preserves_complete_hash_mapping(self):
        directory = self.directory()
        contents = {"first.txt": b"non-secret original", "nested/second.txt": b"different non-secret original"}
        for name, value in contents.items():
            self.write(directory, name, value)
        result = m.scan_public(directory, {}, m.secret_forms({b"1" * 32}, b"synthetic-local-token-input"))
        self.assertTrue(result["ok"])
        self.assertEqual(result["files_scanned"], len(contents))
        self.assertEqual(result["failed_paths"], [])
        self.assertEqual(result["file_hashes"], {name: m.b.sha(value) for name, value in contents.items()})

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
        contexts = m.b.privacy_contexts(m.INSPECT, self.origin["contract"], m.PARENT / "evidence")
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
            **m.lineage_fields(), "contract_sha256": "a" * 64})

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
        identity = {"ok": True, **m.lineage_fields(), "freeze_commit": "f" * 40}
        self.write(directory, m.RECOVERY + "/after-result.json", {**identity, "snapshot": after_ref})
        self.write(directory, m.RECOVERY + "/assemble-result.json", {**identity, "manifest": manifest_ref})
        return directory, descriptor, m.INSPECT.Context(ROOT, directory / "manifest.json")

    def test_after_and_assembly_results_bind_exact_files(self):
        directory, descriptor, ctx = self.result_fixture()
        with patch.object(m, "DATA", directory), patch.object(m, "verify_after_recovery", return_value={"total_complete": 0}) as verifier:
            m.capture_results({"freeze_commit": "f" * 40}, descriptor, ctx)
            verifier.assert_called_once()
        original = m.read
        for change in (lambda reference: reference.update(sha256="a" * 64), lambda reference: reference.update(path="other.json")):
            altered = original(directory / m.RECOVERY / "after-result.json")
            change(altered["snapshot"])
            with patch.object(m, "DATA", directory), patch.object(m, "read", lambda file: altered if file == directory / m.RECOVERY / "after-result.json" else original(file)):
                with self.assertRaisesRegex(AssertionError, "CAPTURE_RESULT_REFERENCE"):
                    m.capture_results({"freeze_commit": "f" * 40}, descriptor, ctx)

    def test_manifest_cannot_substitute_different_after_content(self):
        directory, descriptor, ctx = self.result_fixture(mismatched_after=True)
        with patch.object(m, "DATA", directory), self.assertRaisesRegex(AssertionError, "MANIFEST_AFTER_BINDING"):
            m.capture_results({"freeze_commit": "f" * 40}, descriptor, ctx)

    def node_interop(self, name="interop"):
        self.assertIn(name, self.interop, "NODE_AFTER_ASSEMBLE_FIXTURE_REQUIRED: pass --node-fixture")
        directory, contract, descriptor, _ = self.interop[name]
        return (directory, contract, descriptor,
                m.INSPECT.Context(ROOT, directory / "manifest.json"))

    @contextlib.contextmanager
    def synthetic_git(self):
        # Only Git resolution is synthetic. Actual producer bytes and the entire
        # evidence parser/hash/lineage validation remain live in these tests.
        node_bytes = (ROOT / m.NODE).read_bytes()
        actual_head = m.b.git("rev-parse", "HEAD")

        def git(*args):
            self.assertIn(args, [("merge-base", "--is-ancestor", "a" * 40, "HEAD"),
                                 ("merge-base", "--is-ancestor", actual_head, "HEAD")])
            return ""

        def git_bytes(*args):
            self.assertEqual(args, ("show", "a" * 40 + ":" + m.NODE))
            return node_bytes

        with patch.object(m.b, "git", git), patch.object(m.b, "git_bytes", git_bytes), \
                patch.object(m, "_private_bytes", side_effect=lambda name: self.private_originals[name]):
            yield

    def test_actual_node_after_assemble_outputs_satisfy_python_contract(self):
        directory, contract, descriptor, ctx = self.node_interop()
        before = {file.relative_to(directory).as_posix(): m.sha(file) for file in directory.rglob("*") if file.is_file()}
        self.assertEqual(contract["freeze_commit"], "a" * 40)
        self.assertEqual(len(descriptor["after_complete"]), 31)
        with self.synthetic_git(), patch.object(m, "DATA", directory), patch.object(m.subprocess, "run", side_effect=AssertionError("SUBPROCESS_FORBIDDEN")), \
                patch.object(m.b, "write", side_effect=AssertionError("WRITE_FORBIDDEN")):
            result = m.capture_results(contract, descriptor, ctx)
        self.assertEqual(result["c4_complete"], 31)
        self.assertEqual(result["c6_complete"], 39)
        self.assertEqual(result["total_complete"], 142)
        self.assertEqual(result["new_reads"], 72)
        self.assertEqual(before, {file.relative_to(directory).as_posix(): m.sha(file)
                                  for file in directory.rglob("*") if file.is_file()})
        print(json.dumps({"node_python_interop": True, "fixture": directory.relative_to(ROOT).as_posix(),
                          "verified_files": len(before), "result": result}), flush=True)

    def test_repeated_disconnect_node_outputs_satisfy_python_contract(self):
        directory, contract, descriptor, ctx = self.node_interop("interop-resumed")
        with self.synthetic_git(), patch.object(m, "DATA", directory):
            result = m.capture_results(contract, descriptor, ctx)
        self.assertEqual(result["attempts"], 4)
        self.assertEqual(result["total_complete"], 142)
        self.assertEqual(result["new_reads"], 69)

    def test_wrong_tool_bytes_still_rejected_in_synthetic_interop(self):
        directory, contract, descriptor, ctx = self.node_interop()
        with self.synthetic_git(), patch.object(m, "DATA", directory), patch.object(m.b, "git_bytes", return_value=b"wrong tool"), \
                self.assertRaisesRegex(AssertionError, "AFTER_ATTEMPT_TOOL"):
            m.capture_results(contract, descriptor, ctx)

    def test_snapshot_dictionary_order_does_not_change_capture_order(self):
        directory, _, _, ctx = self.node_interop()
        snapshot = m.read(directory / "snapshots/after.json")
        wanted = list(m._plan_records(ctx, snapshot))
        for item in snapshot["databases"].values():
            item["tables"] = dict(reversed(list(item["tables"].items())))
        self.assertEqual(list(m._plan_records(ctx, snapshot)), wanted)

    def test_configuration_summaries_are_bound_to_raw_pages_and_environment(self):
        directory, _, descriptor, ctx = self.node_interop()
        after = m.read(directory / "snapshots/after.json")["protected_configuration"]
        before = ctx.document(descriptor["before"])["protected_configuration"]
        m._verify_configuration(ctx, after, before)
        for mutation in ("values", "rules", "route", "missing-page"):
            altered = copy.deepcopy(after)
            item = altered["production"]
            if mutation == "values":
                item["values"]["DECLARED_BUT_ABSENT"] = "not-in-original-response"
            elif mutation == "rules":
                item["rules"] = [{"name": "unapproved", "type": "branch"}]
            elif mutation == "route":
                item["variables"][0]["path"] = item["variables"][0]["path"].replace("firmware-production", "firmware-rehearsal")
            else:
                item["variables"] = []
            with self.subTest(mutation=mutation), self.assertRaises((AssertionError, m.INSPECT.EvidenceError)):
                m._verify_configuration(ctx, altered, before)

    def test_native_retry_reservations_preserve_actual_retry_time_and_failures(self):
        directory, _, _, ctx = self.node_interop("native-transport")
        for name, completed, failures in (("native-success", 1, 1), ("native-failed", 0, 1)):
            source = m._after_source(ctx, directory / name, 0, m.INSPECT.timestamp("2026-10-19T00:00:00Z"), False)
            self.assertEqual(len(source["complete"]), completed)
            self.assertEqual(len(source["failures"]), failures)
            record = ctx.document(source["record_refs"][0])
            self.assertEqual(record["request_attempts"], 2)
            self.assertEqual(len(record["request_failures"]), 1 if completed else 2)

    def test_post_response_disconnects_close_reload_and_interoperate(self):
        directory, contract, descriptor, ctx = self.node_interop("interop-body")
        with self.synthetic_git(), patch.object(m, "DATA", directory):
            result = m.capture_results(contract, descriptor, ctx)
        self.assertEqual(result["attempts"], 7)
        self.assertEqual(result["total_complete"], 142)
        self.assertEqual(result["new_reads"], 72)
        for number in range(2, 7):
            stem = m.TAIL + "/attempt-" + str(number) + "/"
            attempt = m.read(directory / stem / "attempt-result.json")
            self.assertFalse(attempt["ok"])
            self.assertEqual(attempt["complete_labels"], [])
            record = ctx.document(attempt["new_reads"][0])
            self.assertFalse(record["completed"])
            self.assertEqual(record["status"], 200)
            self.assertEqual(len(record["request_failures"]), record["request_attempts"] - 1)
            self.assertIn(attempt["new_reads"][0], attempt["failures"])

    def body_fixture(self, number):
        directory, _, _, ctx = self.node_interop("interop-body")
        relative = m.TAIL + "/attempt-" + str(number) + "/"
        attempt = m.read(directory / relative / "attempt-result.json")
        label = attempt["failure_labels"][0]
        return directory, ctx, relative, label, ctx.document(attempt["new_reads"][0])

    def test_partial_body_metadata_and_storage_paths_are_strict(self):
        _, ctx, relative, label, record = self.body_fixture(2)
        m._partial_body(ctx, relative, label, record)
        for change in ({"partial_body_sha256": "0" * 64}, {"partial_body_size_bytes": record["partial_body_size_bytes"] + 1},
                       {"decoded_body": record["body"]}, {"wire_received_size_bytes": -1},
                       {"response_headers": {**record["response_headers"], "content-encoding": "gzip"}},
                       {"body": {**record["body"], "path": relative + label + ".body"}}):
            with self.subTest(change=change), self.assertRaises(AssertionError):
                m._partial_body(ctx, relative, label, {**record, **change})

    def test_private_partial_original_is_required_and_hash_checked(self):
        _, ctx, relative, label, record = self.body_fixture(3)
        with self.synthetic_git():
            m._partial_body(ctx, relative, label, record)
            raw = self.private_originals[record["private_wire"]["path"]]
            with patch.object(m, "_private_bytes", return_value=bytes([raw[0] ^ 1]) + raw[1:]), \
                    self.assertRaisesRegex(AssertionError, "AFTER_PARTIAL_DIGEST"):
                m._partial_body(ctx, relative, label, record)
            with patch.object(m, "_private_bytes", side_effect=FileNotFoundError), self.assertRaises(FileNotFoundError):
                m._partial_body(ctx, relative, label, record)
            wrong = {**record, "private_wire": {**record["private_wire"], "path": ".cache/unrelated-private.body"}}
            with patch.object(m, "_private_bytes") as read_private, self.assertRaisesRegex(AssertionError, "AFTER_PRIVATE_PATH"):
                m._partial_body(ctx, relative, label, wrong)
            read_private.assert_not_called()

    def test_response_failure_cannot_be_washed_into_complete_or_pre_response(self):
        directory, ctx, relative, label, record = self.body_fixture(2)
        original = ctx.document
        for mutation in ("complete", "pre-response"):
            altered = copy.deepcopy(record)
            if mutation == "complete":
                altered["completed"] = True
                altered.pop("error_code")
            else:
                altered.pop("status")
            def document(reference):
                return altered if reference["path"] == relative + label + ".http.json" else original(reference)
            with self.subTest(mutation=mutation), patch.object(ctx, "document", document), self.assertRaises(AssertionError):
                m._after_source(ctx, directory / relative, 2, m.INSPECT.timestamp("2026-10-19T00:00:00Z"), True)

    def test_resume_summary_cannot_hide_failures_or_change_first_missing(self):
        directory, contract, descriptor, ctx = self.node_interop("interop-resumed")
        original = ctx.document
        after_ref = m.read(directory / m.RECOVERY / "after-result.json")["snapshot"]
        for field, value, error in (("reused_failures", [], "AFTER_REUSED_FAILURES"),
                                    ("first_missing", "protected-audit_logs-rows8-16", "AFTER_FIRST_MISSING"),
                                    ("new_reads", [], "AFTER_NEW_READS")):
            def altered(reference):
                result = original(reference)
                if reference == after_ref:
                    result["recovery"][field] = value
                return result

            with self.subTest(field=field), self.synthetic_git(), patch.object(m, "DATA", directory), \
                    patch.object(ctx, "document", altered), self.assertRaisesRegex(AssertionError, error):
                m.verify_after_recovery(contract, descriptor, ctx)

    def test_node_after_assemble_lineage_mismatches_are_rejected(self):
        directory, contract, descriptor, ctx = self.node_interop()
        original = m.read
        for name in ("after", "assemble"):
            path = directory / m.RECOVERY / (name + "-result.json")
            for field in [*m.lineage_fields(), "freeze_commit", *(["tool_commit"] if name == "after" else [])]:
                altered = original(path)
                altered[field] = "0" * 40
                with self.subTest(result=name, field=field), patch.object(m, "DATA", directory), \
                        patch.object(m, "read", lambda file: altered if file == path else original(file)), \
                        self.assertRaisesRegex(AssertionError, "CAPTURE_SOURCE_BINDING"):
                    m.capture_results(contract, descriptor, ctx)

    def test_node_after_assemble_reference_mismatches_are_rejected(self):
        directory, contract, descriptor, ctx = self.node_interop()
        original = m.read
        for name, key in (("after", "snapshot"), ("assemble", "manifest")):
            path = directory / m.RECOVERY / (name + "-result.json")
            for field, value in (("sha256", "0" * 64), ("size_bytes", 0), ("path", "wrong.json")):
                altered = original(path)
                altered[key][field] = value
                with self.subTest(result=name, field=field), patch.object(m, "DATA", directory), \
                        patch.object(m, "read", lambda file: altered if file == path else original(file)), \
                        self.assertRaisesRegex(AssertionError, "CAPTURE_RESULT_REFERENCE"):
                    m.capture_results(contract, descriptor, ctx)

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
            output = {"path": m.COMMANDS + "/" + name + ".log", "size_bytes": 2, "sha256": "b" * 64}
            outputs.append(copy.deepcopy(output))
            documents[m.DATA / m.COMMANDS / (name + ".json")] = {"label": name, "command": command, "args": args,
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
            receipt = documents[m.DATA / m.COMMANDS / "formal-precheck.json"]
            receipt["process_closed"] = False
            with self.assertRaises(AssertionError):
                m.ready()
            receipt["process_closed"] = True
            receipt["output"]["sha256"] = "c" * 64
            with self.assertRaisesRegex(AssertionError, "RECEIPT_OUTPUT_CHANGED"):
                m.ready()

    def test_admission_cannot_substitute_another_valid_receipt_output(self):
        with self.admission_fixture() as (documents, _):
            precheck = documents[m.DATA / m.COMMANDS / "formal-precheck.json"]
            plan_receipt = documents[m.DATA / m.COMMANDS / "formal-rerun-plan.json"]
            precheck["output"] = copy.deepcopy(plan_receipt["output"])
            with self.assertRaisesRegex(AssertionError, "ADMISSION_OUTPUT_BINDING"):
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
                if reference == descriptor["predecessor_contract"]:
                    return original_read(m.PARENT_CONTRACT)
                if reference == descriptor["predecessor_matrix"]:
                    return original_read(m.PARENT_MATRIX)
                return ctx_original.read(reference)

            def document(self, reference):
                return m.INSPECT.json_bytes(self.read(reference))

        with patch.object(m, "read", return_value=descriptor), patch.object(m.INSPECT, "Context", return_value=CopiedContext()), \
                patch.object(Path, "read_bytes", lambda path: b"tampered-nonprefix" if path == target else original_read(path)):
            with self.assertRaisesRegex(m.INSPECT.EvidenceError, "FILE_DIGEST_MISMATCH"):
                m.verify_import()

    def test_full_c5_import_is_verified_without_formal_copy_or_network(self):
        descriptor, original = self.descriptor, self.original
        parent_copies = {descriptor["predecessor_contract"]["path"]: m.PARENT_CONTRACT,
                         descriptor["predecessor_matrix"]["path"]: m.PARENT_MATRIX}
        checked = set()

        class CopiedContext:
            def read(self, reference):
                checked.add(reference["path"])
                if reference["path"] not in parent_copies:
                    return original.read(reference)
                raw = parent_copies[reference["path"]].read_bytes()
                assert set(reference) == {"path", "size_bytes", "sha256"}
                assert len(raw) == reference["size_bytes"] and m.b.sha(raw) == reference["sha256"]
                return raw

            def document(self, reference):
                return m.INSPECT.json_bytes(self.read(reference))

        with patch.object(m, "read", return_value=descriptor), patch.object(m.INSPECT, "Context", return_value=CopiedContext()), \
                patch.object(m.b, "write", side_effect=AssertionError("WRITE_FORBIDDEN")):
            imported, parent, matrix, _ = m.verify_import(m.PARENT / "evidence")
        self.assertEqual(imported, descriptor)
        self.assertEqual(parent, self.parent)
        self.assertEqual(matrix, self.previous)
        self.assertTrue({item["path"] for item in descriptor["files"]} <= checked)
        self.assertEqual(len(checked), 1187)

    def test_import_rejects_offline_scope_and_predecessor_identity_drift(self):
        for key, value in (("schema", "p44-after-recovery-v1"), ("source_commit", m.PREDECESSOR_COMMIT),
                           ("predecessor_commit", m.SOURCE_COMMIT), ("predecessor_index_commit", m.SOURCE_INDEX),
                           ("offline_identity", {**m.OFFLINE_IDENTITY, "mode": "fallback"})):
            descriptor = {**self.descriptor, key: value}
            with self.subTest(field=key), patch.object(m, "read", return_value=descriptor), \
                    patch.object(m.b, "write", side_effect=AssertionError("WRITE_FORBIDDEN")), self.assertRaises(AssertionError):
                m.verify_import()

    def test_successor_package_paths_and_predecessor_are_data_driven(self):
        spec = importlib.util.spec_from_file_location("p44_successor_test", ROOT / m.PYTHON)
        next_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(next_module)
        directory = self.directory()
        package = {"schema": "p44-after-package-v1", "version": 7, "package": "docs/acceptance-contracts/P4-4-v7",
                   "round_id": "P44-SYNTHETIC-07", "max_after_invocations": 2,
                   "predecessor": {"commit": m.C6_TOOL, "bundle_commit": "b" * 40, "index_commit": "c" * 40,
                                   "contract_sha256": "d" * 64, "matrix_sha256": "e" * 64}}
        self.write(directory, "package.json", package)
        next_module.configure_package((directory / "package.json").relative_to(ROOT).as_posix())
        self.assertEqual(next_module.PREDECESSOR_COMMIT, m.C6_TOOL)
        self.assertEqual(next_module.LEGACY_PREDECESSOR, m.LEGACY_PREDECESSOR)
        self.assertIn("P4-4-v6.contract.json", next_module.validation_commands()["final"])
        self.assertIn("P4-4-v7/final-evidence-matrix.json", next_module.validation_commands()["final"])
        contract = next_module.successor(self.parent, {"sha256": "a" * 64})
        after = next(row for row in contract["commands"] if row["id"] == "formal-after")
        self.assertIn("--package-spec", after["command"])
        self.assertNotIn("--invocation", after["command"])
        self.assertIn("At most two", after["description"])
        self.assertEqual(contract["version"], 7)

    def test_successor_cli_output_is_consumed_by_python(self):
        if "successor-cli" not in self.interop:
            self.skipTest("successor CLI packet not supplied")
        directory, contract, descriptor, packet = self.interop["successor-cli"]
        spec = importlib.util.spec_from_file_location("p44_successor_cli_test", ROOT / m.PYTHON)
        next_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(next_module)
        with patch.object(next_module, "read", return_value=packet["package_spec"]):
            next_module.configure_package(packet["package_spec_path"])
        node_bytes = (ROOT / m.NODE).read_bytes()
        def git(*args):
            self.assertEqual(args, ("merge-base", "--is-ancestor", "a" * 40, "HEAD"))
            return ""
        def git_bytes(*args):
            self.assertEqual(args, ("show", "a" * 40 + ":" + m.NODE))
            return node_bytes
        ctx = next_module.INSPECT.Context(ROOT, directory / "manifest.json")
        with patch.object(next_module, "DATA", directory), patch.object(next_module.b, "git", git), \
                patch.object(next_module.b, "git_bytes", git_bytes):
            result = next_module.capture_results(contract, descriptor, ctx)
        self.assertEqual(result["total_complete"], 142)
        self.assertEqual(result["attempts"], 3)
        self.assertEqual(result["new_reads"], 72)

    def test_successor_multislot_receipts_and_stock_matrix_validators(self):
        directory = self.directory()
        matrix, contract, plan = self.mixed()
        spec_path = ".cache/p44-v7-development/synthetic-package.json"
        commands = "recovery-commands-v7"
        recovery = "recovery-v7"
        fixture = "inputs/after-recovery-v7.json"
        package = {"max_after_invocations": 2}
        argv = [m.NODE, "--package-spec", spec_path, "after"]
        text = " ".join(["node", m.NODE, "--package-spec", spec_path, "run", "formal-after", "node", *argv])
        definition = next(row for row in contract["commands"] if row["id"] == "formal-after")
        definition["command"] = text
        self.write(directory, "contract.json", contract)
        self.write(directory, fixture, {"files": []})
        source_hash = m.sha(ROOT / m.NODE)
        attempts = []
        receipts = []
        for slot, code in ((1, 1), (2, 0)):
            start = "2026-10-21T00:0" + str(slot) + ":00Z"
            end = "2026-10-21T00:0" + str(slot) + ":02Z"
            attempt_dir = m.TAIL + "/attempt-" + str(slot + 1)
            reservation = {"tool_commit": contract["freeze_commit"], "tool_sha256": source_hash,
                           "started": start, "first_missing": "protected-patches-rows8-16"}
            self.write(directory, attempt_dir + "/attempt-reservation.json", reservation)
            attempt = self.write(directory, attempt_dir + "/attempt-result.json", {"ok": code == 0, "ended": end,
                                  **({"error_code": "UND_ERR_SOCKET"} if code else {})})
            attempts.append(attempt)
            stem = commands + "/formal-after-invocation-" + str(slot)
            log = self.write(directory, stem + ".log", b"UND_ERR_SOCKET\n" if code else b"completed\n")
            reserved = {"label": "formal-after", "command": "node", "args": argv, "cwd": str(ROOT), "started": start}
            self.write(directory, stem + "-reservation.json", reserved)
            receipts.append(self.write(directory, stem + ".json", {**reserved, "ended": end, "exitCode": code,
                "signal": None, "closed": True, "process_closed": True, "spawn_failed": False, "output": log}))
        approval = {"schema": "p44-after-continuation-v1", "slot": 2, "prior_receipt": receipts[0],
            "prior_attempt_result": attempts[0], "tool_commit": contract["freeze_commit"], "tool_sha256": source_hash,
            "first_missing": "protected-patches-rows8-16", "decision": "CONTINUE_MISSING_ONLY",
            "basis": "Synthetic transport-state restoration; no blind retry", "approved_by": "Synthetic independent root",
            "approved_at": "2026-10-21T00:01:30Z"}
        self.write(directory, recovery + "/continuation-2.json", approval)
        ctx = m.INSPECT.Context(ROOT, directory / "manifest.json")
        with patch.multiple(m, DATA=directory, CONTRACT=directory / "contract.json", COMMANDS=commands,
                            RECOVERY=recovery, FIXTURE=fixture, PACKAGE_SPEC=package, PACKAGE_SPEC_PATH=spec_path):
            selected = m.new_receipt("formal-after", definition, ctx)
            self.assertEqual(selected["output_evidence"], "evidence/" + commands + "/formal-after-invocation-2.log")
            self.assertEqual(len(m.after_receipts(definition, ctx)), 2)
            for broken in ({**approval, "basis": ""}, {**approval, "prior_receipt": receipts[1]},
                           {**approval, "first_missing": "wrong"}, {**approval, "approved_at": "2099-01-01T00:00:00Z"},
                           {**approval, "approved_at": "2026-10-21T00:02:01Z"}):
                with patch.object(m, "read", wraps=m.read) as reader:
                    actual_read = lambda file: m.INSPECT.json_bytes(m.b.guard(file).read_bytes())
                    reader.side_effect = lambda file: broken if Path(file).name == "continuation-2.json" else actual_read(file)
                    with self.assertRaises(AssertionError):
                        m.after_receipts(definition, ctx)
            prior_file = directory / receipts[0]["path"]
            with patch.object(Path, "exists", autospec=True, side_effect=lambda file: False if file == prior_file else Path.is_file(file)):
                with self.assertRaises(AssertionError):
                    m.after_receipts(definition, ctx)
        matrix["commands"] = [selected if row["id"] == "formal-after" else row for row in matrix["commands"]]
        for file in directory.rglob("*"):
            if file.is_file():
                matrix["evidence_hashes"]["evidence/" + file.relative_to(directory).as_posix()] = m.sha(file)
        for row in matrix["criteria"]:
            if row["id"] == "P44-RAW-STATE":
                row["evidence"] += ["evidence/" + item["path"] for item in receipts]
        self.assertFalse(m.RULES.validate_matrix(matrix, contract, matrix["contract_sha256"]))
        self.assertFalse(m.RULES.validate_reuse(matrix, contract, self.previous, plan, self.sources))
        self.assertFalse(m.RULES.validate_planned_execution(matrix, contract, plan))
        duplicate = copy.deepcopy(matrix)
        duplicate["commands"].append(copy.deepcopy(selected))
        self.assertTrue(m.RULES.validate_matrix(duplicate, contract, matrix["contract_sha256"]))
        variable = copy.deepcopy(matrix)
        next(row for row in variable["commands"] if row["id"] == "formal-after")["command"] += " --invocation 2"
        self.assertTrue(m.RULES.validate_matrix(variable, contract, matrix["contract_sha256"]))

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
