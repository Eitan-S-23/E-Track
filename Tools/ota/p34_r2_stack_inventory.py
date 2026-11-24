"""R2-specific virtual targets, checked local tables and stack-frame inventory."""
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_early_stack_graph as parser
import p34_early_usb_retry as revision

AREA = revision.AREA
ALIASES = {"uint8_t": "unsigned char", "uint16_t": "unsigned short", "uint32_t": "unsigned long",
           "int8_t": "signed char", "int16_t": "short", "int32_t": "long", "size_t": "unsigned int",
           "long unsigned int": "unsigned long", "short unsigned int": "unsigned short",
           "long int": "long", "short int": "short", "long long unsigned int": "unsigned long long"}


def canonical(name):
    name = re.sub(r"\s*\[clone [^]]+\]", "", name)
    for old in sorted(ALIASES, key=len, reverse=True):
        name = re.sub(r"\b" + old + r"\b", ALIASES[old], name)
    name = " ".join(name.split())
    return re.sub(r"\s*([(),*&<>])\s*", r"\1", name)


def software_bound(entry, graph, frames, unresolved, trail=()):
    if entry in trail:
        raise ValueError("recursive edge " + hex(entry))
    if unresolved.get(entry):
        raise ValueError("unresolved control at " + hex(entry))
    if entry not in frames:
        raise ValueError("unknown frame " + hex(entry))
    children = [software_bound(c, graph, frames, unresolved, (*trail, entry)) for c in graph[entry]]
    cost, path = max(children, default=(0, []), key=lambda item: item[0])
    return frames[entry] + cost, [entry, *path]


def local_table(node, site, read):
    instructions = node["instructions"]
    index = next(i for i, ins in enumerate(instructions) if ins["address"] == site["address"])
    op = site["op"].split(".")[0]
    if op == "tbb":
        match = re.fullmatch(r"\[pc, (\w+)\]", site["args"])
        if not match or index < 2:
            raise ValueError("unsupported byte table")
        reg, before, base, width = match[1], instructions[index-2:index], site["address"] + 4, 1
    elif op == "ldr":
        match = re.fullmatch(r"pc, \[(\w+), (\w+), lsl #2\]", site["args"])
        if not match or index < 3:
            raise ValueError("unsupported word table")
        adr = instructions[index-1]
        located = re.search(r"adr " + match[1] + r", ([0-9a-f]+) <", adr["args"])
        if adr["op"] != "add" or not located:
            raise ValueError("unresolved table base")
        reg, before, base, width = match[2], instructions[index-3:index-1], int(located[1], 16), 4
    else:
        raise ValueError("not a supported table")
    cmp, guard = before
    match = re.match(re.escape(reg) + r", #(\d+)\b", cmp["args"])
    if cmp["op"] != "cmp" or not match or guard["op"].split(".")[0] != "bhi":
        raise ValueError("missing adjacent unsigned range guard")
    count = int(match[1]) + 1
    if not 1 <= count <= 256:
        raise ValueError("unsupported table size")
    protected = {i["address"] for i in instructions if cmp["address"] < i["address"] <= site["address"]}
    for ins in instructions:
        if ins["op"].split(".")[0] in parser.BRANCHES:
            target = re.search(r"\b([0-9a-f]+) <", ins["args"])
            if target and int(target[1], 16) in protected:
                raise ValueError("branch can bypass range guard")
    values = [int.from_bytes(read(base + width*i, width), "little") for i in range(count)]
    targets = [base + 2*v if width == 1 else v & ~1 for v in values]
    local = {i["address"] for i in instructions}
    if any(t not in local for t in targets) or (width == 4 and any(not v & 1 for v in values)):
        raise ValueError("table escapes decoded local instructions")
    return dict(base=base, width=width, count=count, values=values, targets=targets,
                range_guard=[cmp, guard], scope="local targets already scanned, no additional function edge")


