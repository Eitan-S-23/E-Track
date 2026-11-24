"""Offline R2-A to R2-B FULL package; no device, server, publication or release."""
import argparse
import json
import lzma
import os
from pathlib import Path
import runpy
import secrets
import struct
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_session as cli
import p34_install_cost as host
import p34_finalized_vtor as vtor
import prepare_baud_assets as full

SELF=Path(__file__).resolve()
IMAGES=ROOT/'.cache/p34-recovery-sources1'
DECODER=ROOT/'.cache/p34q/irq/assets/bin/full_image_host.exe'
DECODER_SHA='82c5e6d24bbe3b2fa0bf8d98e129cf481f32fa397771bcaec12409f483b998f8'
LABELS=('positive','payload-crc','truncated','same-version','wrong-flags')


def prepare(store,out):
    cli.require(not out.exists() and not os.environ.get('OTA_AES_KEY'),'preserve package; no external key override')
    files=['full.etu','result.json',*(name+'.etu' for name in LABELS[1:]),
           *(name+suffix for name in LABELS for suffix in ('.log','.json'))]
    for name in files:store.checked(out/name)
    for key in ('HOME','USERPROFILE','APPDATA','LOCALAPPDATA','TEMP','TMP','TMPDIR','XDG_CACHE_HOME',
                'XDG_CONFIG_HOME','XDG_DATA_HOME','PYTHONUSERBASE','PYTHONPYCACHEPREFIX','CCACHE_DIR','SCCACHE_DIR'):
        store.checked(out/'host'/key.lower())
    source=store.read(IMAGES/'result.json')
    for item in source['inputs']+source['outputs']:
        cli.require(cli.record(store.checked(item['path']))==item,'finalized source provenance drift')
    cli.require(cli.record(DECODER)['sha256']==DECODER_SHA,'known native decoder drift')
    paths=[SELF,ROOT/'Tools/etu_pack.py',Path(cli.__file__),Path(host.__file__),Path(vtor.__file__),
           Path(vtor.sources.__file__),Path(full.__file__),full.HARNESS,DECODER,
           IMAGES/'result.json',IMAGES/'r2-a.bin',IMAGES/'r2-b.bin',
           ROOT/'.cache/p34-next/n03/assets/result.json']
    inputs=[cli.record(p) for p in paths]
    images={name:(IMAGES/name).read_bytes() for name in vtor.IDENTITIES}
    for name,image in images.items():
        cli.require(cli.record(IMAGES/name)['sha256']==vtor.IDENTITIES[name],'exact R2 identity required')
        vtor.sources.verify(image)
        vtor.classify(image,before=vtor.RUNTIME,after=vtor.RUNTIME,table=image[0x800:0x800+524],dhcsr=0,halted=False)
    a,b=images['r2-a.bin'],images['r2-b.bin']
    cli.require(len(a)==len(b) and a[:0x400]==b[:0x400] and a[0x460:]==b[0x460:],
                'this transition must be header-only, not a changed-executable speed claim')
    env=host.environment(store,out)
    os.environ.update(env)
    sys.path.insert(0,str(Path(sys.base_prefix)/'Lib/site-packages'))
    pack=runpy.run_path(str(ROOT/'Tools/etu_pack.py'))
    compressed=pack['lzma_alone_encode'](b)
    cli.require(len(compressed)>13 and struct.unpack('<Q',compressed[5:13])[0]==len(b),'finite LZMA length differs')
    # The project keeps the encoder EOS but replaces its unknown-size header.
    # Restore only that field for liblzma; native tests consume the actual bytes.
    standard_alone=compressed[:5]+b'\xff'*8+compressed[13:]
    cli.require(lzma.decompress(standard_alone,format=lzma.FORMAT_ALONE)==b,'independent LZMA roundtrip failed')
    nonce=secrets.token_bytes(16)
    encrypted=pack['aes_ctr_xcrypt'](bytes.fromhex(pack['DEFAULT_KEY_HEX']),nonce,compressed,True)
    cli.require(pack['aes_ctr_xcrypt'](bytes.fromhex(pack['DEFAULT_KEY_HEX']),nonce,encrypted,False)==compressed,
                'AES roundtrip failed')
    blob=pack['build_etu_header'](11,nonce,encrypted,30277,0,bytes(8))+encrypted
    header=full.package_info(blob,30276,30277)
    outputs=[store.raw(out/'full.etu',blob)]
    outcomes={}
    for label,data,expected in [('positive',blob,'ok'),*full.negatives(blob,30276)]:
        name='full.etu' if label=='positive' else label+'.etu'
        if label!='positive':outputs.append(store.raw(out/name,data))
        log=host.command(store,out,label,[DECODER,out/name,IMAGES/'r2-a.bin',IMAGES/'r2-b.bin',expected],env,180)
        value=json.loads(log)
        cli.require(value['passed'] and value['guards_ok'] and value['workspace_lifecycle_ok'],'native validation failed')
        if label=='positive':
            cli.require(value['byte_identical'] and value['boot_ok'] and value['programmed_bytes']==len(b),
                        'full native decoded image differs')
        else:cli.require(value['prepares']==0,'invalid package reached candidate preparation')
        outcomes[label]=value
        outputs += [cli.record(out/(label+suffix)) for suffix in ('.log','.json')]
    cli.require(inputs==[cli.record(p) for p in paths],'package inputs changed')
    store.write(out/'result.json',dict(result='R2_TRANSITION_PACKAGE_HOST_VERIFIED',inputs=inputs,outputs=outputs,
        package=cli.record(out/'full.etu'),header=header,checks=outcomes,current=cli.record(IMAGES/'r2-a.bin'),
        target=cli.record(IMAGES/'r2-b.bin'),header_only=True,hardware=False,production_release=False,
        physical_receiver_verified=False,ota_sender_and_collectors_ready=False,
        purpose='normal original-Boot transition after verified R2-A recovery; not group16 or general-update timing'))
    print('R2_TRANSITION_PACKAGE_HOST_VERIFIED',len(blob),header['full_sha256'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'isolated root required')
    store=cli.Store(ROOT);prepare(store,store.checked(args.output_dir))


if __name__=='__main__':main()
