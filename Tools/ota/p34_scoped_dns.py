"""Per-service DNS fallback with unchanged TLS hostname and immutable asset gates."""
import hashlib
import http.client
import ipaddress
import json
import re
import secrets
import socket
import ssl
import struct
import urllib.parse
import urllib.request

import p34_session as cli

SERVER = "8.8.8.8"


def hostname(origin):
    cli.require(re.fullmatch(r"https://[a-z0-9-]+\.trycloudflare\.com", origin), "unbound service origin")
    return urllib.parse.urlsplit(origin).hostname


def dns_name(raw, offset, seen=None):
    seen = set() if seen is None else set(seen)
    labels, end = [], None
    while True:
        cli.require(offset < len(raw) and offset not in seen, "invalid DNS name/pointer")
        seen.add(offset)
        size = raw[offset]
        offset += 1
        if size & 0xc0 == 0xc0:
            cli.require(offset < len(raw), "truncated DNS pointer")
            pointer = ((size & 0x3f) << 8) | raw[offset]
            name, _ = dns_name(raw, pointer, seen)
            labels.append(name)
            end = offset + 1
            break
        cli.require(size <= 63 and offset + size <= len(raw), "invalid DNS label")
        if not size:
            end = offset
            break
        labels.append(raw[offset:offset + size].decode("ascii").lower())
        offset += size
        cli.require(sum(map(len, labels)) + len(labels) <= 255, "oversized DNS name")
    return ".".join(labels), end


def parse_answer(raw, ident, host):
    cli.require(12 <= len(raw) <= 4096, "invalid DNS packet size")
    tx, flags, questions, answers, authority, additional = struct.unpack_from("!6H", raw)
    cli.require(tx == ident and flags & 0x8000 and flags & 0x7a0f == 0 and
                questions == 1 and 0 < answers <= 32 and authority + additional <= 64,
                "DNS ID/status/count mismatch")
    name, offset = dns_name(raw, 12)
    cli.require(name == host and raw[offset:offset + 4] == struct.pack("!HH", 1, 1), "DNS question mismatch")
    offset += 4
    records = []
    for _ in range(answers):
        name, offset = dns_name(raw, offset)
        cli.require(offset + 10 <= len(raw), "truncated DNS answer")
        kind, cls, ttl, size = struct.unpack_from("!HHIH", raw, offset)
        offset += 10
        end = offset + size
        cli.require(cls == 1 and ttl > 0 and end <= len(raw), "invalid DNS answer")
        value = None
        if kind == 1:
            cli.require(size == 4, "invalid IPv4 answer size")
            value = str(ipaddress.IPv4Address(raw[offset:end]))
            cli.require(ipaddress.ip_address(value).is_global and not ipaddress.ip_address(value).is_multicast,
                        "non-public DNS destination")
        elif kind == 5:
            value, consumed = dns_name(raw, offset)
            cli.require(consumed == end, "CNAME length mismatch")
        records.append((name, kind, value))
        offset = end
    allowed = {host}
    for _ in range(answers):
        allowed.update(value for name, kind, value in records if kind == 5 and name in allowed)
    addresses = sorted({value for name, kind, value in records if kind == 1 and name in allowed})
    cli.require(addresses, "no A records for the requested service")
    return addresses


def resolve(origin):
    host = hostname(origin)
    ident = secrets.randbelow(65536)
    question = b"".join(bytes([len(p)]) + p.encode("ascii") for p in host.split(".")) + b"\0"
    packet = struct.pack("!6H", ident, 0x100, 1, 0, 0, 0) + question + struct.pack("!HH", 1, 1)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as stream:
        stream.settimeout(5)
        stream.connect((SERVER, 53))
        stream.send(packet)
        raw = stream.recv(4097)
    return parse_answer(raw, ident, host)


def opener(origin, address):
    host = hostname(origin)
    ip = ipaddress.ip_address(address)
    cli.require(ip.version == 4 and ip.is_global and not ip.is_multicast, "invalid pinned address")
    context = ssl.create_default_context()
    cli.require(context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED, "TLS verification required")

    class BoundConnection(http.client.HTTPSConnection):
        def connect(self):
            cli.require(self.host == host and self.port == 443 and not self._tunnel_host,
                        "cross-origin connection/redirect rejected")
            # HTTPSConnection still verifies and sends SNI for self.host, not the IP.
            self._create_connection = lambda endpoint, timeout, source_address=None: socket.create_connection(
                (address, 443), timeout, source_address)
            return super().connect()

    class SameOriginRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, fp, code, message, headers, newurl):
            parsed = urllib.parse.urlsplit(newurl)
            cli.require(parsed.scheme + "://" + parsed.netloc == origin,
                        "cross-origin redirect rejected")
            return super().redirect_request(request, fp, code, message, headers, newurl)

    return urllib.request.build_opener(urllib.request.ProxyHandler({}),
        PinnedHandler(BoundConnection, context), SameOriginRedirect())


class PinnedHandler(urllib.request.HTTPSHandler):
    def __init__(self, connection, context):
        super().__init__(context=context, check_hostname=True)
        self.connection = connection

    def https_open(self, request):
        return self.do_open(self.connection, request, context=self._context)


def verify(api, c, origin):
    addresses = resolve(origin)
    c.action("scoped-dns", "resolved", host=hostname(origin), server=SERVER, addresses=addresses,
             system_dns_changed=False, tls_hostname_verification=True)
    # One address per bounded readiness attempt; never weaken an integrity failure.
    client = opener(origin, addresses[0])
    phone = api.legacy["named"]["raw_load"]("scoped_dns_query", c.HERE / "prefix_phone.py")
    with client.open(origin + c.service.LATEST_PATH + "?" + urllib.parse.urlencode(phone.latest_query(c)), timeout=15) as response:
        value = json.loads(response.read(16384))
    api.validate_served(c, value, origin)
    with client.open(value["asset"]["downloadUrl"], timeout=15) as response:
        data = response.read(len(c.screen_bytes) + 1)
    cli.require(data == c.screen_bytes, "HTTPS package bytes differ")
    return dict(origin=origin, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
        file_name=api.served_name, kind=c.package_kind, filename_contract_verified=True,
        resolver=SERVER, address=addresses[0], tls_hostname_verified=True, system_dns_changed=False)
