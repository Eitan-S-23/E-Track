"""Pin decoded physical NOR geometry/timing to versioned reference bytes and tests."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
import p34_install_cost as host
from recovery_entry.nor_profile import pinned


def main():
    cli = host.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    store = cli.Store(ROOT); out = store.checked(ROOT/'.cache/p34-nor-profile1')
    cli.require(not out.exists(), 'preserve profile evidence')
    names = ('Tools/ota/recovery_entry/nor_profile.py', 'Tools/ota/recovery_entry/probe.py',
             'Tools/ota/p34_nor_profile.py', 'Tools/ota/p34_install_cost.py', 'Tools/ota/p34_session.py',
             '.agents/skills/e-track-flutter-debug/scripts/host_io.py', 'tests/boot/test_p34_nor_profile.py',
             '.cache/p34-host-nor-read1/sfdp.bin', '.cache/p34-host-nor-read1/worker.json',
             '.cache/p34-nor-profile-reference1/result.json', '.cache/p34-nor-profile-reference1/linux-sfdp.h',
             '.cache/p34-nor-profile-reference1/linux-sfdp.c', '.cache/p34-nor-profile-reference1/zephyr-jesd216.c')
    for name in ('result.json', 'tests.log', 'tests.json'): store.checked(out/name)
    for n in names: store.checked(out/'source'/n)
    inputs = [cli.record(ROOT/n) for n in names]
    profile = pinned((ROOT/'.cache/p34-host-nor-read1/sfdp.bin').read_bytes())
    env = host.environment(store, out)
    for n in names: store.raw(out/'source'/n, (ROOT/n).read_bytes())
    log = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
                       ROOT/'tests/boot/test_p34_nor_profile.py', '-v'], env, 30)
    match = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', log)
    cli.require(match and inputs == [cli.record(ROOT/n) for n in names], 'profile source/test drift')
    store.write(out/'result.json', dict(result='NOR_COMMON_PROFILE_HOST_PASS', profile=profile,
                inputs=inputs, tests=int(match[1]), hardware=False))
    print('NOR_COMMON_PROFILE_HOST_PASS', int(match[1]))


if __name__ == '__main__': main()
