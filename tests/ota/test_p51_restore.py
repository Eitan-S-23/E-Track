"""Host mailbox guards for the P51 adaptation of the existing restore fixture."""
import hashlib
from pathlib import Path
import struct
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota/p34-acceptance'))
import live_mcu as m


class RestoreMailboxTests(unittest.TestCase):
    def sample(self, versions=(30316, 30313), phase=1):
        base = bytes(0x460)
        boot = hashlib.sha256(b'bound-boot').hexdigest()
        raw = bytearray(640)
        words = [0x41343352,1,phase,0,12345,0,0,1,*versions,len(base),zlib.crc32(base),0,0,0,0]
        if phase == 3:
            words[12:15] = [1,0,1]
        struct.pack_into('<16I',raw,0,*words)
        raw[319] = raw[575] = 0x55
        raw[576:608] = bytes.fromhex(boot)
        raw[608:640] = hashlib.sha256(base).digest()
        return raw, base, boot

    def test_default_binding_preserved(self):
        raw,base,boot = self.sample((30287,30286))
        self.assertEqual(m.restore_gate(raw,base,boot,1)['phase'],1)

    def test_explicit_p51_ready_and_committed(self):
        for phase in (1,3):
            raw,base,boot = self.sample(phase=phase)
            self.assertEqual(m.restore_gate(raw,base,boot,phase,versions=(30316,30313))['phase'],phase)

    def test_wrong_version_identity_crc_and_hash(self):
        raw,base,boot = self.sample()
        for offset in (32,36,40,44,576,608):
            with self.subTest(offset=offset):
                bad = bytearray(raw)
                bad[offset] ^= 1
                with self.assertRaises(RuntimeError):
                    m.restore_gate(bad,base,boot,1,versions=(30316,30313))

    def test_not_an_unbound_or_replayed_command(self):
        raw,base,boot = self.sample()
        with self.assertRaises(RuntimeError):
            m.restore_gate(raw,base,boot,1)
        for versions in ((30313,30316),(30313,30313),(True,1),(30316,0),[30316,30313]):
            with self.assertRaises(RuntimeError):
                m.restore_gate(raw,base,boot,1,versions=versions)
        for offset in (20,24,48):
            bad = bytearray(raw)
            bad[offset] = 1
            with self.assertRaises(RuntimeError):
                m.restore_gate(bad,base,boot,1,versions=(30316,30313))

    def test_failed_commit_or_settings_change_rejected(self):
        raw,base,boot = self.sample(phase=3)
        for offset in (12,48,52,56,448,575):
            bad = bytearray(raw)
            bad[offset] ^= 1
            with self.assertRaises(RuntimeError):
                m.restore_gate(bad,base,boot,3,versions=(30316,30313))


if __name__ == '__main__':
    unittest.main()
