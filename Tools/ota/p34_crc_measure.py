"""Measure the installed CRC App using a header-only successor, same APK and Boot."""
import argparse
import os
from pathlib import Path
import sys
import types

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_crc_trial as base
import p34_radio_archive as archival

cli,batch=base.cli,base.batch
AREA=base.build.AREA
PRIOR=base.TRIALS/'bootstrap'
OUT=AREA/'trials/measure'
ARCHIVE=AREA/'archive-measure'
TEST=ROOT/'tests/ota/test_p34_crc_measure.py'
HOST=AREA/'measure-tests-001'


def assets(s):
    value=s.read(AREA/'assets/result.json')
    cli.require(value['result']=='CRC_ASSETS_VERIFIED' and value['hardware'] is False,'verified assets required')
    group=value['groups']['measure']
    for item in [*value['inputs'],group['receiver'],group['target'],group['package'],
                 *[x['package'] for x in group['negatives']]]:
        cli.require(cli.record(s.checked(item['path']))==item,'measurement bytes changed')
    cli.require(group['specification']['receiver']==30251 and group['specification']['target_version']==30252 and
                all(group['decoded'][k] for k in ('passed','byte_identical','boot_ok','guards_ok','workspace_lifecycle_ok')),
                'wrong CRC measurement')
    before,after=(Path(group[k]['path']).read_bytes() for k in ('receiver','target'))
    cli.require(before[:0x400]+before[0x460:]==after[:0x400]+after[0x460:],'measurement alters executable')
    return group


def predecessor(s,group):
    return batch.clone(batch.radio.confirmed_predecessor,ORDER=('bootstrap','measure'),TRIALS=base.TRIALS)(s,'measure',group)


class Measure(base.Crc):
    def __init__(self,s,arm):
        cli.require(arm=='measure','only measurement cell admitted')
        self.arm='batch'; self.assets=assets(s)
        self.proof,self.report=predecessor(s,self.assets),batch.apk(s)
        path=Path(self.proof['plan']['profile']['path'])
        batch.radio.backend.Backend.__init__(self,s,path,s.read(path),cli.RECONNECT_GROUP)
        self.receiver_version,self.target_version=30251,30252
        self.served_name=self.assets['specification']['served_name']

    def context(self,out):
        c=super().context(out)
        prior=base.assets(self.store)
        c.n04_prior_assets.append(prior); c.previous_assets=prior
        old=c.sources
        extra=[cli.record(p) for p in (Path(__file__),TEST,ARCHIVE/'result.json')]
        c.sources=lambda: sorted({x['path']:x for x in [*old(),*extra]}.values(),key=lambda x:x['path'])
        return c


def archive_ready(s):
    value=s.read(ARCHIVE/'result.json')
    cli.require(value['result']=='INACTIVE_CAPTURE_ARCHIVED_VERIFIED' and value['usb_closed'] and
                value['protected_snapshot_unchanged'] and value['configuration_unchanged'] and
                value['app_stopped'] and len(value['remaining'])==7,'measurement archive unresolved')
    owner=s.read(AREA/'runtime/archive-measure/closed.json')
    cli.require(owner['worker_exit']==0 and not owner['forced_termination'],'archive owner unresolved')


def tests(s):
    value=s.read(HOST/'result.json')
    cli.require(value['result']=='PASS' and value['source']==cli.record(__file__) and
                value['test']==cli.record(TEST),'current measurement tests required')
    return cli.record(HOST/'result.json')


def archive(s,owner,worker):
    current=archival.proof(s,PRIOR)
    previous=archival.proof(s,batch.TRIALS/'batch')
    cli.require(current['summary']['input']['targetVersionCode']==30251 and
                previous['summary']['input']['targetVersionCode']==30250,'wrong archival lineage')
    checked=s.read(archival.AREA/'archive-tests/result.json')
    cli.require(checked['result']=='PASS' and checked['source']==cli.record(archival.__file__) and
                checked['test']==cli.record(archival.TEST),'archive guards changed')
    if worker:
        radio=types.SimpleNamespace(ORDER=('bootstrap',),TRIALS=base.TRIALS,
            old=types.SimpleNamespace(TRIAL=batch.TRIALS/'batch'),APK=batch.AREA/'apk-g1/apk.json',
            backend=archival.radio.backend)
        batch.clone(archival.worker,radio=radio)(s,'bootstrap',ARCHIVE)
    else:
        cli.require(not ARCHIVE.exists(),'preserve archive attempt')
        for name in ('intent.json','result.json','capture','usb','host','stop-intent.json','mkdir-intent.json','move-intent.json'):
            s.checked(ARCHIVE/name)
        s.write(ARCHIVE/'intent.json',dict(source=cli.record(__file__),tests=checked,
            protected_version=30251,selected_version=30250,no_delete=True,no_ota=True))
        print(owner.owned.launch(AREA/'runtime/archive-measure',Path(__file__),['archive-worker'],600))


