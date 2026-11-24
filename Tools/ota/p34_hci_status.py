"""Read Bluetooth HCI logging configuration after confirmed CRC measurement closure."""
import argparse
import json
from pathlib import Path
import runpy
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_batch_review as review
import p34_crc_measure as measure

cli=review.cli
OUT=ROOT/'.cache/p34-hci/status-001'


def inputs(s):
    pointer,report=review.load_report(s,measure.OUT)
    cli.require(report['summary']['input']['targetVersionCode']==30252,'latest firmware differs')
    apk=measure.batch.apk(s)
    return pointer,apk


def worker(s):
    pointer,apk=inputs(s)
    b,d,p,lock=runpy.run_path(str(ROOT/'Tools/ota/p34_signing_migration.py'))['runtime']()
    value=dict(result='HCI_STATUS_INCOMPLETE',phone_read_only=True,no_ota=True,prior=pointer)
    try:
        with lock.device_lock(),d['usb'](b,p,OUT):
            p.phone_identity()
            cli.require(d['installed'](b,p,apk['apk']['sha256']) is not None,'installed APK changed')
            properties={name:p.command(['shell','getprop',name],timeout=30,check=False).strip() for name in (
                'persist.sys.bluetooth.btsnooplogmode','persist.bluetooth.btsnooplogmode',
                'persist.bluetooth.btsnoopenable','ro.build.version.sdk')}
            settings={space+'/'+name:p.command(['shell','settings','get',space,name],timeout=30,check=False).strip()
                for space,name in (('global','bluetooth_btsnoop_log_mode'),('secure','bluetooth_hci_log'))}
            cli.require(all(len(v)<4096 for v in [*properties.values(),*settings.values()]),'unexpected property size')
            access={}
            for path in ('/data/misc/bluetooth/logs','/sdcard/btsnoop_hci.log',
                         '/data/misc/bluetooth/logs/btsnoop_hci.log',
                         '/data/user_de/0/com.android.shell/files/bugreports'):
                p.command(['shell','test','-r',path],timeout=30,check=False)
                receipt=json.loads((p.RUNTIME/'commands.jsonl').read_text().splitlines()[-1])
                access[path]=dict(readable=receipt['exit']==0,exit=receipt['exit'])
            value.update(result='HCI_STATUS_READ',properties=properties,settings=settings,
                path_access=access,
                scope='configuration only; enabled setting is not proof of a readable HCI capture')
            reports='/data/user_de/0/com.android.shell/files/bugreports'
            if OUT.name=='status-003' and access[reports]['readable']:
                listing=p.command(['shell','ls','-lt',reports],timeout=30,check=False)
                cli.require(len(listing.encode())<=65536,'report inventory too large')
                value['existing_reports']=listing
        value['usb_closed']=True
    except Exception as error:
        value.update(error=type(error).__name__,detail=str(error))
    s.write(OUT/'result.json',dict(time=cli.now(),**value))
    print(json.dumps(value),flush=True)
    cli.require('error' not in value,'HCI configuration check incomplete')


if __name__=='__main__':
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'explicit root and isolated Python required')
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('mode',choices=('launch','worker'))
    parser.add_argument('--attempt',choices=('001','002','003'),default='001')
    args=parser.parse_args(); mode=args.mode; s=cli.Store(ROOT)
    OUT=ROOT/('.cache/p34-hci/status-'+args.attempt)
    owner=cli.load_module('hci_status_owner',ROOT/'.cache/p3-4-screening-20260922/supervisor.py')
    if mode=='launch':
        cli.require(not OUT.exists(),'preserve HCI status attempt')
        inputs(s)
        for name in ('intent.json','result.json','host','usb'): s.checked(OUT/name)
        s.write(OUT/'intent.json',dict(source=cli.record(__file__),phone_read_only=True,no_ota=True))
        print(owner.owned.launch(ROOT/('.cache/p34-hci/runtime/status-'+args.attempt),Path(__file__),
            ['worker','--attempt',args.attempt],600))
    else:
        cli.require(owner.owned.in_job(),'finite owned worker required'); worker(s)
