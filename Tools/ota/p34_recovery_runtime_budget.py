"""HOST_ONLY operation counts and explicitly non-guaranteed timing extrapolation."""
import argparse
import json
import math
from pathlib import Path
import re
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_install_cost as host
import p34_nor_audit

cli=host.cli
SELF=Path(__file__).resolve()


class Counter:
    def __init__(self): self.total=0;self.kinds={}
    def __len__(self): return self.total
    def append(self,item):
        self.total+=1
        kind=item[0] if type(item[0])is str else 'store'
        self.kinds[kind]=self.kinds.get(kind,0)+1


def extrapolate(calls,baseline_calls,baseline_seconds):
    if (type(calls)is not int or calls<0 or type(baseline_calls)is not int or baseline_calls<=0 or
        type(baseline_seconds) not in (int,float) or not math.isfinite(baseline_seconds) or baseline_seconds<=0):
        raise ValueError('finite measured baseline and exact model call counts required')
    return calls*baseline_seconds/baseline_calls


def sources(store):
    paths=[SELF,ROOT/'tests/boot/test_p34_recovery_runtime_budget.py',ROOT/'Tools/ota/p34_install_cost.py',
           ROOT/'Tools/ota/p34_session.py',ROOT/'Tools/ota/p34_nor_audit.py',
           ROOT/'.agents/skills/e-track-flutter-debug/scripts/host_io.py',
           ROOT/'.cache/p34-recovery-ports3/result.json',ROOT/'.cache/p34-gpio-device1/audit.json',
           ROOT/'.cache/p34-recovery-preflight1/envelope.bin']
    ports=store.read(ROOT/'.cache/p34-recovery-ports3/result.json')
    audit=store.read(ROOT/'.cache/p34-gpio-device1/audit.json')
    cli.require(ports['result']=='RECOVERY_PORTS_HOST_PASS' and audit['result']=='GPIO_SESSION_SDK_AUDIT_PASS',
                'original adapter and physical GPIO evidence required')
    for record in ports['inputs']+audit['inputs']:
        cli.require(cli.record(record['path'])==record,'budget dependency drift')
        paths.append(Path(record['path']))
    return list(dict.fromkeys(paths))


def baseline(store):
    worker=store.read(ROOT/'.cache/p34-gpio-device1/worker.json')
    active=False;done=False;count=0;native=0
    for row in p34_nor_audit.events(ROOT/'.cache/p34-gpio-device1/events.jsonl'):
        if row['event']=='gpio-read-start':
            cli.require(not active and not done,'one measured GPIO interval required');active=True
        elif row['event']=='gpio-read-returned':
            cli.require(active,'unpaired measured end');active=False;done=True
        elif active and row['event']=='ap-call-returned':
            cli.require(row['rc']>=0 and row['ended']>=row['started'],'physical call failure')
            count+=1;native+=row['ended']-row['started']
    elapsed=worker['read']['elapsed_seconds']
    cli.require(done and not active and count==76115 and 0<native<elapsed<300,'physical timing binding mismatch')
    return dict(native_calls=count,elapsed_seconds=elapsed,native_seconds=native,
                inclusive_seconds_per_call=elapsed/count,qualification='One GPIO read sample, not a worst-case bound')


