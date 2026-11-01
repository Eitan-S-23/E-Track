"""ROM-bound, read-only Bluetooth getter; no physical Binder/ADB operation."""
import unittest
from unittest.mock import patch

import runner as r
import test_runner as fixtures


def parcel(state):
    return ("Result: Parcel(00000000 %08x   '........')\r\n" % state).encode()


class RadioGetterTests(unittest.TestCase):
    def driver(self, outputs):
        d = object.__new__(r.Android)
        d.p = fixtures.plan()
        d.p['preparation'] = {'radio_state_reader': 'vivo-pd2312-sdk33-getState-v1'}
        d.calls = []
        d.record = lambda *args, **kwargs: None
        def cmd(args, seconds=5):
            d.calls.append((args, seconds))
            return outputs.pop(0)
        d.cmd = cmd
        return d

    def test_parcel_states_are_not_boolean_or_exception_guesses(self):
        for value, expected in ((10, False), (12, True), (11, None), (13, None), (14, None), (15, None), (16, None)):
            with self.subTest(value=value):
                self.assertIs(r.parse_radio_parcel(parcel(value)), expected)
        for raw in (b'', b'state: OFF', parcel(0), parcel(1), parcel(17),
                    parcel(10).replace(b'00000000', b'ffffffff', 1), parcel(12) + b'other\n',
                    parcel(10).replace(b'........', b'error...'), b'x'*257):
            with self.subTest(raw=raw), self.assertRaises(r.Stop):
                r.parse_radio_parcel(raw)

    def test_actual_on_reply_replay(self):
        file = r.ROOT / '.cache/p35-native-log-20261101/binder-probe-01/state.raw'
        raw = file.read_bytes() if file.exists() else parcel(12)
        self.assertIs(r.parse_radio_parcel(raw), True)

    def test_fingerprint_and_framework_are_verified_before_the_first_getter(self):
        d = self.driver([r.RADIO_FINGERPRINT.encode(),
            (r.RADIO_FRAMEWORK_SHA256 + '  ' + r.RADIO_FRAMEWORK).encode(), parcel(12), parcel(10)])
        self.assertIs(r.validate_plan(d.p), d.p)
        self.assertIs(d.radio_state(), True)
        self.assertIs(d.radio_state(), False)
        self.assertEqual([x[0] for x in d.calls], [
            ['shell', 'getprop', 'ro.build.fingerprint'], ['shell', 'sha256sum', r.RADIO_FRAMEWORK],
            list(r.RADIO_BINDER), list(r.RADIO_BINDER)])

    def test_changed_rom_or_framework_cannot_issue_any_binder_transaction(self):
        for outputs in ([b'another-ROM'], [r.RADIO_FINGERPRINT.encode(), b'0'*64 + b'  ' + r.RADIO_FRAMEWORK.encode()]):
            d = self.driver(outputs)
            with self.assertRaises(r.Stop):
                d.radio_state()
            self.assertFalse(any(x[0] == list(r.RADIO_BINDER) for x in d.calls))
        d.p['preparation']['radio_state_reader'] = 'arbitrary-transaction'
        with self.assertRaises(r.Stop):
            r.validate_plan(d.p)

    def test_profile_checks_and_state_read_share_the_existing_deadline(self):
        now = [0.0]
        d = self.driver([r.RADIO_FINGERPRINT.encode()])
        cmd = d.cmd
        def late(args, seconds=5):
            raw = cmd(args, seconds)
            now[0] += 6
            return raw
        d.cmd = late
        with patch.object(r.time, 'monotonic', lambda: now[0]), self.assertRaises(r.Stop):
            d.radio_state()
        self.assertEqual(len(d.calls), 1)

    def test_failed_getter_never_falls_back_to_a_missing_adapter(self):
        d = self.driver([b'Result: Parcel(ffffffff 0000000a)'])
        d.radio_getter_verified = True
        with self.assertRaises(r.Stop):
            d.radio_state()
        self.assertEqual([c[0] for c in d.calls], [list(r.RADIO_BINDER)])


if __name__ == '__main__':
    unittest.main()
