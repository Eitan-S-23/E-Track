"""HOST_ONLY qualification of single-read timing/decoder; physical entry pending."""
import argparse
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_install_cost as host
import p34_recovery_ports

cli=host.cli
SELF=Path(__file__).resolve()
SOURCES=[SELF,ROOT/'Tools/ota/recovery_confirm/gpio_read.py',ROOT/'tests/boot/test_p34_gpio_read_probe.py',
         ROOT/'Tools/ota/p34_recovery_ports.py',ROOT/'.cache/p34-recovery-ports3/result.json']


def sources(store):
    port=store.read(ROOT/'.cache/p34-recovery-ports3/result.json')
    cli.require(port['result']=='RECOVERY_PORTS_HOST_PASS','original port tests missing')
    cli.require(all(cli.record(item['path'])==item for item in port['inputs']),'original port source drift')
    return list(dict.fromkeys(SOURCES+[Path(item['path']) for item in port['inputs']]))


def preflight(store,out,inputs):
    cli.require(not out.exists(),'preserve GPIO host evidence')
    for path in inputs: store.checked(out/'source'/path.relative_to(ROOT))
    for name in ('tests.log','tests.json','result.json'): store.checked(out/name)
    for key in ('HOME','USERPROFILE','APPDATA','LOCALAPPDATA','TEMP','TMP','TMPDIR','XDG_CACHE_HOME',
                'XDG_CONFIG_HOME','XDG_DATA_HOME','PYTHONUSERBASE','PYTHONPYCACHEPREFIX','CCACHE_DIR','SCCACHE_DIR'):
        store.checked(out/'host'/key.lower())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'isolated root required')
    store=cli.Store(ROOT);out=store.checked(args.output_dir);inputs=sources(store)
    preflight(store,out,inputs)
    records=[cli.record(path) for path in inputs]
    env=host.environment(store,out)
    for path in inputs: store.raw(out/'source'/path.relative_to(ROOT),path.read_bytes())
    log=host.command(store,out,'tests',[sys.executable,'-I','-S','-B','-X','utf8',
        ROOT/'tests/boot/test_p34_gpio_read_probe.py','-v'],env,90)
    count=re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b',log)
    cli.require(count and records==[cli.record(path) for path in inputs],'GPIO test/source drift')
    store.write(out/'result.json',dict(result='GPIO_READ_HOST_PASS',tests=int(count[1]),inputs=records,
        hardware=False,physical_entry=False,physical_timing_qualified=False))
    print('GPIO_READ_HOST_PASS tests='+str(int(count[1])))


if __name__=='__main__': main()

