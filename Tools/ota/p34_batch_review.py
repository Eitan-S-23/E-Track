"""Compare completed batch screening evidence without device access or replay."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_batch_trial as trial

cli = trial.cli
OUT = trial.AREA / 'review-001'


def probes(messages):
    rows = [json.loads(x[len('OTA_LINK_STATS '):]) for x in messages.splitlines()
            if x.startswith('OTA_LINK_STATS ')]
    rows = [x for x in rows if x['label'] == 'probe']
    rounds = [x for x in rows if x['attempt'] is None]
    attempts = [x for x in rows if x['attempt'] is not None]
    cli.require(len(rounds) == 1 and attempts, 'one reconnect round required')
    total = rounds[0]['phases']['reconnect']
    cli.require(len(total) == 2 and all(type(x) is int for x in total) and total[1] > total[0],
                'invalid reconnect clock')
    cli.require([x['attempt'] for x in attempts] == list(range(1, len(attempts)+1)),
                'missing or duplicate probe attempts')
    cli.require(rounds[0]['attempts'] == [x['attempts'][0] for x in attempts] and
                attempts[-1]['attempts'][0]['outcome'] == 'completed', 'probe outcomes do not close')
    result = []
    for value in attempts:
        pair = value['phases']['probe_attempt']
        cli.require(len(pair) == 2 and all(type(x) is int for x in pair) and pair[1] >= pair[0],
                    'invalid attempt clock')
        result.append(dict(attempt=value['attempt'], seconds=(pair[1]-pair[0])/1e6,
            outcome=value['attempts'][0]['outcome'], binding=value['bind'], info=value['getInfo']))
    elapsed = (total[1]-total[0])/1e6
    residual = elapsed-sum(x['seconds'] for x in result)
    cli.require(residual >= 0, 'attempt durations exceed reconnect round')
    return dict(seconds=elapsed, attempts=result, outside_attempts_seconds=residual,
        scope='duration sums only; separate stopwatch origins never subtracted; binding/INFO nested in attempts')


def load_report(s, root):
    pointer = s.read(root / 'analysis/latest.json')['report']
    cli.require(cli.record(s.checked(pointer['path'])) == pointer, 'report bytes changed')
    report = s.read(pointer['path'])
    cli.require(report['result'] == 'FULL_INSTALL_VERIFIED', 'complete install required')
    for item in [*report['inputs'].values(), report['after']]:
        cli.require(cli.record(s.checked(item['path'])) == item, 'original input changed')
    closure = s.read(report['after']['path'])
    cli.require(closure['retained_verified'] and closure['reader_closed'] and
                closure['final_state']['bcb_state'] == 4 and
                all(closure['final_state'][k] == 1 for k in ('confirm_done','state_snapped','sd_ready')),
                'ordinary confirmation required')
    for item in closure['final_identity'].values():
        cli.require(cli.record(s.checked(item['path'])) == item, 'raw readback changed')
    for name in ('coordinator','network','s04'):
        value = s.read(root / 'runtime' / name / 'closed.json')
        cli.require(value['worker_exit'] == 0 and not value['forced_termination'], 'owner unresolved')
    return pointer, report


def review(s):
    cli.require(not OUT.exists(), 'preserve prior review')
    old_pointer, old = load_report(s, trial.install.prior.PRIOR)
    pointer, current = load_report(s, trial.TRIALS / 'batch')
    apk = trial.apk(s)
    _, messages = trial.followup.fixed_envelope().verify(
        Path(current['inputs']['snapshot']['path']).read_bytes(),
        sentinel=apk['metadata']['device_observation']['sentinel'], target='02:00:00:00:00:01')
    stats = trial.full_metrics(messages, current['summary']['input']['packageBytes'], '02:00:00:00:00:01')
    before = old['full_metrics']
    value = dict(result='BATCH_SCREEN_REVIEWED', predecessor=old_pointer, current=pointer,
        source=cli.record(__file__), metrics=stats, reconnect=probes(messages),
        speed_gain_percent=(stats['throughput_kib_s']/before['throughput_kib_s']-1)*100,
        transfer_seconds_saved=before['transfer_seconds']-stats['transfer_seconds'],
        installation_reconnect_seconds_added=stats['installation_reconnect_seconds']-before['installation_reconnect_seconds'],
        throughput_kb_s=stats['throughput_kib_s']*1.024,
        targets_met=stats['throughput_kib_s']*1.024 >= 50 and stats['installation_reconnect_seconds'] <= 20,
        strict_same_package_ab=False, device_operations=0,
        next='retain batch3; inspect failed discovery/INFO attempts and firmware apply/backup separately; do not sum MCU and App clocks')
    s.write(OUT / 'result.json', value)
    print(json.dumps(value))


if __name__ == '__main__':
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'explicit root and isolated Python required')
    review(cli.Store(ROOT))
