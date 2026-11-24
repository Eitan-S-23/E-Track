import ctypes
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
sys.path.insert(0, str(ROOT/'tests/boot'))
import p34_confirm_page as core
from recovery_confirm.eeprom_page import EEPROM
from recovery_confirm.page_port import PagePort
from recovery_confirm import gpio_page as gpio
from recovery_confirm.native_io import Words
from recovery_confirm import flash_port as flash
from recovery_confirm.flash_plan import APP_START, IMAGE_SIZE
from recovery_confirm import boot_exit as leave
from recovery_confirm import confirm_io
from p34_eeprom_wire_model import Clock, Slave

BEFORE = (ROOT/'.cache/p34-host-nor-rebuild1/bcb-before.bin').read_bytes()[:128]
BOOT = (ROOT/'.cache/p34-native-acquire1/boot-readback.bin').read_bytes()
IMAGE = (ROOT/'.cache/p34-recovery-sources1/r2-a.bin').read_bytes()


class SDK:
    def __init__(self, slave):
        self.slave = slave
        self.tar = 0
        self.csw = 0x23000052
        self.calls = []
        self.memory = {gpio.DHCSR: 0x30003, gpio.WDT_PAUSE: 0x1000, gpio.MODE: 0x5000,
                       gpio.TYPE: 0xc0, gpio.DRIVE: 0, gpio.PULL: 0}
        self.fail_call = None
        self.dp = 0xf0000040
        self.original = {a: self.memory.get(a, 0xc0) for a in (gpio.MODE, gpio.TYPE, gpio.DRIVE, gpio.PULL, gpio.OUTPUT)}

    def JLINKARM_CORESIGHT_ReadAPDPReg(self, index, ap, out):
        self.calls.append(('read', index, ap, self.tar))
        if (index, ap) == (0, 1):
            value = self.csw
        elif (index, ap) == (1, 0):
            value = self.dp
        elif (index, ap) == (3, 1):
            if self.tar == gpio.OUTPUT:
                value = sum(self.slave.level[p] << p for p in (6, 7))
            elif self.tar == gpio.INPUT:
                value = sum(self.slave.physical(p) << p for p in (6, 7))
            else:
                value = self.memory[self.tar]
            self.tar += 4
        else:
            raise AssertionError((index, ap))
        ctypes.cast(out, ctypes.POINTER(ctypes.c_uint32))[0] = value
        return -1 if len(self.calls) == self.fail_call else 0

    def JLINKARM_CORESIGHT_WriteAPDPReg(self, index, ap, value):
        self.calls.append(('write', index, ap, self.tar, value))
        if (index, ap) == (1, 1):
            self.tar = value
        elif (index, ap) == (3, 1):
            assert self.tar in (gpio.SET, gpio.CLEAR) and value in (0x40, 0x80)
            self.slave.set(6 if value == 0x40 else 7, int(self.tar == gpio.SET))
            self.tar += 4
        else:
            raise AssertionError((index, ap))
        return -1 if len(self.calls) == self.fail_call else 0


class Dap:
    ready = True
    callback_error = None
    word_csw = 0x23000052

    def __init__(self, sdk):
        self.sdk = sdk


