"""Inventory early App call edges without treating unresolved edges as zero cost."""
import json
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli

AREA = ROOT / ".cache/p34-early-fault"
BRANCHES = set("b bl blx beq bne bcs bcc bhs blo bmi bpl bvs bvc bhi bls bge blt bgt ble cbz cbnz".split())


def parse(text):
    nodes = {}
    current = None
    for line in text.splitlines():
        head = re.match(r"^([0-9a-f]+) <(.+)>:$", line)
        if head:
            current = int(head[1], 16)
            if current in nodes:
                raise ValueError("duplicate disassembly address")
            nodes[current] = dict(name=head[2], instructions=[])
            continue
        ins = re.match(r"^\s*([0-9a-f]+):\s+(?:[0-9a-f]{4,8}\s+)+\s*(\S+)\s*(.*)$", line)
        if current is not None and ins and not ins[2].startswith("."):
            nodes[current]["instructions"].append(dict(address=int(ins[1], 16), op=ins[2], args=ins[3]))
    return nodes


def edges(nodes, main_cutoff=None):
    graph, unknown, boundaries = {}, {}, []
    for address, node in nodes.items():
        graph[address], unknown[address] = set(), []
        local = {i["address"] for i in node["instructions"]}
        for ins in node["instructions"]:
            if node["name"] == "main" and main_cutoff is not None and ins["address"] > main_cutoff:
                continue
            op, args = ins["op"].split(".")[0], ins["args"]
            if op in BRANCHES:
                target = re.search(r"\b([0-9a-f]+) <", args)
                if target:
                    dst = int(target[1], 16)
                    if dst in local and op not in ("bl", "blx"):
                        if node["name"] == "main" and main_cutoff is not None and dst > main_cutoff:
                            unknown[address].append(dict(reason="branch escapes phase slice", **ins))
                    elif dst in nodes:
                        graph[address].add(dst)
                    else:
                        unknown[address].append(dict(reason="target is not a function entry", **ins))
                else:
                    unknown[address].append(dict(reason="unresolved branch", **ins))
            elif op == "bx" and args.strip() != "lr":
                unknown[address].append(dict(reason="indirect tail call", **ins))
            elif op in ("tbb", "tbh"):
                # Not assumed local until its table and complete targets are checked.
                unknown[address].append(dict(reason="unchecked switch table", **ins))
            elif re.match(r"pc\s*,", args) or (op.startswith("ldr") and args.startswith("pc,")):
                unknown[address].append(dict(reason="computed PC write", **ins))
            elif op in ("pop", "ldmia") and "pc}" in args:
                boundaries.append(dict(function=address, kind="stack return", **ins))
            elif op == "mov" and args.startswith("sp,"):
                boundaries.append(dict(function=address, kind="stack replacement", **ins))
    return graph, unknown, boundaries


def reachable(roots, graph):
    seen, todo = set(), list(roots)
    while todo:
        address = todo.pop()
        if address in seen:
            continue
        if address not in graph:
            raise ValueError("missing root/edge " + hex(address))
        seen.add(address)
        todo.extend(graph[address] - seen)
    return seen


def selftest():
    text = ("00000010 <a>:\n  10: f000 f806 bl 20 <b>\n"
            "  14: 4798 blx r3\n  16: e7fb b.n 10 <a>\n"
            "00000020 <b>:\n  20: 4718 bx r3\n  22: 4770 bx lr\n")
    nodes = parse(text)
    g, u, _ = edges(nodes)
    assert g[16] == {32} and g[32] == set()
    assert len(u[16]) == len(u[32]) == 1
    assert reachable([16], g) == {16, 32}
    nodes[16]["name"] = "main"
    nodes[16]["instructions"].append(dict(address=24, op="b", args="30 <main+0x20>"))
    nodes[16]["instructions"].append(dict(address=48, op="nop", args=""))
    _, u, _ = edges(nodes, 24)
    assert any(i["reason"] == "branch escapes phase slice" for i in u[16])
    g[32].add(16)
    assert reachable([16], g) == {16, 32}  # Reachability terminates; not a recursion proof.
    try:
        reachable([64], g)
    except ValueError:
        pass
    else:
        raise AssertionError("missing target accepted")
    return 6


