"""Reconcile closed host evidence without upgrading a truncated native SDK audit."""
import argparse
from collections import deque
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
import p34_nor_audit as audit
import p34_install_cost as host
from recovery_entry import host_nor as hn

cli = audit.cli
AREA = ROOT/'.cache/p34-host-nor-rebuild1'
FAILURE = ROOT/'.cache/p34-nor-audit1/failure.json'
PAIRS = {
    'attempt': ('returned', ('operation',)),
    'debug-write-attempt': ('debug-write-returned', ('address', 'value', 'operation')),
    'i2c-edge-attempt': ('i2c-edge-verified', ('edge', 'pin', 'high')),
    'nor-ap-csw-restore-attempt': ('nor-ap-csw-restored', ('value',)),
    'nor-cache-bypass-attempt': ('nor-cache-bypass-returned', ('value',)),
    'nor-fifo-burst-attempt': ('nor-fifo-burst-returned', ('bytes',)),
    'nor-fifo-read-attempt': ('nor-fifo-read-returned', ()),
    'nor-mapped-read-attempt': ('nor-mapped-read-returned', ('address',)),
    'nor-mmio-write-attempt': ('nor-mmio-write-returned', ('address', 'value')),
    'nor-mutation-command-attempt': ('nor-mutation-command-returned', ('address', 'value')),
    'nor-read-command-write-attempt': ('nor-read-command-write-returned', ('address', 'value')),
    'nor-tx-attempt': ('nor-tx-returned', ('bytes',)),
}
PASSIVE = {'control-word', 'owner-word', 'presence', 'setting', 'state-word',
           'i2c-record-data-sampled', 'nor-internal-read-returned', 'nor-fifo-word',
           'nor-mmio-read', 'nor-tx-word', 'nor-mutation-start', 'nor-mutation-settled'}
SOURCES = [Path(__file__), ROOT/'tests/boot/test_p34_nor_reconcile.py',
           Path(audit.__file__), ROOT/'Tools/ota/p34_entry_audit.py',
           ROOT/'Tools/ota/recovery_entry/host_writer.py', Path(host.__file__), Path(cli.__file__)]


