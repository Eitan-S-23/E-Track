"""Exact 303-sector orchestration on an already admitted held connection.

No entry, EEPROM, NOR, reset, resume or close capability is provided here.
"""
import hashlib
import math
import time

from .flash_plan import APP_START, SECTOR_SIZE, geometry
from .flash_port import Sector
from .mutation_audit import flash_stores
from .native_io import guarded

PREIMAGE_SHA = 'b777d7ff8ffe2ec449758d90a18ed81200dd8c93276312104272326d48888e39'


class Sequence:
    def __init__(self, dap, image, preimage, owner, emit, logs, remaining, *, reserve=3600,
                 clock=time.monotonic, sleep=time.sleep, native_guard=guarded, sector_factory=Sector):
        extent = geometry(image)
        if (type(preimage) is not bytes or len(preimage) != extent.erase_end-APP_START or
                hashlib.sha256(preimage).hexdigest() != PREIMAGE_SHA):
            raise ValueError('exact captured original envelope required')
        if type(reserve) not in (int, float) or not math.isfinite(reserve) or not 0 < reserve <= 7200:
            raise ValueError('explicit downstream/close reserve required')
        self.dap, self.image, self.preimage = dap, image, preimage
        self.owner, self.emit, self.logs, self.remaining = owner, emit, logs, remaining
        self.reserve, self.clock, self.sleep = reserve, clock, sleep
        self.native_guard, self.factory = native_guard, sector_factory
        self.log_start = logs.gate.index
        if len(logs.gate.paths)-self.log_start < len(extent.sectors)+1:
            raise ValueError('preflighted log positions for every sector and successor required')
        self.used = self.active = self.app_may_have_changed = False
        self.error = None
        self.previous_left = None
        self.current_port = self.last_returned = None
        self.index = 0
        self.completed = []
        self.boundary(self.log_start)
        self.fresh_head()

    def boundary(self, log_index):
        if (self.error is not None or self.logs.dap is not self.dap or self.owner() is not True or
                self.logs.target_allowed() is not True or self.logs.gate.index != log_index or
                self.left() <= self.reserve):
            raise ValueError('Flash handoff owner/log/reserve missing')

    def fresh_head(self):
        # Re-audit the actual AP-only prefix, not a caller-supplied clean flag.
        if self.logs.gate.index <= 0 or self.logs.gate.boundary is None:
            raise ValueError('separately sealed entry and fresh accepted log head required')
        self.native_guard(self.logs.verify_head, seconds=min(300, self.left()-self.reserve))
        self.boundary(self.logs.gate.index)

    def left(self):
        value = self.remaining()
        if (type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 28800 or
                self.previous_left is not None and value > self.previous_left):
            raise ValueError('invalid/nonmonotonic complete-worker allowance')
        self.previous_left = value
        return value

    def admitted(self):
        return (self.active and self.error is None and self.owner() is True and self.logs.target_allowed() is True and
                self.logs.gate.index == self.log_start+self.index and self.left() > self.reserve)

    def bounded_call(self, function, *args, seconds):
        if not self.admitted() or self.current_port is None:
            raise ValueError('sector native call not admitted')
        budget = self.current_port.words.budget
        budget.end = min(budget.end, budget.now()+self.left()-self.reserve)
        result = self.native_guard(function, *args, seconds=min(seconds, budget.left()))
        self.boundary(self.log_start+self.index)
        budget.now()
        return result

    def run(self):
        if self.used:
            raise ValueError('Flash sequence cannot replay')
        self.used = self.active = True
        desired = self.image+self.preimage[len(self.image):]
        try:
            self.emit('flash-sequence-start', sectors=303, reserve_seconds=self.reserve)
            for index, (address, bank) in enumerate(geometry(self.image).sectors):
                self.index = index
                if not self.admitted() or self.left() < self.reserve+300:
                    raise ValueError('full next-sector and downstream allowance/owner missing')
                self.fresh_head()
                self.current_port = self.factory(self.dap, self.image, self.preimage, index, self.admitted, self.emit,
                    seconds=300, clock=self.clock, sleep=self.sleep, guard=self.bounded_call)
                self.app_may_have_changed = True
                result = self.current_port.run()
                self.last_returned = result
                self.boundary(self.log_start+index)
                offset = index*SECTOR_SIZE
                count = sum(desired[i:i+4] != b'\xff'*4 for i in range(offset,offset+SECTOR_SIZE,4))
                if (type(result) is not dict or result.get('complete') is not True or
                        result.get('reset_allowed') is not False or result.get('address') != address or
                        type(result.get('bank')) is not int or result['bank'] != bank or
                        type(result.get('programmed_words')) is not int or result['programmed_words'] != count):
                    raise ValueError('sector returned an incomplete/mismatched result')
                expected = flash_stores(self.image, self.preimage, index)
                # One bounded guard covers native switching AND host seal/head work.
                trace = self.native_guard(lambda:self.logs.switch(
                    read_allowed=lambda a:a in self.current_port.words.reads, expected_stores=expected),
                    seconds=min(300, self.left()-self.reserve))
                if (trace['target_writes'] != len(expected) or trace['log_file_closed'] != 1 or
                        trace['native_close'] != 0 or not self.logs.target_allowed() or
                        self.logs.gate.index != self.log_start+index+1):
                    raise ValueError('sector did not reach verified next-log admission')
                self.completed.append(dict(index=index, address=address, bank=bank, programmed_words=count))
                self.boundary(self.log_start+index+1)
                self.emit('flash-sequence-sector-audited', **self.completed[-1])
                self.boundary(self.log_start+index+1)
            self.boundary(self.log_start+len(self.completed))
            return dict(result='ALL_FLASH_SECTORS_AUDITED', sectors=len(self.completed), reset_allowed=False,
                        eeprom_confirmed=False, runtime_health_verified=False)
        except BaseException as error:
            if self.error is None:
                self.error = type(error).__name__+': '+str(error)
            raise
        finally:
            self.active = False
