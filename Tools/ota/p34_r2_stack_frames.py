"""R2 frame matching and conservative fixed-prefix assembly frame checks."""
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_r2_stack_inventory as previous

AREA = previous.AREA


def canonical(text):
    text = previous.canonical(text)
    text = re.sub(r"\.(?:constprop|isra)\.\d+$", "", text)
    for word in ("unsigned long long", "unsigned long", "unsigned short", "unsigned char", "signed char"):
        text = text.replace(word + " const", "const " + word)
    return re.sub(r"([\w:]+) const(?=[*&])", r"const \1", text)


def matches(signature, name):
    signature, name = canonical(signature), canonical(name)
    if signature == name:
        return True
    if signature.endswith(name) and signature[:-len(name)].endswith(" "):
        return True
    if re.fullmatch(r"\w+", name):
        return re.search(r"(?:^|\s)" + re.escape(name) + r"\([^()]*\)$", signature) is not None
    return False


def registers(args):
    match = re.search(r"\{([^}]+)\}", args)
    if not match:
        raise ValueError("unknown register save")
    count = 0
    for token in match[1].replace(" ", "").split(","):
        if "-" in token:
            span = re.fullmatch(r"([rsd])(\d+)-\1(\d+)", token)
            if not span or int(span[3]) < int(span[2]):
                raise ValueError("unknown register range")
            count += (int(span[3]) - int(span[2]) + 1) * (8 if span[1] == "d" else 4)
        elif re.fullmatch(r"(?:r\d+|s\d+|d\d+|sl|fp|ip|lr|pc)", token):
            count += 8 if token.startswith("d") else 4
        else:
            raise ValueError("unexpected register " + token)
    return count


def prefix_frame(node):
    positives, first_control = [], None
    for ins in node["instructions"]:
        op, args = ins["op"].split(".")[0], ins["args"]
        if op in previous.parser.BRANCHES | {"bx", "tbb", "tbh"} or args.startswith("pc,"):
            first_control = ins["address"] if first_control is None else first_control
        amount = 0
        if re.search(r"\[sp, #-", args):
            raise ValueError("negative SP-relative access")
        if op in ("push", "vpush") or (op in ("stmdb", "vstmdb") and args.startswith("sp!")):
            amount = registers(args)
        elif op.startswith(("push", "vpush")):
            raise ValueError("conditional/unclassified stack save")
        elif args.startswith("sp,"):
            immediate = re.fullmatch(r"sp, (?:sp, )?#(\d+)(?:\s+@.*)?", args)
            if op not in ("sub", "add") or not immediate:
                raise ValueError("nonconstant stack assignment")
            if op == "sub": amount = int(immediate[1])
        elif "sp!" in args and op not in ("ldmia", "vldmia"):
            raise ValueError("unclassified stack writeback")
        elif "[sp" in args and ("!" in args or "]," in args):
            if not (op.startswith("ldr") and re.search(r"\[sp\], #\d+", args)):
                raise ValueError("unclassified memory stack update")
        elif op.startswith("ldm") and re.search(r"\{[^}]*\bsp\b", args):
            raise ValueError("stack restored from register list")
        elif op == "msr" and re.match(r"(?:MSP|PSP)", args, re.I):
            raise ValueError("hardware stack replacement")
        if amount:
            if first_control is not None:
                raise ValueError("stack allocation after control transfer")
            positives.append(dict(address=ins["address"], bytes=amount, instruction=ins))
    if positives:
        last = positives[-1]["address"]
        first = node["instructions"][0]["address"]
        for ins in node["instructions"]:
            target = re.search(r"\b([0-9a-f]+) <", ins["args"])
            if ins["op"].split(".")[0] in previous.parser.BRANCHES and target and first <= int(target[1], 16) <= last:
                raise ValueError("control can reenter allocation prefix")
    return dict(bytes=sum(v["bytes"] for v in positives), allocations=positives,
                policy="all positive SP adjustments precede first control; no reentry; no unknown SP writes")


