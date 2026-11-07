"""Execute real release argument selection with a fake Flutter function, no build."""
from pathlib import Path
import shutil
import sys
import textwrap
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota/p34-acceptance"))
import live_host as h

PUBLIC = "https://app-update.example.invalid"
FIRMWARE = "https://firmware-update.example.invalid/api/public/firmware/latest"
APP_DEFINE = "--dart-define=TRACE_CLOUDFLARE_UPDATE_MANIFEST_URL="
FIRMWARE_DEFINE = "--dart-define=TRACE_CLOUDFLARE_FIRMWARE_LATEST_URL="
KEY_DEFINE = "--dart-define=TRACE_UPDATE_PAYLOAD_ED25519_PUBLIC_KEY_BASE64="


class UpdateEndpointSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        h.require(Path.cwd() == ROOT and sys.dont_write_bytecode, "contained root required")
        cls.out = h.fresh(ROOT / ".cache/flutter-update-endpoint-tests" / uuid.uuid4().hex)
        cls.bash = shutil.which("bash")
        h.require(cls.bash, "installed Bash required; no SDK download")
        workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
        step = workflow.split("      - name: Build release APK\n", 1)[1].split("\n      - name:", 1)[0]
        cls.script = textwrap.dedent(step.split("        run: |\n", 1)[1])

    def run_case(self, settings=None, expected_code=0):
        out = h.fresh(self.out / self._testMethodName)
        env = h.environment(out)
        for key in tuple(env):
            if key.startswith(("TRACE_", "DISPATCH_", "CASE_")) or key in ("BASH_ENV", "ENV", "SHELLOPTS", "BASHOPTS"):
                env.pop(key)
        env.update(CASE_DIR=str(out).replace("\\", "/"), CASE_FLUTTER_EXIT="0", TRACE_OTA_LINK_PROFILE="baseline")
        env.update(settings or {})
        script = """python() { printf '%s\\n' '--dart-define=TRACE_OTA_LINK_PROFILE=baseline'; }
flutter() { printf 'CAPTURE_ARG:%s\\n' "$@"; return "$CASE_FLUTTER_EXIT"; }
cd "$CASE_DIR" || exit 1
""" + self.script
        h.raw(out / "fixture.sh", script.encode())
        process = h.Process(out, "shell", [self.bash, "--noprofile", "--norc", "-s"], env, stdin=script.encode())
        stdout = process.wait(30, success_codes=(0, 1, 17)).decode("utf-8")
        self.assertEqual(process.process.returncode, expected_code)
        arguments = [line.removeprefix("CAPTURE_ARG:") for line in stdout.splitlines() if line.startswith("CAPTURE_ARG:")]
        return arguments, stdout

    def test_unconfigured_build_keeps_legacy_fallback(self):
        arguments, _ = self.run_case()
        self.assertIn("apk", arguments)
        self.assertFalse(any(arg.startswith((APP_DEFINE, FIRMWARE_DEFINE)) for arg in arguments))

    def test_public_service_sets_both_default_endpoints(self):
        arguments, _ = self.run_case({"TRACE_PUBLIC_UPDATE_SERVICE_URL": PUBLIC})
        self.assertEqual(arguments.count(APP_DEFINE + PUBLIC + "/api/public/latest"), 1)
        self.assertEqual(arguments.count(FIRMWARE_DEFINE + PUBLIC + "/api/public/firmware/latest"), 1)

    def test_firmware_only_override_keeps_unconfigured_app_fallback(self):
        arguments, _ = self.run_case({"DISPATCH_FIRMWARE_LATEST_URL": FIRMWARE})
        self.assertIn(FIRMWARE_DEFINE + FIRMWARE, arguments)
        self.assertFalse(any(arg.startswith(APP_DEFINE) for arg in arguments))

    def test_firmware_override_preserves_configured_app_endpoint(self):
        arguments, _ = self.run_case({"TRACE_PUBLIC_UPDATE_SERVICE_URL": PUBLIC,
                                     "DISPATCH_FIRMWARE_LATEST_URL": FIRMWARE})
        self.assertEqual(arguments.count(APP_DEFINE + PUBLIC + "/api/public/latest"), 1)
        self.assertEqual([arg for arg in arguments if arg.startswith(FIRMWARE_DEFINE)], [FIRMWARE_DEFINE + FIRMWARE])

    def test_trailing_slash_is_normalized_for_each_endpoint(self):
        arguments, _ = self.run_case({"TRACE_PUBLIC_UPDATE_SERVICE_URL": PUBLIC + "/",
                                     "DISPATCH_FIRMWARE_LATEST_URL": FIRMWARE + "/"})
        self.assertIn(APP_DEFINE + PUBLIC + "/api/public/latest", arguments)
        self.assertIn(FIRMWARE_DEFINE + FIRMWARE, arguments)

    def test_payload_key_is_not_replaced_by_firmware_override(self):
        arguments, _ = self.run_case({"TRACE_PUBLIC_UPDATE_SERVICE_URL": PUBLIC,
                                     "DISPATCH_FIRMWARE_LATEST_URL": FIRMWARE,
                                     "TRACE_UPDATE_PAYLOAD_ED25519_PUBLIC_KEY_BASE64": "public-key-fixture"})
        self.assertIn(KEY_DEFINE + "public-key-fixture", arguments)
        self.assertIn(APP_DEFINE + PUBLIC + "/api/public/latest", arguments)

    def test_missing_payload_key_remains_explicit(self):
        arguments, stdout = self.run_case({"TRACE_PUBLIC_UPDATE_SERVICE_URL": PUBLIC})
        self.assertFalse(any(arg.startswith(KEY_DEFINE) for arg in arguments))
        self.assertIn("public key is not configured; signed Cloudflare manifests will fail closed", stdout)

    def test_insecure_firmware_url_is_rejected_before_flutter(self):
        arguments, _ = self.run_case({"DISPATCH_FIRMWARE_LATEST_URL": "http://firmware.example.invalid/latest"}, 1)
        self.assertEqual(arguments, [])

    def test_firmware_credential_query_is_rejected_before_flutter(self):
        arguments, _ = self.run_case({"DISPATCH_FIRMWARE_LATEST_URL": FIRMWARE + "?token=fixture"}, 1)
        self.assertEqual(arguments, [])

    def test_firmware_fragment_is_rejected_before_flutter(self):
        arguments, _ = self.run_case({"DISPATCH_FIRMWARE_LATEST_URL": FIRMWARE + "#fragment"}, 1)
        self.assertEqual(arguments, [])

    def test_build_failure_still_propagates(self):
        arguments, stdout = self.run_case({"CASE_FLUTTER_EXIT": "17"}, 17)
        self.assertIn("apk", arguments)
        self.assertIn("Android release build failed", stdout)


