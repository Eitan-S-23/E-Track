"""Source-bound App-only CRC candidate build from the retained erase baseline."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_install_cost as host

cli = host.cli
AREA = ROOT / '.cache/p34-crc-screen'
BASE = ROOT / '.cache/p34-erase'


def build(s):
    tests = s.read(AREA / 'host-001/result.json')
    cli.require(tests['result'] == 'CRC_HOST_SCREEN_PASS', 'CRC tests required')
    for item in tests['sources']:
        cli.require(cli.record(s.checked(item['path'])) == item, 'tested source changed')
    previous = s.read(BASE / 'build/result.json')
    artifacts = {Path(x['path']).suffix:x for x in previous['artifacts']}
    for item in previous['artifacts']:
        cli.require(cli.record(s.checked(item['path'])) == item, 'retained artifact changed')
    current = s.read(ROOT / '.cache/p34-batch-fix/assets/result.json')['target']
    cli.require(cli.record(current['path']) == current, 'current target changed')
    before, target = (Path(x['path']).read_bytes() for x in (artifacts['.bin'],current))
    cli.require(before[:0x400]+before[0x460:] == target[:0x400]+target[0x460:],
                'erase baseline is not current executable')
    fw, bld, logs = (s.checked(AREA/n) for n in ('f','b','build'))
    cli.require(not any(p.exists() for p in (fw,bld,logs)), 'preserve build attempt')
    manifest = s.read(BASE/'build/source.json')
    copies = []
    for item in manifest['files']:
        source = s.checked(item['path'])
        cli.require(cli.record(source) == item, 'original source changed')
        copies.append((source,s.checked(fw/source.relative_to(BASE/'f'))))
    overlay = s.checked(fw/'boot/src/boot_crc32.c')
    args = [str(x).replace(str(BASE),str(AREA)) for x in s.read(BASE/'build/configure.json')['command']]
    args = [x+' -DCONFIG_OTA_APP_CRC32_NIBBLE=1' if x.startswith('-DCMAKE_C_FLAGS:STRING=') else x for x in args]
    cli.require(sum('CONFIG_OTA_APP_CRC32_NIBBLE=1' in x for x in args)==1, 'missing CRC flag')
    s.checked(AREA/'install')
    env = host.environment(s,logs)
    for source,dest in copies:
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,dest)
    shutil.copyfile(ROOT/'boot/src/boot_crc32.c',overlay)
    s.write(logs/'source.json',dict(base=cli.record(BASE/'build/source.json'),
        overlay=['boot/src/boot_crc32.c'],files=[cli.record(p) for p in sorted(fw.rglob('*')) if p.is_file()]))
    host.command(s,logs,'configure',args,env,180)
    output = host.command(s,logs,'build',[args[0],'--build',bld,'--target','X_Track_App_GCC','--parallel','6'],env,900)
    def warnings(data):
        text=data.decode(errors='replace').replace(str(AREA),str(BASE)).replace(AREA.as_posix(),BASE.as_posix())
        return Counter(x.split('warning:',1)[1].strip() for x in text.splitlines() if 'warning:' in x)
    old, new = warnings((BASE/'build/build.log').read_bytes()),warnings(output)
    produced=[cli.record(s.checked(bld/'app-gcc'/('X-Track-App-GCC'+ext))) for ext in ('.bin','.elf','.map','.hex')]
    value=dict(result='CRC_APP_BUILT',warnings=sum(new.values()),new_warnings=dict(new-old),
        errors=output.count(b'error:'),boot_built=False,hardware=False,artifacts=produced,
        source=cli.record(logs/'source.json'),tests=cli.record(AREA/'host-001/result.json'),
        retained_executable_equivalent=True,retained_target=current,helper=cli.record(__file__))
    s.write(logs/'result.json',value)
    cli.require(not (new-old) and value['errors']==0,'new build diagnostics require review')
    print(json.dumps(value),flush=True)


if __name__ == '__main__':
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'explicit root and isolated Python required')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('launch','worker'))
    args=parser.parse_args()
    s=cli.Store(ROOT)
    owner=cli.load_module('crc_build_owner',ROOT/'.cache/p3-4-screening-20260922/supervisor.py')
    if args.mode=='launch':
        print(owner.owned.launch(s.checked(AREA/'runtime/build-001'),Path(__file__),['worker'],1500))
    else:
        cli.require(owner.owned.in_job(),'finite owned build required')
        build(s)
