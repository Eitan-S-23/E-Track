"""Host callbacks for the existing fixed A/B/A/B C reader. No NVM write API."""
import ctypes
import struct
import time

from .probe import require
from .report import _active, _valid

PIN_FN = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int)
READ_FN = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p)


class Bus(ctypes.Structure):
    _fields_ = [("ctx", ctypes.c_void_p), ("sda", PIN_FN), ("scl", PIN_FN),
                ("read_sda", READ_FN), ("read_scl", READ_FN), ("pause", READ_FN)]


class Capture(ctypes.Structure):
    _fields_ = [("raw", ctypes.c_ubyte*256), ("completed", ctypes.c_uint),
                ("active", ctypes.c_int), ("value", ctypes.c_ubyte*64), ("stable", ctypes.c_int)]


class Guard:
    def __init__(self, pins, *, seconds=300, clock=time.monotonic, sleep=time.sleep):
        require(type(seconds) in (int,float) and 0 < seconds <= 300, "finite I2C capture deadline")
        self.pins, self.clock, self.sleep, self.seconds = pins, clock, sleep, seconds
        self.started, self.error, self.calls = clock(), None, 0
        self.refs = [PIN_FN(lambda ctx, high:self.invoke(lambda:self.pins.set(7,high))),
                     PIN_FN(lambda ctx, high:self.invoke(lambda:self.pins.set(6,high))),
                     READ_FN(lambda ctx:self.invoke(lambda:self.pins.read(7),0)),
                     READ_FN(lambda ctx:self.invoke(lambda:self.pins.read(6),0)),
                     READ_FN(lambda ctx:self.invoke(self.pause,-1))]
        self.bus = Bus(None,*self.refs)

    def check(self):
        require(0 <= self.clock()-self.started < self.seconds,"I2C deadline expired/backward clock")

    def invoke(self, operation, failed=None):
        # Never let Python exceptions escape a ctypes callback. After a fault,
        # even the C reader's STOP cleanup callbacks cannot change pins.
        if self.error is not None: return failed
        try:
            self.check(); self.calls += 1
            value=operation(); self.check()
            return value
        except BaseException as error:
            self.error=type(error).__name__+": "+str(error)
            return failed

    def pause(self):
        start=self.clock()
        while self.clock()-start < .00001:
            self.check(); self.sleep(.00001)
        return 0


def bind(library):
    require(ctypes.sizeof(Capture)==332,"host BCB ABI mismatch")
    function=library.rr_bcb_capture
    function.argtypes=[ctypes.POINTER(Bus),ctypes.POINTER(Capture)]
    function.restype=ctypes.c_int
    return function


def capture(function,pins,**kwargs):
    guard=Guard(pins,**kwargs); out=Capture()
    result=function(ctypes.byref(guard.bus),ctypes.byref(out))
    try:
        guard.check()
    except BaseException as error:
        if guard.error is None: guard.error=type(error).__name__+": "+str(error)
    raw=bytes(out.raw)
    complete=(guard.error is None and result==0 and out.completed==4 and out.stable==1 and
              raw[:128]==raw[128:] and out.active==_active(raw[:64],raw[64:128]))
    selected=raw[(out.active-1)*64:out.active*64] if complete and out.active in (1,2) else None
    record=None if selected is None else dict(state=selected[5],boot_try=selected[6],copy_phase=selected[7],
        seq=struct.unpack_from("<H",selected,8)[0],resume_block=struct.unpack_from("<H",selected,10)[0],
        cand_addr=struct.unpack_from("<I",selected,12)[0],cand_len=struct.unpack_from("<I",selected,16)[0],
        cand_crc32=struct.unpack_from("<I",selected,20)[0],cand_vcode=struct.unpack_from("<I",selected,24)[0],
        cur_vcode=struct.unpack_from("<I",selected,28)[0],backup_len=struct.unpack_from("<I",selected,32)[0],
        backup_crc32=struct.unpack_from("<I",selected,36)[0],backup_vcode=struct.unpack_from("<I",selected,40)[0])
    return dict(result="HOST_BCB_CAPTURED" if complete else "FAILED",raw_hex=raw.hex(),
                native_result=result,completed=out.completed,stable=out.stable,active=out.active,
                first_pair_valid=[_valid(raw[:64]),_valid(raw[64:128])],selected=record,
                callback_error=guard.error,callbacks=guard.calls,elapsed_seconds=guard.clock()-guard.started,
                bcb_admitted=complete and out.active in (1,2),device_execute_ready=False,
                eeprom_payload_bytes_written=0,internal_address_pointer_changed=True if complete else None)


