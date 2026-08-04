#!/usr/bin/env python3
"""Exercise OtaUpdate::Session against SdFat-style cached file handles."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]


def compile_test(build_dir: Path, executable: Path) -> None:
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    cxx = shutil.which("c++") or shutil.which("g++") or shutil.which("clang++")
    if not cc or not cxx:
        raise RuntimeError("A host C and C++ compiler are required")

    includes = [
        ROOT / "tests/ota/stubs",
        ROOT / "USER",
        ROOT / "USER/App",
        ROOT / "Libraries",
        ROOT / "boot/include",
    ]
    c_sources = [
        ROOT / "Libraries/OTA/ota_sd.c",
        ROOT / "Libraries/OTA/ota_staging.c",
        ROOT / "boot/src/boot_crc32.c",
        ROOT / "boot/src/boot_sha256.c",
    ]
    objects: list[Path] = []
    include_args = [f"-I{path}" for path in includes]

    for source in c_sources:
        output = build_dir / f"{source.stem}.o"
        subprocess.run(
            [
                cc,
                "-std=c99",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-O2",
                *include_args,
                "-c",
                str(source),
                "-o",
                str(output),
            ],
            cwd=ROOT,
            check=True,
        )
        objects.append(output)

    subprocess.run(
        [
            cxx,
            "-std=c++11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-O2",
            "-D_WIN32",
            *include_args,
            str(ROOT / "tests/ota/test_ota_update.cpp"),
            str(ROOT / "USER/App/Utils/OtaUpdate/OtaUpdate.cpp"),
            *[str(path) for path in objects],
            "-o",
            str(executable),
        ],
        cwd=ROOT,
        check=True,
    )


def main() -> int:
    cache_dir = ROOT / ".cache"
    cache_dir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="etrack-p2-4-ota-update-",
        dir=cache_dir,
        ignore_cleanup_errors=True,
    ) as temp_dir:
        build_dir = Path(temp_dir)
        replacement = build_dir / "replacement.etu"
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "Tools/etu_pack.py"),
                "pack-full",
                "--app",
                str(ROOT / "tests/ota-vectors/toy-new.bin"),
                "--out",
                str(replacement),
                "--target-vcode",
                "20800",
            ],
            cwd=ROOT,
            check=True,
        )

        executable = build_dir / "test_ota_update.exe"
        compile_test(build_dir, executable)
        original = ROOT / "tests/ota-vectors/toy-full.etu"
        for scenario in (
            "confirm-replace",
            "append",
            "truncate",
            "second-pass-replace",
            "unavailable",
            "stage-before-apply",
            "begin-non-confirmed",
        ):
            subprocess.run(
                [str(executable), scenario, str(original), str(replacement)],
                cwd=ROOT,
                check=True,
            )
        print("P2_4_OTA_UPDATE=PASS scenarios=7")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
