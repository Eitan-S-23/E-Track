"""Online sealed-segment audit primitives; no hardware entry or write authority.

Unlike the closed-session auditor, a successful intermediate segment must have
no native Close. State and journal sequence carry forward only after validation.
"""
from dataclasses import dataclass
import re

from .ap_journal import next_tar, valid_time
from p34_nor_audit import WREG, RREG, VALUE, RETURN


def uint32(value):
    return type(value) is int and 0 <= value <= 0xffffffff


def journal(rows, sequence, previous_end):
    pending = None
    for row in rows:
        event = row['event']
        if event == 'ap-call-attempt':
            sequence += 1
            if (pending is not None or type(row['sequence']) is not int or
                    row['sequence'] != sequence or type(row['ap']) is not int or
                    row['ap'] not in (0, 1) or row['operation'] not in ('read', 'write') or
                    type(row['index']) is not int or not 0 <= row['index'] <= 3 or
                    (row['value'] is not None if row['operation'] == 'read' else not uint32(row['value']))):
                raise ValueError('segment AP attempt ordering')
            pending = row
        elif event == 'ap-call-returned':
            if (pending is None or type(row['sequence']) is not int or row['sequence'] != sequence or
                    type(row['rc']) is not int or row['rc'] < 0 or
                    not valid_time(row['started']) or not valid_time(row['ended']) or
                    row['ended'] < row['started'] or
                    previous_end is not None and row['started'] < previous_end or
                    (not uint32(row['read_value']) if pending['operation'] == 'read' else row['read_value'] is not None)):
                raise ValueError('segment AP return/clock ordering')
            previous_end = row['ended']
            yield ((pending['operation'], 'AP' if pending['ap'] else 'DP', pending['index'],
                    pending['value'], row['read_value'], row['rc']), sequence, previous_end)
            pending = None
        elif event.startswith('ap-call-'):
            raise ValueError('unknown AP event')
    if pending is not None:
        raise ValueError('AP call crosses segment boundary')


