import contextlib
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
sys.path.insert(0,str(ROOT/'tests/boot'))
import p34_recovery_preflight as run
import test_p34_control_probe as controls

BOOT=(ROOT/'.cache/p34-native-acquire1/boot-readback.bin').read_bytes()
APP=(ROOT/'.cache/p34-native-image1/app-readback.bin').read_bytes()
ENVELOPE=(ROOT/'.cache/p34-finalized-reader-device1/readback.bin').read_bytes()+bytes(i%251 for i in range(964))


class Port:
    def __init__(self,fault=None):
        self.fault=fault;self.chunks=0;self.calls=[]
    def read32(self,address):
        self.calls.append((address,4))
        if address==run.flash.DHCSR: return 0x10001|(0x02000000 if self.fault=='reset' and self.chunks>3 else 0)
        if address==run.VTOR: return run.START
        if address in (run.STATE,run.ISR): return int(self.fault=='active')
        return int(self.fault=='metadata' and self.chunks>3)
    def read_bytes(self,address,size):
        self.chunks+=1;self.calls.append((address,size))
        if self.fault=='short': return b''
        source=BOOT+ENVELOPE
        offset=address-0x08000000
        data=source[offset:offset+size]
        if self.fault=='changed' and address==run.START: data=bytes([data[0]^1])+data[1:]
        return data


