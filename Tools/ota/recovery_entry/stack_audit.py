"""Conservative linked-entry graph, with an explicit fixed-callback assumption."""
import re
import struct

from p34_boot_stack import bound

BRANCHES = set("b bl beq bne bcs bcc bhs blo bmi bpl bvs bvc bhi bls bge blt bgt ble cbz cbnz".split())
# Supersets of the private callback assignments in supervisor.c. This is not
# permission to analyze arbitrary callers of runtime.c with these bindings.
CALLBACKS = {
    "re_begin": {"sample"},
    "re_begin_limited": {"sample"},
    "re_alive": {"sample"},
    "re_observe": {"owned", "read32", "write32", "read8"},
}
BCB_CALLBACKS = {
    "re_begin_limited": {"tgt_sample"}, "re_alive": {"tgt_sample"},
    "cap_owned": {"tgt_owned"}, "re_capture_once": {"tgt_owned"},
    "cap_sda": {"tgt_sda"}, "cap_scl": {"tgt_scl"},
    "cap_read_sda": {"tgt_read_sda"}, "cap_read_scl": {"tgt_read_scl"},
    "bcb_arbiter": {"snapshot_read"},
}
for _name in ("scl", "start", "stop", "send", "receive", "read_block", "rr_bcb_capture"):
    BCB_CALLBACKS[_name] = {"cap_sda", "cap_scl", "cap_read_sda", "cap_read_scl", "cap_pause"}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def load_bytes(elf, address, size):
    need(len(elf) >= 52 and elf[:7] == b"\x7fELF\x01\x01\x01", "ELF32 LE required")
    ph, = struct.unpack_from("<I", elf, 28)
    stride, count = struct.unpack_from("<HH", elf, 42)
    need(stride == 32 and ph + count * stride <= len(elf), "program table bounds")
    matches = []
    for i in range(count):
        kind, off, vma, lma, filesz, memsz, flags, align = struct.unpack_from("<8I", elf, ph+i*stride)
        if kind == 1 and vma <= address and address+size <= vma+filesz:
            need(vma == lma and off+filesz <= len(elf), "load mapping")
            matches.append(elf[off+address-vma:off+address-vma+size])
    need(len(matches) == 1, "ambiguous/missing instruction load bytes")
    return matches[0]