class FlashSDK(SDK):
    def __init__(self, clock, preimage, fault=None):
        super().__init__(Slave(clock,BEFORE+b'R'*128))
        self.clock, self.flash, self.fault = clock, bytearray(preimage), fault
        self.memory.update(flash.CLOCK)
        self.memory.update({a:0 for a in flash.CONFIG})
        self.memory[flash.FLASH+0x60] = 0x11
        self.memory.update({flash.IDCODE:0x70083347,flash.FSIZE:1024})
        self.memory.update({flash.FLASH+0x1c:0,flash.FLASH+0x20:0xffff0000,
                            flash.FLASH+0x2c:0x1f,flash.FLASH+0xcc:0})
        self.unlocked_keys = {key:0 for key,_,_,_ in flash.BANKS}
        self.mutations = []
        self.write_log = []
        for _,s,c,a in flash.BANKS:
            self.memory.update({s:0x20,c:0x80,a:0})
        self.mutation_seen = False

    def JLINKARM_CORESIGHT_ReadAPDPReg(self,index,ap,out):
        self.clock.value += .000001
        if (index,ap) == (3,1) and APP_START <= self.tar < APP_START+len(self.flash):
            self.calls.append(('read',index,ap,self.tar))
            offset = self.tar-APP_START
            ctypes.cast(out,ctypes.POINTER(ctypes.c_uint32))[0] = int.from_bytes(self.flash[offset:offset+4],'little')
            self.tar += 4
            return 0
        return super().JLINKARM_CORESIGHT_ReadAPDPReg(index,ap,out)

    def JLINKARM_CORESIGHT_WriteAPDPReg(self,index,ap,value):
        self.clock.value += .000001
        if (index,ap) != (3,1):
            return super().JLINKARM_CORESIGHT_WriteAPDPReg(index,ap,value)
        address = self.tar
        self.calls.append(('write',index,ap,address,value))
        self.write_log.append((address,value))
        self.tar += 4
        mutation = None
        for key,status,ctrl,addr in flash.BANKS:
            if address == key:
                if value == flash.KEY1: self.unlocked_keys[key] = 1
                elif value == flash.KEY2 and self.unlocked_keys[key] == 1:
                    self.memory[ctrl] = 0
                else: raise AssertionError('invalid keys')
                break
            if address == status:
                assert value == 0x34
                if self.fault != 'stale': self.memory[status] &= ~value
                break
            if address == addr:
                assert not self.memory[ctrl] & 0x80
                self.memory[addr] = value
                break
            if address == ctrl:
                assert value in (0,1,2,0x42,0x80) and not self.memory[ctrl] & 0x80
                self.memory[ctrl] = value & ~0x40
                if value == 0x42:
                    offset = self.memory[addr]-APP_START
                    assert offset >= 0 and offset % 2048 == 0 and offset+2048 <= len(self.flash)
                    if self.fault not in ('ignored','protected','noerase'):
                        self.flash[offset:offset+2048] = b'\xff'*2048
                    self.memory[status] = {'ignored':0,'busy':1,'protected':0x10}.get(self.fault,0x20)
                    mutation = ('erase',self.memory[addr])
                break
        else:
            assert APP_START <= address < APP_START+len(self.flash)
            _,status,ctrl,_ = flash.BANKS[int(address >= 0x08080000)]
            assert self.memory[ctrl] == 1
            offset = address-APP_START
            assert self.flash[offset:offset+4] == b'\xff'*4
            self.flash[offset:offset+4] = value.to_bytes(4,'little')
            self.memory[status] = 0x20
            mutation = ('program',address)
        if mutation:
            self.mutations.append(mutation)
            self.mutation_seen = True
            if self.fault == 'delivered': return -1
            if self.fault == 'dp-after': self.dp |= 0x20
        return 0


class ResetSDK(SDK):
    def __init__(self,clock,fault=None):
        super().__init__(Slave(clock,BEFORE+b'R'*128))
        self.clock,self.fault = clock,fault
        self.write_log = []
        self.core = {15:0x08045a78,16:0x21000000,17:0x20057da0,20:4<<24}
        self.memory.update({leave.AIRCR:0xfa050300,leave.DEMCR:0x1000000,leave.DFSR:2,
                            leave.VTOR:APP_START,leave.DCRDR:0})
        for origin in (0,0x08000000):
            self.memory[origin] = int.from_bytes(BOOT[:4],'little')
            self.memory[origin+4] = int.from_bytes(BOOT[4:8],'little')

    def JLINKARM_CORESIGHT_ReadAPDPReg(self,index,ap,out):
        self.clock.value += .000001
        clear = (index,ap)==(3,1) and self.tar==leave.DHCSR
        result = super().JLINKARM_CORESIGHT_ReadAPDPReg(index,ap,out)
        if clear: self.memory[leave.DHCSR] &= ~0x02000000
        return result

    def JLINKARM_CORESIGHT_WriteAPDPReg(self,index,ap,value):
        self.clock.value += .000001
        if (index,ap)!=(3,1): return super().JLINKARM_CORESIGHT_WriteAPDPReg(index,ap,value)
        address = self.tar
        self.calls.append(('write',index,ap,address,value))
        self.write_log.append((address,value))
        self.tar += 4
        if address == leave.DFSR:
            assert value==8
            if self.fault!='stale': self.memory[address] &= ~value
        elif address == leave.DEMCR:
            if self.fault!='arm': self.memory[address] = value
        elif address == leave.AIRCR:
            assert value==0x05fa0304
            if self.fault=='undelivered': return -1
            self.memory[leave.DHCSR] = 0x02030003
            self.memory[leave.VTOR] = 0
            if self.fault!='catch': self.memory[leave.DFSR] |= 8
            self.core = {15:0x080028b8,16:0x1000000,17:0x20058000,20:0}
            if self.fault=='pc': self.core[15] = 0x08045a78
            if self.fault=='alias': self.memory[4] ^= 2
            if self.fault=='pause': self.memory[leave.PAUSE] = 0
            if self.fault=='delivered': return -1
        elif address == leave.DCRSR:
            assert value in (15,16,17,20)
            self.memory[leave.DCRDR] = self.core[value]
        elif address == leave.DHCSR:
            assert value==0xa05f0001
            self.memory[address] = 0x10001
            if self.fault=='release': return -1
        else: raise AssertionError(hex(address))
        return 0


class PortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dll, cls.fn = core.bind(Path(os.environ['P34_CONFIRM_DLL']))
        proposed = []
        result = core.confirm(cls.fn, BEFORE, BOOT, IMAGE, lambda a,n: BEFORE[a:a+n],
                              lambda a,d: (proposed.append((a,d)) or -1))
        assert result['status'] == 0 and len(proposed) == 1
        cls.address, cls.target = proposed[0]

    def make(self, native=False):
        clock = Clock()
        slave = Slave(clock, BEFORE+b'R'*128)
        sdk = SDK(slave)
        words = Words(Dap(sdk), lambda *a,**k: None, reads=gpio.READS,
                      write_allowed=gpio.allowed_write, seconds=600, clock=clock,
                      guard=lambda fn,*a,**k: fn(*a))
        pins = gpio.Pins(words, sdk.original, lambda: True) if native else slave
        wire = EEPROM(pins, self.address, self.target, clock=clock, sleep=clock.sleep)
        return clock, slave, sdk, words, wire

    def settled(self, clock, wire, offset=0):
        result = wire.page(self.address+offset, self.target[offset:offset+8], 15)
        clock.sleep(.005)
        self.assertTrue(wire.ack(15))
        return result

    def test_wire_reads_both_records_with_repeated_start_and_last_nack(self):
        _, slave, _, _, wire = self.make()
        for address in (0,64):
            self.assertEqual(wire.read(address,64,15), BEFORE[address:address+64])
        self.assertEqual(slave.segments, [(0xa0,0),(0xa1,), (0xa0,64),(0xa1,)])
        self.assertEqual(slave.master_acks, ([0]*63+[1])*2)
        self.assertEqual((slave.starts, slave.stops), (4,2))
        self.assertEqual(slave.data, BEFORE+b'R'*128)

    def test_exact_eight_page_wire_through_original_confirmation_core(self):
        for native in (False, True):
            with self.subTest(native=native):
                clock, slave, _, words, wire = self.make(native)
                class ModelTransport:
                    host_only = True
                    read, page, ack = wire.read, wire.page, wire.ack
                port = PagePort(ModelTransport(), self.address, self.target, clock=clock, sleep=clock.sleep)
                result = core.confirm(self.fn, BEFORE, BOOT, IMAGE, port.read, port.write)
                self.assertEqual(result['status'], 1, result['callback_errors'])
                payloads = [s for s in slave.segments if len(s)>2]
                self.assertEqual(payloads, [tuple(bytes((0xa0,self.address+i))+self.target[i:i+8]) for i in range(0,64,8)])
                self.assertEqual(bytes(slave.data[self.address:self.address+64]), self.target)
                self.assertEqual(bytes(slave.data[64:128]), BEFORE[64:128])
                self.assertEqual(bytes(slave.data[128:]), b'R'*128)
                self.assertIsNone(words.error)

    def test_unknown_stop_and_every_delivered_edge_error_stop_all_later_io(self):
        _, normal, _, _, wire = self.make()
        wire.page(self.address,self.target[:8],15)
        count = len(normal.edges)
        for edge in range(1,count+1):
            clock, slave, _, _, wire = self.make()
            slave.fail_edge = edge
            with self.assertRaises(OSError): wire.page(self.address,self.target[:8],15)
            self.assertEqual(len(slave.edges), edge)
            first = wire.error
            clock.sleep(.01)
            for operation in (lambda: wire.read(0,64,15), lambda: wire.ack(15),
                              lambda: wire.page(self.address,self.target[:8],15)):
                with self.assertRaises(ValueError): operation()
            self.assertEqual(len(slave.edges), edge)
            self.assertEqual(wire.error, first)

    def test_all_page_byte_nacks_stop_and_settle_without_payload_retry(self):
        for byte in range(1,11):
            clock, slave, _, _, wire = self.make()
            slave.nack_byte = byte
            result = wire.page(self.address,self.target[:8],15)
            self.assertEqual(result['status'], -1)
            self.assertTrue(result['released'])
            count = len(slave.edges)
            clock.sleep(.005)
            self.assertTrue(wire.ack(15))
            self.assertIsInstance(wire.read(0,64,15), bytes)
            count = len(slave.edges)
            with self.assertRaises(ValueError): wire.page(self.address+8,self.target[8:16],15)
            self.assertEqual(len(slave.edges), count)

    def test_wait_busy_and_read_while_pending_do_not_send_new_payload(self):
        for operation in ('read', 'early_ack', 'second_page'):
            clock, slave, _, _, wire = self.make()
            wire.page(self.address,self.target[:8],15)
            count = len(slave.edges)
            fn = {'read': lambda: wire.read(0,64,15), 'early_ack': lambda: wire.ack(15),
                  'second_page': lambda: wire.page(self.address+8,self.target[8:16],15)}[operation]
            with self.assertRaises(ValueError): fn()
            self.assertEqual(len(slave.edges), count)
        clock, slave, _, _, wire = self.make()
        wire.page(self.address,self.target[:8],15)
        clock.sleep(.005)
        slave.busy_until = clock()+1
        self.assertFalse(wire.ack(15))
        self.assertIsNotNone(wire.pending_stop)
        count = len(slave.edges)
        clock.sleep(2)
        with self.assertRaises(ValueError): wire.ack(15)
        self.assertEqual(len(slave.edges), count)

    def test_wrong_pages_and_scope_reject_before_any_edges(self):
        for address,data in ((64,self.target[:8]),(1,self.target[:8]),(0,self.target[:7]),(0,b'X'*8)):
            _, slave, _, _, wire = self.make()
            with self.assertRaises(ValueError): wire.page(address,data,15)
            self.assertFalse(slave.edges)
        for address,size in ((128,64),(0,8),(0,128),(1,64)):
            _, slave, _, _, wire = self.make()
            with self.assertRaises(ValueError): wire.read(address,size,15)
            self.assertFalse(slave.edges)

    def test_native_scope_format_halt_and_sticky_errors_never_reach_gpio(self):
        for fault in ('running','reset','pause','csw','dp','config'):
            _, slave, sdk, _, wire = self.make(True)
            if fault=='running': sdk.memory[gpio.DHCSR] &= ~0x20000
            if fault=='reset': sdk.memory[gpio.DHCSR] |= 0x02000000
            if fault=='pause': sdk.memory[gpio.WDT_PAUSE] = 0
            if fault=='csw': sdk.csw ^= 1
            if fault=='dp': sdk.dp |= 0x20
            if fault=='config': sdk.memory[gpio.MODE] ^= 0x1000
            with self.assertRaises((ValueError,OSError)): wire.page(self.address,self.target[:8],15)
            self.assertFalse(slave.edges)
        for address,value in ((gpio.MODE,0),(gpio.SET,0x100),(0x08010000,0),(0xe000ed0c,0x05fa0004)):
            _, slave, sdk, words, _ = self.make(True)
            with self.assertRaises(ValueError): words.write32(address,value)
            self.assertFalse(sdk.calls)

    def test_deadline_and_clock_errors_latch_without_cleanup(self):
        for fault in ('expired','backward','sleep'):
            clock, slave, _, _, wire = self.make()
            if fault=='expired': clock.value = 601
            if fault=='backward': clock.value = -1
            if fault=='sleep': wire.sleep = lambda _: None
            with self.assertRaises(ValueError): wire.page(self.address,self.target[:8],15)
            count = len(slave.edges)
            with self.assertRaises(ValueError): wire.read(0,64,15)
            self.assertEqual(len(slave.edges), count)

    def test_native_delivered_gpio_drw_and_post_write_dp_failures_latch(self):
        for fault in ('delivered','dp-after'):
            clock, slave, sdk, words, wire = self.make(True)
            original = sdk.JLINKARM_CORESIGHT_WriteAPDPReg
            def write(index,ap,value):
                data = (index,ap) == (3,1)
                result = original(index,ap,value)
                if data:
                    if fault == 'delivered': return -1
                    sdk.dp |= 0x20
                return result
            sdk.JLINKARM_CORESIGHT_WriteAPDPReg = write
            with self.assertRaises(OSError): wire.page(self.address,self.target[:8],15)
            count = len(sdk.calls)
            clock.sleep(.01)
            for fn in (lambda: wire.ack(15),lambda: wire.read(0,64,15),lambda: words.write32(gpio.SET,0x80)):
                with self.assertRaises(ValueError): fn()
            self.assertEqual(len(sdk.calls),count)
            self.assertEqual(len(slave.edges),1)

    def flash_model(self,index=0,fault=None):
        clock = Clock()
        raw = (ROOT/'.cache/p34-finalized-reader-device1/readback.bin').read_bytes()+bytes(i%251 for i in range(964))
        sdk = FlashSDK(clock,raw,fault)
        port = flash.Sector(Dap(sdk),IMAGE,raw,index,lambda: True,lambda *a,**k: None,
                            seconds=300,clock=clock,sleep=clock.sleep,guard=lambda fn,*a,**k: fn(*a))
        return clock,sdk,port,raw

    def test_flash_both_bank_boundaries_and_preserved_nonff_suffix(self):
        for index in (0,223,224,302):
            with self.subTest(index=index):
                _,sdk,port,raw = self.flash_model(index)
                result = port.run()
                offset = index*2048
                desired = IMAGE+raw[IMAGE_SIZE:]
                self.assertEqual(sdk.flash[:offset],raw[:offset])
                self.assertEqual(sdk.flash[offset:offset+2048],desired[offset:offset+2048])
                self.assertEqual(sdk.flash[offset+2048:],raw[offset+2048:])
                self.assertFalse(result['reset_allowed'])
                self.assertEqual(result['bank'],1 if index<224 else 2)
                self.assertEqual([m for m in sdk.mutations if m[0]=='erase'],[('erase',APP_START+offset)])
                self.assertFalse(any(a in (flash.FLASH+8,flash.FLASH+0x1c) for a,_ in sdk.write_log))
                self.assertFalse(any(v & 0xc and a in (flash.FLASH+16,flash.FLASH+0x50) for a,v in sdk.write_log))
                count = len(sdk.calls)
                with self.assertRaises(ValueError): port.run()
                self.assertEqual(len(sdk.calls),count)

    def test_flash_fresh_odf_busy_protection_and_full_erase_oracles(self):
        for fault in ('stale','ignored','busy','protected','noerase'):
            with self.subTest(fault=fault):
                _,sdk,port,_ = self.flash_model(fault=fault)
                with self.assertRaises(ValueError): port.run()
                self.assertFalse(port.done)
                self.assertFalse(any(m[0]=='program' for m in sdk.mutations))
                if fault in ('ignored','busy','protected'):
                    self.assertEqual(sdk.write_log[-1],(port.ctrl,0x42))
                count = len(sdk.calls)
                with self.assertRaises(ValueError): port.words.write32(port.ctrl,0x80)
                self.assertEqual(len(sdk.calls),count)

    def test_flash_delivered_and_post_dp_errors_consume_operation_no_cleanup(self):
        for fault in ('delivered','dp-after'):
            _,sdk,port,_ = self.flash_model(fault=fault)
            with self.assertRaises(OSError): port.run()
            self.assertEqual(sdk.mutations,[('erase',APP_START)])
            self.assertEqual(sdk.write_log[-1],(port.ctrl,0x42))
            count = len(sdk.calls)
            with self.assertRaises(ValueError): port.run()
            self.assertEqual(len(sdk.calls),count)

    def test_flash_wrong_identity_preimage_clock_and_scope_fail_before_unlock(self):
        for fault in ('id','size','clock','preimage','initial-error','initial-mode',
                      'other-mode','other-unlocked','other-busy','epps0','epps1','fap','usd','slib'):
            _,sdk,port,_ = self.flash_model()
            if fault=='id': sdk.memory[flash.IDCODE] ^= 1
            if fault=='size': sdk.memory[flash.FSIZE] = 2048
            if fault=='clock': sdk.memory[flash.FLASH+0x60] = 0
            if fault=='preimage': sdk.flash[0] ^= 1
            if fault=='initial-error': sdk.memory[port.status_reg] = 4
            if fault=='initial-mode': sdk.memory[port.ctrl] = 0x81
            if fault=='other-mode': sdk.memory[flash.BANKS[1][2]] = 1
            if fault=='other-unlocked': sdk.memory[flash.BANKS[1][2]] = 0
            if fault=='other-busy': sdk.memory[flash.BANKS[1][1]] = 1
            if fault=='epps0': sdk.memory[flash.FLASH+0x20] ^= 0x10000
            if fault=='epps1': sdk.memory[flash.FLASH+0x2c] ^= 0x10
            if fault=='fap': sdk.memory[flash.FLASH+0x1c] = 2
            if fault=='usd': sdk.memory[flash.FLASH+0x1c] = 1
            if fault=='slib': sdk.memory[flash.FLASH+0xcc] = 8
            with self.assertRaises(ValueError): port.run()
            self.assertFalse(sdk.write_log)
        _,sdk,port,_ = self.flash_model()
        with self.assertRaises(ValueError): port.words.write32(APP_START,0)
        self.assertFalse(sdk.calls)

    def test_flash_direct_helper_misuse_cannot_expand_static_write_scope(self):
        for address,value in ((flash.FLASH+8,flash.KEY1),(flash.BANKS[1][0],flash.KEY1),
                              (flash.BANKS[1][2],0),(flash.BANKS[0][3],APP_START+2048),
                              (flash.BANKS[0][2],0x44),(flash.BANKS[0][2],0x100),
                              (0x08000000,0),(0x080A7800,0),(APP_START,0)):
            _,sdk,port,_ = self.flash_model()
            with self.assertRaises(ValueError): port.write(address,value)
            self.assertFalse(sdk.write_log)

    def exit_model(self,fault=None,admit=lambda phase: True):
        clock = Clock()
        sdk = ResetSDK(clock,fault)
        port = leave.Exit(Dap(sdk),BOOT,admit,lambda *a,**k:None,clock=clock,sleep=clock.sleep,
                          guard=lambda fn,*a,**k:fn(*a))
        return clock,sdk,port

    def test_fresh_boot_reset_catch_then_separate_release_no_old_context_restore(self):
        _,sdk,port = self.exit_model()
        result = port.reset_and_catch()
        self.assertEqual(result['result'],'FRESH_BOOT_CAUGHT')
        self.assertEqual(result['context']['pc'],0x080028b8)
        self.assertFalse(any(a==leave.DHCSR for a,_ in sdk.write_log))
        self.assertFalse(port.release()['runtime_health_verified'])
        self.assertEqual([v for a,v in sdk.write_log if a==leave.AIRCR],[0x05fa0304])
        self.assertEqual([v for a,v in sdk.write_log if a==leave.DHCSR],[0xa05f0001])
        self.assertFalse(any(a==leave.PAUSE for a,_ in sdk.write_log))
        self.assertEqual(sdk.memory[leave.DEMCR],0x1000000)
        count = len(sdk.calls)
        with self.assertRaises(ValueError): port.release()
        self.assertEqual(len(sdk.calls),count)

    def test_uncertain_reset_delivery_is_observed_but_never_replayed_or_released(self):
        for fault in ('delivered','undelivered'):
            _,sdk,port = self.exit_model(fault)
            if fault=='delivered':
                self.assertEqual(port.reset_and_catch()['result'],'RESET_CAUGHT_DELIVERY_UNCERTAIN')
            else:
                with self.assertRaises(ValueError): port.reset_and_catch()
            count = len(sdk.calls)
            with self.assertRaises(ValueError): port.reset_and_catch()
            with self.assertRaises(ValueError): port.release()
            self.assertEqual(len(sdk.calls),count)
            self.assertEqual(len([a for a,v in sdk.write_log if a==leave.AIRCR]),1)
            self.assertFalse(any(a==leave.DHCSR for a,v in sdk.write_log))
            after_reset = sdk.write_log[next(i for i,(a,v) in enumerate(sdk.write_log) if a==leave.AIRCR)+1:]
            self.assertTrue(all(a==leave.DCRSR and v in (15,16,17,20) for a,v in after_reset))

    def test_reset_catch_identity_and_pause_failures_never_release(self):
        for fault in ('stale','arm','catch','pc','alias','pause'):
            _,sdk,port = self.exit_model(fault)
            if fault=='stale': sdk.memory[leave.DFSR] |= 8
            with self.assertRaises(ValueError): port.reset_and_catch()
            self.assertFalse(any(a==leave.DHCSR for a,_ in sdk.write_log))
        _,sdk,port = self.exit_model()
        sdk.memory[leave.DHCSR] |= 0x02000000
        with self.assertRaises(ValueError): port.reset_and_catch()
        self.assertFalse(sdk.write_log)

    def test_reset_admission_and_unknown_release_do_not_mutate_again(self):
        _,sdk,port = self.exit_model(admit=lambda phase:False)
        with self.assertRaises(ValueError): port.reset_and_catch()
        self.assertFalse(sdk.calls)
        _,sdk,port = self.exit_model('release')
        port.reset_and_catch()
        with self.assertRaises(OSError): port.release()
        count = len(sdk.calls)
        with self.assertRaises(ValueError): port.release()
        self.assertEqual(len(sdk.calls),count)
        self.assertEqual(sdk.memory[leave.DHCSR],0x10001)

    def test_pure_c_draft_and_actual_wire_observer_use_original_before_pair(self):
        clock,slave,_,_,wire = self.make()
        plan = confirm_io.draft(self.fn,BEFORE*2,BOOT,IMAGE)
        transaction = confirm_io.Transaction(self.fn,plan,wire,clock=clock,sleep=clock.sleep)
        result = transaction.run()
        self.assertEqual(result['result'],'EEPROM_BYTES_CONFIRMED',result['error'])
        self.assertFalse(result['reset_qualified'])
        self.assertIsNone(result['error'])
        self.assertTrue(confirm_io.observe(self.fn,plan,result['after']))
        before = len(slave.edges)
        with self.assertRaises(ValueError): transaction.run()
        self.assertEqual(len(slave.edges),before)

    def test_confirmation_prewrite_drift_or_unknown_stop_forbids_payload_or_observation(self):
        for fault in ('drift','edge'):
            clock,slave,_,_,wire = self.make()
            plan = confirm_io.draft(self.fn,BEFORE*2,BOOT,IMAGE)
            if fault=='drift': slave.data[80] ^= 1
            else: slave.fail_edge=1
            result = confirm_io.Transaction(self.fn,plan,wire,clock=clock,sleep=clock.sleep).run()
            self.assertEqual(result['result'],'EEPROM_PREWRITE_REJECTED')
            self.assertEqual(result['pages'],0)
            self.assertFalse(any(len(s)>2 for s in slave.segments))

    def test_confirmation_oracle_rejects_changed_slot_pair_or_wrong_images(self):
        plan = confirm_io.draft(self.fn,BEFORE*2,BOOT,IMAGE)
        for data in (plan.target,plan.target*2+b'X',plan.target+BEFORE,
                     (plan.target[:80]+bytes([plan.target[80]^1])+plan.target[81:])*2):
            self.assertFalse(confirm_io.observe(self.fn,plan,data))
        with self.assertRaises(ValueError): confirm_io.draft(self.fn,BEFORE+plan.target,BOOT,IMAGE)
        with self.assertRaises(ValueError): confirm_io.draft(self.fn,BEFORE*2,BOOT,IMAGE[:-1])


if __name__ == '__main__': unittest.main()
