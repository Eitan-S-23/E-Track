import copy
import ctypes
import io
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
sys.path.insert(0, str(ROOT/'tests/boot'))
import p34_online_log_probe as run
from test_p34_native_probe import SDK
from test_p34_mutation_audit import MemoryPath, record


class PathModel(MemoryPath):
    def open(self, mode='r', **kwargs):
        return io.BytesIO(self.data.encode('utf-8')) if 'b' in mode else io.StringIO(self.data)


class LoggingSDK(SDK):
    def __init__(self, paths, fault=None):
        super().__init__()
        self.dp, self.tar = 0x40, 0xe000ef38
        self.paths, self.fault = paths, fault
        self.path = None
        self.wrapped = set()
        self.target_accesses = 0
        self.switches = 0

    def log(self, text):
        if self.path is not None and not (self.fault == 'new-empty' and self.path is self.paths[1]):
            self.path.data += text

    def __getattr__(self, name):
        function = super().__getattr__(name)
        if name not in self.wrapped:
            old = function.callback
            def invoke(*args):
                if name == 'JLINKARM_SetLogFile':
                    self.log('JLINK_SetLogFile()\n')
                    self.log('T5270 000:115.893 Closed\n')
                    selected = [p for p in self.paths if str(p).encode('ascii') == args[0]]
                    assert len(selected) == 1
                    self.path = selected[0]
                    self.switches += 1
                    return None
                if name == 'JLINKARM_ExecCommand':
                    return int(args[0] == b'InhibitConnectRetries = 1')
                if name == 'JLINKARM_Close':
                    self.log('JLINK_Close()\n')
                    if self.fault == 'close': raise OSError('uncertain close')
                    self.log('T565C 097:837.264 Closed\n')
                    return None
                if name in ('JLINKARM_CORESIGHT_ReadAPDPReg', 'JLINKARM_CORESIGHT_WriteAPDPReg'):
                    index, ap = args[:2]
                    read = name.endswith('ReadAPDPReg')
                    if ap == 1 and index == 3 and self.bank == 0:
                        self.target_accesses += 1
                    rc = old(*args)
                    port = 'AP' if ap else 'DP'
                    if read:
                        value = ctypes.cast(args[2], ctypes.POINTER(ctypes.c_uint32))[0]
                        self.log(f'JLINK_CORESIGHT_ReadAPDPReg({port} reg 0x{index:02X})\nValue=0x{value:08X}\n')
                    else:
                        self.log(f'JLINK_CORESIGHT_WriteAPDPReg({port} reg 0x{index:02X}, 0x{args[2]:08X})\n')
                    self.log(f'T0000 000:000.000 - 0.1ms returns {rc}\n')
                    return rc
                return old(*args)
            function.callback = invoke
            self.wrapped.add(name)
        return function


def session(fault=None):
    paths = [PathModel(name, '') for name in ('sdk-000.log', 'sdk-001.log')]
    sdk = LoggingSDK(paths, fault)
    rows, initial = [], []
    def persist(event, **fields): rows.append(dict(event=event, **fields))
    def collect(event, **fields):
        persist(event, **fields)
        initial.append(dict(event=event, **fields))
    with mock.patch('recovery_entry.native_probe.guarded', side_effect=lambda fn,*a,**kw:fn(*a)):
        dap = run.base.Dap(sdk, paths[0], 'unused-project-model.jlink', io.BytesIO())
        dap.sdk = run.JournalSDK(sdk, collect)
        observation = run.base.Observation(dap, collect, seconds=90)
        result = run.execute(dap, observation, persist, initial, paths, record, lambda:90)
    return result, rows, paths, sdk


class Tests(unittest.TestCase):
    def test_real_native_dap_observation_and_online_gate_close_without_target_access(self):
        result, rows, paths, sdk = session()
        self.assertEqual(result['result'], 'ONLINE_LOG_AP_ONLY_CLOSED', result)
        trace = run.audit_trace(paths, rows, result['dap'], record, result['close_returned'])
        self.assertEqual((trace['target_reads'], trace['target_writes'], trace['native_close']), (0, 0, 1))
        self.assertEqual(trace['native_calls'], result['native_calls'])
        self.assertEqual(sdk.target_accesses, 0)
        self.assertEqual(sdk.switches, 2)  # Initial redirection plus one live switch.
        forbidden = {'JLINKARM_Connect', 'JLINKARM_ReadMemEx', 'JLINKARM_Reset', 'JLINKARM_Halt', 'JLINKARM_Go'}
        self.assertFalse(forbidden & {name for name, _ in sdk.calls})
        self.assertEqual((sdk.dp, sdk.tar, sdk.csw), (0x40, 0xe000ef38, 0x23000052))

    def test_failed_new_sink_closes_once_without_target_access_or_false_restore(self):
        result, _, _, sdk = session('new-empty')
        self.assertEqual(result['result'], 'FAILED')
        self.assertTrue(result['close_returned'])
        self.assertFalse(result['dap']['tar_restored'])
        self.assertIsNotNone(result['native_ap_error'])
        self.assertEqual(sdk.target_accesses, 0)
        self.assertEqual(sum(name == 'JLINKARM_Close' for name, _ in sdk.calls), 1)
        self.assertEqual(sdk.switches, 2)

    def test_uncertain_native_close_does_not_retry_or_report_success(self):
        result, _, _, sdk = session('close')
        self.assertEqual(result['result'], 'FAILED')
        self.assertFalse(result['close_returned'])
        self.assertIn('close_error', result)
        self.assertEqual(sum(name == 'JLINKARM_Close' for name, _ in sdk.calls), 1)

    def test_offline_raw_head_and_final_evidence_mutations_reject(self):
        original, rows, paths, _ = session()
        for fault in ('head-hash', 'head-sequence', 'head-count', 'close-marker', 'native-value', 'split'):
            with self.subTest(fault=fault):
                changed = copy.deepcopy(rows)
                files = [PathModel(str(p), p.data) for p in paths]
                head = next(row for row in changed if row['event'] == 'online-log-head-verified')
                if fault == 'head-hash': head['record']['sha256'] = '0'*64
                if fault == 'head-sequence': head['trace']['sequence'] += 1
                if fault == 'head-count': head['trace']['native_calls'] = 2
                if fault == 'close-marker': files[1].data = files[1].data.replace('T565C 097:837.264 Closed\n', '')
                if fault == 'native-value': files[1].data = files[1].data.replace('Value=0xF0000040', 'Value=0xF0000000', 1)
                if fault == 'split': changed = [row for row in changed if row['event'] != 'online-log-switch-returned']
                with self.assertRaises((ValueError, RuntimeError)):
                    run.audit_trace(files, changed, original['dap'], record, True)


if __name__ == '__main__': unittest.main()
