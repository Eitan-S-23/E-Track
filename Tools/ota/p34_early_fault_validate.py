"""Validate the actual opt-in vector tables, entry bytes and promotion assembly."""
import json
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_early_fault as e


def parse_symbols(text):
    return {m[2]: int(m[0], 16) for m in re.findall(
        r"(?m)^([0-9a-f]+) (?:[0-9a-f]+ )?([A-Za-z]) (\S+)\s*$", text)}


def tables(raw, symbols, entries):
    check = e.model.cli.require
    check(len(entries) == 131, "entry count")
    base = 0x08010000
    rt = symbols["p34_runtime_vectors"]
    early = symbols["p34_early_exception"]
    check(rt % 1024 == 0 and rt >= base + 0x460, "runtime alignment/header overlap")
    check(rt - base + 524 <= len(raw), "runtime outside image")
    expected = [0 if name == "0" else symbols[name] | (0 if i == 0 else 1)
                for i, name in enumerate(entries)]
    runtime = list(struct.unpack_from("<131I", raw, rt-base))
    primary = list(struct.unpack_from("<131I", raw))
    check(runtime == expected, "runtime symbolic entries changed")
    for i, value in enumerate(primary):
        check(value == (early | 1 if i in e.SLOTS else expected[i]), "primary slot mismatch " + str(i))
    check({i for i in range(131) if primary[i] != runtime[i]} == set(e.SLOTS), "unapproved slot delta")
    check(raw[early-base:early-base+4] == bytes.fromhex("72b6fee7"), "early handler is not cpsid/local loop")
    check(symbols["__fw_header_start__"] == base + 0x400 and
          symbols["__fw_header_end__"] == base + 0x460, "firmware header drift")
    return dict(primary=primary, runtime=runtime, runtime_address=rt, early_address=early)


def function(text, name):
    start = re.search(r"(?m)^[0-9a-f]+ <" + re.escape(name) + r">:", text)
    e.model.cli.require(start is not None, "missing function " + name)
    end = re.search(r"(?m)^[0-9a-f]+ <", text[start.end():])
    return text[start.start():start.end()+end.start()] if end else text[start.start():]


def main():
    cli, area = e.model.cli, e.AREA
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode, "isolated root")
    s = cli.Store(ROOT); s.checked(area / "validation.json")
    cli.require(not (area / "validation.json").exists(), "preserve validation")
    prepared = s.read(area / "prepared.json")
    for r in prepared["sources"] + prepared["implementation"]: cli.require(cli.record(r["path"]) == r, "source drift")
    inputs = [Path(__file__), area / "prepared.json"]
    configs = {}
    for mode in ("off2", "on"):
        receipt = s.read(area / mode / "result.json")
        for r in receipt["artifacts"] + receipt["inputs"]:
            cli.require(cli.record(r["path"]) == r, "build binding drift")
            inputs.append(Path(r["path"]))
        inputs.append(area / mode / "result.json")
        for tag in ("configure", "build", "symbols", "disassembly", "attributes", "extract"):
            rec = s.read(area / mode / (tag + ".json"))
            cli.require(rec["exit"] == 0 and cli.record(rec["log"]["path"]) == rec["log"], "command binding")
            inputs += [area / mode / (tag + ".json"), Path(rec["log"]["path"])]
        cc = area / mode / "b/compile_commands.json"; inputs.append(cc)
        commands = [c for c in s.read(cc) if "X_Track_App_GCC.dir" in c["command"]]
        for tail in ("USER/main.cpp", "USER/HAL/HAL.cpp", str(e.FAULT).replace("\\", "/")):
            cli.require(sum(c["file"].replace("\\", "/").endswith(tail) for c in commands) == 1, "wrong real source " + tail)
        cli.require(all(("-DP34_EARLY_FAULT_VECTORS=1" in c["command"]) == (mode == "on") for c in commands), "target flag drift")
        configs[mode] = dict(app_compile_commands=len(commands), warnings=receipt["warnings"], errors=receipt["errors"])
    raw = (area / "on/b/app-gcc/X-Track-App-GCC.bin").read_bytes()
    symbols = parse_symbols((area / "on/symbols.log").read_text())
    values = tables(raw, symbols, prepared["entries"])
    negative = 0
    for index in (0, 3, 7, 15, 130):
        bad = bytearray(raw); bad[index*4] ^= 2
        try: tables(bad, symbols, prepared["entries"])
        except RuntimeError: negative += 1
        else: raise RuntimeError("corrupt primary accepted")
    bad = bytearray(raw); bad[values["runtime_address"]-0x08010000+12] ^= 2
    try: tables(bad, symbols, prepared["entries"])
    except RuntimeError: negative += 1
    else: raise RuntimeError("corrupt runtime accepted")
    for address in (0x08010400, 0x08010804):
        wrong = dict(symbols, p34_runtime_vectors=address)
        try: tables(raw, wrong, prepared["entries"])
        except RuntimeError: negative += 1
        else: raise RuntimeError("bad table placement accepted")
    text = (area / "on/disassembly.log").read_text()
    promotion = function(text, "p34_enable_runtime_vectors")
    for marker in ("IPSR", "PRIMASK", "cpsid", "dsb", "isb", "p34_runtime_diagnostics_ready", "p34_early_exception"):
        cli.require(marker in promotion, "promotion assembly marker missing " + marker)
    hardfault = function(text, "HardFault_Handler")
    for marker in ("vApplicationHardFaultDump", "vApplicationHardFaultTrace", "vApplicationHardFaultHook"):
        cli.require(marker in hardfault, "lost runtime diagnostics")
    hal = function(text, "_ZN3HAL8HAL_InitEv")
    cli.require("p34_enable_runtime_vectors" in hal, "promotion not in real HAL_Init")
    inputs += [area / "tests/result.json", area / "promotion-tests/result.json"]
    s.write(area / "validation.json", dict(result="EARLY_ARTIFACT_CHECKS_PASS", inputs=[cli.record(p) for p in sorted(set(inputs))],
             configs=configs, table_checks=values, artifact_negatives=negative,
             promotion_assembly=promotion, runtime_hardfault=hardfault,
             stage1_early_software_frame=0, stage2_total_stack_bound=None,
             stage2_status="IRQ_AND_INITIALIZATION_CALLCHAIN_REVIEW_REQUIRED", hardware=False, independent_acceptance=False))
    print("EARLY_ARTIFACT_CHECKS_PASS negatives", negative, "runtime_vtor", hex(values["runtime_address"]))


if __name__ == "__main__": main()
