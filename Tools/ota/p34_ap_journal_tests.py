"""Contained HOST_ONLY tests for whole-session AP journal/audit primitives."""
import argparse
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_install_cost as host

SOURCES=[Path(__file__),*(ROOT/name for name in ('Tools/ota/recovery_confirm/ap_journal.py',
    'tests/boot/test_p34_ap_journal.py','Tools/ota/p34_nor_audit.py','Tools/ota/p34_session.py',
    'Tools/ota/p34_install_cost.py','.agents/skills/e-track-flutter-debug/scripts/host_io.py'))]


def preflight(store,out):
    host.cli.require(not out.exists(),'preserve AP journal test evidence')
    for path in SOURCES: store.checked(out/'source'/path.relative_to(ROOT))
    for name in ('tests.json','tests.log','result.json'): store.checked(out/name)
    for key in ('HOME','USERPROFILE','APPDATA','LOCALAPPDATA','TEMP','TMP','TMPDIR','XDG_CACHE_HOME',
                'XDG_CONFIG_HOME','XDG_DATA_HOME','PYTHONUSERBASE','PYTHONPYCACHEPREFIX','CCACHE_DIR','SCCACHE_DIR'):
        store.checked(out/'host'/key.lower())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    cli=host.cli
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'isolated root required')
    store=cli.Store(ROOT);out=store.checked(args.output_dir)
    preflight(store,out)
    inputs=[cli.record(p) for p in SOURCES]
    env=host.environment(store,out)
    for path in SOURCES: store.raw(out/'source'/path.relative_to(ROOT),path.read_bytes())
    log=host.command(store,out,'tests',[sys.executable,'-I','-S','-B','-X','utf8',ROOT/'tests/boot/test_p34_ap_journal.py','-v'],env,60)
    match=re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b',log)
    cli.require(match and inputs==[cli.record(p) for p in SOURCES],'AP test/source drift')
    store.write(out/'result.json',dict(result='AP_JOURNAL_HOST_PASS',tests=int(match[1]),inputs=inputs,hardware=False))
    print('AP_JOURNAL_HOST_PASS tests='+str(int(match[1])))


if __name__=='__main__': main()

