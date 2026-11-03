"""Run the prepared GDB batch and send stage-bound physical-action reminders."""
import csv
import io
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
AREA = Path(__file__).resolve().parent
assert Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
sys.path.insert(0, str(ROOT / 'Tools/ota/p34-acceptance'))
import live_host as h

CLI = Path('D:/github/my/cc-connect-thread-guard/build/cc-connect.exe')
MESSAGES = {
    'hold': '\u7a0b\u5e8f\u5df2\u505c\u5728\u5b89\u5168\u4f4d\u7f6e\u3002\u8bf7\u73b0\u5728\u6309\u4f4f\u7535\u6e90\u952e\u4e0d\u653e\uff0c\u7b49\u6211\u63d0\u793a\u677e\u624b\u3002\u65e0\u9700\u56de\u590d\u6d88\u606f\u3002',
    'release': '\u957f\u6309\u91c7\u96c6\u5df2\u5b8c\u6210\u3002\u8bf7\u73b0\u5728\u677e\u5f00\u7535\u6e90\u952e\uff0c\u7b49\u4e0b\u4e00\u6761\u63d0\u793a\u3002\u65e0\u9700\u56de\u590d\u3002',
    'short': '\u8bf7\u73b0\u5728\u6309\u4e00\u4e0b\u7535\u6e90\u952e\uff1a\u6309\u4f4f\u7ea6\u4e00\u79d2\u540e\u677e\u5f00\uff0c\u4e0d\u8981\u8d85\u8fc7\u4e09\u79d2\u3002\u65e0\u9700\u56de\u590d\u3002',
    'abort': '\u91c7\u96c6\u5df2\u505c\u6b62\u3002\u5982\u679c\u8fd8\u6309\u7740\u7535\u6e90\u952e\uff0c\u8bf7\u73b0\u5728\u677e\u5f00\uff0c\u6682\u65f6\u4e0d\u8981\u518d\u6309\u3002\u6211\u6b63\u5728\u6838\u5bf9\u8bbe\u5907\u72b6\u6001\uff0c\u65e0\u9700\u56de\u590d\u3002',
}


def preflight():
    plan = h.read_json(AREA / 'key-plan-02.json')
    for name in ('gdb', 'server', 'definitions', 'entry', 'postRead'):
        h.pinned(plan[name])
    out = h.checked(Path(plan['out']))
    h.require(not out.exists(), 'existing key execution: do not replay')
    h.require(CLI.is_file(), 'notification CLI unavailable')
    key = os.environ.get('CC_SESSION_KEY', '').split(':')
    h.require(len(key) == 3 and key[0] == 'feishu' and re.fullmatch(r'ou_[A-Za-z0-9]+', key[2]),
              'current requester identity unavailable')
    h.require(os.environ.get('CC_PROJECT') and
              (Path(os.environ['CC_DATA_DIR']) / 'run/api.sock').exists(), 'notification route unavailable')
    for root in (ROOT, Path('D:/github/my/E-Track')):
        for name in ('p34-live-device.lock', 'p35-reconcile-device.lock', 'p35-pipeline.lock'):
            h.require(not (root / '.cache' / name).exists(), 'existing device owner')
    h.checked(ROOT / '.cache/p34-live-device.lock')
    paths = ['settings.jlink', 'server.log', 'stack-before.bin', 'stack-after.bin',
             'intent.json', 'result.json', 'failed.json', 'notifications.json']
    paths += ['stage-' + s + '.log' for s in ('hold', 'release', 'short', 'finished')]
    for label in ('server', 'gdb', 'processes', 'notify-hold', 'notify-release', 'notify-short', 'notify-abort'):
        paths += [label + '.' + ext for ext in ('stdout', 'stderr', 'started.json', 'closed.json')]
    paths += ['host/' + n.lower() for n in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'TEMP',
              'TMP', 'TMPDIR', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'PYTHONUSERBASE',
              'CCACHE_DIR', 'SCCACHE_DIR', 'gitconfig', 'android')]
    for path in paths:
        h.checked(out / path)
    h.require(not any(h.listening(p) for p in plan['ports']), 'debugger port occupied')
    return plan, out, key[2]


