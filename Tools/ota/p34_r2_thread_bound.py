"""Conditional R2 startup bound with explicit EH, format and GPIO contexts."""
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_r2_stack_inventory as base

AREA = base.AREA
ACCOUNT = "_ZN7AccountC1EPKcP10DataCentermPv"


def normal_flow(body):
    """Constructor-only normal CFG; calls may return, no implicit EH edges."""
    ins = {i["address"]: i for i in body}
    following = {i["address"]: body[j+1]["address"] if j+1 < len(body) else None
                 for j, i in enumerate(body)}
    todo, seen = [body[0]["address"]], set()
    while todo:
        a = todo.pop()
        if a in seen:
            continue
        if a not in ins:
            raise ValueError("normal CFG escapes body")
        seen.add(a)
        i = ins[a]
        op, args = i["op"].split(".")[0], i["args"]
        if op in ("pop", "ldmia") and "pc}" in args:
            continue
        if op == "bl":
            if not re.search(r"[0-9a-f]+ <[^>]+>", args):
                raise ValueError("unknown normal call")
            todo.append(following[a])
        elif op in base.parser.BRANCHES:
            match = re.search(r"\b([0-9a-f]+) <", args)
            if not match:
                raise ValueError("unknown normal branch")
            todo.append(int(match[1], 16))
            if op != "b":
                todo.append(following[a])
        elif op in ("bx", "blx", "tbb", "tbh") or args.startswith("pc,"):
            raise ValueError("unsupported normal control")
        else:
            todo.append(following[a])
    return seen


def require_format(value):
    if value != b'assertion "%s" failed: file "%s", line %d%s%s\n':
        raise ValueError("assert format no longer the bound non-floating literal")