def calculate(store,out):
    sys.path.insert(0,str(ROOT/'tests/boot'))
    import test_p34_recovery_ports as model
    started=time.monotonic()
    observed=baseline(store)
    page=store.read(ROOT/'.cache/p34-confirm-page2/result.json')
    cli.require(cli.record(page['dll']['path'])==page['dll'],'C draft DLL drift')
    dll,fn=model.core.bind(Path(page['dll']['path']))
    plan=model.confirm_io.draft(fn,model.BEFORE*2,model.BOOT,model.IMAGE)
    def make():
        clock=model.Clock();slave=model.Slave(clock,model.BEFORE+b'R'*128)
        sdk=model.SDK(slave);sdk.calls=Counter()
        words=model.Words(model.Dap(sdk),lambda *a,**k:None,reads=model.gpio.READS,write_allowed=model.gpio.allowed_write,
                          seconds=2400,clock=clock,guard=lambda f,*a,**k:f(*a))
        pins=model.gpio.Pins(words,sdk.original,lambda:True)
        wire=model.EEPROM(pins,plan.address,plan.record,seconds=1800,clock=clock,sleep=clock.sleep)
        return clock,slave,sdk,wire
    clock,slave,sdk,wire=make()
    wire.read(0,64,300);read64=len(sdk.calls)
    cli.require(read64==observed['native_calls'],'model/physical read call count differs')
    a=len(sdk.calls);wire.page(plan.address,plan.record[:8],120);page8=len(sdk.calls)-a
    clock.sleep(.005)
    a=len(sdk.calls);cli.require(wire.ack(30),'model ACK failed');ack=len(sdk.calls)-a
    a=len(sdk.calls);wire.read(plan.address,8,300);read8=len(sdk.calls)-a
    clock,slave,sdk,wire=make()
    transaction=model.confirm_io.Transaction(fn,plan,wire,seconds=1800,clock=clock,sleep=clock.sleep)
    result=transaction.run()
    cli.require(result['result']=='EEPROM_BYTES_CONFIRMED' and result['error'] is None and result['pages']==8,
                'complete C-driven model transaction failed')
    eeprom=dict(read64_calls=read64,page8_calls=page8,ready_ack_calls=ack,read8_calls=read8,
                transaction_calls=len(sdk.calls),pages=result['pages'],model_kinds=sdk.calls.kinds)
    for key in ('read64','page8','ready_ack','read8','transaction'):
        eeprom[key+'_extrapolated_seconds']=extrapolate(eeprom[key+'_calls'],read64,observed['elapsed_seconds'])
    preimage=(ROOT/'.cache/p34-recovery-preflight1/envelope.bin').read_bytes()
    clock=model.Clock();sdk=model.FlashSDK(clock,preimage)
    sdk.calls=Counter();sdk.write_log=Counter();sdk.mutations=Counter()
    sectors=[]
    for index in range(303):
        cli.require(time.monotonic()-started<240,'finite host model budget exhausted')
        before=len(sdk.calls)
        port=model.flash.Sector(model.Dap(sdk),model.IMAGE,preimage,index,lambda:True,lambda *a,**k:None,
            seconds=300,clock=clock,sleep=clock.sleep,guard=lambda f,*a,**k:f(*a))
        result=port.run()
        sectors.append(dict(index=index,native_calls=len(sdk.calls)-before,programmed_words=result['programmed_words'],bank=result['bank']))
        if index%32==31: print('HOST_ONLY_FLASH_COUNT sectors='+str(index+1),flush=True)
    cli.require(bytes(sdk.flash)==model.IMAGE+preimage[len(model.IMAGE):] and sdk.mutations.kinds.get('erase')==303,
                'sequential model/collateral mismatch')
    flash=dict(sectors=sectors,native_calls=len(sdk.calls),native_kinds=sdk.calls.kinds,
               target_stores=len(sdk.write_log),mutations=sdk.mutations.kinds,
               extrapolated_seconds=extrapolate(len(sdk.calls),read64,observed['elapsed_seconds']))
    store.write(out/'model.json',dict(result='RECOVERY_RUNTIME_MODEL_COUNTED',observed_gpio=observed,eeprom=eeprom,flash=flash,
        hardware_operations=0,flash_timing_qualified=False,eeprom_write_timing_qualified=False,
        assumptions='Inclusive GPIO seconds/call projected onto different operation mixes; extra Flash busy polls are not modeled',
        no_write_authority=True,host_elapsed_seconds=time.monotonic()-started))
    print('RECOVERY_RUNTIME_MODEL_COUNTED',json.dumps(dict(eeprom=eeprom,flash_native_calls=flash['native_calls'],
          flash_extrapolated_seconds=flash['extrapolated_seconds'])),flush=True)


def preflight(store,out,inputs):
    cli.require(not out.exists(),'preserve runtime model evidence')
    for name in ('model.json','model-run.log','model-run.json','tests.json','tests.log','result.json','plan.json'):
        store.checked(out/name)
    for path in inputs: store.checked(out/'source'/path.relative_to(ROOT))
    for key in ('HOME','USERPROFILE','APPDATA','LOCALAPPDATA','TEMP','TMP','TMPDIR','XDG_CACHE_HOME',
                'XDG_CONFIG_HOME','XDG_DATA_HOME','PYTHONUSERBASE','PYTHONPYCACHEPREFIX','CCACHE_DIR','SCCACHE_DIR'):
        store.checked(out/'host'/key.lower())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('run','worker'))
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'isolated root required')
    store=cli.Store(ROOT);out=store.checked(args.output_dir);inputs=sources(store)
    if args.action=='worker':
        cli.require(store.read(out/'plan.json')['inputs']==[cli.record(path) for path in inputs],'model source drift')
        calculate(store,out);return
    preflight(store,out,inputs)
    records=[cli.record(path) for path in inputs]
    env=host.environment(store,out)
    for path in inputs: store.raw(out/'source'/path.relative_to(ROOT),path.read_bytes())
    store.write(out/'plan.json',dict(inputs=records,hardware=False))
    log=host.command(store,out,'tests',[sys.executable,'-I','-S','-B','-X','utf8',
        ROOT/'tests/boot/test_p34_recovery_runtime_budget.py','-v'],env,30)
    match=re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b',log)
    cli.require(match,'budget helper tests failed')
    host.command(store,out,'model-run',[sys.executable,'-I','-S','-B','-X','utf8',SELF,'worker','--output-dir',out],env,300)
    cli.require(records==[cli.record(path) for path in inputs],'model/test source drift')
    store.write(out/'result.json',dict(result='RECOVERY_RUNTIME_HOST_PASS',tests=int(match[1]),inputs=records,
                                      model=cli.record(out/'model.json'),hardware=False))
    print('RECOVERY_RUNTIME_HOST_PASS')


if __name__=='__main__': main()
