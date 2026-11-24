"""Complete-state successor after exactly three R2 sectors, never old-App resume.

Three separately sealed completed-sector readbacks replace the three omitted
write segments. All other original full-state captures and exit gates remain.
"""
from . import install as old
from .flash_continue import Remaining


class Install(old.Install):
    def __init__(self,*args,**kwargs):
        if kwargs.get('retained_entry') is None:raise ValueError('retained original context required')
        super().__init__(*args,**kwargs)
        self.control.expected_header=self.assets['image'][0x400:0x460]
        self.partial=self.assets['image'][:6144]+self.assets['envelope'][6144:]
        # Header identity is R2 already; CPU/RAM remain the old halted runtime.
        self.after_app=True
        self.app_may_have_changed=True
        self.prefix_verified=False

    def entry(self):
        super().entry()
        port=self.words(old.INTERNAL_READS,90)
        for index in range(3):
            if not self.owner():raise ValueError('completed-prefix owner missing')
            if (port.read32(old.flash.IDCODE)!=0x70083347 or port.read32(old.flash.FSIZE)&0xffff!=1024 or
                    port.read32(old.flash.DHCSR)&0x020affff!=0x20003 or port.read32(old.flash.PAUSE)!=0x1000):
                raise ValueError('completed-prefix identity/context changed')
            if any(port.read32(c)!=0x80 or port.read32(s)&0x15 for _,s,c,_ in old.flash.BANKS):
                raise ValueError('completed-prefix banks not idle/locked')
            offset=index*2048
            raw=port.read_bytes(old.APP_START+offset,1024)+port.read_bytes(old.APP_START+offset+1024,1024)
            if raw!=self.assets['image'][offset:offset+2048]:raise ValueError('completed prefix changed')
            self.seal(old.INTERNAL_READS)
            port.check()
        self.prefix_verified=True

    def internal(self,label):
        if label!='before':return super().internal(label)
        # Reuse the exact archive/metadata checks with this precisely derived
        # partial physical envelope; restore immutable original assets finally.
        original=self.assets
        self.assets=dict(original,image=self.partial)
        try:return super().internal(label)
        finally:self.assets=original

    def run(self):
        if self.used:raise ValueError('installation continuation cannot replay')
        self.used=self.active=True
        try:
            self.entry()
            if not self.prefix_verified:raise ValueError('fresh completed-prefix proof missing')
            self.internal('before')
            before=self.pair('before',self.assets['bcb'])
            self.plan=old.draft(self.function,before,self.assets['boot'],self.assets['image'])
            if self.plan.address!=0:raise ValueError('original C selected unauthorized EEPROM record')
            self.save('draft-a',0,self.plan.record)
            self.nor('before')
            self.results['preflash_state']=self.state()
            self.phase_start('REMAINING_FLASH')
            self.flash_sequence=Remaining(self.dap,self.assets['image'],self.assets['envelope'],self.owner,
                self.logs.emit,self.logs,self.remaining,clock=self.clock,sleep=self.sleep,native_guard=self.native_guard)
            self.results['flash']=self.component(self.flash_sequence.run)
            if self.results['flash']['result']!='REMAINING_300_FLASH_SECTORS_AUDITED':raise ValueError('incomplete remainder')
            self.phase_start('EEPROM_CONFIRM')
            def archive_operation(index,kind,address,value):
                if kind=='read':self.archive('confirm-read-'+str(index),0,value)
            self.eeprom_wire=old.Wire(self.dap,self.pin_config,self.plan,self.owner,self.logs.emit,self.logs,
                self.remaining,archive_operation,clock=self.clock,sleep=self.sleep,guard=self.native_guard)
            transaction=old.Transaction(self.function,self.plan,self.eeprom_wire,clock=self.clock,sleep=self.sleep)
            confirmation=self.component(transaction.run)
            self.results['confirmation']=confirmation
            if (confirmation['result']!='EEPROM_BYTES_CONFIRMED' or confirmation['error'] is not None or
                    confirmation['pages']!=8 or not old.observe(self.function,self.plan,confirmation['after'])):
                raise ValueError('original C confirmation failed; no retry/reset')
            self.internal('after')
            self.nor('after')
            self.results['final_state']=self.state()
            final=self.pair('after',self.plan.target*2)
            if not old.observe(self.function,self.plan,final):raise ValueError('final C observer rejected BCB')
            self.final_confirmed=True
            self.boot_and_health()
            self.phase='READY_FOR_FINAL_NATIVE_CLOSE'
            return dict(result=self.phase,app_may_have_changed=True,runtime_health_observed=True,
                        final_native_close_audited=False,historical_sdk_audit_passed=False)
        except BaseException as error:
            if self.error is None:self.error=type(error).__name__+': '+str(error)
            raise
        finally:self.active=False