class PreflightTests(unittest.TestCase):
    def test_complete_original_prefix_and_exact_964b_supplement(self):
        port=Port();saved=[]
        data=run.acquire(port,BOOT,APP,lambda n,o,r:saved.append((n,o,r)))
        self.assertEqual(data['boot'],BOOT)
        self.assertEqual(data['envelope'],ENVELOPE)
        self.assertEqual(data['collateral'],ENVELOPE[619580:])
        self.assertEqual(len(data['collateral']),964)
        self.assertFalse(data['write_admitted'])
        self.assertEqual(b''.join(r for n,o,r in saved if n=='envelope'),ENVELOPE)
        self.assertTrue(all(a in run.READS and a+s-4 in run.READS for a,s in port.calls))

    def test_reset_active_short_changed_and_metadata_fail_closed(self):
        for fault in ('reset','active','short','changed','metadata'):
            with self.subTest(fault=fault):
                port=Port(fault)
                with self.assertRaises(ValueError): run.acquire(port,BOOT,APP)
                if fault=='active': self.assertEqual(port.chunks,0)

    def test_invalid_expected_image_rejects_before_target_io(self):
        port=Port()
        with self.assertRaises(ValueError): run.acquire(port,BOOT,APP[:-1])
        self.assertFalse(port.calls)

    def test_completed_chunk_is_saved_before_late_reset_rejection(self):
        saved=[]
        with self.assertRaises(ValueError): run.acquire(Port('reset'),BOOT,APP,lambda n,o,r:saved.append((n,o,r)))
        self.assertTrue(saved)
        self.assertTrue(all(type(r)is bytes and r for n,o,r in saved))

    def run_worker(self,fault=None):
        store=run.cli.Store(ROOT)
        out=store.checked(Path(os.environ['P34_TEST_OUT'])/('worker-model-'+(fault or 'ok')))
        run.preflight(store,out)
        store.write(out/'plan.json',dict(out=str(out),inputs=[run.cli.record(p) for p in run.SOURCES],
                                        native_history_approved=str(run.base.HISTORY)))
        sdk=controls.SDK()
        sdk.JLINKARM_ExecCommand.callback=lambda command,*args: int(command==b'InhibitConnectRetries = 1')
        for address in run.META: sdk.memory[address]=0
        sdk.memory[run.flash.DHCSR]=0x10001
        sdk.memory[run.VTOR]=run.START
        sdk.memory[run.STATE]=sdk.memory[run.ISR]=0
        blob=BOOT+ENVELOPE
        for i in range(0,len(blob),4):
            sdk.memory[0x08000000+i]=int.from_bytes(blob[i:i+4],'little')
        original=run.Words
        def words(*a,**k): return original(*a,guard=lambda fn,*v,**kw:fn(*v),**k)
        original_budget=run.reader_seconds
        def budget(deadline):
            if fault=='budget': raise ValueError('insufficient prequalified capture budget after connection')
            return original_budget(deadline)
        original_open=Path.open
        closed=[]
        class Stream:
            def __init__(self,stream,name): self.stream,self.name=stream,name
            def __getattr__(self,name): return getattr(self.stream,name)
            def close(self):
                self.stream.close();closed.append(self.name)
                if fault=='close' and self.name=='boot.bin': raise OSError('injected archive close error')
        def opened(path,*a,**k):
            stream=original_open(path,*a,**k)
            return Stream(stream,path.name) if path.parent==out and path.name in ('boot.bin','envelope.bin') and a==('xb',) else stream
        with mock.patch.object(run.base,'in_job',return_value=True), \
             mock.patch.object(run.base,'native_presence',return_value=dict(debugger_processes=[])), \
             mock.patch.object(run.base,'guarded',return_value=sdk), \
             mock.patch.object(run.os,'add_dll_directory',return_value=contextlib.nullcontext()), \
             mock.patch('recovery_entry.native_probe.guarded',side_effect=lambda fn,*a,**k:fn(*a)), \
             mock.patch.object(run,'Words',side_effect=words),mock.patch.object(Path,'open',opened), \
             mock.patch.object(run,'reader_seconds',side_effect=budget):
            self.assertEqual(run.worker(store,out),1 if fault else 0)
        result=store.read(out/'worker.json')
        return result,sdk,out,closed

    def test_owned_native_worker_writes_only_project_archives_not_target_data(self):
        result,sdk,out,_=self.run_worker()
        self.assertEqual(result['result'],'FLASH_PREFLIGHT_CAPTURED_NOT_WRITE_ADMITTED')
        self.assertTrue(result['close_returned'])
        self.assertEqual((out/'collateral.bin').read_bytes(),ENVELOPE[619580:])
        self.assertFalse(any(n=='JLINKARM_CORESIGHT_WriteAPDPReg' and a[:2]==(3,1) for n,a in sdk.calls))

    def test_archive_close_error_still_closes_native_once_and_other_streams(self):
        result,sdk,_,closed=self.run_worker('close')
        self.assertEqual(result['result'],'FAILED')
        self.assertTrue(result['close_returned'])
        self.assertEqual(result['archive_close_errors'][0]['name'],'boot')
        self.assertEqual(closed,['boot.bin','envelope.bin'])
        self.assertEqual(sum(n=='JLINKARM_Close' for n,a in sdk.calls),1)

    def test_common_deadline_deducts_connection_and_never_starts_without_budget(self):
        self.assertEqual(run.reader_seconds(330,clock=lambda:10),300)
        self.assertEqual(run.reader_seconds(330,clock=lambda:60),270)
        for now in (91,330,400):
            with self.assertRaises(RuntimeError): run.reader_seconds(330,clock=lambda:now)
        result,sdk,out,closed=self.run_worker('budget')
        self.assertEqual(result['result'],'FAILED')
        self.assertTrue(result['close_returned'])
        self.assertFalse((out/'envelope.bin').exists())
        self.assertEqual(closed,[])

    def fixture(self):
        rows=[]
        class Recorded(Port):
            def read32(self,address):
                value=super().read32(address)
                rows.append(dict(event='recovery-word-read',address=address,value=value))
                return value
            def read_bytes(self,address,size):
                rows.append(dict(event='recovery-chunk-read-attempt',address=address,bytes=size))
                value=super().read_bytes(address,size)
                rows.append(dict(event='recovery-chunk-read-returned',address=address,data_hex=value.hex()))
                return value
        run.acquire(Recorded(),BOOT,APP)
        rows.extend((dict(event='attempt',operation='close'),dict(event='returned',operation='close')))
        return rows,dict(ap_csw=0x23000052,original_tar=0x12345678)

    def sdk_lines(self,rows,close=True):
        returned='T0000 000:000.000 - 0.100ms returns 0\n'
        for row in rows:
            if row['event']=='recovery-word-read':
                address=row['address'];raw=row['value'].to_bytes(4,'little')
            elif row['event']=='recovery-chunk-read-returned':
                address=row['address'];raw=bytes.fromhex(row['data_hex'])
            else: continue
            yield f'JLINK_CORESIGHT_WriteAPDPReg(AP reg 0x01, 0x{address:08X})\n'
            yield returned
            for i in range(0,len(raw),4):
                yield 'JLINK_CORESIGHT_ReadAPDPReg(AP reg 0x03)\n'
                yield f'Value=0x{int.from_bytes(raw[i:i+4],"little"):08X}\n'
                yield returned
        yield 'JLINK_CORESIGHT_WriteAPDPReg(AP reg 0x01, 0x12345678)\n'
        yield returned
        if close: yield 'JLINK_Close()\n'

    def test_sdk_audit_full_positive_and_forbidden_high_level_or_drw(self):
        import itertools
        rows,meta=self.fixture()
        result=run.scan_trace(self.sdk_lines(rows),iter(rows),meta,BOOT,ENVELOPE)
        self.assertEqual(result['memory_words'],176988)
        self.assertEqual(result['counts'],dict(chunk=672,word=5420,close_attempt=1,close_returned=1))
        for line in ('JLINK_Halt()','JLINK_Reset()','JLINK_Connect()',
                     'JLINK_CORESIGHT_WriteAPDPReg(AP reg 0x03, 0x00000000)'):
            with self.assertRaises((ValueError,RuntimeError)):
                run.scan_trace(itertools.chain([line],self.sdk_lines(rows)),iter(rows),meta,BOOT,ENVELOPE)

    def test_sdk_audit_rejects_owner_chunk_archive_and_close_corruption(self):
        rows,meta=self.fixture()
        for fault in ('owner','missing-attempt','changed-chunk','dropped-guard','archive','close'):
            with self.subTest(fault=fault):
                changed=[dict(row) for row in rows]
                envelope=ENVELOPE
                if fault=='owner':
                    next(r for r in changed if r['event']=='recovery-word-read' and r['address']==run.flash.DHCSR)['value']|=0x20000
                if fault=='missing-attempt':
                    changed.remove(next(r for r in changed if r['event']=='recovery-chunk-read-attempt'))
                if fault=='changed-chunk':
                    next(r for r in changed if r['event']=='recovery-chunk-read-returned')['data_hex']='00'*96
                if fault=='dropped-guard':
                    changed.remove(next(r for r in changed if r['event']=='recovery-word-read' and r['address']==run.STATE))
                if fault=='archive': envelope=bytes([ENVELOPE[0]^1])+ENVELOPE[1:]
                with self.assertRaises(RuntimeError):
                    run.scan_trace(self.sdk_lines(changed,close=fault!='close'),iter(changed),meta,BOOT,envelope)

    def test_audit_requires_successful_worker_close_before_reading_trace(self):
        store=run.cli.Store(ROOT)
        out=store.checked(Path(os.environ['P34_TEST_OUT'])/'audit-closed-gate')
        store.write(out/'plan.json',dict(inputs=[run.cli.record(p) for p in run.SOURCES],before_history=[]))
        store.write(out/'parent.json',dict(exit=0,timeout=False,after_history=[]))
        store.write(out/'worker.json',dict(result='FAILED',close_returned=False,reset_seen=False))
        with self.assertRaises(RuntimeError): run.audit(store,out)


if __name__=='__main__': unittest.main()
