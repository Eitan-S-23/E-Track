"""Reuse tested archival: protect30249, preserve inactive30248 without deletion."""
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_radio_archive as archive
import p34_batch_install as install

cli = archive.cli
OUT = install.AREA / 'archive-001'
PRIORITY = ROOT / '.cache/p34-radio-fix/recorder-fix/trials-v2/priority'


if __name__ == '__main__':
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'explicit root and isolated Python required')
    s = cli.Store(ROOT)
    installed = s.read(install.OUT / 'result.json')
    cli.require(installed['result'] == 'FIXED_SIGNER_BATCH_UPDATE_VERIFIED' and installed['usb_closed'] and
                installed['snapshot_preserved'] and installed['configuration_preserved'], 'install unresolved')
    closed = s.read(install.AREA / 'runtime/install-001/closed.json')
    cli.require(closed['worker_exit'] == 0 and not closed['forced_termination'], 'installer still owns phone')
    tests = s.read(archive.AREA / 'archive-tests/result.json')
    cli.require(tests['result'] == 'PASS' and tests['source'] == cli.record(archive.__file__) and
                tests['test'] == cli.record(archive.TEST), 'archive guards changed')
    supervisor = cli.load_module('batch_archive_owner', ROOT / '.cache/p3-4-screening-20260922/supervisor.py')
    if sys.argv[1:] == ['launch']:
        cli.require(not OUT.exists(), 'preserve archive attempt')
        for name in ('intent.json', 'result.json', 'stop-intent.json', 'mkdir-intent.json',
                     'move-intent.json', 'capture', 'usb', 'host'):
            s.checked(OUT / name)
        archive.proof(s, install.prior.PRIOR)
        archive.proof(s, PRIORITY)
        s.write(OUT / 'intent.json', dict(source=cli.record(__file__), implementation=cli.record(archive.__file__),
            tests=tests, selected_version=30248, protected_version=30249, no_delete=True, no_ota=True))
        print(supervisor.owned.launch(install.AREA / 'runtime/archive-001', Path(__file__), ['worker'], 600))
    else:
        cli.require(sys.argv[1:] == ['worker'] and supervisor.owned.in_job(), 'finite archive owner required')
        radio = types.SimpleNamespace(ORDER=('combined',), TRIALS=install.prior.PRIOR.parent,
            old=types.SimpleNamespace(TRIAL=PRIORITY), APK=install.AREA / 'apk-g1/apk.json', backend=archive.radio.backend)
        fn = archive.worker
        types.FunctionType(fn.__code__, dict(fn.__globals__, radio=radio), fn.__name__)(s, 'combined', OUT)
