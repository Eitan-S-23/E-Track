"""Two fixed-APK FULL cells; source-bound configuration, original readback/analysis."""
import argparse
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_ui_trial as ui
import p34_probe_profile as profile
import p34_probe_install_resume as install
import p34_scoped_dns as dns

cli, batch = ui.cli, ui.batch
AREA = profile.assets_api.AREA
TRIALS = AREA / 'trials'
ORDER = ('control', 'reuse')
TEST = ROOT / 'tests/ota/test_p34_probe_trial.py'
HOST = AREA / 'trial-tests-002'
batch.radio.backend.verify_experiment = profile.verify


def predecessor(s, arm, group):
    old = SimpleNamespace(TRIAL=profile.assets_api.PRIOR, parent=batch.radio.old.parent)
    return batch.clone(batch.radio.confirmed_predecessor, ORDER=ORDER, TRIALS=TRIALS, old=old)(s, arm, group)


class Probe(ui.Ui):
    def __init__(self, s, arm, preinstall=False):
        self.probe_arm, self.preinstall = arm, preinstall
        self.ui_arm, self.arm = 'measure', 'batch'
        self.assets = profile.assets(s, arm)
        self.proof = predecessor(s, arm, self.assets)
        self.report = install.inputs(s)[0] if preinstall else install.apk(s)
        path = Path(self.proof['plan']['profile']['path'])
        batch.radio.backend.Backend.__init__(self, s, path, s.read(path), cli.RECONNECT_GROUP)
        spec = self.assets['specification']
        self.receiver_version, self.target_version = spec['receiver'], spec['target_version']
        self.served_name = spec['served_name']

    def context(self, out):
        c = super().context(out)
        c.n04_prior_assets.append(ui.assets(self.store, 'measure'))
        if self.probe_arm == 'reuse':
            c.n04_prior_assets.append(profile.assets(self.store, 'control'))
        c.previous_assets = c.n04_prior_assets[-1]
        old = c.sources
        paths = [Path(__file__), TEST, Path(profile.__file__), Path(install.__file__), Path(dns.__file__),
                 Path(install.previous.__file__), install.previous.OUT / 'result.json',
                 install.previous.OUT / 'usb/commands.jsonl',
                 AREA / 'assets/result.json', AREA / 'apk-g1/apk.json', AREA / 'profile-tests-001/result.json',
                 ROOT / 'Tools/ota/p34_probe_artifacts.py']
        if not self.preinstall:
            paths += [install.OUT / 'result.json', AREA / ('archive-' + self.probe_arm) / 'result.json']
        records = [cli.record(p) for p in paths]
        c.sources = lambda: sorted({x['path']: x for x in [*old(), *records]}.values(), key=lambda x: x['path'])
        return c

    def phone(self, c, name, *, producer=False):
        phone = super().phone(c, name, producer=producer)
        old = phone.config
        def config(*args):
            value = dict(old(*args), schema=6,
                         reuseRebootInfoLink=self.assets['specification']['reuseRebootInfoLink'])
            profile.validate_config(value, self.assets)
            return value
        phone.config = config
        return phone

    def verify_served(self, c, origin, *, proxy=False):
        return dns.verify(self, c, origin)


def tests(s):
    value = s.read(HOST / 'result.json')
    cli.require(value['result'] == 'PASS' and value['source'] == cli.record(__file__) and
                value['test'] == cli.record(TEST) and value['profile'] == cli.record(profile.__file__), 'trial tests stale')
    return cli.record(HOST / 'result.json')


