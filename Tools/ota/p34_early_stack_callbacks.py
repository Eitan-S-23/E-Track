"""Resolve bounded startup callback families against the existing ON image."""
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_early_stack_graph as base

AREA = base.AREA


def table(raw, symbols, nodes, name, expected):
    address = symbols[name]
    offset = symbols["_sidata"] - 0x08010000 + address - symbols["_sdata"]
    if not symbols["_sdata"] <= address or offset < 0 or offset + 4*len(expected) > len(raw):
        raise ValueError("callback table outside initialized image")
    words = struct.unpack_from("<%dI" % len(expected), raw, offset)
    targets = []
    for word, wanted in zip(words, expected):
        if not word & 1 or word & ~1 not in nodes or nodes[word & ~1]["name"] != wanted:
            raise ValueError("callback table target mismatch: " + wanted)
        targets.append(word & ~1)
    return dict(symbol=name, ram_address=address, image_offset=offset, words=list(words), targets=targets)


def main():
    cli = base.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated root required")
    store = cli.Store(ROOT)
    out = store.checked(AREA / "stack-callbacks1/result.json")
    cli.require(not out.exists(), "preserve callback evidence")
    old = store.read(AREA / "stack-graph1/result.json")
    for record in old["inputs"]:
        cli.require(cli.record(record["path"]) == record, "graph input drift")
    prepared = store.read(AREA / "prepared.json")
    for record in prepared["sources"] + prepared["implementation"]:
        cli.require(cli.record(record["path"]) == record, "prepared source drift")
    sources = ["USER/HAL/HAL.cpp", "USER/HAL/HAL_Bluetooth.cpp", "USER/HAL/HAL_Encoder.cpp",
               "USER/HAL/HAL_Audio.cpp", "USER/HAL/HAL_USB.cpp", "USER/main.cpp",
               "MDK-ARM_F435/Platform/Core/HardwareSerial.cpp", "MDK-ARM_F435/Platform/Core/timer.c",
               "MDK-ARM_F435/Platform/HAL/HAL_Display.cpp", "MDK-ARM_F435/Platform/lv_port/lv_port_disp.cpp",
               "Libraries/ButtonEvent/ButtonEvent.cpp", "USER/App/Utils/TonePlayer/TonePlayer.cpp",
               "Libraries/USB_MSC/msc_class/msc_class.c", "Libraries/USB_MSC/msc_class/msc_desc.c",
               "MDK-ARM_F435/Platform/middlewares/usb_drivers/src/usbd_core.c",
               "MDK-ARM_F435/Platform/middlewares/usb_drivers/src/usbd_int.c",
               "MDK-ARM_F435/Platform/middlewares/usb_drivers/src/usbd_sdr.c"]
    paths = [Path(__file__), Path(base.__file__), AREA / "stack-graph1/result.json",
             AREA / "on/disassembly.log", AREA / "on/symbols.log",
             AREA / "on/b/app-gcc/X-Track-App-GCC.bin"] + [AREA / "f" / p for p in sources]
    records = [cli.record(p) for p in paths]
    nodes = base.parse(paths[3].read_text())
    named = {n["name"]: a for a, n in nodes.items()}
    graph, unknown, _ = base.edges(nodes, old["main_inclusive_cutoff"])
    libc = named["__libc_init_array"]
    graph[libc].update(old["constructors"])
    unknown[libc] = []
    symbols = {m[2]: int(m[0], 16) for m in re.findall(
        r"(?m)^([0-9a-f]+) (?:[0-9a-f]+ )?([A-Za-z]) (\S+)\s*$", paths[4].read_text())}
    raw = paths[5].read_bytes()
    class_names = ["class_%s_handler" % s for s in
                   ("init", "clear", "setup", "ept0_tx", "ept0_rx", "in", "out", "sof", "event")]
    desc_names = ["get_device_" + s for s in
                  ("descriptor", "qualifier", "configuration", "other_speed", "lang_id",
                   "manufacturer_string", "product_string", "serial_string", "interface_string", "config_string")]
    tables = [table(raw, symbols, nodes, "msc_class_handler", class_names),
              table(raw, symbols, nodes, "msc_desc_handler", desc_names)]
    usb_targets = sorted(set(t for t in tables for t in t["targets"]))
    bindings = {
        "_ZN14HardwareSerial10IRQHandlerEv": ["_ZL12ble_isr_hookP14HardwareSerial"],
        "TMR4_GLOBAL_IRQHandler": ["_ZL24HAL_TimerInterrputUpdatev"],
        "_ZN11ButtonEvent12EventMonitorEb": ["_ZL19Encoder_PushHandlerP11ButtonEventi",
                                                "_ZL16Encoder_BHandlerP11ButtonEventi",
                                                "_ZL16Encoder_AHandlerP11ButtonEventi"],
        "_ZN10TonePlayer6UpdateEm": ["_ZZN3HAL10Audio_InitEvENUlmtE_4_FUNEmt"],
    }
    resolved = []
    for address, node in nodes.items():
        keep = []
        for ins in unknown[address]:
            targets, reason = None, None
            if ins["op"] == "ldr.w" and re.fullmatch(r"pc, \[sp\], #(4|8)", ins["args"]):
                targets, reason = [], "postindexed stack return; frame still requires analysis"
            elif node["name"] in bindings and ins["op"] in ("blx", "bx"):
                targets = [named[n] for n in bindings[node["name"]]]
                reason = "startup callback target union from bound registration sources"
            elif node["name"].startswith("usbd_") and ins["op"] in ("blx", "bx"):
                targets = usb_targets
                reason = "conservative union of all bound MSC class and descriptor table targets"
            if targets is None:
                keep.append(ins)
            else:
                graph[address].update(targets)
                resolved.append(dict(ins, function=address, name=node["name"], targets=targets, reason=reason))
        unknown[address] = keep
    # Reject byte-level table corruption rather than trusting source declarations alone.
    negatives = 0
    for item, expected in zip(tables, (class_names, desc_names)):
        bad = bytearray(raw)
        bad[item["image_offset"]] ^= 1
        try:
            table(bad, symbols, nodes, item["symbol"], expected)
        except ValueError:
            negatives += 1
        else:
            raise AssertionError("non-Thumb callback accepted")
    scopes = {}
    for name, scope in old["scopes"].items():
        found = base.reachable(scope["roots"], graph)
        scopes[name] = dict(roots=scope["roots"], functions=sorted(found), count=len(found),
                           unresolved=[dict(function=a, name=nodes[a]["name"], **i)
                                       for a in sorted(found) for i in unknown[a]])
    cli.require(records == [cli.record(p) for p in paths], "inputs changed")
    store.write(out, dict(result="EARLY_CALLBACK_GRAPH_REFINEMENT", inputs=records,
                         tables=tables, table_negative_checks=negatives, resolved=resolved, scopes=scopes,
                         graph={hex(a): sorted(v) for a, v in graph.items()}, total_bound=None,
                         status="UNKNOWN_REMAINING_EDGES_FRAMES_AND_NESTING",
                         assumptions=["Normal reset; no arbitrary RAM corruption or pointer overwrite",
                                      "Only the bound startup registrations precede promotion",
                                      "USB table target union deliberately overapproximates individual slots"],
                         hardware=False, independent_acceptance=False))
    for name, scope in scopes.items():
        print(name, "functions", scope["count"], "unresolved", len(scope["unresolved"]))
    print("callback tables", len(tables), "negative checks", negatives, "resolved sites", len(resolved))


if __name__ == "__main__":
    main()
