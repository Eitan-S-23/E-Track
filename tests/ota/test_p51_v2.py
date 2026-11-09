"""V2 automation admission, actual telemetry and restore-byte negative tests."""
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota/p51-acceptance'))
import benchmark
import run
import v2
h = v2.h


class WireTests(unittest.TestCase):
    def test_live_plan_rejects_legacy_before_reading_artifacts(self):
        for protocol in (1, None, True, '2'):
            with self.subTest(protocol=protocol), patch.object(h, 'pinned') as files:
                with self.assertRaisesRegex(RuntimeError, 'V2-only execution'):
                    run.validate_live(dict(firmware=dict(protocol=protocol),
                        benchmark=dict(wire='v2-only', link=v2.PROFILE)))
                files.assert_not_called()

    def test_unqualified_live_input_cannot_open_output_or_device_owner(self):
        argv = ['run.py', 'long', '--inputs', 'old.json', '--out', '.cache/not-created',
                '--contract', 'old-contract.json', '--matrix', 'old-matrix.json', '--command-id', 'LONG']
        with patch.object(sys, 'argv', argv), patch.object(h, 'read_json', return_value=dict(firmware=dict(protocol=1))), \
                patch.object(h, 'fresh') as output, patch.object(h, 'device_owner') as device, \
                patch.object(run, 'gate') as gate, self.assertRaises(RuntimeError):
            run.main()
        output.assert_not_called()
        device.assert_not_called()
        gate.assert_not_called()

    def test_v2_requires_declaration_not_just_changing_protocol_number(self):
        for config in ({}, dict(wire='v2-only'), dict(wire='v2-only', link={**v2.PROFILE, 'windowSegments': 32})):
            with self.subTest(config=config), self.assertRaises(RuntimeError):
                v2.live_plan(dict(firmware=dict(protocol=2), benchmark=config))

    def test_clock_only_does_not_require_a_new_device_binding(self):
        argv = ['run.py', 'clock', '--inputs', 'old.json', '--out', '.cache/not-created',
                '--contract', 'old-contract.json', '--matrix', 'old-matrix.json', '--command-id', 'CLOCK']
        with patch.object(sys, 'argv', argv), patch.object(h, 'read_json', return_value={}), \
                patch.object(run, 'validate', return_value={}) as offline, \
                patch.object(run, 'validate_live') as live, \
                patch.object(h, 'fresh', side_effect=RuntimeError('stop before clock')), \
                self.assertRaisesRegex(RuntimeError, 'stop before clock'):
            run.main()
        offline.assert_called_once()
        live.assert_not_called()

    def test_actual_events_reject_v1_bitmap_and_unnegotiated_data(self):
        row = dict(protocol=2, bitmap=None, session=7, event='beginAck')
        self.assertEqual(v2.states([row]), [row])
        for delta in ({'protocol': 1}, {'protocol': None}, {'bitmap': 0}, {'session': 0},
                      {'session': 256}, {'protocol': True}):
            with self.subTest(delta=delta), self.assertRaises(RuntimeError):
                v2.states([{**row, **delta}])
        self.assertEqual(v2.states([dict(protocol=None, bitmap=None, session=0, event='identity')])[0]['protocol'], None)

    def test_runtime_pump_checks_new_wire_events_not_only_final_state(self):
        driver = object.__new__(benchmark.Observer)
        driver.stream_capture = driver.cursor = object()
        driver.live = []
        driver.pump_stream = lambda: driver.live.append(dict(protocol=1, bitmap=0, session=1, event='data'))
        with self.assertRaisesRegex(RuntimeError, 'V1'):
            driver.pump()

    def test_retired_control_and_prefix_probe_rejected(self):
        for command in range(1, 5):
            group = dict(label='upgrade', summary=dict(transfer={}), lines=[
                'OTA_LINK_SAMPLE label=upgrade kind=control_start us=1 cmd=%d session=1 seq=1 bytes=10' % command])
            with self.subTest(command=command), self.assertRaisesRegex(RuntimeError, 'V1 command'):
                v2.diagnostics([group])
        with self.assertRaisesRegex(RuntimeError, 'prefix probe'):
            v2.diagnostics([dict(label='prefix-probe', lines=[], summary={})])

    def test_new_service_versions_come_from_the_bound_pair(self):
        plan = dict(mcu=dict(package={}), phone=dict(app=dict(version_code=100)),
            firmware=dict(current=dict(version=30321), target=dict(version=30322), release_id='p51-benchmark-30321-30322'))
        result = benchmark.network_plan(plan)['reference_service']
        self.assertEqual((result['baseVersion'], result['targetVersion'], result['releaseId']),
                         (30321, 30322, 'p51-benchmark-30321-30322'))


