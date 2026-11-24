"""C-draft-bound EEPROM wire with one audited log per settled operation.

No connect, reset, Flash or NOR capability. A complete coordinator must supply
the retained owner and archive callback; this is not an installation entry.
"""
import math
import time

from .confirm_io import Draft
from .eeprom_page import EEPROM
from . import gpio_page as gpio
from .native_io import Words, guarded


def stores(kind, address=0, payload=b'', size=0):
    """Independent master-edge oracle, including idempotent GPIO stores."""
    if (type(address) is not int or type(payload) is not bytes or type(size) is not int or
            kind not in ('read', 'page', 'ack')):
        raise ValueError('invalid EEPROM operation plan')
    if kind == 'read' and not (payload == b'' and
            (size == 64 and address in (0, 64) or size == 8 and address in range(0, 64, 8))):
        raise ValueError('read plan outside pair/current A page')
    if kind == 'page' and not (address in range(0, 64, 8) and len(payload) == 8 and size == 0):
        raise ValueError('page plan outside inactive A')
    if kind == 'ack' and (address != 0 or payload or size):
        raise ValueError('ACK plan has payload')
    edges = []
    def setpin(pin, high): edges.append((gpio.SET if high else gpio.CLEAR, 1 << pin))
    def start():
        setpin(7, 0); setpin(6, 0)
    def stop():
        setpin(6, 0); setpin(7, 0); setpin(6, 1); setpin(7, 1)
    def bit(value):
        setpin(7, value); setpin(6, 1); setpin(6, 0)
    def send(value):
        for shift in range(7, -1, -1): bit((value >> shift) & 1)
        setpin(7, 1); setpin(6, 1); setpin(6, 0)
    start()
    send(0xa0)
    if kind != 'ack': send(address)
    if kind == 'page':
        for value in payload: send(value)
    elif kind == 'read':
        setpin(7, 1); setpin(6, 1); start(); send(0xa1)
        for index in range(size):
            setpin(7, 1)
            for _ in range(8):
                setpin(6, 1); setpin(6, 0)
            bit(int(index == size-1))
            setpin(7, 1)
    stop()
    return tuple(edges)


class Wire(EEPROM):
    def __init__(self, dap, original, plan, owner, emit, logs, remaining, archive, *,
                 seconds=1800, reserve=900, clock=time.monotonic, sleep=time.sleep, guard=guarded):
        if not isinstance(plan, Draft) or plan.address != 0:
            raise ValueError('only original-C inactive A draft is authorized')
        if type(reserve) not in (int,float) or not math.isfinite(reserve) or not 0 < reserve <= 7200:
            raise ValueError('finite downstream/close reserve required')
        self.dap, self.owner, self.logs, self.remaining = dap, owner, logs, remaining
        self.reserve, self.native_guard, self.archive = reserve, guard, archive
        self.previous_left = None
        self.active = self.sealing = False
        self.index = logs.gate.index
        self.completed = []
        self.error = None
        if len(logs.gate.paths)-self.index < 31:
            raise ValueError('30 operations and successor log positions required')
        words = Words(dap, emit, reads=gpio.READS, write_allowed=lambda a,v:self.admitted() and gpio.allowed_write(a,v),
                      seconds=seconds, clock=clock, guard=self.bounded_call)
        pins = gpio.Pins(words, original, self.admitted)
        super().__init__(pins, plan.address, plan.record, seconds=seconds, clock=clock, sleep=sleep, emit=emit)
        self.boundary()
        self.fresh_head()

    def left(self):
        value = self.remaining()
        if (type(value) not in (int,float) or not math.isfinite(value) or not 0 < value <= 28800 or
                self.previous_left is not None and value > self.previous_left):
            raise ValueError('complete-worker allowance invalid/nonmonotonic')
        self.previous_left = value
        return value

    def boundary(self):
        if (self.error is not None or self.logs.dap is not self.dap or self.owner() is not True or
                not self.logs.target_allowed() or self.logs.gate.index != self.index or self.left() <= self.reserve):
            raise ValueError('EEPROM handoff owner/log/reserve missing')
        self.budget.now()
        self.pins.words.check()

    def fresh_head(self):
        if self.index <= 0 or self.logs.gate.boundary is None:
            raise ValueError('fresh accepted AP-only head required')
        self.native_guard(self.logs.verify_head, seconds=min(300,self.left()-self.reserve,self.budget.left()))
        self.boundary()

    def admitted(self):
        self.boundary()
        return self.active and not self.sealing

    def bounded_call(self, function, *args, seconds):
        if not self.admitted(): raise ValueError('no active EEPROM wire operation')
        words = self.pins.words
        words.budget.end = min(words.budget.end, words.budget.now()+self.left()-self.reserve)
        result = self.native_guard(function, *args, seconds=min(seconds,words.budget.left(),self.end-self.now()))
        self.now()
        self.boundary()
        return result

    def operation(self, kind, address, payload, size, seconds):
        try:
            if self.active or self.sealing or len(self.completed) >= 30:
                raise ValueError('EEPROM reentry/operation count exceeded')
            self.boundary()
            self.fresh_head()
            expected = stores(kind,address,payload,size)
            self.active = True
            if kind == 'read': result = super().read(address,size,seconds)
            elif kind == 'page': result = super().page(address,payload,seconds)
            else: result = super().ack(seconds)
            self.active = False
            self.boundary()
            if (kind == 'read' and (type(result) is not bytes or len(result) != size) or
                    kind == 'page' and (type(result) is not dict or result.get('status') != 0 or result.get('released') is not True) or
                    kind == 'ack' and result is not True):
                raise ValueError('negative/unsettled wire result; preserve without observer retry')
            self.native_guard(self.archive,len(self.completed),kind,address,result,
                              seconds=min(300,self.left()-self.reserve,self.budget.left(),self.pins.words.budget.left()))
            self.boundary()
            self.sealing = True
            trace = self.native_guard(lambda:self.logs.switch(read_allowed=lambda a:a in gpio.READS,
                expected_stores=expected), seconds=min(300,self.left()-self.reserve,self.budget.left()))
            if trace['target_writes'] != len(expected) or trace['log_file_closed'] != 1 or trace['native_close'] != 0:
                raise ValueError('EEPROM segment audit mismatch')
            self.index += 1
            self.completed.append(dict(kind=kind,address=address,stores=len(expected)))
            self.sealing = False
            self.boundary()
            self.emit('eeprom-operation-audited',index=len(self.completed)-1,**self.completed[-1])
            self.boundary()
            return result
        except BaseException as error:
            self.fail(error)
        finally:
            self.active = self.sealing = False

    def read(self,address,size,seconds): return self.operation('read',address,b'',size,seconds)
    def page(self,address,data,seconds): return self.operation('page',address,data,0,seconds)
    def ack(self,seconds): return self.operation('ack',0,b'',0,seconds)
