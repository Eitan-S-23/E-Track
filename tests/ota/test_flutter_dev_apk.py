#!/usr/bin/env python3
"""Offline fixtures for the development APK helper. Never builds an APK."""

import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import unittest
from unittest import mock
import uuid
import zipfile


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from Tools.flutter import dev_apk as APK
from Tools.flutter import dev_checks as CHECKS


class DevelopmentApkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.output = CHECKS.make_directory(
            ROOT, Path(".cache/flutter-dev-apk-tests") / ("run-" + uuid.uuid4().hex), exclusive=True
        )
        print(f"APK helper fixtures: {cls.output}", flush=True)

    def setUp(self):
        self.root = CHECKS.make_directory(ROOT, self.output / self._testMethodName)
        self.run = CHECKS.make_directory(self.root, Path("run"))
        self.write(CHECKS.APP / "android/app/build.gradle.kts", b"compileSdk = 35\n")
        self.properties = self.write(
            CHECKS.APP / "android/gradle/wrapper/gradle-wrapper.properties",
            b"distributionUrl=https\\://services.gradle.org/distributions/gradle-8.12-all.zip\n",
        )
        self.write(Path("host-sdk/cmdline-tools/latest/bin/sdkmanager"), b"fixture\n")
        self.write(Path("host-sdk/licenses/android-sdk-license"), b"fixture-license\n")
        self.write(Path("host-java/bin/java"), b"fixture\n")
        base = CHECKS.contained_environment(self.root, self.run)
        base.update({"ANDROID_HOME": str(self.root / "host-sdk"),
                     "JAVA_HOME_17_X64": str(self.root / "host-java")})
        self.env = APK.environment(self.root, self.run, base)

    def write(self, relative, data):
        path = CHECKS.checked_path(self.root, relative)
        CHECKS.make_directory(self.root, path.parent)
        path.write_bytes(data)
        return path

    def archive_bytes(self, entries):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, data in entries:
                archive.writestr(name, data)
        return buffer.getvalue()

    def fake_fetch(self, corrupted=False):
        payload = self.archive_bytes([("gradle-8.12/bin/gradle", b"fixture launcher\n")])

        def fetch(url, path, limit):
            data = (("0" * 64 if corrupted else hashlib.sha256(payload).hexdigest()).encode("ascii")
                    if url.endswith(".sha256") else payload)
            self.assertLess(len(data), limit)
            CHECKS.checked_path(self.root, path).write_bytes(data)

        return fetch

    def test_versions_are_derived_from_tracked_inputs(self):
        self.assertEqual(("8.12", "35"), APK.android_versions(self.root))
        self.properties.write_bytes(b"distributionUrl=https://other.invalid/gradle.zip\n")
        with self.assertRaisesRegex(ValueError, "official"):
            APK.android_versions(self.root)

    def test_environment_redirects_android_java_outputs_and_drops_signing_secrets(self):
        env = APK.environment(self.root, self.run, {
            **self.env, "ANDROID_RELEASE_KEYSTORE_PASSWORD": "fixture-only",
            "SIDELOAD_KEY_PASSWORD": "fixture-only",
            "JAVA_OPTS": "-Duser.home=/unapproved",
            "_JAVA_OPTIONS": "-Djava.io.tmpdir=/unapproved",
            "JDK_JAVA_OPTIONS": "-Duser.home=/unapproved",
            "SDKMANAGER_OPTS": "-Duser.home=/unapproved",
        })
        for key in ("ANDROID_HOME", "ANDROID_SDK_ROOT", "ANDROID_USER_HOME", "ANDROID_AVD_HOME"):
            self.assertTrue(Path(env[key]).is_relative_to(self.run))
        self.assertIn(str(self.run / "home"), env["JAVA_TOOL_OPTIONS"])
        self.assertIn(str(self.run / "tmp"), env["JAVA_TOOL_OPTIONS"])
        self.assertNotIn("ANDROID_RELEASE_KEYSTORE_PASSWORD", env)
        self.assertNotIn("SIDELOAD_KEY_PASSWORD", env)
        for key in ("JAVA_OPTS", "_JAVA_OPTIONS", "JDK_JAVA_OPTIONS", "SDKMANAGER_OPTS"):
            self.assertNotIn(key, env)

    def test_prepare_verifies_download_and_preserves_tracked_wrapper_properties(self):
        original = self.properties.read_bytes()
        APK.prepare(self.root, self.run, self.env, fetch=self.fake_fetch())
        self.assertTrue((self.run / "gradle-dist/gradle-8.12/bin/gradle").is_file())
        metadata = json.loads((self.run / "apk-toolchain.json").read_text())
        self.assertEqual("8.12", metadata["gradle_version"])
        self.assertEqual(original, self.properties.read_bytes())
        self.assertEqual(b"fixture-license\n", (self.run / "android-sdk/licenses/android-sdk-license").read_bytes())

    def test_bad_checksum_never_extracts_distribution(self):
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            APK.prepare(self.root, self.run, self.env, fetch=self.fake_fetch(corrupted=True))
        self.assertFalse((self.run / "gradle-dist").exists())

    def test_archive_rejects_escape_before_writing_any_member(self):
        for name in ("../escape.txt", "/absolute.txt", "C:/escape.txt", "dir\\escape.txt"):
            with self.subTest(name=name):
                member = zipfile.ZipInfo("placeholder")
                member.filename = name
                member.orig_filename = name
                archive = self.write(Path("bad.zip"), self.archive_bytes([
                    ("ordinary.txt", b"must not be extracted"), (member, b"bad")
                ]))
                with zipfile.ZipFile(archive) as fixture:
                    self.assertEqual(name, fixture.infolist()[1].orig_filename)
                with self.assertRaisesRegex(ValueError, "Unsafe distribution"):
                    APK.extract_distribution(self.root, archive, self.run / "unpacked")
                self.assertFalse((self.run / "unpacked").exists())

    def test_archive_rejects_symlinks(self):
        link = zipfile.ZipInfo("gradle/link")
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive = self.write(Path("link.zip"), self.archive_bytes([(link, b"../../outside")]))
        with self.assertRaisesRegex(ValueError, "Unsafe distribution"):
            APK.extract_distribution(self.root, archive, self.run / "unpacked")

    def test_stale_apk_is_rejected_without_download(self):
        self.write(APK.APK_RELATIVE, b"old-apk")
        fetch = mock.Mock()
        with self.assertRaisesRegex(ValueError, "pre-existing APK"):
            APK.prepare(self.root, self.run, self.env, fetch=fetch)
        fetch.assert_not_called()

    def test_release_signing_file_is_rejected_without_download(self):
        self.write(CHECKS.APP / "android/key.properties", b"fixture-only\n")
        fetch = mock.Mock()
        with self.assertRaisesRegex(ValueError, "release signing"):
            APK.prepare(self.root, self.run, self.env, fetch=fetch)
        fetch.assert_not_called()

    def test_missing_jdk_is_failure_not_silent_fallback(self):
        with self.assertRaisesRegex(ValueError, "JDK 17"):
            APK.prepare(self.root, self.run, {**self.env, "JAVA_HOME": ""}, fetch=mock.Mock())

    def test_wrapper_install_checks_sdk_and_preserves_other_local_properties(self):
        for relative in ("cmdline-tools/latest/bin/sdkmanager", "platform-tools/adb",
                         "platforms/android-35/android.jar", "build-tools/35.0.0/apksigner"):
            self.write(Path("run/android-sdk") / relative, b"fixture\n")
        for relative in ("gradlew", "gradlew.bat", "gradle/wrapper/gradle-wrapper.jar"):
            self.write(Path("run/wrapper-bootstrap") / relative, b"new-wrapper\n")
        local = self.write(CHECKS.APP / "android/local.properties",
                           b"flutter.sdk=old\nflutter.versionName=fixture\n")
        original = self.properties.read_bytes()
        with mock.patch.object(APK, "assert_ignored") as guard:
            APK.install_wrapper(self.root, self.run)
        self.assertEqual(4, guard.call_count)
        self.assertIn("flutter.versionName=fixture", local.read_text())
        self.assertIn(str(self.run / "sdk"), local.read_text())
        self.assertEqual(original, self.properties.read_bytes())

    def test_tracked_inputs_cannot_be_overwritten_as_generated_outputs(self):
        APK.assert_ignored(ROOT, ROOT / CHECKS.APP / "android/gradlew")
        with self.assertRaisesRegex(ValueError, "tracked or non-ignored"):
            APK.assert_ignored(ROOT, ROOT / CHECKS.APP / "android/app/build.gradle.kts")

    def test_missing_android_package_stops_wrapper_install(self):
        with self.assertRaisesRegex(ValueError, "not installed"):
            APK.install_wrapper(self.root, self.run)
        self.assertFalse((self.root / CHECKS.APP / "android/gradlew").exists())

    def test_artifact_collection_binds_bytes_commit_and_debug_classification(self):
        data = self.archive_bytes([("AndroidManifest.xml", b"fixture, not a real APK manifest")])
        self.write(APK.APK_RELATIVE, data)
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            APK.collect(self.root, self.run, "1" * 40)
        metadata = json.loads((self.run / "artifacts/trace-dev-debug.json").read_text())
        self.assertEqual(hashlib.sha256(data).hexdigest(), metadata["sha256"])
        self.assertEqual("1" * 40, metadata["commit"])
        self.assertFalse(metadata["release_signing"])
        self.assertEqual("NOT_RUN", metadata["formal_acceptance"])
        self.assertEqual(data, (self.run / "artifacts/trace-dev-debug.apk").read_bytes())

    def test_missing_apk_or_commit_cannot_be_reported_as_generated(self):
        with self.assertRaisesRegex(ValueError, "missing or empty"):
            APK.collect(self.root, self.run, "1" * 40)
        self.write(APK.APK_RELATIVE, self.archive_bytes([("AndroidManifest.xml", b"fixture")]))
        with self.assertRaisesRegex(ValueError, "exact tested commit"):
            APK.collect(self.root, self.run, "")
        self.assertFalse((self.run / "artifacts").exists())

    def test_plan_is_debug_only_and_bounded(self):
        plan = APK.plan(self.root, self.run, self.env)
        build = next(argv for name, argv, _, _ in plan if name == "apk_build")
        self.assertIn("--debug", build)
        self.assertIn("--no-pub", build)
        self.assertNotIn("--release", build)
        self.assertTrue(all(0 < timeout <= 1200 for _, _, _, timeout in plan))
        sdk = next(argv for name, argv, _, _ in plan if name == "apk_sdk")
        self.assertIn(f"--sdk_root={self.run / 'android-sdk'}", sdk)
        self.assertIn("platforms;android-35", sdk)

    def test_cli_never_builds_or_downloads_locally(self):
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}), \
                mock.patch.object(APK, "prepare") as prepare, \
                mock.patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit):
            APK.main(["prepare", "--repo-root", str(self.root), "--run-dir", str(self.run)])
        prepare.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
