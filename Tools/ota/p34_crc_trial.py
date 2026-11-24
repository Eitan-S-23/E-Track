"""One CRC bootstrap with existing batch APK; never claim new-code install timing."""
from pathlib import Path
import hashlib
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_batch_trial as batch
import p34_crc_build as build
import p34_crc_archive as archive
import p34_historical_inputs as history

cli=batch.cli
TRIALS=build.AREA/'trials-v3'
TEST=ROOT/'tests/ota/test_p34_crc_trial.py'
HOST=build.AREA/'trial-tests-005'
OLD_CRC=ROOT/'.cache/p34-erase/f/boot/src/boot_crc32.c'
history.ARCHIVES=dict(history.ARCHIVES, **{'boot/src/boot_crc32.c':
    (OLD_CRC.relative_to(ROOT).as_posix(),'b7f5c763006fa3bc4b60a861fb82c2a1311373846aca6deb70cc09277287d0c4')})


def assets(s):
    value=s.read(build.AREA/'assets/result.json')
    cli.require(value['result']=='CRC_ASSETS_VERIFIED' and value['hardware'] is False,'verified CRC assets required')
    for item in value['inputs']:
        cli.require(cli.record(s.checked(item['path']))==item,'CRC input changed')
    group=value['groups']['bootstrap']
    for item in [group['receiver'],group['target'],group['package'],*[x['package'] for x in group['negatives']]]:
        cli.require(cli.record(s.checked(item['path']))==item,'CRC asset changed')
    cli.require(group['specification']['receiver']==30250 and group['specification']['target_version']==30251 and
                all(group['decoded'][k] for k in ('passed','byte_identical','boot_ok','guards_ok','workspace_lifecycle_ok')),
                'wrong CRC bootstrap')
    cli.require(group['receiver_bindings']['whole_boot']==group['target_bindings']['whole_boot'], 'Boot changed')
    return group


def predecessor(s,group):
    return batch.clone(batch.radio.confirmed_predecessor,ORDER=('batch','bootstrap'),TRIALS=batch.TRIALS)(s,'bootstrap',group)


def archive_ready(s):
    value=s.read(archive.OUT/'result.json')
    cli.require(value['result']=='INACTIVE_CAPTURE_ARCHIVED_VERIFIED' and value['usb_closed'] and
                value['protected_snapshot_unchanged'] and value['configuration_unchanged'] and
                value['app_stopped'] and len(value['remaining'])==7,'CRC archive unresolved')
    owner=s.read(build.AREA/'runtime/archive-bootstrap/closed.json')
    cli.require(owner['worker_exit']==0 and not owner['forced_termination'],'archive owner unresolved')
    return value


def prepare_capacity(s,p,out,c,known):
    names=p.command(['exec-out','run-as',c.PKG,'ls','-1','files/p34-observations']).splitlines()
    cli.require(len(names)==len(set(names)) and len(names)<=8 and
                all(batch.capacity.CAPTURE.fullmatch(n) for n in names),'unexpected capture inventory')
    if len(names)<8:
        return
    capture=sorted(names)[-1]; remote='files/p34-observations/'+capture
    events=p.file_bytes(c.PKG,remote+'/events.jsonl',16*1024*1024)
    health=p.file_bytes(c.PKG,remote+'/health.json',8192)
    proof=batch.capacity.validate_query(events,health,capture,known,
        c.apk['metadata']['device_observation']['sentinel'],c.TARGET)
    pid=p.command(['shell','pidof',c.PKG],check=False).strip()
    cli.require(pid in ('',str(proof['pid'])),'different App invocation')
    config=p.file_bytes(c.PKG,'files/p34-experiment.json',8192)
    cli.require(hashlib.sha256(config).hexdigest() in known,'unknown current config')
    s.raw(out/'events-before.jsonl',events); s.raw(out/'health-before.json',health)
    s.raw(out/'runtime-config.json',config)
    batch.capacity.validate_query(p.file_bytes(c.PKG,remote+'/events.jsonl',16*1024*1024),
        p.file_bytes(c.PKG,remote+'/health.json',8192),capture,known,
        c.apk['metadata']['device_observation']['sentinel'],c.TARGET)
    cli.require(p.command(['shell','pidof',c.PKG],check=False).strip()==pid,'process changed before stop')
    s.write(out/'stop-intent.json',dict(pid=pid,proof=proof,reason='owned unused capture fills prestart store'))
    p.command(['shell','am','force-stop',c.PKG])
    batch.capacity.ensure_capacity(s,p,out/'capacity',package=c.PKG,
        sentinel=c.apk['metadata']['device_observation']['sentinel'],target=c.TARGET,known_configs=known)
    cli.require(p.file_bytes(c.PKG,'files/p34-experiment.json',8192)==config,'configuration changed')


