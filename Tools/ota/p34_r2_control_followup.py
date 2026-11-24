"""Merge R2 arithmetic proofs and bind three remaining startup control sites."""
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_r2_stack_inventory as base

AREA = base.AREA


def guarded_null(body, word):
    expected = [(0x08010a3c, "ldr", "r3, [pc, #12]"),
                (0x08010a3e, "cbz", "r3, 8010a42 <register_tm_clones+0x16>"),
                (0x08010a40, "bx", "r3"), (0x08010a42, "bx", "lr")]
    found = {i["address"]: i for i in body}
    if word != 0 or any(a not in found or found[a]["op"] != op or
                         found[a]["args"].split("\t")[0] != args for a, op, args in expected):
        raise ValueError("null callback guard changed")


def main():
    cli = base.revision.gate.early.model.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated project root required")
    store = cli.Store(ROOT)
    out = store.checked(AREA / "control-followup1/result.json")
    cli.require(not out.exists(), "preserve followup evidence")
    paths = [Path(__file__), Path(base.__file__), Path(base.parser.__file__),
             AREA / "stack-frames1/result.json", AREA / "stack-analysis1/result.json",
             AREA / "arithmetic-stack1/result.json", AREA / "irq-budget1/result.json",
             AREA / "on/disassembly.log", AREA / "on/b/app-gcc/X-Track-App-GCC.bin",
             AREA / "f/Libraries/SdFat/src/SdCard/SdioCard.h",
             AREA / "f/Libraries/SdFat/src/SdCard/SdioCard_AT32.cpp"]
    records = [cli.record(p) for p in paths]
    old, inventory, arithmetic, irq = [store.read(p) for p in paths[3:7]]
    for manifest in (old, inventory, arithmetic, irq):
        for record in manifest["inputs"]:
            cli.require(cli.record(record["path"]) == record, "input drift")
    nodes = base.parser.parse(paths[7].read_text())
    named = {n["name"]: a for a, n in nodes.items()}
    raw = paths[8].read_bytes()
    graph = {int(a, 16): set(v) for a, v in old["graph"].items()}
    frames = {int(a, 16): v for a, v in old["frames"].items()}
    pending = {i["address"]: dict(i) for scope in old["scopes"].values() for i in scope["unresolved"]}
    resolved = list(arithmetic["classified_sites"])
    for site in resolved:
        pending.pop(site["address"])
    for name, proof in arithmetic["proofs"].items():
        cli.require(not graph[named[name]], "arithmetic leaf has external graph edges")
        frames[named[name]] = proof["bytes"]
    for name, proof in irq["manually_inspected_frames"].items():
        frames[named[name]] = proof["bytes"]
    slot = 0x0805cc4c + 8 + 4
    target = struct.unpack_from("<I", raw, slot - 0x08010000)[0]
    cli.require(target == named["_ZN10SdioCardEX10syncBlocksEv"] | 1, "vtable slot drift")
    for name in ("_ZN10SdioCardEX9readBlockEmPh", "_ZN10SdioCardEX10writeBlockEmPKh"):
        owner = named[name]
        sites = [i for i in pending.values() if i["function"] == owner]
        cli.require(len(sites) == 1 and sites[0]["op"] == "blx" and sites[0]["args"] == "r3",
                    "SD virtual call changed")
        body = nodes[owner]["instructions"]
        index = next(j for j, i in enumerate(body) if i["address"] == sites[0]["address"])
        cli.require([(i["op"], i["args"]) for i in body[index-3:index]] ==
                    [("ldr", "r3, [r4, #0]"), ("mov", "r0, r4"), ("ldr", "r3, [r3, #4]")],
                    "SD receiver/slot load changed")
        graph[owner].add(target & ~1)
        resolved.append(dict(pending.pop(sites[0]["address"]), target=target & ~1,
                             vtable_word_address=slot, kind="same bound SdioCardEX receiver, sync slot"))
    body = nodes[named["register_tm_clones"]]["instructions"]
    word = struct.unpack_from("<I", raw, 0x08010a4c - 0x08010000)[0]
    guarded_null(body, word)
    for bad_body, bad_word in ((body, 1), (body[:-1], 0)):
        try:
            guarded_null(bad_body, bad_word)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid null guard accepted")
    resolved.append(dict(pending.pop(0x08010a40), kind="immutable zero literal before CBZ", word=word))
    scopes = {}
    for name, scope in old["scopes"].items():
        found = base.parser.reachable(scope["functions"], graph)
        cli.require(found == set(scope["functions"]), "new reachable functions need fresh control inventory")
        scopes[name] = dict(functions=sorted(found),
            unresolved=[i for i in pending.values() if i["function"] in found],
            missing_frames=[dict(address=a, name=nodes[a]["name"]) for a in sorted(found) if a not in frames])
    cli.require(records == [cli.record(p) for p in paths], "inputs changed during followup")
    store.write(out, dict(result="R2_CONTROL_FOLLOWUP", inputs=records, guard_checks=3,
        resolved=resolved, scopes=scopes, graph={hex(a): sorted(v) for a, v in graph.items()},
        frames={hex(a): v for a, v in frames.items()}, total_system_bound=None,
        status="UNKNOWN_INITIALIZATION_CALLBACKS_UNWIND_AND_FINAL_IRQ_ACTIVE_SET",
        hardware=False, independent_acceptance=False,
        limits=["Arithmetic frame values are whole shared-body bounds, not additive symbol-entry frames",
                "SD receiver ownership inherited from the source-bound cold startup inventory",
                "No recursion, exception-unwind or initialization-total safety claim"]))
    print("R2_CONTROL_FOLLOWUP", "classified", len(resolved), "remaining",
          len(scopes["initialization"]["unresolved"]), "missing_frames", scopes["initialization"]["missing_frames"])


if __name__ == "__main__":
    main()
