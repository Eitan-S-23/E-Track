"""Two bounded UI-cadence cells with the existing APK and original collectors."""
import argparse
import os
from pathlib import Path
import sys
import types

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_ui_screen as screen
import p34_crc_measure as previous
import p34_radio_archive as archival

base,batch,cli=previous.base,previous.batch,previous.cli
AREA=screen.AREA
TRIALS=AREA/'trials'
TEST=ROOT/'tests/ota/test_p34_ui_trial.py'
HOST=AREA/'trial-tests-002'
base.history.ARCHIVES=dict(base.history.ARCHIVES, **{
    'USER/HAL/HAL_OTA_Package.cpp': ('.cache/p34-crc-screen/f/USER/HAL/HAL_OTA_Package.cpp',
        'c08e0f12b7ce2af62643c4f5008cc68fb49ff0cb48a3e36cec32e2998b05921a'),
    'USER/HAL/HAL_OTA_Package.h': ('.cache/p34-crc-screen/f/USER/HAL/HAL_OTA_Package.h',
        '3e6b0564ee03ed949f71468a9adb639c8a27e72050bd014815c44146f44f3a53')})


def archive_area(arm):
    return ROOT/'.cache/p34-ui-cadence' if arm=='bootstrap' else AREA


def assets(s,arm):
    cli.require(arm in ('bootstrap','measure'),'unlisted UI arm')
    value=s.read(AREA/'assets/result.json')
    cli.require(value['result']=='UI_ASSETS_VERIFIED' and value['hardware'] is False,'verified UI assets required')
    group=value['groups'][arm]
    for item in [*value['inputs'],group['receiver'],group['target'],group['package'],
                 *[x['package'] for x in group['negatives']]]:
        cli.require(cli.record(s.checked(item['path']))==item,'UI asset changed')
    version=30253 if arm=='bootstrap' else 30254
    cli.require(group['specification']['receiver']==version-1 and group['specification']['target_version']==version and
                all(group['decoded'][k] for k in ('passed','byte_identical','boot_ok','guards_ok','workspace_lifecycle_ok')),
                'wrong UI asset identity')
    cli.require(group['receiver_bindings']['whole_boot']==group['target_bindings']['whole_boot'],'Boot changed')
    return group


def predecessor(s,arm,group):
    order,root=(('measure','bootstrap'),previous.AREA/'trials') if arm=='bootstrap' else (('bootstrap','measure'),TRIALS)
    return batch.clone(batch.radio.confirmed_predecessor,ORDER=order,TRIALS=root)(s,arm,group)


class Ui(base.Crc):
    def __init__(self,s,arm):
        self.ui_arm=arm
        self.arm='batch';self.assets=assets(s,arm)
        self.proof,self.report=predecessor(s,arm,self.assets),batch.apk(s)
        path=Path(self.proof['plan']['profile']['path'])
        batch.radio.backend.Backend.__init__(self,s,path,s.read(path),cli.RECONNECT_GROUP)
        self.receiver_version,self.target_version=(30252,30253) if arm=='bootstrap' else (30253,30254)
        self.served_name=self.assets['specification']['served_name']

    def context(self,out):
        c=super().context(out)
        priors=[base.assets(self.store),previous.assets(self.store)]
        if self.ui_arm=='measure':
            priors.append(assets(self.store,'bootstrap'))
        c.n04_prior_assets+=priors;c.previous_assets=priors[-1]
        old=c.sources
        extra=[cli.record(p) for p in (Path(__file__),TEST,AREA/'assets/result.json',
            AREA/'build/result.json',archive_area(self.ui_arm)/('archive-'+self.ui_arm)/'result.json')]
        c.sources=lambda:sorted({x['path']:x for x in [*old(),*extra]}.values(),key=lambda x:x['path'])
        return c


def tests(s):
    value=s.read(HOST/'result.json')
    cli.require(value['result']=='PASS' and value['source']==cli.record(__file__) and
                value['test']==cli.record(TEST),'current UI trial tests required')
    return cli.record(HOST/'result.json')


def archive(s,owner,arm,worker):
    current=previous.OUT if arm=='bootstrap' else TRIALS/'bootstrap'
    prior=previous.PRIOR if arm=='bootstrap' else previous.OUT
    archival.proof(s,current);archival.proof(s,prior)
    out=archive_area(arm)/('archive-'+arm)
    checked=s.read(archival.AREA/'archive-tests/result.json')
    cli.require(checked['result']=='PASS' and checked['source']==cli.record(archival.__file__) and
                checked['test']==cli.record(archival.TEST),'archive guards changed')
    if worker:
        radio=types.SimpleNamespace(ORDER=(current.name,),TRIALS=current.parent,
            old=types.SimpleNamespace(TRIAL=prior),APK=batch.AREA/'apk-g1/apk.json',backend=archival.radio.backend)
        batch.clone(archival.worker,radio=radio)(s,current.name,out)
    else:
        cli.require(not out.exists(),'preserve archival operation')
        for name in ('intent.json','result.json','capture','usb','host','stop-intent.json','mkdir-intent.json','move-intent.json'):
            s.checked(out/name)
        s.write(out/'intent.json',dict(source=cli.record(__file__),tests=checked,no_ota=True,no_delete=True,
            protected=str(current),selected=str(prior)))
        print(owner.owned.launch(s.checked(AREA/'runtime'/('archive-'+arm)),Path(__file__),
                                 ['archive-worker','--arm',arm],600))