def tests():
    assert canonical("uint32_t f(uint8_t)").endswith(canonical("f(unsigned char)"))
    assert canonical("A::f() [clone .isra.0]") == canonical("A::f()")
    assert software_bound(1, {1: {2}, 2: set()}, {1: 8, 2: 16}, {})[0] == 24
    for graph, frames, unknown in [({1: {1}}, {1: 8}, {}), ({1: {2}, 2: set()}, {1: 8}, {}),
                                  ({1: set()}, {1: 8}, {1: ["indirect"]})]:
        try:
            software_bound(1, graph, frames, unknown)
        except ValueError:
            pass
        else:
            raise AssertionError("unknown/cycle accepted")
    node = dict(instructions=[dict(address=0x10, op="cmp", args="r3, #1"),
                dict(address=0x12, op="bhi.n", args="20 <f+0x10>"),
                dict(address=0x14, op="tbb", args="[pc, r3]"),
                dict(address=0x20, op="bx", args="lr")])
    assert local_table(node, node["instructions"][2], lambda a, n: bytes([4]))["targets"] == [0x20, 0x20]
    try:
        local_table(node, node["instructions"][2], lambda a, n: bytes([255]))
    except ValueError:
        pass
    else:
        raise AssertionError("escaping table accepted")
    node["instructions"].append(dict(address=0x22, op="b.n", args="14 <f+0x4>"))
    try:
        local_table(node, node["instructions"][2], lambda a, n: bytes([4]))
    except ValueError:
        pass
    else:
        raise AssertionError("guard bypass accepted")
    return 9


