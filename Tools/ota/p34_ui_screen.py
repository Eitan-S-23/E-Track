"""Host checks and isolated App-only UI-cadence candidate; no device operations."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_install_cost as host
import p34_crc_review as review

cli=host.cli
BASE=ROOT/'.cache/p34-crc-screen'
AREA=ROOT/'.cache/p34-ui-cadence-r2'
HEADER=ROOT/'USER/HAL/ota_ui_cadence.h'
TEST=ROOT/'tests/ota/test_ota_ui_cadence.cpp'


def gated(text):
    before='#include "lv_port/lv_port.h"'
    after=before+'\n#include "HAL/ota_ui_cadence.h"\n\n#if defined(OTA_TARGET_APP) && CONFIG_OTA_UI_CADENCE\n#include "HAL/HAL_OTA_Package.h"\n#endif'
    loop='    HAL::HAL_Update();\n    lv_task_handler();'
    replacement='''    HAL::HAL_Update();
#if defined(OTA_TARGET_APP) && CONFIG_OTA_UI_CADENCE
    // Keep RX/health/watchdog service running between expensive UI refreshes.
    static OtaUiCadence uiCadence;
    if (uiCadence.due(millis(), HAL::OTA_OverlayIsBleOwned()))
    {
        lv_task_handler();
    }
#else
    lv_task_handler();
#endif'''
    cli.require(text.count(before)==1 and text.count(loop)==1,'main integration input changed')
    return text.replace(before,after).replace(loop,replacement)


def ble_query(text,header=False):
    old='bool OTA_OverlayIsOtaOwned();' if header else '''bool HAL::OTA_OverlayIsOtaOwned()
{
    return g_ota_overlay_owner == OTA_OVERLAY_PACKAGE;
}'''
    extra='\nbool OTA_OverlayIsBleOwned();' if header else '''

bool HAL::OTA_OverlayIsBleOwned()
{
    return g_ota_overlay_owner == OTA_OVERLAY_BLE;
}'''
    cli.require(text.count(old)==1,'overlay query input changed')
    return text.replace(old,old+extra)


def tests(s):
    out=s.checked(AREA/'tests')
    cli.require(not out.exists(),'preserve tests')
    env=host.environment(s,out)
    for enabled in (0,1):
        exe=s.checked(out/('cadence-%d.exe'%enabled))
        args=['D:/install/mingw64/bin/g++.exe','-std=c++11','-O2','-Wall','-Wextra','-Werror',
              '-DCONFIG_OTA_UI_CADENCE=%d'%enabled,'-I'+str(ROOT/'USER'),TEST,'-o',exe]
        host.command(s,out,'compile-%d'%enabled,args,env,60)
        result=host.command(s,out,'run-%d'%enabled,[exe],env,30)
        cli.require(b'OTA_UI_CADENCE_PASS checks=17' in result,'cadence tests missing')
    original=(BASE/'f/USER/main.cpp').read_text(encoding='utf-8')
    candidate=gated(original)
    cli.require(candidate.endswith(original[original.index('    OTA_ConfirmUpdate();'):]),
                'health/watchdog/main suffix changed')
    cli.require('#define CONFIG_OTA_UI_CADENCE 0' in HEADER.read_text(),'must default off')
    for suffix in ('cpp','h'):
        path='USER/HAL/HAL_OTA_Package.'+suffix
        expected=ble_query((BASE/'f'/path).read_text(encoding='utf-8'),suffix=='h')
        query='bool HAL::OTA_OverlayIsBleOwned()\n{\n    return g_ota_overlay_owner == OTA_OVERLAY_BLE;\n}'
        cli.require(('bool OTA_OverlayIsBleOwned();' if suffix=='h' else query) in expected and
                    ('bool OTA_OverlayIsBleOwned();' if suffix=='h' else query) in (ROOT/path).read_text(encoding='utf-8'),
                    'BLE query must not use the distinct PACKAGE owner')
    cli.require('HAL::OTA_OverlayIsBleOwned()' in candidate and
                'uiCadence.due(millis(), HAL::OTA_OverlayIsOtaOwned())' not in candidate,
                'main gate uses wrong overlay owner')
    s.write(out/'result.json',dict(result='UI_CADENCE_HOST_PASS',native_checks=34,
        integration_checks=5,hardware=False,sources=[cli.record(p) for p in (Path(__file__),HEADER,TEST,ROOT/'USER/main.cpp',
            ROOT/'USER/HAL/HAL_OTA_Package.cpp',ROOT/'USER/HAL/HAL_OTA_Package.h')]))
    print('UI_CADENCE_HOST_PASS native34 integration5')


def prepare(s):
    proof=s.read(AREA/'tests/result.json')
    cli.require(proof['result']=='UI_CADENCE_HOST_PASS','host tests required')
    for item in proof['sources']:
        cli.require(cli.record(item['path'])==item,'tested input changed')
    fw=s.checked(AREA/'f')
    cli.require(not fw.exists(),'preserve source tree')
    manifest=s.read(BASE/'build/source.json')
    copies=[]
    for item in manifest['files']:
        source=s.checked(item['path'])
        cli.require(cli.record(source)==item,'CRC source changed')
        copies.append((source,s.checked(fw/source.relative_to(BASE/'f'))))
    header=s.checked(fw/'USER/HAL/ota_ui_cadence.h')
    for source,target in copies:
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
    shutil.copyfile(HEADER,header)
    s.write(AREA/'prepared.json',dict(base=cli.record(BASE/'build/source.json'),
        tests=cli.record(AREA/'tests/result.json'),header=cli.record(header),
        next='Apply the reviewed main.cpp cadence patch, then launch the App-only build'))
    print('UI_CADENCE_SOURCE_PREPARED')


def build(s):
    prepared=s.read(AREA/'prepared.json')
    cli.require(prepared['tests']==cli.record(AREA/'tests/result.json'),'tests changed')
    fw,bld,out=(s.checked(AREA/n) for n in ('f','b','build'))
    cli.require(not bld.exists() and not out.exists(),'preserve build')
    expected=gated((BASE/'f/USER/main.cpp').read_text(encoding='utf-8'))
    cli.require((fw/'USER/main.cpp').read_text(encoding='utf-8')==expected,'unexpected main overlay')
    overlays=['USER/main.cpp','USER/HAL/ota_ui_cadence.h','USER/HAL/HAL_OTA_Package.cpp','USER/HAL/HAL_OTA_Package.h']
    for suffix in ('cpp','h'):
        path='USER/HAL/HAL_OTA_Package.'+suffix
        cli.require((fw/path).read_text(encoding='utf-8')==ble_query((BASE/'f'/path).read_text(encoding='utf-8'),suffix=='h'),
                    'unexpected overlay query changes')
    for item in s.read(BASE/'build/source.json')['files']:
        original=Path(item['path']); target=s.checked(fw/original.relative_to(BASE/'f'))
        if target.relative_to(fw).as_posix() not in overlays:
            cli.require(target.read_bytes()==original.read_bytes(),'unrelated firmware source changed')
    cli.require((fw/'USER/HAL/ota_ui_cadence.h').read_bytes()==HEADER.read_bytes(),'header differs')
    s.write(out/'source.json',dict(base=prepared['base'],overlays=overlays,
        files=[cli.record(p) for p in sorted(fw.rglob('*')) if p.is_file()]))
    args=[str(x).replace(str(BASE),str(AREA)) for x in s.read(BASE/'build/configure.json')['command']]
    args=[x+' -DCONFIG_OTA_UI_CADENCE=1' if x.startswith('-DCMAKE_CXX_FLAGS:STRING=') else x for x in args]
    cli.require(sum('CONFIG_OTA_UI_CADENCE=1' in x for x in args)==1,'App flag missing')
    s.checked(AREA/'install')
    env=host.environment(s,out)
    host.command(s,out,'configure',args,env,180)
    output=host.command(s,out,'build',[args[0],'--build',bld,'--target','X_Track_App_GCC','--parallel','6'],env,900)
    def normalized(raw):
        return review.warnings(raw.replace(b'p34-ui-cadence-r2',b'p34-crc-screen'))
    old,new=normalized((BASE/'build/build.log').read_bytes()),normalized(output)
    artifacts=[cli.record(s.checked(bld/'app-gcc'/('X-Track-App-GCC'+ext))) for ext in ('.bin','.elf','.map','.hex')]
    result=dict(result='UI_CADENCE_APP_BUILT',warnings=sum(new.values()),new_warnings=dict(new-old),
        errors=output.count(b'error:'),artifacts=artifacts,boot_built=False,hardware=False,
        source=cli.record(out/'source.json'),tests=prepared['tests'])
    s.write(out/'result.json',result)
    cli.require(not(new-old) and not result['errors'],'new diagnostics require review')
    print(json.dumps(result),flush=True)


def main():
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'explicit root and isolated Python required')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('test','prepare','launch','worker'))
    mode=parser.parse_args().mode;s=cli.Store(ROOT)
    if mode in ('test','prepare'):
        (tests if mode=='test' else prepare)(s);return
    owner=cli.load_module('ui_screen_owner',ROOT/'.cache/p3-4-screening-20260922/supervisor.py')
    if mode=='launch':
        print(owner.owned.launch(s.checked(AREA/'runtime/build-001'),Path(__file__),['worker'],1500))
    else:
        cli.require(owner.owned.in_job(),'finite owned build required');build(s)


if __name__=='__main__':
    main()
