"""Reusable bounded Commander read batch; caller must have device/MRU authority."""
from pathlib import Path
import re

import p34_early_identity as identity


def run(out, regions, *, seconds=90):
    cli, host, device = identity.cli, identity.host, identity.device
    store = cli.Store(identity.ROOT)
    out = store.checked(out)
    cli.require(not out.exists() and 0 < seconds <= 180, "fresh bounded read batch required")
    allowed = ((0x08000000, 0x08100000), (0x90000000, 0x90300000),
               (0xe000edf0, 0xe000edf4), (0xe000ed08, 0xe000ed0c), (0xa0001010, 0xa0001014))
    cli.require(regions and sum(size for _, size in regions.values()) <= 0x301000, "read scope too large")
    for name, (address, size) in regions.items():
        cli.require(re.fullmatch(r"[a-z_]+", name) is not None and 0 < size <= 0x100000 and
                    any(a <= address < address+size <= b for a, b in allowed), "unapproved read range/name")
        store.checked(out / (name+".bin"))
    for name in ("result.json", "commands.jlink", "settings.jlink", "sdk.log", "command.json", "command.log"):
        store.checked(out / name)
    for name in ("home", "userprofile", "appdata", "localappdata", "temp", "tmp", "tmpdir", "xdg_cache_home",
                 "xdg_config_home", "xdg_data_home", "pythonuserbase", "pythonpycacheprefix", "ccache_dir", "sccache_dir"):
        store.checked(out / "host" / name)
    device.IO["checked_output"](device.MRU.parent, device.MRU)
    env = host.environment(store, out)
    lines = ["exec DisableAutoUpdateFW", "exec SetEnableMemCache = 0", "exec InvalidateCache",
             "exec ExcludeFlashCacheRange 0x08000000-0x080FFFFF",
             "exec ExcludeFlashCacheRange 0x90000000-0x902FFFFF"]
    lines += ["savebin " + device.quote(out / (name+".bin")) + ", 0x%08X, 0x%X" % region
              for name, region in regions.items()]
    lines.append("qc")
    store.raw(out / "commands.jlink", ("\n".join(lines)+"\n").encode("ascii"))
    result = dict(result="READ_FAILED", source=cli.record(Path(__file__)), regions=regions,
                  mru_before=cli.record(device.MRU), flash_commands=0, reset_commands=0, halt_commands=0)
    try:
        result["presence"] = identity.native.native_presence()
        data = host.command(store, out, "command", [device.JLINK, "-Device", "AT32F435RGT7", "-If", "SWD",
            "-Speed", "1000", "-USB", "123456", "-AutoConnect", "1", "-ExitOnError", "1", "-NoGui", "1",
            "-SettingsFile", out / "settings.jlink", "-Log", out / "sdk.log", "-CommandFile", out / "commands.jlink"], env, seconds)
        cli.require(b"Not all bytes" not in data, "partial Commander read")
        for name, (_, size) in regions.items():
            cli.require((out / (name+".bin")).stat().st_size == size, "short read")
        result["result"] = "READ_COMPLETED"
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    finally:
        result["mru_after"] = cli.record(device.MRU)
        result["files"] = [cli.record(p) for p in sorted(out.iterdir()) if p.is_file()]
        store.write(out / "result.json", result)
    cli.require(result["result"] == "READ_COMPLETED", result.get("error", "read failed"))
    return result
