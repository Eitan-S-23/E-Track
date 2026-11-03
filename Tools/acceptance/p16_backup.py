"""Read-only recovery inputs before the authorized P1-6 group16 campaign."""
import argparse
import csv
import hashlib
import importlib.util
import io
from pathlib import Path
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota/p34-acceptance'))
import live_host as h
import live_mcu as m

COMMAND = h.command


def passive(out, label, argv, env, **kwargs):
    argv = list(map(str, argv))
    if label == 'commander':
        index = argv.index('-Device') + 1
        h.require(argv[index] == 'AT32F435RGT7', 'unexpected device profile')
        argv[index] = 'CORTEX-M4'
        lines = Path(argv[argv.index('-CommandFile') + 1]).read_text(encoding='ascii').splitlines()
        allowed = set(m.START) | {'sleep 1000', 'qc'}
        h.require(all(line in allowed or line.startswith('savebin "') for line in lines), 'not a passive command')
    raw = COMMAND(out, label, argv, env, **kwargs)
    if label == 'processes':
        names = {row[0].lower() for row in csv.reader(io.StringIO(raw.decode('utf8', 'replace'))) if row}
        h.require('uv4.exe' not in names, 'Keil owns or could acquire the probe')
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    h.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              'explicit isolated worktree execution required')
    out = h.checked(args.out)
    plan = h.read_json(ROOT / '.cache/p17-key-method-20261104-01/key-plan-03.json')['retained']
    for root in (ROOT, Path('D:/github/my/E-Track')):
        for name in ('p34-live-device.lock', 'p35-pipeline.lock', 'p35-reconcile-device.lock'):
            h.require(not (root / '.cache' / name).exists(), 'outstanding device owner')
    for name in ('intent.json', 'result.json', 'failure.json', 'symbols-target', '0001-before', '0002-backups', '0003-after'):
        h.checked(out / name)
    h.fresh(out)
    h.save(out / 'intent.json', dict(task='P1-6', purpose='Read-only recovery preparation, not fault acceptance',
        plan=plan, operations=dict(reset=0, halt=0, flash=0, persistentWrite=0)))
    old = h.command
    h.command = passive
    try:
        with h.device_owner(out):
            mcu = m.MCU(plan, out)
            before = mcu.inspect('target', 'before')
            table = mcu.bind('target')['table']
            commands = [('internal', 0x08000000, 0x100000), ('candidate', 0x90000000, 0x100000),
                        ('backup', 0x90100000, 0x100000), ('recovery', 0x90200000, 0x100000),
                        ('fpb', 0xe0002000, 40), ('tick', table['SystemTickCount'][0], 4)]
            raw, _, folder = mcu.execute(commands, {name:size for name,_,size in commands}, 'backups', seconds=300)
            h.require(raw['internal'][:65536] == h.pinned(plan['boot']).read_bytes(), 'Boot changed during backup')
            image = h.pinned(plan['images']['target']['image']).read_bytes()
            h.require(raw['internal'][65536:65536 + len(image)] == image, 'App changed during backup')
            fpb = struct.unpack('<10I', raw['fpb'])
            h.require(all(not word & 1 for word in fpb[2:8]), 'active hardware breakpoint')
            spec = importlib.util.spec_from_file_location('p16_backup_validator', ROOT / 'Tools/jlink/prepare-bootstrap-app.py')
            validator = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(validator)
            slots = {}
            for name, kind in (('candidate', 1), ('backup', 2), ('recovery', 4)):
                data = raw[name]
                header = m.slot_header(data[:32], kind)
                h.require(not header.get('erased'), 'restore slot lacks original image')
                payload = data[4096:4096 + header['bytes']]
                parsed = validator.validate_app(payload)
                h.require(parsed['version_code'] == header['version'] and
                          zlib.crc32(payload) == header['crc32'] and payload[0x428:0x430].hex() == header['sha8'],
                          'slot header/payload mismatch: ' + name)
                slots[name] = dict(header=header, raw=h.record(folder / (name + '.bin')),
                                   imageSha256=hashlib.sha256(payload).hexdigest(), payloadBytes=len(payload))
            after = mcu.inspect('target', 'after')
            h.require(before['storage'] == after['storage'] and after['registers']['freeze'] == 0,
                      'storage changed or debug freeze left enabled')
            h.save(out / 'result.json', dict(outcome='READ_ONLY_RECOVERY_INPUTS_CAPTURED', slots=slots,
                internal=h.record(folder / 'internal.bin'), before=before, after=after,
                boardWrites=0, reset=0, halt=0, restorationQualified=False,
                limitation='A complete backup is not proof the restore command works; no AUTO row was executed.'))
            print('READ_ONLY_RECOVERY_INPUTS_CAPTURED', flush=True)
    except BaseException as error:
        h.save(out / 'failure.json', dict(error=str(error), noAutomaticRetry=True,
            mutationsRequested=False, lockRetained=(ROOT / '.cache/p34-live-device.lock').exists()))
        raise
    finally:
        h.command = old


if __name__ == '__main__':
    main()
