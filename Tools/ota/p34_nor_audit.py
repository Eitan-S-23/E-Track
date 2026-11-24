"""Offline streaming SDK/journal equality and exact NOR mutation audit."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import re
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
import p34_session as cli
from recovery_entry import host_writer as hw

WRITE_EVENTS = {'debug-write-attempt', 'i2c-edge-attempt', 'nor-mmio-write-attempt',
                'nor-read-command-write-attempt', 'nor-mutation-command-attempt'}
READ_EVENTS = {'nor-fifo-read-returned', 'nor-fifo-burst-returned',
               'nor-mapped-read-returned', 'nor-internal-read-returned'}
WREG = re.compile(r'JLINK_CORESIGHT_WriteAPDPReg\((AP|DP) reg 0x([0-9A-Fa-f]+), 0x([0-9A-Fa-f]+)\)')
RREG = re.compile(r'JLINK_CORESIGHT_ReadAPDPReg\((AP|DP) reg 0x([0-9A-Fa-f]+)\)')
VALUE = re.compile(r'\bValue=0x([0-9A-Fa-f]+)')
RETURN = re.compile(r'\breturns (-?\d+)\s*$')


def events(path):
    with path.open(encoding='utf-8') as stream:
        for line in stream: yield json.loads(line)


def expected_writes(path):
    for e in events(path):
        if e['event'] in WRITE_EVENTS: yield e['address'], e['value']
        elif e['event'] == 'nor-cache-bypass-attempt': yield 0xa000103c, e['value']
        elif e['event'] == 'nor-tx-word': yield 0xa0001100, e['value']


class ReadFrames:
    def __init__(self, path):
        self.frames = (e for e in events(path) if e['event'] in READ_EVENTS)
        self.frame, self.offset, self.count, self.bytes = next(self.frames, None), 0, 0, 0
    def word(self, address, value, width):
        fifo, mapped = address == 0xa0001100, 0x90000000 <= address < 0x91000000
        internal = (self.frame is not None and self.frame['event'] == 'nor-internal-read-returned' and
                    address == self.frame['address']+self.offset)
        if not (fifo or mapped or internal): return
        cli.require(self.frame is not None, 'SDK data read has no journal frame')
        e = self.frame; kind = e['event']
        cli.require((fifo and kind in ('nor-fifo-read-returned', 'nor-fifo-burst-returned')) or
                    (mapped and kind == 'nor-mapped-read-returned' and address == 0x90000000+e['address']+self.offset) or
                    internal, 'SDK/journal frame type/address mismatch')
        raw = bytes.fromhex(e['data_hex'])
        data = (value & ((1 << (8*width))-1)).to_bytes(width, 'little')
        cli.require(raw[self.offset:self.offset+width] == data, 'SDK/journal data bytes mismatch')
        self.offset += width; self.bytes += width
        if self.offset == len(raw):
            self.count += 1; self.offset = 0; self.frame = next(self.frames, None)
    def finish(self): cli.require(self.frame is None and self.offset == 0, 'journal frames missing SDK reads')


def action_manifest(source):
    actions = [('erase', hw.LOW, b'')]
    for offset in range(0, len(source), 4096):
        actions.append(('erase', hw.LOW+4096+offset, b''))
        for page in range(offset, min(offset+4096, len(source)), 256):
            actions.append(('program', hw.LOW+4096+page, source[page:page+256]))
    header = b'ETSL\x04\xff\xff\xff'+struct.pack('<III', len(source), zlib.crc32(source), 30276)+source[0x428:0x430]
    return actions+[('program', hw.LOW, header), ('program', hw.LOW+28, b'TMOC')]


class Targets:
    def __init__(self, source=None):
        self.actions = [] if source is None else action_manifest(source)
        self.index, self.word, self.command, self.wren, self.tx = 0, 0, [], False, None
        self.count, self.commands, self.tx_bytes = 0, 0, 0
    def write(self, address, value, csw):
        self.count += 1
        if address == 0xe000edf4:
            cli.require(value in (15, 16, 17, 20), 'non-read core selector')
        elif address in (0x40020418, 0x40020428):
            cli.require(value in (0x40, 0x80), 'GPIO outside BCB pins')
        elif address == 0xa0001010:
            cli.require(value in (0, 7, 0x100000, 0x100007), 'CTRL outside mode/divisor scope')
        elif address == 0xa000103c:
            cli.require(value in (0, 1), 'XIP3 outside cache bypass bit')
        elif address == 0xa0001024:
            cli.require(value == 1, 'invalid completion acknowledgement')
        elif 0xa0001000 <= address <= 0xa000100c and address % 4 == 0:
            cli.require(address-0xa0001000 == self.word*4, 'CMD quartet order violation')
            self.command.append(value); self.word += 1
            if self.word == 4:
                self.launch(); self.command, self.word = [], 0
        elif address == 0xa0001100:
            cli.require(csw & 0x37 == 2 and self.tx is not None, 'TX outside fixed pending FIFO')
            expected, offset = self.tx
            cli.require(expected[offset:offset+4] == value.to_bytes(4, 'little'), 'TX source/data mismatch')
            offset += 4; self.tx_bytes += 4
            self.tx = None if offset == len(expected) else (expected, offset)
        else:
            raise RuntimeError('SDK target write outside authorized ports: '+hex(address))
    def launch(self):
        address, options, size, trigger = self.command
        opcode = trigger >> 24; self.commands += 1
        cli.require(self.tx is None, 'new command before prior TX completed')
        if opcode in (5, 0x35):
            cli.require(self.command == [0, 0x1000000, 0, (opcode << 24)|0xc], 'status command framing')
        elif opcode == 0x9f:
            cli.require(self.command == [0, 0x1000000, 3, 0x9f000000], 'RDID framing')
        elif opcode == 0x5a:
            cli.require(address in (0, 128) and options == 0x1080003 and size == 128 and trigger == 0x5a000000, 'SFDP framing')
        elif opcode == 3:
            cli.require(0 <= address < address+size <= 0x1000000 and options == 0x1000003 and
                        0 < size <= 128 and size % 4 == 0 and trigger == 0x03000000, 'read framing')
        elif opcode == 6:
            cli.require(self.actions and not self.wren and self.command == [0, 0x1000000, 0, 0x06000002], 'unpaired WREN')
            self.wren = True
        elif opcode in (2, 0x20):
            cli.require(self.wren and self.index < len(self.actions), 'mutation without admitted WREN/action')
            kind, expected_address, data = self.actions[self.index]
            cli.require(opcode == (2 if kind == 'program' else 0x20) and address == expected_address and
                        options == 0x1000003 and size == len(data) and trigger == (opcode << 24)|2,
                        'mutation differs from exact recovery manifest')
            cli.require(hw.LOW <= address and address+(4096 if kind == 'erase' else size) <= hw.HIGH, 'mutation range')
            self.index += 1; self.wren = False
            if kind == 'program': self.tx = (data, 0)
        else: raise RuntimeError('unlisted NOR opcode '+hex(opcode))
    def finish(self):
        cli.require(self.index == len(self.actions) and self.tx is None and not self.wren and self.word == 0,
                    'incomplete NOR operation manifest')


def trace(area, worker, *, source=None):
    writes = iter(expected_writes(area/'events.jsonl')); frames = ReadFrames(area/'events.jsonl')
    target = Targets(source)
    original = worker['dap']['ap_csw']; csw, tar, bank, pending = original, None, 0, None
    ctrl, bypass = 0x100000, 0
    with (area/'sdk.log').open(encoding='utf-8') as stream:
        for line in stream:
            cli.require('CPU_WriteMem' not in line, 'high-level CPU write in SDK log')
            wr, rd = WREG.search(line), RREG.search(line)
            if wr:
                cli.require(pending is None, 'overlapping SDK call')
                port, register, value = wr[1], int(wr[2], 16), int(wr[3], 16)
                pending = ('write', port, register)
                if port == 'DP':
                    cli.require((register == 2 and value in (0, 0xf0)) or
                                (register == 1 and value in (0x50000040, 0x10000040, 0x40)), 'unlisted DP write')
                    if register == 2: bank = value
                elif register == 0:
                    cli.require(value in (original, (original & ~0x37)|0x12, original & ~0x37, (original & ~0x37)|2), 'unlisted CSW')
                    csw = value
                elif register == 1: tar = value
                else:
                    cli.require(register == 3 and bank == 0 and tar is not None, 'unlisted AP write')
                    cli.require(next(writes, None) == (tar, value), 'SDK/action-journal write mismatch')
                    target.write(tar, value, csw)
                    if tar == 0xa0001010: ctrl = value
                    if tar == 0xa000103c: bypass = value
                    if csw & 0x30 == 0x10: tar = (tar & ~1023) | ((tar+(1 << (csw & 7))) & 1023)
            elif rd:
                cli.require(pending is None, 'overlapping SDK read')
                pending = ('read', rd[1], int(rd[2], 16))
            elif VALUE.search(line) and pending and pending[0] == 'read':
                value = int(VALUE.search(line)[1], 16)
                if pending[1:] == ('AP', 3) and bank == 0:
                    cli.require(tar is not None and csw & 7 in (0, 2), 'unknown transfer format')
                    if 0x90000000 <= tar < 0x91000000:
                        cli.require(ctrl == 0x100007 and bypass == 1, 'mapped read without fresh cache bypass /12')
                    frames.word(tar, value, 1 << (csw & 7))
                    if csw & 0x30 == 0x10: tar = (tar & ~1023) | ((tar+(1 << (csw & 7))) & 1023)
            elif RETURN.search(line) and pending:
                cli.require(int(RETURN.search(line)[1]) >= 0, 'failed/uncertain SDK register call')
                pending = None
            elif re.search(r'JLINK\w*_(?:Write|CORESIGHT_Write)', line):
                raise RuntimeError('unrecognized SDK write call')
    cli.require(pending is None and next(writes, None) is None, 'unfinished SDK/journal writes')
    cli.require(csw == original and tar == worker['dap']['original_tar'], 'AP format/address not restored')
    cli.require(ctrl == 0x100000 and bypass == 0, 'controller mode/cache not restored')
    target.finish(); frames.finish()
    return dict(target_writes=target.count, nor_commands=target.commands, mutation_commands=target.index,
                tx_payload_bytes=target.tx_bytes, sdk_matched_frames=frames.count, sdk_matched_bytes=frames.bytes)


def physical_files(area, worker):
    regions = [('candidate-backup', 0, 0x200000), ('tail', 0x299000, 0x300000),
               ('staging', 0x300000, 0x500000), ('recovery', 0x200000, 0x299000)]
    frames = (e for e in events(area/'events.jsonl') if e['event'] == 'nor-mapped-read-returned')
    def consume(iterator, address, end, record):
        digest = hashlib.sha256(); count = 0
        while address+count < end:
            frame = next(iterator)
            raw = bytes.fromhex(frame['data_hex'])
            cli.require(frame['address'] == address+count and 0 < len(raw) <= 1024 and
                        len(raw) <= end-address-count, 'physical archive frame ordering')
            digest.update(raw); count += len(raw)
        cli.require(count == record['bytes'] and digest.hexdigest() == record['sha256'] and
                    cli.record(Path(record['path'])) == record, 'SDK-correlated archive/file mismatch')
    for name, start, end in regions: consume(frames, start, end, worker['protected_before'][name])
    verification_bytes = 0
    for frame in frames:
        if frame['address'] == 0:
            frames = itertools.chain((frame,), frames)
            break
        size = len(bytes.fromhex(frame['data_hex']))
        cli.require(hw.LOW <= frame['address'] < frame['address']+size <= hw.HIGH, 'unexpected C-core read range')
        verification_bytes += size
    else: raise RuntimeError('missing post-transaction archives')
    for name, start, end in regions:
        consume(frames, start, end, worker['protected_after'][name])
        if name != 'recovery':
            cli.require(worker['protected_before'][name]['sha256'] == worker['protected_after'][name]['sha256'],
                        'protected region changed')
    cli.require(next(frames, None) is None, 'extra mapped read outside the audited sequence')
    internal = (e for e in events(area/'events.jsonl') if e['event'] == 'nor-internal-read-returned')
    consume(internal, 0x08000000, 0x08010000, worker['boot_after'])
    consume(internal, 0x08010000, 0x08010000+617588, worker['app_after'])
    cli.require(next(internal, None) is None, 'extra internal read frame')
    from p34_entry_audit import wire
    segments, segment = [], None
    for e in events(area/'events.jsonl'):
        if e['event'] == 'i2c-edge-attempt' and e['edge'] == 1:
            cli.require(segment is None, 'overlapping BCB capture')
            segment = [dict(event='i2c-capture-start')]
        if segment is not None:
            segment.append(e)
            if e['event'] == 'i2c-edge-verified' and e['edge'] == 5748:
                segments.append(segment); segment = None
    cli.require(len(segments) == 2 and segment is None, 'two complete BCB captures required')
    wires = []
    for segment, key in zip(segments, ('bcb_before', 'bcb_after')):
        capture = worker[key]
        wires.append(wire(segment, dict(before=worker['before'], capture=capture['capture'])))
        cli.require(cli.record(Path(capture['raw']['path'])) == capture['raw'], 'BCB raw-file drift')
    cli.require(worker['bcb_before']['raw']['sha256'] == worker['bcb_after']['raw']['sha256'], 'BCB changed')
    return dict(nor_archives=8, internal_images=2, bcb_traces=wires, c_core_physical_read_bytes=verification_bytes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--include-rebuild', action='store_true')
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode, 'isolated root required')
    store = cli.Store(ROOT); out = store.checked(args.output_dir)
    cli.require(not out.exists(), 'preserve audit')
    store.checked(out/'result.json')
    areas = ['p34-host-nor-status1', 'p34-host-nor-read1', 'p34-host-nor-mapped1']
    if args.include_rebuild: areas.append('p34-host-nor-rebuild1')
    results = []
    for name in areas:
        area = store.checked(ROOT/'.cache'/name)
        parent, worker, plan = (store.read(area/(n+'.json')) for n in ('parent', 'worker', 'plan'))
        cli.require(parent['exit'] == 0 and not parent['timeout'] and worker['close_returned'], 'worker not normally closed')
        cli.require(parent['after_history'] == plan['before_history'], 'authorized SEGGER history changed')
        evidence = [cli.record(area/n) for n in ('sdk.log', 'events.jsonl', 'worker.json', 'parent.json', 'plan.json')]
        for item in plan['inputs']:
            path = store.checked(area/'source'/Path(item['path']).relative_to(ROOT))
            value = cli.record(path)
            cli.require(value['sha256'] == item['sha256'] and value['bytes'] == item['bytes'], 'frozen snapshot drift')
            evidence.append(value)
        source = (ROOT/'.cache/p34-recovery-sources1/r2-a.bin').read_bytes() if name.endswith('rebuild1') else None
        if source is not None:
            cli.require(hashlib.sha256(source).hexdigest() == hw.PINNED, 'recovery source drift')
            evidence.append(cli.record(ROOT/'.cache/p34-recovery-sources1/r2-a.bin'))
            evidence.extend(worker['protected_before'].values())
            evidence.extend(worker['protected_after'].values())
            evidence.extend([worker['boot_after'], worker['app_after'], worker['bcb_before']['raw'], worker['bcb_after']['raw']])
        item = dict(area=name, trace=trace(area, worker, source=source), parent=cli.record(area/'parent.json'))
        if source is not None: item['physical_files'] = physical_files(area, worker)
        cli.require(all(cli.record(store.checked(record['path'])) == record for record in evidence), 'input changed during audit')
        item['evidence'] = evidence
        results.append(item)
    store.write(out/'result.json', dict(result='NOR_SDK_JOURNAL_AUDIT_PASS', traces=results,
        script=cli.record(Path(__file__)), hardware=False, scope='logged SDK operations and source-bound journal bytes'))
    print('NOR_SDK_JOURNAL_AUDIT_PASS', json.dumps(results))


if __name__ == '__main__': main()
