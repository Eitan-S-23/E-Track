"""Archive inactive30249 while retaining the confirmed30250 original capture."""
from pathlib import Path
import sys
import types

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_radio_archive as archive
import p34_batch_trial as batch
import p34_crc_build as build

cli=archive.cli
OUT=build.AREA/'archive-bootstrap'


if __name__=='__main__':
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'explicit root and isolated Python required')
    s=cli.Store(ROOT)
    batch.apk(s)
    tests=s.read(archive.AREA/'archive-tests/result.json')
    cli.require(tests['result']=='PASS' and tests['source']==cli.record(archive.__file__) and
                tests['test']==cli.record(archive.TEST),'archive tests changed')
    archive.proof(s,batch.TRIALS/'batch')
    archive.proof(s,batch.install.prior.PRIOR)
    owner=cli.load_module('crc_archive_owner',ROOT/'.cache/p3-4-screening-20260922/supervisor.py')
    if sys.argv[1:]==['launch']:
        cli.require(not OUT.exists(),'preserve archive attempt')
        for name in ('intent.json','result.json','stop-intent.json','mkdir-intent.json','move-intent.json','capture','usb','host'):
            s.checked(OUT/name)
        s.write(OUT/'intent.json',dict(source=cli.record(__file__),implementation=cli.record(archive.__file__),
            tests=tests,protected_version=30250,selected_version=30249,no_delete=True,no_ota=True))
        print(owner.owned.launch(build.AREA/'runtime/archive-bootstrap',Path(__file__),['worker'],600))
    else:
        cli.require(sys.argv[1:]==['worker'] and owner.owned.in_job(),'finite archive owner required')
        radio=types.SimpleNamespace(ORDER=('batch',),TRIALS=batch.TRIALS,
            old=types.SimpleNamespace(TRIAL=batch.install.prior.PRIOR),APK=batch.AREA/'apk-g1/apk.json',
            backend=archive.radio.backend)
        batch.clone(archive.worker,radio=radio)(s,'batch',OUT)