def archive(s, owner, arm, worker):
    current = profile.assets_api.PRIOR if arm == 'control' else TRIALS / 'control'
    previous = ui.TRIALS / 'bootstrap' if arm == 'control' else profile.assets_api.PRIOR
    ui.archival.proof(s, current)
    ui.archival.proof(s, previous)
    out = s.checked(AREA / ('archive-' + arm))
    if worker:
        radio = SimpleNamespace(ORDER=(current.name,), TRIALS=current.parent,
            old=SimpleNamespace(TRIAL=previous), APK=AREA / 'apk-g1/apk.json', backend=batch.radio.backend)
        batch.clone(ui.archival.worker, radio=radio)(s, current.name, out)
    else:
        install.apk(s)
        tests(s)
        cli.require(not out.exists(), 'preserve archive attempt')
        for name in ('intent.json', 'result.json', 'capture', 'host', 'usb', 'stop-intent.json', 'mkdir-intent.json', 'move-intent.json'):
            s.checked(out / name)
        s.write(out / 'intent.json', dict(source=cli.record(__file__), implementation=cli.record(ui.archival.__file__),
            protected=str(current), selected=str(previous), no_delete=True, no_ota=True))
        print(owner.owned.launch(s.checked(AREA / 'runtime' / ('archive-' + arm)), Path(__file__),
                                 ['archive-worker', '--arm', arm], 600))


def archive_ready(s, arm):
    value = s.read(AREA / ('archive-' + arm) / 'result.json')
    cli.require(value['result'] == 'INACTIVE_CAPTURE_ARCHIVED_VERIFIED' and value['usb_closed'] and
                value['protected_snapshot_unchanged'] and value['configuration_unchanged'] and
                value['app_stopped'] and len(value['remaining']) == 7, 'archive unresolved')
    receipt = s.read(AREA / 'runtime' / ('archive-' + arm) / 'closed.json')
    cli.require(receipt['worker_exit'] == 0 and not receipt['forced_termination'], 'archive owner unresolved')


if __name__ == '__main__':
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=('check', 'archive', 'archive-worker', 'launch', 'coordinator', 'network', 'cell'))
    p.add_argument('--arm', choices=ORDER, required=True)
    a = p.parse_args()
    s, out = cli.Store(ROOT), TRIALS / a.arm
    owner = cli.load_module('probe_trial_owner', ROOT / '.cache/p3-4-screening-20260922/supervisor.py')
    if a.mode not in ('check', 'archive', 'launch'):
        cli.require(owner.owned.in_job(), 'finite owner required')
    if a.mode.startswith('archive'):
        archive(s, owner, a.arm, a.mode == 'archive-worker')
    else:
        if a.mode == 'launch':
            cli.require(not out.exists(), 'preserve trial attempt')
            tests(s)
            archive_ready(s, a.arm)
        api = Probe(s, a.arm, preinstall=a.mode == 'check')
        c = api.context(out)
        api.preflight(c, out)
        if a.mode == 'check':
            value = api.phone(c, 'probe_offline').config(c, 's04', 921600, 28, 'https://offline.trycloudflare.com')
            profile.validate_config(value, api.assets)
            cli.require(api.installed_context(out).receiver_image_sha == api.assets['target']['sha256'], 'wrong target binding')
            print('PROBE_OFFLINE_VERIFIED_NOT_INSTALLATION', a.arm, len(c.sources()))
        elif a.mode == 'launch':
            s.write(out / 'intent.json', dict(time=cli.now(), sources=c.sources(), tests=tests(s), arm=a.arm,
                scope='one legal FULL cell; same APK and receiver code, no replay/reset/Boot replacement', independent_acceptance=False))
            print(owner.owned.launch(s.checked(out / 'runtime/coordinator'), Path(__file__), ['coordinator', '--arm', a.arm], 6000))
        else:
            cli.require(c.sources() == s.read(out / 'intent.json')['sources'], 'running inputs changed')
            os.environ.update(c.environment())
            if a.mode == 'coordinator':
                batch.clone(ui.coordinate, __file__=__file__, tests=tests)(s, api, c, owner, out, a.arm)
            else:
                api.validate(c, out)
                code = api.network_worker(c, out) if a.mode == 'network' else api.cell_worker(c, out, 's04')
                cli.require(code == 0, 'trial failed; reconcile original evidence')
