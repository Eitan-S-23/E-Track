"""PB6/PB7-only open-drain edges on an already halted, exclusively owned target."""
from .native_io import Words

DHCSR, WDT_PAUSE = 0xe000edf0, 0xe0042008
MODE, TYPE, DRIVE, PULL, INPUT, OUTPUT, SET, CLEAR = (
    0x40020400, 0x40020404, 0x40020408, 0x4002040c,
    0x40020410, 0x40020414, 0x40020418, 0x40020428)
READS = (DHCSR, WDT_PAUSE, MODE, TYPE, DRIVE, PULL, INPUT, OUTPUT)


def allowed_write(address, value):
    return address in (SET, CLEAR) and value in (0x40, 0x80)


class Pins:
    def __init__(self, words, original, owner):
        if not isinstance(words, Words):
            raise ValueError('bounded native word port required')
        if set(original) != {MODE, TYPE, DRIVE, PULL, OUTPUT}:
            raise ValueError('exact original pin configuration required')
        if original[MODE] & 0xf000 != 0x5000 or original[TYPE] & 0xc0 != 0xc0 or original[OUTPUT] & 0xc0 != 0xc0:
            raise ValueError('released PB6/PB7 open-drain profile required')
        self.words, self.original, self.owner = words, dict(original), owner
        self.error = None
        self.edges = 0

    def check(self, *, config=False):
        if self.error is not None:
            raise ValueError('GPIO port failure latched')
        self.words.check()
        if self.owner() is not True:
            raise ValueError('exclusive stopped owner lost')
        status = self.words.read32(DHCSR)
        if status & 0x020a0000 != 0x00020000 or not self.words.read32(WDT_PAUSE) & 0x1000:
            raise ValueError('halt/reset/watchdog pause changed')
        if config:
            for address in (MODE, TYPE, DRIVE, PULL):
                if self.words.read32(address) != self.original[address]:
                    raise ValueError('GPIO configuration changed')
        self.words.check()

    def verify_idle(self):
        try:
            self.check(config=True)
            if self.words.read32(OUTPUT) != self.original[OUTPUT] or self.words.read32(INPUT) & 0xc0 != 0xc0:
                raise ValueError('EEPROM bus not released/high')
            self.words.check()
        except BaseException as error:
            self.fail(error)

    def fail(self, error):
        if self.error is None:
            self.error = type(error).__name__+': '+str(error)
        if self.words.error is None:
            self.words.error = self.error
        raise error

    def set(self, pin, high):
        try:
            if type(pin) is not int or pin not in (6, 7) or type(high) is not int or high not in (0, 1):
                raise ValueError('only PB6/PB7 binary levels allowed')
            self.check(config=self.edges % 128 == 0)
            before = self.words.read32(OUTPUT)
            if before & ~0xc0 != self.original[OUTPUT] & ~0xc0:
                raise ValueError('other GPIO output changed')
            transition = pin == 7 and bool(before & 0x40) and bool(before & 0x80) != bool(high)
            if transition and self.words.read32(INPUT) & 0xc0 != before & 0xc0:
                raise ValueError('START/STOP physical pre-level mismatch')
            self.words.write32(SET if high else CLEAR, 1 << pin)
            self.edges += 1
            expected = before | (1 << pin) if high else before & ~(1 << pin)
            if self.words.read32(OUTPUT) != expected:
                raise ValueError('GPIO latch readback mismatch')
            if pin == 6 or transition:
                physical = self.words.read32(INPUT)
                if bool(physical & (1 << pin)) != bool(high) or transition and not physical & 0x40:
                    raise ValueError('GPIO physical edge not established')
            self.check()
        except BaseException as error:
            self.fail(error)

    def read(self, pin):
        try:
            if type(pin) is not int or pin not in (6, 7):
                raise ValueError('only PB6/PB7 inputs allowed')
            self.check()
            value = int(bool(self.words.read32(INPUT) & (1 << pin)))
            self.words.check()
            return value
        except BaseException as error:
            self.fail(error)
