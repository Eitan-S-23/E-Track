"""One newly authorized system report; HCI-only host retention, no OTA replay."""
import argparse
from contextlib import contextmanager
import datetime as dt
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_hci_export as export
import p34_hci_status as status

cli = status.cli
OUT = ROOT / '.cache/p34-hci/export-current-001'
RUNTIME = ROOT / '.cache/p34-hci/runtime/export-current-001'
TESTS = ROOT / '.cache/p34-hci/current-tests-001/result.json'
USB_SECONDS = 1500


class DeadlineIO:
    """Adapt only this session's initial receipt, not historical helper sources."""
    def __init__(self, original, ready):
        self.original, self.ready = original, ready
        self.used = False

    def __getattr__(self, name):
        return getattr(self.original, name)

    def write_json(self, root, path, value, **kwargs):
        if Path(path) == self.ready:
            cli.require(not self.used and not kwargs.get('replace'), 'initial deadline only')
            self.used = True
            value = dict(value, deadline=(dt.datetime.now(dt.timezone.utc) +
                dt.timedelta(seconds=USB_SECONDS)).isoformat(),
                deadline_adapter=cli.record(__file__), maximum_seconds=USB_SECONDS)
        return self.original.write_json(root, path, value, **kwargs)


class Backend:
    def __init__(self, original, out):
        self.original = original
        self.io = DeadlineIO(original.io, out / 'usb/ready.json')

    def __getattr__(self, name):
        return getattr(self.original, name)


class Evidence:
    def __init__(self, store):
        self.store = store

    def save(self, path, value):
        return self.store.write(path, value)

    def raw(self, path, value):
        import os
        path = self.store.checked(path)
        self.store.checked(path.parent).mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        return cli.record(path)


def generate(c, p, out):
    cli.require(not (out / 'generation-intent.json').exists(),
                'generation already reserved; reconcile without replay')
    before = export.remote_preflight(c, p, out)
    args = ['shell', 'bugreportz', '-p']
    c.save(out / 'generation-intent.json', dict(command=args, maximum_seconds=900,
        maximum_reports=1, authorized_directory=export.REMOTE, system_sidecars=True,
        authority='Current user explicitly approved one new report after HCI status-003',
        no_ota=True, no_install=True, delete_existing=False, upload=False))
    print('Generating the single newly authorized report', flush=True)
    raw = p.command(args, timeout=900, binary=True, check=False)
    c.raw(out / 'generation.stdout', raw)
    receipt = json.loads((p.RUNTIME / 'commands.jsonl').read_text().splitlines()[-1])
    cli.require(receipt['exit'] == 0, 'generation uncertain; reconcile, never regenerate')
    remote = export.completed_report(raw)
    cli.require(PurePosixPath(remote).name not in before, 'pre-existing report reused')
    c.save(out / 'generated.json', dict(remote=remote, maximum_reports=1))
    return remote


def retrieve(c, p, out, remote):
    remote = export.report_path(remote)
    cli.require(p.command(['shell', 'readlink', '-f', remote]).strip() == remote,
                'report resolves elsewhere')
    size = p.command(['shell', 'stat', '-c', '%s', remote]).strip()
    cli.require(size.isdigit() and 0 < int(size) <= export.MAX_ARCHIVE, 'report size bound')
    digest = p.command(['shell', 'sha256sum', remote]).split()[0]
    cli.require(re.fullmatch(r'[0-9a-f]{64}', digest), 'invalid report hash')
    blob = p.command(['exec-out', 'cat', remote], timeout=180, binary=True)
    cli.require(len(blob) == int(size) and hashlib.sha256(blob).hexdigest() == digest,
                'report readback differs')
    cli.require(p.command(['shell', 'sha256sum', remote]).split()[0] == digest,
                'report changed during retrieval')
    selected, names = export.hci_members(blob)
    extracted = [dict(member=name, original=c.raw(out / ('hci-%02d.btsnoop' % i), data),
                      summary=summary) for i, (name, data, summary) in enumerate(selected, 1)]
    c.save(out / 'archive.json', dict(remote=remote, bytes=len(blob), sha256=digest,
        extracted=extracted, bluetooth_member_names=names, whole_report_saved_on_host=False,
        phone_report_deleted=False))
    cli.require(extracted, 'no HCI members; preserve report, never regenerate')
    return dict(result='HCI_EXTRACTED', extracted=extracted, target_connection='NOT_ANALYZED')