def main():
    cli, host = revision.gate.early.model.cli, revision.gate.early.model.host
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated project root required")
    store = cli.Store(ROOT); out = store.checked(AREA / "stack-analysis1")
    cli.require(not out.exists(), "preserve analysis")
    for name in ("demangled.log", "demangled.json", "result.json"):
        store.checked(out / name)
    for key in ("home", "userprofile", "appdata", "localappdata", "temp", "tmp", "tmpdir", "xdg_cache_home",
                "xdg_config_home", "xdg_data_home", "pythonuserbase", "pythonpycacheprefix", "ccache_dir", "sccache_dir"):
        store.checked(out / "host" / key)
    for manifest in ("prepared.json", "validation.json", "stack-callbacks1/result.json"):
        data = store.read(AREA / manifest)
        for record in data.get("sources", []) + data.get("implementation", []) + data.get("inputs", []):
            cli.require(cli.record(record["path"]) == record, "input drift")
    raw = (AREA / "on/b/app-gcc/X-Track-App-GCC.bin").read_bytes()
    cli.require(cli.record(AREA / "on/b/app-gcc/X-Track-App-GCC.bin")["sha256"] ==
                "387a48705d81941834b6644d22da9573df3160b1717e56338cd86cdf948bcdb3", "not selected R2")
    dis = (AREA / "on/disassembly.log").read_text()
    nodes = parser.parse(dis); named = {n["name"]: a for a, n in nodes.items()}
    syms = {m[3]: (int(m[0], 16), int(m[1], 16)) for m in re.findall(
        r"(?m)^([0-9a-f]+) ([0-9a-f]+) ([A-Za-z]) (\S+)$", (AREA / "on/symbols.log").read_text())}
    def read(address, size):
        offset = address - 0x08010000
        if offset < 0 or offset + size > len(raw):
            raise ValueError("read outside bound image")
        return raw[offset:offset+size]
    previous = store.read(AREA / "stack-callbacks1/result.json")
    graph = {int(a, 16): set(v) for a, v in previous["graph"].items()}
    initial = store.read(AREA / "stack-graph1/result.json")
    _, unknown, _ = parser.edges(nodes, initial["main_inclusive_cutoff"])
    closed = {i["address"] for i in previous["resolved"]}
    closed.update(i["address"] for i in initial["resolved"])
    for a in unknown:
        unknown[a] = [i for i in unknown[a] if i["address"] not in closed]
    # Explicit sites bind the load offset and immutable vtable slot to this ELF.
    virtuals = {
        0x08014e8c: ("_ZTV10SdioCardEX", 12),
        0x08041582: ("_ZTV14HardwareSerial", 16),
        0x0804159c: ("_ZTV14HardwareSerial", 16),
        0x080415aa: ("_ZTV14HardwareSerial", 20),
        0x080112a0: ("_ZTV7TwoWire", 0),
        0x080112cc: ("_ZTV7TwoWire", 0),
        0x08011b3c: ("_ZTV15Adafruit_ST7789", 80),
        0x08011b8a: ("_ZTV15Adafruit_ST7789", 92),
        0x08011c2e: ("_ZTV15Adafruit_ST7789", 80),
        0x08011eb0: ("_ZTV15Adafruit_ST7789", 48),
        0x08012d34: ("_ZTV10SdioCardEX", 4),
        0x08012dbc: ("_ZTV10SdioCardEX", 8),
        0x08012ee2: ("_ZTV10SdioCardEX", 0),
        0x08012fa8: ("_ZTV10SdioCardEX", 12),
        0x08013d62: ("_ZTV10SdioCardEX", 8),
        0x08013dec: ("_ZTV10SdioCardEX", 0),
    }
    # Locate the write virtual site rather than assuming a prior revision's address.
    write = named["msc_disk_write"]
    sites = [i for i in unknown[write] if i["op"] == "blx"]
    cli.require(len(sites) == 1, "write site ambiguity")
    virtuals[sites[0]["address"]] = ("_ZTV10SdioCardEX", 16)
    resolved, rejected_tables = [], []
    for a, node in nodes.items():
        kept = []
        for ins in unknown[a]:
            site = ins["address"]
            if site in virtuals:
                table_name, offset = virtuals[site]; address, size = syms[table_name]
                cli.require(offset + 12 <= size, "vtable bounds")
                value = struct.unpack("<I", read(address + 8 + offset, 4))[0]
                cli.require(value & 1 and value & ~1 in nodes, "invalid virtual target")
                index = next(i for i, n in enumerate(node["instructions"]) if n["address"] == site)
                prior = node["instructions"][max(0, index-6):index]
                cli.require(any(n["op"].startswith("ldr") and re.search(r", #(\d+)\]", n["args"]) and
                    int(re.search(r", #(\d+)\]", n["args"])[1]) == offset for n in prior), "vslot load not found")
                graph[a].add(value & ~1)
                resolved.append(dict(function=a, site=site, table=table_name, offset=offset, word=value,
                                     target=value & ~1, kind="bound virtual slot", preceding=prior))
            elif node["name"] in ("_ZN7FatFile4syncEv", "_ZN7FatFile4openEPS_P7fname_th") and ins["op"] == "blx":
                target = named["_ZL14SD_GetDateTimePtS_"]
                graph[a].add(target)
                resolved.append(dict(function=a, site=site, target=target, kind="only registered startup date-time callback"))
            elif node["name"] in ("_Znwj", "_Znaj") and ins["op"] == "bx":
                targets = [named["_ZL11first_allocj"], named["lv_mem_alloc"]]
                graph[a].update(targets)
                resolved.append(dict(function=a, site=site, targets=targets, kind="allocator default and sole reassignment union"))
            elif ins["op"] == "tbb" or (ins["op"].startswith("ldr") and "lsl #2" in ins["args"]):
                try:
                    proof = local_table(node, ins, read)
                except ValueError as error:
                    rejected_tables.append(dict(function=a, site=site, reason=str(error))); kept.append(ins)
                else:
                    resolved.append(dict(function=a, site=site, kind="checked local switch table", **proof))
            else:
                kept.append(ins)
        unknown[a] = kept
    cli.require({i["site"] for i in resolved if i["kind"] == "bound virtual slot"} == set(virtuals), "missing virtual site")
    env = host.environment(store, out)
    nm = revision.gate.early.tc.ARM / "bin/arm-none-eabi-nm.exe"
    elf = AREA / "on/b/app-gcc/X-Track-App-GCC.elf"
    demangled = host.command(store, out, "demangled", [nm, "-n", "-S", "-C", elf], env, 60).decode()
    pretty = {}
    for m in re.finditer(r"(?m)^([0-9a-f]+) (?:[0-9a-f]+ )?[tTwW] (.+)$", demangled):
        pretty.setdefault(int(m[1], 16), []).append(canonical(m[2]))
    owners = {}
    for address, names in pretty.items():
        for name in names:
            owners.setdefault(name, set()).add(address)
    usages, su_paths = [], sorted((AREA / "on/b").rglob("*.su"))
    for path in su_paths:
        for line in path.read_text().splitlines():
            location, size, kind = line.rsplit("\t", 2)
            match = re.match(r"^(.*?):(\d+):(\d+):(.*)$", location)
            cli.require(match is not None, "unparsed stack record")
            usages.append(dict(signature=canonical(match[4]), location=location, bytes=int(size), kind=kind, sidecar=str(path)))
    frames, origins = {}, {}
    for a in nodes:
        names = pretty.get(a, [])
        if any(len(owners[n]) != 1 for n in names):
            continue
        matches = [u for u in usages if any(u["signature"] == n or
                   ("(" in n and u["signature"].endswith(n) and
                    u["signature"][:-len(n)].endswith(" ")) for n in names)]
        if matches and all(m["kind"] == "static" for m in matches):
            frames[a] = max(m["bytes"] for m in matches)
            origins[a] = matches
    manual = {"p34_early_exception": 0, "Reset_Handler": 0, "__libc_init_array": 16,
              "memcpy": 8, "memset": 0, "strcmp": 0}
    for name, size in manual.items():
        a = named[name]
        cli.require(a not in frames, "unexpected assembly/compiler frame overlap")
        frames[a] = size; origins[a] = dict(kind="manual whole linked routine inspection", instructions=nodes[a]["instructions"])
    entries = {}
    for name in ("Reset_Handler", "SysTick_Handler", "UART5_IRQHandler", "USART1_IRQHandler", "USART2_IRQHandler",
                 "TMR4_GLOBAL_IRQHandler", "EDMA_Stream1_IRQHandler", "DMA1_Channel3_IRQHandler", "OTGFS1_IRQHandler"):
        try:
            value, path = software_bound(named[name], graph, frames, unknown)
            entries[name] = dict(bytes=value, path=[nodes[a]["name"] for a in path])
        except ValueError as error:
            entries[name] = dict(bytes=None, reason=str(error))
    scopes = {}
    for name, old in previous["scopes"].items():
        found = parser.reachable(old["roots"], graph)
        scopes[name] = dict(count=len(found), functions=sorted(found),
            missing_frames=[dict(address=a, name=nodes[a]["name"]) for a in sorted(found) if a not in frames],
            unresolved=[dict(function=a, name=nodes[a]["name"], **i) for a in sorted(found) for i in unknown[a]])
    source_names = ["USER/App/Utils/new/new.cpp", "USER/HAL/HAL_SD_CARD.cpp", "USER/HAL/HAL_Bluetooth.cpp",
                    "Libraries/SdFat/src/SdFat.h", "Libraries/SdFat/src/SdCard/SdioCard.h",
                    "MDK-ARM_F435/Platform/HAL/HAL_Display.cpp", "MDK-ARM_F435/Platform/Core/HardwareSerial.cpp",
                    "ArduinoAPI/Wire.cpp", "ArduinoAPI/WireBase.cpp"]
    paths = [Path(__file__), Path(parser.__file__), nm, elf, AREA / "prepared.json", AREA / "validation.json",
             AREA / "on/disassembly.log", AREA / "on/symbols.log", AREA / "on/b/app-gcc/X-Track-App-GCC.bin",
             AREA / "stack-graph1/result.json", AREA / "stack-callbacks1/result.json", out / "demangled.log", out / "demangled.json"]
    paths += su_paths + [AREA / "f" / n for n in source_names]
    store.write(out / "result.json", dict(result="R2_VIRTUAL_AND_STACK_INVENTORY", inputs=[cli.record(p) for p in paths],
        parser_checks=tests(), entries=entries, scopes=scopes, resolved=resolved, rejected_tables=rejected_tables,
        graph={hex(a): sorted(g) for a, g in graph.items()}, frames={hex(a): v for a, v in frames.items()},
        frame_origins={hex(a): v for a, v in origins.items()}, total_bound=None,
        status="UNKNOWN_REMAINING_CONTROL_FRAMES_AND_IRQ_NESTING", hardware=False, independent_acceptance=False,
        limitations=["Per-entry numbers exclude hardware exception frames and nesting",
                     "Tail calls retain the full caller frame, deliberately conservative",
                     "Virtual owner sets are limited to the source-bound cold startup objects",
                     "No application-wide stack-safety or runtime high-water claim"]))
    for name, value in entries.items(): print(name, value)
    for name, scope in scopes.items(): print(name, "functions", scope["count"], "unknown sites", len(scope["unresolved"]), "missing frames", len(scope["missing_frames"]))


if __name__ == "__main__":
    main()