class RestoreTests(unittest.TestCase):
    def setUp(self):
        parent = h.checked(Path(os.environ['P51_TEST_AREA']))
        parent.mkdir(parents=True, exist_ok=True)
        self.out = h.checked(Path(tempfile.mkdtemp(prefix='v2-restore-', dir=parent)))
        self.index = 0

    def pin(self, name, data):
        self.index += 1
        path = h.checked(self.out / ('%03d-' % self.index + name))
        h.raw(path, data)
        return h.record(path)

    def fixture(self):
        base, target, restore = (bytearray(0x600) for _ in range(3))
        struct.pack_into('<I', base, 0x408, 30321)
        struct.pack_into('<I', target, 0x408, 30322)
        struct.pack_into('<I', restore, 0x408, 30322)
        boot = b'host-only synthetic Boot'
        restore[0x460:0x470] = struct.pack('<4I', 30322, 30321, len(base), zlib.crc32(base))
        restore[0x470:0x490] = hashlib.sha256(base).digest()
        restore[0x490:0x4b0] = hashlib.sha256(boot).digest()
        image = dict(image=self.pin('restore.bin', restore), elf=self.pin('restore.elf', b'fake-elf'),
                     map=self.pin('restore.map', b'fake-map'))
        header = self.pin('bindings.h', b'host fixture only')
        compiled = self.pin('raw.bin', restore)
        build = dict(result='APP_BUILT', variant='restore', boot_built=False,
            restore_bindings=header, artifacts=[compiled, image['elf'], image['map']])
        binding = dict(schema='p51-v2-restore-binding-v1', base=self.pin('base.bin', base),
            target=self.pin('target.bin', target), boot=self.pin('boot.bin', boot), restore=image,
            build=self.pin('build.json', json.dumps(build).encode()), bindings_header=header)
        return binding, restore

    def plan(self, binding):
        return dict(benchmark=dict(restore_binding=self.pin('binding.json', json.dumps(binding).encode())),
            mcu=dict(boot=binding['boot'], images=dict(base=dict(image=binding['base']),
                target=dict(image=binding['target']), restore=binding['restore'])))

    def test_matching_compiled_backup_binding(self):
        binding, _ = self.fixture()
        self.assertEqual(v2.restore_binding(self.plan(binding)), binding)

    def test_old_versions_hashes_and_modified_program_cannot_be_restored(self):
        for offset in (0x408, 0x460, 0x464, 0x468, 0x46c, 0x470, 0x490, 0x4d0):
            binding, raw = self.fixture()
            raw[offset] ^= 1
            binding['restore']['image'] = self.pin('mutated.bin', raw)
            with self.subTest(offset=offset), self.assertRaises(RuntimeError):
                v2.restore_binding(self.plan(binding))

    def test_wrong_header_source_and_old_compiler_evidence_rejected(self):
        binding, _ = self.fixture()
        binding['bindings_header'] = self.pin('wrong.h', b'old receiver')
        with self.assertRaises(RuntimeError):
            v2.restore_binding(self.plan(binding))


if __name__ == '__main__':
    unittest.main()
