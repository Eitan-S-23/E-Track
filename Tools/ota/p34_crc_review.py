"""Review existing CRC artifacts without repeating the successful compiler run."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_crc_build as build
import p34_erase_candidate as prior


def warnings(data):
    for separator in (b'/', b'\\'):
        data=data.replace(b'.cache'+separator+b'p34-crc-screen'+separator,
                          b'.cache'+separator+b'p34-erase'+separator)
    return prior.warning_counts(data)


def main():
    cli,host=build.cli,build.host
    s=cli.Store(ROOT)
    out=s.checked(build.AREA/'build-review-001')
    cli.require(not out.exists(),'preserve review')
    count=prior.warning_checks()
    original=b'warning: CMakeFiles/D_/repo/.cache/p34-erase/f/a.o uses 2-byte wchar_t'
    candidate=original.replace(b'p34-erase',b'p34-crc-screen')
    for separator in (b'/',b'\\'):
        a,b=(x.replace(b'/',separator) for x in (original,candidate))
        cli.require(warnings(a)==warnings(b),'CMake embedded path differs')
        cli.require(warnings(a)!=warnings(b.replace(b'a.o',b'b.o')),'object name lost')
        cli.require(warnings(a)!=warnings(b.replace(b'2-byte',b'4-byte')),'warning meaning lost')
        cli.require(sum((warnings(b+b'\n'+b)-warnings(a)).values())==1,'multiplicity lost')
        count+=4
    report=s.read(build.AREA/'build/result.json')
    cli.require(report['result']=='CRC_APP_BUILT' and report['errors']==0 and not report['boot_built'],
                'compiler did not complete')
    owner=s.read(build.AREA/'runtime/build-001/closed.json')
    cli.require(owner['worker_exit']==1 and not owner['forced_termination'],'build outcome not reconciled')
    log=(build.AREA/'runtime/build-001/worker.log').read_text()
    cli.require(log.rstrip().endswith('RuntimeError: new build diagnostics require review'),
                'different worker failure')
    for item in [*report['artifacts'],report['source'],report['tests']]:
        cli.require(cli.record(s.checked(item['path']))==item,'artifact changed')
    for item in s.read(report['source']['path'])['files']:
        cli.require(cli.record(s.checked(item['path']))==item,'built source changed')
    old=(build.BASE/'build/build.log').read_bytes()
    new=(build.AREA/'build/build.log').read_bytes()
    cli.require(warnings(old)==warnings(new) and sum(warnings(new).values())==report['warnings'],
                'real new diagnostics require repair')
    commands=s.read(build.AREA/'b/compile_commands.json')
    selected=[x for x in commands if x['file'].replace('\\','/').endswith('/boot/src/boot_crc32.c')
              and 'X_Track_App_GCC.dir' in x['command']]
    cli.require(len(selected)==1 and '-DCONFIG_OTA_APP_CRC32_NIBBLE=1' in selected[0]['command'],
                'App CRC flag missing')
    env=host.environment(s,out)
    elf=next(x for x in report['artifacts'] if x['path'].endswith('.elf'))
    tool=Path('D:/singlechip/gcc+gdb+openocd/tools/arm-gnu-toolchain-13.3.rel1-ming/bin/arm-none-eabi-objdump.exe')
    host.command(s,out,'crc-disassembly',[tool,'-d','--disassemble=boot_crc32_update',elf['path']],env,30)
    s.write(out/'result.json',dict(result='CRC_BUILD_REVIEW_PASS',build=cli.record(build.AREA/'build/result.json'),
        source=cli.record(__file__),warning_normalizer_tests=count,warnings=report['warnings'],new_warnings=0,
        errors=0,firmware_rebuilt=False,boot_built=False,hardware=False,
        reason='Preserve failed comparison; reuse tested warning normalizer for the new CMake embedded source path.'))
    print('CRC_BUILD_REVIEW_PASS',report['warnings'],'warnings; new0 errors0; no rebuild')


if __name__=='__main__':
    build.cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                      'explicit root and isolated Python required')
    main()
