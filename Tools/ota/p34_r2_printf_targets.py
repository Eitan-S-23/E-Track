"""Bound R2 formatting callbacks for the currently resolved startup callers."""
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_r2_stack_inventory as base

AREA = base.AREA


def literal_argument(body, index, read):
    load, add, mov = body[index-3:index]
    match = re.fullmatch(r"r3, \[pc, #(\d+)\]\s+@ \(([0-9a-f]+) <[^>]+>\)", load["args"])
    if (load["op"] != "ldr" or not match or
            (add["op"], add["args"]) != ("add", "r1, sp, #16") or
            mov["op"] != "mov" or not mov["args"].startswith("r0, ")):
        raise ValueError("format callback argument sequence changed")
    address = ((load["address"] + 4) & ~3) + int(match[1])
    if address != int(match[2], 16):
        raise ValueError("PC-relative annotation mismatch")
    return address, read(address)


def main():
    cli = base.revision.gate.early.model.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated project root required")
    store = cli.Store(ROOT)
    out = store.checked(AREA / "printf-targets1/result.json")
    cli.require(not out.exists(), "preserve formatting evidence")
    paths = [Path(__file__), Path(base.__file__), Path(base.parser.__file__),
             AREA / "control-followup1/result.json", AREA / "on/disassembly.log",
             AREA / "on/b/app-gcc/X-Track-App-GCC.bin"]
    records = [cli.record(p) for p in paths]
    old = store.read(paths[3])
    for record in old["inputs"]:
        cli.require(cli.record(record["path"]) == record, "followup input drift")
    nodes = base.parser.parse(paths[4].read_text())
    named = {n["name"]: a for a, n in nodes.items()}
    raw = paths[5].read_bytes()
    def read(address):
        cli.require(0 <= address-0x08010000 <= len(raw)-4, "literal outside BIN")
        return struct.unpack_from("<I", raw, address-0x08010000)[0]
    graph = {int(a, 16): set(v) for a, v in old["graph"].items()}
    formats = {"_printf_float": ("r7", 17), "_printf_i": ("sl", 2), "_printf_common": ("r9", 3)}
    callers = {"_svfiprintf_r": "__ssputs_r", "_vfiprintf_r": "__sfputs_r"}
    edges = []
    for name in ("_printf_float", "_printf_i"):
        parents = {nodes[a]["name"] for a, targets in graph.items() if named[name] in targets}
        cli.require(parents == set(callers), "unreviewed formatting caller")
    for caller, target in callers.items():
        body = nodes[named[caller]]["instructions"]
        calls = [(j, i) for j, i in enumerate(body) if i["op"] == "bl" and
                 any("<"+name+">" in i["args"] for name in ("_printf_float", "_printf_i"))]
        cli.require(len(calls) == 2, "format call count changed")
        for index, site in calls:
            address, word = literal_argument(body, index, read)
            cli.require(word == named[target] | 1, "format callback literal mismatch")
            edges.append(dict(caller=caller, site=site, literal_address=address, word=word, target=target,
                              instructions=body[index-3:index+1]))
    parents = {nodes[a]["name"] for a, targets in graph.items() if named["_printf_common"] in targets}
    cli.require(parents == {"_printf_float", "_printf_i"}, "unreviewed common caller")
    preservation = {}
    for name, (reg, _) in formats.items():
        body = nodes[named[name]]["instructions"]
        uses = [i for i in body if i["args"].startswith(reg+",")]
        expected = {"_printf_float": [("mov", "r7, r3"), ("str", "r7, [sp, #0]")],
                    "_printf_i": [("mov", "sl, r3"), ("str.w", "sl, [sp]")],
                    "_printf_common": [("ldr.w", "r9, [sp, #32]")]}[name]
        cli.require([(i["op"], i["args"]) for i in uses] == expected, "callback register assignment changed")
        preservation[name] = uses
        if name != "_printf_common":
            index = next(j for j, i in enumerate(body) if i["op"] == "bl" and "<_printf_common>" in i["args"])
            cli.require(body[index-5] == uses[1], "fifth argument forwarding changed")
            cli.require(not any(i["op"].startswith("str") or i["args"].startswith(reg+",")
                                for i in body[index-4:index]), "forwarded callback overwritten")
        else:
            cli.require(body[0]["op"] == "stmdb" and body[0]["args"] ==
                        "sp!, {r4, r5, r6, r7, r8, r9, sl, lr}", "common fifth argument offset changed")
    resolved, scopes = [], {}
    destinations = {named[n] for n in callers.values()}
    pending = {i["address"]: i for scope in old["scopes"].values() for i in scope["unresolved"]}
    for name, (reg, count) in formats.items():
        sites = [i for i in pending.values() if i["function"] == named[name]]
        cli.require(len(sites) == count and all(i["op"] == "blx" and i["args"] == reg for i in sites),
                    "format indirect sites changed")
        for site in sites:
            resolved.append(dict(pending.pop(site["address"]), targets=sorted(destinations)))
        graph[named[name]].update(destinations)
    for name, scope in old["scopes"].items():
        found = base.parser.reachable(scope["functions"], graph)
        cli.require(found == set(scope["functions"]), "new reachable bodies need control inventory")
        scopes[name] = dict(scope, unresolved=[i for i in pending.values() if i["function"] in found])
    sample = edges[0]["instructions"]
    for bad in (sample[:1]+[dict(sample[1], args="r1, sp, #20")]+sample[2:],
                [dict(sample[0], args="r3, [r0]")]+sample[1:]):
        try:
            literal_argument(bad, 3, read)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid argument sequence accepted")
    cli.require(records == [cli.record(p) for p in paths], "inputs changed during formatting analysis")
    store.write(out, dict(result="R2_CONDITIONAL_PRINTF_CALLBACK_TARGETS", inputs=records,
        argument_edges=edges, register_provenance=preservation, resolved=resolved, tests=2,
        graph={hex(a): sorted(v) for a, v in graph.items()}, frames=old["frames"], scopes=scopes,
        total_system_bound=None, hardware=False, independent_acceptance=False,
        conditions=["Currently resolved entry-call set; any newly resolved indirect caller must recheck this set",
                    "Callee-saved register preservation under matching AAPCS routines; no memory corruption",
                    "Target union includes string and FILE output; FILE subcallbacks remain unresolved"],
        status="UNKNOWN_REMAINING_STARTUP_CALLBACKS_UNWIND_AND_IRQ_ACTIVE_SET"))
    print("R2_CONDITIONAL_PRINTF_CALLBACK_TARGETS", "classified", len(resolved), "remaining",
          len(scopes["initialization"]["unresolved"]), "negative_checks", 2)


if __name__ == "__main__":
    main()
