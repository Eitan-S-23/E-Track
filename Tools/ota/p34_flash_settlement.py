"""Bounded read-only settlement of install2's partial Flash; no repair API."""
import argparse
import ctypes
import json
import math
import os
from pathlib import Path
import re
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_install_recovery as prior
import p34_install_offline_audit as audit
from recovery_confirm.native_io import Words
from recovery_confirm.online_log import OnlineLog
from recovery_confirm.mutation_audit import SealedGate
from recovery_confirm.ap_journal import JournalSDK
from recovery_entry.control_probe import Control,DCRSR,READ_WORDS
from recovery_entry.rendezvous import WFI

base,cli,host=prior.base,prior.cli,prior.host
from recovery_confirm import flash_port as flash
SELF=Path(__file__).resolve()
PROOF=ROOT/'.cache/p34-flash-failure-audit1/result.json'
EXPECTED=ROOT/'.cache/p34-flash-failure-audit1/expected-envelope.bin'
AREA=ROOT/'.cache/p34-recovery-install2'
META=(flash.IDCODE,flash.FSIZE,*flash.CLOCK,*flash.CONFIG,*flash.PROTECTION,
      *(a for _,s,c,_ in flash.BANKS for a in (s,c)))
READS={flash.DHCSR,flash.PAUSE,*META,*range(0x08010000,0x08011800,4)}
CONTROL_READS=READS|READ_WORDS|{WFI}
LOGS=tuple('sdk-%03d.log'%i for i in range(5))
FILES=(*LOGS,'events.jsonl','callbacks.log','worker.log','worker.json','parent.json','plan.json',
       'project.jlink','affected.bin','result.json','tests.json','tests.log')


class RetainedObservation(base.Observation):
    def close(self):
        if self.closed: return
        self.backend.power_changed=False
        self.backend.metadata['dp_restore_deferred_for_halt']=True
        try:
            if self.backend.ready:
                self.backend.metadata['retained_dp_ctrlstat']=self.backend._power_ready()
        finally:
            super().close()


class Boundary:
    def __init__(self,port,remaining,guard=base.guarded):
        self.port,self.remaining,self.guard=port,remaining,guard
        self.previous=None
    def limit(self):
        left=self.remaining()
        if (type(left) not in (int,float) or not math.isfinite(left) or not 60<left<=180 or
                self.previous is not None and left>self.previous):
            raise ValueError('settlement close reserve/clock lost')
        self.previous=left
        return min(30,self.port.check(),left-60)
    def __call__(self,function,*args):
        value=self.guard(function,*args,seconds=self.limit())
        self.limit()
        return value


def capture(port,control,expected,context,seal,archive,*,bounded):
    if len(expected)!=6144: raise ValueError('exact affected6KiB expected')
    def metadata():
        if port.read32(flash.DHCSR)&0x020affff!=0x20003 or port.read32(flash.PAUSE)!=0x1000:
            raise ValueError('retained halt/reset/pause changed')
        raw={a:port.read32(a) for a in META}
        if any(raw[s]&0x15 for _,s,_,_ in flash.BANKS): raise ValueError('Flash busy/error; observe only')
        if (raw[flash.BANKS[0][1]]!=0x20 or raw[flash.BANKS[0][2]]!=1 or
                raw[flash.BANKS[1][2]]!=0x80): raise ValueError('unexpected Flash settlement controls')
        if raw[flash.IDCODE]!=0x70083347 or raw[flash.FSIZE]&0xffff!=1024:
            raise ValueError('Flash identity changed')
        if any(raw[a]!=v for a,v in flash.CLOCK.items()): raise ValueError('clock profile changed')
        return raw
    before=metadata()
    initial=bounded(control.initial)
    if (not initial['halted'] or initial['lockup'] or initial['reset_sticky'] or initial['dhcsr_control']!=3 or
            initial['vtor']!=0x08010000 or initial['comparators']!=[0]*6 or initial['debug_apb1_frz']!=0x1000):
        raise ValueError('retained entry controls differ')
    if bounded(control.context)!=context: raise ValueError('retained CPU context differs')
    selectors=tuple((DCRSR,v) for v in (15,16,17,20))
    bounded(seal,CONTROL_READS,selectors,False)
    actual=bytearray()
    for offset in range(0,6144,1024):
        if metadata()!=before: raise ValueError('Flash changed before read')
        actual.extend(port.read_bytes(0x08010000+offset,1024))
        if metadata()!=before: raise ValueError('Flash changed after read')
    bounded(archive,bytes(actual))
    if bytes(actual)!=expected: raise ValueError('affected Flash differs from reconciled partial prefix')
    bounded(seal,READS,(),True)
    if bounded(control.context)!=context or metadata()!=before: raise ValueError('terminal context/controller drift')
    bounded(seal,CONTROL_READS,selectors,False)
    return dict(result='PARTIAL_FLASH_SETTLED_READ_ONLY',before=before,after=before,context=context,
                last_word=0x8965ff72,next_address=0x08011228,repair_admitted=False)


