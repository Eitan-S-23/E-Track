"""Settled-state polling and exact no-erase third-sector remainder.

No device entry or repair authority is provided. A caller must freshly prove
the retained context, observed partial image and current PG controller state.
"""
import hashlib

from .flash_port import Sector,BANKS
from .mutation_audit import flash_stores

PARTIAL_SHA='dadadad5ea6d0a5af0227880dea37960486dc8f340e7b7dc93700d5e88e0985c'
NEXT=0x08011228
PREFIX_STORES=287


class ObservedSector(Sector):
    def wait(self,seconds):
        end=min(self.words.budget.end,self.words.budget.now()+seconds)
        while True:
            self.check()
            status=self.words.read32(self.status_reg)
            observed=self.words.budget.now()
            if status&0x14:raise ValueError('Flash program/protection error')
            if status&0x21==0x20:
                if observed>=end:
                    self.emit('flash-completion-observed-late',status=status,deadline=end,observed=observed,
                              physical_completion_within_phase_deadline_proven=False)
                    self.words.check()
                return
            if observed>=end:raise ValueError('Flash still busy/uncompleted at observation deadline')
            self.sleep(max(0,min(.001,end-observed)))


class PartialSector(ObservedSector):
    def __init__(self,dap,image,preimage,owner,emit,**kwargs):
        if type(preimage) is not bytes or hashlib.sha256(preimage).hexdigest()!=PARTIAL_SHA:
            raise ValueError('exact independently reconciled partial envelope required')
        super().__init__(dap,image,preimage,2,owner,emit,**kwargs)
        full=flash_stores(image,preimage,2)
        if full[PREFIX_STORES-1]!=(0x08011224,0x8965ff72):raise ValueError('partial store boundary differs')
        self.plan=full[PREFIX_STORES:]
        self.position=0
        if self.before[:552]!=self.after[:552] or self.before[552:]!=b'\xff'*1496:
            raise ValueError('partial image does not match precise prefix/erased tail')

    def allowed(self,address,value):
        return (self.position<len(self.plan) and self.plan[self.position]==(address,value) and
                super().allowed(address,value))

    def write(self,address,value):
        if self.position>=len(self.plan) or self.plan[self.position]!=(address,value):
            raise ValueError('write differs from no-erase remainder plan')
        super().write(address,value)
        self.position+=1

    def run(self):
        try:
            if self.used:raise ValueError('partial sector cannot replay')
            self.used=True
            self.check(config=True)
            if (self.words.read32(self.ctrl)!=1 or self.words.read32(self.status_reg)!=0x20 or
                    self.words.read32(BANKS[1][2])!=0x80 or self.words.read32(BANKS[1][1])&0x15):
                raise ValueError('fresh settled PG/other-bank state required')
            if self.read_sector()!=self.before:raise ValueError('partial sector changed since settlement')
            self.erased=True
            self.programmed_words=138
            for offset in range(552,2048,4):
                raw=self.after[offset:offset+4]
                if raw==b'\xff'*4:continue
                address=self.address+offset;value=int.from_bytes(raw,'little')
                if address<NEXT:raise ValueError('completed prefix must not replay')
                self.fresh_flags()
                self.write(address,value)
                self.wait(.5)
                if self.words.read32(address)!=value:raise ValueError('remaining word readback mismatch')
                self.programmed_words+=1
            self.lock()
            if self.position!=len(self.plan) or self.read_sector()!=self.after:
                raise ValueError('complete third-sector plan/readback differs')
            self.check(config=True)
            if any(self.words.read32(c)!=0x80 or self.words.read32(s)&0x15 for _,s,c,_ in BANKS):
                raise ValueError('final two-bank status/lock differs')
            self.emit('flash-sector-remainder-verified',address=self.address,bank=self.bank,
                      preserved_words=138,programmed_words=self.programmed_words)
            self.words.check();self.done=True
            return dict(address=self.address,bank=self.bank,complete=True,reset_allowed=False,
                        programmed_words=self.programmed_words,preserved_words=138,erase_commands=0)
        except BaseException as error:
            if self.error is None:self.error=type(error).__name__+': '+str(error)
            if self.words.error is None:self.words.error=self.error
            raise
