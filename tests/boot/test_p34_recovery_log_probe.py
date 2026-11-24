import contextlib
import itertools
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
sys.path.insert(0,str(ROOT/'tests/boot'))
import p34_recovery_log_probe as run
from recovery_confirm.log_segments import Segments,rotation_events,checked_records,checked_lines
import test_p34_recovery_preflight as fixture
import test_p34_control_probe as controls


class SegmentTests(unittest.TestCase):
    def model(self):
        paths=tuple('log-%d'%i for i in range(6))
        records={p:dict(path=p,bytes=10,sha256='mock-'+p) for p in paths}
        calls=[];events=[]
        segment=Segments(paths,calls.append,lambda p:dict(records[p]),
                         lambda e,**k:events.append(dict(event=e,**k)))
        return segment,calls,events,records

    def test_six_segments_exact_order_one_finish(self):
        segment,calls,events,records=self.model()
        for _ in range(5): segment.rotate()
        result=segment.finish(True)
        self.assertEqual(calls,list(segment.paths[1:]))
        rotation_events(events)
        checked_records(segment.paths,result,lambda p:records[p])
        for operation in (segment.rotate,lambda:segment.finish(True)):
            with self.assertRaises(ValueError): operation()
        self.assertEqual(len(calls),5)

    def test_switch_failure_latches_without_retry_or_seal(self):
        segment,calls,events,_=self.model()
        def fail(path): calls.append(path);raise OSError('unknown delivery')
        segment.switch=fail
        with self.assertRaises(OSError): segment.rotate()
        with self.assertRaises(ValueError): segment.rotate()
        with self.assertRaises(ValueError): segment.finish(True)
        self.assertEqual(len(calls),1)
        self.assertFalse(segment.sealed)
        with self.assertRaises(ValueError): rotation_events(events)

    def test_native_close_missing_and_sealed_content_changed(self):
        for fault in ('close','changed','empty','oversize'):
            with self.subTest(fault=fault):
                segment,_,_,records=self.model()
                for _ in range(5): segment.rotate()
                if fault=='changed': records['log-0']['sha256']='changed'
                if fault=='empty': records['log-5']['bytes']=0
                if fault=='oversize': records['log-5']['bytes']=16*1024*1024+1
                with self.assertRaises(ValueError): segment.finish(fault!='close')

    def test_duplicate_paths_missing_reordered_and_extra_rotation(self):
        with self.assertRaises(ValueError): Segments(['a']*6,None,None,None)
        segment,_,events,records=self.model()
        for _ in range(5): segment.rotate()
        for rows in (events[:-1],list(reversed(events)),events+events[-2:]):
            with self.assertRaises(ValueError): rotation_events(rows)
        result=segment.finish(True)
        for rows in (result[:-1],list(reversed(result))):
            with self.assertRaises(ValueError): checked_records(segment.paths,rows,lambda p:records[p])

    def test_boundary_snapshot_rejects_changed_dp_csw_tar_and_expired_budget(self):
        class Dap:
            word_csw=0x23000052
            def __init__(self,changed=None): self.changed=changed;self.switched=False;self.calls=[]
            def _read_reg(self,index,ap):
                self.calls.append(('read',index,ap))
                value={(1,0):0xf0000040,(0,1):self.word_csw,(1,1):0x08030000}[(index,ap)]
                return value^1 if self.switched and self.changed==(index,ap) else value
            def _call(self,*args): self.calls.append(args);self.switched=True
        for changed in (None,(1,0),(0,1),(1,1)):
            dap=Dap(changed);rows=[]
            action=lambda:run.rotate_dap(dap,Path('log'),lambda e,**k:rows.append(k),lambda:30)
            if changed:
                with self.assertRaises(RuntimeError): action()
            else:
                action();self.assertEqual(rows[0]['before'],rows[0]['after'])
            self.assertEqual(sum(c[0]=='JLINKARM_SetLogFile' for c in dap.calls),1)
        dap=Dap()
        with self.assertRaises(RuntimeError): run.rotate_dap(dap,Path('log'),lambda *a,**k:None,lambda:4)
        self.assertFalse(dap.calls)

    def test_strict_original_scanner_accepts_ordered_native_segments_not_dropped_or_reset(self):
        case=fixture.PreflightTests()
        rows,meta=case.fixture()
        lines=list(case.sdk_lines(rows))
        cuts=[0,*[len(lines)*i//6 for i in range(1,6)],len(lines)]
        segments=[lines[a:b] for a,b in zip(cuts,cuts[1:])]
        trace=run.prior.scan_trace(itertools.chain.from_iterable(segments),iter(rows),meta,fixture.BOOT,fixture.ENVELOPE)
        self.assertEqual(trace['memory_words'],176988)
        for bad in (segments[:-1],list(reversed(segments)),[segments[0],['JLINK_Reset()'],*segments[1:]]):
            with self.assertRaises((ValueError,RuntimeError)):
                run.prior.scan_trace(itertools.chain.from_iterable(bad),iter(rows),meta,fixture.BOOT,fixture.ENVELOPE)

    def segmented_fixture(self):
        case=fixture.PreflightTests()
        original,meta=case.fixture()
        rows=[];logs=[[]];count=0
        values=[0xf0000040,0x23000052,0x08010000]
        def boundary():
            lines=[]
            for port,reg,value in zip(('DP','AP','AP'),(1,0,1),values):
                lines.extend((f'JLINK_CORESIGHT_ReadAPDPReg({port} reg 0x{reg:02X})\n',
                              f'Value=0x{value:08X}\n','T0000 000:000.000 - 0.100ms returns 0\n'))
            return lines
        for row in original:
            rows.append(row)
            logs[-1].extend(list(case.sdk_lines([row]))[:-3])
            if row['event']=='recovery-chunk-read-returned' and len(row['data_hex'])==2048:
                count+=1
                if count%128==0:
                    index=len(logs)-1
                    rows.append(dict(event='sdk-log-switch-attempt',old=index,new=index+1))
                    logs[-1].extend(boundary())
                    logs.append(boundary())
                    rows.append(dict(event='sdk-log-state',before=values,after=values,started=1,ended=2))
                    rows.append(dict(event='sdk-log-switch-returned',old=index,new=index+1))
        logs[-1].extend(list(case.sdk_lines([])))
        return logs,rows,meta

    def test_segment_boundaries_bind_native_state_and_complete_frame_counts(self):
        logs,rows,meta=self.segmented_fixture()
        trace=run.prior.scan_trace(checked_lines(logs,rows),iter(rows),meta,fixture.BOOT,fixture.ENVELOPE)
        self.assertEqual(trace['memory_words'],176988)
        for fault in ('half-call','half-frame','state','missing-state'):
            with self.subTest(fault=fault):
                changed=[list(log) for log in logs]
                events=[dict(row) for row in rows]
                if fault=='half-call': changed[1].insert(0,changed[0].pop())
                if fault=='half-frame':
                    changed[1][:0]=changed[0][-12:];del changed[0][-12:]
                if fault=='state': changed[1][1]='Value=0xF0000041\n'
                if fault=='missing-state': events.remove(next(r for r in events if r['event']=='sdk-log-state'))
                with self.assertRaises((ValueError,RuntimeError)):
                    run.prior.scan_trace(checked_lines(changed,events),iter(events),meta,fixture.BOOT,fixture.ENVELOPE)

    def worker(self,fault=None):
        store=run.cli.Store(ROOT)
        out=store.checked(Path(os.environ['P34_TEST_OUT'])/('worker-'+(fault or 'ok')))
        run.preflight(store,out)
        store.write(out/'plan.json',dict(out=str(out),inputs=[run.cli.record(p) for p in run.SOURCES],
                                      native_history_approved=str(run.base.HISTORY)))
        sdk=controls.SDK()
        sdk.JLINKARM_ExecCommand.callback=lambda command,*a:int(command==b'InhibitConnectRetries = 1')
        def logfile(path):
            path=Path(path.decode('ascii'))
            store.raw(store.checked(path),b'MOCK SDK LOG: not physical evidence\n')
            if fault=='switch' and path.name==run.LOGS[1]: raise OSError('unknown switch return')
        sdk.JLINKARM_SetLogFile.callback=logfile
        for address in run.prior.META: sdk.memory[address]=0
        sdk.memory[run.prior.flash.DHCSR]=0x10001
        sdk.memory[run.prior.VTOR]=run.prior.START
        sdk.memory[run.prior.STATE]=sdk.memory[run.prior.ISR]=0
        blob=fixture.BOOT+(ROOT/'.cache/p34-recovery-preflight1/envelope.bin').read_bytes()
        for i in range(0,len(blob),4): sdk.memory[0x08000000+i]=int.from_bytes(blob[i:i+4],'little')
        words=run.prior.Words
        with mock.patch.object(run.base,'in_job',return_value=True), \
             mock.patch.object(run.base,'native_presence',return_value=dict(debugger_processes=[])), \
             mock.patch.object(run.base,'guarded',return_value=sdk), \
             mock.patch.object(run.os,'add_dll_directory',return_value=contextlib.nullcontext()), \
             mock.patch('recovery_entry.native_probe.guarded',side_effect=lambda fn,*a,**k:fn(*a)), \
             mock.patch.object(run.prior,'Words',side_effect=lambda *a,**k:words(*a,guard=lambda fn,*v,**kw:fn(*v),**k)):
            self.assertEqual(run.worker(store,out),1 if fault else 0)
        return store.read(out/'worker.json'),sdk,out

    def test_full_native_mock_worker_rotates_without_target_data_write(self):
        result,sdk,out=self.worker()
        self.assertEqual(result['result'],'SEGMENTED_READ_CAPTURED_NOT_WRITE_ADMITTED')
        self.assertEqual(len(result['logs']),6)
        self.assertTrue(result['close_returned'])
        self.assertEqual(sum(n=='JLINKARM_SetLogFile' for n,a in sdk.calls),6)
        self.assertEqual(sum(n=='JLINKARM_Close' for n,a in sdk.calls),1)
        self.assertFalse(any(n=='JLINKARM_CORESIGHT_WriteAPDPReg' and a[:2]==(3,1) for n,a in sdk.calls))

    def test_failed_switch_stops_next_capture_and_still_closes(self):
        result,sdk,out=self.worker('switch')
        self.assertEqual(result['result'],'FAILED')
        self.assertTrue(result['close_returned'])
        self.assertEqual(sum(n=='JLINKARM_SetLogFile' for n,a in sdk.calls),2)
        self.assertEqual(sum(n=='JLINKARM_Close' for n,a in sdk.calls),1)
        self.assertEqual((out/'boot.bin').stat().st_size,65536)
        self.assertEqual((out/'envelope.bin').stat().st_size,65536)


if __name__=='__main__': unittest.main()
