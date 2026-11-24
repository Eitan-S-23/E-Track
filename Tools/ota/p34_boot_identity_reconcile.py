"""Bind the native identity checker to the verified replacement Boot only."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_boot_entry_reconcile as previous

OUT = ROOT / ".cache/p34-boot/identity-fix"
BASE = ROOT / ".cache/p34-boot/entry-fix/result.json"


def run():
    store = cli.Store(ROOT)
    cli.require(not store.checked(OUT).exists(), "preserve prior identity tests")
    base = store.read(BASE)
    cli.require(base["passed"] and base["tests"] == 351, "prior entry repair missing")
    for key in ("proof", "targeted", "targeted_log", "console"):
        cli.require(cli.record(base[key]["path"]) == base[key], "prior evidence changed")
    patches = {
        ROOT / "Tools/ota/p34_session_backend.py":
            b'                if api.group == cli.BOOT_COPY_GROUP:\n'
            b'                    self.BOOT_SHA = self.bindings["whole_boot"]["sha256"]\n',
        ROOT / "tests/ota/test_p34_boot_ota.py":
            b'        self.assertEqual(c.BOOT_SHA, M.BOOT_SHA)\n'
            b'        self.assertEqual(api.legacy["core"]["Context"].BOOT_SHA, M.device.BOOT_SHA)\n',
    }
    changed = [item for item in base["sources"] if cli.record(item["path"]) != item]
    cli.require({Path(item["path"]) for item in changed} == set(patches), "unexpected changed inputs")
    for item in changed:
        path = Path(item["path"])
        raw = path.read_bytes()
        cli.require(raw.count(patches[path]) == 1, "unexpected identity repair")
        old = raw.replace(patches[path], b"")
        cli.require(len(old) == item["bytes"] and hashlib.sha256(old).hexdigest() == item["sha256"],
                    "prior source does not reconstruct exactly")
    sources = [cli.record(item["path"]) for item in base["sources"]]
    for leaf in ("targeted.log", "targeted.json", "console.log", "proof.json", "result.json"):
        store.checked(OUT / leaf)
    env = dict(os.environ, P34_TEST_OUT=str(OUT))
    for key in ("TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA"):
        p = store.checked(OUT / "host" / key.lower())
        p.mkdir(parents=True, exist_ok=True)
        env[key] = str(p)
    store.write(OUT / "proof.json", dict(base=cli.record(BASE), sources=sources, prior_sources=changed,
        exact_prior_reconstruction=True, scope="Only verified Boot-copy Context instance receives new BOOT_SHA; "
        "old-group inherited value is unchanged. Retest all Boot integration and start guards."))
    command = [sys.executable, "-I", "-S", "-B", "-X", "utf8", str(Path(__file__)), "child"]
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=240,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    store.raw(OUT / "console.log", result.stdout + result.stderr)
    fresh = store.read(OUT / "targeted.json")
    cli.require(result.returncode == 0 and fresh["passed"] and fresh["tests"] == 8 and fresh["skipped"] == 0 and
                set(fresh["ids"]) == set(base["fresh_ids"]), "identity checks failed or coverage changed")
    cli.require(all(cli.record(item["path"]) == item for item in sources), "source changed during checks")
    value = dict(base, sources=sources, proof=cli.record(OUT / "proof.json"),
        targeted=cli.record(OUT / "targeted.json"), targeted_log=cli.record(OUT / "targeted.log"),
        console=cli.record(OUT / "console.log"))
    store.write(OUT / "result.json", value)
    store.write(store.base / "tests/latest.json", value, replace=True)
    print("PASS: bound native Boot hash; 8 executed + 343 unchanged original PASS; coverage351")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    if sys.argv[1:] == ["child"]:
        previous.OUT = OUT
        raise SystemExit(previous.child())
    cli.require(not sys.argv[1:], "unexpected arguments")
    run()
