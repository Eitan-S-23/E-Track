"""Exact-record I2C page/read protocol. Injected pins; no device entry or reset."""
import math
import time

from .native_io import Budget

PAGE_SECONDS = .005


class EEPROM:
    def __init__(self, pins, address, record, *, seconds=600, clock=time.monotonic, sleep=time.sleep, emit=lambda *a, **k: None):
        if type(address) is not int or address not in (0, 64) or type(record) is not bytes or len(record) != 64:
            raise ValueError('one exact inactive 64B record required')
        self.pins, self.address, self.record = pins, address, record
        self.budget, self.sleep, self.emit = Budget(seconds, clock), sleep, emit
        self.end = self.budget.end
        self.error = None
        self.page_index = 0
        self.pending_stop = None
        self.write_failed = False
        self.ack_attempted = False

    def now(self):
        if self.error is not None:
            raise ValueError('EEPROM wire failure latched')
        now = self.budget.now()
        if now >= self.end:
            raise ValueError('EEPROM operation deadline exhausted')
        return now

    def begin(self, seconds):
        now = self.budget.now()
        if self.error is not None or type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 300:
            raise ValueError('invalid EEPROM operation/timeout')
        self.end = min(self.budget.end, now+seconds)
        self.now()
        self.pins.verify_idle()
        self.now()

    def call(self, fn, *args):
        self.now()
        value = fn(*args)
        self.now()
        return value

    def pause(self):
        start = self.now()
        self.sleep(.00001)
        if self.now() < start+.00001:
            raise ValueError('I2C minimum wait returned early')

    def set(self, pin, high):
        self.call(self.pins.set, pin, high)
        self.pause()

    def sample(self, pin):
        value = self.call(self.pins.read, pin)
        if type(value) is not int or value not in (0, 1):
            raise ValueError('nonbinary GPIO sample')
        return value

    def start(self):
        if self.sample(6) != 1 or self.sample(7) != 1:
            raise ValueError('START requires released/high bus')
        self.set(7, 0)
        self.set(6, 0)

    def stop(self):
        self.set(6, 0)
        self.set(7, 0)
        self.set(6, 1)
        if self.sample(6) != 1:
            raise ValueError('SCL not high before STOP')
        self.set(7, 1)
        self.call(self.pins.verify_idle)
        return self.now()

    def bit(self, value):
        self.set(7, value)
        if self.sample(7) != value:
            raise ValueError('master SDA bit not present')
        self.set(6, 1)
        if self.sample(6) != 1 or self.sample(7) != value:
            raise ValueError('master bit changed on SCL rise')
        self.set(6, 0)

    def send(self, byte):
        for shift in range(7, -1, -1):
            self.bit((byte >> shift) & 1)
        self.set(7, 1)
        self.set(6, 1)
        if self.sample(6) != 1:
            raise ValueError('ACK SCL held low')
        ack = self.sample(7) == 0
        self.set(6, 0)
        return ack

    def receive(self, last):
        self.set(7, 1)
        value = 0
        for _ in range(8):
            self.set(6, 1)
            if self.sample(6) != 1:
                raise ValueError('read SCL held low')
            value = (value << 1) | self.sample(7)
            self.set(6, 0)
        self.bit(int(last))
        self.set(7, 1)
        return value

    def fail(self, error):
        if self.error is None:
            self.error = type(error).__name__+': '+str(error)
        raise error

    def page(self, address, data, seconds):
        try:
            if self.pending_stop is not None or self.write_failed or self.page_index >= 8:
                raise ValueError('unsettled page, prior write failure or replay')
            offset = self.page_index*8
            if type(address) is not int or address != self.address+offset or type(data) is not bytes or data != self.record[offset:offset+8]:
                raise ValueError('page differs from exact ordered record')
            self.begin(seconds)
            self.page_index += 1
            self.ack_attempted = False
            self.emit('eeprom-page-start', address=address, data_hex=data.hex())
            self.now()
            self.start()
            good = True
            for value in bytes((0xa0, address))+data:
                if not self.send(value):
                    good = False
                    break
            stop = self.stop()
            self.pending_stop = stop
            self.write_failed = not good
            result = dict(status=0 if good else -1, released=True, stop_upper=stop)
            self.emit('eeprom-page-stop', address=address, **result)
            self.now()
            return result
        except BaseException as error:
            self.fail(error)

    def ack(self, seconds):
        try:
            if self.ack_attempted or self.pending_stop is None or self.budget.now() < self.pending_stop+PAGE_SECONDS:
                raise ValueError('ready probe before known write-cycle wait')
            self.begin(seconds)
            self.ack_attempted = True
            self.start()
            good = self.send(0xa0)
            self.stop()
            if good:
                self.pending_stop = None
            self.now()
            return good
        except BaseException as error:
            self.fail(error)

    def read(self, address, size, seconds):
        try:
            if self.pending_stop is not None or type(address) is not int or type(size) is not int:
                raise ValueError('unsettled EEPROM or invalid read')
            pair_read = size == 64 and address in (0, 64)
            page_read = size == 8 and self.page_index and address == self.address+(self.page_index-1)*8
            if not pair_read and not page_read:
                raise ValueError('read outside BCB pair/current page')
            self.begin(seconds)
            self.start()
            if not self.send(0xa0) or not self.send(address):
                self.stop()
                raise ValueError('EEPROM read address NACK')
            self.set(7, 1)
            self.set(6, 1)
            self.start()
            if not self.send(0xa1):
                self.stop()
                raise ValueError('EEPROM read command NACK')
            data = bytes(self.receive(i == size-1) for i in range(size))
            self.stop()
            self.now()
            return data
        except BaseException as error:
            self.fail(error)
