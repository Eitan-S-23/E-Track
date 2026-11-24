"""Separate conditional Boot-MSP and App-MSP comparisons for the R2 pairing."""
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_r2_stack_inventory as base

AREA = base.AREA
BOOT = ROOT / ".cache/p34-bc-target"


def early_vectors(raw):
    vectors = struct.unpack_from("<131I", raw)
    slots = (2, 3, 4, 5, 6, 11, 12, 14)
    if vectors[0] != 0x20058000 or any(vectors[n] != 0x0801bf2b for n in slots):
        raise ValueError("R2 early vector/MSP binding changed")
    if raw[0xbf2a:0xbf2e] != bytes.fromhex("72b6fee7"):
        raise ValueError("early handler is not the bound stackless halt")
    return dict(msp=vectors[0], slots=slots, handler=0x0801bf2a, bytes="72b6fee7")


def main():
    cli = base.revision.gate.early.model.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated project root required")
    store = cli.Store(ROOT)
    out = store.checked(AREA / "two-msp1/result.json")
    cli.require(not out.exists(), "preserve two-stage evidence")
    paths = [Path(__file__), Path(base.__file__), BOOT / "stack-analysis.json",
        BOOT / "g16-disassembly.log", BOOT / "f/boot/platform/at32/boot_handoff_at32.c",
        AREA / "irq-closure1/result.json", AREA / "thread-bound1/result.json",
        AREA / "validation.json", AREA / "on/b/app-gcc/X-Track-App-GCC.bin"]
    records = [cli.record(p) for p in paths]
    boot, irq, thread, validation = (store.read(paths[i]) for i in (2, 5, 6, 7))
    for manifest in (boot, irq, thread, validation):
        for record in manifest["inputs"]:
            cli.require(cli.record(record["path"]) == record, "paired artifact drift")
    vector_proof = early_vectors(paths[8].read_bytes())
    handoff = paths[4].read_text().split("void boot_handoff_to_app(void)", 1)[1]
    tokens = ["NVIC->ICER[index] = UINT32_MAX;", "NVIC->ICPR[index] = UINT32_MAX;",
              "SysTick->CTRL = 0u;", "SCB->VTOR = OTA_APP_ORIGIN;",
              'boot_platform_log("BOOT: App vectors changed after validation',
              "boot_branch_to_app(initial_msp, reset_handler);"]
    positions = [handoff.index(t) for t in tokens]
    cli.require(positions == sorted(positions), "handoff cleanup/mismatch order changed")
    nodes = base.parser.parse(paths[3].read_text())
    branch = next(n for n in nodes.values() if n["name"] == "boot_branch_to_app")
    cli.require([(i["op"], i["args"]) for i in branch["instructions"]] ==
                [("msr", "MSP, r0"), ("dsb", "sy"), ("isb", "sy"), ("bx", "r1")],
                "MSP transition changed")
    stages = {}
    for group, variant in boot["variants"].items():
        value = variant["entries"]["Reset_Handler"]["bytes"]
        cli.require(value == 2136, "accepted Boot software bound changed")
        stages[group] = dict(boot_initial_msp=variant["initial_msp"],
            boot_msp=dict(software=value, conservative_hardware=4*108, combined=value+4*108,
                          comparison_budget=4096, comparison_margin=4096-value-4*108),
            app_msp=dict(software=thread["software_bound"], hardware_and_irq=irq["envelope"]["total"],
                         combined=irq["combined_conditional"], reserved=8192, margin=irq["margin_conditional"]))
    raw = paths[8].read_bytes()
    for off in (0, 8, 0xbf2a):
        altered = bytearray(raw)
        altered[off] ^= 1
        try:
            early_vectors(altered)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid stage pairing accepted")
    cli.require(records == [cli.record(p) for p in paths], "input drift during pairing")
    store.write(out, dict(result="R2_CONDITIONAL_TWO_MSP_PAIRING", inputs=records,
        stages=stages, early_vector_proof=vector_proof, handoff_order=positions,
        branch_instructions=branch["instructions"], negative_checks=3,
        full_system_bound=None, hardware=False, independent_acceptance=False,
        conditions=["Exact R2 primary vectors paired with the bound isolated group1/group16 Boot artifacts only",
                    "Normal reset and accepted Boot frame/callback assumptions; neither a current-device identity nor future-App guarantee",
                    "Before App VTOR all original Boot assumptions apply; after VTOR and before MSP switch external IRQs/SysTick are cleared and stopped",
                    "Core exceptions in the App-vector window use R2 stackless halt; retained four hardware frames are conservative, not an extra software allowance",
                    "Boot full thread maximum includes vector mismatch log/hold; do not treat that window as merely the four branch instructions",
                    "After MSP switch the separately derived nine-IRQ closure and accepted conditional startup thread apply",
                    "4096B Boot comparison is the prior reviewed budget, not a hardware guard; do not sum the two stages",
                    "Original reviewer must confirm the pairing; no flash, production or formal acceptance authorization implied"],
        status="TWO_STAGE_PAIRING_READY_FOR_INDEPENDENT_REVIEW"))
    print("R2_CONDITIONAL_TWO_MSP_PAIRING", stages, "negative_checks", 3)


if __name__ == "__main__":
    main()
