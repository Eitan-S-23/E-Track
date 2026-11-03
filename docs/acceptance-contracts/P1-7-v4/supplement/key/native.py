"""Small interactive adapter for the installed Commander, not an SWD driver."""
from datetime import datetime, timezone
from pathlib import Path
import csv
import io
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
AREA = Path(__file__).resolve().parent
assert Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
sys.path.insert(0, str(ROOT / 'Tools/ota/p34-acceptance'))
import live_host as h


def words(reply, address, count):
    found = {}
    for match in re.finditer(r'(?m)^([0-9A-Fa-f]{8})\s*=\s*((?:[0-9A-Fa-f]{8}(?:\s+|$))+)', reply):
        for index, value in enumerate(match[2].split()):
            found[int(match[1], 16) + index * 4] = int(value, 16)
    h.require(all(address + i * 4 in found for i in range(count)), 'missing native memory words')
    return [found[address + i * 4] for i in range(count)]


class Commander:
    def __init__(self, plan, out, *, seconds=30):
        self.out, self.index = h.checked(out), 0
        self.deadline = time.monotonic() + seconds
        self.queue = queue.Queue()
        self.closed = False
        self.job = self.process = self.thread = None
        self.streams = []
        self.argv = [str(h.pinned(plan['tools']['commander'])), '-Device', 'CORTEX-M4',
                     '-If', 'SWD', '-Speed', '1000', '-USB', str(plan['probe_serial']),
                     '-AutoConnect', '0', '-ExitOnError', '1', '-NoGui', '1',
                     '-SettingsFile', str(h.checked(out / 'settings.jlink')),
                     '-Log', str(h.checked(out / 'sdk.log'))]
        for name in ('native.stdout', 'native.stderr', 'native.started.json', 'native.closed.json', 'commands'):
            h.require(not h.checked(out / name).exists(), 'spent native output')
        env = h.environment(out)
        processes = h.command(out, 'processes', ['tasklist', '/FO', 'CSV', '/NH'], env, seconds=15)
        names = {row[0].lower() for row in csv.reader(io.StringIO(processes.decode('utf8', 'replace'))) if row}
        blocked = {'uv4.exe', 'jlink.exe', 'jlinkrttlogger.exe', 'jlinkrttviewer.exe',
                   'jlinkgdbserver.exe', 'jlinkgdbservercl.exe', 'jlinkguiserver.exe',
                   'jflash.exe', 'jflashlite.exe', 'jmem.exe', 'jscope.exe', 'jlinkconfig.exe'}
        h.require(not names & blocked, 'another debugger exists')
        h.save(out / 'native.started.json', dict(argv=self.argv, cwd=str(ROOT), seconds=seconds,
                utc=datetime.now(timezone.utc).isoformat()))
        try:
            self.streams = [h.checked(out / ('native.' + kind)).open('xb') for kind in ('stdout', 'stderr')]
            self.job = h.host.owned.WindowsJob()
            self.process = subprocess.Popen(self.argv, cwd=ROOT, env=env, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=self.streams[1], creationflags=subprocess.CREATE_NO_WINDOW)
            self.job.assign(self.process)
            self.thread = threading.Thread(target=self._reader, daemon=True)
            self.thread.start()
            self._prompt(10)
            for command in ('exec DisableAutoUpdateFW', 'exec SetRestartOnClose = 0',
                            'exec InhibitConnectRetries = 1', 'exec SetEnableMemCache = 0', 'connect'):
                reply = self.command(command, seconds=10)
            h.require('Cortex-M4 identified.' in reply, 'generic core not identified')
        except BaseException:
            self.close()
            raise

    def _reader(self):
        try:
            while True:
                data = os.read(self.process.stdout.fileno(), 4096)
                if not data:
                    break
                self.streams[0].write(data)
                self.streams[0].flush()
                self.queue.put(data)
        except BaseException as error:
            self.queue.put(error)
        finally:
            self.queue.put(None)

    def _prompt(self, seconds):
        deadline = min(self.deadline, time.monotonic() + seconds)
        data = bytearray()
        while True:
            remaining = deadline - time.monotonic()
            h.require(remaining > 0, 'native prompt deadline reached')
            try:
                item = self.queue.get(timeout=remaining)
            except queue.Empty:
                raise RuntimeError('native prompt timeout') from None
            h.require(item is not None and isinstance(item, bytes), 'native process ended or reader failed')
            data.extend(item)
            h.require(len(data) < 1024 * 1024, 'oversized native response')
            if bytes(data).rstrip().endswith(b'J-Link>'):
                return data.decode('utf8', 'replace')

    def command(self, command, *, seconds=5):
        h.require('\n' not in command and '\r' not in command and not self.closed, 'invalid command')
        h.require(time.monotonic() < self.deadline, 'session deadline reached')
        self.index += 1
        label = '%04d' % self.index
        before = time.monotonic_ns()
        h.save(self.out / 'commands' / (label + '.intent.json'), dict(command=command, startNs=before))
        self.process.stdin.write((command + '\n').encode('ascii'))
        self.process.stdin.flush()
        reply = self._prompt(seconds)
        h.raw(self.out / 'commands' / (label + '.stdout'), reply.encode('utf8'))
        h.save(self.out / 'commands' / (label + '.closed.json'), dict(endNs=time.monotonic_ns()))
        h.require('Error:' not in reply and 'Unknown command' not in reply, 'native command rejected')
        return reply

    def read(self, address, count=1):
        h.require(0 < count <= 128, 'read bound')
        return words(self.command('mem32 0x%08X, %d' % (address, count)), address, count)

    def close(self):
        if self.closed:
            return
        errors = []
        try:
            if self.process and self.process.poll() is None:
                self.process.stdin.write(b'qc\n')
                self.process.stdin.flush()
                self.process.wait(timeout=5)
        except BaseException as error:
            errors.append(str(error))
        finally:
            if self.job:
                self.job.terminate()
                self.job.close()
            if self.process:
                self.process.wait(timeout=5)
                self.process.stdin.close()
            if self.thread:
                self.thread.join(timeout=5)
                h.require(not self.thread.is_alive(), 'native reader did not close')
            if self.process:
                self.process.stdout.close()
            for stream in self.streams:
                stream.close()
            self.closed = True
            h.save(self.out / 'native.closed.json', dict(exitCode=self.process.returncode if self.process else None,
                    cleanupComplete=True, closeErrors=errors, commandCount=self.index))


def qualify():
    plan = h.read_json(ROOT / '.cache/p17-generic-readiness-20261104-01/inspect-01/plan.json')
    for base in (ROOT, Path('D:/github/my/E-Track')):
        for name in ('p34-live-device.lock', 'p35-reconcile-device.lock', 'p35-pipeline.lock'):
            h.require(not (base / '.cache' / name).exists(), 'existing device owner')
    out = h.fresh(AREA / 'qualify-01')
    with h.device_owner(out):
        native = Commander(plan, out)
        try:
            cpuid = native.read(0xE000ED00)[0]
            dhcsr = native.read(0xE000EDF0)[0]
            h.require(cpuid == 0x410FC241 and not dhcsr & 0x20000, 'wrong/halted core')
            result = dict(outcome='INTERACTIVE_READ_ROUTE_QUALIFIED', cpuid=cpuid, dhcsr=dhcsr,
                          resetCommands=0, haltCommands=0, flashCommands=0, keyCalls=0)
            h.save(out / 'result.json', result)
            print(json.dumps(result), flush=True)
        finally:
            native.close()


if __name__ == '__main__':
    h.require(sys.argv[1:] == ['--qualify'], 'only the bounded read qualification is exposed')
    qualify()
