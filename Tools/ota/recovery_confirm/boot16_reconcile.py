"""Original closed-log reconciliation; uncertainty never grants a restore token."""
import hashlib

import p34_boot16_probe as prior
from . import boot16_program as p
from .mutation_audit import SealedGate, target_events


def require(value, message):
    if not value: raise ValueError(message)


def partitions(rows):
    groups, current = [], []
    for row in rows:
        if row['event'] == 'online-log-switch-returned':
            require((row['old'], row['new']) == (len(groups), len(groups)+1), 'Boot16 log order')
            groups.append(current)
            current = []
        current.append(row)
    groups.append(current)
    return groups


def entry_state(rows):
    first, contexts, selected, values = {}, [], None, []
    wanted = (p.PAUSE, 0xe0002000, p.REGS['dfsr'], p.REGS['demcr'], *range(p.COMP, p.COMP+24, 4))
    for op, address, value in target_events(rows):
        if op == 'read' and address in wanted: first.setdefault(address, value)
        if op == 'write' and address == p.DCRSR:
            require(selected is None and value == (15, 16, 17, 20)[len(values)], 'CPU selector order')
            selected = value
        if op == 'read' and address == prior.entry.DCRDR:
            require(selected is not None, 'unsolicited CPU register read')
            values.append(value)
            selected = None
        if op == 'read' and address == 0xe000ef34:
            require(len(values) == 4 and selected is None, 'incomplete CPU context')
            contexts.append(dict(zip(('pc', 'xpsr', 'msp', 'special', 'fpccr'), [*values, value])))
            values = []
    require(len(contexts) == 2 and contexts[0] == contexts[1] and prior.entry.context_ok(contexts[0]),
            'two matching admitted contexts required')
    before = dict(pause=first[p.PAUSE], fp=first[0xe0002000], dfsr=first[p.REGS['dfsr']],
                  demcr=first[p.REGS['demcr']], comparators=[first[p.COMP+4*i] for i in range(6)])
    require(before['fp'] == 0x261 and before['comparators'] == [0]*6, 'unowned entry breakpoint')
    return before, contexts[0]


def capture_specs():
    specs = []
    for label in ('before', 'after'):
        for name, address, size in (('boot', p.boot16.START, 65536), ('app', p.APP, p.APP_BYTES)):
            for offset in range(0, size, p.BLOCK):
                specs.append((label+'-'+name, offset, address+offset, min(p.BLOCK, size-offset)))
    return specs


def capture_bytes(rows, address, size):
    chunks = [row for row in rows if row['event'] == 'recovery-chunk-read-returned'
              and address <= row['address'] < address+size]
    require([r['address'] for r in chunks] == list(range(address, address+size, 1024)), 'capture coverage/order')
    raw = b''.join(bytes.fromhex(row['data_hex']) for row in chunks)
    require(len(raw) == size, 'capture size differs')
    return raw


