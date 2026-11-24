"""Bracket the authorized NOR identity reads with matched-App idle observations."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_early_identity as identity
import p34_early_fault_validate as artifact


def snapshot(stage):
    cli, host, device = identity.cli, identity.host, identity.device
    store = cli.Store(ROOT)
    out = store.checked(identity.AREA / stage)
    cli.require(not out.exists(), "preserve idle observation")
    symbols_path = ROOT / ".cache/p34-app-handoff/symbols.log"
    dis_path = ROOT / ".cache/p34-app-handoff/disassembly.log"
    symbols = artifact.parse_symbols(symbols_path.read_text())
    dis = dis_path.read_text()
    cli.require("#204" in artifact.function(dis, "ota_ble_session_active") and
                "#428" in artifact.function(dis, "ota_ble_session_isr_active"), "session offsets changed")
    regions = dict(app_header=(0x08010000, 0x460), session=(symbols["_ZL13s_ble_session"], 576),
                   core=(0xe000edf0, 4), vtor=(0xe000ed08, 4), qspi=(0xa0001010, 4))
    for name in ("result.json", "commands.jlink", "settings.jlink", "sdk.log", "command.json", "command.log"):
        store.checked(out / name)
    for name in regions:
        store.checked(out / (name+".bin"))
    for name in ("home", "userprofile", "appdata", "localappdata", "temp", "tmp", "tmpdir", "xdg_cache_home",
                 "xdg_config_home", "xdg_data_home", "pythonuserbase", "pythonpycacheprefix", "ccache_dir", "sccache_dir"):
        store.checked(out / "host" / name)
    env = host.environment(store, out)
    lines = ["exec DisableAutoUpdateFW", "exec SetEnableMemCache = 0", "exec InvalidateCache",
             "exec ExcludeFlashCacheRange 0x08000000-0x080FFFFF"]
    for name, (address, size) in regions.items():
        lines.append("savebin " + device.quote(out / (name+".bin")) + ", 0x%08X, 0x%X" % (address, size))
    lines.append("qc")
    store.raw(out / "commands.jlink", ("\n".join(lines)+"\n").encode("ascii"))
    result = dict(result="IDLE_OBSERVATION_FAILED", source=cli.record(Path(__file__)),
                  inputs=[cli.record(symbols_path), cli.record(dis_path)], mru_before=cli.record(device.MRU),
                  flash=0, reset=0, halt=0)
    try:
        result["presence"] = identity.native.native_presence()
        data = host.command(store, out, "command", [device.JLINK, "-Device", "AT32F435RGT7", "-If", "SWD",
            "-Speed", "1000", "-USB", "123456", "-AutoConnect", "1", "-ExitOnError", "1", "-NoGui", "1",
            "-SettingsFile", out / "settings.jlink", "-Log", out / "sdk.log", "-CommandFile", out / "commands.jlink"], env, 60)
        cli.require(b"Not all bytes" not in data, "partial idle observation")
        raw = {n: (out / (n+".bin")).read_bytes() for n in regions}
        cli.require(all(len(raw[n]) == size for n, (_, size) in regions.items()), "short idle read")
        initial = (identity.AREA / "initial/app_slot.bin").read_bytes()
        cli.require(raw["app_header"] == initial[:0x460], "App identity header changed")
        core, vtor, qspi = [int.from_bytes(raw[n], "little") for n in ("core", "vtor", "qspi")]
        cli.require(not core & (1 << 17) and vtor == 0x08010000, "halted/wrong App phase")
        cli.require(qspi & (1 << 20) and not qspi & (7 << 16), "XIP unavailable/busy")
        cli.require(raw["session"][204] == raw["session"][428] == 0, "active BLE OTA; no NOR reads")
        result.update(result="IDLE_XIP_OBSERVED", state=raw["session"][204], isr_active=raw["session"][428],
                      vtor=vtor, core=core, qspi=qspi, atomic_snapshot=False)
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    finally:
        result["mru_after"] = cli.record(device.MRU)
        result["files"] = [cli.record(p) for p in sorted(out.glob("*.bin"))]
        store.write(out / "result.json", result)
    cli.require(result["result"] == "IDLE_XIP_OBSERVED", result.get("error", "idle observation failed"))
    print(stage, "IDLE_XIP_OBSERVED", flush=True)


def main():
    identity.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                         sys.dont_write_bytecode, "isolated project root required")
    initial = identity.cli.Store(ROOT).read(identity.AREA / "initial/result.json")
    identity.cli.require(initial["result"] == "INITIAL_IDENTITY_MATCHED", "initial match required")
    for record in initial["files"]:
        identity.cli.require(identity.cli.record(record["path"]) == record, "initial evidence drift")
    snapshot("idle")
    sys.argv = [str(identity.__file__), "nor"]
    code = identity.main()
    identity.cli.require(code == 0, "NOR observation failed; preserve result")
    snapshot("post")


if __name__ == "__main__":
    main()
