"""Conditional R2 pre-promotion IRQ allowance; initialization stays unresolved."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_r2_stack_inventory as base

AREA = base.AREA
PRIORITIES = {"SysTick_Handler": 0, "EDMA_Stream1_IRQHandler": 0,
              "DMA1_Channel3_IRQHandler": 0, "UART5_IRQHandler": 1,
              "USART1_IRQHandler": 1, "USART2_IRQHandler": 1,
              "OTGFS1_IRQHandler": 1, "TMR4_GLOBAL_IRQHandler": 2}
MANUAL = {"__aeabi_uldivmod": 16, "sinf": 16, "memchr": 16, "__cmpdf2": 4,
          "__aeabi_dcmpeq": 8, "__aeabi_dcmplt": 8, "__aeabi_dcmple": 8,
          "__aeabi_dcmpge": 8, "__aeabi_dcmpgt": 8}


def envelope(entries, priorities):
    bands = {}
    for name, priority in priorities.items():
        if entries[name]["bytes"] is None:
            raise ValueError("unknown IRQ entry")
        bands[priority] = max(bands.get(priority, 0), entries[name]["bytes"])
    # At most one software handler at each preempt priority, plus HardFault/NMI.
    hardware = (len(bands) + 2) * (32 + 72 + 4)
    return dict(software_bands=bands, software=sum(bands.values()), hardware=hardware,
                total=sum(bands.values()) + hardware)


def main():
    cli = base.revision.gate.early.model.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated root required")
    store = cli.Store(ROOT); out = store.checked(AREA / "irq-budget1/result.json")
    cli.require(not out.exists(), "preserve IRQ evidence")
    old = store.read(AREA / "stack-frames1/result.json")
    for record in old["inputs"]:
        cli.require(cli.record(record["path"]) == record, "frame input drift")
    analysis = store.read(AREA / "stack-analysis1/result.json")
    for record in analysis["inputs"]:
        cli.require(cli.record(record["path"]) == record, "artifact/source drift")
    dis_path = AREA / "on/disassembly.log"
    nodes = base.parser.parse(dis_path.read_text())
    named = {n["name"]: a for a, n in nodes.items()}
    graph = {int(a, 16): set(v) for a, v in old["graph"].items()}
    frames = {int(a, 16): v for a, v in old["frames"].items()}
    unknown = {}
    for scope in old["scopes"].values():
        for site in scope["unresolved"]:
            unknown.setdefault(site["function"], []).append(site)
    inspected = {}
    for name, value in MANUAL.items():
        address = named[name]
        cli.require(address not in frames, "manual frame must close a genuine gap")
        frames[address] = value
        inspected[name] = dict(bytes=value, instructions=nodes[address]["instructions"],
            basis="whole linked routine inspection: conditional allocation at most once; balanced paths or tail exit")
    divide = nodes[named["__aeabi_uldivmod"]]["instructions"]
    cli.require(sum(i["op"] == "strd" and i["args"] == "ip, lr, [sp, #-16]!" for i in divide) == 1 and
                sum(i["op"] == "add" and i["args"] == "sp, #16" for i in divide) == 1,
                "division allocation/release changed")
    entries = {}
    for name in PRIORITIES:
        found = base.parser.reachable([named[name]], graph)
        cli.require(all(nodes[a]["instructions"] for a in found), "missing body in bounded entry")
        value, path = base.software_bound(named[name], graph, frames, unknown)
        entries[name] = dict(bytes=value, path=[nodes[a]["name"] for a in path], functions=sorted(found))
    budget = envelope(entries, PRIORITIES)
    assert envelope({"a": {"bytes": 8}, "b": {"bytes": 16}}, {"a": 0, "b": 0})["software"] == 16
    try:
        envelope({"a": {"bytes": None}}, {"a": 0})
    except ValueError:
        pass
    else:
        raise AssertionError("unknown entry used as zero")
    symbols = {m[2]: int(m[0], 16) for m in re.findall(
        r"(?m)^([0-9a-f]+) (?:[0-9a-f]+ )?([A-Za-z]) (\S+)\s*$", (AREA / "on/symbols.log").read_text())}
    stack = symbols["__StackTop"] - symbols["__StackLimit"]
    cli.require(stack == 8192 and symbols["_estack"] == symbols["__StackTop"], "stack layout changed")
    source_names = ["MDK-ARM_F435/Platform/Core/mcu_core.c", "MDK-ARM_F435/Platform/Core/delay.c",
        "MDK-ARM_F435/Platform/mcu_config.h", "MDK-ARM_F435/Platform/Core/HardwareSerial.h",
        "MDK-ARM_F435/Platform/Core/HardwareSerial.cpp", "MDK-ARM_F435/Platform/Core/timer.c",
        "MDK-ARM_F435/Platform/HAL/HAL_Display.cpp", "Libraries/W25Q128/qspi_cmd_en25qh128a.cpp",
        "Libraries/USB_MSC/usb_conf.h", "USER/HAL/HAL_USB.cpp", "USER/HAL/HAL.cpp", "USER/HAL/HAL_Config.h",
        "MDK-ARM_F435/RTE/Device/-AT32F435RGT7/at32f435_437_misc.c",
        "vendor/AT32F435_437_DFP/Peripherals/inc/at32f435_437_misc.h"]
    paths = [Path(__file__), Path(base.__file__), AREA / "stack-frames1/result.json", AREA / "stack-analysis1/result.json",
             AREA / "on/symbols.log", dis_path, AREA / "prepared.json"] + [AREA / "f" / p for p in source_names]
    missing = [v for v in old["scopes"]["initialization"]["missing_frames"] if v["name"] not in MANUAL]
    store.write(out, dict(result="R2_CONDITIONAL_IRQ_ALLOWANCE", inputs=[cli.record(p) for p in paths],
        entries=entries, manually_inspected_frames=inspected, priorities=PRIORITIES, envelope=budget,
        stack_reserved_bytes=stack, conditional_thread_comparison_limit=stack-budget["total"],
        initialization_missing_frames=missing, initialization_unresolved_sites=old["scopes"]["initialization"]["unresolved"],
        test_checks=2, full_system_bound=None, status="UNKNOWN_INITIALIZATION_CONTROL_AND_FINAL_ACTIVE_SET_REVIEW",
        conditions=["Normal reset/reviewed Boot entry with NVIC disabled and cleared, SysTick stopped",
            "Source-derived candidate IRQ set only; final active-set completeness remains a review item",
            "Core_Init selects group 4 before external IRQ enabling: four preempt bits, no subpriority bits",
            "Serial default subpriority 3 does not create another preemption level in this group",
            "SysTick_Config's transient low priority occurs before external IRQ setup; explicit priority is then zero",
            "Configurable fault priorities remain reset zero; primary core fault paths are early zero-software-frame halt",
            "Up to 108 hardware bytes per level conservatively includes basic, FP and alignment frames",
            "MSP before runtime VTOR publication only; no runtime diagnostic, PSP/RTOS, debugger-state or hot-plug guarantee"],
        hardware=False, independent_acceptance=False))
    print("R2_CONDITIONAL_IRQ_ALLOWANCE", budget, "thread comparison", stack-budget["total"])
    print("initialization missing frames", missing, "unresolved control sites", len(old["scopes"]["initialization"]["unresolved"]))


if __name__ == "__main__":
    main()