class Pins:
    def __init__(self,control,raw,emit):
        require(raw["gpiob_mode"] & 0xf000 == 0x5000 and raw["gpiob_type"] & 0xc0 == 0xc0 and
                raw["gpiob_output"] & 0xc0 == 0xc0 and raw["gpiob_input"] & 0xc0 == 0xc0 and
                raw["crm_ahben1"] & 2 and raw["debug_apb1_frz"] & 0x1000,"qualified released OD bus required")
        enabled=[n for n,v in raw.items() if (n.startswith("dma") or n.startswith("edma")) and v&1]
        require(set(enabled)=={"dma1_3","dma2_4"} and raw["display_dma_count"]==raw["sd_dma_count"]==0 and
                raw["display_dma_peripheral"]==0x4001300c and raw["sd_dma_peripheral"]==0x50061080,
                "DMA ownership differs from qualified halted profile")
        self.control,self.dap,self.emit=control,control.dap,emit
        self.original={0x40020400:raw["gpiob_mode"],0x40020404:raw["gpiob_type"],
                       0x40020408:raw["gpiob_drive"],0x4002040c:raw["gpiob_pull"]}
        self.original_output=raw["gpiob_output"]
        self.edges,self.samples,self.clock_edges=0,0,0

    def expected_clock_data(self):
        require(self.clock_edges<2420,"fixed I2C clock budget exceeded")
        transaction,edge=divmod(self.clock_edges,605)
        for start,value in ((0,0xa0),(9,0x40 if transaction%2 else 0),(19,0xa1)):
            if start<=edge<start+8:
                bit=(value>>(7-(edge-start)))&1
                return bit,bit
        if edge==18: return 1,1  # Released SDA before repeated START.
        if edge==604: return 0,0  # STOP setup.
        if edge>=28 and (edge-28)%9==8:
            bit=int((edge-28)//9==63)
            return bit,bit
        return 1,None  # EEPROM owns ACK/data; the master must release SDA.

    def owner(self):
        status=self.control.status()
        require(status["halted"] and not status["reset_sticky"] and not status["lockup"],"I2C lost retained halt")

    def verify(self,*,idle):
        self.owner()
        require(self.control._read32(0xe0042008)&0x1000,"I2C lost WDT halt pause")
        require(all(self.control._read32(a)==v for a,v in self.original.items()),"I2C pin configuration changed")
        if idle:
            require(self.control._read32(0x40020414)==self.original_output and
                    self.control._read32(0x40020410)&0xc0==0xc0,"I2C bus not released/high")

    def set(self,pin,high):
        require(type(pin) is int and pin in (6,7) and type(high) is int and high in (0,1),"fixed I2C pin scope")
        self.owner()
        if self.edges%128==0: self.verify(idle=False)
        before=self.control._read32(0x40020414)
        rising=pin==6 and high==1 and not before&0x40
        data_expect=None
        if rising:
            drive,data_expect=self.expected_clock_data()
            physical=self.control._read32(0x40020410)
            require(not physical&0x40 and bool(before&0x80)==bool(drive),"unqualified SCL rise/master data")
            if data_expect is not None:
                require(bool(physical&0x80)==bool(data_expect),"master SDA bit not physically present")
        if pin==7 and before&0x40:
            physical=self.control._read32(0x40020410)
            require(physical&0xc0==before&0xc0,"START/STOP physical pre-level mismatch")
            if bool(before&0x80)!=bool(high):
                phase=self.clock_edges%605
                require((high==0 and phase in (0,19) and self.clock_edges<2420) or
                        (high==1 and phase==0 and self.clock_edges>0),"unexpected START/STOP position")
        address=0x40020418 if high else 0x40020428
        value=1<<pin
        self.edges+=1
        self.emit("i2c-edge-attempt",edge=self.edges,pin=pin,high=high,address=address,value=value)
        rc=self.dap._call("JLINKARM_CORESIGHT_WriteAPDPReg",1,1,address)
        require(type(rc) is int and rc>=0,"I2C GPIO TAR failed")
        rc=self.dap._call("JLINKARM_CORESIGHT_WriteAPDPReg",3,1,value)
        require(type(rc) is int and rc>=0,"I2C GPIO write failed")
        self.dap._power_ready()
        output=self.control._read32(0x40020414)
        require(bool(output&value)==bool(high),"I2C GPIO latch readback mismatch")
        if pin==6 and high==0:
            require(not self.control._read32(0x40020410)&value,"SCL did not fall")
        if rising:
            physical=self.control._read32(0x40020410)
            require(physical&0x40,"SCL rise not physically present")
            if data_expect is not None:
                require(bool(physical&0x80)==bool(data_expect),"master SDA bit changed at SCL rise")
            self.clock_edges+=1
        if pin==7 and before&0x40:
            physical=self.control._read32(0x40020410)
            require(physical&0x40 and bool(physical&0x80)==bool(high),"START/STOP physical post-level mismatch")
        self.emit("i2c-edge-verified",edge=self.edges,pin=pin,high=high)

    def read(self,pin):
        require(pin in (6,7),"fixed I2C input scope")
        self.owner()
        value=int(bool(self.control._read32(0x40020410)&(1<<pin)))
        if pin==6:
            require(value==1,"released SCL not physically high")
        if pin==7:
            if self.samples%515<3:
                require(value==0,"EEPROM NACK; retain without cleanup")
            self.samples+=1
            if self.samples%515==0:
                self.emit("i2c-record-data-sampled",records=self.samples//515,stop_still_required=True)
        return value
