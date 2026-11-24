"""Pure host DNS/TLS boundary tests; no resolver, phone or firmware contact."""
import io
import os
from pathlib import Path
import ssl
import struct
import sys
import unittest
from unittest import mock
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_scoped_dns as d
import p34_install_cost as host


class Tests(unittest.TestCase):
    HOST = "fixture.trycloudflare.com"
    ORIGIN = "https://fixture.trycloudflare.com"

    def packet(self, *, flags=0x8180, ident=17, ip=b"\x68\x12\x01\x01"):
        name = b"".join(bytes([len(p)]) + p.encode() for p in self.HOST.split(".")) + b"\0"
        return (struct.pack("!6H", ident, flags, 1, 1, 0, 0) + name + struct.pack("!HH", 1, 1) +
                b"\xc0\x0c" + struct.pack("!HHIH", 1, 1, 60, len(ip)) + ip)

    def test_public_a_response(self):
        self.assertEqual(d.parse_answer(self.packet(), 17, self.HOST), ["104.18.1.1"])

    def test_mismatched_id_question_status_and_truncation(self):
        for raw in (self.packet(ident=18), self.packet(flags=0x8183), self.packet(flags=0x8380),
                    self.packet()[:-1], self.packet()[:10]):
            with self.subTest(raw=raw), self.assertRaises(RuntimeError):
                d.parse_answer(raw, 17, self.HOST)
        with self.assertRaises(RuntimeError):
            d.parse_answer(self.packet(), 17, "other.trycloudflare.com")

    def test_private_multicast_and_bad_address_rejected(self):
        for ip in (b"\x7f\0\0\1", b"\xc0\xa8\0\1", b"\xe0\0\0\1", b"\1\2\3"):
            with self.subTest(ip=ip), self.assertRaises(RuntimeError):
                d.parse_answer(self.packet(ip=ip), 17, self.HOST)

    def test_pointer_loop_rejected(self):
        with self.assertRaises(RuntimeError):
            d.dns_name(b"\xc0\0", 0)

    def test_origin_scope(self):
        for origin in ("http://fixture.trycloudflare.com", "https://fixture.trycloudflare.com:443",
                       "https://fixture.trycloudflare.com.evil.invalid", "https://user@fixture.trycloudflare.com"):
            with self.subTest(origin=origin), self.assertRaises(RuntimeError):
                d.hostname(origin)

    def test_one_pinned_https_handler_with_verified_hostname(self):
        client = d.opener(self.ORIGIN, "104.18.1.1")
        handlers = [h for h in client.handlers if isinstance(h, urllib.request.HTTPSHandler)]
        self.assertEqual(len(handlers), 1)
        handler = handlers[0]
        self.assertIsInstance(handler, d.PinnedHandler)
        self.assertTrue(handler._context.check_hostname)
        self.assertEqual(handler._context.verify_mode, ssl.CERT_REQUIRED)
        connection = handler.connection(self.HOST, context=handler._context)
        with mock.patch("http.client.HTTPSConnection.connect"):
            connection.connect()
        with mock.patch("socket.create_connection") as create:
            connection._create_connection((self.HOST, 443), 5)
            create.assert_called_once_with(("104.18.1.1", 443), 5, None)
        self.assertEqual(connection.host, self.HOST)

    def test_cross_origin_connection_rejected(self):
        handler = next(h for h in d.opener(self.ORIGIN, "104.18.1.1").handlers if isinstance(h, d.PinnedHandler))
        connection = handler.connection("evil.invalid", context=handler._context)
        with self.assertRaises(RuntimeError):
            connection.connect()

    def test_real_https_constructor_before_network(self):
        client = d.opener(self.ORIGIN, "104.18.1.1")
        handler = next(h for h in client.handlers if isinstance(h, d.PinnedHandler))
        with mock.patch.object(handler.connection, "connect", side_effect=RuntimeError("before-network")):
            with self.assertRaisesRegex(RuntimeError, "before-network"):
                client.open(self.ORIGIN, timeout=1)

    def test_cross_origin_redirect_and_http_downgrade_rejected(self):
        client = d.opener(self.ORIGIN, "104.18.1.1")
        redirect = next(h for h in client.handlers if isinstance(h, urllib.request.HTTPRedirectHandler))
        for url in ("http://fixture.trycloudflare.com/asset", "https://evil.invalid/asset"):
            with self.subTest(url=url), self.assertRaises(RuntimeError):
                redirect.redirect_request(urllib.request.Request(self.ORIGIN), None, 302, "redirect", {}, url)


if __name__ == "__main__":
    d.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "explicit root and isolated Python required")
    s = d.cli.Store(ROOT)
    out = ROOT / ".cache/p34-connect-fix/followup/scoped-dns/tests-r2"
    d.cli.require(not out.exists(), "preserve test evidence")
    os.environ.update(host.environment(s, out))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    log = s.raw(out / "tests.log", stream.getvalue().encode())
    s.write(out / "result.json", dict(result="PASS" if result.wasSuccessful() else "FAIL", tests=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), source=d.cli.record(d.__file__),
        test=d.cli.record(__file__), log=log, hardware=False))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