def main():
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated project root required")
    store = cli.Store(ROOT)
    out = store.checked(AREA / "stack-graph1/result.json")
    cli.require(not out.exists(), "preserve evidence")
    prepared = store.read(AREA / "prepared.json")
    for record in prepared["sources"] + prepared["implementation"]:
        cli.require(cli.record(record["path"]) == record, "prepared input drift")
    validation = store.read(AREA / "validation.json")
    for record in validation["inputs"]:
        cli.require(cli.record(record["path"]) == record, "artifact input drift")
    paths = [Path(__file__), AREA / "prepared.json", AREA / "validation.json",
             AREA / "on/disassembly.log", AREA / "on/symbols.log",
             AREA / "on/b/app-gcc/X-Track-App-GCC.bin"]
    records = [cli.record(p) for p in paths]
    nodes = parse(paths[3].read_text())
    named = {n["name"]: a for a, n in nodes.items()}
    main_ins = nodes[named["main"]]["instructions"]
    calls = [i for i in main_ins if i["op"] == "bl" and "<_ZN3HAL8HAL_InitEv>" in i["args"]]
    cli.require(len(calls) == 1, "ambiguous main phase boundary")
    cutoff = calls[0]["address"]
    graph, unknown, boundaries = edges(nodes, cutoff)
    raw = paths[5].read_bytes()
    symbols = {m[2]: int(m[0], 16) for m in re.findall(
        r"(?m)^([0-9a-f]+) (?:[0-9a-f]+ )?([A-Za-z]) (\S+)\s*$", paths[4].read_text())}
    constructors = []
    for kind in ("preinit", "init"):
        start, end = (symbols["__" + kind + "_array_" + suffix] for suffix in ("start", "end"))
        cli.require(0x08010000 <= start <= end <= 0x08010000 + len(raw) and (end-start) % 4 == 0,
                    "invalid init array bounds")
        constructors += [struct.unpack_from("<I", raw, off-0x08010000)[0] & ~1
                         for off in range(start, end, 4)]
    for address in constructors:
        cli.require(address in nodes, "unknown constructor entry")
    libc = named["__libc_init_array"]
    cli.require(len(unknown[libc]) == 2 and all(i["op"] == "blx" for i in unknown[libc]),
                "unexpected constructor control flow")
    graph[libc].update(constructors)
    resolved = [dict(i, function=libc, targets=constructors, reason="bound Flash preinit/init arrays")
                for i in unknown[libc]]
    unknown[libc] = []
    vectors = struct.unpack_from("<131I", raw)
    # Deliberate superset, not a claim that every NVIC line is enabled.
    irq_roots = sorted({v & ~1 for v in vectors[2:] if v})
    roots = {"initialization": [named["Reset_Handler"]], "primary_vector_superset": irq_roots}
    scopes = {}
    for name, entries in roots.items():
        found = reachable(entries, graph)
        scopes[name] = dict(roots=entries, functions=sorted(found), count=len(found),
                           unresolved=[dict(function=a, name=nodes[a]["name"], **i)
                                       for a in sorted(found) for i in unknown[a]])
    cli.require(records == [cli.record(p) for p in paths], "input changed during analysis")
    store.write(out, dict(result="EARLY_CALLGRAPH_INVENTORY", inputs=records, parser_checks=selftest(),
                         main_inclusive_cutoff=cutoff, constructors=constructors, scopes=scopes,
                         nodes={hex(a): dict(name=n["name"], targets=sorted(graph[a])) for a, n in nodes.items()},
                         resolved=resolved, boundaries=boundaries,
                         status="UNKNOWN_UNRESOLVED_EDGES_AND_STACK_FRAMES", total_bound=None,
                         limitations=["Direct reachability only; unresolved targets may add further callees",
                                      "Primary vector superset is not an NVIC enable/nesting proof",
                                      "No recursion or library stack bound inferred from this inventory"],
                         hardware=False, independent_acceptance=False))
    for name, scope in scopes.items():
        print(name, "functions", scope["count"], "unresolved", len(scope["unresolved"]))


if __name__ == "__main__":
    main()
