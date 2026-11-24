"""Instruction-level stack proof for the selected R2 shared arithmetic bodies."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_r2_stack_inventory as base

AREA = base.AREA
NAMES = ("__adddf3", "__aeabi_ui2d", "__aeabi_i2d", "__aeabi_l2d",
         "__aeabi_dmul", "__aeabi_ddiv")
CONDITIONS = set("eq ne cs cc hs lo mi pl vs vc hi ls ge lt gt le".split())
EXTERNAL_RETURN = -1


def reglist(args):
    match = re.fullmatch(r"\{([^}]+)\}", args)
    if not match:
        raise ValueError("unsupported register list")
    names = match[1].replace(" ", "").split(",")
    order = {**{f"r{i}": i for i in range(13)}, "sl": 10, "fp": 11,
             "ip": 12, "lr": 14, "pc": 15}
    if any(n not in order for n in names) or len(set(names)) != len(names):
        raise ValueError("unsupported register name")
    if names != sorted(names, key=order.get):
        raise ValueError("register list is not architectural order")
    return names


def leaf_bound(entry, bodies):
    """Explore flags nondeterministically; preserve saved LR values on the stack."""
    instructions, following = {}, {}
    for body in bodies:
        for i, ins in enumerate(body):
            address = ins["address"]
            if address in instructions:
                raise ValueError("overlapping instruction bodies")
            instructions[address] = ins
            following[address] = body[i + 1]["address"] if i + 1 < len(body) else None
    todo, seen, reached = [(entry, (), EXTERNAL_RETURN)], set(), set()
    maximum, exits = 0, 0
    while todo:
        pc, stack, lr = state = todo.pop()
        if state in seen:
            continue
        if len(seen) >= 50000 or len(stack) > 128:
            raise ValueError("state/growing-stack bound exceeded")
        seen.add(state)
        if pc not in instructions:
            raise ValueError("control escapes bound instruction set")
        reached.add(pc)
        ins = instructions[pc]
        op, args = ins["op"].split(".")[0], ins["args"]
        nxt = following[pc]
        maximum = max(maximum, 4 * len(stack))
        conditional = False
        stem = op
        for prefix in ("push", "pop", "blx", "bx", "bl", "b"):
            if op == prefix or op[len(prefix):] in CONDITIONS and op.startswith(prefix):
                stem, conditional = prefix, op != prefix
                break
        if conditional:
            todo.append((nxt, stack, lr))
        if stem == "push":
            values = tuple(lr if r == "lr" else None for r in reglist(args))
            todo.append((nxt, values + stack, lr))
        elif stem == "pop":
            regs = reglist(args)
            if len(stack) < len(regs):
                raise ValueError("stack underflow")
            values = dict(zip(regs, stack))
            tail = stack[len(regs):]
            lr = values.get("lr", lr)
            target = values.get("pc", nxt)
            if "pc" in values and target == EXTERNAL_RETURN:
                if tail:
                    raise ValueError("unbalanced external return")
                exits += 1
            elif target is None:
                raise ValueError("unknown popped PC")
            else:
                todo.append((target, tail, lr))
        elif stem in ("b", "bl") or op in ("cbz", "cbnz"):
            match = re.search(r"\b([0-9a-f]+) <", args)
            if not match:
                raise ValueError("unknown direct target")
            if op in ("cbz", "cbnz"):
                todo.append((nxt, stack, lr))
            todo.append((int(match[1], 16), stack, nxt if stem == "bl" else lr))
        elif stem == "bx":
            if args != "lr" or lr is None:
                raise ValueError("unknown register return")
            if lr == EXTERNAL_RETURN:
                if stack:
                    raise ValueError("unbalanced LR return")
                exits += 1
            else:
                todo.append((lr, stack, lr))
        else:
            if (stem == "blx" or op in ("tbb", "tbh", "svc", "bkpt", "msr") or
                    op.startswith(("ldm", "stm", "vpush", "vpop", "vldm", "vstm", "rfe", "srs")) or
                    re.search(r"\b(?:sp|pc)\b", args)):
                raise ValueError("unclassified stack/control instruction")
            # Arithmetic helpers use LR as scratch after saving the real return.
            if args.startswith("lr,") and not op.startswith(("cmp", "cmn", "tst", "teq")):
                lr = None
            todo.append((nxt, stack, lr))
    if not exits:
        raise ValueError("no balanced return")
    return dict(bytes=maximum, states=len(seen), exits=exits, instructions=sorted(reached))


def tests():
    def ins(a, op, args):
        return dict(address=a, op=op, args=args)
    body = [ins(16, "push", "{r4, lr}"), ins(18, "bleq", "20 <helper>"),
            ins(22, "pop", "{r4, pc}"), ins(32, "bx", "lr")]
    assert leaf_bound(16, [body])["bytes"] == 8
    shared = [ins(48, "push", "{r4, lr}"), ins(50, "b", "16 <entry+6>")]
    assert leaf_bound(48, [body, shared])["bytes"] == 8
    dead = [ins(16, "bx", "lr"), ins(18, "b", "99 <dead>")]
    assert leaf_bound(16, [dead])["instructions"] == [16]
    bad = [[ins(16, "bx", "r3")], [ins(16, "pop", "{pc}")],
           [ins(16, "mov", "sp, r3")], [ins(16, "b", "99 <missing>")],
           [ins(16, "push", "{r4, lr}"), ins(18, "b", "10 <again>")],
           [ins(16, "mov", "lr, r3"), ins(18, "bx", "lr")],
           [ins(16, "vpush", "{d8-d9}")]]
    for body in bad:
        try:
            leaf_bound(16, [body])
        except ValueError:
            pass
        else:
            raise AssertionError("unknown/unsafe instruction path accepted")
    return 10


def main():
    cli = base.revision.gate.early.model.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated project root required")
    store = cli.Store(ROOT)
    out = store.checked(AREA / "arithmetic-stack1/result.json")
    cli.require(not out.exists(), "preserve arithmetic evidence")
    paths = [Path(__file__), Path(base.__file__), Path(base.parser.__file__),
             AREA / "stack-frames1/result.json", AREA / "stack-analysis1/result.json",
             AREA / "on/disassembly.log", AREA / "on/b/app-gcc/X-Track-App-GCC.bin"]
    records = [cli.record(p) for p in paths]
    old = store.read(paths[3])
    for manifest in (old, store.read(paths[4])):
        for record in manifest["inputs"]:
            cli.require(cli.record(record["path"]) == record, "bound input drift")
    nodes = base.parser.parse(paths[5].read_text())
    named = {node["name"]: a for a, node in nodes.items()}
    bodies = [nodes[named[name]]["instructions"] for name in NAMES]
    checks = tests()
    proofs = {name: leaf_bound(named[name], bodies) for name in NAMES}
    closed = [i for i in old["scopes"]["initialization"]["unresolved"] if i["name"] in NAMES]
    unreachable = [i for i in closed if i["address"] not in proofs[i["name"]]["instructions"]]
    # This literal dead fragment follows an unconditional branch and has no incoming edge.
    cli.require([i["address"] for i in unreachable] == [0x0805370c], "unreviewed dead fragment")
    cli.require(not any(re.search(r"\b805370[8c] <", ins["args"])
                        for node in nodes.values() for ins in node["instructions"]),
                "dead fragment has a direct incoming reference")
    for site in closed:
        site["disposition"] = ("unreachable from selected arithmetic entry" if site in unreachable
                               else "visited with explicit saved-return tracking")
    cli.require(records == [cli.record(p) for p in paths], "inputs changed during analysis")
    store.write(out, dict(result="R2_SHARED_ARITHMETIC_LEAF_STACK", inputs=records,
        tests=checks, proofs=proofs, classified_sites=closed, total_system_bound=None,
        hardware=False, independent_acceptance=False,
        limits=["Bounded linked arithmetic instruction set only; not a general ARM emulator",
                "Flags are nondeterministic, LR and saved return words tracked, unknown control rejected",
                "Leaf bounds include shared code; do not add another owner-symbol frame",
                "Initialization callbacks, unwind and final IRQ active-set remain unresolved"]))
    print("R2_SHARED_ARITHMETIC_LEAF_STACK", {n: p["bytes"] for n, p in proofs.items()},
          "classified_sites", len(closed), "tests", checks)


if __name__ == "__main__":
    main()
