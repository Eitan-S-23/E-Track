"""Single-use A/B/A/B capture through the existing wire, with no page API."""
import time

from .eeprom_page import EEPROM


class ReadPair(EEPROM):
    ORDER = (0, 64, 0, 64)

    def __init__(self, pins, *, seconds=900, clock=time.monotonic, sleep=time.sleep, emit=lambda *a,**k:None):
        # Base read framing needs no record. Both base mutation entry points
        # are sealed below; this placeholder must never become a payload.
        super().__init__(pins, 0, bytes(64), seconds=seconds, clock=clock, sleep=sleep, emit=emit)
        self.capture_used = False
        self.capture_active = False
        self.read_index = 0

    def page(self, *args, **kwargs):
        self.fail(ValueError('read-pair has no EEPROM page capability'))

    def ack(self, *args, **kwargs):
        self.fail(ValueError('read-pair has no write-cycle ACK capability'))

    def read(self, address, size, seconds):
        try:
            if (not self.capture_active or self.read_index >= len(self.ORDER) or type(address) is not int or
                    address != self.ORDER[self.read_index] or type(size) is not int or size != 64):
                raise ValueError('only the current A/B/A/B read is available')
            self.read_index += 1
            return super().read(address, size, seconds)
        except BaseException as error:
            self.fail(error)

    def capture(self, after_read=lambda index,address,raw:None):
        try:
            if self.capture_used or self.error is not None:
                raise ValueError('read-pair capture consumed/failed')
            self.capture_used = True
            self.capture_active = True
            chunks = []
            for index, address in enumerate(self.ORDER):
                data = self.read(address, 64, min(300, self.budget.left()))
                chunks.append(data)
                after_read(index, address, data)
                self.budget.now()
            capture = b''.join(chunks)
            if capture[:128] != capture[128:]:
                raise ValueError('BCB pair changed between complete observations')
            return capture
        except BaseException as error:
            self.fail(error)
        finally:
            self.capture_active = False
