"""Only sectors3..302 after fresh physical verification of the completed prefix."""
from .flash_sequence import Sequence
from .flash_remainder import ObservedSector
from .flash_plan import geometry, SECTOR_SIZE
from .mutation_audit import flash_stores


class Remaining(Sequence):
    def __init__(self,*args,**kwargs):
        kwargs.setdefault('sector_factory',ObservedSector)
        super().__init__(*args,**kwargs)

    def run(self):
        if self.used: raise ValueError('remaining Flash sequence cannot replay')
        self.used = self.active = True
        desired = self.image+self.preimage[len(self.image):]
        try:
            self.emit('flash-continuation-start',first=3,last=302,sectors=300,reserve_seconds=self.reserve)
            for ordinal,(address,bank) in enumerate(geometry(self.image).sectors[3:]):
                self.index = ordinal
                index = ordinal+3
                if not self.admitted() or self.left()<self.reserve+300:
                    raise ValueError('full remaining-sector/downstream allowance missing')
                self.fresh_head()
                self.current_port = self.factory(self.dap,self.image,self.preimage,index,self.admitted,self.emit,
                    seconds=300,clock=self.clock,sleep=self.sleep,guard=self.bounded_call)
                self.app_may_have_changed = True
                result = self.current_port.run()
                self.last_returned = result
                self.boundary(self.log_start+ordinal)
                offset = index*SECTOR_SIZE
                count = sum(desired[i:i+4]!=b'\xff'*4 for i in range(offset,offset+SECTOR_SIZE,4))
                if (type(result) is not dict or result.get('complete') is not True or
                        result.get('reset_allowed') is not False or result.get('address')!=address or
                        type(result.get('bank')) is not int or result['bank']!=bank or
                        type(result.get('programmed_words')) is not int or result['programmed_words']!=count):
                    raise ValueError('remaining sector result differs')
                expected = flash_stores(self.image,self.preimage,index)
                trace = self.native_guard(lambda:self.logs.switch(
                    read_allowed=lambda a:a in self.current_port.words.reads,expected_stores=expected),
                    seconds=min(300,self.left()-self.reserve))
                if (trace['target_writes']!=len(expected) or trace['log_file_closed']!=1 or trace['native_close'] or
                        not self.logs.target_allowed() or self.logs.gate.index!=self.log_start+ordinal+1):
                    raise ValueError('remaining sector lacks a sealed successor')
                self.completed.append(dict(index=index,address=address,bank=bank,programmed_words=count))
                self.boundary(self.log_start+ordinal+1)
                self.emit('flash-sequence-sector-audited',**self.completed[-1])
                self.boundary(self.log_start+ordinal+1)
            self.boundary(self.log_start+300)
            return dict(result='REMAINING_300_FLASH_SECTORS_AUDITED',sectors=300,first=3,last=302,
                        reset_allowed=False,eeprom_confirmed=False,runtime_health_verified=False)
        except BaseException as error:
            if self.error is None:self.error=type(error).__name__+': '+str(error)
            raise
        finally:self.active=False
