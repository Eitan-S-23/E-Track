"""HOST_ONLY page transport model. No GPIO, J-Link or device entry exists here."""
import math

WRITE_CYCLE_SECONDS = .005


class PagePort:
    def __init__(self, io, address, data, *, clock, sleep, seconds=60):
        if getattr(io, 'host_only', False) is not True:
            raise ValueError('injected host EEPROM model required')
        if type(address) is not int or address not in (0,64) or type(data) is not bytes or len(data)!=64:
            raise ValueError('one exact inactive-slot record required')
        if type(seconds) not in (int,float) or not math.isfinite(seconds) or not 0<seconds<=300:
            raise ValueError('finite host-model deadline required')
        self.io,self.address,self.data,self.clock,self.sleep=io,address,data,clock,sleep
        self.previous=clock()
        if type(self.previous) not in (int,float) or not math.isfinite(self.previous):raise ValueError('clock')
        self.deadline=self.previous+seconds
        self.attempts=self.pages=0
        self.observe_allowed=True
        self.error=None
        self.clock_failed=False
        self.events=[]

    def now(self):
        if self.clock_failed:raise ValueError('page clock failure latched')
        now=self.clock()
        if type(now) not in (int,float) or not math.isfinite(now) or not self.previous<=now<self.deadline:
            self.clock_failed=True;self.observe_allowed=False
            raise ValueError('page clock/deadline exhausted')
        self.previous=now
        return now

    def budget(self):return min(15,self.deadline-self.now())

    def read(self,address,size):
        try:
            if not self.observe_allowed or type(address) is not int or type(size) is not int or address not in (0,64) or size!=64:
                raise ValueError('independent observation unavailable or outside BCB pair')
            raw=self.io.read(address,size,self.budget())
            self.now()
            if type(raw) is not bytes or len(raw)!=size:raise ValueError('incomplete independent read')
            return raw
        except BaseException as error:
            self.observe_allowed=False
            if self.error is None:self.error=type(error).__name__+': '+str(error)
            raise

    def write(self,address,data):
        try:
            if self.error is not None or not self.observe_allowed or self.attempts or type(address) is not int or type(data) is not bytes or address!=self.address or data!=self.data:
                raise ValueError('record mismatch or write replay')
            self.now();self.attempts=1
            for offset in range(0,64,8):
                page=data[offset:offset+8]
                started=self.now();self.observe_allowed=False;self.pages+=1
                self.events.append(dict(event='page-attempt',address=address+offset,data_hex=page.hex()))
                response=self.io.page(address+offset,page,self.budget())
                returned=self.now()
                if (type(response) is not dict or type(response.get('status')) is not int or
                        response['status'] not in (0,-1) or response.get('released') is not True or
                        type(response.get('stop_upper')) not in (int,float) or
                        not math.isfinite(response['stop_upper']) or not started<=response['stop_upper']<=returned):
                    raise ValueError('unknown STOP/release; do not poll or observe')
                ready_at=response['stop_upper']+WRITE_CYCLE_SECONDS
                now=self.now()
                if ready_at>=self.deadline:raise ValueError('no write-cycle settlement budget')
                if now<ready_at:self.sleep(ready_at-now)
                if self.now()<ready_at:raise ValueError('write-cycle wait returned early')
                # A fixed worst-case wait followed by one ACK probe is bounded.
                # NACK here is not permission to replay the payload or assume completion.
                ack=self.io.ack(self.budget());self.now()
                if ack is not True:raise ValueError('ready ACK not established')
                self.observe_allowed=True
                self.events.append(dict(event='page-settled',address=address+offset,stop_upper=response['stop_upper']))
                try:
                    actual=self.io.read(address+offset,8,self.budget());self.now()
                    if type(actual) is not bytes or len(actual)!=8:
                        self.observe_allowed=False
                        raise ValueError('incomplete page readback')
                except BaseException:
                    self.observe_allowed=False
                    raise
                if actual!=page:raise ValueError('page readback mismatch')
                if response['status']!=0:raise ValueError('uncertain page return after settlement')
            return 0
        except BaseException as error:
            if self.error is None:self.error=type(error).__name__+': '+str(error)
            return -1
