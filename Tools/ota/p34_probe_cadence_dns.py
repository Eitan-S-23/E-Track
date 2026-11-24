"""Resume an unstarted cadence cell after strict DNS failure; no OTA replay."""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_probe_cadence as old
import p34_dns_readiness as dns

cli, AREA = old.cli, old.AREA
OUT = AREA / 'trial-dns'
TEST = ROOT / 'tests/ota/test_p34_dns_readiness.py'
HOST = AREA / 'dns-tests-002'


def reconciled(s):
    cli.require(not (old.OUT / 'cells').exists() and not (old.OUT / 'runtime/s04').exists(), 'cell may have started')
    records = []
    for name in ('coordinator', 'network'):
        path = old.OUT / 'runtime' / name / 'closed.json'
        value = s.read(path)
        cli.require(value['worker_exit'] == 1 and not value['forced_termination'], 'failed owner unresolved')
        records.append(cli.record(path))
    path = old.OUT / 'network-result.json'
    value = s.read(path)
    cli.require(value['result'] == 'NETWORK_INCOMPLETE' and value['device_operations'] == 0 and
                value['detail'] == 'DNS ID/status/count mismatch', 'different network failure')
    records.append(cli.record(path))
    path = old.OUT / 'network-owner/network/closed.json'
    value = s.read(path)
    cli.require(value['listener_closed'] and value['worker_stopped'], 'failed service resources unresolved')
    return records + [cli.record(path)]


def tests(s):
    old.tests(s)
    value = s.read(HOST / 'result.json')
    cli.require(value['result'] == 'PASS' and value['sources'] == sources(), 'DNS tests stale')
    return cli.record(HOST / 'result.json')


def sources():
    return [cli.record(p) for p in (Path(__file__), Path(dns.__file__), TEST, Path(dns.original.__file__),
                                  ROOT / 'tests/ota/test_p34_scoped_dns.py')]


class Cadence(old.Cadence):
    def __init__(self, s):
        reconciled(s)
        super().__init__(s)

    def context(self, out):
        c = super().context(out)
        before = c.sources
        extra = sources() + reconciled(self.store) + [cli.record(HOST / 'result.json')]
        c.sources = lambda: sorted({x['path']:x for x in [*before(), *extra]}.values(), key=lambda x:x['path'])
        return c

    def verify_served(self, c, origin, *, proxy=False):
        return dns.verify(self, c, origin)


if __name__ == '__main__':
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    cli.require(len(sys.argv) in (2, 4) and sys.argv[1] in ('launch', 'coordinator', 'network', 'cell') and
                (len(sys.argv) == 2 or sys.argv[2:] == ['--arm', 'cadence']), 'exact recovery invocation required')
    mode = sys.argv[1]
    s = cli.Store(ROOT)
    owner = cli.load_module('cadence_dns_owner', ROOT / '.cache/p3-4-screening-20260922/supervisor.py')
    if mode != 'launch': cli.require(owner.owned.in_job(), 'finite owner required')
    tests(s)
    if mode == 'launch': cli.require(not OUT.exists(), 'preserve recovery attempt')
    api = Cadence(s)
    c = api.context(OUT)
    api.preflight(c, OUT)
    if mode == 'launch':
        s.write(OUT / 'intent.json', dict(time=cli.now(), sources=c.sources(), tests=tests(s), arm='cadence',
            scope='resume unstarted100ms cell with bounded strict DNS readiness; same APK/assets/archive', independent_acceptance=False))
        print(owner.owned.launch(s.checked(OUT / 'runtime/coordinator'), Path(__file__), ['coordinator'], 6000))
    else:
        cli.require(c.sources() == s.read(OUT / 'intent.json')['sources'], 'running sources changed')
        os.environ.update(c.environment())
        if mode == 'coordinator':
            old.batch.clone(old.ui.coordinate, __file__=__file__, tests=tests)(s, api, c, owner, OUT, 'cadence')
        else:
            api.validate(c, OUT)
            code = api.network_worker(c, OUT) if mode == 'network' else api.cell_worker(c, OUT, 's04')
            cli.require(code == 0, 'recovery worker failed; reconcile instead of replay')