def sources(store):
    proof=store.read(PROOF)
    cli.require(proof['result']=='PARTIAL_FLASH_PREFIX_RECONCILED_NOT_RESUME_ADMITTED' and
                proof['expected_envelope']==cli.record(EXPECTED),'partial-prefix proof required')
    for record in proof['inputs']+proof['logs']:
        cli.require(audit.record(store.checked(record['path']))==record,'partial-prefix evidence drift')
    return list(dict.fromkeys([*prior.sources(store),SELF,ROOT/'tests/boot/test_p34_flash_settlement.py',PROOF,EXPECTED,
                              ROOT/'Tools/ota/p34_flash_failure_audit.py',ROOT/'Tools/ota/p34_install_offline_audit.py',
                              AREA/'worker.json',AREA/'parent.json',AREA/'plan.json']))


def preflight(store,out,inputs):
    cli.require(not out.exists(),'preserve settlement evidence')
    for name in FILES:store.checked(out/name)
    for path in inputs:store.checked(out/'source'/path.relative_to(ROOT))


def worker(store,out):
    deadline=time.monotonic()+180
    cli.require(base.in_job(),'owned settlement worker required')
    plan=store.read(out/'plan.json')
    cli.require(plan['inputs']==[cli.record(p) for p in sources(store)] and plan['out']==str(out),'settlement source drift')
    cli.require(plan['native_history_approved']==str(base.HISTORY) and
                cli.record(base.JLINK/'JLink_x64.dll')['sha256']==base.DLL_SHA,'native identity/scope mismatch')
    expected=EXPECTED.read_bytes()[:6144]
    context=store.read(AREA/'worker.json')['component_results']['entry']['context']
    result=dict(result='FAILED',close_returned=False,repair_admitted=False)
    observer=dap=logs=None
    normal=False
    with (out/'events.jsonl').open('x',encoding='utf-8') as events,(out/'callbacks.log').open('xb') as callbacks:
        initial=[]
        def persist(event,**fields):
            events.write(json.dumps(dict(time=cli.now(),event=event,**fields))+'\n');events.flush()
        def collect(event,**fields):persist(event,**fields);initial.append(dict(event=event,**fields))
        try:
            cli.require(deadline-time.monotonic()>150 and not base.native_presence()['debugger_processes'],'settlement setup allowance/owner')
            with os.add_dll_directory(str(base.JLINK)):
                sdk=base.guarded(ctypes.CDLL,str(base.JLINK/'JLink_x64.dll'))
                dap=base.Dap(sdk,out/LOGS[0],out/'project.jlink',callbacks)
                dap.sdk=JournalSDK(sdk,collect)
                observer=RetainedObservation(dap,collect,seconds=120)
                observer.connect()
                logs=OnlineLog(dap,SealedGate([out/n for n in LOGS],dap.metadata,cli.record),persist,
                               lambda:deadline-time.monotonic(),initial_rows=initial)
                logs.switch(read_allowed=lambda _:False,expected_stores=(),expected_dp_writes=prior.setup.dp_plan(dap.metadata)[0])
                observer.emit=logs.emit
                port=Words(dap,logs.emit,reads=READS,write_allowed=lambda a,v:False,seconds=min(90,deadline-time.monotonic()-60))
                control=Control(dap,observer,logs.emit,expected[0x400:0x460],retained=True)
                def seal(reads,stores,bind):
                    return logs.switch(read_allowed=lambda a:a in reads,expected_stores=stores,bind_words=bind)
                result['capture']=capture(port,control,expected,context,seal,
                                          lambda raw:store.raw(out/'affected.bin',raw),
                                          bounded=Boundary(port,lambda:deadline-time.monotonic()))
                observer._check()
                cli.require(port.writes==0,'unexpected data write')
                logs.prepare_close();normal=True
        except BaseException as error: result['error']=type(error).__name__+': '+str(error)
        finally:
            try:
                if observer:observer.close()
                elif dap:dap.close()
            except BaseException as error: normal=False;result['close_error']=type(error).__name__+': '+str(error)
            result['close_returned']=bool(dap and dap.close_returned)
            if dap:result['dap']=dict(dap.metadata)
            if normal:
                try:
                    logs.gate.cursor.metadata=dict(dap.metadata,original_dp=0xf0000040)
                    result['final_trace']=logs.finish(read_allowed=lambda _:False,expected_stores=())
                    result.update(result='PARTIAL_FLASH_SETTLED_CLOSED_NOT_WRITE_ADMITTED',logs=logs.gate.records,
                                  affected=cli.record(out/'affected.bin'))
                except BaseException as error:result['audit_error']=type(error).__name__+': '+str(error)
            if logs:result['sealed']=list(logs.gate.records)
            try:
                result['sources_unchanged_after_close']=plan['inputs']==[cli.record(p) for p in sources(store)]
            except BaseException as error:
                result['sources_unchanged_after_close']=False
                result['source_error']=type(error).__name__+': '+str(error)
            if not result['sources_unchanged_after_close']:result['result']='FAILED'
            store.write(out/'worker.json',result)
    print(json.dumps(result));return 0 if result['result']=='PARTIAL_FLASH_SETTLED_CLOSED_NOT_WRITE_ADMITTED' else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('selftest','capture','worker'))
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--tests',type=Path)
    parser.add_argument('--native-history-approved',type=Path)
    args=parser.parse_args()
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'isolated root required')
    store=cli.Store(ROOT);out=store.checked(args.output_dir)
    if args.action=='worker':return worker(store,out)
    inputs=sources(store);preflight(store,out,inputs);records=[cli.record(p) for p in inputs]
    if args.action=='capture':
        tests=store.read(args.tests)
        cli.require(tests['result']=='FLASH_SETTLEMENT_HOST_PASS' and tests['inputs']==records,'bound settlement tests required')
        cli.require(args.native_history_approved==base.HISTORY,'exact native history permission')
        before=base.history(store)
    env=host.environment(store,out)
    for p in inputs:store.raw(out/'source'/p.relative_to(ROOT),p.read_bytes())
    if args.action=='selftest':
        env['P34_TEST_OUT']=str(out)
        log=host.command(store,out,'tests',[sys.executable,'-I','-S','-B','-X','utf8',ROOT/'tests/boot/test_p34_flash_settlement.py','-v'],env,120)
        count=re.search(rb'Ran (\d+) tests',log)
        cli.require(count and records==[cli.record(p) for p in inputs],'settlement test/source drift')
        store.write(out/'result.json',dict(result='FLASH_SETTLEMENT_HOST_PASS',tests=int(count[1]),inputs=records,hardware=False))
        print('FLASH_SETTLEMENT_HOST_PASS',int(count[1]));return 0
    store.write(out/'plan.json',dict(out=str(out),inputs=records,tests=cli.record(args.tests),before_history=before,
        native_history_approved=str(base.HISTORY),scope='retained context+two-bank state+affected6KiB;8 DCRSR selectors only;no repair/reset/resume',
        worker_seconds=180,parent_seconds=240))
    result=base.owned_run(store,out,[SELF,'worker','--output-dir',out],env,timeout=240)
    result.update(after_history=base.history(store),presence_after=base.native_presence())
    store.write(out/'parent.json',result);print(json.dumps(result));return 0 if result['exit']==0 and not result['timeout'] else 1


if __name__=='__main__':raise SystemExit(main())
