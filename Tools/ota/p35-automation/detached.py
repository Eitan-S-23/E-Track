"""Bounded Windows supervisor outside the disposable terminal Job.

The supervised command still uses the existing owned Windows Job and receipts.
Detachment is explicit and verified, never a fallback from failed ownership.
"""
import argparse
import contextlib
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys
import time
import re

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner as r


def in_job():
    r.require(os.name == 'nt', 'detached supervisor requires Windows')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    kernel.IsProcessInJob.restype = wintypes.BOOL
    member = wintypes.BOOL()
    if not kernel.IsProcessInJob(kernel.GetCurrentProcess(), None, ctypes.byref(member)):
        raise ctypes.WinError(ctypes.get_last_error())
    return bool(member.value)


def launch(out, argv, env, *, seconds, pins=()):
    h = r.load_host()
    out = h.checked(out)
    r.require(not out.exists(), 'supervisor output already exists; reconcile, never relaunch')
    r.require(type(seconds) is int and 1 <= seconds <= 18000, 'bounded supervisor deadline')
    r.require(isinstance(argv, list) and argv and all(isinstance(x, str) and x for x in argv), 'command argv')
    for name in ('launch.json', 'started.json', 'ready.json', 'result.json', 'worker.stdout', 'worker.stderr',
                 'command.stdout', 'command.stderr', 'command.started.json', 'command.closed.json', 'host'):
        h.checked(out / name)
    broker = Path(__file__).with_suffix('.vbs')
    checked_pins = [h.record(Path(__file__)), h.record(broker)] + list(pins)
    for pin in checked_pins:
        h.pinned(pin)
    child_env = h.environment(out)
    # Secrets are loaded by the task's existing protected-input adapter inside
    # the worker, not transported through WMI argv, files or environment dumps.
    read_only_env = {k:env[k] for k in ('GH_CONFIG_DIR',) if env.get(k)}
    h.save(out / 'launch.json', dict(argv=argv, seconds=seconds, pins=checked_pins, readOnlyEnv=read_only_env))
    worker = [str(Path(sys.executable).with_name('pythonw.exe')), '-I', '-S', '-B', '-u', '-X', 'utf8', str(Path(__file__).resolve()),
              '--worker', str(out)]
    try:
        raw = h.command(out, 'broker', ['cscript.exe', '//nologo', '//B', '//T:15', str(broker),
                        subprocess.list2cmdline(worker), str(r.ROOT)], child_env, seconds=20)
        match = re.fullmatch(rb'PID=(\d+)\s*', raw)
        r.require(match is not None, 'WMI process creation not confirmed; do not retry')
        pid = int(match[1])
        h.save(out / 'started.json', dict(pid=pid, argv=worker, broker='Win32_Process.Create', hidden=True,
            launcherPid=os.getpid(), launcherInJob=in_job(), monotonicNs=time.monotonic_ns()))
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if (out / 'ready.json').exists():
                ready = h.read_json(out / 'ready.json')
                r.require(ready['pid'] == pid and ready['inJob'] is False, 'worker detachment unverified')
                return ready
            if (out / 'result.json').exists():
                raise r.Stop('SUPERVISOR_FAILED', 'worker exited before readiness; inspect preserved receipts')
            time.sleep(.05)
        raise r.Stop('SUPERVISOR_UNKNOWN', 'readiness unknown; do not launch another worker')
    except BaseException as error:
        h.save(out / 'launch-failure.json', dict(errorType=type(error).__name__,
            detail=str(error), replay=False))
        raise


def worker(out):
    h = r.load_host()
    out = h.checked(out)
    manifest = h.read_json(out / 'launch.json')
    result = dict(outcome='SUPERVISOR_FAILED', exitCode=None)
    try:
        r.require(not in_job(), 'worker still belongs to terminal Job; no command started')
        for pin in manifest['pins']:
            h.pinned(pin)
        h.save(out / 'ready.json', dict(pid=os.getpid(), inJob=False, monotonicNs=time.monotonic_ns(),
            seconds=manifest['seconds']))
        env = h.environment(out)
        env.update(manifest['readOnlyEnv'])
        h.command(out, 'command', manifest['argv'], env, seconds=manifest['seconds'], success_codes=(0, 2))
        closed = h.read_json(out / 'command.closed.json')
        r.require(closed['cleanup_complete'] and not closed['stopped_while_running'], 'command closure incomplete')
        result.update(outcome='COMMAND_COMPLETED', exitCode=closed['exit_code'],
            commandReceipt=h.record(out / 'command.closed.json'))
    except BaseException as error:
        result.update(errorType=type(error).__name__, detail=str(error))
    h.save(out / 'result.json', result)
    return 0 if result['outcome'] == 'COMMAND_COMPLETED' else 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', type=Path, required=True)
    args = parser.parse_args()
    r.require(Path.cwd() == r.ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              'isolated Python from the active root required')
    h = r.load_host()
    out = h.checked(args.worker)
    with h.checked(out / 'worker.stdout').open('x', encoding='utf-8') as stdout, \
         h.checked(out / 'worker.stderr').open('x', encoding='utf-8') as stderr, \
         contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        raise SystemExit(worker(out))
