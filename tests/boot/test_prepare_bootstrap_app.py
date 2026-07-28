#!/usr/bin/env python3
"""Host checks for the tool-only P1-5 deployment utilities."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "Tools" / "jlink" / "prepare-bootstrap-app.py"
JLINK_COMMON = ROOT / "Tools" / "jlink" / "jlink-common.ps1"
DEPLOY = ROOT / "Tools" / "jlink" / "deploy-ota-bootstrap.ps1"
RECOVERY_FLASH = ROOT / "Tools" / "jlink" / "flash-recovery-container.ps1"
LAYOUT_TEXT = (ROOT / "Libraries/OTA/ota_layout.h").read_text(encoding="ascii")


def parse_layout_macro(name: str) -> int:
    match = re.search(
        rf"(?m)^\s*#define\s+{re.escape(name)}\s+(0x[0-9A-Fa-f]+|[0-9]+)\s*$",
        LAYOUT_TEXT,
    )
    if match is None:
        raise AssertionError(f"layout macro is absent or non-literal: {name}")
    return int(match.group(1), 0)


FW_OFFSET = parse_layout_macro("OTA_FW_HEADER_OFFSET")
FW_SIZE = parse_layout_macro("OTA_FW_HEADER_SIZE")
APP_ORIGIN = parse_layout_macro("OTA_APP_ORIGIN")
RAM_END = parse_layout_macro("OTA_OVERLAY_ORIGIN") + parse_layout_macro(
    "OTA_OVERLAY_LENGTH"
)
IMAGE_LENGTH = FW_OFFSET + 0x200


class FlatWorkspace:
    def __init__(self) -> None:
        self.cache = ROOT / ".cache"
        self.cache.mkdir(exist_ok=True)
        self.prefix = f"p1-5-tool-{os.getpid()}"
        self.paths: list[Path] = []

    def track(self, path: Path) -> Path:
        if path not in self.paths:
            self.paths.append(path)
        return path

    def __truediv__(self, name: str) -> Path:
        return self.track(self.cache / f"{self.prefix}-{name}")

    def __enter__(self) -> FlatWorkspace:
        return self

    def __exit__(self, *_: object) -> None:
        for path in reversed(self.paths):
            path.unlink(missing_ok=True)


def run(*args: str, expect: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(TOOL), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != expect:
        raise AssertionError(
            f"unexpected exit {result.returncode} (expected {expect})\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


def ps_quote(path: Path) -> str:
    return str(path.resolve()).replace("'", "''")


def run_powershell(
    executable: str, script: str, expect: int = 0
) -> subprocess.CompletedProcess[str]:
    script = "Import-Module Microsoft.PowerShell.Utility; " + script
    result = subprocess.run(
        [executable, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != expect:
        raise AssertionError(
            f"unexpected PowerShell exit {result.returncode} (expected {expect})\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


def make_image() -> bytes:
    image = bytearray((index * 17 + 3) & 0xFF for index in range(IMAGE_LENGTH))
    struct.pack_into("<I", image, 0, RAM_END)
    struct.pack_into("<I", image, 4, APP_ORIGIN + 0x101)
    header = bytearray(FW_SIZE)
    header[0:4] = b"ETFW"
    struct.pack_into("<II", header, 4, 1, 20800)
    header[12:28] = b"2.8.0\x00" + bytes(10)
    struct.pack_into("<III", header, 28, 1720000000, 1, IMAGE_LENGTH)
    header[72:74] = bytes((1, 1))
    header[74:92] = bytes([0xFF]) * 18
    image[FW_OFFSET : FW_OFFSET + FW_SIZE] = header
    digest_image = bytearray(image)
    digest_image[FW_OFFSET + 40 : FW_OFFSET + 72] = bytes(32)
    digest_image[FW_OFFSET + 92 : FW_OFFSET + 96] = bytes(4)
    image[FW_OFFSET + 40 : FW_OFFSET + 72] = hashlib.sha256(digest_image).digest()
    struct.pack_into(
        "<I", image, FW_OFFSET + 92, zlib.crc32(image[FW_OFFSET : FW_OFFSET + 92])
    )
    return bytes(image)


def make_recovery(image: bytes) -> bytes:
    return image + struct.pack("<II", len(image), zlib.crc32(image) & 0xFFFFFFFF)


def main() -> int:
    checks = 0
    common_text = JLINK_COMMON.read_text(encoding="ascii")
    deploy_text = DEPLOY.read_text(encoding="ascii")
    recovery_flash_text = RECOVERY_FLASH.read_text(encoding="ascii")
    combined_scripts = common_text + deploy_text + recovery_flash_text

    assert "Invoke-P1BootstrapCommand" not in combined_scripts
    assert "InstallRecovery" not in deploy_text
    assert "Assert-P1NormalResetEvidence" in common_text
    assert "repo-default-hex" in deploy_text and "selected-legacy" in deploy_text
    assert "CFSR is nonzero" in common_text
    assert deploy_text.count("-WaitMilliseconds 90000") == 2
    assert deploy_text.count("-TimeoutSeconds 30") == 2
    assert "Format-P1NormalResetPassLine" in common_text
    assert "Format-P1NormalResetPassLine" in deploy_text
    assert "Format-P1RecoveryFlashPassLine" in common_text
    assert "Format-P1RecoveryFlashPassLine" in recovery_flash_text
    assert not (ROOT / "boot" / "include" / "boot_bootstrap.h").exists()
    assert not (ROOT / "boot" / "src" / "boot_bootstrap.c").exists()
    checks += 13

    with FlatWorkspace() as work:
        image = make_image()
        recovery_bytes = make_recovery(image)
        app = work / "app.bin"
        prepared = work / "prepared.bin"
        recovery = work / "recovery.bin"
        app.write_bytes(image)

        result = run(
            "prepare",
            "--input",
            str(app),
            "--input-kind",
            "app",
            "--output",
            str(prepared),
            "--recovery-output",
            str(recovery),
        )
        assert "P1_5_APP_PREPARE=PASS" in result.stdout
        assert "source_preserved=1" in result.stdout
        assert prepared.read_bytes() == image
        assert recovery.read_bytes() == recovery_bytes
        assert app.read_bytes() == image
        checks += 5

        result = run("verify", "--input", str(app), "--input-kind", "app")
        assert "kind=app" in result.stdout
        result = run("verify", "--input", str(recovery), "--input-kind", "recovery")
        assert "kind=recovery" in result.stdout
        checks += 2

        auto_prepared = work / "auto-prepared.bin"
        run(
            "prepare",
            "--input",
            str(recovery),
            "--input-kind",
            "auto",
            "--output",
            str(auto_prepared),
        )
        assert auto_prepared.read_bytes() == image
        assert recovery.read_bytes() == recovery_bytes
        checks += 2

        bad_recovery = work / "bad-recovery.bin"
        bad_recovery.write_bytes(recovery_bytes[:-1] + b"\x00")
        result = run(
            "verify",
            "--input",
            str(bad_recovery),
            "--input-kind",
            "recovery",
            expect=1,
        )
        assert "recovery trailer" in result.stderr
        checks += 1

        bad_header = work / "bad-header.bin"
        corrupted = bytearray(image)
        corrupted[FW_OFFSET] ^= 0xFF
        bad_header.write_bytes(corrupted)
        result = run(
            "verify",
            "--input",
            str(bad_header),
            "--input-kind",
            "app",
            expect=1,
        )
        assert "fw_header magic" in result.stderr
        checks += 1

        app_before = app.read_bytes()
        result = run(
            "prepare",
            "--input",
            str(app),
            "--input-kind",
            "app",
            "--output",
            str(app),
            expect=1,
        )
        assert "input and output paths must differ" in result.stderr
        assert app.read_bytes() == app_before
        checks += 2

        recovery_before = recovery.read_bytes()
        result = run(
            "prepare",
            "--input",
            str(recovery),
            "--input-kind",
            "recovery",
            "--output",
            str(recovery),
            expect=1,
        )
        assert "input and output paths must differ" in result.stderr
        assert recovery.read_bytes() == recovery_before
        checks += 2

        collision_output = work / "collision-output.bin"
        result = run(
            "prepare",
            "--input",
            str(recovery),
            "--input-kind",
            "recovery",
            "--output",
            str(collision_output),
            "--recovery-output",
            str(recovery),
            expect=1,
        )
        assert "recovery output must differ from input" in result.stderr
        assert not collision_output.exists()
        assert recovery.read_bytes() == recovery_before
        checks += 3

        same_outputs = work / "same-output.bin"
        result = run(
            "prepare",
            "--input",
            str(app),
            "--input-kind",
            "app",
            "--output",
            str(same_outputs),
            "--recovery-output",
            str(same_outputs),
            expect=1,
        )
        assert "recovery output must differ from App output" in result.stderr
        assert not same_outputs.exists()
        checks += 2

        result = run("command", expect=2)
        assert "invalid choice" in result.stderr
        checks += 1

        powershell = shutil.which("powershell.exe") or shutil.which("pwsh")
        powershell_checks = 0
        if powershell is not None:
            common = ps_quote(JLINK_COMMON)
            good_log = work / "reset-good.log"
            bad_cfsr_log = work / "reset-bad-cfsr.log"
            bad_pc_log = work / "reset-bad-pc.log"
            good_log.write_text(
                "PC = 08000020, CycleCnt = 00000000\n"
                "PC = 08012345, CycleCnt = 00000001\n"
                "E000ED08 = 08010000\n"
                "E000ED28 = 00000000\n",
                encoding="ascii",
            )
            bad_cfsr_log.write_text(
                good_log.read_text(encoding="ascii").replace(
                    "E000ED28 = 00000000", "E000ED28 = 00010000"
                ),
                encoding="ascii",
            )
            bad_pc_log.write_text(
                good_log.read_text(encoding="ascii").replace(
                    "PC = 08012345", "PC = 08000010"
                ),
                encoding="ascii",
            )

            script = (
                f"$ErrorActionPreference='Stop'; . '{common}'; "
                f"$e=Assert-P1NormalResetEvidence -LogPath '{ps_quote(good_log)}'; "
                "if($e.PC -ne 0x08012345 -or $e.VTOR -ne 0x08010000 "
                "-or $e.CFSR -ne 0){throw 'parsed evidence mismatch'}"
            )
            run_powershell(powershell, script)
            powershell_checks += 1

            script = (
                f"$ErrorActionPreference='Stop'; . '{common}'; "
                "$line=Format-P1NormalResetPassLine "
                "-PC 0x08012345 -VTOR 0x08010000 -CFSR 0 "
                "-FinalPC 0x08023456 -FinalVTOR 0x08010000 -FinalCFSR 0 "
                "-RttAddress 0x20044E04 -CurVcode '20802'; "
                "$expected='P1_5_NORMAL_RESET=PASS pc=0x08012345 "
                "vtor=0x08010000 cfsr=0x00000000 final_pc=0x08023456 "
                "final_vtor=0x08010000 final_cfsr=0x00000000 "
                "rtt=0x20044E04 cur_vcode=20802'; "
                "if($line -ne $expected){throw \"normal reset line mismatch: $line\"}"
            )
            run_powershell(powershell, script)
            powershell_checks += 1

            script = (
                f"$ErrorActionPreference='Stop'; . '{common}'; "
                "$line=Format-P1RecoveryFlashPassLine "
                "-Container 'recovery.bin' -StrippedApp 'app.bin' "
                "-PC 0x08034567 -VTOR 0x08010000 -CFSR 0 "
                "-RttAddress 0x20044E04; "
                "$expected='P1_5_RECOVERY_FLASH=PASS container=recovery.bin "
                "stripped=app.bin pc=0x08034567 vtor=0x08010000 "
                "cfsr=0x00000000 rtt=0x20044E04 source_preserved=1'; "
                "if($line -ne $expected){throw \"recovery line mismatch: $line\"}"
            )
            run_powershell(powershell, script)
            powershell_checks += 1

            result = run_powershell(
                powershell,
                f"$ErrorActionPreference='Stop'; . '{common}'; "
                f"Assert-P1NormalResetEvidence -LogPath '{ps_quote(bad_cfsr_log)}'",
                expect=1,
            )
            assert "CFSR is nonzero" in (result.stdout + result.stderr)
            powershell_checks += 1

            result = run_powershell(
                powershell,
                f"$ErrorActionPreference='Stop'; . '{common}'; "
                f"Assert-P1NormalResetEvidence -LogPath '{ps_quote(bad_pc_log)}'",
                expect=1,
            )
            assert "outside the App partition" in (result.stdout + result.stderr)
            powershell_checks += 1

            collision_name = f"p1-5-legacy-collision-{os.getpid()}.hex"
            selected = work.track(ROOT / ".cache" / collision_name)
            repository_default = work.track(
                ROOT / "Tools" / "jlink" / collision_name
            )
            preserved_dir = ROOT / ".cache"
            selected.write_bytes(b"SELECTED-LEGACY")
            repository_default.write_bytes(b"REPOSITORY-DEFAULT")
            selected_hash = hashlib.sha256(selected.read_bytes()).hexdigest()
            default_hash = hashlib.sha256(repository_default.read_bytes()).hexdigest()
            selected_copy = work.track(
                preserved_dir
                / f"selected-legacy-{selected_hash}-{collision_name}"
            )
            default_copy = work.track(
                preserved_dir
                / f"repo-default-hex-{default_hash}-{collision_name}"
            )
            script = (
                f"$ErrorActionPreference='Stop'; . '{common}'; "
                f"Copy-P1PreservedArtifact -SourcePath '{ps_quote(selected)}' "
                f"-DestinationDirectory '{ps_quote(preserved_dir)}' "
                "-Role 'selected-legacy' | Out-Null; "
                f"Copy-P1PreservedArtifact -SourcePath '{ps_quote(repository_default)}' "
                f"-DestinationDirectory '{ps_quote(preserved_dir)}' "
                "-Role 'repo-default-hex' | Out-Null"
            )
            run_powershell(powershell, script)
            assert selected_copy.exists() and default_copy.exists()
            assert selected_copy.read_bytes() == b"SELECTED-LEGACY"
            assert default_copy.read_bytes() == b"REPOSITORY-DEFAULT"
            powershell_checks += 3

        checks += powershell_checks
        print(
            f"P1_5_PREPARE_TOOL=PASS checks={checks} "
            f"powershell_checks={powershell_checks}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
