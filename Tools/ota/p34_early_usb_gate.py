"""EARLY-05 isolated SD readiness/USB order revision; preserve previous evidence."""
import argparse
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_early_fault as early
import p34_early_fault_build as builder
import p34_early_fault_validate as validator

OLD = ROOT / ".cache/p34-early-fault"
AREA = ROOT / ".cache/p34-early-usb"
DISK = "Libraries/USB_MSC/msc_diskio.cpp"
HEADER = "Libraries/USB_MSC/msc_diskio.h"
BOT = "Libraries/USB_MSC/msc_class/msc_bot_scsi.c"
BOT_HEADER = "Libraries/USB_MSC/msc_class/msc_bot_scsi.h"
GUARD = "defined(P34_EARLY_FAULT_VECTORS) && defined(MSC_USE_SD_CARD)"
ADAPTER = '''
#if defined(P34_EARLY_FAULT_VECTORS) && defined(MSC_USE_SD_CARD)
#include "HAL/HAL.h"
int p34_msc_media_ready(uint8_t lun)
{
  return lun == 0 && HAL::SD_GetReady();
}
#endif
'''
FAILURE = '''
#if defined(P34_EARLY_FAULT_VECTORS) && defined(MSC_USE_SD_CARD)
static usb_sts_type p34_msc_failure(void *udev, uint8_t lun,
                                     uint8_t key, uint8_t asc)
{
  usbd_core_type *pudev = (usbd_core_type *)udev;
  msc_type *pmsc = (msc_type *)pudev->class_handler->pdata;
  if(lun < MSC_SUPPORT_MAX_LUN)
  {
    pmsc->blk_nbr[lun] = 0;
    pmsc->blk_size[lun] = 0;
  }
  pmsc->data_len = 0;
  pmsc->blk_len = 0;
  for(unsigned i = 0; i < 12; ++i) pmsc->data[i] = 0;
  pmsc->msc_state = MSC_STATE_MACHINE_FAILED;
  pmsc->csw_struct.bCSWStatus = CSW_BCSWSTATUS_FAILED;
  bot_scsi_sense_code(udev, key, asc);
  return USB_FAIL;
}
#endif
'''


def replace(text, old, new, count=1):
    early.model.cli.require(text.count(old) == count, "transform anchor: " + old[:90])
    return text.replace(old, new)


def function(text, name):
    match = re.search(r"(?m)^(?:static )?(?:usb_sts_type|void|int) " + re.escape(name) + r"\([^\n]*(?:\n[^\n]*)?\)\s*\n\{", text)
    early.model.cli.require(match is not None, "missing function " + name)
    end = text.find("\n}", match.end())
    early.model.cli.require(end >= 0, "missing function end")
    return text[match.start():end+2]


def transform(relative, text):
    if relative == "USER/HAL/HAL.cpp":
        # The old OFF branch remains textually identical, including diagnostic strings.
        a = text.index('\tCONFIG_DEBUG_SERIAL.printf("USB: Initializing')
        b = text.index('\tSD_Init();', a) + len('\tSD_Init();')
        original = text[a:b]
        usb = original[:original.index('\n\tSD_Init();')].rstrip()
        text = text[:a] + '#if defined(P34_EARLY_FAULT_VECTORS)\n\tSD_Init();\n' + usb + '\n#else\n' + original + '\n#endif' + text[b:]
    elif relative == HEADER:
        marker = "uint8_t *get_inquiry(uint8_t lun);"
        text = replace(text, marker, "#if " + GUARD + "\nint p34_msc_media_ready(uint8_t lun);\n#endif\n\n" + marker)
    elif relative == DISK:
        text = replace(text, '#include <string.h>', '#include <string.h>\n' + ADAPTER)
        for name in ("msc_disk_capacity", "msc_disk_read", "msc_disk_write"):
            old = function(text, name)
            gate = "\n#if " + GUARD + "\n"
            if name == "msc_disk_capacity":
                gate += "  if(blk_nbr) *blk_nbr = 0;\n  if(blk_size) *blk_size = 0;\n"
            gate += "  if(!p34_msc_media_ready(lun)) return USB_FAIL;\n#endif\n"
            new = old.replace("\n{", "\n{" + gate, 1)
            text = replace(text, old, new)
    elif relative == BOT:
        text = replace(text, '#include "../msc_diskio.h"', '#include "../msc_diskio.h"\n' + FAILURE)
        for name in ("bot_scsi_test_unit", "bot_scsi_capacity", "bot_scsi_format_capacity",
                     "bot_scsi_read10", "bot_scsi_write10"):
            old = function(text, name)
            gate = "\n#if " + GUARD + "\n  if(!p34_msc_media_ready(lun))\n    return p34_msc_failure(udev, lun, SENSE_KEY_NOT_READY, MEDIUM_NOT_PRESENT);\n#endif\n"
            new = old.replace("\n{", "\n{" + gate, 1)
            if name in ("bot_scsi_capacity", "bot_scsi_format_capacity"):
                call = "  msc_disk_capacity(lun, &pmsc->blk_nbr[lun], &pmsc->blk_size[lun]);"
                guarded = "#if " + GUARD + "\n  if(msc_disk_capacity(lun, &pmsc->blk_nbr[lun], &pmsc->blk_size[lun]) != USB_OK ||\n     pmsc->blk_nbr[lun] == 0 || pmsc->blk_size[lun] == 0)\n    return p34_msc_failure(udev, lun, SENSE_KEY_NOT_READY, MEDIUM_NOT_PRESENT);\n#else\n" + call + "\n#endif"
                new = replace(new, call, guarded)
            if name in ("bot_scsi_read10", "bot_scsi_write10"):
                original = "      bot_scsi_sense_code(udev, SENSE_KEY_HARDWARE_ERROR, MEDIUM_NOT_PRESENT);" if name.endswith("write10") else "    bot_scsi_sense_code(udev, SENSE_KEY_HARDWARE_ERROR, MEDIUM_NOT_PRESENT);"
                # Preserve legacy/QSPI behavior; failed ON SD I/O is not reported as success.
                asc = "0x0C" if name.endswith("write10") else "0x11"
                extra = "#if " + GUARD + "\n    int ready = p34_msc_media_ready(lun);\n    return p34_msc_failure(udev, lun,\n        ready ? SENSE_KEY_MEDIUM_ERROR : SENSE_KEY_NOT_READY,\n        ready ? " + asc + " : MEDIUM_NOT_PRESENT);\n#else\n" + original + "\n#endif"
                new = replace(new, original, extra)
            text = replace(text, old, new)
    return text