def tests():
    assert matches("void UART5_IRQHandler()", "UART5_IRQHandler")
    assert not matches("void Other::UART5_IRQHandler()", "UART5_IRQHandler")
    assert not matches("void xUART5_IRQHandler()", "UART5_IRQHandler")
    assert matches("void f(const uint8_t*)", "f(unsigned char const*)")
    assert matches("convert", "convert.constprop.0")
    good = dict(instructions=[dict(address=0x10, op="push", args="{r4, lr}"),
                             dict(address=0x12, op="sub", args="sp, #16"),
                             dict(address=0x14, op="bl", args="30 <callee>"),
                             dict(address=0x18, op="add", args="sp, #16"),
                             dict(address=0x1a, op="pop", args="{r4, pc}")])
    assert prefix_frame(good)["bytes"] == 24
    assert registers("{d8-d15}") == 64
    for instruction in [dict(address=0x20, op="sub", args="sp, #8"),
                        dict(address=0x20, op="mov", args="sp, r3"),
                        dict(address=0x20, op="b.n", args="10 <f>")]:
        try:
            prefix_frame(dict(instructions=good["instructions"]+[instruction]))
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe stack pattern accepted")
    return 10


def main():
    cli = previous.revision.gate.early.model.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated root required")
    store = cli.Store(ROOT); out = store.checked(AREA / "stack-frames1/result.json")
    cli.require(not out.exists(), "preserve frame evidence")
    old = store.read(AREA / "stack-analysis1/result.json")
    for record in old["inputs"]:
        cli.require(cli.record(record["path"]) == record, "input drift")
    nodes = previous.parser.parse((AREA / "on/disassembly.log").read_text())
    named = {n["name"]: a for a, n in nodes.items()}
    graph = {int(k, 16): set(v) for k, v in old["graph"].items()}
    frames = {int(k, 16): v for k, v in old["frames"].items()}
    initial = store.read(AREA / "stack-graph1/result.json")
    callbacks = store.read(AREA / "stack-callbacks1/result.json")
    _, unknown, _ = previous.parser.edges(nodes, initial["main_inclusive_cutoff"])
    closed = {i["address"] for i in initial["resolved"] + callbacks["resolved"]}
    closed.update(i["site"] for i in old["resolved"])
    for a in unknown:
        unknown[a] = [i for i in unknown[a] if i["address"] not in closed]
    resolved = []
    additions = {
        "_ZN10SdioCardEX11writeBlocksEmPKhj": "_ZN10SdioCardEX10syncBlocksEv",
        "DMA1_Channel3_IRQHandler": "_ZL25disp_send_finish_callbackv",
    }
    for caller, callee in additions.items():
        address = named[caller]
        cli.require(len(unknown[address]) == 1 and unknown[address][0]["op"] in ("blx", "bx"), "callback site drift")
        graph[address].add(named[callee])
        resolved.append(dict(caller=caller, target=callee, site=unknown[address][0],
            policy="SdioCardEX sync virtual / sole display callback union, including post-promotion registration conservatively"))
        unknown[address] = []
    # Do not let conditional register calls disappear through the older inventory parser.
    conditions = "eq ne cs cc mi pl vs vc hi ls ge lt gt le".split()
    for a, node in nodes.items():
        for ins in node["instructions"]:
            op = ins["op"].split(".")[0]
            if op in {base+condition for base in ("bl", "blx", "bx") for condition in conditions}:
                if op in previous.parser.BRANCHES: continue
                if ins["args"].strip() == "lr" and op.startswith("bx"): continue
                target = re.search(r"\b([0-9a-f]+) <", ins["args"])
                if target and int(target[1], 16) in nodes: graph[a].add(int(target[1], 16))
                else: unknown[a].append(dict(ins, reason="conditional control requires resolution"))
    pretty = {}
    for m in re.finditer(r"(?m)^([0-9a-f]+) (?:[0-9a-f]+ )?[tTwW] (.+)$",
                         (AREA / "stack-analysis1/demangled.log").read_text()):
        pretty.setdefault(int(m[1], 16), set()).add(canonical(m[2]))
    owners = {}
    for address, names in pretty.items():
        for name in names: owners.setdefault(name, set()).add(address)
    records = []
    for path in (AREA / "on/b").rglob("*.su"):
        for line in path.read_text().splitlines():
            location, size, kind = line.rsplit("\t", 2)
            match = re.match(r"^(.*?):(\d+):(\d+):(.*)$", location)
            cli.require(match is not None, "unparsed usage")
            records.append(dict(signature=match[4], location=location, bytes=int(size), kind=kind, path=str(path)))
    origins, rejected = {}, {}
    for a, node in nodes.items():
        if a in frames: continue
        names = pretty.get(a, [])
        candidates = [] if any(len(owners[n]) != 1 for n in names) else [
            r for r in records if any(matches(r["signature"], n) for n in names)]
        if candidates and all(r["kind"] == "static" for r in candidates):
            frames[a] = max(r["bytes"] for r in candidates)
            origins[a] = dict(kind="compiler signature match", records=candidates)
        else:
            try:
                proof = prefix_frame(node)
            except ValueError as error:
                rejected[a] = str(error)
            else:
                frames[a] = proof["bytes"]
                origins[a] = dict(kind="fixed linked prefix", **proof, instructions=node["instructions"])
    entries = {}
    for name in old["entries"]:
        try:
            value, path = previous.software_bound(named[name], graph, frames, unknown)
            entries[name] = dict(bytes=value, path=[nodes[a]["name"] for a in path])
        except ValueError as error:
            entries[name] = dict(bytes=None, reason=str(error))
    scopes = {}
    original_scopes = store.read(AREA / "stack-callbacks1/result.json")["scopes"]
    for name, info in original_scopes.items():
        found = previous.parser.reachable(info["roots"], graph)
        scopes[name] = dict(count=len(found), functions=sorted(found),
            missing_frames=[dict(address=a, name=nodes[a]["name"], reason=rejected.get(a)) for a in sorted(found) if a not in frames],
            unresolved=[dict(i, function=a, name=nodes[a]["name"]) for a in sorted(found) for i in unknown[a]])
    paths = [Path(__file__), Path(previous.__file__), AREA / "stack-analysis1/result.json",
             AREA / "f/MDK-ARM_F435/Platform/HAL/HAL_Display.cpp", AREA / "f/MDK-ARM_F435/Platform/lv_port/lv_port_disp.cpp",
             AREA / "f/Libraries/SdFat/src/SdCard/SdioCard_AT32.cpp"]
    store.write(out, dict(result="R2_SOFTWARE_STACK_ENTRY_ANALYSIS", inputs=[cli.record(p) for p in paths],
        tests=tests(), entries=entries, scopes=scopes, resolved=resolved,
        frames={hex(a): v for a, v in frames.items()}, new_frame_origins={hex(a): v for a, v in origins.items()},
        graph={hex(a): sorted(v) for a, v in graph.items()}, total_system_bound=None,
        status="UNKNOWN_INITIALIZATION_AND_EXCEPTION_NESTING", hardware=False, independent_acceptance=False,
        limits=["Entry numbers are software-only; exclude hardware exception frames and preemption",
                "Simple assembly prefix proof rejects post-branch allocations and dynamic SP writes",
                "All source-derived callback owner assumptions remain conditional"] ))
    for name, entry in entries.items(): print(name, entry)
    for name, scope in scopes.items(): print(name, "functions", scope["count"], "unresolved", len(scope["unresolved"]), "missing frames", len(scope["missing_frames"]))


if __name__ == "__main__":
    main()
