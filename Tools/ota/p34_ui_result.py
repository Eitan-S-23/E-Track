"""Reconcile completed UI-cadence cells offline, without repeating device work."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_ui_trial as trial
import p34_batch_review as review

cli=trial.cli


def closed(s,out):
    for name in ('coordinator','network','s04'):
        receipt=s.read(out/'runtime'/name/'closed.json')
        cli.require(receipt['worker_exit']==0 and not receipt['forced_termination'],
                    'original worker is not normally closed: '+name)


def trial_root(route):
    cli.require(route in ('main','dns'),'unlisted result route')
    return trial.TRIALS if route=='main' else trial.AREA/'trials-dns'


def worker(s,arm,route='main'):
    out=trial_root(route)/arm
    closed(s,out)
    # The cell already runs the strict analysis after native/USB closure.
    # Reuse its original report rather than rebuilding that context again.
    pointer,verified=review.load_report(s,out)
    cli.require(verified['summary']['input']['targetVersionCode']==(30253 if arm=='bootstrap' else 30254),
                'report belongs to a different UI cell')
    metrics=verified['full_metrics']
    value=dict(result='UI_CELL_RECONCILED',arm=arm,route=route,report=pointer,
        target=verified['summary']['input']['targetVersionCode'],metrics=metrics,
        throughput_kb_s=metrics['throughput_kib_s']*1.024,
        no_device_operations=True,no_upgrade_replayed=True,
        cadence_effect_measured=arm=='measure',
        scope='bootstrap installs the new receiver; only header-only successor measures its cadence')
    if arm=='measure':
        prior,baseline=review.load_report(s,trial.previous.OUT)
        old=baseline['full_metrics']
        value.update(baseline=prior,
            transfer_speed_change_percent=(metrics['throughput_kib_s']/old['throughput_kib_s']-1)*100,
            transfer_seconds_saved=old['transfer_seconds']-metrics['transfer_seconds'],
            reconnect_seconds_saved=old['installation_reconnect_seconds']-metrics['installation_reconnect_seconds'],
            targets_met=metrics['throughput_kib_s']*1.024>=50 and metrics['installation_reconnect_seconds']<=20,
            strict_identical_package_ab=False)
    suffix='' if route=='main' else '-'+route
    s.write(trial.AREA/('review-'+arm+suffix)/'result.json',value)
    print(json.dumps(value),flush=True)


if __name__=='__main__':
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'explicit root and isolated Python required')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('launch','worker'))
    p.add_argument('--arm',choices=('bootstrap','measure'),required=True)
    p.add_argument('--route',choices=('main','dns'),default='main')
    args=p.parse_args();s=cli.Store(ROOT)
    owner=cli.load_module('ui_result_owner',ROOT/'.cache/p3-4-screening-20260922/supervisor.py')
    if args.mode=='launch':
        closed(s,trial_root(args.route)/args.arm)
        suffix='' if args.route=='main' else '-'+args.route
        s.checked(trial.AREA/('review-'+args.arm+suffix)/'result.json')
        print(owner.owned.launch(s.checked(trial.AREA/'runtime'/('analyze-'+args.arm+suffix+'-001')),
                                 Path(__file__),['worker','--arm',args.arm,'--route',args.route],900))
    else:
        cli.require(owner.owned.in_job(),'finite analysis worker required')
        worker(s,args.arm,args.route)