def prepare(store):
    cli = early.model.cli
    cli.require(not AREA.exists(), "preserve revision")
    previous = store.read(OLD / "prepared.json")
    for r in previous["sources"] + previous["implementation"]:
        cli.require(cli.record(r["path"]) == r, "old snapshot drift")
    copies = [(Path(r["path"]), store.checked(AREA / "f" / Path(r["path"]).relative_to(OLD / "f")))
              for r in previous["sources"]]
    store.checked(AREA / "prepared.json")
    changed = []
    for source, target in copies:
        target.parent.mkdir(parents=True, exist_ok=True)
        relative = source.relative_to(OLD / "f").as_posix()
        if relative in ("USER/HAL/HAL.cpp", HEADER, DISK, BOT):
            old = source.read_text(encoding="utf-8")
            new = transform(relative, old)
            cli.require(old != new, "missing intended change")
            target.write_text(new, encoding="utf-8", newline="\n")
            changed.append(relative)
        else:
            shutil.copyfile(source, target)
    store.write(AREA / "prepared.json", dict(base=cli.record(OLD / "prepared.json"), entries=previous["entries"],
        sources=[cli.record(p) for p in sorted((AREA / "f").rglob("*")) if p.is_file()],
        implementation=[cli.record(Path(__file__)), cli.record(ROOT / "tests/boot/test_p34_early_usb_gate.cpp")],
        changed=changed, hardware=False))
    print("EARLY_USB_PREPARED changed", changed)


def tests(store):
    cli, host = early.model.cli, early.model.host
    prepared = store.read(AREA / "prepared.json")
    for r in prepared["sources"] + prepared["implementation"]:
        cli.require(cli.record(r["path"]) == r, "source drift")
    out = store.checked(AREA / "tests")
    cli.require(not out.exists(), "preserve tests")
    for n in ("types.inc", "functions.inc", "gate.exe", "compile.log", "compile.json", "run.log", "run.json", "result.json"):
        store.checked(out / n)
    for key in ("home", "userprofile", "appdata", "localappdata", "temp", "tmp", "tmpdir", "xdg_cache_home",
                "xdg_config_home", "xdg_data_home", "pythonuserbase", "pythonpycacheprefix", "ccache_dir", "sccache_dir"):
        store.checked(out / "host" / key)
    env = host.environment(store, out)
    types = (AREA / "f" / BOT_HEADER).read_text(encoding="utf-8")
    types = re.sub(r'(?m)^#include .*$', '', types)
    store.raw(out / "types.inc", types.encode())
    disk = (AREA / "f" / DISK).read_text(encoding="utf-8")
    bot = (AREA / "f" / BOT).read_text(encoding="utf-8")
    pieces = [function(disk, n) for n in ("p34_msc_media_ready", "msc_disk_capacity", "msc_disk_read", "msc_disk_write")]
    pieces += [function(bot, n) for n in ("p34_msc_failure", "bot_scsi_test_unit", "bot_scsi_capacity",
                "bot_scsi_format_capacity", "bot_scsi_check_address", "bot_scsi_read10", "bot_scsi_write10",
                "bot_scsi_datain_handler", "bot_scsi_dataout_handler", "bot_cbw_decode", "bot_scsi_send_data",
                "bot_scsi_send_csw", "bot_scsi_sense_code", "bot_scsi_stall", "bot_scsi_cmd_process")]
    store.raw(out / "functions.inc", "\n\n".join(pieces).encode())
    harness = ROOT / "tests/boot/test_p34_early_usb_gate.cpp"
    host.command(store, out, "compile", ["D:/install/mingw64/bin/g++.exe", "-std=c++11", "-O2", "-Wall", "-Werror",
                 "-I" + str(out), harness, "-o", out / "gate.exe"], env, 60)
    log = host.command(store, out, "run", [out / "gate.exe"], env, 60)
    cli.require(b"EARLY_USB_GATE_PASS" in log, "missing test result")
    paths = [Path(__file__), harness, AREA / "prepared.json", out / "types.inc", out / "functions.inc",
             out / "gate.exe", out / "compile.json", out / "compile.log", out / "run.json", out / "run.log"]
    store.write(out / "result.json", dict(result="EARLY_HOST_PASS", scope="EARLY-05 USB readiness and BOT propagation",
        inputs=[cli.record(p) for p in paths], output=log.decode(), hardware=False, independent_acceptance=False))
    print(log.decode().strip())


def build(mode):
    early.AREA = AREA
    builder.main(mode)


if __name__ == "__main__":
    early.model.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                            "isolated root required")
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "tests", "off", "on"))
    action = parser.parse_args().action
    if action in ("off", "on"):
        build(action)
    else:
        {"prepare": prepare, "tests": tests}[action](early.model.cli.Store(ROOT))