class ReleaseVisibilityTests(unittest.TestCase):
    def run_case(self, prerelease, automatic="false", exists="false"):
        h.require(Path.cwd() == ROOT and sys.dont_write_bytecode, "contained root required")
        out = h.fresh(ROOT / ".cache/flutter-update-endpoint-tests" / uuid.uuid4().hex)
        env = h.environment(out)
        for key in ("BASH_ENV", "ENV", "SHELLOPTS", "BASHOPTS"):
            env.pop(key, None)
        env.update(CASE_DIR=str(out).replace("\\", "/"), RELEASE_PRERELEASE=prerelease,
                   AUTO_RELEASE_ON_PUSH=automatic, RELEASE_EXISTS=exists, RELEASE_TAG="test-v1.0.73",
                   RELEASE_NOTES_PATH=str(h.checked(out / "notes.md")).replace("\\", "/"),
                   GITHUB_SHA="1" * 40, GITHUB_RUN_NUMBER="1")
        workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
        step = workflow.split("      - name: Create or update GitHub Release\n", 1)[1].split("\n      - name:", 1)[0]
        body = textwrap.dedent(step.split("        run: |\n", 1)[1])
        script = """git() { printf 'Test release fixture\\n'; }
gh() { printf 'GH_ARG:%s\\n' "$@"; }
cd "$CASE_DIR" || exit 1
""" + body
        h.raw(out / "fixture.sh", script.encode())
        bash = shutil.which("bash")
        h.require(bash, "installed Bash required")
        raw = h.command(out, "shell", [bash, "--noprofile", "--norc", "-s"], env,
                        stdin=script.encode(), seconds=30).decode()
        return [line.removeprefix("GH_ARG:") for line in raw.splitlines() if line.startswith("GH_ARG:")]

    def test_prerelease_is_never_latest(self):
        arguments = self.run_case("true")
        self.assertIn("--prerelease", arguments)
        self.assertEqual(arguments.count("--latest=false"), 1)

    def test_default_formal_release_visibility_is_unchanged(self):
        arguments = self.run_case("false")
        self.assertNotIn("--prerelease", arguments)
        self.assertNotIn("--latest=false", arguments)

    def test_explicit_existing_release_edit_keeps_prerelease_not_latest(self):
        arguments = self.run_case("true", exists="true")
        self.assertIn("edit", arguments)
        self.assertIn("--prerelease", arguments)
        self.assertEqual(arguments.count("--latest=false"), 1)

    def test_automatic_release_keeps_existing_not_latest_policy(self):
        arguments = self.run_case("false", automatic="true")
        self.assertNotIn("--prerelease", arguments)
        self.assertIn("--latest=false", arguments)


if __name__ == "__main__":
    unittest.main(verbosity=2)
