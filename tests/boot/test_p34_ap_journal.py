import ctypes
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
from recovery_confirm.ap_journal import JournalSDK,calls,audit


class SDK:
    def __init__(self): self.calls=[];self.fail=False
    def JLINKARM_CORESIGHT_ReadAPDPReg(self,index,ap,out):
        self.calls.append(('read',index,ap))
        ctypes.cast(out,ctypes.POINTER(ctypes.c_uint32))[0]=0x1234
        return -1 if self.fail else 0
    def JLINKARM_CORESIGHT_WriteAPDPReg(self,index,ap,value):
        self.calls.append(('write',index,ap,value));return 0
    def JLINKARM_Close(self): self.calls.append(('close',))


class Tests(unittest.TestCase):
    def fixture(self):
        sdk=SDK();rows=[];proxy=JournalSDK(sdk,lambda event,**kw:rows.append(dict(event=event,**kw)))
        proxy.JLINKARM_CORESIGHT_WriteAPDPReg(1,1,0x08010000)
        proxy.JLINKARM_CORESIGHT_ReadAPDPReg(3,1,ctypes.byref(ctypes.c_uint32()))
        proxy.JLINKARM_CORESIGHT_WriteAPDPReg(1,1,0xe000edf4)
        proxy.JLINKARM_CORESIGHT_WriteAPDPReg(3,1,15)
        proxy.JLINKARM_CORESIGHT_WriteAPDPReg(1,1,0x12345678)
        metadata=dict(ap_csw=0x23000052,original_tar=0x12345678)
        return proxy,sdk,rows,metadata

    def lines(self,rows):
        for operation,port,reg,value,data,rc in calls(rows):
            if operation=='read':
                yield f'JLINK_CORESIGHT_ReadAPDPReg({port} reg 0x{reg:02X})\n'
                yield f'Value=0x{data:08X}\n'
            else: yield f'JLINK_CORESIGHT_WriteAPDPReg({port} reg 0x{reg:02X}, 0x{value:08X})\n'
            yield f'T0000 000:000.000 - 0.1ms returns {rc}\n'
        yield 'JLINK_Close()\n'

    def scan(self,lines,rows,metadata):
        return audit(lines,rows,metadata,read_allowed=lambda a:a==0x08010000,
                     write_allowed=lambda a,v:a==0xe000edf4 and v in (None,15,16,17,20))

    def test_complete_proxy_calls_match_sdk_and_separate_write_scope(self):
        _,sdk,rows,meta=self.fixture()
        result=self.scan(self.lines(rows),rows,meta)
        self.assertEqual(result,dict(native_calls=5,target_reads=1,target_writes=1,native_close=1))
        self.assertEqual(len(sdk.calls),5)

    def test_negative_native_or_failed_journal_latches_without_second_call(self):
        for fault in ('native','before','after'):
            sdk=SDK();rows=[]
            def emit(event,**kw):
                rows.append(dict(event=event,**kw))
                if (fault=='before' and event.endswith('attempt')) or (fault=='after' and event.endswith('returned')):
                    raise OSError('injected journal failure')
            sdk.fail=fault=='native'
            proxy=JournalSDK(sdk,emit)
            with self.assertRaises(OSError): proxy.JLINKARM_CORESIGHT_ReadAPDPReg(3,1,ctypes.byref(ctypes.c_uint32()))
            count=len(sdk.calls)
            with self.assertRaises(ValueError): proxy.JLINKARM_CORESIGHT_ReadAPDPReg(3,1,ctypes.byref(ctypes.c_uint32()))
            self.assertEqual(count,len(sdk.calls))
            self.assertEqual(count,0 if fault=='before' else 1)

    def test_journal_missing_pair_and_native_value_operation_or_close_corruption(self):
        _,_,rows,meta=self.fixture()
        original=list(self.lines(rows))
        for fault in ('missing-attempt','missing-return','value','register','return','close','post-close','reset','duplicate-value'):
            with self.subTest(fault=fault):
                changed=[dict(row) for row in rows];lines=list(original)
                if fault=='missing-attempt': changed.pop(0)
                if fault=='missing-return': changed.pop()
                if fault=='value': lines=[line.replace('Value=0x00001234','Value=0x00005678') for line in lines]
                if fault=='register': lines[0]=lines[0].replace('reg 0x01','reg 0x03')
                if fault=='return': lines[1]=lines[1].replace('returns 0','returns -1')
                if fault=='close': lines.pop()
                if fault=='post-close': lines+=original[:2]
                if fault=='reset': lines.insert(0,'JLINK_Reset()\n')
                if fault=='duplicate-value': lines.insert(4,lines[3])
                with self.assertRaises(ValueError): self.scan(lines,changed,meta)

    def test_jointly_changed_target_write_or_read_still_needs_independent_scope(self):
        _,_,rows,meta=self.fixture()
        for change in ('write','read','selector'):
            modified=[dict(row) for row in rows]
            if change=='write': modified[4]['value']=0x08010000
            if change=='read': modified[0]['value']=0x08000000
            if change=='selector': modified[6]['value']=0x1000f
            with self.assertRaises(ValueError): self.scan(self.lines(modified),modified,meta)

    def test_original_tar_restore_is_not_permission_to_read_or_write_it(self):
        _,_,rows,meta=self.fixture()
        modified=[dict(row) for row in rows]
        modified[0]['value']=meta['original_tar']
        with self.assertRaises(ValueError): self.scan(self.lines(modified),modified,meta)

    def arbitrary(self,operations):
        rows=[]
        for i,(operation,port,index,value,data) in enumerate(operations,1):
            rows.extend((dict(event='ap-call-attempt',sequence=i,operation=operation,ap=int(port=='AP'),index=index,value=value),
                         dict(event='ap-call-returned',sequence=i,rc=0,read_value=data,started=i,ended=i+.1)))
        return rows

    def test_one_k_boundary_requires_explicit_tar_reload_for_reads_and_writes(self):
        meta=dict(ap_csw=0x23000052,original_tar=0x12345678)
        for operation in ('read','write'):
            for reload in (False,True):
                operations=[('write','AP',1,0x080103fc,None),
                            (operation,'AP',3,15 if operation=='write' else None,0x1234 if operation=='read' else None)]
                if reload: operations.append(('write','AP',1,0x08010000,None))
                operations.extend(((operation,'AP',3,15 if operation=='write' else None,0x1234 if operation=='read' else None),
                                   ('write','AP',1,meta['original_tar'],None)))
                rows=self.arbitrary(operations)
                action=lambda:audit(self.lines(rows),rows,meta,read_allowed=lambda a:a in (0x080103fc,0x08010000),
                                    write_allowed=lambda a,v:a in (0x080103fc,0x08010000) and v in (None,15))
                if reload: self.assertEqual(action()['native_calls'],5)
                else:
                    with self.assertRaises(ValueError): action()

    def test_bank_f0_only_allows_identity_read_not_csw_or_tar(self):
        meta=dict(ap_csw=0x23000052,original_tar=0x12345678)
        for operation in ('read','write'):
            for index in (0,1):
                value=meta['ap_csw'] if index==0 else meta['original_tar']
                rows=self.arbitrary([('write','DP',2,0xf0,None),
                    (operation,'AP',index,value if operation=='write' else None,value if operation=='read' else None),
                    ('write','DP',2,0,None),('write','AP',1,meta['original_tar'],None)])
                with self.assertRaises(ValueError): self.scan(self.lines(rows),rows,meta)
        rows=self.arbitrary([('write','DP',2,0xf0,None),('read','AP',3,None,0x24770011),
                             ('write','DP',2,0,None),('write','AP',1,meta['original_tar'],None)])
        self.assertEqual(self.scan(self.lines(rows),rows,meta)['target_reads'],0)

    def test_invalid_clocks_latch_before_or_after_exactly_one_native_call(self):
        for bad in (float('nan'),float('inf'),-float('inf'),True,None,'1'):
            for phase in ('start','end'):
                sdk=SDK();rows=[];times=iter([bad] if phase=='start' else [1,bad])
                proxy=JournalSDK(sdk,lambda event,**kw:rows.append(dict(event=event,**kw)),clock=lambda:next(times))
                with self.assertRaises((ValueError,OSError)):
                    proxy.JLINKARM_CORESIGHT_ReadAPDPReg(3,1,ctypes.byref(ctypes.c_uint32()))
                self.assertEqual(len(sdk.calls),int(phase=='end'))
                with self.assertRaises(ValueError): proxy.JLINKARM_CORESIGHT_WriteAPDPReg(1,1,0)
                proxy.JLINKARM_Close()
                self.assertEqual(sdk.calls[-1],('close',))
                with self.assertRaises(ValueError): list(calls(rows))
        sdk=SDK();times=iter([1,2,1]);rows=[]
        proxy=JournalSDK(sdk,lambda event,**kw:rows.append(dict(event=event,**kw)),clock=lambda:next(times))
        proxy.JLINKARM_CORESIGHT_WriteAPDPReg(1,1,0)
        with self.assertRaises(ValueError): proxy.JLINKARM_CORESIGHT_WriteAPDPReg(1,1,0)
        self.assertEqual(len(sdk.calls),1)

    def test_auditor_rejects_forged_nonfinite_or_backwards_call_times(self):
        _,_,rows,meta=self.fixture()
        original=list(self.lines(rows))
        for bad in (float('nan'),float('inf'),True,None):
            changed=[dict(row) for row in rows];changed[1]['started']=bad
            with self.assertRaises(ValueError): self.scan(original,changed,meta)
        changed=[dict(row) for row in rows]
        changed[3]['started']=changed[1]['started']-1
        with self.assertRaises(ValueError): self.scan(original,changed,meta)


if __name__=='__main__': unittest.main()