def target_events(rows):
    frame = None
    for row in rows:
        event = row['event']
        if event.startswith(('recovery-word-', 'recovery-chunk-')):
            if not uint32(row.get('address')) or row['address'] % 4:
                raise ValueError('non-word target frame address')
            if event.startswith('recovery-word-') and not uint32(row.get('value')):
                raise ValueError('non-uint32 target frame value')
        if event in ('recovery-chunk-read-attempt', 'recovery-word-write-attempt'):
            if frame is not None:
                raise ValueError('overlapping target frames')
            frame = row
        elif event == 'recovery-chunk-read-returned':
            if (frame is None or frame['event'] != 'recovery-chunk-read-attempt' or
                    row['address'] != frame['address']):
                raise ValueError('unpaired chunk frame')
            raw = bytes.fromhex(row['data_hex'])
            address, size = frame['address'], frame['bytes']
            if (type(address) is not int or type(size) is not int or address % 4 or
                    not 0 < size <= 1024 or size % 4 or len(raw) != size or
                    address // 1024 != (address + size - 1) // 1024):
                raise ValueError('invalid chunk frame')
            for offset in range(0, size, 4):
                yield ('read', address + offset, int.from_bytes(raw[offset:offset+4], 'little'))
            frame = None
        elif event == 'recovery-word-write-returned':
            if (frame is None or frame['event'] != 'recovery-word-write-attempt' or
                    (row['address'], row['value']) != (frame['address'], frame['value'])):
                raise ValueError('unpaired target store')
            yield ('write', row['address'], row['value'])
            frame = None
        elif event == 'recovery-word-read':
            if frame is not None:
                raise ValueError('word read inside target frame')
            yield ('read', row['address'], row['value'])
        elif event.startswith(('recovery-word-', 'recovery-chunk-')):
            raise ValueError('unknown target event')
    if frame is not None:
        raise ValueError('target frame crosses segment boundary')


@dataclass(frozen=True)
class State:
    bank: int
    csw: int
    tar: object
    sequence: int = 0
    previous_end: object = None


class Cursor:
    """One serial connection, fail-closed even when raw and journal are altered."""
    def __init__(self, metadata):
        self.metadata = dict(metadata)
        self.state = State(0, metadata['ap_csw'], None)
        self.error = None
        self.finished = False
        self.segments = 0
        self.native_calls = self.target_reads = self.target_writes = 0

    def verify(self, lines, rows, *, read_allowed, expected_stores, expected_dp_writes=(),
               final=False, bind_words=True, native_closed=False, switched_away=False):
        if self.error is not None or self.finished:
            raise ValueError('segment audit consumed/failed')
        try:
            return self._verify(lines, list(rows), read_allowed, tuple(expected_stores),
                                tuple(expected_dp_writes), final, bind_words, native_closed, switched_away)
        except BaseException as error:
            self.error = type(error).__name__ + ': ' + str(error)
            raise

    def _verify(self, lines, rows, read_allowed, stores, dp_writes, final, bind_words, native_closed, switched_away):
        if type(final) is not bool or type(switched_away) is not bool or final and switched_away:
            raise ValueError('distinct active/file-switch/native-close phases required')
        if (any(not uint32(a) or a % 4 or not uint32(v) for a, v in stores) or
                any(not uint32(v) or v not in (0, 0x40, 0x10000000, 0x10000040, 0x50000000, 0x50000040)
                    for v in dp_writes)):
            raise ValueError('invalid independent target/DP write plan')
        bank, csw, tar = self.state.bank, self.state.csw, self.state.tar
        sequence, previous_end = self.state.sequence, self.state.previous_end
        expected = iter(journal(rows, sequence, previous_end))
        targets = iter(target_events(rows)) if bind_words else None
        writable = {address for address, _ in stores}
        store_index = dp_index = count = reads = writes = closed = close_completed = 0
        log_switches = log_closed = 0
        observed = {}
        pending = None
        first, tail = [], []
        for line in lines:
            if ('CPU_WriteMem' in line or
                    re.search(r'JLINK(?:ARM)?_(?:Connect|Halt|Reset|Go|Step|SetRESET|ClrRESET|SetPower)\(', line)):
                raise ValueError('unlisted high-level device operation')
            if re.search(r'JLINK(?:ARM)?_Close\(', line):
                if closed or pending or log_switches or not final:
                    raise ValueError('intermediate/duplicate/mid-call native Close')
                closed += 1
            if re.search(r'JLINK(?:ARM)?_SetLogFile\(', line):
                if not switched_away or log_switches or closed or pending:
                    raise ValueError('unexpected/duplicate/mid-call log-file switch')
                log_switches += 1
            if re.fullmatch(r'\s*(?:T[0-9A-Fa-f]+\s+\d+:\d+\.\d+\s+)?Closed\s*', line):
                if closed and not close_completed:
                    close_completed += 1
                elif log_switches and not log_closed:
                    log_closed += 1
                else:
                    raise ValueError('unpaired/duplicate native Closed marker')
            wr, rd, val, ret = WREG.search(line), RREG.search(line), VALUE.search(line), RETURN.search(line)
            if wr or rd:
                if closed or log_switches or pending:
                    raise ValueError('post-Close/overlapping native call')
                pending = (['write', wr[1], int(wr[2], 16), int(wr[3], 16), None, None] if wr else
                           ['read', rd[1], int(rd[2], 16), None, None, None])
            elif val and pending and pending[0] == 'read':
                if pending[4] is not None:
                    raise ValueError('duplicate AP value')
                pending[4] = int(val[1], 16)
            elif ret and pending:
                pending[5] = int(ret[1])
                item = next(expected, None)
                if (pending[0] == 'read' and not uint32(pending[4]) or
                        item is None or tuple(pending) != item[0] or pending[5] < 0):
                    raise ValueError('native/journal segment mismatch')
                _, sequence, previous_end = item
                op, port, reg, value, data, _ = pending
                target = None
                if op == 'write':
                    if port == 'DP':
                        if reg == 2 and value in (0, 0xf0):
                            bank = value
                        elif reg == 1 and dp_index < len(dp_writes) and value == dp_writes[dp_index]:
                            dp_index += 1
                            observed.pop('dp', None)
                        else:
                            raise ValueError('DP write differs from independent phase plan')
                    elif reg == 0 and bank == 0:
                        if value not in (self.metadata['ap_csw'], (self.metadata['ap_csw'] & ~0x37) | 0x12):
                            raise ValueError('CSW write scope')
                        csw = value
                        observed.pop('csw', None)
                    elif reg == 1 and bank == 0:
                        if value != self.metadata['original_tar'] and value not in writable and not read_allowed(value):
                            raise ValueError('TAR outside segment scope')
                        tar = value
                        observed.pop('tar', None)
                    elif reg == 3 and bank == 0 and tar is not None and csw & 0x37 == 0x12:
                        if store_index >= len(stores) or stores[store_index] != (tar, value):
                            raise ValueError('target store differs from exact independent plan')
                        store_index += 1
                        writes += 1
                        target = ('write', tar, value)
                        tar = next_tar(tar)
                        observed.pop('tar', None)
                    else:
                        raise ValueError('AP write scope')
                else:
                    if port == 'DP':
                        if reg not in (0, 1):
                            raise ValueError('DP read scope')
                        if reg == 1:
                            observed['dp'] = data
                    elif reg in (0, 1) and bank == 0:
                        known = csw if reg == 0 else tar
                        if known is not None and data != known:
                            raise ValueError('observed AP state differs from tracked state')
                        observed['csw' if reg == 0 else 'tar'] = data
                        # An unknown wrap remains unknown until an explicit TAR write.
                    elif reg == 3 and bank == 0:
                        if tar is None or csw & 0x37 != 0x12 or not read_allowed(tar):
                            raise ValueError('target read scope')
                        reads += 1
                        target = ('read', tar, data)
                        tar = next_tar(tar)
                        observed.pop('tar', None)
                    elif not (reg == 3 and bank == 0xf0):
                        raise ValueError('AP identity scope')
                if targets is not None and target is not None and target != next(targets, None):
                    raise ValueError('target frame/native data mismatch')
                operation = tuple(pending)
                if len(first) < 3:
                    first.append(operation)
                tail = (tail + [operation])[-3:]
                count += 1
                pending = None
            elif re.search(r'JLINK\w*_(?:Write|CORESIGHT_(?:Read|Write))', line):
                raise ValueError('unrecognized native access')
        if (pending or next(expected, None) is not None or store_index != len(stores) or dp_index != len(dp_writes) or
                targets is not None and next(targets, None) is not None or closed != int(final) or
                close_completed != int(final) or log_switches != int(switched_away) or
                log_closed != int(switched_away) or not count):
            raise ValueError('incomplete sealed segment')
        if final and (tar != self.metadata['original_tar'] or csw != self.metadata['ap_csw'] or bank != 0):
            raise ValueError('final AP state not restored')
        if final and (native_closed is not True or not uint32(self.metadata.get('original_dp')) or
                      observed != dict(tar=self.metadata['original_tar'], csw=self.metadata['ap_csw'],
                                       dp=self.metadata['original_dp'])):
            raise ValueError('final native readbacks/Close return not proven')
        self.state = State(bank, csw, tar, sequence, previous_end)
        self.finished = final
        self.segments += 1
        self.native_calls += count
        self.target_reads += reads
        self.target_writes += writes
        return dict(native_calls=count, target_reads=reads, target_writes=writes, native_close=closed,
                    native_close_completed=close_completed,
                    log_file_switches=log_switches, log_file_closed=log_closed,
                    first=first, tail=tail, sequence=sequence)


def flash_stores(image, preimage, index):
    """Independent ordered DRW oracle for one successful, unmodified Sector."""
    from .flash_plan import geometry, APP_START, SECTOR_SIZE, IMAGE_SIZE
    from .flash_port import BANKS, KEY1, KEY2
    extent = geometry(image)
    if (type(preimage) is not bytes or len(preimage) != extent.erase_end - APP_START or
            type(index) is not int or not 0 <= index < len(extent.sectors)):
        raise ValueError('exact full preimage and sector index required')
    address, bank = extent.sectors[index]
    key, status, ctrl, addr = BANKS[bank-1]
    offset = address - APP_START
    after = (image + preimage[IMAGE_SIZE:])[offset:offset+SECTOR_SIZE]
    result = [(key, KEY1), (key, KEY2), (status, 0x34), (ctrl, 2), (addr, address),
              (ctrl, 0x42), (ctrl, 0), (ctrl, 0x80)]
    words = [(address+i, int.from_bytes(after[i:i+4], 'little')) for i in range(0, SECTOR_SIZE, 4)
             if after[i:i+4] != b'\xff'*4]
    if words:
        result.extend(((key, KEY1), (key, KEY2), (ctrl, 1)))
        for item in words:
            result.extend(((status, 0x34), item))
        result.extend(((ctrl, 0), (ctrl, 0x80)))
    return tuple(result)


class SealedGate:
    """Audit a switched-away original file before granting the next segment.

    switch/connection ownership and physical write admission belong to the future
    coordinator. This class cannot open a device or grant that missing admission.
    """
    def __init__(self, paths, metadata, record):
        if not paths or len(set(paths)) != len(paths):
            raise ValueError('distinct preflighted original segment paths required')
        self.paths, self.record = tuple(paths), record
        self.cursor = Cursor(metadata)
        self.index = 0
        self.active = False
        self.error = None
        self.records = []
        self.boundary = None

    def check(self):
        if self.error is not None or self.cursor.error is not None or self.cursor.finished:
            raise ValueError('sealed gate consumed/failed')

    def begin(self, index):
        self.check()
        if self.active or type(index) is not int or index != self.index or index >= len(self.paths):
            self.error = 'segment replay/order violation'
            raise ValueError(self.error)
        self.active = True

    def seal(self, index, rows, *, read_allowed, expected_stores, expected_dp_writes=(),
             final=False, bind_words=True, native_closed=False):
        try:
            self.check()
            if not self.active or index != self.index or final != (index == len(self.paths)-1):
                raise ValueError('segment seal order/final mismatch')
            path = self.paths[index]
            before = self.record(path)
            if before['path'] != str(path) or not 0 < before['bytes'] <= 16*1024*1024:
                raise ValueError('invalid sealed SDK segment')
            with path.open('r', encoding='utf-8', errors='strict') as stream:
                result = self.cursor.verify(stream, rows, read_allowed=read_allowed,
                                            expected_stores=expected_stores, expected_dp_writes=expected_dp_writes,
                                            final=final, bind_words=bind_words, native_closed=native_closed,
                                            switched_away=not final)
            if self.boundary is not None and result['first'] != self.boundary:
                raise ValueError('post-switch AP state differs from sealed tail')
            if not final:
                tail = result['tail']
                if (len(tail) != 3 or [op[:3] for op in tail] !=
                        [('read', 'DP', 1), ('read', 'AP', 0), ('read', 'AP', 1)] or
                        tail[0][4] & 0xf0000000 != 0xf0000000 or tail[0][4] & 0xb2 or
                        tail[1][4] != self.cursor.metadata['ap_csw'] or tail[1][4] & 0x37 != 0x12):
                    raise ValueError('missing/unhealthy pre-switch AP state')
                self.boundary = tail
            # Rehash every original at final closure, not quadratically per sector.
            if (self.record(path) != before or
                    final and self.records != [self.record(p) for p in self.paths[:index]]):
                raise ValueError('sealed original SDK bytes changed')
            self.records.append(before)
            self.index += 1
            self.active = False
            return result
        except BaseException as error:
            self.error = type(error).__name__ + ': ' + str(error)
            raise
