"""Exact R2-A single-sector AP adapter; no connect, reset, option or mass erase."""
import time

from .flash_plan import APP_START, IMAGE_SIZE, SECTOR_SIZE, geometry
from .native_io import Words

FLASH = 0x40023c00
KEY1, KEY2 = 0x45670123, 0xcdef89ab
DHCSR, PAUSE, IDCODE, FSIZE = 0xe000edf0, 0xe0042008, 0xe0042000, 0x1ffff7e0
CLOCK = {0x40023800:50368131, 0x40023804:70145, 0x40023808:36874,
         0x400238a0:28672, 0x400238a4:13}
CONFIG = (FLASH, FLASH+0x58, FLASH+0x60)
PROTECTION = (FLASH+0x1c,FLASH+0x20,FLASH+0x2c,FLASH+0xcc)
BANKS = ((FLASH+4,FLASH+12,FLASH+16,FLASH+20),
         (FLASH+0x44,FLASH+0x4c,FLASH+0x50,FLASH+0x54))


class Sector:
    def __init__(self, dap, image, preimage, index, owner, emit, *, seconds=300,
                 clock=time.monotonic, sleep=time.sleep, guard=None):
        extent = geometry(image)
        if type(preimage) is not bytes or len(preimage) != extent.erase_end-APP_START:
            raise ValueError('full physical-envelope preimage required; no implicit FF suffix')
        if type(index) is not int or not 0 <= index < len(extent.sectors):
            raise ValueError('sector index outside exact R2 envelope')
        self.address, bank = extent.sectors[index]
        self.key, self.status_reg, self.ctrl, self.addr = BANKS[bank-1]
        offset = self.address-APP_START
        self.before = preimage[offset:offset+SECTOR_SIZE]
        desired = image+preimage[IMAGE_SIZE:]
        self.after = desired[offset:offset+SECTOR_SIZE]
        self.bank = bank
        self.owner, self.emit, self.sleep = owner, emit, sleep
        self.expected_write = None
        reads = {DHCSR,PAUSE,IDCODE,FSIZE,*CLOCK,*CONFIG,*PROTECTION,*range(self.address,self.address+SECTOR_SIZE,4)}
        reads.update(a for _,s,c,_ in BANKS for a in (s,c))
        kwargs = {} if guard is None else dict(guard=guard)
        self.words = Words(dap,emit,reads=reads,write_allowed=self.allowed,seconds=seconds,clock=clock,**kwargs)
        self.config = None
        self.used = False
        self.error = None
        self.done = False
        self.programmed_words = 0
        self.erased = False

    def allowed(self, address, value):
        if self.expected_write != (address,value) or not self.used or self.done or self.error is not None:
            return False
        if address == self.key: return value in (KEY1,KEY2)
        if address == self.status_reg: return value == 0x34
        if address == self.ctrl: return value in (0,1,2,0x42,0x80)
        if address == self.addr: return value == self.address
        if self.erased and address % 4 == 0 and self.address <= address < self.address+SECTOR_SIZE:
            offset = address-self.address
            return value == int.from_bytes(self.after[offset:offset+4],'little')
        return False

    def check(self, *, config=False):
        if self.error is not None or self.owner() is not True:
            raise ValueError('Flash owner/failure gate')
        if self.words.read32(DHCSR) & 0x020a0000 != 0x20000 or not self.words.read32(PAUSE) & 0x1000:
            raise ValueError('Flash lost halt/watchdog pause/reset epoch')
        if config:
            if any(self.words.read32(a) != v for a,v in CLOCK.items()):
                raise ValueError('qualified 288MHz clock profile changed')
            values = {a:self.words.read32(a) for a in (*CONFIG,*PROTECTION)}
            div = values[FLASH+0x60]
            if div & 3 != (div >> 4) & 3 or (div >> 4) & 3 not in (1,2):
                raise ValueError('Flash clock not established at <=104MHz')
            if (values[FLASH+0x1c] & 3 or values[FLASH+0x20] & 0xffff0000 != 0xffff0000 or
                    values[FLASH+0x2c] & 0x1f != 0x1f or values[FLASH+0xcc] & 8):
                raise ValueError('Flash USD/access protection/SLIB not qualified')
            if self.config is None:
                self.config = values
            elif values != self.config:
                raise ValueError('Flash PSR/CONTR/DIVR changed')
        self.words.check()

    def write(self, address, value):
        self.check()
        self.expected_write = (address,value)
        try:
            self.words.write32(address,value)
        finally:
            self.expected_write = None

    def read_sector(self):
        self.check()
        raw = b''.join(self.words.read_bytes(self.address+i,1024) for i in (0,1024))
        self.check()
        return raw

    def unlocked(self):
        if self.words.read32(self.ctrl) != 0x80:
            raise ValueError('unexplained initial Flash mode/lock')
        for _,status,_,_ in BANKS:
            if self.words.read32(status) & 0x15:
                raise ValueError('unexplained initial Flash busy/error')
        self.write(self.key,KEY1)
        self.write(self.key,KEY2)
        if self.words.read32(self.ctrl) != 0:
            raise ValueError('normal Flash controller unlock failed')

    def fresh_flags(self):
        if self.words.read32(self.status_reg) & 0x15:
            raise ValueError('Flash error/busy before operation; no clear')
        self.write(self.status_reg,0x34)
        if self.words.read32(self.status_reg) & 0x35:
            raise ValueError('stale completion not cleared')

    def wait(self, seconds):
        end = min(self.words.budget.end,self.words.budget.now()+seconds)
        while True:
            self.check()
            status = self.words.read32(self.status_reg)
            if self.words.budget.now() >= end:
                raise ValueError('Flash completion unknown at operational deadline')
            if status & 0x14:
                raise ValueError('Flash program/protection error')
            if status & 0x21 == 0x20:
                return
            self.sleep(max(0,min(.001,end-self.words.budget.now())))

    def lock(self):
        if self.words.read32(self.status_reg) & 0x15:
            raise ValueError('cannot clear mode/relock while busy or errored')
        self.write(self.ctrl,0)
        if self.words.read32(self.ctrl) != 0:
            raise ValueError('Flash mode did not clear')
        self.write(self.ctrl,0x80)
        if self.words.read32(self.ctrl) != 0x80:
            raise ValueError('Flash relock not established')

    def run(self):
        try:
            if self.used:
                raise ValueError('sector operation cannot be replayed')
            self.used = True
            self.check(config=True)
            if any(self.words.read32(c) != 0x80 or self.words.read32(s) & 0x15 for _,s,c,_ in BANKS):
                raise ValueError('both banks must start idle/locked without error')
            if self.words.read32(IDCODE) != 0x70083347 or self.words.read32(FSIZE) & 0xffff != 1024:
                raise ValueError('RGT7 identity/capacity mismatch')
            if self.read_sector() != self.before:
                raise ValueError('sector differs from physical preimage')
            self.unlocked()
            self.fresh_flags()
            self.write(self.ctrl,2)
            self.write(self.addr,self.address)
            self.write(self.ctrl,0x42)
            self.wait(3)
            self.lock()
            if self.read_sector() != b'\xff'*SECTOR_SIZE:
                raise ValueError('erase did not produce complete FF sector')
            self.erased = True
            nonblank = [(self.address+i,int.from_bytes(self.after[i:i+4],'little'))
                        for i in range(0,SECTOR_SIZE,4) if self.after[i:i+4] != b'\xff'*4]
            if nonblank:
                self.unlocked()
                self.write(self.ctrl,1)
                for address,value in nonblank:
                    self.fresh_flags()
                    self.write(address,value)
                    self.wait(.5)
                    if self.words.read32(address) != value:
                        raise ValueError('program word readback mismatch')
                    self.programmed_words += 1
                self.lock()
            if self.read_sector() != self.after:
                raise ValueError('complete sector including collateral differs')
            self.check(config=True)
            if any(self.words.read32(c) != 0x80 or self.words.read32(s) & 0x15 for _,s,c,_ in BANKS):
                raise ValueError('final two-bank status/lock differs')
            self.emit('flash-sector-verified',address=self.address,bank=self.bank,programmed_words=self.programmed_words)
            self.words.check()
            self.done = True
            return dict(address=self.address,bank=self.bank,complete=True,reset_allowed=False,
                        programmed_words=self.programmed_words)
        except BaseException as error:
            if self.error is None:
                self.error = type(error).__name__+': '+str(error)
            if self.words.error is None:
                self.words.error = self.error
            raise
