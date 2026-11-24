"""Host-only real Boot checkpoint recovery experiment; no firmware target builds."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_install_cost as host
cli = host.cli
AREA = ROOT / ".cache/p34-boot-checkpoint"
POLICY = ROOT / "Tools/ota/p34_boot_checkpoint.h"
HOOK = ROOT / "tests/boot/p34_checkpoint_hook.h"
HARNESS = ROOT / "tests/boot/test_p34_boot_checkpoint.c"
BOOT = ROOT / "boot/src/boot_state_machine.c"
FIXTURE = ROOT / "tests/boot/test_boot_state_machine.c"
OLD = '''        next = *current;
        next.resume_block = (uint16_t)(block + 1u);
        if (commit_record(io, active, current, &next) != 0)
        {
            return BOOT_STATE_STATUS_COMMIT;
        }
        boot_p1_6_checkpoint(OTA_P1_6_CP_COPY_RESUME_COMMITTED,
                             current->copy_phase, current->resume_block);'''
NEW = '''        if (p34_boot_checkpoint_due(current->copy_phase == BCB_COPY_APPLY,
                                    block + 1u, block_count))
        {
            next = *current;
            next.resume_block = (uint16_t)(block + 1u);
            if (commit_record(io, active, current, &next) != 0)
            {
                return BOOT_STATE_STATUS_COMMIT;
            }
            boot_p1_6_checkpoint(OTA_P1_6_CP_COPY_RESUME_COMMITTED,
                                 current->copy_phase, current->resume_block);
        }'''


def prepare(s):
    for leaf in ("boot_state_machine.c", "fixture.c", "prepared.json"):
        cli.require(not s.checked(AREA/leaf).exists(), "preserve prepared model")
    prior = s.read(ROOT/".cache/p34-boot/preparation/result.json")
    record = next(x for x in prior["sources"] if Path(x["path"]) == BOOT)
    cli.require(cli.record(BOOT) == record, "installed Boot source changed")
    AREA.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BOOT, AREA/"boot_state_machine.c")
    shutil.copyfile(FIXTURE, AREA/"fixture.c")
    s.write(AREA/"prepared.json", dict(boot=record, fixture=cli.record(FIXTURE), device_operations=0))
    print("MODEL_SOURCE_COPIED; apply isolated integration patch before test")


def validate(s):
    prepared=s.read(AREA/"prepared.json")
    cli.require(cli.record(BOOT)==prepared["boot"] and cli.record(FIXTURE)==prepared["fixture"], "baseline changed")
    original=BOOT.read_text(encoding="utf-8")
    cli.require(original.count(OLD)==1, "ambiguous copy checkpoint anchor")
    expected=original.replace('#include "boot_state_machine.h"', '#include "boot_state_machine.h"\n#include "p34_boot_checkpoint.h"', 1).replace(OLD,NEW)
    cli.require((AREA/"boot_state_machine.c").read_text(encoding="utf-8")==expected, "unexpected Boot delta")
    expected=FIXTURE.read_text(encoding="utf-8").replace('TEST_IMAGE_LEN = 0x2800','TEST_IMAGE_LEN = 617588').replace('TEST_BLOCK_COUNT = 3','TEST_BLOCK_COUNT = 151').replace('TEST_HISTORY_MAX = 64','TEST_HISTORY_MAX = 4096')
    cli.require((AREA/"fixture.c").read_text(encoding="utf-8")==expected, "unexpected fixture delta")


def test(s, out):
    out=s.checked(out)
    cli.require(not out.exists(), "preserve model test evidence")
    validate(s)
    common=[ROOT/p for p in ("boot/src/boot_fw_header.c", "boot/src/boot_slot.c",
        "boot/src/boot_crc32.c", "boot/src/boot_sha256.c", "Libraries/EEPROM/eeprom_bcb.c")]
    paths=[BOOT,FIXTURE,POLICY,HOOK,HARNESS,Path(__file__),AREA/"boot_state_machine.c",AREA/"fixture.c",*common]
    paths += sorted((ROOT/"boot/include").glob("*.h")) + sorted((ROOT/"Libraries/OTA").glob("*.h")) + sorted((ROOT/"Libraries/EEPROM").glob("*.h"))
    bound=[cli.record(p) for p in paths]
    variants=("baseline", "default_control", "g1", "g4", "g16")
    for name in variants:
        s.checked(out/(name+".exe"))
        for tag in ("compile", "run"):
            for suffix in (".json", ".log"):s.checked(out/(name+"-"+tag+suffix))
    s.checked(out/"result.json")
    for key in ("HOME","USERPROFILE","APPDATA","LOCALAPPDATA","TEMP","TMP","TMPDIR","XDG_CACHE_HOME","XDG_CONFIG_HOME","XDG_DATA_HOME","PYTHONUSERBASE","PYTHONPYCACHEPREFIX","CCACHE_DIR","SCCACHE_DIR"):
        s.checked(out/"host"/key.lower())
    env=host.environment(s,out)
    base=["D:/install/mingw64/bin/gcc.exe","-std=c99","-O2","-Wall","-Wextra","-Werror",
          "-DP34_BOOT_SKIP_IDENTICAL_BLOCKS=1","-I"+str(ROOT/"boot/include"),"-I"+str(ROOT/"Libraries"),"-I"+str(ROOT/"Tools/ota"),"-I"+str(AREA)]
    results={}
    for name in variants:
        small=name in ("baseline","default_control")
        args=base+([] if small else ["-DP34_BOOT_APPLY_CHECKPOINT_BLOCKS="+name[1:],"-include",HOOK])
        args += [FIXTURE if small else HARNESS, BOOT if name=="baseline" else AREA/"boot_state_machine.c",*common,"-o",out/(name+".exe")]
        host.command(s,out,name+"-compile",args,env,120)
        if name=="default_control":
            cli.require((out/(name+".exe")).read_bytes()==(out/"baseline.exe").read_bytes(),
                        "default-off native executable differs from baseline")
        raw=host.command(s,out,name+"-run",[out/(name+".exe")],env,900)
        marker=b"P1_3_STATE_MACHINE=PASS" if small else b"BOOT_CHECKPOINT_MODEL_PASS"
        cli.require(marker in raw, "model oracle missing")
        results[name]=raw.decode().splitlines()[-1]
    cli.require(bound==[cli.record(p) for p in paths], "inputs changed while testing")
    s.write(out/"result.json",dict(result="BOOT_CHECKPOINT_HOST_MODEL_PASS",variants=results,
        sources=bound,device_operations=0,firmware_built=False,measured_speedup=False,
        scope="Real Boot/BCB code, simulated Flash/EEPROM faults; not electrical power-loss or hardware acceptance"))
    print(json.dumps(results))


if __name__ == "__main__":
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode, "isolated explicit root required")
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("mode",choices=("prepare","test"));p.add_argument("--out",type=Path)
    a=p.parse_args();s=cli.Store(ROOT)
    if a.mode=="prepare":prepare(s)
    else:
        cli.require(a.out is not None,"explicit output required");test(s,a.out)