def analyze(elf, symbols, disassembly, sidecars, *, capability="nor"):
    need(capability in ("nor", "bcb"), "unknown capability")
    callbacks = BCB_CALLBACKS if capability == "bcb" else CALLBACKS
    # nm's T/t also labels literal tables placed in .text. Only ELF STT_FUNC
    # symbols are executable roots; treating table bytes as code is invalid.
    sh, = struct.unpack_from("<I", elf, 32)
    stride, count = struct.unpack_from("<HH", elf, 46)
    need(stride == 40 and sh+stride*count <= len(elf), "section table bounds")
    sections = [struct.unpack_from("<10I", elf, sh+i*stride) for i in range(count)]
    typed = {}
    for section in sections:
        if section[1] != 2:
            continue
        need(section[9] == 16 and section[5] % 16 == 0 and section[6] < count,
             "symbol table format")
        strings = sections[section[6]]
        need(strings[4]+strings[5] <= len(elf) and section[4]+section[5] <= len(elf),
             "symbol table bounds")
        table = elf[strings[4]:strings[4]+strings[5]]
        for off in range(section[4], section[4]+section[5], 16):
            name, address, size, info, other, index = struct.unpack_from("<IIIBBH", elf, off)
            if info & 15 != 2 or not index:
                continue
            need(name < len(table), "symbol name bounds")
            name = table[name:].split(b"\0", 1)[0].decode("ascii")
            need(name not in typed and size > 0, "duplicate/empty function")
            typed[name] = (address & ~1, size)
    names = {m[3]: (int(m[0], 16), int(m[1], 16)) for m in re.findall(
        r"(?m)^([0-9a-f]+) ([0-9a-f]+) ([tT]) (\S+)$", symbols) if m[3] in typed}
    need(names and names == typed, "function symbol/ELF mismatch")
    functions = {n: [] for n in names}
    current = None
    for line in disassembly.splitlines():
        head = re.match(r"^([0-9a-f]+) <([^>]+)>:$", line)
        if head:
            current = head[2] if head[2] in names else None
            continue
        ins = re.match(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{4}\s+)+)\s*(\S+)\s*(.*)$", line)
        if current is None or ins is None or ins[3].startswith("."):
            continue
        address = int(ins[1], 16)
        start, size = names[current]
        if not start <= address < start+size:
            continue
        raw = b"".join(int(word, 16).to_bytes(2, "little") for word in ins[2].split())
        need(address+len(raw) <= start+size, "instruction crosses function")
        need(load_bytes(elf, address, len(raw)) == raw, "disassembly differs from ELF")
        functions[current].append(dict(address=address, op=ins[3].split(".")[0], args=ins[4]))
    frames = {}
    for text in sidecars:
        for line in text.splitlines():
            location, size, kind = line.rsplit("\t", 2)
            name = location.rsplit(":", 1)[1]
            if name not in names:
                continue
            need(kind == "static", "dynamic frame: " + name)
            need(name not in frames, "duplicate frame: " + name)
            frames[name] = int(size)
    for name in ("re_bootstrap_entry", "re_terminal"):
        need(name in functions and name not in frames, "assembly frame identity")
        # No software stack frame may cross the MSP replacement.
        for ins in functions[name]:
            need(ins["op"] not in {"push", "pop", "bl", "blx", "stmdb", "ldmia"} and
                 not re.search(r"\bsp\b", ins["args"]), "assembly software stack/call")
        frames[name] = 0
    graph = {name: set() for name in names}
    sites = []
    for name, instructions in functions.items():
        need(instructions, "missing instructions: " + name)
        local = {i["address"] for i in instructions}
        for ins in instructions:
            op, args = ins["op"], ins["args"]
            need(not op.startswith("v"), "unexpected FP/vector instruction")
            if op in BRANCHES:
                match = re.search(r"\b([0-9a-f]+) <([^>]+)>", args)
                need(match is not None, "unresolved direct transfer")
                target = int(match[1], 16)
                if target in local and op != "bl":
                    continue
                matches = [n for n, (start, _) in names.items() if start == target]
                need(len(matches) == 1, "branch target is not function entry")
                graph[name].add(matches[0])
            elif op in {"blx", "bx"} and args.strip() != "lr":
                need(name in callbacks, "unbound indirect transfer: " + name)
                targets = callbacks[name]
                need(targets <= names.keys(), "missing callback target")
                graph[name].update(targets)
                sites.append(dict(function=name, targets=sorted(targets), **ins))
            elif op in {"tbb", "tbh"}:
                raise ValueError("unbound switch table")
            elif re.match(r"pc\s*,", args):
                need(op == "ldr" and re.fullmatch(r"pc, \[sp\], #4", args), "unbound PC write")
    need(set(frames) == set(names), "missing target frame")
    entries = {}
    selected = "re_capture_target_once" if capability == "bcb" else "re_supervise_once"
    for name in ("re_bootstrap_entry", selected, "re_terminal"):
        size, chain = bound(name, graph, frames)
        entries[name] = dict(software_bytes=size, chain=chain,
                             with_exception_reserve=size+216)
    need(max(e["with_exception_reserve"] for e in entries.values()) <= 8192, "stack overflow")
    return dict(entries=entries, frames=frames, graph={n: sorted(v) for n, v in graph.items()},
                callback_sites=sites, exception_reserve=216, stack_capacity=8192,
                callback_basis="private fixed " + capability + " adapter assignments; no arbitrary caller",
                tail_policy="retain full caller frame", hardware=False,
                device_execute_ready=False)