def main():
    plan, out, requester = preflight()
    if sys.argv[1:] == ['check']:
        print('PREFLIGHT_PASS: fresh contained outputs; pinned inputs; current-session notification identity', flush=True)
        return
    h.require(sys.argv[1:] == ['run'], 'explicit check or run required')
    h.fresh(out)
    env = h.environment(out)
    notices = []

    def notify(stage):
        body = ('<at user_id="' + requester + '">requester</at> ' + MESSAGES[stage]).encode('utf8')
        # Current CC_PROJECT and CC_SESSION_KEY are inherited, never logged in argv.
        raw = h.command(out, 'notify-' + stage, [CLI, 'send', '--stdin'], env, stdin=body, seconds=20)
        h.require(b'Message sent successfully.' in raw, 'notification delivery not confirmed')
        notices.append(dict(stage=stage, monoNs=time.monotonic_ns(), delivered=True))
        print('NOTIFIED ' + stage, flush=True)

    h.save(out / 'intent.json', dict(plan=h.record(AREA / 'key-plan-02.json'),
           entry=h.record(Path(__file__)), operations=plan['operations'], formalAcceptance=False))
    with h.device_owner(out):
        raw = h.command(out, 'processes', ['tasklist', '/FO', 'CSV', '/NH'], env, seconds=15)
        names = {row[0].lower() for row in csv.reader(io.StringIO(raw.decode('utf8', 'replace'))) if row}
        h.require(not names & {'uv4.exe', 'jlink.exe', 'jlinkrttlogger.exe', 'jlinkrttviewer.exe',
                  'jlinkgdbserver.exe', 'jlinkgdbservercl.exe', 'jflash.exe', 'jlinkguiserver.exe',
                  'arm-none-eabi-gdb.exe'}, 'another debugger exists')
        server = gdb = None
        try:
            ports = plan['ports']
            server = h.Process(out, 'server', [h.pinned(plan['server']), '-select',
                'USB=' + str(plan['retained']['probe_serial']), '-device', 'CORTEX-M4', '-if', 'SWD',
                '-speed', '1000', '-port', str(ports[0]), '-swoport', str(ports[1]),
                '-telnetport', str(ports[2]), '-rtttelnetport', str(ports[3]), '-localhostonly',
                '-noir', '-nohalt', '-noreset', '-nogui', '-singlerun',
                '-SettingsFile', out / 'settings.jlink', '-log', out / 'server.log'], env)
            def ready():
                h.require(server.alive(), 'server stopped before readiness')
                return b'Waiting for GDB connection' in (out / 'server.stdout').read_bytes()
            h.wait_for(ready, 15)
            gdb = h.Process(out, 'gdb', [h.pinned(plan['gdb']), '-nx', '-nh', '--batch',
                            '-x', h.pinned(plan['entry'])], env)
            deadline = time.monotonic() + plan['overallSeconds']
            sent = set()
            while gdb.alive():
                h.require(time.monotonic() < deadline, 'key window expired; state reconciliation required')
                for stage in ('hold', 'release', 'short'):
                    if stage not in sent and (out / ('stage-' + stage + '.log')).exists():
                        notify(stage)
                        sent.add(stage)
                time.sleep(.05)
            raw = gdb.wait(5)
            server.wait(10)
            h.require((out / 'stage-finished.log').exists() and b'P17_ERROR' not in raw, 'incomplete key batch')
            long = re.search(rb'P17_RESULT long result=1 ticks=(\d+) gpio=([0-9a-f]+)', raw)
            short = re.search(rb'P17_RESULT short result=0 ticks=(\d+) gpio=([0-9a-f]+)', raw)
            h.require(long and short and int(long[1]) >= 3000 and 0 < int(short[1]) < 3000,
                      'key result/timing missing')
            h.save(out / 'result.json', dict(outcome='KEY_PREDICATES_OBSERVED_POSTCHECK_PENDING',
                longTicks=int(long[1]), shortTicks=int(short[1]), notifications=notices,
                devicePostcheck='NOT_RUN', formalAcceptance=False, resetCommands=1, keyCalls=2,
                flashProgramming=0, portsClosed=not any(h.listening(p) for p in ports)))
            print('KEY_PREDICATES_OBSERVED_POSTCHECK_PENDING', flush=True)
        except BaseException as error:
            for process in (gdb, server):
                if process is not None:
                    process.close('key_batch_stopped')
            if any(n['stage'] == 'hold' for n in notices):
                try:
                    notify('abort')
                except BaseException:
                    print('ABORT_NOTIFICATION_FAILED: release key if held', flush=True)
            h.save(out / 'failed.json', dict(outcome='STOPPED_RECONCILE_DEVICE', error=str(error),
                                           deviceLockRetained=True, notifications=notices))
            raise
        finally:
            for process in (gdb, server):
                if process is not None:
                    process.close()
            h.save(out / 'notifications.json', notices)


if __name__ == '__main__':
    main()
