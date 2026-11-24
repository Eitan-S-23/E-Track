"""Bind EARLY-05 native matrix to the isolated GCC OFF/ON artifacts."""
from pathlib import Path
import argparse
import difflib
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_early_usb_gate as gate
import p34_early_fault_validate as original


def order(assembly, expected):
    calls = [m[1] for m in re.finditer(r"\b(?:bl|b(?:\.[nw])?)\s+[0-9a-f]+ <([^>]+)>", assembly)]
    selected = [n for n in calls if n in expected]
    if selected != expected:
        raise ValueError("startup call order mismatch: " + repr(selected))
    return selected


def main(retry=False):
    cli = gate.early.model.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated root required")
    store = cli.Store(ROOT)
    area = gate.AREA
    control_area = area
    if retry:
        import p34_early_usb_retry as revision
        area = revision.AREA
    out = store.checked(area / "validation.json")
    diff_path = store.checked(area / "source-diff.patch")
    cli.require(not out.exists(), "preserve artifact validation")
    prepared = store.read(area / "prepared.json")
    previous = store.read(gate.OLD / "prepared.json")
    for record in prepared["sources"] + prepared["implementation"] + previous["sources"] + previous["implementation"]:
        cli.require(cli.record(record["path"]) == record, "source drift")
    before = {Path(r["path"]).relative_to(gate.OLD / "f").as_posix(): r["sha256"] for r in previous["sources"]}
    after = {Path(r["path"]).relative_to(area / "f").as_posix(): r["sha256"] for r in prepared["sources"]}
    cli.require(before.keys() == after.keys(), "unexpected source additions/deletions")
    differences = sorted(k for k in before if before[k] != after[k])
    cli.require(differences == sorted([gate.BOT, gate.HEADER, gate.DISK, "USER/HAL/HAL.cpp"]), "unapproved source scope")
    paths = [Path(__file__), Path(gate.__file__), Path(original.__file__), area / "prepared.json",
             gate.OLD / "prepared.json", area / "tests/result.json", gate.OLD / "usb-preinit1/result.json"]
    if retry:
        control_prepared = store.read(control_area / "prepared.json")
        control_sources = {Path(r["path"]).relative_to(control_area / "f").as_posix(): r["sha256"] for r in control_prepared["sources"]}
        cli.require(control_sources.keys() == after.keys(), "retry source inventory drift")
        cli.require([k for k in after if after[k] != control_sources[k]] == [gate.BOT], "retry scope drift")
        old_bot = (control_area / "f" / gate.BOT).read_text(encoding="utf-8")
        new_bot = (area / "f" / gate.BOT).read_text(encoding="utf-8")
        cli.require(gate.FAILURE in old_bot and old_bot.count(revision.BEFORE) == 1 and
                    new_bot == old_bot.replace(revision.BEFORE, revision.AFTER), "OFF exclusion/reuse proof failed")
        paths += [Path(revision.__file__), control_area / "prepared.json", area / "control-reuse.json"]
    tests = store.read(area / "tests/result.json")
    cli.require("EARLY_USB_GATE_PASS cases=" + ("42" if retry else "40") in tests["output"], "host matrix incomplete")
    for record in tests["inputs"]:
        cli.require(cli.record(record["path"]) == record, "host test drift")
        paths.append(Path(record["path"]))
    results, assembly = {}, {}
    for mode in ("off2", "on"):
        work = (control_area if mode == "off2" else area) / mode
        receipt = store.read(work / "result.json")
        cli.require(receipt["errors"] == 0, "compiler errors")
        for record in receipt["artifacts"] + receipt["inputs"]:
            cli.require(cli.record(record["path"]) == record, "build drift")
            paths.append(Path(record["path"]))
        paths.append(work / "result.json")
        for tag in ("configure", "build", "symbols", "disassembly", "attributes", "extract"):
            command = store.read(work / (tag + ".json"))
            cli.require(command["exit"] == 0 and cli.record(command["log"]["path"]) == command["log"], "command receipt drift")
            paths += [work / (tag + ".json"), Path(command["log"]["path"])]
        commands_path = work / "b/compile_commands.json"
        paths.append(commands_path)
        commands = [c for c in store.read(commands_path) if "X_Track_App_GCC.dir" in c["command"]]
        for tail in (gate.BOT, gate.DISK, "USER/HAL/HAL.cpp", "USER/main.cpp"):
            cli.require(sum(c["file"].replace("\\", "/").endswith(tail) for c in commands) == 1, "wrong source entry")
        cli.require(all(("-DP34_EARLY_FAULT_VECTORS=1" in c["command"]) == (mode == "on") for c in commands), "macro mismatch")
        assembly[mode] = (work / "disassembly.log").read_text()
        results[mode] = dict(warnings=receipt["warnings"], errors=receipt["errors"], commands=len(commands), reused=retry and mode == "off2")
    raw = (area / "on/b/app-gcc/X-Track-App-GCC.bin").read_bytes()
    off = (control_area / "off2/b/app-gcc/X-Track-App-GCC.bin").read_bytes()
    baseline = gate.early.BASE / "b/app-gcc/X-Track-App-GCC.bin"
    paths.append(baseline)
    cli.require(off == baseline.read_bytes(), "OFF baseline mismatch")
    off_symbols = (control_area / "off2/symbols.log").read_text()
    cli.require("p34_msc_" not in off_symbols, "OFF leaked readiness helpers")
    symbols = original.parse_symbols((area / "on/symbols.log").read_text())
    vectors = original.tables(raw, symbols, prepared["entries"])
    expected = ["_ZN3HAL7SD_InitEv", "_ZN3HAL8Usb_InitEv", "p34_enable_runtime_vectors"]
    actual_order = order(original.function(assembly["on"], "_ZN3HAL8HAL_InitEv"), expected)
    order(original.function(assembly["off2"], "_ZN3HAL8HAL_InitEv"), expected[1::-1])
    negative = 0
    for names in (expected[::-1], expected[:1], expected + expected[:1]):
        try:
            order("\n".join("bl 1 <" + name + ">" for name in names), expected)
        except ValueError:
            negative += 1
        else:
            raise AssertionError("bad startup order accepted")
    snippets = {}
    for name in ("msc_disk_capacity", "msc_disk_read", "msc_disk_write", "p34_msc_media_ready"):
        text = original.function(assembly["on"], name)
        cli.require("SD_GetReady" in text or "p34_msc_media_ready" in text[text.index(":")+1:], "missing backend gate")
        snippets[name] = text
    for name in ("bot_scsi_test_unit", "bot_scsi_capacity", "bot_scsi_format_capacity", "bot_scsi_read10", "bot_scsi_write10"):
        text = original.function(assembly["on"], name)
        cli.require("p34_msc_media_ready" in text, "missing command readiness gate")
        snippets[name] = text
    cli.require("SdioCard5begin" in original.function(assembly["on"], "_ZN10SdioCardEX10readBlocksEmPhj"), "SD recovery unexpectedly changed")
    frames = []
    for path in (area / "on/b").rglob("*.su"):
        chosen = []
        for line in path.read_text().splitlines():
            if any(n in line for n in ("p34_msc", "bot_scsi_read10", "bot_scsi_write10", "HAL_Init", "msc_disk_", "p34_enable_runtime_vectors")):
                loc, size, kind = line.rsplit("\t", 2)
                chosen.append(dict(location=loc, bytes=int(size), kind=kind))
        if chosen:
            paths.append(path)
            frames.extend(chosen)
    delta = "".join("".join(difflib.unified_diff(
        (gate.OLD / "f" / name).read_text(encoding="utf-8").splitlines(keepends=True),
        (area / "f" / name).read_text(encoding="utf-8").splitlines(keepends=True),
        fromfile="old/" + name, tofile="new/" + name)) for name in differences)
    store.raw(diff_path, delta.encode("utf-8"))
    paths.append(diff_path)
    store.write(out, dict(result="EARLY_USB_ARTIFACT_CHECKS_PASS", inputs=[cli.record(p) for p in sorted(set(paths))],
                         changed=differences, configurations=results, off_baseline_identical=True,
                         binary_sizes=dict(off=len(off), on=len(raw)), vector_checks=vectors,
                         actual_startup_order=actual_order, order_negative_checks=negative,
                         gate_assembly=snippets, selected_frames=frames, total_stack_bound=None,
                         stack_status="EARLY-03_REQUIRES_NEW_ARTIFACT_CALLCHAIN_AND_IRQ_BOUND",
                         hardware=False, independent_acceptance=False))
    print("EARLY_USB_ARTIFACT_CHECKS_PASS", "OFF", len(off), "ON", len(raw), "order negatives", negative)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--retry", action="store_true")
    main(parser.parse_args().retry)