class Crc(batch.Batch):
    def __init__(self,s,arm):
        cli.require(arm=='bootstrap','only unspent CRC bootstrap admitted')
        # The inherited context enumerates the closed radio lineage under batch.
        self.arm='batch'
        self.assets=assets(s)
        self.proof,self.report=predecessor(s,self.assets),batch.apk(s)
        path=Path(self.proof['plan']['profile']['path'])
        batch.radio.backend.Backend.__init__(self,s,path,s.read(path),cli.RECONNECT_GROUP)
        self.receiver_version,self.target_version=30250,30251
        self.served_name=self.assets['specification']['served_name']

    def context(self,out):
        c=super().context(out)
        prior=batch.assets(self.store)
        c.n04_prior_assets.append(prior)
        c.previous_assets=prior
        original=c.sources
        extra=[cli.record(p) for p in (Path(__file__),TEST,build.AREA/'assets/result.json',
            build.AREA/'build/result.json',build.AREA/'build-review-001/result.json',
            archive.OUT/'result.json',Path(archive.__file__),OLD_CRC)]
        c.sources=lambda: sorted({x['path']:x for x in [*original(),*extra]}.values(),key=lambda x:x['path'])
        return c

    def inspect(self,c,out):
        phone=self.phone(c,'crc_prestart_capacity')
        lock=c.load('crc_prestart_capacity_lock',ROOT/'Tools/ota/repeat_cycle.py')
        with lock.device_lock(),phone.usb(c,out.parent/'capacity-preflight') as p:
            prepare_capacity(self.store,p,out.parent/'capacity-preflight',c,self.known_configs(c))
        return super().inspect(c,out)


def tests(s):
    path=HOST/'result.json'; value=s.read(path)
    cli.require(value['result']=='PASS' and value['source']==cli.record(__file__) and
                value['test']==cli.record(TEST),'current CRC trial tests required')
    return cli.record(path)


def reconciled_preflight(s):
    archive_ready(s)
    failed=build.AREA/'trials/bootstrap'
    cli.require(not (failed/'cells').exists() and not (failed/'runtime/s04').exists(),
                'original cell may have started')
    for name,code in (('coordinator',1),('network',0)):
        owner=s.read(failed/'runtime'/name/'closed.json')
        cli.require(owner['worker_exit']==code and not owner['forced_termination'],'old owner unresolved')
    network=s.read(failed/'network-owner/network/closed.json')
    cli.require(network['listener_closed'] and network['worker_stopped'],'old listener unresolved')
    result=s.read(failed/'network-result.json')
    cli.require(result['result']=='NETWORK_CLOSED' and result['device_operations']==0,'old network uncertain')
    phone=s.read(failed/'prestart-phone/result.json')
    cli.require(phone['stable_completed'] and phone['pid'] is None and phone['usb_closed'],'old inspection uncertain')
    second=build.AREA/'trials-v2/bootstrap'
    cli.require(not (second/'cells').exists() and not (second/'runtime/network').exists(),'second window may have acted')
    owner=s.read(second/'runtime/coordinator/closed.json')
    result=s.read(second/'coordinator-result.json')
    cli.require(owner['worker_exit']==1 and not owner['forced_termination'] and
                result['detail']=='App observation store has no verified free slot; review preserved captures before cleanup',
                'different second-window failure')


def preserve_failure(s,out,error):
    value=dict(time=cli.now(),error=type(error).__name__,detail=str(error))
    s.write(out/'coordinator-failure.json',value)
    return value


def coordinator():
    s=cli.Store(ROOT); out=TRIALS/'bootstrap'
    owner=cli.load_module('crc_coordinator_owner',ROOT/'.cache/p3-4-screening-20260922/supervisor.py')
    cli.require(owner.owned.in_job(),'finite coordinator required')
    api=Crc(s,'bootstrap'); c=api.context(out); api.preflight(c,out)
    cli.require(c.sources()==s.read(out/'intent.json')['sources'],'running sources changed')
    result=dict(result='CRC_BOOTSTRAP_INCOMPLETE'); started=False
    try:
        observed=api.inspect(c,out/'prestart-phone')
        api.prepare(c,out,observed,tests(s))
        owner.owned.launch(out/'runtime/network',Path(__file__),['network','--arm','bootstrap'],cli.NETWORK_SUPERVISOR_SECONDS)
        started=True
        def ready():
            # Closed/ready are write-once receipts; avoid polling the mutable heartbeat.
            cli.require(not (out/'runtime/network/closed.json').exists(),'network closed before readiness')
            return (out/'live-network.json').exists()
        cli.wait_until(ready,seconds=cli.NETWORK_READY_WAIT_SECONDS)
        api.network_ready(c,out)
        owner.owned.launch(out/'runtime/s04',Path(__file__),['cell','--arm','bootstrap'],cli.CELL_SECONDS)
        s.write(out/'coordinator-ready.json',dict(time=cli.now(),cell='s04',arm='bootstrap'))
        cli.wait_until(lambda:(out/'runtime/s04/closed.json').exists(),seconds=cli.CELL_SECONDS+30)
        result.update(cell=s.read(out/'cells/s04/result.json'),owner=s.read(out/'runtime/s04/closed.json'))
        result['result']=result['cell']['result']
    except Exception as error:
        result.update(preserve_failure(s,out,error))
    finally:
        if started:
            try:
                s.write(out/'network-stop.json',dict(time=cli.now(),reason='coordinator-closure'))
                cli.wait_until(lambda:(out/'runtime/network/closed.json').exists(),seconds=600)
                result['network_owner']=s.read(out/'runtime/network/closed.json')
            except Exception as error:
                result['cleanup_error']=dict(error=type(error).__name__,detail=str(error))
        s.write(out/'coordinator-result.json',dict(result,time=cli.now()))
    cli.require('error' not in result and 'cleanup_error' not in result,'CRC coordinator needs reconciliation')


if __name__=='__main__':
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'explicit root and isolated Python required')
    if sys.argv[1:]==['coordinator','--arm','bootstrap']:
        coordinator()
    else:
        batch.clone(batch.radio.main,__file__=__file__,Radio=Crc,TRIALS=TRIALS,ORDER=('bootstrap',),
            validate_config=batch.validate_config,tests=tests,verify_pre_cell_failure=reconciled_preflight)()
