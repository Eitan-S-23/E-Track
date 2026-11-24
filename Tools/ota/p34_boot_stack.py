"""Source-bound conservative Boot call graph; explicitly separate App-vector window."""
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_boot_checkpoint_model as model

AREA = ROOT / ".cache/p34-bc-target"
# Conservative unions of bindings in boot_main, boot_recovery and boot_handoff.
CALLBACKS = {
    "boot_fw_header_validate_ex": ["image_read_bridge", "internal_flash_read", "handoff_flash_read"],
    "image_read_bridge": ["state_external_read", "state_internal_read"],
    "validate_external_source": ["state_external_read"],
    "verified_prefix_matches_source": ["state_external_read", "state_internal_read"],
    "copy_source": ["state_external_read", "state_internal_read", "state_internal_erase", "state_internal_program"],
    "boot_state_machine_run": ["state_log"],
    "read_byte": ["uart_getc"],
    "cancel_transfer": ["uart_putc"],
    "boot_ymodem_receive": ["uart_getc", "uart_putc", "recovery_begin", "recovery_write", "recovery_end", "recovery_abort"],
    "bcb_arbiter": ["eeprom_read"],
    "bcb_commit": ["eeprom_read", "eeprom_write"],
}
# Frames manually checked against every instruction of the linked routines.
ASM_FRAMES = {"Reset_Handler": 0, "ACC_IRQHandler": 0, "__aeabi_uldivmod": 16,
              "__udivmoddi4": 32, "__aeabi_idiv0": 0, "memcmp": 8, "memset": 0, "memcpy": 8}


def bound(name, graph, frames, trail=()):
    if name in trail:
        raise ValueError("recursive edge: " + " -> ".join((*trail, name)))
    if name not in graph or name not in frames:
        raise ValueError("unknown target/frame: " + name)
    children = [bound(child, graph, frames, (*trail, name)) for child in graph[name]]
    cost, path = max(children, default=(0, []), key=lambda item: item[0])
    return frames[name] + cost, [name, *path]


def parser_tests():
    # Tail edges conservatively retain the entire caller frame, never undercount.
    assert bound("a", {"a": {"b"}, "b": set()}, {"a": 8, "b": 16})[0] == 24
    for graph, frames in [({"a": {"a"}}, {"a": 8}), ({"a": {"b"}}, {"a": 8}),
                          ({"a": set()}, {})]:
        try: bound("a", graph, frames)
        except ValueError: pass
        else: raise AssertionError("unsafe graph accepted")
    return 4


