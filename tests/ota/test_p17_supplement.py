"""P1-7 supplemental original oracles: timing, identity and reporting boundaries."""
import copy
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/acceptance'))
import p17_supplement as r


def fixture():
    out = 'P17_RESULT long result=1 ticks=3000 gpio=00005eff\nP17_RESULT short result=0 ticks=10 gpio=00005eff\n'
    rows = ['Flash breakpoints disabled']
    for t, pc, ret in ((100, '08001E6D', '01000000'), (3124, '080019AA', None),
                       (5000, '08001E6D', '00000000'), (5052, '080019AA', None)):
        rows.append("03-00000000-00-%08d-0023: Writing register 'pc' = 0x%s" % (t, pc))
        if ret:
            rows.append("Read register 'r0' (4 bytes) from hardware: 0x" + ret)
    rows.extend('Read 4 bytes @ address 0x20001030 (Data = 0x%08X)' % t for t in (1003, 4003, 4003, 4013))
    return out, '\n'.join(rows)


class Tests(unittest.TestCase):
    def test_key_positive(self):
        result = r.key_gate(*fixture())
        self.assertEqual((result['longTicks'], result['shortTicks']), (3000, 10))
        self.assertIn('not a measured one-second', result['limitation'])

    def test_false_long(self):
        out, log = fixture()
        with self.assertRaises(RuntimeError):
            r.key_gate(out.replace('long result=1', 'long result=0'), log)

    def test_early_long(self):
        out, log = fixture()
        with self.assertRaises(RuntimeError):
            r.key_gate(out.replace('ticks=3000', 'ticks=2999'), log)

    def test_short_entered(self):
        out, log = fixture()
        with self.assertRaises(RuntimeError):
            r.key_gate(out.replace('short result=0', 'short result=1'), log)

    def test_missing_native_ticks(self):
        out, log = fixture()
        with self.assertRaises(RuntimeError):
            r.key_gate(out, log.replace('0x00000FAD', '0x00000FAE'))

    def test_wrong_function(self):
        out, log = fixture()
        with self.assertRaises(RuntimeError):
            r.key_gate(out, log.replace('08001E6D', '08001E6F'))

    def test_short_host_long_interval(self):
        out, log = fixture()
        with self.assertRaises(RuntimeError):
            r.key_gate(out, log.replace('00003124', '00000150'))

    def test_native_return_mismatch(self):
        out, log = fixture()
        with self.assertRaises(RuntimeError):
            r.key_gate(out, log.replace('01000000', '00000000'))

    def test_missing_duplicate_and_reset(self):
        out, log = fixture()
        for text, native in (('', log), (out + out, log), (out, log + '\nResetting target')):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                r.key_gate(text, native)

    def test_battery_report_scope(self):
        report = dict(quote=r.BATTERY_QUOTE, source='current-conversation-user', instrumented=False,
            procedure=dict(usbDisconnected=True, jlinkDisconnected=True, batteryOnly=True,
                           powerButtonStartup=True, enteredApp=True))
        context = 'P17-BATTERY-01 ' + r.BATTERY_QUOTE
        self.assertEqual(r.battery_gate(report, context)['result'], 'PASS')
        for key, value in (('instrumented', True), ('quote', ''), ('source', 'agent-assumption')):
            bad = copy.deepcopy(report)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                r.battery_gate(bad, context)
        bad = copy.deepcopy(report)
        bad['procedure']['jlinkDisconnected'] = False
        with self.assertRaises(RuntimeError):
            r.battery_gate(bad, context)

    def test_cli_help(self):
        result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8',
            ROOT/'Tools/acceptance/p17_supplement.py', '--help'], cwd=ROOT, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn(b'--bundle', result.stdout)


if __name__ == '__main__':
    unittest.main()