def archive_ready(s,arm):
    area=archive_area(arm)
    value=s.read(area/('archive-'+arm)/'result.json')
    cli.require(value['result']=='INACTIVE_CAPTURE_ARCHIVED_VERIFIED' and value['usb_closed'] and
                value['protected_snapshot_unchanged'] and value['configuration_unchanged'] and
                value['app_stopped'] and len(value['remaining'])==7,'archive unresolved')
    owner=s.read(area/'runtime'/('archive-'+arm)/'closed.json')
    cli.require(owner['worker_exit']==0 and not owner['forced_termination'],'archive owner unresolved')


def coordinate(s,api,c,owner,out,arm):
    result=dict(result='UI_TRIAL_INCOMPLETE');started=False
    try:
        observed=api.inspect(c,out/'prestart-phone')
        api.prepare(c,out,observed,tests(s))
        owner.owned.launch(out/'runtime/network',Path(__file__),['network','--arm',arm],cli.NETWORK_SUPERVISOR_SECONDS)
        started=True
        def ready():
            cli.require(not(out/'runtime/network/closed.json').exists(),'network closed before readiness')
            return(out/'live-network.json').exists()
        cli.wait_until(ready,seconds=cli.NETWORK_READY_WAIT_SECONDS)
        api.network_ready(c,out)
        owner.owned.launch(out/'runtime/s04',Path(__file__),['cell','--arm',arm],cli.CELL_SECONDS)
        s.write(out/'coordinator-ready.json',dict(time=cli.now(),cell='s04',arm=arm))
        cli.wait_until(lambda:(out/'runtime/s04/closed.json').exists(),seconds=cli.CELL_SECONDS+30)
        result.update(cell=s.read(out/'cells/s04/result.json'),owner=s.read(out/'runtime/s04/closed.json'))
        result['result']=result['cell']['result']
    except Exception as error:
        result.update(base.preserve_failure(s,out,error))
    finally:
        if started:
            try:
                s.write(out/'network-stop.json',dict(time=cli.now(),reason='coordinator-closure'))
                cli.wait_until(lambda:(out/'runtime/network/closed.json').exists(),seconds=600)
                result['network_owner']=s.read(out/'runtime/network/closed.json')
            except Exception as error:
                result['cleanup_error']=dict(error=type(error).__name__,detail=str(error))
        s.write(out/'coordinator-result.json',dict(result,time=cli.now()))
    cli.require('error' not in result and 'cleanup_error' not in result,'UI trial needs reconciliation')


def main():
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'explicit root and isolated Python required')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('archive','archive-worker','check','launch','coordinator','network','cell'))
    p.add_argument('--arm',choices=('bootstrap','measure'),default='bootstrap');a=p.parse_args()
    s=cli.Store(ROOT);out=TRIALS/a.arm
    owner=cli.load_module('ui_trial_owner',ROOT/'.cache/p3-4-screening-20260922/supervisor.py')
    if a.mode not in ('archive','check','launch'):
        cli.require(owner.owned.in_job(),'finite owner required')
    if a.mode.startswith('archive'):
        archive(s,owner,a.arm,a.mode=='archive-worker');return
    if a.mode=='launch':
        cli.require(not out.exists(),'UI cell already reserved');tests(s);archive_ready(s,a.arm)
    api=Ui(s,a.arm);c=api.context(out);api.preflight(c,out)
    if a.mode=='check':
        value=api.phone(c,'ui_check').config(c,'s04',921600,28,'https://offline.trycloudflare.com')
        batch.validate_config(value,api.assets)
        cli.require(api.installed_context(out).receiver_image_sha==api.assets['target']['sha256'],'wrong target context')
        print('UI_TRIAL_OFFLINE_VERIFIED',len(c.sources()));return
    if a.mode=='launch':
        s.write(out/'intent.json',dict(time=cli.now(),sources=c.sources(),tests=tests(s),arm=a.arm,
            scope='one legal FULL cell, same APK and Boot; retained target verified before subsequent cell',
            independent_acceptance=False))
        print(owner.owned.launch(out/'runtime/coordinator',Path(__file__),['coordinator','--arm',a.arm],6000));return
    cli.require(c.sources()==s.read(out/'intent.json')['sources'],'running sources changed')
    os.environ.update(c.environment())
    if a.mode=='coordinator':
        coordinate(s,api,c,owner,out,a.arm)
    else:
        api.validate(c,out)
        code=api.network_worker(c,out) if a.mode=='network' else api.cell_worker(c,out,'s04')
        cli.require(code==0,'UI trial worker failed')


if __name__=='__main__':
    main()