def coordinate(s,api,c,owner):
    result=dict(result='CRC_MEASUREMENT_INCOMPLETE'); started=False
    try:
        observed=api.inspect(c,OUT/'prestart-phone')
        api.prepare(c,OUT,observed,tests(s))
        owner.owned.launch(OUT/'runtime/network',Path(__file__),['network'],cli.NETWORK_SUPERVISOR_SECONDS)
        started=True
        def ready():
            cli.require(not (OUT/'runtime/network/closed.json').exists(),'network closed before readiness')
            return (OUT/'live-network.json').exists()
        cli.wait_until(ready,seconds=cli.NETWORK_READY_WAIT_SECONDS)
        api.network_ready(c,OUT)
        owner.owned.launch(OUT/'runtime/s04',Path(__file__),['cell'],cli.CELL_SECONDS)
        s.write(OUT/'coordinator-ready.json',dict(time=cli.now(),cell='s04',arm='measure'))
        cli.wait_until(lambda:(OUT/'runtime/s04/closed.json').exists(),seconds=cli.CELL_SECONDS+30)
        result.update(cell=s.read(OUT/'cells/s04/result.json'),owner=s.read(OUT/'runtime/s04/closed.json'))
        result['result']=result['cell']['result']
    except Exception as error:
        result.update(base.preserve_failure(s,OUT,error))
    finally:
        if started:
            try:
                s.write(OUT/'network-stop.json',dict(time=cli.now(),reason='coordinator-closure'))
                cli.wait_until(lambda:(OUT/'runtime/network/closed.json').exists(),seconds=600)
                result['network_owner']=s.read(OUT/'runtime/network/closed.json')
            except Exception as error:
                result['cleanup_error']=dict(error=type(error).__name__,detail=str(error))
        s.write(OUT/'coordinator-result.json',dict(result,time=cli.now()))
    cli.require('error' not in result and 'cleanup_error' not in result,'measurement needs reconciliation')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('archive','archive-worker','check','launch','coordinator','network','cell'))
    mode=p.parse_args().mode
    s=cli.Store(ROOT)
    owner=cli.load_module('crc_measure_owner',ROOT/'.cache/p3-4-screening-20260922/supervisor.py')
    if mode not in ('archive','check','launch'):
        cli.require(owner.owned.in_job(),'finite owner required')
    if mode.startswith('archive'):
        archive(s,owner,mode=='archive-worker'); return
    if mode=='launch':
        cli.require(not OUT.exists(),'measurement already reserved')
        tests(s); archive_ready(s)
    api=Measure(s,'measure'); c=api.context(OUT); api.preflight(c,OUT)
    if mode=='check':
        value=api.phone(c,'crc_measure_check').config(c,'s04',921600,28,'https://offline.trycloudflare.com')
        batch.validate_config(value,api.assets)
        cli.require(api.installed_context(OUT).receiver_image_sha==api.assets['target']['sha256'],'wrong target context')
        print('CRC_MEASURE_OFFLINE_VERIFIED',len(c.sources())); return
    if mode=='launch':
        s.write(OUT/'intent.json',dict(time=cli.now(),sources=c.sources(),tests=tests(s),arm='measure',
            scope='one legal FULL30251-to30252 CRC measurement, same batch APK, no Boot replacement',independent_acceptance=False))
        print(owner.owned.launch(OUT/'runtime/coordinator',Path(__file__),['coordinator'],6000)); return
    cli.require(c.sources()==s.read(OUT/'intent.json')['sources'],'running sources changed')
    os.environ.update(c.environment())
    if mode=='coordinator':
        coordinate(s,api,c,owner)
    else:
        api.validate(c,OUT)
        code=api.network_worker(c,OUT) if mode=='network' else api.cell_worker(c,OUT,'s04')
        cli.require(code==0,'measurement worker failed')


if __name__=='__main__':
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'explicit root and isolated Python required')
    main()
