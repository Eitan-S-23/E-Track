"""EARLY-03-R1: finite IRQ-derived enable closure for the unchanged R2 App."""
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_r2_stack_inventory as base
import p34_r2_irq_budget as prior

AREA = base.AREA
TMR1 = "TMR1_OVF_TMR10_IRQHandler"
TONE = "_Z12toneSetTimerP8tmr_type"
HANDLER = "_ZL17Tone_TimerHandlerv"


def closure(seeds, effects):
    active, rounds = set(seeds), []
    while True:
        added = set()
        for name in sorted(active):
            if name not in effects:
                raise ValueError("IRQ has no derived-enable audit: " + name)
            added.update(effects[name])
        added -= active
        rounds.append(dict(active=sorted(active), added=sorted(added)))
        if not added:
            return active, rounds
        active.update(added)


def tests():
    active, rounds = closure({"a"}, {"a": {"b"}, "b": {"c"}, "c": {"a"}})
    assert active == {"a", "b", "c"} and len(rounds) == 3
    try:
        closure({"a"}, {"a": {"b"}})
    except ValueError:
        pass
    else:
        raise AssertionError("unaudited derived IRQ accepted")
    assert closure({"a"}, {"a": set()})[0] == {"a"}
    values = {"a": dict(bytes=24), "b": dict(bytes=16)}
    old = prior.envelope({"a": values["a"]}, {"a": 0})
    new = prior.envelope(values, {"a": 0, "b": 0})
    assert old == new
    try:
        prior.envelope({"a": dict(bytes=None)}, {"a": 0})
    except ValueError:
        pass
    else:
        raise AssertionError("unknown IRQ frame accepted")
    return 5


