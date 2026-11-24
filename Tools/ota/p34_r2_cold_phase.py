"""Conditional cold-start slices; preserve the unsliced R2 evidence separately."""
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_r2_stack_inventory as base

AREA = base.AREA
GPS = "_ZN3HAL13GPS_Simulator17ParseLastGPSPointEPKc"
BACKLIGHT = "_ZN3HAL20Backlight_SetGradualEtt"


def require_cold(cache, registered, anim_var, anim_getter):
    if cache != 0 or registered or anim_var != 0 or anim_getter != 0:
        raise ValueError("cold phase assumptions do not hold")


def main():
    cli = base.revision.gate.early.model.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated project root required")
    store = cli.Store(ROOT)
    out = store.checked(AREA / "cold-phase1/result.json")
    cli.require(not out.exists(), "preserve cold-phase evidence")
    source_paths = ["Simulator/LVGL.Simulator/lvgl/src/core/lv_obj.c",
        "Simulator/LVGL.Simulator/lvgl/src/draw/lv_img_cache.c",
        "Simulator/LVGL.Simulator/lvgl/src/misc/lv_fs.c",
        "Simulator/LVGL.Simulator/lvgl/src/misc/lv_anim.c",
        "USER/HAL/HAL_Backlight.cpp", "USER/HAL/HAL_GPS_Simulator.cpp",
        "USER/lv_port/lv_port_fs_sdfat.cpp", "USER/main.cpp", "USER/App/Utils/new/new.cpp"]
    paths = [Path(__file__), Path(base.__file__), Path(base.parser.__file__),
        AREA / "printf-targets1/result.json", AREA / "stack-graph1/result.json",
        AREA / "on/disassembly.log", AREA / "on/symbols.log",
        AREA / "on/b/app-gcc/X-Track-App-GCC.bin", AREA / "prepared.json"]
    paths += [AREA / "f" / p for p in source_paths]
    records = [cli.record(p) for p in paths]
    old, initial = store.read(paths[3]), store.read(paths[4])
    prepared = store.read(AREA / "prepared.json")
    for record in old["inputs"] + prepared["sources"] + prepared["implementation"]:
        cli.require(cli.record(record["path"]) == record, "input drift")
    nodes = base.parser.parse(paths[5].read_text())
    named = {n["name"]: a for a, n in nodes.items()}
    graph = {int(a, 16): set(v) for a, v in old["graph"].items()}
    raw = paths[7].read_bytes()
    words = lambda a: struct.unpack_from("<I", raw, a-0x08010000)[0]
    functions = set(old["scopes"]["initialization"]["functions"])
    all_phase = set().union(*(set(s["functions"]) for s in old["scopes"].values()))
    def parents(name, scope):
        return {nodes[a]["name"] for a in scope if named[name] in graph[a]}
    cli.require(parents("lv_fs_drv_register", set(graph)) == {"_Z15lv_port_fs_initv"},
                "additional linked filesystem registration")
    cli.require(named["_Z15lv_port_fs_initv"] not in all_phase and
                named["lv_fs_drv_register"] not in all_phase, "filesystem registration reachable before promotion")
    cli.require(parents("lv_anim_start", functions) == {BACKLIGHT}, "additional startup animation producer")
    cli.require(parents("lv_img_cache_set_size", set(graph)) == {"lv_init"}, "additional cache size writer")
    cli.require(parents("lv_img_cache_invalidate_src", functions) == {"lv_img_cache_set_size"},
                "additional startup cache invalidation")
    symbols = paths[6].read_text()
    bss = {}
    for name in ("lv_initialized", "_lv_img_cache_array", "_lv_fsdrv_ll"):
        match = re.search(r"(?m)^([0-9a-f]+) ([0-9a-f]+) [bB] " + name + r"$", symbols)
        cli.require(match is not None, "cold state is not BSS")
        bss[name] = dict(address=int(match[1], 16), bytes=int(match[2], 16))
    cli.require(words(0x08024f08) == bss["_lv_img_cache_array"]["address"] and
                words(0x0802b4dc) == bss["_lv_fsdrv_ll"]["address"] and
                words(0x0802b80c) == bss["_lv_fsdrv_ll"]["address"], "state literal mismatch")
    checks = {}
    def check(name, address, op, args):
        i = next(i for i in nodes[named[name]]["instructions"] if i["address"] == address)
        cli.require(i["op"] == op and i["args"].split("\t")[0] == args, "phase instruction changed")
        checks.setdefault(name, []).append(i)
    check("lv_init", 0x0801e5be, "cbnz", "r3, 801e604 <lv_init+0x4c>")
    check("lv_img_cache_set_size", 0x08024ed8, "cbz", "r3, 8024ee6 <lv_img_cache_set_size+0x16>")
    check("_lv_ll_init", 0x0802b918, "movs", "r3, #0")
    check("_lv_ll_init", 0x0802b91e, "strd", "r3, r3, [r0, #4]")
    check("_lv_ll_get_head", 0x0802ba0c, "ldr", "r0, [r0, #4]")
    check("lv_fs_get_drv", 0x0802b7f2, "cbnz", "r1, 802b7f8 <lv_fs_get_drv+0x14>")
    check("lv_fs_open", 0x0802b822, "cbz", "r0, 802b880 <lv_fs_open+0x70>")
    check("lv_fs_open", 0x0802b880, "movs", "r0, #3")
    check(GPS, 0x080445de, "cbnz", "r0, 8044620 <_ZN3HAL13GPS_Simulator17ParseLastGPSPointEPKc+0x58>")
    check("lv_anim_init", 0x0802ab4e, "movs", "r2, #64")
    check("lv_anim_init", 0x0802ab50, "movs", "r1, #0")
    check("lv_anim_init", 0x0802ab54, "bl", "8056d0c <memset>")
    check("lv_anim_start", 0x0802ac72, "cbz", "r3, 802ac84 <lv_anim_start+0x6c>")
    check("lv_anim_start", 0x0802ac8a, "cbz", "r0, 802ac90 <lv_anim_start+0x78>")
    # The sole startup producer writes neither var (+0) nor get_value_cb (+16).
    producer = nodes[named[BACKLIGHT]]["instructions"]
    stores = [(i["op"], i["args"].split("\t")[0]) for i in producer if i["op"].startswith("str")]
    cli.require(stores == [("str", "r3, [sp, #4]"), ("str", "r3, [sp, #24]"),
                          ("strd", "r0, r0, [sp, #28]"), ("strd", "r5, r4, [sp, #36]")],
                "startup descriptor writes changed")
    require_cold(0, False, 0, 0)
    for values in ((1, False, 0, 0), (0, True, 0, 0), (0, False, 1, 0), (0, False, 0, 1)):
        try:
            require_cold(*values)
        except ValueError:
            pass
        else:
            raise AssertionError("non-cold state accepted")
    removed = []
    def restrict(name, allowed):
        a = named[name]
        keep = {named[n] for n in allowed}
        cli.require(keep <= graph[a], "expected slice edge missing")
        removed.extend(dict(caller=name, target=nodes[v]["name"]) for v in sorted(graph[a]-keep))
        graph[a] = keep
    graph[named["lv_img_cache_set_size"]].remove(named["lv_img_cache_invalidate_src"])
    removed.append(dict(caller="lv_img_cache_set_size", target="lv_img_cache_invalidate_src"))
    restrict(GPS, ["lv_fs_open"])
    restrict("lv_fs_open", ["lv_fs_get_drv"])
    restrict("lv_fs_get_drv", ["_lv_ll_get_head"])
    pending = {i["address"]: i for s in old["scopes"].values() for i in s["unresolved"]}
    suppressed = [pending.pop(a) for a in (0x0802b830, 0x0802b848, 0x0802ac76, 0x0802ac8e)]
    scopes = {}
    for name, scope in initial["scopes"].items():
        found = base.parser.reachable(scope["roots"], graph)
        scopes[name] = dict(roots=scope["roots"], functions=sorted(found),
            unresolved=[i for i in pending.values() if i["function"] in found],
            missing_frames=[v for v in old["scopes"][name]["missing_frames"] if v["address"] in found])
    cli.require(records == [cli.record(p) for p in paths], "inputs changed during phase analysis")
    store.write(out, dict(result="R2_CONDITIONAL_COLD_PHASE", inputs=records, bss=bss,
        checks=checks, producer=producer, tests=5, removed_edges=removed, suppressed_sites=suppressed,
        graph={hex(a): sorted(v) for a, v in graph.items()}, frames=old["frames"], scopes=scopes,
        total_system_bound=None, hardware=False, independent_acceptance=False,
        conditions=["Normal data/BSS initialization, no memory corruption, single cold startup before promotion",
                    "No unresolved indirect edge may add filesystem registration, cache resizing or animation producers",
                    "LVGL init is non-reentrant; completed repeated calls return through lv_initialized",
                    "These slices do not apply to post-promotion runtime, hotplug or a warm HAL reinitialization"],
        status="CONDITIONAL_PHASE_EVIDENCE_PENDING_REVIEW_AND_REMAINING_CONTROL"))
    print("R2_CONDITIONAL_COLD_PHASE", {n: (len(s["functions"]), len(s["unresolved"])) for n, s in scopes.items()}, "tests", 5)


if __name__ == "__main__":
    main()
