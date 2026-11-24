"""Conditional startup Print/newlib targets, with newly reachable bodies checked."""
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_r2_stack_inventory as base

AREA = base.AREA


def require_word(actual, expected):
    if actual != expected:
        raise ValueError("bound callback/data word changed")


def main():
    cli = base.revision.gate.early.model.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated project root required")
    store = cli.Store(ROOT)
    out = store.checked(AREA / "runtime-targets1/result.json")
    cli.require(not out.exists(), "preserve runtime-target evidence")
    sources = ["MDK-ARM_F435/Platform/Core/HardwareSerial.cpp", "USER/HAL/HAL_Config.h",
               "USER/HAL/HAL.cpp", "USER/HAL/HAL_I2C_Scan.cpp"]
    paths = [Path(__file__), Path(base.__file__), Path(base.parser.__file__),
             AREA / "cold-phase1/result.json", AREA / "on/disassembly.log",
             AREA / "on/symbols.log", AREA / "on/b/app-gcc/X-Track-App-GCC.bin"]
    paths += [AREA / "f" / p for p in sources]
    records = [cli.record(p) for p in paths]
    old = store.read(paths[3])
    for record in old["inputs"]:
        cli.require(cli.record(record["path"]) == record, "input drift")
    nodes = base.parser.parse(paths[4].read_text())
    named = {n["name"]: a for a, n in nodes.items()}
    symbols = {m[3]: int(m[0], 16) for m in re.findall(
        r"(?m)^([0-9a-f]+) (?:([0-9a-f]+) )?([A-Za-z]) (\S+)$", paths[5].read_text())}
    raw = paths[6].read_bytes()
    def word(address):
        cli.require(0 <= address-0x08010000 <= len(raw)-4, "word outside bound BIN")
        return struct.unpack_from("<I", raw, address-0x08010000)[0]
    graph = {int(a, 16): set(v) for a, v in old["graph"].items()}
    pending = {i["address"]: i for s in old["scopes"].values() for i in s["unresolved"]}
    bindings, resolved = [], []
    def bind(address, expected, meaning):
        value = word(address)
        require_word(value, expected)
        bindings.append(dict(address=address, value=value, meaning=meaning))
    def close(site, targets):
        i = pending.pop(site)
        graph[i["function"]].update(named[n] for n in targets)
        resolved.append(dict(i, targets=targets))
    vtable = symbols["_ZTV14HardwareSerial"] + 8
    bind(vtable, named["_ZN14HardwareSerial5writeEh"] | 1, "HardwareSerial byte writer")
    bind(vtable+4, named["_ZN5Print5writeEPKhj"] | 1, "HardwareSerial inherited buffer writer")
    close(0x08010bba, ["_ZN5Print5writeEPKhj"])
    close(0x08010c36, ["_ZN14HardwareSerial5writeEh"])
    # A newly reachable Print buffer loop has one additional byte-write virtual.
    byte_loop = named["_ZN5Print5writeEPKhj"]
    _, unknown, _ = base.parser.edges(nodes)
    cli.require(len(unknown[byte_loop]) == 1 and unknown[byte_loop][0]["address"] == 0x08010b94,
                "Print byte loop changed")
    graph[byte_loop].add(named["_ZN14HardwareSerial5writeEh"])
    resolved.append(dict(unknown[byte_loop][0], function=byte_loop,
                         targets=["_ZN14HardwareSerial5writeEh"]))
    bind(0x080569bc, named["__swrite"] | 1, "std FILE write slot")
    bind(0x080569c0, named["__sseek"] | 1, "std FILE seek slot")
    for site, target in ((0x08059324, "__sseek"), (0x0805936e, "__sseek"), (0x080593bc, "__swrite")):
        close(site, [target])
    cli.require(not any(any(t in name for t in ("fopencookie", "funopen", "fdopen", "fopen"))
                        for name in named), "additional FILE factory needs ownership audit")
    cli.require("_ZSt13set_terminatePFvvE" not in named and "_signal_r" not in named and
                "signal" not in named, "mutable handler registration is linked")
    def data_address(name, offset=0):
        return symbols["_sidata"] + symbols[name] - symbols["_sdata"] + offset
    bind(data_address("_ZN10__cxxabiv119__terminate_handlerE"), named["abort"] | 1, "default terminate handler")
    bind(data_address("_impure_ptr"), symbols["_impure_data"], "default reentrancy object")
    bind(data_address("_impure_data", 60), 0, "initial signal handler table")
    close(0x0804ff32, ["abort"])
    close(0x08056e22, [])
    before = set().union(*(set(s["functions"]) for s in old["scopes"].values()))
    after = set().union(*(base.parser.reachable(s["roots"], graph) for s in old["scopes"].values()))
    new = after-before
    closed = {i["address"] for i in resolved}
    new_unknown = [dict(i, function=a, name=nodes[a]["name"]) for a in new for i in unknown[a]
                   if i["address"] not in closed]
    # Do not reuse old reachability as proof that newly exposed functions are resolved.
    for a in new:
        for ins in nodes[a]["instructions"]:
            op = ins["op"].split(".")[0]
            if re.fullmatch(r"(?:bl|blx|bx)(?:eq|ne|cs|cc|mi|pl|vs|vc|hi|ls|ge|lt|gt|le)", op):
                if ins["args"] != "lr":
                    new_unknown.append(dict(ins, function=a, name=nodes[a]["name"], reason="new conditional control"))
    pending.update({i["address"]: i for i in new_unknown})
    scopes = {}
    for name, s in old["scopes"].items():
        found = base.parser.reachable(s["roots"], graph)
        scopes[name] = dict(roots=s["roots"], functions=sorted(found),
            unresolved=[i for i in pending.values() if i["function"] in found],
            missing_frames=[dict(address=a, name=nodes[a]["name"]) for a in sorted(found)
                            if hex(a) not in old["frames"]])
    require_word(0, 0)
    for value in (1, 0xffffffff):
        try:
            require_word(value, 0)
        except ValueError:
            pass
        else:
            raise AssertionError("mutated data accepted")
    cli.require(records == [cli.record(p) for p in paths], "input changed during analysis")
    store.write(out, dict(result="R2_CONDITIONAL_RUNTIME_TARGETS", inputs=records, tests=3,
        bindings=bindings, resolved=resolved, new_functions=[dict(address=a, name=nodes[a]["name"])
        for a in sorted(new)], scopes=scopes, graph={hex(a): sorted(v) for a, v in graph.items()},
        frames=old["frames"], total_system_bound=None, hardware=False, independent_acceptance=False,
        conditions=["Startup Print receivers are the constructed HardwareSerial diagnostics, including CONFIG_DEBUG_SERIAL",
                    "Valid normal libc state, standard FILE objects and no custom signal/terminate registration",
                    "Native exception terminate handlers originate from get_terminate; foreign/corrupted exceptions excluded",
                    "Newly resolved caller/ownership paths must revalidate these conditions"],
        status="UNKNOWN_UNWIND_AND_FINAL_PHASE_OWNERSHIP_REVIEW"))
    print("R2_CONDITIONAL_RUNTIME_TARGETS", "new functions", len(new), "remaining",
          len(scopes["initialization"]["unresolved"]), "missing frames", scopes["initialization"]["missing_frames"])


if __name__ == "__main__":
    main()
