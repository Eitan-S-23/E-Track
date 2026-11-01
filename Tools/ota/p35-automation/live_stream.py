"""Single-connection P35 frame receiver: validate, persist, then acknowledge."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner as r

REMOTE_PORT = 49135
MAX_BATCH = 1024 * 1024


def exact(peer, length, wire=None):
    chunks = bytearray()
    while len(chunks) < length:
        part = peer.recv(length - len(chunks))
        r.require(part, 'live stream closed before complete frame', 'EVIDENCE_GAP')
        if wire is not None:
            wire.write(part)
            wire.flush()
        chunks.extend(part)
    return bytes(chunks)


def receive(peer, sink, *, sync=lambda: None, wire=None):
    decoder = r.Decoder()
    body_hash = hashlib.sha256()
    total, batches = 0, 0
    while decoder.closed is None:
        size, = struct.unpack('!I', exact(peer, 4, wire))
        r.require(0 < size <= MAX_BATCH, 'invalid live frame length', 'EVIDENCE_GAP')
        data = exact(peer, size, wire)
        r.require(data.endswith(b'\n') and all(line.startswith((b'OTA_P35_STATE ', b'OTA_P35_CAPTURE '))
                  for line in data.splitlines()), 'noncanonical live frame', 'EVIDENCE_GAP')
        first_states = decoder.previous is None
        states = decoder.feed(data)
        r.require(decoder.opened is not None and not decoder.pending, 'missing live header/partial record', 'EVIDENCE_GAP')
        cid = decoder.opened.get('captureId')
        r.require(isinstance(cid, str) and r.re.fullmatch('[0-9a-f]{32}', cid) and
                  type(decoder.opened.get('schema')) is int and
                  decoder.opened == dict(schema=1,kind='open',captureId=cid), 'invalid live header', 'EVIDENCE_GAP')
        if states:
            r.require(states[0]['captureId'] == cid and (not first_states or states[0]['seq'] == 1),
                      'live capture identity mismatch', 'EVIDENCE_GAP')
        for line in data.splitlines(keepends=True):
            if line.startswith(r.PREFIX.encode()):
                body_hash.update(line)
        if decoder.closed is not None:
            r.require(set(decoder.closed) == {'schema','kind','captureId','records','sha256','healthy','lost','error'} and
                      type(decoder.closed.get('schema')) is int and decoder.closed['schema'] == 1 and
                      type(decoder.closed.get('records')) is int and type(decoder.closed.get('lost')) is int and
                      decoder.previous is not None and decoder.closed.get('captureId') == decoder.previous['captureId']
                      and decoder.closed.get('records') == decoder.previous['seq'] and
                      decoder.closed.get('healthy') is True and decoder.closed.get('lost') == 0 and
                      decoder.closed.get('error') is None and decoder.closed.get('sha256') == body_hash.hexdigest(),
                      'unhealthy live footer/hash', 'EVIDENCE_GAP')
        r.require(sink.write(data) == len(data), 'short live evidence write', 'EVIDENCE_GAP')
        sink.flush()
        sync()
        peer.sendall(('ACK %d %s\n' % (size, hashlib.sha256(data).hexdigest())).encode('ascii'))
        total += size
        batches += 1
    return dict(bytes=total, batches=batches, records=decoder.previous['seq'],
                captureId=decoder.previous['captureId'], source='acknowledged-stream-v1')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True, type=int)
    parser.add_argument('--wire-out', required=True, type=Path)
    args = parser.parse_args()
    r.require(1024 <= args.port <= 65535 and args.port != 5037, 'invalid local stream port')
    h = r.load_host()
    wire_path = h.checked(args.wire_out)
    r.require(not wire_path.exists(), 'existing wire evidence; no replay')
    deadline = time.monotonic() + 5
    peer = None
    while time.monotonic() < deadline:
        try:
            peer = socket.create_connection(('127.0.0.1', args.port), timeout=min(1, deadline-time.monotonic()))
            # ADB may accept locally before the App listens remotely. A closed
            # socket before any byte is not a connected producer or replay.
            peer.settimeout(max(.01, deadline-time.monotonic()))
            if peer.recv(1, socket.MSG_PEEK):
                break
            peer.close()
            peer = None
        except (OSError, TimeoutError):
            if peer is not None:
                peer.close()
                peer = None
        time.sleep(.02)
    r.require(peer is not None, 'live producer connection deadline', 'CAPABILITY_MISSING')
    with peer:
        peer.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        peer.settimeout(5)
        with wire_path.open('xb') as wire:
            result = receive(peer, sys.stdout.buffer, sync=lambda: os.fsync(sys.stdout.fileno()), wire=wire)
    print(json.dumps(result), file=sys.stderr, flush=True)


if __name__ == '__main__':
    main()
