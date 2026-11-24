"""Prepare UI-cadence bootstrap30253 and header-only measurement30254."""
import argparse
import copy
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_ui_screen as screen
import p34_batch_review as review
import p34_crc_measure as prior
import p34_patch_assets as shared

cli,host=screen.cli,screen.host
OUT=screen.AREA/'assets'


def prepare(s):
    cli.require(not OUT.exists() and not os.environ.get('OTA_AES_KEY'),'preserve assets/no key override')
    anchor,report=review.load_report(s,prior.OUT)
    current=prior.assets(s)
    cli.require(report['summary']['input']['targetVersionCode']==30252 and
                report['summary']['input']['targetImageSha256']==current['target']['sha256'],'wrong predecessor')
    built=s.read(screen.AREA/'build/result.json')
    cli.require(built['result']=='UI_CADENCE_APP_BUILT' and not built['new_warnings'] and
                built['errors']==0 and not built['boot_built'],'reviewed App-only build required')
    owner=s.read(screen.AREA/'runtime/build-001/closed.json')
    cli.require(owner['worker_exit']==0 and not owner['forced_termination'],'build owner unresolved')
    artifacts={Path(x['path']).suffix:x for x in built['artifacts']}
    inputs=[anchor,cli.record(screen.AREA/'build/result.json'),built['source'],built['tests'],
            *built['artifacts'],cli.record(__file__),cli.record(prior.AREA/'assets/result.json')]
    for item in inputs:
        cli.require(cli.record(s.checked(item['path']))==item,'input changed')
    env=host.environment(s,OUT);os.environ.update(env)
    sys.path.insert(0,str(Path(sys.base_prefix)/'Lib/site-packages'))
    pack=cli.load_module('ui_pack',screen.AREA/'f/Tools/etu_pack.py')
    unpack=cli.load_module('ui_unpack',screen.AREA/'f/Tools/etu_unpack.py')
    tools=cli.load_module('ui_package_tools',ROOT/'Tools/ota/prepare_baud_assets.py')
    decoder=s.read(ROOT/'.cache/p34-next/n03/assets/result.json')['decoder']
    cli.require(cli.record(s.checked(decoder['path']))==decoder,'decoder changed')
    constants=s.read(ROOT/'.cache/p34ab/assets/session-assets.json')['constants']
    receiver,bindings=current['target'],current['target_bindings'];groups={}
    for name,version in (('bootstrap',30253),('measure',30254)):
        raw=bytearray(Path(artifacts['.bin']['path']).read_bytes())
        raw[0x400:0x460]=pack.build_fw_header(bytes(raw),f'3.2.{version-30200}-p34u',1786320000)
        target=s.raw(OUT/(name+'.bin'),bytes(raw));identity=shared.identity(bytes(raw),unpack)
        cli.require(identity['version_code']==version,'target version mismatch')
        before=Path(receiver['path']).read_bytes()
        blob=shared.wrap_payload(pack,pack.lzma_alone_encode(bytes(raw)),before,bytes(raw),kind='full')
        package=s.raw(OUT/('p34-ui-'+name+'-full.etu'),blob)
        def native(label,item,expected):
            return json.loads(host.command(s,OUT,name+'-'+label,
                [decoder['path'],item['path'],receiver['path'],target['path'],expected],env,180))
        decoded=native('positive',package,'ok')
        cli.require(all(decoded[k] for k in ('passed','byte_identical','boot_ok','guards_ok','workspace_lifecycle_ok')),
                    'positive decoder check failed')
        negatives=[]
        for label,broken,expected in tools.negatives(blob,version-1):
            item=s.raw(OUT/(name+'-'+label+'.etu'),broken);result=native(label,item,expected)
            cli.require(result['passed'] and result['prepares']==0,'negative reached preparation')
            negatives.append(dict(name=label,package=item,native=result))
        target_bindings=shared.bindings(dict(target_bindings=bindings),target,identity,artifacts,constants)
        cli.require(target_bindings['whole_boot']==current['target_bindings']['whole_boot'],'Boot changed')
        groups[name]=dict(result='UI_ASSETS_VERIFIED',specification=dict(receiver=version-1,target_version=version,
            version_name=f'3.2.{version-30200}-p34u',served_name='p34-ui-'+name+'-full.etu',
            release_key='p34-ui-'+name,kind='full',pauseScanDuringOta=True,androidHighPriority=True,dataBatchFrames=3),
            receiver=receiver,receiver_bindings=bindings,target=target,target_identity=identity,
            target_bindings=target_bindings,package=package,package_kind='full',decoded=decoded,negatives=negatives)
        receiver,bindings=target,copy.deepcopy(target_bindings)
    a,b=(Path(groups[k]['target']['path']).read_bytes() for k in ('bootstrap','measure'))
    cli.require(a[:0x400]+a[0x460:]==b[:0x400]+b[0x460:],'measurement changes executable')
    s.write(OUT/'result.json',dict(result='UI_ASSETS_VERIFIED',hardware=False,groups=groups,inputs=inputs+[decoder],
        scope='bootstrap installs receiver cadence; header-only successor measures that receiver'))
    print('UI_ASSETS_VERIFIED', {k:v['package']['bytes'] for k,v in groups.items()},flush=True)


if __name__=='__main__':
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'explicit root and isolated Python required')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('launch','worker'));a=p.parse_args()
    s=cli.Store(ROOT);s.checked(Path(__file__));s.checked(OUT)
    owner=cli.load_module('ui_assets_owner',ROOT/'.cache/p3-4-screening-20260922/supervisor.py')
    if a.mode=='launch':
        print(owner.owned.launch(s.checked(screen.AREA/'runtime/assets-001'),Path(__file__),['worker'],900))
    else:
        cli.require(owner.owned.in_job(),'finite asset worker required');prepare(s)
