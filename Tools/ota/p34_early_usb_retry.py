"""Preserve ready-media capacity after I/O failure in a fresh EARLY-05 revision."""
import argparse
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_early_usb_gate as gate

OLD = gate.AREA
AREA = ROOT / ".cache/p34-early-usb-r2"
BEFORE = "if(lun < MSC_SUPPORT_MAX_LUN)"
AFTER = "if(lun < MSC_SUPPORT_MAX_LUN && key == SENSE_KEY_NOT_READY)"
EXTRA = '''
    for (uint8_t command : {uint8_t(MSC_CMD_READ_10), uint8_t(MSC_CMD_WRITE_10)}) {
        Fixture f(true, 8192); f.prime(); io_ok = false; f.command(command);
        if (command == MSC_CMD_WRITE_10) bot_scsi_dataout_handler(&f.device, 1);
        assert(f.state.blk_nbr[0] == 8192 && f.state.blk_size[0] == 512);
        io_ok = true; f.command(command);
        if (command == MSC_CMD_WRITE_10) bot_scsi_dataout_handler(&f.device, 1);
        else bot_scsi_datain_handler(&f.device, 1);
        assert(passed_csw == 1 && f.state.csw_struct.dCSWDataResidue == 0);
        assert(command == MSC_CMD_READ_10 ? reads == 2 : writes == 2);
        ++cases;
    }
'''


def prepare(store):
    cli = gate.early.model.cli
    cli.require(not AREA.exists(), "preserve revision")
    previous = store.read(OLD / "prepared.json")
    for record in previous["sources"] + previous["implementation"]:
        cli.require(cli.record(record["path"]) == record, "input drift")
    copies = [(Path(r["path"]), store.checked(AREA / "f" / Path(r["path"]).relative_to(OLD / "f")))
              for r in previous["sources"]]
    for name in ("prepared.json", "off2/result.json", "control-reuse.json"):
        store.checked(AREA / name)
    for source, target in copies:
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.relative_to(OLD / "f").as_posix() == gate.BOT:
            text = source.read_text(encoding="utf-8")
            cli.require(text.count(BEFORE) == 1, "unique helper required")
            target.write_text(text.replace(BEFORE, AFTER), encoding="utf-8", newline="\n")
        else:
            shutil.copyfile(source, target)
    # Exact original receipt, not a claim that an OFF build ran in this directory.
    # The only delta is inside an ON-and-SD-only helper; original OFF anchor is retained.
    original_control = OLD / "off2/result.json"
    cli.require(store.read(original_control)["baseline_identical"], "original OFF reproduction required")
    store.raw(AREA / "off2/result.json", original_control.read_bytes())
    store.write(AREA / "control-reuse.json", dict(original=cli.record(original_control),
        executed_here=False, reason="Only p34_msc_failure ON/SD helper predicate changes; OFF excludes the entire helper",
        original_binary=cli.record(OLD / "off2/b/app-gcc/X-Track-App-GCC.bin")))
    store.write(AREA / "prepared.json", dict(base=cli.record(OLD / "prepared.json"), entries=previous["entries"],
        sources=[cli.record(p) for p in sorted((AREA / "f").rglob("*")) if p.is_file()],
        implementation=[cli.record(Path(__file__)), cli.record(Path(gate.__file__)),
                        cli.record(ROOT / "tests/boot/test_p34_early_usb_gate.cpp")],
        changed=[gate.BOT], hardware=False))
    print("EARLY_USB_R2_PREPARED original OFF receipt reused, not reexecuted")


def tests(store):
    cli, host = gate.early.model.cli, gate.early.model.host
    prepared = store.read(AREA / "prepared.json")
    for record in prepared["sources"] + prepared["implementation"]:
        cli.require(cli.record(record["path"]) == record, "source drift")
    out = store.checked(AREA / "tests")
    cli.require(not out.exists(), "preserve tests")
    for name in ("types.inc", "functions.inc", "retry.cpp", "gate.exe", "compile.json", "compile.log", "run.json", "run.log", "result.json"):
        store.checked(out / name)
    for key in ("home", "userprofile", "appdata", "localappdata", "temp", "tmp", "tmpdir", "xdg_cache_home",
                "xdg_config_home", "xdg_data_home", "pythonuserbase", "pythonpycacheprefix", "ccache_dir", "sccache_dir"):
        store.checked(out / "host" / key)
    old_tests = store.read(OLD / "tests/result.json")
    for record in old_tests["inputs"]:
        cli.require(cli.record(record["path"]) == record, "old host evidence drift")
    env = host.environment(store, out)
    store.raw(out / "types.inc", (OLD / "tests/types.inc").read_bytes())
    functions = (OLD / "tests/functions.inc").read_text().replace(BEFORE, AFTER)
    target = (AREA / "f" / gate.BOT).read_text(encoding="utf-8")
    cli.require(gate.function(functions, "p34_msc_failure") == gate.function(target, "p34_msc_failure"), "extraction mismatch")
    store.raw(out / "functions.inc", functions.encode())
    template = ROOT / "tests/boot/test_p34_early_usb_gate.cpp"
    text = template.read_text()
    marker = '    std::printf("EARLY_USB_GATE_PASS cases=%u\\n", cases);'
    cli.require(text.count(marker) == 1, "host extension anchor")
    store.raw(out / "retry.cpp", text.replace(marker, EXTRA + marker).encode())
    host.command(store, out, "compile", ["D:/install/mingw64/bin/g++.exe", "-std=c++11", "-O2", "-Wall", "-Werror",
                 "-I" + str(out), out / "retry.cpp", "-o", out / "gate.exe"], env, 60)
    log = host.command(store, out, "run", [out / "gate.exe"], env, 60)
    cli.require(b"EARLY_USB_GATE_PASS cases=42" in log, "retry regression missing")
    inputs = [Path(__file__), template, AREA / "prepared.json", OLD / "tests/result.json"]
    inputs += [out / n for n in ("types.inc", "functions.inc", "retry.cpp", "gate.exe", "compile.json", "compile.log", "run.json", "run.log")]
    store.write(out / "result.json", dict(result="EARLY_HOST_PASS", inputs=[cli.record(p) for p in inputs],
        output=log.decode(), scope="40 original cases plus successful read/write retries after ready-media I/O failure",
        hardware=False, independent_acceptance=False))
    print(log.decode().strip())


if __name__ == "__main__":
    gate.early.model.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                                "isolated root required")
    parser = argparse.ArgumentParser(); parser.add_argument("action", choices=("prepare", "tests", "on"))
    action = parser.parse_args().action
    if action == "on":
        gate.early.AREA = AREA
        gate.builder.main("on")
    else:
        {"prepare": prepare, "tests": tests}[action](gate.early.model.cli.Store(ROOT))
