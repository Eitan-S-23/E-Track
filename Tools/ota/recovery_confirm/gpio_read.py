"""Single 64B EEPROM read measurement and independent physical-sample decoder."""
import time

from .eeprom_page import EEPROM
from .gpio_page import Pins, SET, CLEAR, INPUT, OUTPUT


class ReadOnlyEEPROM(EEPROM):
    def page(self,*args):
        raise ValueError('measurement cannot write an EEPROM page')

    def ack(self,*args):
        raise ValueError('measurement cannot probe a write cycle')


class Read64:
    def __init__(self,pins,emit,*,clock=time.monotonic,sleep=time.sleep):
        if not isinstance(pins,Pins):
            raise ValueError('native GPIO port required')
        self.pins,self.emit,self.clock=pins,emit,clock
        self.wire=ReadOnlyEEPROM(pins,0,b'\x00'*64,seconds=300,clock=clock,sleep=sleep)
        self.used=False
        self.error=None

    def run(self):
        if self.used: raise ValueError('single GPIO measurement already consumed')
        self.used=True
        started=self.clock()
        before=(self.pins.words.read_count,self.pins.words.writes,self.pins.edges)
        try:
            self.emit('gpio-read-start',started=started,output=self.pins.original[OUTPUT])
            raw=self.wire.read(0,64,300)
            ended=self.clock()
            if not 0 < ended-started < 300 or self.wire.error or self.pins.error or self.pins.words.error:
                raise ValueError('GPIO measurement timing/port failure')
            result=dict(raw_hex=raw.hex(),elapsed_seconds=ended-started,
                target_reads=self.pins.words.read_count-before[0],gpio_stores=self.pins.words.writes-before[1],
                edges=self.pins.edges-before[2],eeprom_payload_writes=0,physical_waveform_timing_qualified=False)
            self.emit('gpio-read-returned',ended=ended,**result)
            return result
        except BaseException as error:
            self.error=type(error).__name__+': '+str(error)
            raise


def wire_trace(rows,raw,original):
    """Decode only the exact read interval; the enclosing cell needs SDK audit."""
    if type(raw) is not bytes or len(raw)!=64 or original&0xc0!=0xc0:
        raise ValueError('exact 64B read and released original GPIO required')
    rows=list(rows)
    if not rows or rows[0]['event']!='gpio-read-start' or rows[-1]['event']!='gpio-read-returned':
        raise ValueError('exact measurement interval required, no outside target IO')
    started=finished=False
    output=original
    pending=None
    fresh_input=None
    post_expected=None
    drive=[];sampled=[];current=None
    starts=stops=attempts=returns=0
    start_positions=[];stop_positions=[]
    for row in rows:
        event=row['event']
        if event=='recovery-word-write-attempt' and row['address'] in (SET,CLEAR) and (not started or finished):
            raise ValueError('GPIO store outside the sole read interval')
        if event=='gpio-read-start':
            if started or row['output']!=original: raise ValueError('duplicate/changed measurement start')
            started=True
        if event=='gpio-read-returned':
            if not started or finished or row['raw_hex']!=raw.hex() or post_expected is not None:
                raise ValueError('measurement return or boundary witness missing')
            finished=True
        if not started or finished: continue
        if event=='recovery-word-write-attempt':
            if pending is not None or post_expected is not None or row['address'] not in (SET,CLEAR) or row['value'] not in (0x40,0x80):
                raise ValueError('measurement write outside GPIO scope')
            target=(output|row['value']) if row['address']==SET else output&~row['value']
            boundary=row['value']==0x80 and output&0x40 and bool(output&0x80)!=bool(target&0x80)
            if boundary and fresh_input!=(output,output&0xc0):
                raise ValueError('START/STOP has no fresh physical pre-level witness')
            pending=(row['address'],row['value']);attempts+=1
        elif event=='recovery-word-write-returned':
            if pending!=(row['address'],row['value']): raise ValueError('unpaired GPIO store')
            address,value=pending
            previous=output
            output=(output|value) if address==SET else (output&~value)
            if value==0x40:
                if not previous&0x40 and output&0x40:
                    drive.append(int(bool(output&0x80)));sampled.append(None);current=len(drive)-1
                if not output&0x40: current=None
            elif previous&0x40 and bool(previous&0x80)!=bool(output&0x80):
                post_expected=output&0xc0
                if output&0x80:
                    stops+=1;stop_positions.append(len(drive))
                else:
                    starts+=1;start_positions.append(len(drive))
            pending=None;returns+=1
            fresh_input=None
        elif event=='recovery-word-read':
            if row['address']==OUTPUT and row['value']!=output:
                raise ValueError('physical GPIO latch differs from transmitted edge')
            if row['address']==INPUT:
                if post_expected is not None:
                    if row['value']&0xc0!=post_expected:
                        raise ValueError('START/STOP physical post-level mismatch')
                    post_expected=None
                fresh_input=(output,row['value']&0xc0)
                if bool(row['value']&0x40)!=bool(output&0x40):
                    raise ValueError('contradictory physical SCL sample')
                if output&0x40:
                    bit=int(bool(row['value']&0x80))
                    if current in (None,18,604):
                        if bit!=int(bool(output&0x80)):
                            raise ValueError('START/STOP physical SDA differs from driven level')
                    elif sampled[current] is not None and sampled[current]!=bit:
                        raise ValueError('contradictory physical SDA within stable high bit')
                    if current is not None: sampled[current]=bit
    if not finished or pending or attempts!=returns or output!=original or (starts,stops,len(drive))!=(2,1,605):
        raise ValueError('incomplete fixed EEPROM random-read trace')
    if start_positions!=[0,19] or stop_positions!=[605]:
        raise ValueError('START/STOP at unexpected protocol positions')
    def byte(bits):
        if len(bits)!=8 or any(bit not in (0,1) for bit in bits): raise ValueError('missing physical SDA sample')
        return sum(bit<<(7-i) for i,bit in enumerate(bits))
    if [byte(drive[i:i+8]) for i in (0,9,19)]!=[0xa0,0,0xa1] or any(sampled[i]!=0 for i in (8,17,27)):
        raise ValueError('not one acknowledged A0/pointer/repeated-START/A1 read')
    if any(drive[i]!=1 for i in (8,17,27)):
        raise ValueError('master did not release SDA for slave ACK')
    if any(sampled[i:i+8]!=drive[i:i+8] for i in (0,9,19)):
        raise ValueError('master address/pointer bits differ from physical SDA')
    if any(drive[28+i*9:36+i*9]!=[1]*8 for i in range(64)):
        raise ValueError('master did not release SDA for slave read data')
    reconstructed=bytes(byte(sampled[28+i*9:36+i*9]) for i in range(64))
    if reconstructed!=raw or any(drive[36+i*9]!=int(i==63) for i in range(64)):
        raise ValueError('physical bytes or final master NACK differ')
    if any(sampled[36+i*9]!=int(i==63) for i in range(64)):
        raise ValueError('physical master ACK/final NACK differs')
    return dict(gpio_stores=returns,rising_clocks=605,starts=2,stops=1,bytes=64,eeprom_payload_writes=0)
