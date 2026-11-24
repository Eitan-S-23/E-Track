import copy
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_r2_trial_assets as assets


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = assets.cli.Store(ROOT)
        cls.group = assets.derive(cls.store)

    def test_exact_existing_package_and_actual_r2_image_bindings(self):
        group = self.group
        self.assertEqual((group['specification']['receiver'], group['specification']['target_version']), (30276, 30277))
        self.assertEqual(group['package'], self.store.read(assets.PACKAGE)['package'])
        self.assertEqual(group['package']['bytes'], 294052)
        self.assertEqual(group['package']['sha256'], 'a67ff12d91a83c7f4bf0324f98ee68c1880547f39a37f3e2137707c3aed196e0')
        for name, version in (('receiver', 30276), ('target', 30277)):
            binding = group[name + '_bindings']
            self.assertEqual(binding['profile']['identity']['version_code'], version)
            self.assertEqual(binding['profile']['map']['sha256'], assets.r2_health.MAP_SHA)
            self.assertEqual(binding['layout']['session'], 0x20052988)
            self.assertEqual(binding['whole_boot']['sha256'], 'a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4')
        self.assertEqual(len(group['negatives']), 4)
        self.assertTrue(all(n['native']['passed'] and n['native']['prepares'] == 0 for n in group['negatives']))

    def test_schema9_fixed_axes_validate_for_r2_without_old_lineage(self):
        value = self.store.read(ROOT / '.cache/p34-sha-candidate/trials/measure/cells/s04/runtime-config.json')
        group = self.group
        value.update(currentVersionCode=30276, targetVersionCode=30277,
            currentImageSha256=group['receiver']['sha256'], targetImageSha256=group['target']['sha256'],
            packageBytes=group['package']['bytes'], packageSha256=group['package']['sha256'])
        assets.policy.validate(value, group)
        for key, wrong in (('requestedBaud', 115200), ('senderWindowSegments', 16), ('dataBatchFrames', 3),
                           ('rebootInfoTimeoutMs', 2000), ('rebootInfoMaxAttempts', 3), ('currentVersionCode', 30275)):
            with self.assertRaises(RuntimeError): assets.policy.validate(dict(value, **{key: wrong}), group)

    def test_cross_compiled_abi_member_and_identity_mutations_reject(self):
        old = self.store.read(assets.PRIOR)['groups']['measure']['target_bindings']['layout']['members']
        layout = self.store.read(assets.ABI)
        assets.validate_abi(old, layout)
        bad = copy.deepcopy(old)
        bad['members']['isr_active']['offset'] += 4
        with self.assertRaises(RuntimeError): assets.validate_abi(bad, layout)
        bad = bytearray(Path(self.group['target']['path']).read_bytes())
        bad[0x900] ^= 1
        with self.assertRaises(ValueError): assets.identity(bytes(bad))

    def test_original_elf_drift_rejected_and_executed_dependencies_bound(self):
        record = assets.cli.record
        elf = assets.BUILD / 'X-Track-App-GCC.elf'
        def changed(path):
            item = record(path)
            return dict(item, sha256='0' * 64) if Path(path) == elf else item
        with mock.patch.object(assets.cli, 'record', side_effect=changed):
            with self.assertRaisesRegex(RuntimeError, 'R2 original ELF binding differs'):
                assets.derive(self.store)
        names = {p.relative_to(ROOT).as_posix() for p in assets.sources(self.store)}
        for name in ('Tools/ota/p34_patch_preparation.py', 'Tools/ota/p34_install_candidate.py',
                     '.agents/skills/e-track-flutter-debug/scripts/host_io.py',
                     '.cache/p34-sha-candidate/trials/measure/cells/s04/runtime-config.json',
                     '.cache/p34-recovery-sources1/result.json'):
            self.assertIn(name, names)


if __name__ == '__main__': unittest.main()
