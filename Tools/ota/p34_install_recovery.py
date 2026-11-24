"""Source-bound installation host under the existing App/A64/original-Boot scope.

Preparation and host tests do not operate a device. Physical execution requires
the complete current test receipt; never replay a failed/uncertain cell.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_probe_acquire as base
import p34_install_body_tests as body_tests
import p34_online_log_probe as setup
import p34_confirm_page as confirm
import p34_failed_install_audit as failed_entry
from recovery_confirm.ap_journal import JournalSDK
from recovery_confirm.mutation_audit import SealedGate
from recovery_confirm.online_log import OnlineLog
from recovery_confirm.install import Install,BODY_SEGMENTS
from recovery_confirm.nor_capture import REGIONS

cli,host = base.cli,base.host
SELF = Path(__file__).resolve()
BODY_TESTS = ROOT/'.cache/p34-install-body-tests8/result.json'
WORKER_SECONDS,PARENT_SECONDS = 28000,28200
LOGS = tuple('sdk-%03d.log'%index for index in range(BODY_SEGMENTS+2))
ASSETS = {
    'boot': ROOT/'.cache/p34-native-acquire1/boot-readback.bin',
    'old_app': ROOT/'.cache/p34-native-image1/app-readback.bin',
    'envelope': ROOT/'.cache/p34-recovery-preflight1/envelope.bin',
    'image': ROOT/'.cache/p34-recovery-sources1/r2-a.bin',
    'bcb': ROOT/'.cache/p34-host-nor-rebuild1/bcb-before.bin',
    'map': ROOT/'.cache/p34-early-usb-r2/on/b/app-gcc/X-Track-App-GCC.map',
    **{name:ROOT/'.cache/p34-host-nor-rebuild1'/('after-'+name+'.bin') for name in REGIONS},
}
ARCHIVES = {'draft-a':64}
for label in ('before','after'):
    ARCHIVES.update({label+'-boot':65536,label+'-envelope':620544,label+'-bcb':256})
    ARCHIVES.update({label+'-'+name:end-start for name,(start,end,_) in REGIONS.items()})
for index in (0,1,4,7,10,13,16,19,22,25,26,27,28,29):
    ARCHIVES['confirm-read-'+str(index)] = 64 if index in (0,1,26,27,28,29) else 8
FILES = (*LOGS,*(name+'.bin' for name in ARCHIVES),
         'plan.json','parent.json','worker.json','worker.log','events.jsonl','callbacks.log','project.jlink',
         'tests.json','tests.log','result.json')


def sources(store):
    tested = store.read(BODY_TESTS)
    current_body = body_tests.sources(store)
    cli.require(tested['result']=='INSTALL_BODY_HOST_PASS' and
                tested['inputs']==[cli.record(path) for path in current_body],'complete body test/source binding required')
    return list(dict.fromkeys([*body_tests.sources(store),*base.SOURCES,*setup.sources(store),
        SELF,BODY_TESTS,ROOT/'tests/boot/test_p34_install_recovery.py',*ASSETS.values(),
        *failed_entry.INPUTS,failed_entry.RECEIPT]))


def preflight(store,out,inputs):
    cli.require(not out.exists(),'preserve original installation cell; never replay')
    for name in FILES: store.checked(out/name)
    for source in inputs: store.checked(out/'source'/source.relative_to(ROOT))
    for key in ('HOME','USERPROFILE','APPDATA','LOCALAPPDATA','TEMP','TMP','TMPDIR','XDG_CACHE_HOME',
                'XDG_CONFIG_HOME','XDG_DATA_HOME','PYTHONUSERBASE','PYTHONPYCACHEPREFIX','CCACHE_DIR','SCCACHE_DIR'):
        store.checked(out/'host'/key.lower())


class Archives:
    def __init__(self,store,out):
        self.store,self.out = store,store.checked(out)
        self.paths = {name:store.checked(out/(name+'.bin')) for name in ARCHIVES}
        cli.require(not any(path.exists() for path in self.paths.values()),'preserve archives')
        self.streams,self.hashes,self.records = {},{},{}
        self.error = None
        self.finished = False

    def write(self,name,offset,data):
        try:
            cli.require(not self.error and not self.finished and name in ARCHIVES and type(offset) is int and
                        type(data) is bytes and 0<len(data)<=32768,'archive scope/phase')
            if name not in self.streams:
                cli.require(offset==0,'archive first offset')
                self.streams[name] = self.paths[name].open('xb')
                self.hashes[name] = hashlib.sha256()
            stream = self.streams[name]
            cli.require(stream.tell()==offset and offset+len(data)<=ARCHIVES[name],'archive offset/extent')
            cli.require(stream.write(data)==len(data),'short archive write')
            stream.flush()
            os.fsync(stream.fileno())
            self.hashes[name].update(data)
            record = cli.record(self.paths[name])
            cli.require(record['bytes']==offset+len(data) and record['sha256']==self.hashes[name].hexdigest(),
                        'durable archive readback differs')
            self.records[name] = record
            return record
        except BaseException as error:
            if self.error is None: self.error = type(error).__name__+': '+str(error)
            raise

    def finish(self):
        cli.require(not self.error and not self.finished and set(self.records)==set(ARCHIVES),'incomplete archive set')
        for name,size in ARCHIVES.items():
            cli.require(self.records[name]['bytes']==size and cli.record(self.paths[name])==self.records[name],
                        'incomplete/changed final archive')
        self.finished = True
        return dict(self.records)

    def close(self):
        errors = []
        for name,stream in self.streams.items():
            if not stream.closed:
                try: stream.close()
                except BaseException as error: errors.append(name+': '+str(error))
        if errors: raise OSError('; '.join(errors))


def execute(dap,observation,persist,initial_rows,paths,record,remaining,archives,assets,function,
            *,clock=time.monotonic,guard=base.guarded,retained_entry=None):
    result = dict(result='FAILED',close_returned=False,historical_sdk_audit_passed=False)
    logs = body = None
    normal = False
    restore = None
    original_close = observation.close
    def close():
        retain = not normal and (retained_entry is not None or body is not None and body.control.mutation_attempted)
        if not retain or observation.closed:
            return original_close()
        # Install before connect: Observation can close internally on admission
        # failure, before a body or the first target selector exists.
        dap.power_changed = False
        dap.metadata['dp_restore_deferred_for_halt'] = True
        try:
            if dap.ready: dap.metadata['retained_dp_ctrlstat'] = dap._power_ready()
        finally:
            original_close()
    observation.close = close
    try:
        observation.connect()
        cli.require(dap.original_csw==dap.word_csw==0x23000052,'qualified native word profile required')
        acquisition,restore = setup.dp_plan(dap.metadata)
        logs = OnlineLog(dap,SealedGate(paths,dap.metadata,record),persist,remaining,initial_rows=initial_rows,clock=clock)
        logs.switch(read_allowed=lambda _:False,expected_stores=[],expected_dp_writes=acquisition)
        body = Install(dap,observation,logs,remaining,archives.write,assets,function,clock=clock,guard=guard,
                       retained_entry=retained_entry)
        result['body'] = body.run()
        cli.require(result['body']['result']=='READY_FOR_FINAL_NATIVE_CLOSE','incomplete installation body')
        result['archives'] = guard(archives.finish,seconds=min(60,remaining()-90))
        logs.prepare_close()
        normal = True
    except BaseException as error:
        result['error'] = type(error).__name__+': '+str(error)
    finally:
        try:
            observation.close()
        except BaseException as error:
            normal = False
            result['close_error'] = type(error).__name__+': '+str(error)
        try: archives.close()
        except BaseException as error:
            normal = False
            result['archive_close_error'] = type(error).__name__+': '+str(error)
        result.update(close_returned=dap.close_returned,dap=dict(dap.metadata),native_ap_error=dap.sdk.error)
        if body:
            result.update(phase=body.phase,app_may_have_changed=body.app_may_have_changed,
                flash_sectors_audited=len(body.flash_sequence.completed) if body.flash_sequence else 0,
                eeprom_pages_attempted=body.eeprom_wire.page_index if body.eeprom_wire else 0,
                reset_attempted=bool(body.exit_port and body.exit_port.reset_attempted),
                release_attempted=bool(body.exit_port and body.exit_port.release_attempted),
                release_returned=body.released,component_results=body.results)
        if normal:
            try:
                trace = guard(lambda:logs.finish(read_allowed=lambda _:False,expected_stores=[],
                    expected_dp_writes=restore),seconds=min(60,remaining()))
                preserved_dp = not dap.power_changed and dap.metadata['original_dp']&0xf0000000==0xf0000000
                cli.require(dap.close_returned and dap.metadata['tar_restored'] and dap.metadata['csw_restored'] and
                            (dap.metadata['dp_restored'] or preserved_dp),'normal final AP/native restoration missing')
                result.update(result='R2_INSTALLED_ORIGINAL_BOOT_CLOSED',final_trace=trace,
                              logs=list(logs.gate.records),runtime_health_observed=True,
                              original_dp_preserved_without_write=preserved_dp)
            except BaseException as error:
                result['final_audit_error'] = type(error).__name__+': '+str(error)
        if logs: result.update(log_mode=logs.mode,log_error=logs.error,sealed=list(logs.gate.records))
    return result


def json_result(value):
    if type(value) is bytes: return dict(bytes=len(value),hex=value.hex())
    if isinstance(value,dict): return {key:json_result(item) for key,item in value.items()}
    if isinstance(value,(list,tuple)): return [json_result(item) for item in value]
    return value


def worker(store,out):
    deadline = time.monotonic()+WORKER_SECONDS
    cli.require(base.in_job(),'owned installation worker required')
    plan = store.read(out/'plan.json')
    cli.require(plan['out']==str(out) and plan['inputs']==[cli.record(p) for p in sources(store)],'installation source drift')
    cli.require(plan['native_history_approved']==str(base.HISTORY) and plan['scope']==SCOPE,'exact recorded operation scope required')
    cli.require(cli.record(base.JLINK/'JLink_x64.dll')['sha256']==base.DLL_SHA,'native DLL drift')
    assets = {name:path.read_bytes() for name,path in ASSETS.items()}
    retained_entry = failed_entry.predecessor(store)
    page = store.read(ROOT/'.cache/p34-confirm-page2/result.json')
    cli.require(cli.record(page['dll']['path'])==page['dll'],'original C oracle DLL drift')
    dll,function = confirm.bind(Path(page['dll']['path']))
    archives = Archives(store,out)
    dap = observation = None
    result = dict(result='FAILED',close_returned=False)
    with (out/'events.jsonl').open('x',encoding='utf-8') as events,(out/'callbacks.log').open('xb') as callbacks:
        initial = []
        def persist(event,**fields):
            events.write(json.dumps(dict(time=cli.now(),event=event,**fields))+'\n')
            events.flush()
            if event in ('online-log-sealed','recovery-install-phase'): os.fsync(events.fileno())
            if event in ('flash-sequence-sector-audited','recovery-install-phase',
                         'nor-region-captured-audited','eeprom-operation-audited'):
                print(json.dumps(dict(time=cli.now(),event=event,**fields)),flush=True)
        def collect(event,**fields):
            persist(event,**fields)
            initial.append(dict(event=event,**fields))
        try:
            cli.require(not base.native_presence()['debugger_processes'],'competing debugger')
            cli.require(deadline-time.monotonic()>WORKER_SECONDS-60,'worker setup exhausted initial allowance')
            with os.add_dll_directory(str(base.JLINK)):
                sdk = base.guarded(ctypes.CDLL,str(base.JLINK/'JLink_x64.dll'))
                dap = base.Dap(sdk,out/LOGS[0],out/'project.jlink',callbacks)
                dap.sdk = JournalSDK(sdk,collect)
                observation = base.Observation(dap,collect,seconds=600)
                result = execute(dap,observation,persist,initial,[out/name for name in LOGS],cli.record,
                                 lambda:deadline-time.monotonic(),archives,assets,function,retained_entry=retained_entry)
        except BaseException as error:
            result['outer_error'] = type(error).__name__+': '+str(error)
            if observation is None and dap is not None and dap._opened:
                try: dap.close()
                except BaseException as close: result['outer_close_error'] = str(close)
            try: archives.close()
            except BaseException as close: result['outer_archive_close_error'] = str(close)
        if dap: result.update(close_returned=dap.close_returned,dap=dict(dap.metadata))
        try:
            result['sources_unchanged_after_close'] = plan['inputs']==[cli.record(path) for path in sources(store)]
        except BaseException as error:
            result.update(sources_unchanged_after_close=False,source_check_error=type(error).__name__+': '+str(error))
        if not result['sources_unchanged_after_close']:
            result.update(result='FAILED',source_drift_after_close=True)
        store.write(out/'worker.json',json_result(result))
    print(json.dumps(dict(result=result['result'],phase=result.get('phase'),close_returned=result['close_returned'])),flush=True)
    return 0 if result['result']=='R2_INSTALLED_ORIGINAL_BOOT_CLOSED' else 1


SCOPE = dict(app=[0x08010000,0x080a7800],preserved_suffix_bytes=964,eeprom=[0,64],
             eeprom_source='unchanged original C transaction',boot_payload_writes=0,nor_payload_writes=0,
             exit='verified fresh original Boot reset/catch and separate release',jlink_supply_change=False,
             entry='exact reconciled install1 retained context; no original-App resume or fresh rendezvous')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('selftest','execute','worker'))
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--tests',type=Path)
    parser.add_argument('--native-history-approved',type=Path)
    args = parser.parse_args()
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'isolated root required')
    store = cli.Store(ROOT)
    out = store.checked(args.output_dir)
    if args.action=='worker': return worker(store,out)
    inputs = sources(store)
    preflight(store,out,inputs)
    records = [cli.record(p) for p in inputs]
    if args.action=='execute':
        failed_entry.predecessor(store)
        tests = store.read(args.tests)
        cli.require(tests['result']=='INSTALL_HOST_PASS' and tests['inputs']==records,'complete current host test binding required')
        cli.require(args.native_history_approved==base.HISTORY,'exact native history authority required')
        cli.require(shutil.disk_usage(ROOT).free>=20*1024**3,'20 GiB project-drive evidence margin required')
        before = base.history(store)
    env = host.environment(store,out)
    for source in inputs: store.raw(out/'source'/source.relative_to(ROOT),source.read_bytes())
    if args.action=='selftest':
        env['P34_TEST_OUT'] = str(out)
        log = host.command(store,out,'tests',[sys.executable,'-I','-S','-B','-X','utf8',
            ROOT/'tests/boot/test_p34_install_recovery.py','-v'],env,180)
        count = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b',log)
        cli.require(count and records==[cli.record(p) for p in inputs],'installation host test/source drift')
        store.write(out/'result.json',dict(result='INSTALL_HOST_PASS',tests=int(count[1]),inputs=records,
            hardware=False,physical_admission=False))
        print('INSTALL_HOST_PASS tests='+str(int(count[1])));return 0
    store.write(out/'plan.json',dict(out=str(out),inputs=records,tests=cli.record(args.tests),scope=SCOPE,
        before_history=before,native_history_approved=str(base.HISTORY),worker_seconds=WORKER_SECONDS,
        parent_seconds=PARENT_SECONDS,physical_timing_bound_qualified=False,historical_sdk_audit_passed=False))
    result = base.owned_run(store,out,[SELF,'worker','--output-dir',out],env,timeout=PARENT_SECONDS)
    result.update(after_history=base.history(store),presence_after=base.native_presence())
    store.write(out/'parent.json',result)
    print(json.dumps(result))
    return 0 if result['exit']==0 and not result['timeout'] else 1


if __name__=='__main__': raise SystemExit(main())
