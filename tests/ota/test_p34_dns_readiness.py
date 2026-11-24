"""DNS readiness regressions: negative replies may wait, malformed/TLS may not."""
import io
import runpy
import ssl
from pathlib import Path
import struct
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_probe_cadence_dns as entry
f = entry.dns
HOST = 'fresh.trycloudflare.com'
ORIGIN = 'https://' + HOST


def packet(rcode=0, *, ident=42, flags=0x8180, answers=0, ns=0, tail=b''):
    name = b''.join(bytes([len(p)]) + p.encode() for p in HOST.split('.')) + b'\0'
    return struct.pack('!6H', ident, flags | rcode, 1, answers, ns, 0) + name + struct.pack('!HH', 1, 1) + tail


class Guards(unittest.TestCase):
    def test_well_formed_negative_only(self):
        for code in (0, 2, 3):
            with self.subTest(code=code), self.assertRaises(f.NotReady): f.parse(packet(code), 42, HOST)

    def test_public_positive_uses_original_parser(self):
        rr = b'\xc0\x0c' + struct.pack('!HHIH', 1, 1, 60, 4) + bytes([104, 16, 230, 132])
        self.assertEqual(f.parse(packet(answers=1, tail=rr), 42, HOST), ['104.16.230.132'])
        with self.assertRaises(RuntimeError): f.parse(packet(answers=1, tail=rr[:-4]+bytes([127,0,0,1])), 42, HOST)

    def test_malformed_or_refused_is_not_retryable(self):
        cases = [packet(3, ident=43), packet(3, flags=0x8380), packet(3, flags=0x81c0),
                 packet(5), packet(3, ns=65), packet(3, tail=b'extra'), packet(3)[:-1], b'short']
        for raw in cases:
            with self.subTest(raw=raw), self.assertRaises(RuntimeError) as caught: f.parse(raw, 42, HOST)
            self.assertNotIsInstance(caught.exception, f.NotReady)
        with self.assertRaises(RuntimeError) as caught: f.parse(packet(3), 42, 'different.trycloudflare.com')
        self.assertNotIsInstance(caught.exception, f.NotReady)

    def test_negative_authority_bounds(self):
        soa = b'\xc0\x0c\xc0\x0c' + struct.pack('!5I', 1, 2, 3, 4, 5)
        rr = b'\xc0\x0c' + struct.pack('!HHIH', 6, 1, 60, len(soa)) + soa
        with self.assertRaises(f.NotReady): f.parse(packet(3, ns=1, tail=rr), 42, HOST)
        with self.assertRaises(RuntimeError) as caught: f.parse(packet(3, ns=1, tail=rr[:-1]), 42, HOST)
        self.assertNotIsInstance(caught.exception, f.NotReady)

    def test_bounded_wait_then_positive(self):
        lookup = mock.Mock(side_effect=[f.NotReady('nxdomain'), f.NotReady('nodata'), ['104.16.230.132']])
        sleep, report = mock.Mock(), mock.Mock()
        self.assertEqual(f.resolve(ORIGIN, lookup=lookup, sleep=sleep, report=report), ['104.16.230.132'])
        self.assertEqual(lookup.call_count, 3)
        self.assertEqual(sleep.call_args_list, [mock.call(2), mock.call(2)])
        self.assertEqual(report.call_count, 2)

    def test_terminal_failure_is_finite(self):
        lookup, sleep = mock.Mock(side_effect=f.NotReady('not-ready')), mock.Mock()
        with self.assertRaisesRegex(RuntimeError, 'readiness exhausted'): f.resolve(ORIGIN, lookup=lookup, sleep=sleep)
        self.assertEqual(lookup.call_count, 6)
        self.assertEqual(sleep.call_count, 5)

    def test_no_retry_for_other_failures(self):
        lookup, sleep = mock.Mock(side_effect=RuntimeError('wrong ID')), mock.Mock()
        with self.assertRaisesRegex(RuntimeError, 'wrong ID'): f.resolve(ORIGIN, lookup=lookup, sleep=sleep)
        self.assertEqual(lookup.call_count, 1)
        sleep.assert_not_called()

    def test_tls_failure_is_propagated_without_retry(self):
        with mock.patch.object(f, 'resolve', return_value=['104.16.230.132']) as resolve, \
             mock.patch.object(f.original, 'opener', side_effect=ssl.SSLCertVerificationError('bad certificate')) as opener:
            with self.assertRaises(ssl.SSLCertVerificationError): f.verify(mock.Mock(), mock.Mock(), ORIGIN)
        self.assertEqual(resolve.call_count, 1)
        self.assertEqual(opener.call_count, 1)

    def test_exact_failure_and_no_cell_reconciled(self):
        s = entry.cli.Store(ROOT)
        self.assertEqual(len(entry.reconciled(s)), 4)
        fake = mock.Mock(wraps=s)
        old_read = s.read
        def read(path):
            result = old_read(path)
            return dict(result, detail='different') if Path(path).name == 'network-result.json' else result
        fake.read.side_effect = read
        with self.assertRaises(RuntimeError): entry.reconciled(fake)


if __name__ == '__main__':
    entry.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                      'isolated explicit root required')
    s = entry.cli.Store(ROOT)
    s.checked(entry.HOST)
    entry.cli.require(not entry.HOST.exists(), 'preserve test output')
    stream = io.StringIO()
    original = runpy.run_path(str(ROOT / 'tests/ota/test_p34_scoped_dns.py'), run_name='dns_boundary_tests')['Tests']
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(x) for x in (Guards, original)])
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    log = s.raw(entry.HOST / 'tests.log', stream.getvalue().encode())
    s.write(entry.HOST / 'result.json', dict(result='PASS' if result.wasSuccessful() else 'FAIL', tests=result.testsRun,
        sources=entry.sources(), log=log, no_device_operations=True))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