def main():
    cli = base.revision.gate.early.model.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated project root required")
    store = cli.Store(ROOT)
    out = store.checked(AREA / "irq-closure1/result.json")
    cli.require(not out.exists(), "preserve old and new IRQ evidence")
    sources = ["MDK-ARM_F435/Platform/Core/Tone.cpp", "MDK-ARM_F435/Platform/Core/timer.c",
        "MDK-ARM_F435/Platform/mcu_config.h", "USER/HAL/HAL_Encoder.cpp", "USER/HAL/HAL_Buzz.cpp",
        "USER/HAL/HAL.cpp", "MDK-ARM_F435/Platform/Core/HardwareSerial.cpp",
        "MDK-ARM_F435/Platform/HAL/HAL_Display.cpp", "USER/HAL/HAL_USB.cpp",
        "Libraries/SdFat/src/SdCard/SdioCard_AT32.cpp"]
    paths = [Path(__file__), Path(base.__file__), Path(base.parser.__file__), Path(prior.__file__),
        AREA / "irq-budget1/result.json", AREA / "stack-frames1/result.json",
        AREA / "runtime-targets1/result.json", AREA / "thread-bound1/result.json",
        AREA / "prepared.json", AREA / "on/disassembly.log", AREA / "on/symbols.log",
        AREA / "on/b/app-gcc/X-Track-App-GCC.bin"] + [AREA / "f" / p for p in sources]
    records = [cli.record(p) for p in paths]
    old, original, latest, thread, prepared = [store.read(p) for p in paths[4:9]]
    for manifest in (old, original, latest, thread):
        for record in manifest["inputs"]:
            cli.require(cli.record(record["path"]) == record, "bound evidence drift")
    for record in prepared["sources"] + prepared["implementation"]:
        cli.require(cli.record(record["path"]) == record, "R2 source drift")
    nodes = base.parser.parse(paths[9].read_text())
    named = {n["name"]: a for a, n in nodes.items()}
    graph = {int(a, 16): set(v) for a, v in latest["graph"].items()}
    frames = {int(a, 16): v for a, v in latest["frames"].items()}
    pending = {i["address"]: i for s in latest["scopes"].values() for i in s["unresolved"]}
    raw = paths[11].read_bytes()
    def word(a):
        cli.require(0 <= a-0x08010000 <= len(raw)-4, "literal outside image")
        return struct.unpack_from("<I", raw, a-0x08010000)[0]
    cli.require(word(0x08016608) == named[HANDLER] | 1 and word(0x08016700) == 0x40010000,
                "Tone callback/default TIM1 mismatch")
    table = re.search(r"(?m)^([0-9a-f]+) ([0-9a-f]+) b Timer_CallbackFunction$", paths[10].read_text())
    cli.require(table is not None and int(table[2], 16) == 60 and
                word(0x08018b80) == int(table[1], 16) and word(0x0801897c) == int(table[1], 16),
                "callback BSS table/load/store binding changed")
    checks = {}
    def check(name, address, op, args):
        i = next(i for i in nodes[named[name]]["instructions"] if i["address"] == address)
        cli.require(i["op"] == op and i["args"].split("\t")[0] == args, "instruction binding changed")
        checks.setdefault(name, []).append(i)
    check(TONE, 0x080165ea, "movs", "r3, #0")
    check(TONE, 0x080165ec, "movs", "r2, #1")
    check(TONE, 0x080165ee, "strd", "r3, r2, [sp]")
    check(TMR1, 0x08018b4e, "ldr", "r3, [r3, #0]")
    check(TMR1, 0x08018b68, "ldr", "r3, [r3, #36]")
    check(TMR1, 0x08018b6a, "cbz", "r3, 8018b6e <TMR1_OVF_TMR10_IRQHandler+0x2e>")
    check("Timer_SetInterruptBase", 0x080188d8, "str.w", "r3, [r2, r0, lsl #2]")
    resolved = [pending.pop(a) for a in (0x08018b52, 0x08018b6c)]
    graph[named[TMR1]].add(named[HANDLER])
    priorities = dict(prior.PRIORITIES, **{TMR1: 0})
    effects, audit = {}, {}
    for name in priorities:
        found = base.parser.reachable([named[name]], graph)
        unknown = [i for i in pending.values() if i["function"] in found]
        cli.require(not unknown, "unresolved IRQ control: " + name)
        enablers = {nodes[a]["name"] for a in found if named["nvic_irq_enable"] in graph[a]}
        registrars = {nodes[a]["name"] for a in found if named["Timer_SetInterruptBase"] in graph[a]}
        cli.require(enablers <= {"Timer_SetInterruptBase"} and registrars <= {TONE},
                    "new IRQ-derived enable owner requires audit")
        # The only derived registration reachable from these IRQs is Tone's TIM1.
        effects[name] = {TMR1} if registrars else set()
        audit[name] = dict(functions=sorted(found), nvic_callers=sorted(enablers),
            timer_registrars=sorted(registrars), derived_irqs=sorted(effects[name]),
            timer_enable_callers=sorted(nodes[a]["name"] for a in found if named["Timer_SetEnable"] in graph[a]))
    active, rounds = closure(set(prior.PRIORITIES), effects)
    cli.require(active == set(priorities) and effects["TMR4_GLOBAL_IRQHandler"] == {TMR1} and
                not effects[TMR1], "derived-enable fixed point changed")
    all_reachable = base.parser.reachable([named["Reset_Handler"]]+[named[n] for n in active], graph)
    registration_parents = {nodes[a]["name"] for a in all_reachable if named["Timer_SetInterruptBase"] in graph[a]}
    cli.require(registration_parents == {"Timer_SetInterruptWithPriority", TONE}, "additional timer registration")
    # Reset callback table is zero; reviewed HAL registers TIM4 and Tone registers TIM1.
    # Keep TIM10 flag testing/clearing, but its unregistered callback slot stays zero.
    entries = {}
    for name in sorted(active):
        value, path = base.software_bound(named[name], graph, frames, {})
        entries[name] = dict(bytes=value, path=[nodes[a]["name"] for a in path])
    budget = prior.envelope(entries, priorities)
    before = set().union(*(set(audit[n]["functions"]) for n in prior.PRIORITIES))
    added = set(audit[TMR1]["functions"])-before
    cli.require({nodes[a]["name"] for a in added} <= {TMR1, HANDLER}, "new IRQ adds unaudited state owners")
    cli.require(records == [cli.record(p) for p in paths], "input drift during closure")
    store.write(out, dict(result="R2_IRQ_DERIVED_ENABLE_CLOSURE", inputs=records, tests=tests(),
        priorities=priorities, entries=entries, closure_rounds=rounds, per_irq=audit, checks=checks,
        resolved_sites=resolved, callback_table=dict(address=int(table[1], 16), bytes=int(table[2], 16),
            applicable_registrations={"TIM1": HANDLER, "TIM4": "HAL_TimerInterrputUpdate"}, tim10="zero unregistered slot"),
        new_irq_functions=[dict(address=a, name=nodes[a]["name"], instructions=nodes[a]["instructions"]) for a in sorted(added)],
        envelope=budget, thread_accepted_conditional=thread["software_bound"],
        combined_conditional=thread["software_bound"]+budget["total"],
        margin_conditional=8192-thread["software_bound"]-budget["total"], full_system_bound=None,
        hardware=False, independent_acceptance=False,
        conditions=["Inherited normal reset, group4, fixed R2 startup owners and disabled USB wakeup configuration",
                    "TIM1 may be enabled by TMR4 before promotion; no quiet-user or short-window assumption",
                    "TIM10 slot remains reset zero with only TIM4/TIM1 registrations in this phase",
                    "Source-bound inline display/SysTick enable routes remain the existing seeds",
                    "New callback functions write Tone/GPIO/timer state, not Print/FILE/LVGL/terminate ownership",
                    "Both-MSP review and independent closure remain separate; numbers are not hardware measurements"],
        status="EARLY_03_R1_IMPLEMENTATION_EVIDENCE_READY_FOR_REVIEW"))
    print("R2_IRQ_DERIVED_ENABLE_CLOSURE", "rounds", len(rounds), "TIM1", entries[TMR1], "envelope", budget)


if __name__ == "__main__":
    main()
