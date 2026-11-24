"""Bounded fresh-service DNS readiness; malformed replies remain fatal."""
import secrets
import socket
import struct
import time

import p34_scoped_dns as original


class NotReady(RuntimeError):
    pass


def parse(raw, ident, host):
    original.cli.require(12 <= len(raw) <= 4096, 'invalid DNS packet size')
    tx, flags, qd, an, ns, ar = struct.unpack_from('!6H', raw)
    if an != 0 or flags & 15 not in (0, 2, 3):
        return original.parse_answer(raw, ident, host)
    original.cli.require(tx == ident and flags & 0x8000 and flags & 0x7a40 == 0 and
                         qd == 1 and ns + ar <= 64, 'invalid negative DNS header')
    name, offset = original.dns_name(raw, 12)
    original.cli.require(name == host and raw[offset:offset+4] == struct.pack('!HH', 1, 1),
                         'negative DNS question mismatch')
    offset += 4
    for _ in range(ns + ar):
        _, offset = original.dns_name(raw, offset)
        original.cli.require(offset + 10 <= len(raw), 'truncated negative DNS record')
        kind, _, _, length = struct.unpack_from('!HHIH', raw, offset)
        offset += 10
        end = offset + length
        original.cli.require(end <= len(raw), 'truncated negative DNS data')
        if kind in (2, 5, 12):
            _, used = original.dns_name(raw, offset)
            original.cli.require(used == end, 'negative DNS name length mismatch')
        elif kind == 6:
            _, first = original.dns_name(raw, offset)
            _, second = original.dns_name(raw, first)
            original.cli.require(second + 20 == end, 'negative DNS SOA length mismatch')
        offset = end
    original.cli.require(offset == len(raw), 'negative DNS trailing data')
    raise NotReady('DNS not ready: rcode=%d answers=0' % (flags & 15))


def query(host):
    ident = secrets.randbelow(65536)
    name = b''.join(bytes([len(p)]) + p.encode('ascii') for p in host.split('.')) + b'\0'
    packet = struct.pack('!6H', ident, 0x100, 1, 0, 0, 0) + name + struct.pack('!HH', 1, 1)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as stream:
        stream.settimeout(5)
        stream.connect((original.SERVER, 53))
        stream.send(packet)
        raw = stream.recv(4097)
    return parse(raw, ident, host)


def resolve(origin, *, lookup=query, sleep=time.sleep, report=lambda *args: None):
    host = original.hostname(origin)
    for attempt in range(1, 7):
        try:
            return lookup(host)
        except NotReady as error:
            report(attempt, str(error))
            if attempt == 6:
                raise RuntimeError('fresh-service DNS readiness exhausted') from error
            sleep(2)


def verify(api, c, origin):
    from types import FunctionType
    def ready(value):
        return resolve(value, report=lambda n, detail: c.action('dns-readiness', 'waiting',
            attempt=n, detail=detail, host=original.hostname(value), system_dns_changed=False))
    return FunctionType(original.verify.__code__, dict(original.verify.__globals__, resolve=ready),
                        original.verify.__name__)(api, c, origin)