def reconcile(paths, rows, metadata, record, plan, image, preimage, *, failed=False):
    """Activation originals only. Restoring an already-failed restore is not automatic."""
    groups = partitions(rows)
    require(len(paths) == len(groups), 'all original log segments required')
    require(25 <= len(groups) <= 53 if failed else len(groups) == 57, 'not a pre-release programming failure')
    before, context = entry_state(groups[1])
    plan.desired('activate', preimage)
    selectors = list(p.SELECTORS)
    entry_stores = [(p.PAUSE, before['pause'] | 0x1000), (p.COMP, p.WFI_COMPARATOR)]
    entry_stores += selectors + [(p.COMP, 0)] + selectors
    captures = capture_specs()
    archives = {}
    gate = SealedGate(paths, metadata, record)
    acquisition, restore = prior.setup.dp_plan(metadata)
    previous = None
    terminal_stores = []
    for index, group in enumerate(groups):
        final = index == len(groups)-1
        if index == 0:
            reads, stores = set(), []
        elif index == 1:
            reads, stores = p.CONTROL_READS, entry_stores
        elif index == 2:
            reads, stores = p.CONTROL_READS | p.settle.READS, []
        elif 3 <= index <= 23 or 32 <= index <= 52:
            reads, stores = p.INTERNAL_READS, []
            at = index-3 if index <= 23 else index-32+21
            name, offset, address, size = captures[at]
            # A failed capture may have stopped after a complete native chunk.
            # The before set must be complete; incomplete after is not identity proof.
            if not (failed and final):
                raw = capture_bytes(group, address, size)
                wanted = image if name.endswith('app') else plan.original if name.startswith('before') else plan.activated
                require(raw == wanted[offset:offset+size], 'original capture bytes differ')
                archives.setdefault(name, bytearray()).extend(raw)
        elif 24 <= index <= 31:
            sector = index-24
            reads = p.CONTROL_READS | p.settle.READS | set(range(p.boot16.START+sector*2048, p.boot16.START+(sector+1)*2048, 4))
            stores = list(p.boot16.stores(plan, preimage, sector, 'activate'))
            if preimage[sector*2048:(sector+1)*2048] == plan.activated[sector*2048:(sector+1)*2048]: stores = []
            if failed and final:
                actual = [(a, v) for op, a, v in target_events(group) if op == 'write']
                require(actual == stores[:len(actual)], 'interrupted sector diverges from exact plan')
                stores = actual
                terminal_stores = actual
        elif index == 53:
            reads = p.CONTROL_READS | p.settle.READS
            stores = selectors + ([] if before['dfsr'] & 2 else [(p.REGS['dfsr'], 2)]) + [(p.DHCSR, 0xa05f0001)]
        elif index == 54:
            reads, stores = p.CONTROL_READS, [(p.PAUSE, before['pause'])]
        elif index == 55:
            reads, stores = prior.health.old.READS, []
        else:
            reads, stores = set(), []
        if failed and final:
            require(metadata.get('dp_restore_deferred_for_halt') is True and
                    metadata.get('retained_dp_ctrlstat') == 0xf0000040, 'failed connection not retained')
            gate.cursor.metadata = dict(metadata, original_dp=0xf0000040)
        gate.begin(index)
        trace = gate.seal(index, group, read_allowed=lambda a: a in reads, expected_stores=stores,
            expected_dp_writes=acquisition if index == 0 else restore if final and not failed else [],
            final=final, native_closed=final)
        if index:
            heads = [r for r in group if r['event'] == 'online-log-head-verified']
            require(heads, 'missing active raw head')
            for head in heads:
                item = head['record']
                require(item['path'] == str(paths[index]) and type(item['bytes']) is int and
                        0 < item['bytes'] <= 65536, 'active head extent')
                with paths[index].open('rb') as stream: raw = stream.read(item['bytes'])
                require(len(raw) == item['bytes'] and hashlib.sha256(raw).hexdigest() == item['sha256'], 'active raw head changed')
                require(head['trace']['native_calls'] == 3 and head['trace']['sequence'] == previous['sequence']+3 and
                        [tuple(x) for x in head['trace']['first']] == list(previous['tail']), 'head continuity')
        previous = trace
    require(bytes(archives.get('before-boot', b'')) == preimage and
            bytes(archives.get('before-app', b'')) == image, 'full original preimage not proven')
    if not failed:
        require(bytes(archives.get('after-boot', b'')) == plan.activated and
                bytes(archives.get('after-app', b'')) == image, 'full postimage not proven')
    return dict(result='BOOT16_CLOSED_PREFIX_RECONCILED' if failed else 'BOOT16_CLOSED_NATIVE_RECONCILED',
        before=before, context=context, logs=gate.records, terminal_stores=terminal_stores,
        native_calls=gate.cursor.native_calls, target_reads=gate.cursor.target_reads,
        target_writes=gate.cursor.target_writes, archives={k: bytes(v) for k, v in archives.items()},
        boot_may_have_changed=failed, release_attempted=False if failed else True,
        phase='PROGRAM' if len(groups) <= 32 else 'POST_CAPTURE')
