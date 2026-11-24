"""Full R2 image, original Boot and health on one caller-owned read-only link.

No connection, reset, EEPROM, NOR or phone capability. The caller closes and
audits the native link; this component cannot prove a physical BCB or backup.
"""
import hashlib
import math
import time

import p34_finalized_vtor_capture as capture
from recovery_entry.finalized_reader import Reader
from .native_io import Words,guarded
from .r2_paired_health import Monitor
from . import r2_health as health
from .boot_exit import BOOT_SHA

APP_READS={capture.DHCSR,capture.VTOR,*range(capture.policy.ORIGIN,capture.policy.ORIGIN+capture.IMAGE_BYTES,4)}
BOOT_READS={capture.DHCSR,capture.VTOR,*range(0x08000000,0x08010000,4)}
LOG_COUNT=24


class Checkpoint:
    def __init__(self,dap,logs,remaining,archive,image,boot,map_bytes,*,connection_generation,
                 boot_generation=0,clock=time.monotonic,sleep=time.sleep,guard=guarded):
        digest=hashlib.sha256(image).hexdigest() if type(image) is bytes else None
        if digest not in capture.PLANNED or len(image)!=capture.IMAGE_BYTES:
            raise ValueError('exact planned R2 image required')
        capture.policy.sources.verify(image)
        if type(boot) is not bytes or len(boot)!=65536 or hashlib.sha256(boot).hexdigest()!=BOOT_SHA:
            raise ValueError('exact original full Boot required')
        health.verify_map(map_bytes)
        if type(connection_generation) is not str or not connection_generation or type(boot_generation) is not int or boot_generation<0:
            raise ValueError('explicit checkpoint generation required')
        self.dap,self.logs,self.remaining,self.archive=dap,logs,remaining,archive
        self.image,self.boot,self.map_bytes=image,boot,map_bytes
        self.digest,self.version=digest,capture.PLANNED[digest]
        self.connection_generation,self.boot_generation=connection_generation,boot_generation
        self.clock,self.sleep,self.guard=clock,sleep,guard
        self.previous_left=None
        self.index=logs.gate.index
        self.active=self.used=self.delegating=False
        self.error=None
        self.reader=self.boot_words=self.monitor=None
        self.image_read=0
        if logs.dap is not dap or self.index!=1 or len(logs.gate.paths)!=LOG_COUNT:
            raise ValueError('one sealed setup and exact24 checkpoint logs required')
        self.check()
        self.guard(logs.verify_head,seconds=min(60,self.left()-90))
        self.check()

    def left(self):
        value=self.remaining()
        if (type(value) not in (int,float) or not math.isfinite(value) or not 90<value<=900 or
                self.previous_left is not None and value>self.previous_left):
            raise ValueError('checkpoint global allowance/close reserve lost')
        self.previous_left=value
        return value

    def check(self):
        self.left()
        if (self.error is not None or not self.dap.ready or self.dap.callback_error is not None or
                self.logs.dap is not self.dap or not self.logs.target_allowed() or
                not self.delegating and self.logs.gate.index!=self.index):
            raise ValueError('checkpoint owner/log/failure lost')
        for port in (self.reader,self.boot_words,self.monitor):
            if port is not None and (port.error is not None or getattr(port,'reset_seen',False)):
                raise ValueError('checkpoint shared reset/failure latch set')

    def owner(self):
        self.check()
        return self.active

    def lease(self):
        return dict(owned=self.owner(),connection_generation=self.connection_generation,
                    boot_generation=self.boot_generation,reset_seen=False)

    def native(self,function,*args,seconds):
        if not self.owner():raise ValueError('inactive checkpoint')
        result=self.guard(function,*args,seconds=min(seconds,self.left()-90))
        self.check()
        return result

    def emit_read(self,event,**fields):
        names={'finalized-read-attempt':'recovery-chunk-read-attempt',
               'finalized-read-returned':'recovery-chunk-read-returned'}
        if event not in names:raise ValueError('unexpected finalized reader event')
        self.logs.emit(names[event],**fields)

    def seal(self,reads):
        self.check()
        trace=self.guard(lambda:self.logs.switch(read_allowed=lambda a:a in reads,expected_stores=[]),
                         seconds=min(60,self.left()-90))
        self.index+=1
        self.check()
        if trace['target_writes'] or trace['native_close'] or trace['log_file_closed']!=1:
            raise ValueError('checkpoint read-only segment audit failed')

    def image_reader(self,address,size,seconds):
        raw=self.reader.read(address,size,seconds)
        if address==capture.policy.ORIGIN+self.image_read and size==min(4096,len(self.image)-self.image_read):
            self.image_read+=size
            if self.image_read%32768==0:self.seal(APP_READS)
        return raw

    def running(self):
        owner=self.reader.owner()
        if owner['reset_seen'] or not owner['owned']:raise ValueError('checkpoint running epoch changed')
        if self.reader.read(capture.VTOR,4,min(30,self.left()-90))!=health.RUNTIME.to_bytes(4,'little'):
            raise ValueError('checkpoint requires stable R2 runtime vectors')

    def save(self,name,raw):
        self.check()
        self.guard(self.archive,name,raw,seconds=min(30,self.left()-90))
        self.check()

    def run(self):
        if self.used:raise ValueError('checkpoint cannot replay')
        self.used=self.active=True
        try:
            self.reader=Reader(self.dap,self.emit_read,self.lease,connection_generation=self.connection_generation,
                boot_generation=self.boot_generation,seconds=300,clock=self.clock,guard=self.native)
            observed=capture.capture(self.image_reader,self.reader.owner,image_sha256=self.digest,version=self.version,
                connection_generation=self.connection_generation,boot_generation=self.boot_generation,seconds=300,clock=self.clock)
            if self.image_read!=len(self.image) or observed['result']['phase']!='app-runtime':
                raise ValueError('complete runtime image capture missing')
            self.save('app',observed['raw_image'])
            self.seal(APP_READS)
            self.boot_words=Words(self.dap,self.logs.emit,reads=BOOT_READS,write_allowed=lambda a,v:False,
                                  seconds=120,clock=self.clock,guard=self.native)
            data=bytearray()
            for offset in range(0,65536,32768):
                for at in range(offset,offset+32768,1024):
                    self.running()
                    raw=self.boot_words.read_bytes(0x08000000+at,1024)
                    if raw!=self.boot[at:at+1024]:raise ValueError('original Boot bytes differ')
                    data.extend(raw)
                    self.running()
                if offset+32768==65536:self.save('boot',bytes(data))
                self.seal(BOOT_READS)
            self.monitor=Monitor(self.dap,self.image,self.map_bytes,self.owner,self.logs,self.remaining,
                                  clock=self.clock,sleep=self.sleep,guard=self.native)
            self.delegating=True
            try:runtime=self.monitor.run()
            finally:self.index=self.logs.gate.index;self.delegating=False
            self.check()
            if self.index!=LOG_COUNT-1 or runtime['version_code']!=self.version or runtime['reset_seen']:
                raise ValueError('checkpoint terminal identity/log differs')
            return dict(result='R2_IMAGE_BOOT_HEALTH_CHECKPOINT',version=self.version,image_sha256=self.digest,
                boot_sha256=BOOT_SHA,health=runtime,connection_generation=self.connection_generation,
                boot_generation=self.boot_generation,reset_seen=False,native_close_audited=False,
                physical_bcb_observed=False,backup_observed=False,ota_ready=False)
        except BaseException as error:
            if self.error is None:self.error=type(error).__name__+': '+str(error)
            raise
        finally:self.active=False