def analyze(group):
    dis = (AREA / ("g%d-disassembly.log" % group)).read_text()
    nm = (AREA / ("g%d-symbols.log" % group)).read_text()
    names = {m[3]: (int(m[0], 16), int(m[1], 16)) for m in
             re.findall(r"(?m)^([0-9a-f]+) ([0-9a-f]+) ([tTwW]) (\S+)", nm)}
    functions, name = {}, None
    for line in dis.splitlines():
        header = re.match(r"^([0-9a-f]+) <([^>]+)>:", line)
        if header:
            # nm --size-sort omits size-less assembly aliases such as uldivmod.
            name = header[2] if header[2] in names or header[2] in ASM_FRAMES else None
            if name: functions[name] = []
        elif name:
            instruction = re.match(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{4,8}\s+)+)\s*([^\s]+)\s*(.*)", line)
            if instruction and not instruction[3].startswith("."):
                functions[name].append(dict(address=instruction[1], op=instruction[3], operands=instruction[4]))
    frames, origins = {}, {}
    for p in (AREA / ("b%d" % group)).rglob("*.su"):
        for line in p.read_text().splitlines():
            location, size, kind = line.rsplit("\t", 2)
            function = location.rsplit(":", 1)[1]
            if function not in functions: continue
            model.cli.require(kind == "static", "dynamic frame " + function)
            model.cli.require(function not in frames or frames[function] == int(size), "ambiguous frame " + function)
            frames[function] = int(size); origins[function] = dict(source=location, sidecar=str(p), kind=kind)
    for function, size in ASM_FRAMES.items():
        model.cli.require(function in functions, "missing reviewed assembly " + function)
        model.cli.require(function not in frames, "unexpected compiler/assembly overlap")
        frames[function] = size; origins[function] = dict(kind="linked assembly review", instructions=functions[function])
    graph = {n: set() for n in functions}
    sites, unknown = [], []
    for name, instructions in functions.items():
        for ins in instructions:
            op, args = ins["op"].split(".")[0], ins["operands"]
            target = re.search(r"\b[0-9a-f]+ <([^>]+)>", args)
            if op in {"bl", "b", "beq", "bne", "bcs", "bcc", "bhs", "blo", "bmi", "bpl", "bvs", "bvc", "bhi", "bls", "bge", "blt", "bgt", "ble", "cbz", "cbnz"}:
                if not target:
                    unknown.append(dict(function=name, **ins)); continue
                child = target[1].split("+")[0]
                if child != name or op == "bl": graph[name].add(child)
            elif op in {"blx", "bx"} and args != "lr":
                if name == "boot_branch_to_app" and op == "bx" and args == "r1":
                    sites.append(dict(function=name, boundary="App reset entry after MSP replacement", **ins))
                elif name in CALLBACKS:
                    graph[name].update(CALLBACKS[name])
                    sites.append(dict(function=name, targets=CALLBACKS[name], **ins))
                else: unknown.append(dict(function=name, **ins))
            elif re.match(r"pc,", args) and not (op.startswith("ldr") and args.startswith("pc, [sp]")):
                unknown.append(dict(function=name, **ins))
            elif op in {"tbb", "tbh"}:
                # Source-local switch, all emitted function blocks are scanned.
                sites.append(dict(function=name, boundary="local switch table; entire function scanned", **ins))
    model.cli.require(not unknown, "unclassified control transfer: " + str(unknown))
    entries = {}
    for entry in ["Reset_Handler", "main", "boot_state_machine_run", "copy_source", "boot_recovery_receive", "boot_handoff_to_app", "SysTick_Handler", "ACC_IRQHandler"]:
        try:
            size, path = bound(entry, graph, frames)
            entries[entry] = dict(bytes=size, path=path)
        except ValueError as error:
            entries[entry] = dict(bytes=None, error=str(error))
    raw = (AREA / ("b%d/boot/X-Track-Boot.bin" % group)).read_bytes()
    vectors = struct.unpack_from("<131I", raw)
    allowed = {0, names["SysTick_Handler"][0] | 1, names["ACC_IRQHandler"][0] | 1}
    model.cli.require(set(vectors[2:]) <= allowed, "unreviewed exception handler")
    return dict(entries=entries, graph={k: sorted(v) for k, v in graph.items()}, frames=frames,
                frame_origins=origins, control_sites=sites, initial_msp=vectors[0],
                exception_vector_targets=sorted(set(vectors[2:])), unknown_transfers=unknown)


def main():
    cli = model.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated project root required")
    s = cli.Store(ROOT); out = s.checked(AREA / "stack-analysis.json")
    cli.require(not out.exists(), "preserve stack evidence")
    analysis = s.read(AREA / "analysis.json")
    for r in analysis["inputs"]: cli.require(cli.record(r["path"]) == r, "artifact drift")
    snapshot = s.read(AREA / "snapshot.json")
    for r in snapshot["files"]: cli.require(cli.record(r["path"]) == r, "snapshot drift")
    paths = [Path(r["path"]) for r in analysis["inputs"]] + [Path(__file__), AREA / "analysis.json", AREA / "snapshot.json"]
    # Bind the sources used to resolve function-pointer ownership.
    paths += [AREA / "f" / p for p in ("boot/src/boot_main.c", "boot/src/boot_recovery.c",
              "boot/src/boot_state_machine.c", "boot/platform/at32/boot_handoff_at32.c",
              "boot/platform/at32/boot_platform_at32.c", "cmake/startup_at32f435_437_gcc.S")]
    sources = [cli.record(p) for p in sorted(set(paths))]
    variants = {str(g): analyze(g) for g in (1, 16)}
    cli.require(sources == [cli.record(p) for p in sorted(set(paths))], "analysis input mutation")
    s.write(out, dict(result="STACK_GRAPH_ANALYZED", inputs=sources, variants=variants,
             graph_tests=parser_tests(), tail_policy="retain caller maximum frame, conservative",
             full_system_bound=None, status="UNKNOWN_APP_VECTOR_HANDOFF_WINDOW",
             hardware=False, independent_acceptance=False))
    for g, v in variants.items(): print(g, v["entries"])


if __name__ == "__main__": main()
