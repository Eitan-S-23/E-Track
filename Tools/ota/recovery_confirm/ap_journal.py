"""Exact native AP call journal and whole-session audit, with injected scopes."""
import ctypes
import math
import re
import time

from p34_nor_audit import WREG, RREG, VALUE, RETURN


def valid_time(value):
    return type(value) in (int,float) and math.isfinite(value)


def next_tar(address):
    # The actual AP may wrap at 4KiB. Never infer a safe next address from 1KiB.
    return None if address&1023==1020 else address+4


class JournalSDK:
    """Wrap after Dap constructs native signatures, before the first AP call."""
    def __init__(self,sdk,emit,clock=time.monotonic):
        self.sdk,self.emit,self.clock=sdk,emit,clock
        self.sequence=0
        self.busy=False
        self.error=None
        self.previous_end=None

    def __getattr__(self,name):
        return getattr(self.sdk,name)

    def invoke(self,operation,index,ap,payload):
        if self.busy or self.error is not None:
            raise ValueError('AP journal overlap/failure latched')
        self.busy=True
        self.sequence+=1
        seq=self.sequence
        name='JLINKARM_CORESIGHT_'+('ReadAPDPReg' if operation=='read' else 'WriteAPDPReg')
        try:
            self.emit('ap-call-attempt',sequence=seq,operation=operation,index=index,ap=ap,
                      value=None if operation=='read' else payload)
            started=self.clock()
            if not valid_time(started) or self.previous_end is not None and started<self.previous_end:
                raise ValueError('invalid/nonmonotonic native start clock')
            rc=getattr(self.sdk,name)(index,ap,payload)
            ended=self.clock()
            value=ctypes.cast(payload,ctypes.POINTER(ctypes.c_uint32))[0] if operation=='read' and type(rc)is int and rc>=0 else None
            self.emit('ap-call-returned',sequence=seq,rc=rc,read_value=value,started=started,
                      ended=ended if valid_time(ended) else None)
            if type(rc)is not int or rc<0 or not valid_time(ended) or ended<started:
                raise OSError('native AP error or nonmonotonic call clock')
            self.previous_end=ended
            return rc
        except BaseException as error:
            self.error=type(error).__name__+': '+str(error)
            raise
        finally:
            self.busy=False

    def JLINKARM_CORESIGHT_ReadAPDPReg(self,index,ap,payload):
        return self.invoke('read',index,ap,payload)

    def JLINKARM_CORESIGHT_WriteAPDPReg(self,index,ap,payload):
        return self.invoke('write',index,ap,payload)


def calls(rows):
    pending=None
    sequence=0
    previous_end=None
    for row in rows:
        if row['event']=='ap-call-attempt':
            sequence+=1
            if pending is not None or row['sequence']!=sequence or row['ap'] not in (0,1):
                raise ValueError('AP journal attempt ordering')
            pending=row
        elif row['event']=='ap-call-returned':
            if (pending is None or row['sequence']!=sequence or type(row['rc'])is not int or row['rc']<0 or
                not valid_time(row['started']) or not valid_time(row['ended']) or row['ended']<row['started'] or
                previous_end is not None and row['started']<previous_end):
                raise ValueError('AP journal return ordering/outcome')
            previous_end=row['ended']
            yield (pending['operation'],'AP' if pending['ap'] else 'DP',pending['index'],
                   pending['value'],row['read_value'],row['rc'])
            pending=None
        elif row['event'].startswith('ap-call-'):
            raise ValueError('unknown/failed AP journal event')
    if pending is not None: raise ValueError('unterminated AP journal attempt')


def audit(lines,rows,metadata,*,read_allowed,write_allowed):
    expected=iter(calls(rows))
    pending=None
    bank=0
    csw=metadata['ap_csw']
    tar=None
    count=reads=writes=closed=0
    for line in lines:
        if 'CPU_WriteMem' in line or re.search(r'JLINK(?:ARM)?_(?:Connect|Halt|Reset|Go|Step|SetRESET|ClrRESET|SetPower)\(',line):
            raise ValueError('unlisted high-level device operation')
        if re.search(r'JLINK(?:ARM)?_Close\(',line):
            if closed or pending: raise ValueError('duplicate/mid-call native close')
            closed+=1
        wr,rd,val,ret=WREG.search(line),RREG.search(line),VALUE.search(line),RETURN.search(line)
        if wr or rd:
            if closed or pending: raise ValueError('post-close/overlapping native AP call')
            pending=['write',wr[1],int(wr[2],16),int(wr[3],16),None,None] if wr else ['read',rd[1],int(rd[2],16),None,None,None]
        elif val and pending and pending[0]=='read':
            if pending[4] is not None: raise ValueError('duplicate native AP read value')
            pending[4]=int(val[1],16)
        elif ret and pending:
            pending[5]=int(ret[1])
            if pending[5]<0 or (pending[0]=='read' and pending[4] is None) or tuple(pending)!=next(expected,None):
                raise ValueError('native AP/journal mismatch or failure')
            operation,port,reg,value,data,_=pending
            if operation=='write':
                if port=='DP':
                    if reg==2 and value in (0,0xf0): bank=value
                    elif reg==1 and value in (0,0x40,0x10000000,0x10000040,0x50000000,0x50000040): pass
                    else: raise ValueError('DP write scope')
                elif reg==0 and bank==0:
                    if value not in (metadata['ap_csw'],(metadata['ap_csw']&~0x37)|0x12): raise ValueError('AP CSW scope')
                    csw=value
                elif reg==1 and bank==0:
                    if value!=metadata['original_tar'] and not read_allowed(value) and not write_allowed(value,None):
                        raise ValueError('TAR outside independently admitted read/write scope')
                    tar=value
                elif reg==3 and bank==0 and tar is not None and csw&0x37==0x12 and write_allowed(tar,value):
                    writes+=1
                    tar=next_tar(tar)
                else: raise ValueError('AP target write scope')
            else:
                if port=='DP':
                    if reg not in (0,1): raise ValueError('DP read scope')
                elif reg in (0,1) and bank==0: pass
                elif reg==3 and bank==0:
                    if tar is None or csw&0x37!=0x12 or not read_allowed(tar): raise ValueError('target read scope')
                    reads+=1
                    tar=next_tar(tar)
                elif not (reg==3 and bank==0xf0): raise ValueError('AP identity read scope')
            count+=1
            pending=None
        elif re.search(r'JLINK\w*_(?:Write|CORESIGHT_Write)',line):
            raise ValueError('unrecognized native write')
    if pending or next(expected,None) is not None or closed!=1:
        raise ValueError('incomplete native/journal closure')
    if tar!=metadata['original_tar'] or csw!=metadata['ap_csw']:
        raise ValueError('AP state not restored')
    return dict(native_calls=count,target_reads=reads,target_writes=writes,native_close=closed)
