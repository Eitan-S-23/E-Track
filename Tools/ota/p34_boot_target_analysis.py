"""Compare source-bound isolated Boot artifacts without claiming stack closure."""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_boot_checkpoint_model as model

AREA = ROOT / ".cache/p34-bc-target"


def symbols(text):
    return {m[3]: dict(bytes=int(m[1], 16), kind=m[2]) for m in
            re.findall(r"(?m)^([0-9a-f]+) ([0-9a-f]+) ([a-zA-Z]) (\S+)", text)}


def stack(directory):
    entries = {}
    for p in directory.rglob("*.su"):
        for line in p.read_text().splitlines():
            location, size, kind = line.rsplit("\t", 2)
            path, _, _, function = location.rsplit(":", 3)
            key = path + ":" + function
            model.cli.require(key not in entries, "duplicate stack function identity")
            entries[key] = dict(bytes=int(size), kind=kind)
    model.cli.require(bool(entries), "empty stack data")
    return entries


def main():
    cli = model.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site
                and sys.dont_write_bytecode, "isolated root required")
    s = cli.Store(ROOT)
    output = s.checked(AREA / "analysis.json")
    cli.require(not output.exists(), "preserve analysis")
    result = s.read(AREA / "result.json")
    paths = [Path(__file__), AREA / "result.json", AREA / "inputs.json", AREA / "snapshot.json"]
    for name in ("inputs.json", "snapshot.json"):
        manifest = s.read(AREA / name)
        for r in manifest.get("sources", manifest.get("files", [])):
            cli.require(cli.record(r["path"]) == r, "source/snapshot drift")
    for variant in result["variants"].values():
        for r in variant["artifacts"] + variant["stack_files"] + variant["configuration"]:
            cli.require(cli.record(r["path"]) == r, "artifact drift")
            paths.append(Path(r["path"]))
    variants = {}
    for group in (1, 16):
        logs = {}
        for tag in ("configure", "build", "validate", "size", "attributes", "disassembly", "symbols"):
            receipt = AREA / ("g%d-%s.json" % (group, tag))
            r = s.read(receipt)
            cli.require(r["exit"] == 0 and cli.record(r["log"]["path"]) == r["log"], "invalid command receipt")
            paths += [receipt, Path(r["log"]["path"])]
            logs[tag] = Path(r["log"]["path"]).read_text()
        size = re.search(r"(?m)^\s*(\d+)\s+(\d+)\s+(\d+)\s+\d+\s+[0-9a-f]+\s+", logs["size"])
        cli.require(size is not None, "missing size")
        sections = re.split(r"(?m)^File Attributes:?\s*\n", logs["attributes"], maxsplit=1)
        cli.require(len(sections) == 2, "missing ARM attribute section")
        attributes = sections[1].strip()
        cli.require("Version5 EABI, hard-float ABI" in logs["attributes"], "ABI mismatch")
        indirect, function = [], None
        for line in logs["disassembly"].splitlines():
            match = re.match(r"^[0-9a-f]+ <(.+)>:", line)
            if match: function = match[1]
            if re.search(r"\bblx\s+r\d+", line):
                indirect.append(dict(function=function, instruction=line.strip()))
        variants[str(group)] = dict(text=int(size[1]), data=int(size[2]), bss_including_reservations=int(size[3]),
                abi_attributes=attributes, symbols=symbols(logs["symbols"]), stack=stack(AREA / ("b%d" % group)),
                indirect_blx_register_sites=indirect,
                compiler_warnings=len(re.findall(r"(?i)warning:", logs["build"])),
                configuration_warning_blocks=len(re.findall(r"CMake Warning:", logs["configure"])))
    a, b = variants["1"], variants["16"]
    cli.require(a["abi_attributes"] == b["abi_attributes"], "ARM attributes changed")
    cli.require(a["data"] == b["data"] and a["bss_including_reservations"] == b["bss_including_reservations"], "RAM changed")
    delta_symbols = {k: [a["symbols"].get(k), b["symbols"].get(k)] for k in a["symbols"].keys() | b["symbols"].keys()
                     if a["symbols"].get(k) != b["symbols"].get(k)}
    delta_stack = {k: [a["stack"].get(k), b["stack"].get(k)] for k in a["stack"].keys() | b["stack"].keys()
                   if a["stack"].get(k) != b["stack"].get(k)}
    cli.require(set(delta_symbols) == {"copy_source"}, "unexpected symbol-size differences")
    cli.require(len(delta_stack) == 1 and next(iter(delta_stack)).endswith(":copy_source"), "unexpected stack differences")
    paths = sorted(set(paths))
    s.write(output, dict(result="TARGET_COMPARISON_RECORDED", inputs=[cli.record(p) for p in paths],
             variants=variants, symbol_size_changes=delta_symbols, stack_frame_changes=delta_stack,
             full_stack_bound=None, full_stack_status="NEED_REVIEW",
             gaps=["Register-indirect calls need source-bound target resolution and tail-call audit",
                   "Runtime library/assembly and exception frames lack complete call-chain stack closure",
                   "No electrical power-loss or device performance measurement"], hardware=False))
    print("TARGET_COMPARISON_RECORDED text_delta", b["text"]-a["text"], "stack_copy_source_delta=8; full_stack_bound=UNKNOWN")


if __name__ == "__main__":
    main()
