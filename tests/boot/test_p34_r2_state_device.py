import copy
import ctypes
import io
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
sys.path.insert(0, str(ROOT/'tests/boot'))
import p34_r2_state_device as run
from recovery_confirm import r2_passive_state as passive, r2_ui_binding as ui
from test_p34_online_log_probe import LoggingSDK
from test_p34_r2_checkpoint_device import BinaryBuffer
from test_p34_r2_passive_state import Native as StateMemory
from test_p34_mutation_audit import record
from test_p34_recovery_ports import Clock
from test_p34_r2_checkpoint import MAP


class Native(LoggingSDK):
    def __init__(self, paths, clock, image, fault):
        super().__init__(paths, fault)
        self.clock, self.image = clock, image
        self.special = set()
        self.memory = StateMemory(clock, image, None).memory
        obj, pool = 0x20010000, 0x20040000
        self.memory.update({ui.GUARD: 1, ui.MANAGER+4: pool, ui.MANAGER+8: pool+4,
            ui.MANAGER+12: pool+4, pool: obj, obj: ui.VPTR, ui.COST_ACTIVE: 0,
            **{obj+k: 0 for k in ui.FIELD_OFFSETS.values()}, obj+8: ui.MANAGER, obj+12: ui.NAME})
        if fault == 'busy': self.memory[obj+ui.FIELD_OFFSETS['mode']] = 2
        if fault == 'bad-ui': self.memory[pool] = 0x90000000

    def log(self, text):
        if self.path is not None and not (self.fault == 'new-empty' and self.path is self.paths[1]):
            self.path.append(text)

    def __getattr__(self, name):
        function = super().__getattr__(name)
        if name == 'JLINKARM_CORESIGHT_ReadAPDPReg' and name not in self.special:
            old = function.callback
            def invoke(index, ap, pointer):
                if (index, ap, self.bank) != (3, 1, 0): return old(index, ap, pointer)
                self.target_accesses += 1
                self.clock.value += .00001
                address = self.tar
                if 0x08010000 <= address < 0x08010000+len(self.image):
                    offset = address-0x08010000
                    value = int.from_bytes(self.image[offset:offset+4], 'little')
                    if self.fault == 'image': value ^= 1
                else: value = self.memory[address]
                if self.fault == 'reset' and address == passive.health.DHCSR: value |= 0x02000000
                self.tar += 4
                ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32))[0] = value
                self.log(f'JLINK_CORESIGHT_ReadAPDPReg(AP reg 0x03)\nValue=0x{value:08X}\n')
                self.log('T0000 000:000.000 - 0.1ms returns 0\n')
                return 0
            function.callback = invoke
            self.special.add(name)
        return function


def session(fault=None, dp=0x40):
    image = run.ASSETS['image'].read_bytes()
    clock = Clock()
    paths = [BinaryBuffer(n, '') for n in run.LOGS]
    native = Native(paths, clock, image, fault)
    native.dp = dp
    rows, initial = [], []
    def persist(event, **fields): rows.append(dict(event=event, **fields))
    def collect(event, **fields):
        persist(event, **fields)
        initial.append(dict(event=event, **fields))
    with mock.patch('recovery_entry.native_probe.guarded', side_effect=lambda f, *a, **k: f(*a)):
        dap = run.base.Dap(native, paths[0], ROOT/'.cache/model-only.jlink', io.BytesIO())
        dap.sdk = run.JournalSDK(native, collect, clock=clock)
        obs = run.base.Observation(dap, collect, seconds=120, clock=clock)
        result = run.execute(dap, obs, persist, initial, paths, record, lambda: 180-clock.value,
            image, MAP, clock=clock, sleep=clock.sleep, guard=lambda f, *a, **k: f(*a))
    return result, rows, paths, native


