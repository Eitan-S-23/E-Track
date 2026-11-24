"""Normal R2-A to B phone route; recovery is not relabeled as a historical OTA."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
import p34_sha_trial as prior
import p34_r2_postcheck as post

cli, batch, ui = prior.cli, prior.batch, prior.ui
backend = batch.radio.backend
SELF = Path(__file__).resolve()
TEST = ROOT/'tests/ota/test_p34_r2_trial.py'
AREA = ROOT/'.cache/p34-r2-normal-ota1'
HOST = ROOT/'.cache/p34-r2-trial-tests2'
POST_TESTS = ROOT/'.cache/p34-r2-postcheck-tests3/result.json'
REVIEW = ROOT/'.cache/p34-r2-backup2-independent-review1/result.json'
REVIEW_SHA = '92d2320f5fe409615722907e06a66903b62aa06149da985574e23fef50e0c4cc'


def current(store):
    cli.require(cli.record(REVIEW)['sha256'] == REVIEW_SHA, 'independent closed R2 baseline required')
    value = store.read(REVIEW)
    for item in (*value['source_inputs'], *value['original_inputs'], value['script']):
        cli.require(cli.record(store.checked(item['path'])) == item, 'R2 baseline bytes changed')
    return dict(descriptor=dict(kind='CLOSED_R2A_RECOVERY_AND_READ_ONLY_BASELINE', review=cli.record(REVIEW)),
                historical_ota_predecessor=False)


def historical_phone(store):
    group = store.read(ROOT/'.cache/p34-sha-candidate/assets/result.json')['groups']['measure']
    expected = dict(specification={'receiver': 30275}, receiver=group['target'], receiver_bindings=group['target_bindings'])
    # Used only to recognize/retain the last App capture and configuration.
    # It is explicitly NOT the MCU predecessor for this R2 transition.
    return batch.clone(batch.radio.confirmed_predecessor, ORDER=('measure', 'next'),
        TRIALS=ROOT/'.cache/p34-sha-candidate/trials')(store, 'next', expected)


def sources(store):
    return list(dict.fromkeys([*post.sources(store), SELF, TEST, Path(prior.__file__), REVIEW,
        POST_TESTS, ROOT/'.cache/p34-sha-candidate/assets/result.json',
        ROOT/'.cache/p34-sha-candidate/trials/measure/analysis/latest.json',
        ROOT/'.cache/p3-4-screening-20260922/supervisor.py',
        ROOT/'Tools/ota/p34_capture_capacity.py']))


class Trial(prior.Trial):
    def __init__(self, store):
        self.timed_arm, self.retry_arm = 'measure', 'extended'
        self.probe_arm, self.ui_arm, self.arm = 'reuse', 'measure', 'batch'
        self.preinstall = self.new_preinstall = True
        self.new_arm = self.half_arm = 'measure'
        self.phy_arm, self.phy_checking = 'prefer2m', True
        self.assets = store.read(post.ASSET_RECEIPT)['groups']['transition']
        self.report = post.asset_api.policy.installed(store)
        self.proof, self.historical_capture = current(store), historical_phone(store)
        path = Path(self.historical_capture['plan']['profile']['path'])
        backend.Backend.__init__(self, store, path, store.read(path), cli.RECONNECT_GROUP)
        self.receiver_version, self.target_version = 30276, 30277
        self.served_name = self.assets['specification']['served_name']

    def context(self, out):
        # R2 has its own closed baseline; do not replay historical asset loaders.
        view = SimpleNamespace(**dict(vars(cli), MEASURED_FULL_GROUPS=(), NEW_BOOT_GROUPS=(),
            ALL_PATCH_GROUPS={}, RECONNECT_GROUP=object()))
        c = batch.clone(backend.Backend.context, cli=view)(self, out)
        c.group, c.package_kind = self.group, 'full'
        c.full_assets, c.bindings = self.assets, self.assets['receiver_bindings']
        spec = self.assets['specification']
        c.spec = dict(c.spec, **spec)
        c.receiver_version, c.target_version = self.receiver_version, self.target_version
        c.served_name, c.release_key = spec['served_name'], spec['release_key']
        c.served = c.screen = self.assets['package']
        c.screen_bytes = Path(c.screen['path']).read_bytes()
        c.target, c.target_identity = self.assets['target'], self.assets['target_identity']
        c.apk, c.APK_SHA = self.report, self.report['apk']['sha256']
        c.BOOT_SHA = self.assets['receiver_bindings']['whole_boot']['sha256']
        c.envelope = post.observation_reader(self.store)
        c.p.query.m = c.envelope
        cli.require(Path(c.p.query.__file__) == post.QUERY, 'unexpected original query reader')
        c.flash_addresses = backend.bind_flash_gate(c.bindings['profile'], self.legacy['named']['restored']['clock']['gate']['symbol'])
        c.native_authority = lambda: dict(mode='NO_NATIVE_IN_PHONE_CELL', postcheck=cli.record(post.SELF))
        before = c.sources
        extra = [cli.record(p) for p in sources(self.store)] + self.historical_capture['inputs']
        c.sources = lambda: sorted({r['path']: r for r in [*before(), *extra, self.report['apk'],
                                   *self.report['host_reports']]}.values(), key=lambda r: r['path'])
        return c

    def predecessor(self, c):
        cli.require(c.bindings == self.assets['receiver_bindings'], 'wrong current R2 receiver')
        return self.proof

    def known_configs(self, c):
        return {self.historical_capture['report']['inputs']['config']['sha256']}

    def completed_capture(self, c, observed, previous=None):
        return backend.Backend.completed_capture(self, c, observed, previous=self.historical_capture)

    def install_checkpoint(self, *args, **kwargs):
        raise RuntimeError('old native checkpoint is prohibited in the R2 phone cell')

    def install_worker(self, c, out, cell):
        cli.require(cell == 's04', 'one normal R2 cell required')
        cell_out = out/'cells'/cell
        phone = self.phone(c, 'p34_r2_normal_ota')
        lock = c.load('p34_r2_phone_lock', ROOT/'Tools/ota/repeat_cycle.py')
        result = dict(result='R2_OTA_INCOMPLETE', final_device_verified=False,
                      native_trace_used=False, receiver_predecessor=self.proof['descriptor'])
        try:
            with lock.device_lock(), phone.usb(c, cell_out) as p, phone.network(c, cell_out) as origin:
                phone.release_old(c, p, cell_out)
                expected = phone.config(c, cell, 921600, 28, origin)
                pid = phone.provision(c, p, cell_out, expected)
                result['summary'] = self.observe_install(c, p, phone, cell_out, pid, expected)
                result['postcheck_trigger'] = post.verify_trigger(self.store, cell_out/'finished/snapshot.jsonl')
            result.update(result='R2_OTA_SNAPSHOT_CAPTURED', usb_closed=True)
        except Exception as error:
            result['error'] = type(error).__name__+': '+str(error)
        c.save(cell_out/'result.json', dict(time=c.now(), **result))
        c.save(cell_out/'status.json', dict(time=c.now(), result=result['result'], error=result.get('error'), closed=True), replace=True)
        print(result, flush=True)
        return 0 if result['result'] == 'R2_OTA_SNAPSHOT_CAPTURED' else 1


def tests(store):
    value = store.read(HOST/'result.json')
    cli.require(value['result'] == 'R2_TRIAL_HOST_PASS' and value['inputs'] == [cli.record(p) for p in sources(store)],
                'current R2 trial tests required')
    return cli.record(HOST/'result.json')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=('selftest', 'check', 'launch', 'coordinator', 'network', 'cell'))
    p.add_argument('--arm', choices=('transition',), default='transition')
    a = p.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    s = cli.Store(ROOT)
    if a.mode == 'selftest':
        paths = sources(s)
        post.checkpoint.owner.preflight(s, HOST, paths)
        records = [cli.record(p) for p in paths]
        env = post.host.environment(s, HOST)
        for path in paths: s.raw(HOST/'source'/path.relative_to(ROOT), path.read_bytes())
        log = post.host.command(s, HOST, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8', TEST, '-v'], env, 180)
        count = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', log)
        cli.require(count and records == [cli.record(p) for p in paths], 'R2 trial tests/source drift')
        s.write(HOST/'result.json', dict(result='R2_TRIAL_HOST_PASS', tests=int(count[1]), inputs=records, hardware=False))
        print('R2_TRIAL_HOST_PASS', int(count[1])); return
    tests(s)
    owned = cli.load_module('r2_trial_owner', ROOT/'.cache/p3-4-screening-20260922/supervisor.py')
    if a.mode not in ('check', 'launch'): cli.require(owned.owned.in_job(), 'finite R2 worker required')
    api = Trial(s)
    c = api.context(AREA)
    api.preflight(c, AREA)
    if a.mode == 'check':
        config = api.phone(c, 'r2_offline').config(c, 's04', 921600, 28, 'https://offline.trycloudflare.com')
        post.asset_api.policy.validate(config, api.assets)
        cli.require(api.installed_context(AREA).receiver_image_sha == api.assets['target']['sha256'], 'post target differs')
        print('R2_TRIAL_OFFLINE_VERIFIED', len(c.sources())); return
    if a.mode == 'launch':
        cli.require(not AREA.exists(), 'preserve R2 cell; never replay')
        s.write(AREA/'intent.json', dict(time=cli.now(), sources=c.sources(), tests=tests(s),
            predecessor=api.proof, scope='Normal R2A-toB OTA; user Start after byte admission; no old native trace/reset/replay',
            postcheck_entry=cli.record(post.SELF), postcheck_tests=cli.record(POST_TESTS), independent_acceptance=False))
        print(owned.owned.launch(AREA/'runtime/coordinator', SELF, ['coordinator'], 6000)); return
    cli.require(c.sources() == s.read(AREA/'intent.json')['sources'], 'running R2 sources changed')
    os.environ.update(c.environment())
    if a.mode == 'coordinator':
        batch.clone(ui.coordinate, __file__=str(SELF), tests=tests)(s, api, c, owned, AREA, 'transition')
    else:
        api.validate(c, AREA)
        code = api.network_worker(c, AREA) if a.mode == 'network' else api.cell_worker(c, AREA, 's04')
        cli.require(code == 0, 'R2 cell incomplete; retrieve original outcome, never replay')


if __name__ == '__main__': main()
