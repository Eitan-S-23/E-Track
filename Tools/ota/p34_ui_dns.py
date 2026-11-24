"""Resume the unstarted measurement using scoped DNS, never system DNS edits."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_ui_trial as original
import p34_scoped_dns as dns

cli=original.cli
TRIALS=original.AREA/'trials-dns'
HOST=original.AREA/'dns-tests-002'
TEST=ROOT/'tests/ota/test_p34_ui_dns.py'
FAILED=original.TRIALS/'measure'


def reconciled(s):
    cli.require(not(FAILED/'cells').exists() and not(FAILED/'runtime/s04').exists(),
                'failed network may have started a cell')
    records=[]
    for name in ('network','coordinator'):
        path=FAILED/'runtime'/name/'closed.json';v=s.read(path)
        cli.require(v['worker_exit']==1 and not v['forced_termination'],'failed owner not reconciled')
        records.append(cli.record(path))
    path=FAILED/'network-result.json';v=s.read(path)
    cli.require(v['device_operations']==0 and v['result']=='NETWORK_INCOMPLETE' and
                v['detail']=='fresh service DNS window exhausted; preserve this origin and stop',
                'different service failure')
    records.append(cli.record(path))
    path=FAILED/'network-owner/network/closed.json';v=s.read(path)
    cli.require(v['listener_closed'] and v['worker_stopped'],'old service still owns resources')
    records.append(cli.record(path))
    return records


class Scoped(original.Ui):
    def __init__(self,s,arm):
        cli.require(arm=='measure','only unstarted measurement recovery')
        reconciled(s)
        super().__init__(s,arm)

    def context(self,out):
        c=super().context(out)
        old=c.sources
        records=[cli.record(p) for p in (Path(__file__),Path(dns.__file__),TEST,HOST/'result.json')]
        records+=reconciled(self.store)
        c.sources=lambda:sorted({x['path']:x for x in [*old(),*records]}.values(),key=lambda x:x['path'])
        return c

    def verify_served(self,c,origin,*,proxy=False):
        # Same origin, certificate hostname and exact asset checks remain mandatory.
        return dns.verify(self,c,origin)


def tests(s):
    value=s.read(HOST/'result.json')
    cli.require(value['passed'] and value['sources']==sources(),'current DNS route tests required')
    original.tests(s)
    return cli.record(HOST/'result.json')


def sources():
    return [cli.record(p) for p in (Path(__file__),TEST,Path(dns.__file__),ROOT/'tests/ota/test_p34_scoped_dns.py')]


if __name__=='__main__':
    cli.require(sys.argv[1:] and sys.argv[1] in ('launch','coordinator','network','cell','check') and
                sys.argv[2:]==['--arm','measure'],'exact measurement recovery invocation required')
    coordinate=original.batch.clone(original.coordinate,__file__=__file__,tests=tests)
    original.batch.clone(original.main,__file__=__file__,TRIALS=TRIALS,Ui=Scoped,
                         coordinate=coordinate,tests=tests)()
