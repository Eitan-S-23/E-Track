"""Execute the real workflow selection shell with fake keys/tools, never build."""
import base64
from pathlib import Path
import shutil
import sys
import textwrap
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota/p34-acceptance"))
import live_host as h

PIN = "9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579"
KEY = base64.b64encode(b"test fixture, not a signing key").decode()


class SigningSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        h.require(Path.cwd() == ROOT and sys.dont_write_bytecode, "contained root required")
        cls.out = h.fresh(ROOT / ".cache/android-signing-tests" / uuid.uuid4().hex)
        cls.bash = shutil.which("bash")
        h.require(cls.bash, "installed Bash required; no SDK download")
        cls.workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
        step = cls.workflow.split("      - name: Configure Android release signing\n", 1)[1].split("\n      - name:", 1)[0]
        cls.script = textwrap.dedent(step.split("        run: |\n", 1)[1])

    def run_case(self, settings, expected_code=0):
        out = h.fresh(self.out / self._testMethodName)
        android = h.checked(out / "android")
        android.mkdir()
        env = h.environment(out)
        for key in tuple(env):
            if key.startswith(("ANDROID_RELEASE_", "SIDELOAD_", "ETRACK_DEV_SIGNING_")):
                env.pop(key)
        env.update(settings, GITHUB_OUTPUT=str(h.checked(out / "outputs")).replace("\\", "/"))
        env.setdefault("CASE_CERT", PIN)
        env.setdefault("CASE_KEYTOOL_EXIT", "0")
        script = """keytool() { printf public-certificate-fixture; return "$CASE_KEYTOOL_EXIT"; }
sha256sum() { printf '%s  fixture\\n' "$CASE_CERT"; }
cd "$CASE_DIR"
""" + self.script
        env["CASE_DIR"] = str(out).replace("\\", "/")
        process = h.Process(out, "shell", [self.bash, "--noprofile", "--norc", "-s"], env, stdin=script.encode())
        process.wait(30, success_codes=(0, 1))
        self.assertEqual(process.process.returncode, expected_code)
        outputs = (out / "outputs").read_text() if (out / "outputs").exists() else ""
        return out, outputs

    def test_existing_key_selected_and_pinned(self):
        out, outputs = self.run_case({"ETRACK_DEV_SIGNING_KEYSTORE": KEY})
        self.assertIn("fixed_signing_configured=true", outputs)
        self.assertIn("certificate_sha256=" + PIN, outputs)
        self.assertIn("keyAlias=androiddebugkey", (out / "android/key.properties").read_text())

    def test_no_keys_remains_explicit_nonrelease_fallback(self):
        _, outputs = self.run_case({})
        self.assertIn("fixed_signing_configured=false", outputs)

    def test_partial_formal_key_does_not_fall_back(self):
        _, outputs = self.run_case({"ANDROID_RELEASE_KEYSTORE_BASE64": KEY, "ETRACK_DEV_SIGNING_KEYSTORE": KEY}, 1)
        self.assertNotIn("fixed_signing_configured=true", outputs)

    def test_partial_sideload_key_does_not_fall_back(self):
        _, outputs = self.run_case({"SIDELOAD_KEYSTORE_BASE64": KEY, "ETRACK_DEV_SIGNING_KEYSTORE": KEY}, 1)
        self.assertNotIn("fixed_signing_configured=true", outputs)

    def test_mismatched_existing_certificate_rejected(self):
        out, outputs = self.run_case({"ETRACK_DEV_SIGNING_KEYSTORE": KEY, "CASE_CERT": "0" * 64}, 1)
        self.assertFalse((out / "android/key.properties").exists())
        self.assertNotIn("fixed_signing_configured=true", outputs)

    def test_keytool_failure_rejected(self):
        _, outputs = self.run_case({"ETRACK_DEV_SIGNING_KEYSTORE": KEY, "CASE_KEYTOOL_EXIT": "1"}, 1)
        self.assertNotIn("fixed_signing_configured=true", outputs)

    def test_bad_encoding_rejected(self):
        _, outputs = self.run_case({"ETRACK_DEV_SIGNING_KEYSTORE": "%%%"}, 1)
        self.assertNotIn("fixed_signing_configured=true", outputs)

    def test_formal_configuration_keeps_precedence(self):
        values = {"ANDROID_RELEASE_KEYSTORE_BASE64": KEY, "ANDROID_RELEASE_KEYSTORE_PASSWORD": "fixture",
                  "ANDROID_RELEASE_KEY_ALIAS": "formal-fixture", "ANDROID_RELEASE_KEY_PASSWORD": "fixture",
                  "ETRACK_DEV_SIGNING_KEYSTORE": KEY, "CASE_CERT": "1" * 64}
        out, outputs = self.run_case(values)
        self.assertIn("keyAlias=formal-fixture", (out / "android/key.properties").read_text())
        self.assertIn("certificate_sha256=" + "1" * 64, outputs)

    def test_existing_secret_and_apk_check_are_wired(self):
        self.assertIn("ETRACK_DEV_SIGNING_KEYSTORE: ${{ secrets.ETRACK_DEV_SIGNING_KEYSTORE }}", self.workflow)
        self.assertIn('test "$actual" = "$EXPECTED_CERT_SHA256"', self.workflow)
        self.assertLess(self.workflow.index("Verify release APK signature and identity"), self.workflow.index("Upload Android APK"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