def sources():
    return [cli.record(p) for p in (Path(__file__), Path(export.__file__),
        ROOT / 'tests/ota/test_p34_hci_current.py', ROOT / 'tests/ota/test_p34_hci_export.py',
        ROOT / '.cache/p34-next/device.py')]


def worker(s):
    tests = s.read(TESTS)
    cli.require(tests['passed'] and tests['sources'] == sources(), 'current host tests required')
    pointer, apk = status.inputs(s)
    b, d, p, lock = runpy.run_path(str(ROOT / 'Tools/ota/p34_signing_migration.py'))['runtime']()
    result = dict(result='HCI_EXPORT_INCOMPLETE', prior=pointer, no_ota=True, no_install=True)
    c = Evidence(s)
    try:
        with lock.device_lock(), d['usb'](Backend(b, OUT), p, OUT):
            p.phone_identity()
            cli.require(d['installed'](b, p, apk['apk']['sha256']) is not None, 'installed APK changed')
            remote = generate(c, p, OUT)
            result.update(retrieve(c, p, OUT, remote))
        result['usb_closed'] = True
    except Exception as error:
        result.update(error=type(error).__name__, detail=str(error),
                      next='Reconcile saved intent and phone reports; do not regenerate')
    s.write(OUT / 'result.json', result)
    print(json.dumps(result), flush=True)
    cli.require('error' not in result, 'report export requires reconciliation')


def main():
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, 'explicit root and isolated Python required')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('test', 'launch', 'worker'))
    mode = parser.parse_args().mode
    s = cli.Store(ROOT)
    if mode == 'test':
        import unittest
        sys.path.insert(0, str(ROOT / 'tests/ota'))
        cli.require(not TESTS.exists(), 'preserve test receipt')
        s.checked(TESTS)
        suite = unittest.defaultTestLoader.loadTestsFromNames(
            ['test_p34_hci_export', 'test_p34_hci_current'])
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        s.write(TESTS, dict(passed=result.wasSuccessful(), count=result.testsRun,
                           sources=sources(), device_operations=0))
        cli.require(result.wasSuccessful(), 'host tests failed')
        return
    owner = cli.load_module('current_hci_owner', ROOT / '.cache/p3-4-screening-20260922/supervisor.py')
    if mode == 'launch':
        cli.require(not OUT.exists() and not RUNTIME.exists(), 'spent report scope; reconcile only')
        tests = s.read(TESTS)
        cli.require(tests['passed'] and tests['sources'] == sources(), 'current tests required')
        pointer, apk = status.inputs(s)
        for name in ('intent.json', 'result.json', 'preflight.json', 'generation-intent.json',
                     'generation.stdout', 'generated.json', 'archive.json', 'usb', 'host'):
            s.checked(OUT / name)
        for i in range(1, 9):
            s.checked(OUT / ('hci-%02d.btsnoop' % i))
        s.write(OUT / 'intent.json', dict(source=cli.record(__file__), tests=cli.record(TESTS),
            prior=pointer, apk=apk['apk'], maximum_reports=1, no_ota=True, no_install=True,
            host_output=str(OUT), phone_output=export.REMOTE, seconds=1800))
        print(owner.owned.launch(s.checked(RUNTIME), Path(__file__), ['worker'], 1800))
    else:
        cli.require(owner.owned.in_job(), 'finite owned worker required')
        worker(s)


if __name__ == '__main__':
    main()