def journal(rows, source):
    target = audit.Targets(source)
    reverse = {v[0]: (k, v[1]) for k, v in PAIRS.items()}
    pending, pairs, last_status = {}, 0, deque(maxlen=2)
    active, phase, status_opcode, settled = None, None, None, 0
    tx_words, tx_data = [], None
    for e in rows:
        name = e['event']
        cli.require(name in PAIRS or name in reverse or name in PASSIVE, 'unknown/failure journal event')
        if name in PAIRS:
            cli.require(name not in pending, 'overlapping journal attempt')
            pending[name] = e
            if name == 'nor-tx-attempt':
                tx_data = bytes.fromhex(e['data_hex']); tx_words = []
                cli.require(len(tx_data) == e['bytes'] and e['csw'] & 0x37 == 2, 'TX chunk format')
        elif name in reverse:
            before, keys = reverse[name]
            start = pending.pop(before, None)
            cli.require(start is not None and all(start[k] == e[k] for k in keys), 'missing/mismatched journal return')
            if 'data_hex' in e:
                cli.require(len(bytes.fromhex(e['data_hex'])) == start['bytes'], 'returned read length mismatch')
            if name == 'nor-tx-returned':
                cli.require(b''.join(v.to_bytes(4, 'little') for v in tx_words) == tx_data, 'TX words/chunk mismatch')
                cli.require(active is not None and e['remaining'] ==
                            len(target.actions[active-1][2])-start['offset']-e['bytes'], 'TX remaining mismatch')
                tx_data = None
            pairs += 1
        if name == 'nor-mutation-start':
            cli.require(active is None and e['index'] == settled+1 and target.index == settled, 'mutation start order')
            kind, address, data = target.actions[settled]
            cli.require((e['kind'], e['address'], e['bytes']) == (kind, address, len(data)) and
                        list(last_status) == [(5, 0), (0x35, 2)], 'mutation identity/pre-WREN status')
            active, phase = e['index'], 'start'
        address = value = None
        if name in audit.WRITE_EVENTS: address, value = e['address'], e['value']
        elif name == 'nor-cache-bypass-attempt': address, value = 0xa000103c, e['value']
        elif name == 'nor-tx-word':
            cli.require(tx_data is not None and e['offset'] == pending['nor-tx-attempt']['offset']+4*len(tx_words),
                        'TX word without matching chunk')
            tx_words.append(e['value']); address, value = hn.DT, e['value']
        if address is not None:
            opcode = value >> 24 if address == hn.BASE+12 else None
            if opcode == 6:
                cli.require(active is not None and phase == 'start', 'WREN outside active mutation')
                phase = 'wren'
            elif opcode in (2, 0x20):
                cli.require(active is not None and phase == 'wel', 'mutation without observed WEL')
                phase = 'poll'
            elif opcode in (5, 0x35):
                cli.require(status_opcode is None, 'status result missing')
                status_opcode = opcode
            target.write(address, value, 0x23000042)
        if name == 'nor-mmio-read' and e['address'] == hn.RSTS and status_opcode is not None:
            value = e['value'] & 255
            last_status.append((status_opcode, value))
            if active is not None:
                cli.require(status_opcode == 5, 'unexpected status opcode during mutation')
                if phase == 'wren':
                    cli.require(value == 2, 'WEL not observed'); phase = 'wel'
                elif phase in ('poll', 'settled'):
                    cli.require(value in (0, 1, 3) and phase != 'settled', 'invalid WIP/WEL settlement')
                    if value == 0: phase = 'settled'
                else: raise RuntimeError('status in wrong mutation phase')
            status_opcode = None
        if name == 'nor-mutation-settled':
            cli.require(active == e['index'] and phase == 'settled' and target.index == active and
                        target.tx is None and tx_data is None and not pending, 'unsettled/unfinished mutation')
            limit = 3 if target.actions[active-1][0] == 'erase' else .5
            cli.require(0 <= e['elapsed_seconds'] < limit, 'settlement deadline')
            settled, active, phase = active, None, None
    cli.require(not pending and active is None and status_opcode is None, 'unreturned journal operations')
    target.finish()
    cli.require(settled == len(target.actions), 'missing settled mutations')
    return dict(attempt_return_pairs=pairs, mutation_commands=target.index, settled_mutations=settled,
                target_writes=target.count, nor_commands=target.commands, tx_payload_bytes=target.tx_bytes)


def records(store):
    worker, parent, plan = (store.read(AREA/(n+'.json')) for n in ('worker', 'parent', 'plan'))
    cli.require(worker['result'] == 'RECOVERY_30276_VERIFIED_ORIGINAL_APP_HALTED' and worker['close_returned'] and
                parent['exit'] == 0 and not parent['timeout'] and worker['controller']['restored'] and
                worker['controller']['error'] is None and worker['transaction']['native_result'] == 0 and
                worker['transaction']['callback_error'] is None, 'closed verified worker required')
    cli.require(parent['after_history'] == plan['before_history'], 'native history changed')
    failure = store.read(FAILURE)
    cli.require(failure['result'] == 'EVIDENCE_GAP_NATIVE_SDK_LOG_TRUNCATED', 'original SDK gap required')
    evidence = [cli.record(AREA/n) for n in ('sdk.log', 'events.jsonl', 'worker.json', 'parent.json',
                'plan.json', 'preimages.json', 'admission.json', 'admission.log')]+[cli.record(FAILURE)]
    for rec in failure['inputs']:
        cli.require(cli.record(store.checked(rec['path'])) == rec, 'failed-audit input drift')
    for rec in plan['inputs']:
        p = store.checked(rec['path']); snap = store.checked(AREA/'source'/p.relative_to(ROOT))
        cli.require(cli.record(p) == rec, 'executor source drift')
        frozen = cli.record(snap)
        cli.require((frozen['bytes'], frozen['sha256']) == (rec['bytes'], rec['sha256']), 'snapshot drift')
        evidence.extend((rec, frozen))
    import p34_probe_acquire as base
    # The exact DLL is a read-only external input, never an output boundary.
    dll = cli.record(base.JLINK/'JLink_x64.dll')
    cli.require(dll['sha256'] == base.DLL_SHA, 'native DLL drift')
    evidence.append(dll)
    for name in ('writer', 'bcb_reader', 'validator'):
        cli.require(cli.record(store.checked(plan[name]['path'])) == plan[name], 'native tool drift')
        evidence.append(plan[name])
    evidence.extend([worker['slot'], worker['boot_after'], worker['app_after'], worker['bcb_before']['raw'],
                     worker['bcb_after']['raw'], *worker['protected_before'].values(), *worker['protected_after'].values()])
    return worker, evidence