def main():
    cli = base.revision.gate.early.model.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated project root required")
    store = cli.Store(ROOT)
    out = store.checked(AREA / "thread-bound1/result.json")
    cli.require(not out.exists(), "preserve thread evidence")
    paths = [Path(__file__), Path(base.__file__), Path(base.parser.__file__),
        AREA / "runtime-targets1/result.json", AREA / "irq-budget1/result.json",
        AREA / "on/disassembly.log", AREA / "on/b/app-gcc/X-Track-App-GCC.bin",
        AREA / "f/ArduinoAPI/Arduino.c", AREA / "f/MDK-ARM_F435/Platform/Core/pwm.c"]
    records = [cli.record(p) for p in paths]
    old, irq = store.read(paths[3]), store.read(paths[4])
    for manifest in (old, irq):
        for record in manifest["inputs"]:
            cli.require(cli.record(record["path"]) == record, "input drift")
    nodes = base.parser.parse(paths[5].read_text())
    named = {n["name"]: a for a, n in nodes.items()}
    graph = {int(a, 16): set(v) for a, v in old["graph"].items()}
    frames = {int(a, 16): v for a, v in old["frames"].items()}
    original = set(old["scopes"]["initialization"]["functions"])
    raisers = [n for n in named if any(s in n for s in ("RaiseException", "ForcedUnwind", "Resume_or_Rethrow"))]
    cli.require("__cxa_throw" not in named and all(named[n] not in original for n in raisers),
                "native exception initiation is reachable")
    throwers = [n for n in named if n.startswith("_ZSt") and "__throw" in n]
    cli.require(len(throwers) == 4, "throw-helper set changed")
    for name in throwers:
        body = nodes[named[name]]["instructions"]
        cli.require(all(i["op"] == "push" for i in body[:-1]) and body[-1]["op"] == "bl" and
                    body[-1]["args"] == "8054f44 <abort>", "throw helper does not end directly in abort")
    parents = {a for a in original if named["__cxa_end_cleanup"] in graph[a]}
    cli.require(parents == {named[ACCOUNT]}, "additional reachable cleanup owner")
    body = nodes[named[ACCOUNT]]["instructions"]
    visited = normal_flow(body)
    cleanup = [i for i in body if "<__cxa_end_cleanup>" in i["args"]]
    cli.require(len(cleanup) == 1 and cleanup[0]["address"] not in visited,
                "cleanup reachable by ordinary constructor control")
    graph[named[ACCOUNT]].remove(named["__cxa_end_cleanup"])
    found = base.parser.reachable([named["Reset_Handler"]], graph)
    unresolved = [i for i in old["scopes"]["initialization"]["unresolved"] if i["function"] in found]
    cli.require(not unresolved and named["__restore_core_regs"] not in found,
                "unresolved control/restored SP still in normal startup")
    raw = paths[6].read_bytes()
    address = struct.unpack_from("<I", raw, 0x08054f88-0x08010000)[0]
    offset = address-0x08010000
    fmt = raw[offset:raw.index(b"\0", offset)]
    require_format(fmt)
    gpio_proof = {}
    for name, mode in (("pinMode", 3), ("PWM_Init", 8)):
        body = nodes[named[name]]["instructions"]
        sites = [(j, i) for j, i in enumerate(body) if i["op"] == "bl" and "<pinMode>" in i["args"]]
        cli.require(len(sites) == 1 and body[sites[0][0]-1]["op"] == "movs" and
                    body[sites[0][0]-1]["args"] == f"r1, #{mode}", "nested pinMode argument changed")
        gpio_proof[name] = body[sites[0][0]-1:sites[0][0]+1]
    pin = nodes[named["pinMode"]]["instructions"]
    cli.require([(i["op"], i["args"]) for i in pin if i["op"] == "cmp" and i["args"].startswith("r2,")]
                == [("cmp", "r2, #4"), ("cmp", "r2, #9")], "GPIO special-mode selector changed")
    def bound(a, trail=(), asserting=False, simple=False):
        key = (a, asserting, simple)
        if key in trail:
            raise ValueError("unresolved recursive context " + nodes[a]["name"])
        if a not in frames:
            raise ValueError("unknown frame " + nodes[a]["name"])
        children = set(graph[a])
        if asserting and a == named["_vfiprintf_r"]:
            children.remove(named["_printf_float"])
        if simple and a == named["pinMode"]:
            children = {named["GPIOx_Init"]}
        options = [bound(c, trail+(key,), asserting or a == named["__assert_func"],
                         c == named["pinMode"] and a in (named["pinMode"], named["PWM_Init"])) for c in children]
        value, path = max(options, default=(0, []), key=lambda v: v[0])
        return frames[a]+value, [dict(name=nodes[a]["name"], bytes=frames[a], asserting=asserting, simple=simple)]+path
    value, path = bound(named["Reset_Handler"])
    # A new ordinary branch into a landing pad must invalidate the dead-code proof.
    altered = [dict(i) for i in nodes[named[ACCOUNT]]["instructions"]]
    altered[0] = dict(altered[0], op="b", args=f'{cleanup[0]["address"]:x} <landing>')
    cli.require(cleanup[0]["address"] in normal_flow(altered), "CFG negative did not reach landing pad")
    try:
        require_format(fmt+b"%f")
    except ValueError:
        pass
    else:
        raise AssertionError("floating format accepted")
    cli.require(records == [cli.record(p) for p in paths], "input changed during thread analysis")
    store.write(out, dict(result="R2_CONDITIONAL_STARTUP_THREAD_BOUND", inputs=records,
        ordinary_constructor_instructions=sorted(visited), cleanup_site=cleanup, no_raise_names=raisers,
        abort_only_throwers=throwers, assert_format_address=address, assert_format=fmt.decode(),
        gpio_proof=gpio_proof, software_bound=value, software_path=path, functions=len(found), tests=2,
        conditional_irq_allowance=irq["envelope"]["total"],
        conditional_combined=value+irq["envelope"]["total"], reserved=irq["stack_reserved_bytes"],
        conditional_margin=irq["stack_reserved_bytes"]-value-irq["envelope"]["total"],
        full_system_bound=None, hardware=False, independent_acceptance=False,
        conditions=["All inherited cold-phase, callback ownership and matching ABI conditions remain required",
                    "Ordinary startup cannot initiate native/forced exceptions; actual allocation-error abort paths retained",
                    "Hardware early exceptions halt; they do not create C++ cleanup entries",
                    "assert uses the exact fixed format; no float conversion is removed from other callers",
                    "Nested pinMode is mode 3 or 8, neither of its recursive dispatch modes 4 or 9",
                    "Final temporal IRQ completeness and both-MSP independent review remain open"],
        status="CONDITIONAL_THREAD_BOUND_PENDING_PHASE_AND_IRQ_REVIEW"))
    print("R2_CONDITIONAL_STARTUP_THREAD_BOUND", value, "plus conditional IRQ", irq["envelope"]["total"],
          "combined", value+irq["envelope"]["total"], "tests", 2)


if __name__ == "__main__":
    main()
