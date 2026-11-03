"""Offline P1-6 binding and native ownership regressions; never accesses a probe."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M = load('p16_matrix_test', 'Tools/jlink/p1_6_matrix.py')
V = load('p16_vectors_test', 'tests/boot/test_fw_header_vectors.py')
E = load('p16_execute_test', 'Tools/acceptance/p16_execute.py')


class MatrixTests(unittest.TestCase):
    def setUp(self):
        parent = M.host.checked(ROOT / '.cache')
        parent.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='p16-matrix-', dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.root = M.host.checked(Path(self.temp.name))
        self.assets = self.root / 'assets'
        self.build = self.root / 'build'
        self.assets.mkdir()
        (self.build / 'boot').mkdir(parents=True)
        (self.build / 'app-gcc').mkdir()
        source = bytearray(0x1000)
        struct.pack_into('<II', source, 0, V.RAM_ORIGIN + 4096, V.APP_ORIGIN + 2049)
        self.source = self.root / 'linked.bin'
        self.source.write_bytes(source)
        (self.build / 'boot/X-Track-Boot.bin').write_bytes(b'host-fixture-not-firmware')
        self.manifest = {}
        for name, code in (('V0-final.bin', 30314), ('V1-final.bin', 30315)):
            raw = source + bytearray(65 * 4096 + 1)
            raw[16 * 4096:] = bytes([code & 255]) * (len(raw) - 16 * 4096)
            data = V.mutate_header(V.finalized(raw), 8, struct.pack('<I', code))
            (self.assets / name).write_bytes(data)
            self.manifest[name] = dict(length=len(data), version_code=code,
                raw_sha256=hashlib.sha256(data).hexdigest(),
                double_zero_sha256=data[V.FW_HEADER_OFFSET + 40:V.FW_HEADER_OFFSET + 72].hex(),
                header_crc32='%08x' % struct.unpack_from('<I', data, V.FW_HEADER_OFFSET + 92)[0])
        self.manifest['policy'] = dict(applyGroup=16, rollbackGroup=1, changedBlock=16,
            applyResume=32, rollbackResume=17, blocks=67, appendedOnlyAfter=len(source),
            payloadSource=M.host.record(self.source),
            bootSha256=hashlib.sha256(b'host-fixture-not-firmware').hexdigest())
        self.save_manifest()
        self.boot_map = self.build / 'boot/X-Track-Boot.map'
        self.app_map = self.build / 'app-gcc/X-Track-App-GCC.map'
        self.boot_map.write_text('.p1_6_control 0x20057e00 0x200\n')
        self.app_map.write_text('.p1_6_control 0x20057e00 0x200\n.p34_runtime_vectors 0x08010800 0x20c\n'
                                ' .text._ZN3HAL10HAL_UpdateEv\n                0x080410c8 0x30 module.obj\n')

    def save_manifest(self):
        (self.assets / 'assets.json').write_text(json.dumps(self.manifest))

    def test_current_versions_and_dynamic_block_count(self):
        bound = M.assets(self.assets, self.build)
        self.assertEqual((bound['v0'], bound['v1'], bound['blocks'], bound['vtor']), (30314, 30315, 67, 0x08010800))
        self.assertEqual((bound['changedBlock'], bound['applyResume'], bound['rollbackResume']), (16, 32, 17))
        self.assertEqual(bound['safeHalt'], 0x080410c8)

    def test_missing_or_ambiguous_idle_halt_symbol_rejected(self):
        text = self.app_map.read_text()
        for value in ('', text + text):
            with self.assertRaisesRegex(RuntimeError, 'HAL_Update'):
                M.idle_symbol(value)

    def test_obsolete_per_block_policy_rejected(self):
        self.manifest['policy']['applyGroup'] = 1
        self.save_manifest()
        with self.assertRaisesRegex(RuntimeError, 'group16'):
            M.assets(self.assets, self.build)

    def test_wrong_group_boundary_rejected(self):
        self.manifest['policy']['applyResume'] = 17
        self.save_manifest()
        with self.assertRaisesRegex(RuntimeError, 'checkpoint mismatch'):
            M.assets(self.assets, self.build)

    def test_changed_body_not_accepted_as_safe_suffix(self):
        source = bytearray(self.source.read_bytes())
        source[-1] ^= 1
        self.source.write_bytes(source)
        self.manifest['policy']['payloadSource'] = M.host.record(self.source)
        self.save_manifest()
        with self.assertRaisesRegex(RuntimeError, 'executable bytes'):
            M.assets(self.assets, self.build)

    def test_wrong_boot_rejected(self):
        (self.build / 'boot/X-Track-Boot.bin').write_bytes(b'wrong')
        with self.assertRaisesRegex(RuntimeError, 'Boot artifact'):
            M.assets(self.assets, self.build)

    def test_manifest_tampering_rejected(self):
        for key in ('length', 'version_code', 'raw_sha256', 'double_zero_sha256', 'header_crc32'):
            with self.subTest(key=key):
                old = self.manifest['V0-final.bin'][key]
                self.manifest['V0-final.bin'][key] = None
                self.save_manifest()
                with self.assertRaisesRegex(RuntimeError, 'manifest mismatch'):
                    M.assets(self.assets, self.build)
                self.manifest['V0-final.bin'][key] = old

    def test_corrupt_image_rejected_even_if_raw_hash_updated(self):
        path = self.assets / 'V1-final.bin'
        data = bytearray(path.read_bytes())
        data[-1] ^= 1
        path.write_bytes(data)
        self.manifest[path.name]['raw_sha256'] = hashlib.sha256(data).hexdigest()
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            M.assets(self.assets, self.build)

    def test_nonforward_pair_rejected(self):
        (self.assets / 'V1-final.bin').write_bytes((self.assets / 'V0-final.bin').read_bytes())
        self.manifest['V1-final.bin'] = self.manifest['V0-final.bin']
        self.save_manifest()
        with self.assertRaisesRegex(RuntimeError, 'advance'):
            M.assets(self.assets, self.build)

    def test_wrong_control_address_or_size_rejected(self):
        for text in ('.p1_6_control 0x20057c00 0x200\n', '.p1_6_control 0x20057e00 0x100\n', ''):
            with self.subTest(text=text):
                self.boot_map.write_text(text)
                with self.assertRaises(RuntimeError):
                    M.assets(self.assets, self.build)

    def test_ambiguous_section_rejected(self):
        text = self.boot_map.read_text()
        self.boot_map.write_text(text + text)
        with self.assertRaisesRegex(RuntimeError, 'ambiguous'):
            M.assets(self.assets, self.build)

    def test_runtime_vtor_checked(self):
        self.app_map.write_text('.p1_6_control 0x20057e00 0x200\n.p34_runtime_vectors 0x08010a00 0x20c\n')
        with self.assertRaisesRegex(RuntimeError, 'runtime vector'):
            M.assets(self.assets, self.build)

    def test_native_outputs_and_selector_owned(self):
        command = self.root / 'capture.jlink'
        command.write_text('savebin "' + str(self.root / 'capture.bin') + '", 0x20000000, 0x20\nqc\n')
        args = SimpleNamespace(log=self.root / 'native.log', commands=command, tool=Path('not-launched.exe'), serial=123456, timeout=20)
        observed = []

        def fake(out, label, argv, env, **kwargs):
            observed.extend(map(str, argv))
            (out / 'commander.stdout').write_bytes(b'partial original\n')
            (out / 'commander.stderr').write_bytes(b'failure original\n')
            raise RuntimeError('injected timeout')

        with patch.object(M.host, 'command', side_effect=fake):
            with self.assertRaisesRegex(RuntimeError, 'injected timeout'):
                M.native(args)
        self.assertEqual(observed[observed.index('-USB') + 1], '123456')
        self.assertIn('-Log', observed)
        self.assertEqual(observed[observed.index('-AutoConnect') + 1], '0')
        self.assertIn('-SettingsFile', observed)
        self.assertEqual(args.log.read_bytes(), b'partial original\nfailure original\n')
        with self.assertRaisesRegex(RuntimeError, 'already exists'):
            M.native(args)

    def test_unscoped_or_overwritten_readback_rejected_before_launch(self):
        command = self.root / 'capture.jlink'
        target = self.root / 'exists.bin'
        target.write_bytes(b'original')
        command.write_text('savebin "' + str(target) + '", 0x20000000, 0x20\n')
        args = SimpleNamespace(log=self.root / 'native.log', commands=command, tool=Path('never.exe'), serial=123456, timeout=20)
        with patch.object(M.host, 'command') as launch:
            with self.assertRaisesRegex(RuntimeError, 'overwrite'):
                M.native(args)
            command.write_text('savebin "D:/outside-p16.bin", 0x20000000, 0x20\n')
            with self.assertRaises(ValueError):
                M.native(args)
            launch.assert_not_called()

    def restoration_fixture(self):
        original = b'\xff' * 1048576
        internal = self.root / 'internal.bin'
        internal.write_bytes(original)
        slot = self.root / 'original-slot.bin'
        slot.write_bytes(original)
        expected = dict(internal=M.host.record(internal), slots={
            name:dict(raw=M.host.record(slot), payloadBytes=100) for name in ('candidate','backup','recovery')})
        raw = dict(internal=original, fpb=bytes(40), candidate=original, backup=original, recovery=original)
        for name in expected['slots']:
            (self.root / (name + '.bin')).write_bytes(original)
        (self.root / 'fpb.bin').write_bytes(raw['fpb'])
        return expected, raw, SimpleNamespace(execute=lambda *a, **k: (raw, '', self.root))

    def test_exact_restore_and_explicit_unused_tail_scope(self):
        expected, raw, mcu = self.restoration_fixture()
        self.assertTrue(E.passive_read(mcu, 'test', expected)['slots']['candidate']['fullSlotIdentical'])
        changed = bytearray(raw['candidate']); changed[-1] = 0
        raw['candidate'] = bytes(changed)
        (self.root / 'candidate.bin').write_bytes(raw['candidate'])
        with self.assertRaisesRegex(RuntimeError, 'slot changed'):
            E.passive_read(mcu, 'test', expected)
        result = E.passive_read(mcu, 'test', expected, restored=True)
        self.assertFalse(result['slots']['candidate']['fullSlotIdentical'])

    def test_restore_rejects_header_payload_and_internal_mismatch(self):
        expected, raw, mcu = self.restoration_fixture()
        for name, offset in (('internal', 900000), ('candidate', 0), ('backup', 4097), ('recovery', 4097)):
            old = raw[name]
            changed = bytearray(old); changed[offset] = 0
            raw[name] = bytes(changed)
            with self.assertRaises(RuntimeError):
                E.passive_read(mcu, 'test', expected, restored=True)
            raw[name] = old

    def test_restore_rejects_active_comparator(self):
        expected, raw, mcu = self.restoration_fixture()
        fpb = bytearray(40); struct.pack_into('<I', fpb, 8, 1); raw['fpb'] = bytes(fpb)
        with self.assertRaisesRegex(RuntimeError, 'comparator'):
            E.passive_read(mcu, 'test', expected, restored=True)

    def test_frozen_plan_identity_checked_before_device_entry(self):
        path = self.root / 'plan.json'; path.write_bytes(b'{}')
        contract = dict(task_id='P1-6', status='FROZEN', external_inputs=[dict(id='recovery-plan',
            evidence_sha256=hashlib.sha256(path.read_bytes()).hexdigest())])
        self.assertEqual(E.admitted_plan(contract, path), {})
        path.write_bytes(b'{"changed":true}')
        with self.assertRaisesRegex(RuntimeError, 'differs'):
            E.admitted_plan(contract, path)
        contract['task_id'] = 'P1-7'
        with self.assertRaisesRegex(RuntimeError, 'wrong/unfrozen'):
            E.admitted_plan(contract, path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
