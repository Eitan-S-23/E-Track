"""Read-qualified bank1 mode clear/relock only; no erase/program/flag clear."""
import time
from .native_io import Words, guarded
from . import flash_port as flash, boot16

READS = {flash.DHCSR, flash.PAUSE, flash.IDCODE, flash.FSIZE, *flash.CLOCK,
         *flash.CONFIG, *flash.PROTECTION,
         *(address for bank in flash.BANKS for address in bank[1:])}


class LockOnly:
    def __init__(self, dap, owner, emit, *, clock=time.monotonic, guard=guarded):
        self.owner, self.expected, self.error = owner, None, None
        self.pause = None
        self.used = self.done = False
        def native(function, *args, seconds):
            if self.owner() is not True: raise ValueError('settlement native owner lost')
            result = guard(function, *args, seconds=seconds)
            if self.owner() is not True: raise ValueError('settlement native owner lost')
            return result
        self.words = Words(dap, emit, reads=READS, write_allowed=self.allowed,
                           seconds=60, clock=clock, guard=native)

    def allowed(self, address, value):
        return (self.used and not self.done and self.error is None and self.owner() is True
                and self.expected == (address, value)
                and address == flash.BANKS[0][2] and value in (0, 0x80))

    def edge(self):
        if self.owner() is not True: raise ValueError('settlement owner lost')
        if self.words.read32(flash.DHCSR) & 0x020affff != 0x20003:
            raise ValueError('settlement retained halt required')
        pause = self.words.read32(flash.PAUSE)
        if not pause & 0x1000 or self.pause is not None and pause != self.pause:
            raise ValueError('settlement complete pause value changed')
        if self.words.read32(flash.DHCSR) & 0x020affff != 0x20003 or self.owner() is not True:
            raise ValueError('settlement trailing halt/owner lost')
        if self.pause is None: self.pause = pause
        return pause

    def snapshot(self):
        if self.error is not None or self.owner() is not True: raise ValueError('settlement owner lost')
        self.words.check()
        pause = self.edge()
        values = {address: self.words.read32(address) for address in READS if address not in (flash.DHCSR, flash.PAUSE)}
        if values[flash.IDCODE] != 0x70083347 or values[flash.FSIZE] & 0xffff != 1024:
            raise ValueError('settlement silicon identity differs')
        if any(values[a] != value for a, value in flash.CLOCK.items()): raise ValueError('settlement clock differs')
        div = values[flash.FLASH+0x60]
        if div & 3 != (div >> 4) & 3 or (div >> 4) & 3 not in (1, 2):
            raise ValueError('settlement Flash clock invalid')
        if (values[flash.FLASH+0x1c] & 3 or values[flash.FLASH+0x20] & 0xffff0000 != 0xffff0000 or
                values[flash.FLASH+0x2c] & 0x1f != 0x1f or values[flash.FLASH+0xcc] & 8):
            raise ValueError('settlement protection changed')
        if any(values[s] & 0x15 for _, s, _, _ in flash.BANKS):
            raise ValueError('busy/error Flash cannot be settled by writes')
        if values[flash.BANKS[1][2]] != 0x80: raise ValueError('other bank must remain locked')
        _, status, ctrl, address = flash.BANKS[0]
        if values[ctrl] not in (0, 1, 2, 0x80): raise ValueError('unknown bank1 mode')
        if values[ctrl] != 0x80:
            if values[status] != 0x20 or not boot16.START <= values[address] < boot16.END or values[address] % 2048:
                raise ValueError('unfinished mode must be settled on an authorized Boot sector')
        if self.edge() != pause: raise ValueError('settlement pause drift within snapshot')
        values[flash.PAUSE] = pause
        return values

    def run(self):
        if self.used: raise ValueError('lock-only capability consumed')
        self.used = True
        try:
            before = self.snapshot()
            if self.snapshot() != before: raise ValueError('controller not stable before mode settlement')
            control = flash.BANKS[0][2]
            stores = [] if before[control] == 0x80 else [(control, 0), (control, 0x80)]
            expected = dict(before)
            for address, value in stores:
                if self.snapshot() != expected: raise ValueError('settlement state changed before store')
                self.expected = (address, value)
                try: self.words.write32(address, value)
                finally: self.expected = None
                if self.words.read32(address) != value: raise ValueError('mode/lock readback differs')
                expected[address] = value
            after = self.snapshot()
            if after != expected: raise ValueError('settlement changed other controller state')
            self.done = True
            return dict(result='BOOT16_FLASH_IDLE_LOCKED', stores=stores, before=before, after=after)
        except BaseException as error:
            self.error = type(error).__name__+': '+str(error)
            raise
