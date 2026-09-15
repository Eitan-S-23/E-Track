#!/usr/bin/env python3
"""Offline fixtures for the development APK helper. Never builds an APK."""

import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace
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
        self.write(CHECKS.APP / "android/app/build.gradle.kts",
                   b'compileSdk = 35\napplicationId = "com.example.fixture" // fixture\n')
        self.properties = self.write(
            CHECKS.APP / "android/gradle/wrapper/gradle-wrapper.properties",
            b"distributionUrl=https\\://services.gradle.org/distributions/gradle-8.12-all.zip\n",
        )
        self.write(Path("host-sdk/cmdline-tools/latest/bin/sdkmanager"), b"fixture\n")
        self.write(Path("host-sdk/licenses/android-sdk-license"), b"fixture-license\n")
        self.write(Path("host-java/bin/java"), b"fixture\n")
        base = CHECKS.contained_environment(self.root, self.run)
        # 宿主/CI 环境可能已显式启用包名后缀或设备观测（workflow 的 job env 会
        # 透传）；它们不得渗进 fixture 判定，否则同一提交在不同环境得到不同
        # 期望值。两条路径分别由 test_environment_... /
        # test_debug_application_id_suffix_... 与 test_device_observation_...
        # 显式覆盖。
        for name in (APK.APPLICATION_ID_ENV, APK.DEVICE_OBSERVATION_ENV,
                     APK.OBSERVATION_TARGET_ENV, APK.OBSERVATION_FIRMWARE_URL_ENV):
            base.pop(name, None)
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
            "TRACE_DEV_APP_ID_SUFFIX": ".obs",
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
        # 包名后缀不是凭据：它必须原样到达 Gradle，否则显式启用会静默失效。
        self.assertEqual(".obs", env["TRACE_DEV_APP_ID_SUFFIX"])

    def test_debug_application_id_suffix_is_explicit_and_validated(self):
        self.assertEqual("", APK.application_id_suffix({}))
        self.assertEqual("", APK.application_id_suffix({APK.APPLICATION_ID_ENV: "   "}))
        self.assertEqual(".obs", APK.application_id_suffix({APK.APPLICATION_ID_ENV: " .obs "}))
        for invalid in ("obs", ".", ".1obs", ".ob-s", "com.example.obs"):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(
                    ValueError, "TRACE_DEV_APP_ID_SUFFIX"):
                APK.application_id_suffix({APK.APPLICATION_ID_ENV: invalid})
        # 真实构建配置：未启用时生产包名不变，启用时只追加后缀。
        self.assertEqual("com.wen.gaia.gaia", APK.expected_application_id(ROOT, ""))
        self.assertEqual("com.wen.gaia.gaia.obs", APK.expected_application_id(ROOT, ".obs"))
        self.assertEqual("com.example.fixture.obs",
                         APK.expected_application_id(self.root, ".obs"))

    def test_apk_identity_is_read_from_the_artifact_not_the_build_intent(self):
        self.write(Path("run/apk-toolchain.json"), b'{"build_tools": "35.0.0"}\n')
        apk = self.root / APK.APK_RELATIVE
        calls = []

        def run(argv, **kwargs):
            calls.append(argv)
            return SimpleNamespace(
                returncode=0,
                stdout="package: name='com.example.fixture.obs' versionCode='86'\n",
            )

        self.assertEqual("com.example.fixture.obs",
                         APK.read_application_id(self.root, self.run, apk, run=run))
        self.assertEqual(Path(calls[0][0]), self.run / "android-sdk/build-tools/35.0.0/aapt2")
        self.assertEqual(["dump", "badging"], calls[0][1:3])
        def blank(*args, **kwargs):
            return SimpleNamespace(returncode=0, stdout="")

        with self.assertRaisesRegex(ValueError, "no package identity"):
            APK.read_application_id(self.root, self.run, apk, run=blank)

        def failed(*args, **kwargs):
            return SimpleNamespace(returncode=1, stdout="")

        with self.assertRaisesRegex(ValueError, "could not read the debug APK identity"):
            APK.read_application_id(self.root, self.run, apk, run=failed)

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
                         "platforms/android-35/android.jar", "build-tools/35.0.0/apksigner",
                         "build-tools/35.0.0/aapt2"):
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
        with mock.patch.object(APK, "read_application_id",
                               return_value="com.example.fixture"), \
                mock.patch("sys.stdout", new_callable=io.StringIO):
            APK.collect(self.root, self.run, "1" * 40, self.env)
        metadata = json.loads((self.run / "artifacts/trace-dev-debug.json").read_text())
        self.assertEqual(hashlib.sha256(data).hexdigest(), metadata["sha256"])
        self.assertEqual("1" * 40, metadata["commit"])
        self.assertEqual("com.example.fixture", metadata["application_id"])
        self.assertFalse(metadata["release_signing"])
        self.assertEqual("NOT_RUN", metadata["formal_acceptance"])
        self.assertEqual(data, (self.run / "artifacts/trace-dev-debug.apk").read_bytes())

    def test_collect_rejects_an_apk_whose_real_application_id_differs(self):
        data = self.archive_bytes([("AndroidManifest.xml", b"fixture, not a real APK manifest")])
        self.write(APK.APK_RELATIVE, data)
        env = {**self.env, APK.APPLICATION_ID_ENV: ".obs"}
        with mock.patch.object(APK, "read_application_id",
                               return_value="com.example.fixture"), \
                self.assertRaisesRegex(ValueError, "expected com.example.fixture.obs"):
            APK.collect(self.root, self.run, "1" * 40, env)
        self.assertFalse((self.run / "artifacts").exists())

    def test_missing_apk_or_commit_cannot_be_reported_as_generated(self):
        with self.assertRaisesRegex(ValueError, "missing or empty"):
            APK.collect(self.root, self.run, "1" * 40, self.env)
        self.write(APK.APK_RELATIVE, self.archive_bytes([("AndroidManifest.xml", b"fixture")]))
        with self.assertRaisesRegex(ValueError, "exact tested commit"):
            APK.collect(self.root, self.run, "", self.env)
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

    def observation_env(self):
        """显式启用的设备观测构建环境（不含任何凭据）。"""
        return {
            **self.env,
            APK.DEVICE_OBSERVATION_ENV: "true",
            APK.OBSERVATION_TARGET_ENV: "XTrace",
            APK.OBSERVATION_FIRMWARE_URL_ENV:
                "https://example.pages.dev/api/public/firmware/latest",
        }

    def test_device_observation_is_opt_in_and_absent_by_default(self):
        # 未设置 / 空 / 显式 false 一律等于"不观测"，且不注入任何 dart-define。
        for env in ({}, {APK.DEVICE_OBSERVATION_ENV: "   "},
                    {APK.DEVICE_OBSERVATION_ENV: "false"}):
            with self.subTest(env=env):
                self.assertIsNone(APK.observation_config(env))
        self.assertEqual([], APK.observation_defines(None))
        plan = APK.plan(self.root, self.run, self.env)
        build = next(argv for name, argv, _, _ in plan if name == "apk_build")
        self.assertFalse([arg for arg in build if arg.startswith("--dart-define")])

    def test_device_observation_injection_reaches_the_build_command(self):
        env = self.observation_env()
        config = APK.observation_config(env)
        self.assertEqual("XTrace", config["target"])
        self.assertEqual(env[APK.OBSERVATION_FIRMWARE_URL_ENV],
                         config["firmware_latest_url"])
        self.assertTrue(config["sentinel"].startswith(APK.OBSERVATION_SENTINEL_PREFIX))
        # 指纹只由 (target, url) 决定：键序与开关写法（含大小写/空白）不改变它，
        # 运行期日志里的 sentinel 才能与 CI 记录一一对上。
        self.assertEqual(config["sentinel"], APK.observation_config({
            APK.OBSERVATION_FIRMWARE_URL_ENV: env[APK.OBSERVATION_FIRMWARE_URL_ENV],
            APK.DEVICE_OBSERVATION_ENV: "  TRUE  ",
            APK.OBSERVATION_TARGET_ENV: "XTrace",
        })["sentinel"])
        plan = APK.plan(self.root, self.run, env)
        build = next(argv for name, argv, _, _ in plan if name == "apk_build")
        for expected in (
            f"--dart-define={APK.DEVICE_OBSERVATION_ENV}=true",
            f"--dart-define={APK.OBSERVATION_TARGET_ENV}=XTrace",
            f"--dart-define={APK.OBSERVATION_SENTINEL_ENV}={config['sentinel']}",
            "--dart-define=TRACE_CLOUDFLARE_FIRMWARE_LATEST_URL="
            + env[APK.OBSERVATION_FIRMWARE_URL_ENV],
        ):
            self.assertIn(expected, build)
        self.assertIn("--debug", build)

    def test_device_observation_rejects_incomplete_or_credentialed_config(self):
        base = {
            APK.DEVICE_OBSERVATION_ENV: "true",
            APK.OBSERVATION_TARGET_ENV: "XTrace",
            APK.OBSERVATION_FIRMWARE_URL_ENV: "https://example.pages.dev/latest",
        }
        cases = [
            # 启用后缺 target / 缺地址：不许"半配置"进入构建。
            ({**base, APK.OBSERVATION_TARGET_ENV: ""}, "TRACE_DEV_OBSERVATION_TARGET"),
            ({**base, APK.OBSERVATION_TARGET_ENV: "有中文"}, "TRACE_DEV_OBSERVATION_TARGET"),
            ({**base, APK.OBSERVATION_FIRMWARE_URL_ENV: ""},
             "TRACE_DEV_OBSERVATION_FIRMWARE_LATEST_URL"),
            # 只允许不含凭据的公开 HTTPS 地址。
            ({**base, APK.OBSERVATION_FIRMWARE_URL_ENV: "http://example.pages.dev/latest"},
             "credential-free public https"),
            ({**base, APK.OBSERVATION_FIRMWARE_URL_ENV: "https://u:p@example.pages.dev/latest"},
             "credential-free public https"),
            ({**base, APK.OBSERVATION_FIRMWARE_URL_ENV:
                "https://example.pages.dev/latest?token=fixture"},
             "must not carry credentials"),
            ({**base, APK.OBSERVATION_FIRMWARE_URL_ENV:
                "https://example.pages.dev/latest#fixture"},
             "must not carry credentials"),
            # 开关取值只认 true：含糊的取值不许被当成"已启用"。
            ({APK.DEVICE_OBSERVATION_ENV: "yes"}, "must be exactly"),
        ]
        for env, message in cases:
            with self.subTest(env=env), self.assertRaisesRegex(ValueError, message):
                APK.observation_config(env)
        # 非法配置在构建计划阶段就失败，不会先下载 Gradle 再报错。
        with self.assertRaisesRegex(ValueError, "TRACE_DEV_OBSERVATION_TARGET"):
            APK.plan(self.root, self.run, {**base, APK.OBSERVATION_TARGET_ENV: ""})

    def test_device_observation_rejects_encoded_and_disguised_credential_keys(self):
        """OBS-SEC-01 回归：编码键名、大小写、token 别名与未知参数都不得绕过。

        独立复核 §6.18 证实旧实现对原始 query 做黑名单正则，`%74oken`、
        `sign%61ture`、`access_token` 被放行并进入 defines/collect。凭据
        判定必须在百分号解码与大小写规范化之后进行。
        """
        base = {
            APK.DEVICE_OBSERVATION_ENV: "true",
            APK.OBSERVATION_TARGET_ENV: "XTrace",
        }
        rejects = [
            # §6.18 真实负例：百分号编码的凭据键名。
            "https://example.pages.dev/latest?%74oken=fixture-only",
            "https://example.pages.dev/latest?sign%61ture=fixture-only",
            "https://example.pages.dev/latest?access_token=fixture-only",
            # 大小写与连字符/下划线别名。
            "https://example.pages.dev/latest?TOKEN=fixture-only",
            "https://example.pages.dev/latest?Api-Key=fixture-only",
            # 双重编码（解码一次仍是 %74oken，非白名单键）。
            "https://example.pages.dev/latest?%2574oken=fixture-only",
            # 白名单外的未知键：观测 URL 是"配置公开端点"，不承载未知参数。
            "https://example.pages.dev/latest?unknown_param=1",
            # 凭据藏进白名单键的取值里（解码后为 bearer-x）。
            "https://example.pages.dev/latest?appid=be%61rer-x",
            "https://example.pages.dev/latest?appid=signature",
            "https://example.pages.dev/latest?appid=%74oken",
            # 短别名与空值凭据键。
            "https://example.pages.dev/latest?sig=abc",
            "https://example.pages.dev/latest?token=",
            "https://example.pages.dev/latest?password=fixture",
            "https://example.pages.dev/latest?auth=fixture",
        ]
        for url in rejects:
            with self.subTest(url=url), \
                    self.assertRaisesRegex(ValueError, "must not carry credentials"):
                APK.observation_config({**base, APK.OBSERVATION_FIRMWARE_URL_ENV: url})
        # 正常无凭据端点（含白名单公开参数、大小写、重复参数）仍然可用。
        accepts = [
            "https://example.pages.dev/latest",
            "https://example.pages.dev/latest?appId=x&channel=stable",
            "https://example.pages.dev/latest?appId=x&channel=stable&channel=beta",
            "https://example.pages.dev/latest?deviceModel=M1&currentVersionCode=5",
            "https://example.pages.dev/latest?currentimagesha=" + "a" * 64,
            "https://example.pages.dev/latest?appId=",
        ]
        for url in accepts:
            with self.subTest(url=url):
                config = APK.observation_config(
                    {**base, APK.OBSERVATION_FIRMWARE_URL_ENV: url})
                self.assertEqual(url, config["firmware_latest_url"])
        # 拒绝原因带具体键名，方便 CI 日志定位；编码键名报解码后的名字。
        with self.assertRaisesRegex(
            ValueError, r"credential query parameter 'token'",
        ):
            APK.observation_config({
                **base,
                APK.OBSERVATION_FIRMWARE_URL_ENV:
                    "https://example.pages.dev/latest?%74oken=fixture-only",
            })
        with self.assertRaisesRegex(
            ValueError, r"unexpected query parameter 'unknown_param'",
        ):
            APK.observation_config({
                **base,
                APK.OBSERVATION_FIRMWARE_URL_ENV:
                    "https://example.pages.dev/latest?unknown_param=1",
            })

    def test_collect_refuses_an_apk_without_the_injected_observation_constants(self):
        env = self.observation_env()
        config = APK.observation_config(env)
        constants = {
            "sentinel": config["sentinel"],
            "url": config["firmware_latest_url"],
            "target": config["target"],
        }
        for missing in constants:
            with self.subTest(missing=missing):
                blob = "".join(
                    value for name, value in constants.items() if name != missing
                ).encode("utf-8")
                self.write(APK.APK_RELATIVE, self.archive_bytes([
                    ("AndroidManifest.xml", b"fixture, not a real APK manifest"),
                    (APK.KERNEL_BLOB, blob),
                ]))
                with mock.patch.object(APK, "read_application_id",
                                       return_value="com.example.fixture"), \
                        self.assertRaisesRegex(ValueError, "not observation-ready"):
                    APK.collect(self.root, self.run, "1" * 40, env)
                self.assertFalse((self.run / "artifacts").exists())
        # 没有 kernel blob 同样拒绝：不能"读不到就不检查"。
        self.write(APK.APK_RELATIVE, self.archive_bytes([
            ("AndroidManifest.xml", b"fixture, not a real APK manifest"),
        ]))
        with mock.patch.object(APK, "read_application_id",
                               return_value="com.example.fixture"), \
                self.assertRaisesRegex(ValueError, "no Dart kernel blob"):
            APK.collect(self.root, self.run, "1" * 40, env)
        self.assertFalse((self.run / "artifacts").exists())

    def test_collect_records_the_verified_observation_configuration(self):
        env = self.observation_env()
        config = APK.observation_config(env)
        blob = ("".join(config.values())).encode("utf-8")
        self.write(APK.APK_RELATIVE, self.archive_bytes([
            ("AndroidManifest.xml", b"fixture, not a real APK manifest"),
            (APK.KERNEL_BLOB, blob),
        ]))
        with mock.patch.object(APK, "read_application_id",
                               return_value="com.example.fixture"), \
                mock.patch("sys.stdout", new_callable=io.StringIO):
            APK.collect(self.root, self.run, "1" * 40, env)
        metadata = json.loads((self.run / "artifacts/trace-dev-debug.json").read_text())
        observed = metadata["device_observation"]
        self.assertTrue(observed["enabled"])
        self.assertEqual("XTrace", observed["target"])
        self.assertEqual(config["sentinel"], observed["sentinel"])
        self.assertEqual(config["firmware_latest_url"], observed["firmware_latest_url"])

    def test_collect_without_observation_keeps_the_previous_metadata(self):
        data = self.archive_bytes([("AndroidManifest.xml", b"fixture")])
        self.write(APK.APK_RELATIVE, data)
        with mock.patch.object(APK, "read_application_id",
                               return_value="com.example.fixture"), \
                mock.patch("sys.stdout", new_callable=io.StringIO):
            APK.collect(self.root, self.run, "1" * 40, self.env)
        metadata = json.loads((self.run / "artifacts/trace-dev-debug.json").read_text())
        self.assertNotIn("device_observation", metadata)

    def test_cli_never_builds_or_downloads_locally(self):
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}), \
                mock.patch.object(APK, "prepare") as prepare, \
                mock.patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit):
            APK.main(["prepare", "--repo-root", str(self.root), "--run-dir", str(self.run)])
        prepare.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
