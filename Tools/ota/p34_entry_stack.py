"""Bind the selected RAM ELF to its offline load and complete stack checks."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_install_cost as host
from recovery_entry.stack_audit import analyze
from recovery_entry.load_contract import inspect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", default=".cache/p34-entry-supervisor2")
    parser.add_argument("--output-dir", default=".cache/p34-entry-stack1")
    args = parser.parse_args()
    cli = host.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site
                and sys.dont_write_bytecode, "isolated root required")
    store = cli.Store(ROOT)
    build, out = store.checked(ROOT / args.build), store.checked(ROOT / args.output_dir)
    cli.require(not out.exists(), "preserve prior evidence")
    result = json.loads((build / "result.json").read_text())
    for item in result["inputs"] + result["artifacts"]:
        cli.require(cli.record(item["path"]) == item, "build input/artifact drift")
    paths = [build / n for n in ("entry.elf", "symbols.log", "disassembly.log", "result.json")]
    su = sorted(build.glob("*.su"))
    paths += su + [Path(__file__), ROOT / "Tools/ota/recovery_entry/stack_audit.py",
                  ROOT / "Tools/ota/recovery_entry/load_contract.py", ROOT / "Tools/ota/p34_boot_stack.py"]
    before = [cli.record(p) for p in paths]
    elf = paths[0].read_bytes()
    load = inspect(elf)
    report = analyze(elf, paths[1].read_text(), paths[2].read_text(), [p.read_text() for p in su])
    cli.require(before == [cli.record(p) for p in paths], "analysis input changed")
    store.checked(out / "result.json")
    store.write(out / "result.json", dict(result="ENTRY_LINKED_STACK_CHECK_PASS", inputs=before,
        load=load, analysis=report, independent_acceptance=False))
    print(json.dumps(report["entries"], indent=2))


if __name__ == "__main__":
    main()
