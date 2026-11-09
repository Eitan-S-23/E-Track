"""Prepare V2 automation offline; never start ADB, J-Link, a fixture or an OTA."""
import argparse
import copy
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run
import v2

h, b = run.h, run.benchmark


def assemble(template, receiver, app_build, package_delivery, package_dir, restore_binding, fixture_ready=None):
    plan = copy.deepcopy(template)
    proof = h.read_json(h.pinned(receiver))
    app = h.read_json(h.pinned(app_build))
    restore = h.read_json(h.pinned(restore_binding))
    root = h.checked(package_dir)
    package = h.record(root / 'prepared/patch.etu')
    for name in ('functional_sample', 'cloud', '_long_execution', '_campaign_deadline'):
        plan.pop(name, None)
    plan.update(schema=1, task='P5-1', kind='patch', apk=app['apk'])
    plan['mcu'].update(boot=proof['boot'], package=package, images=dict(
        base=proof['receiver'], target=proof['unpackagedTarget'], restore=restore['restore']))
    firmware = plan['firmware']
    firmware.update(protocol=2, package=package, latest_url=app['latestUrl'])
    for field, role in (('current', 'base'), ('target', 'target')):
        pin = plan['mcu']['images'][role]['image']
        image = h.pinned(pin).read_bytes()
        firmware[field] = dict(version=struct.unpack_from('<I', image, 0x408)[0], sha256=pin['sha256'])
    firmware['release_id'] = 'p51-benchmark-%d-%d' % (firmware['current']['version'], firmware['target']['version'])
    plan['phone']['app'] = app['app']
    plan['phone']['device'].update(expected_version=firmware['current']['version'],
                                   expected_sha256=firmware['current']['sha256'])
    plan['benchmark'] = dict(purpose='fixed-load-benchmark', controls='semantic-v1',
        wire='v2-only', link=dict(v2.PROFILE), budget=dict(b.BUDGET),
        receiver_proof=receiver, restore_binding=restore_binding, app_build=app_build,
        package_delivery=package_delivery, metadata=h.record(root / 'prepared/benchmark-metadata.json'),
        source_proof=h.record(root / 'inputs/benchmark-source.json'),
        verification=h.record(root / 'evidence/benchmark-verification.json'))
    if fixture_ready is not None:
        plan['benchmark']['fixture_ready'] = fixture_ready
    return plan


def verify(plan):
    v2.live_plan(plan)
    run.validate(plan, require_fixture='fixture_ready' in plan['benchmark'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('template', 'receiver', 'apk-build', 'package-delivery', 'package-dir', 'restore-binding', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--fixture-ready', type=Path)
    parser.add_argument('--execution-out', type=Path, required=True)
    args = parser.parse_args()
    h.require(Path.cwd() == h.ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              'explicit worktree and isolated Python required')
    pin = lambda path: h.record(h.checked(path))
    plan = assemble(h.read_json(h.checked(args.template)), pin(args.receiver), pin(args.apk_build),
        pin(args.package_delivery), args.package_dir, pin(args.restore_binding),
        pin(args.fixture_ready) if args.fixture_ready else None)
    verify(plan)
    out, execution = h.checked(args.out), h.checked(args.execution_out)
    h.require(not out.exists() and not execution.exists(), 'preserve prior preparation or campaign')
    for name in ('long.json', 'fixture.json', 'evaluation.json', 'result.json', 'failed.json', 'symbols'):
        h.checked(out / name)
    h.fresh(out)
    try:
        # bind() reads local ELF/map files with binutils; execute() operates hardware.
        mcu = run.m.MCU(plan['mcu'], out / 'symbols')
        bindings = []
        for role in ('base', 'target', 'restore'):
            mcu.bind(role)
            bindings.append(h.record(mcu.out / ('symbols-' + role) / 'result.json'))
        h.save(out / 'long.json', plan)
        h.save(out / 'fixture.json', dict(plan, schema='p51-benchmark-fixture-v1'))
        h.save(out / 'evaluation.json', dict(long_inputs=h.record(out / 'long.json'),
            blocks=[(execution / ('block-%02d' % i)).relative_to(h.ROOT).as_posix()
                    for i in range(1, b.BUDGET['maxRecordings'] + 1)],
            clock=(execution / 'clock').relative_to(h.ROOT).as_posix()))
        h.save(out / 'result.json', dict(outcome='OFFLINE_V2_INPUTS_VERIFIED',
            plan=h.record(out / 'long.json'), evaluation=h.record(out / 'evaluation.json'),
            fixture=h.record(out / 'fixture.json'), elfBindings=bindings,
            fixtureBound=bool(args.fixture_ready), fixtureLivenessChecked=False,
            realDeviceReadiness='NOT_RUN', deviceOperations=0, fourHourTestStarted=False,
            nextStep='Bind a fresh full-lifetime fixture, then check actual installed APK and idle V2 receiver.'))
        print('OFFLINE_V2_INPUTS_VERIFIED; actual fixture/device readiness NOT_RUN', flush=True)
    except BaseException as error:
        h.save(out / 'failed.json', dict(type=type(error).__name__, message=str(error),
            deviceOperations=0, noAutomaticReplay=True))
        raise


if __name__ == '__main__':
    main()