class Tests(unittest.TestCase):
    def assert_close_only(self, native):
        self.assertEqual(sum(n == 'JLINKARM_Close' for n, _ in native.calls), 1)
        self.assertFalse({'JLINKARM_Connect', 'JLINKARM_ReadMemEx', 'JLINKARM_Reset',
            'JLINKARM_Halt', 'JLINKARM_Go'} & {n for n, _ in native.calls})
        self.assertFalse(any(n == 'JLINKARM_CORESIGHT_WriteAPDPReg' and a[:2] == (3, 1) for n, a in native.calls))

    def test_real_native_lifecycle_idle_busy_dp_restore_and_offline_replay(self):
        for fault, dp in ((None, 0x40), ('busy', 0xf0000040)):
            result, rows, paths, native = session(fault, dp)
            self.assertEqual(result['result'], 'R2_STATE_NATIVE_CLOSED', result)
            self.assertEqual(result['state']['unloaded_ui_idle_observed'], fault is None)
            self.assertEqual((native.dp, native.tar, native.csw), (dp, 0xe000ef38, 0x23000052))
            self.assert_close_only(native)
            trace = run.audit_trace(paths, rows, result['dap'], record, True)
            self.assertEqual((trace['target_writes'], trace['native_close']), (0, 1))
            self.assertEqual(trace['logs'], result['logs'])
            self.assertFalse(result['ota_ready'])
            changed = copy.deepcopy(rows)
            next(r for r in changed if r['event'] == 'online-log-head-verified')['record']['sha256'] = '0'*64
            with self.assertRaisesRegex(RuntimeError, 'head changed'):
                run.audit_trace(paths, changed, result['dap'], record, True)
            with self.assertRaises((ValueError, RuntimeError)):
                run.audit_trace(paths, rows, result['dap'], record, False)

    def test_failed_state_or_close_never_promotes_or_retries_close(self):
        for fault in ('new-empty', 'reset', 'image', 'bad-ui', 'close'):
            result, _, _, native = session(fault)
            self.assertEqual(result['result'], 'FAILED', result)
            self.assert_close_only(native)
            self.assertFalse(result.get('native_close_audited', False))
            self.assertEqual(result['close_returned'], fault != 'close')

    def test_fixed_checkpoint_proof_and_changed_evidence_reject(self):
        store = run.cli.Store(ROOT)
        proof = run.predecessor(store)
        self.assertEqual(proof['version'], 30276)
        self.assertFalse(proof['historical_ota_predecessor'])
        saved = run.cli.record
        def corrupt(path):
            value = saved(path)
            return dict(value, sha256='0'*64) if Path(path).name == 'app.bin' else value
        with mock.patch.object(run.cli, 'record', side_effect=corrupt):
            with self.assertRaisesRegex(RuntimeError, 'evidence changed'): run.predecessor(store)

    def fixture(self):
        out = ROOT/'.cache/unused-state-model'
        test = out/'tests/result.json'
        item = dict(path=str(test), bytes=1, sha256='a'*64)
        proof = dict(kind='model')
        plan = dict(out=str(out), scope=run.SCOPE, inputs=[], tests=item, predecessor=proof,
            worker_seconds=180, parent_seconds=240, connection_generation='r2-state-'+out.name,
            before_history=[], native_history_approved=str(run.base.HISTORY))
        return out, test, item, proof, plan

    def test_worker_rejects_job_tests_scope_proof_budget_history_before_loading_native(self):
        store = run.cli.Store(ROOT)
        out, test, item, proof, original = self.fixture()
        plan = original
        tests = dict(result='R2_STATE_DEVICE_HOST_PASS', inputs=[], hardware=False)
        def read(path): return tests if Path(path) == test else plan
        with mock.patch.object(run.base, 'in_job', return_value=False), mock.patch.object(store, 'read') as read_mock:
            with self.assertRaisesRegex(RuntimeError, 'owned state'): run.worker(store, out)
            read_mock.assert_not_called()
        with mock.patch.object(run.base, 'in_job', return_value=True), \
             mock.patch.object(run.base, 'history', return_value=[]), \
             mock.patch.object(store, 'read', side_effect=read), \
             mock.patch.object(run, 'sources', return_value=[]), \
             mock.patch.object(run, 'predecessor', return_value=proof), \
             mock.patch.object(run.cli, 'record', return_value=item), \
             mock.patch.object(run.ctypes, 'CDLL') as load:
            run.validate_worker_plan(store, original, out, [])
            for key, value in (('scope', 'other'), ('inputs', [1]), ('tests', {}), ('predecessor', {}),
                ('worker_seconds', 181), ('parent_seconds', 241), ('connection_generation', 'other'),
                ('before_history', [1]), ('native_history_approved', 'other')):
                plan = dict(original, **{key: value})
                with self.subTest(key=key), self.assertRaises((RuntimeError, KeyError)):
                    run.worker(store, out)
            plan = original
            tests['inputs'] = [1]
            with self.assertRaisesRegex(RuntimeError, 'current state selftests'): run.worker(store, out)
            load.assert_not_called()

    def test_late_outer_failure_preserves_observation_and_one_actual_close(self):
        store = run.cli.Store(ROOT)
        out, _, _, _, plan = self.fixture()
        dap = SimpleNamespace(_opened=True, close_returned=True)
        class Observation:
            closed = False
            native_closes = 0
            def close(self):
                if not self.closed:
                    self.closed = True
                    self.native_closes += 1
        obs = Observation()
        class Directory:
            def __enter__(self): return self
            def __exit__(self, *args): raise OSError('late directory close failure')
        def execute(*args, **kwargs):
            obs.close()
            return dict(result='R2_STATE_NATIVE_CLOSED', close_returned=True, state={'observed': True})
        def opened(path, mode='r', **kwargs):
            self.assertEqual(path.parent, out)
            return io.BytesIO() if 'b' in mode else io.StringIO()
        with mock.patch.object(run.base, 'in_job', return_value=True), \
             mock.patch.object(store, 'read', return_value=plan), \
             mock.patch.object(run, 'sources', return_value=[]), \
             mock.patch.object(run, 'validate_worker_plan'), \
             mock.patch.object(run.cli, 'record', return_value={'sha256': run.base.DLL_SHA}), \
             mock.patch.object(run.base, 'native_presence', return_value={'debugger_processes': []}), \
             mock.patch.object(run.os, 'add_dll_directory', return_value=Directory()), \
             mock.patch.object(run.ctypes, 'CDLL', return_value=object()), \
             mock.patch.object(run.base, 'Dap', return_value=dap), \
             mock.patch.object(run.base, 'Observation', return_value=obs), \
             mock.patch.object(run, 'JournalSDK', return_value=object()), \
             mock.patch.object(run, 'execute', side_effect=execute), \
             mock.patch.object(Path, 'open', new=opened), \
             mock.patch.object(Path, 'read_bytes', return_value=b'model'), \
             mock.patch.object(store, 'write') as save:
            self.assertEqual(run.worker(store, out), 1)
        result = save.call_args.args[1]
        self.assertEqual(result['result'], 'FAILED')
        self.assertTrue(result['state']['observed'])
        self.assertTrue(result['close_returned'])
        self.assertEqual(obs.native_closes, 1)

    def test_current_sources_and_preflight_preserve_existing_area(self):
        store = run.cli.Store(ROOT)
        paths = run.sources(store)
        self.assertIn(run.REVIEW, paths)
        self.assertIn(Path(__file__).resolve(), paths)
        with self.assertRaisesRegex(RuntimeError, 'preserve'): run.preflight(store, run.CHECKPOINT, paths)


if __name__ == '__main__': unittest.main()