def reconcile(store):
    worker, evidence = records(store)
    source_path = ROOT/'.cache/p34-recovery-sources1/r2-a.bin'
    source = source_path.read_bytes()
    cli.require(cli.record(source_path)['sha256'] == audit.hw.PINNED, 'recovery image drift')
    sequence = journal(audit.events(AREA/'events.jsonl'), source)
    archives = audit.physical_files(AREA, worker)
    cli.require((AREA/'recovery-physical-slot.bin').read_bytes() ==
                (AREA/'after-recovery.bin').read_bytes()+(AREA/'after-tail.bin').read_bytes(), 'slot composition drift')
    slot = (AREA/'recovery-physical-slot.bin').read_bytes()
    cli.require(slot[4096:4096+len(source)] == source, 'recovery payload mismatch')
    admission = store.read(AREA/'admission.json')
    cli.require(admission['exit'] == 0 and cli.record(AREA/'admission.log') == admission['log'] and
                'RECOVERY_ADMISSION result=0 reads=4845 version=30276' in (AREA/'admission.log').read_text(),
                'original Boot admission drift')
    for key, path in (('boot', '.cache/p34-native-acquire1/boot-readback.bin'),
                      ('app', '.cache/p34-native-image1/app-readback.bin')):
        cli.require(worker[key+'_after']['sha256'] == cli.record(ROOT/path)['sha256'], 'original internal image mismatch')
    for rec in evidence:
        cli.require(cli.record(Path(rec['path'])) == rec, 'consumed evidence changed')
    return dict(result='JOURNAL_ARCHIVES_RECONCILED_SDK_INCOMPLETE', journal=sequence, archives=archives,
                historical_sdk_audit_passed=False, resume_authorized=False, hardware_operations=0,
                gap=store.read(FAILURE), evidence=evidence, sources=[cli.record(p) for p in SOURCES],
                interpretation='Source-bound host execution/readback, not independent native-write equality.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('selftest', 'reconcile'))
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated project root required')
    store = cli.Store(ROOT); out = store.checked(args.output_dir)
    cli.require(not out.exists(), 'preserve reconciliation')
    for name in ('result.json', 'tests.json', 'tests.log'): store.checked(out/name)
    inputs = [cli.record(p) for p in SOURCES]
    if args.action == 'selftest':
        env = host.environment(store, out)
        data = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8', SOURCES[1], '-v'], env, 180)
        match = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', data)
        cli.require(match is not None, 'test summary missing')
        result = dict(result='NOR_RECONCILE_TESTS_PASS', tests=int(match[1]), sources=inputs, hardware_operations=0)
    else: result = reconcile(store)
    cli.require(inputs == [cli.record(p) for p in SOURCES], 'source changed')
    store.write(out/'result.json', result)
    print(result['result'], json.dumps(result.get('journal', {})))


if __name__ == '__main__': main()
