"""Real recovery components bridged to existing native and EEPROM slave models."""
import ctypes
import io
import os
from pathlib import Path
from unittest import mock

import p34_gpio_read_device as run
import test_p34_app_resume as resume_model
import test_p34_control_probe as controls
import test_p34_owner_probe as owner_model
from p34_eeprom_wire_model import Clock,Slave

ROOT=Path(__file__).resolve().parents[2]


class SDK(resume_model.SDK):
    def __init__(self,clock,slave,fault=None):
        super().__init__(clock)
        self.slave,self.fault=slave,fault
        self.bridge_wrapped=set()
        self.gpio_stores=0
        old=run.cli.Store(ROOT).read(ROOT/'.cache/p34-entry-owner1/worker.json')
        raw=old['retained']['state_samples'][0]['raw']
        self.memory.update({controls.REGISTERS[key]:value for key,value in raw.items()})
        self.memory.update({address:resume_model.baseline()[key] for key,address in run.app_resume.REGISTERS.items()})
        self.memory.update(owner_model.Reader().memory)
        self.memory.update({owner_model.op.QSPI_REGS[key]:value for key,value in old['owner_samples'][0]['qspi'].items()})
        context=old['retained']['context']
        self.memory.update({controls.DHCSR:0x10001,controls.PAUSE:0x1000,0xe000ef34:context['fpccr'],
                            0x40002c00:0,0x20053538:0x104,0x200007e8:0})
        self.core.update({15:context['pc'],16:context['xpsr'],17:context['msp'],20:context['control']<<24})
        if fault=='header': self.memory[0x08010400]^=1

    def __getattr__(self,name):
        function=super().__getattr__(name)
        if name not in self.bridge_wrapped:
            old=function.callback
            def callback(*args):
                address=self.tar
                if name=='JLINKARM_CORESIGHT_ReadAPDPReg' and args[:2]==(3,1) and self.bank==0:
                    if address in (run.gpio.INPUT,run.gpio.OUTPUT):
                        value=self.memory[address]&~0xc0
                        value|=sum((self.slave.physical(pin) if address==run.gpio.INPUT else self.slave.level[pin])<<pin for pin in (6,7))
                        ctypes.cast(args[2],ctypes.POINTER(ctypes.c_uint32))[0]=value
                        self.tar+=4
                        return 0
                if name=='JLINKARM_CORESIGHT_WriteAPDPReg' and args[:2]==(3,1) and address in (run.gpio.SET,run.gpio.CLEAR):
                    self.slave.set(6 if args[2]==0x40 else 7,int(address==run.gpio.SET))
                    self.gpio_stores+=1
                    self.tar+=4
                    return -1 if self.fault=='gpio' and self.gpio_stores==1 else 0
                result=old(*args)
                if name=='JLINKARM_CORESIGHT_WriteAPDPReg' and args[:2]==(3,1):
                    if address==controls.COMP and args[2]==run.rendezvous.WFI_COMPARATOR:
                        self.memory[controls.DHCSR]=0x30003
                    if address==run.app_resume.DHCSR and self.fault=='release': return -1
                return result
            function.callback=callback
            self.bridge_wrapped.add(name)
        return function


def bridge(fault=None):
    clock=Clock()
    before=(ROOT/'.cache/p34-host-nor-rebuild1/bcb-before.bin').read_bytes()[:128]
    slave=Slave(clock,before+b'R'*128)
    sdk=SDK(clock,slave,fault)
    sdk.JLINKARM_ExecCommand.callback=lambda command,*args:int(command==b'InhibitConnectRetries = 1')
    rows=[];saved=[]
    emit=lambda event,**fields:rows.append(dict(event=event,**fields))
    words=run.Words
    store=run.cli.Store(ROOT)
    out=store.checked(Path(os.environ['P34_TEST_OUT'])/'native-model')
    log,project=(store.checked(out/name) for name in ('unused-mock.log','unused-mock.jlink'))
    with mock.patch('recovery_entry.native_probe.guarded',side_effect=lambda function,*args,**kwargs:function(*args)), \
         mock.patch.object(run,'Words',side_effect=lambda *args,**kwargs:words(*args,guard=lambda function,*a,**kw:function(*a),**kwargs)):
        dap=run.base.Dap(sdk,log,project,io.BytesIO())
        dap.sdk=run.ap_journal.JournalSDK(sdk,emit,clock=clock)
        observation=run.base.Observation(dap,emit,seconds=420)
        result=run.execute(dap,observation,emit,lambda raw:(saved.append(raw) or dict(bytes=len(raw))),
                           resume_model.IMAGE,before[:64],clock=clock,sleep=clock.sleep)
    return result,rows,sdk,slave,saved


def sdk_lines(rows):
    """Synthetic SDK rendering, explicitly not a physical trace."""
    for operation,port,index,value,data,rc in run.ap_journal.calls(rows):
        if operation=='read':
            yield f'JLINK_CORESIGHT_ReadAPDPReg({port} reg 0x{index:02X})\n'
            yield f'Value=0x{data:08X}\n'
        else: yield f'JLINK_CORESIGHT_WriteAPDPReg({port} reg 0x{index:02X}, 0x{value:08X})\n'
        yield f'T0000 000:000.000 - 0.1ms returns {rc}\n'
    yield 'JLINK_Close()\n'
