"""Pure-C draft/oracle around separately executed exact EEPROM page transport."""
from dataclasses import dataclass
import time
import threading

from .native_io import Budget
from p34_confirm_page import confirm

_C_LOCK = threading.Lock()


@dataclass(frozen=True)
class Draft:
    before: bytes
    target: bytes
    address: int
    record: bytes
    boot: bytes
    image: bytes


def draft(function, capture, boot, image):
    if type(capture) is not bytes or len(capture)!=256 or capture[:128]!=capture[128:]:
        raise ValueError('stable original A/B/A/B capture required')
    before = capture[:128]
    proposed = []
    with _C_LOCK:
        result = confirm(function,before,boot,image,lambda a,n: before[a:a+n],
                         lambda a,d: (proposed.append((a,d)) or -1))
    if result['status']!=0 or result['callback_errors'] or result['result'].write_attempts!=1 or len(proposed)!=1:
        raise ValueError('original C transaction did not produce one exact draft')
    address,record = proposed[0]
    if address not in (0,64) or len(record)!=64:
        raise ValueError('C draft is not one BCB record')
    target = before[:address]+record+before[address+64:]
    return Draft(before,target,address,record,boot,image)


def observe(function,plan,capture):
    if type(capture) is not bytes or len(capture)!=256 or capture[:128]!=capture[128:] or capture[:128]!=plan.target:
        return False
    pair = capture[:128]
    writes = []
    with _C_LOCK:
        result = confirm(function,plan.before,plan.boot,plan.image,lambda a,n: pair[a:a+n],
                         lambda a,d: (writes.append((a,d)) or -1))
    return (result['status']==2 and not result['callback_errors'] and not writes and
            result['result'].write_attempts==0 and result['result'].active==1+plan.address//64)


class Transaction:
    """Sole-use wire operation. C callbacks above only ever see memory arrays.

    Per-call limits are separate from historical HOST_ONLY PagePort limits.
    A device owner still has to qualify these budgets before the first mutation.
    """
    def __init__(self,function,plan,wire,*,seconds=1800,clock=time.monotonic,sleep=time.sleep):
        if not isinstance(plan,Draft) or wire.address!=plan.address or wire.record!=plan.record:
            raise ValueError('wire/draft mismatch')
        if draft(function,plan.before*2,plan.boot,plan.image)!=plan:
            raise ValueError('draft does not match original C transaction')
        self.function,self.plan,self.wire,self.sleep = function,plan,wire,sleep
        self.budget = Budget(seconds,clock)
        self.used = False
        self.error = None
        self.pages = 0
        self.observation_allowed = True

    def read(self,address,size):
        try:
            if not self.observation_allowed: raise ValueError('wire observation not available')
            raw = self.wire.read(address,size,min(300,self.budget.left()))
            self.budget.now()
            if type(raw) is not bytes or len(raw)!=size:
                raise ValueError('short physical EEPROM read')
            return raw
        except BaseException:
            self.observation_allowed = False
            raise

    def pair(self):
        return self.read(0,64)+self.read(64,64)

    def run(self):
        if self.used: raise ValueError('physical confirmation cannot replay')
        self.used = True
        after = None
        try:
            if self.pair()!=self.plan.before:
                raise ValueError('physical prewrite BCB drift')
            for offset in range(0,64,8):
                started = self.budget.now()
                self.pages += 1
                self.observation_allowed = False
                response = self.wire.page(self.plan.address+offset,self.plan.record[offset:offset+8],min(120,self.budget.left()))
                returned = self.budget.now()
                if (type(response) is not dict or response.get('released') is not True or
                        type(response.get('stop_upper')) not in (int,float) or
                        not started<=response['stop_upper']<=returned or
                        type(response.get('status')) is not int or response['status'] not in (-1,0)):
                    raise ValueError('unknown page STOP/return')
                ready = response['stop_upper']+.005
                if ready>=self.budget.end: raise ValueError('no settlement budget')
                now = self.budget.now()
                if now<ready: self.sleep(ready-now)
                if self.budget.now()<ready: raise ValueError('write-cycle wait returned early')
                if self.wire.ack(min(30,self.budget.left())) is not True:
                    raise ValueError('ready ACK not established')
                self.budget.now()
                self.observation_allowed = True
                actual = self.read(self.plan.address+offset,8)
                if actual!=self.plan.record[offset:offset+8] or response['status']!=0:
                    raise ValueError('page mismatch or negative settled return')
        except BaseException as error:
            self.error = type(error).__name__+': '+str(error)
        if self.pages == 0:
            return dict(result='EEPROM_PREWRITE_REJECTED',error=self.error,after=None,pages=0,reset_qualified=False)
        # An unknown/failed wire never gains permission to send observer traffic.
        if self.observation_allowed and self.wire.error is None and self.wire.pending_stop is None:
            try:
                after = self.pair()+self.pair()
                confirmed = observe(self.function,self.plan,after)
                self.budget.now()
                return dict(result='EEPROM_BYTES_CONFIRMED' if confirmed else 'EEPROM_NOT_CONFIRMED',
                            error=self.error,after=after,pages=self.pages,reset_qualified=False)
            except BaseException as error:
                if self.error is None: self.error = type(error).__name__+': '+str(error)
        return dict(result='EEPROM_OUTCOME_UNKNOWN',error=self.error,after=after,pages=self.pages,reset_qualified=False)
