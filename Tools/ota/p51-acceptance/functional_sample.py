"""Read-only admission of an archived normal preparation, never a packaging route."""
import hashlib
import json
from pathlib import PurePosixPath
import re
import sys
import sysconfig


STEP_ORDER = ('base-verify', 'base-extract', 'finalize', 'finalized-verify', 'full-pack',
              'full-apply', 'full-outer-verify', 'patch-pack', 'patch-apply',
              'patch-outer-verify', 'recovery-create', 'recovery-verify')
BYTE_CHECK = '.github/scripts/firmware-byte-check.py'


def byte_checker(h):
    name = 'p51_firmware_byte_check'
    if name not in sys.modules:
        # The existing parser imports Crypto; do not execute site/.pth startup.
        for folder in (sysconfig.get_path('platlib'), sysconfig.get_path('purelib')):
            if folder not in sys.path:
                sys.path.append(folder)
        h.host.load(name, h.ROOT / BYTE_CHECK)
    return sys.modules[name]


def validate(plan, h):
    if plan['kind'] != 'patch':
        return
    try:
        _validate(plan, h)
    except (KeyError, IndexError, TypeError, ValueError, OSError) as error:
        raise RuntimeError('invalid functional preparation: ' + str(error)) from error


def _validate(plan, h):
    sample = plan.get('functional_sample')
    h.require(isinstance(sample, dict) and sample.get('purpose') == 'normal-upgrade',
              'functional PATCH requires a normal-upgrade sample, not a reference benchmark')
    preparation = h.pinned(sample['preparation'])
    proof = h.read_json(preparation)
    h.require(isinstance(proof, dict) and proof.get('ok') is True and proof.get('packagePurpose') == 'normal-upgrade'
              and proof.get('fullByteEqual') is True and proof.get('patchByteEqual') is True,
              'normal packaging byte-verification proof required')
    full, packet = sample['full_package'], plan['mcu']['package']
    full_bytes, packet_bytes = (h.pinned(pin).read_bytes() for pin in (full, packet))
    h.require(len(packet_bytes) < len(full_bytes), 'functional PATCH must be smaller than FULL')
    assets = {}
    for kind, pin in (('full', full), ('patch', packet)):
        rows = [row for row in proof['assets'] if row['kind'] == kind]
        h.require(len(rows) == 1 and rows[0]['sizeBytes'] == pin['bytes']
                  and rows[0]['sha256'] == pin['sha256'], 'functional package identity differs from preparation')
        assets[kind] = rows[0]
    base_pin = plan['mcu']['images']['base']['image']
    target_pin = plan['mcu']['images']['target']['image']
    base, target = (h.pinned(pin).read_bytes() for pin in (base_pin, target_pin))
    h.require(proof['base']['imageSha256'] == base_pin['sha256']
              and proof['finalImage']['sha256'] == target_pin['sha256']
              and proof['finalImage']['sizeBytes'] == target_pin['bytes'], 'functional source/target identity drift')
    comparison = proof['patchComparison']
    h.require(comparison['encoding'] == 'vendor-bsdiff-lzma'
              and comparison['baseImageSha256'] == base_pin['sha256']
              and comparison['targetImageSha256'] == target_pin['sha256']
              and comparison['patchPackageBytes'] == packet['bytes']
              and comparison['fullPackageBytes'] == full['bytes']
              and comparison['savedBytes'] == full['bytes'] - packet['bytes']
              and comparison['savingsRatio'] == (full['bytes'] - packet['bytes']) / full['bytes']
              and comparison['preferredKindForMatchingBase'] == 'patch', 'normal PATCH comparison drift')
    h.require(len(base) >= 0x460 and len(target) >= 0x460
              and comparison['changesOutsideFwHeader'] is True
              and (base[:0x400] != target[:0x400] or base[0x460:] != target[0x460:]),
              'header-only patches are boundary samples, not representative functional cells')
    checker = byte_checker(h)
    for kind, blob, old in (('full', full_bytes, None), ('patch', packet_bytes, base)):
        try:
            checker.validate_package(blob, target, old)
        except ValueError as error:
            raise RuntimeError('invalid ' + kind + ' ETU: ' + str(error)) from error
    base_fields, target_fields = (checker.recovery.validate_app(image) for image in (base, target))
    h.require(target_fields['version_code'] > base_fields['version_code'], 'functional version must advance')
    h.require(proof['base']['versionCode'] == base_fields['version_code']
              and proof['base']['versionName'] == base_fields['version_name']
              and proof['base']['kind'] in ('app', 'recovery')
              and proof['versionName'] == target_fields['version_name']
              and proof['finalImage']['fileName'] == 'app-final.bin', 'preparation image/version mismatch')
    for kind, version, digest in (('full', 0, ''), ('patch', base_fields['version_code'], base_pin['sha256'])):
        h.require(assets[kind]['baseVersionCode'] == version and assets[kind]['baseImageSha256'] == digest,
                  'preparation asset base identity mismatch')
    tool = comparison['tool']
    h.require(isinstance(tool, dict) and set(tool) == {'fileName', 'sizeBytes', 'sha256'}, 'complete tool identity required')
    tools = [pin for pin in plan.get('tool_dependencies', [])
             if pin.get('bytes') == tool['sizeBytes'] and pin.get('sha256') == tool['sha256']
             and PurePosixPath(pin['path'].replace('\\', '/')).name == tool['fileName']]
    h.require(len(tools) == 1, 'packaging tool must bind one actual tool dependency')
    h.pinned(tools[0])
    archive = preparation.parent

    def original(relative):
        path = h.checked(archive / relative)
        h.require(path.is_file(), 'missing preparation original: ' + relative)
        return path.read_bytes()

    def named_asset(asset):
        name = asset['fileName']
        h.require(isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9_.-]+', name), 'invalid preparation asset name')
        raw = original(name)
        h.require(len(raw) == asset['sizeBytes'] and hashlib.sha256(raw).hexdigest() == asset['sha256'],
                  'preparation original asset identity mismatch')
        return raw

    h.require(named_asset(assets['full']) == full_bytes and named_asset(assets['patch']) == packet_bytes,
              'actual packages differ from archived preparation')
    for relative, expected in (('app-final.bin', target), ('work/base-final.bin', base),
                               ('work/full-candidate.bin', target), ('work/patch-candidate.bin', target)):
        h.require(original(relative) == expected, 'applied/original image mismatch: ' + relative)
    metadata_bytes = original('cloudflare-firmware-release-metadata.json')
    h.require(hashlib.sha256(metadata_bytes).hexdigest() == proof['preparedMetadataSha256'], 'preparation metadata drift')
    metadata = json.loads(metadata_bytes)
    h.require(metadata['assets'] == proof['assets'] and metadata['targetImageSha256'] == target_pin['sha256']
              and metadata['versionCode'] == target_fields['version_code']
              and metadata['versionName'] == proof['versionName'] == proof['build']['versionName']
              and metadata['commitSha'] == proof['commitSha'] == proof['build']['commitSha']
              and metadata['runId'] == proof['runId'] and proof['build']['versionCode'] == target_fields['version_code']
              and proof['build']['buildTimestamp'] == target_fields['build_ts'], 'preparation/build/metadata mismatch')
    recovery = [row for row in proof['assets'] if row['kind'] == 'recovery']
    h.require(len(proof['assets']) == 3 and len(recovery) == 1 and proof['recoveryVerified'] is True,
              'complete normal preparation required')
    h.require(checker.recovery.split_asset(named_asset(recovery[0]), 'recovery')[0] == target,
              'preparation recovery image mismatch')
    verify_steps(proof, original, assets, recovery[0], base_fields, target_fields, h)


def verify_steps(proof, original, assets, recovery, base, target, h):
    rows = proof['steps']
    h.require(isinstance(rows, list) and tuple(row['label'] for row in rows) == STEP_ORDER
              and json.loads(original('steps.json')) == rows, 'complete ordered preparation command evidence required')
    steps, logs = {}, {}
    for row in rows:
        label = row['label']
        h.require(type(row['exitCode']) is int and row['exitCode'] == 0
                  and isinstance(row['executable'], str) and bool(row['executable'])
                  and isinstance(row['argv'], list) and all(isinstance(arg, str) for arg in row['argv']),
                  'unsuccessful or malformed preparation command: ' + label)
        streams = {}
        for stream in ('stdout', 'stderr'):
            raw = original('steps/' + label + '.' + stream + '.txt')
            h.require(hashlib.sha256(raw).hexdigest() == row[stream + 'Sha256'], 'preparation output digest drift: ' + label)
            streams[stream] = raw.decode('utf-8')
        h.require(not re.search(r'^\s*(?:\[err\]|error\b|fatal\b|\S+=FAIL\b)',
                                streams['stdout'] + '\n' + streams['stderr'], re.M | re.I),
                  'preparation output reports failure: ' + label)
        steps[label] = [arg.replace('\\', '/') for arg in row['argv']]
        logs[label] = streams['stdout']

    def argument(label, option):
        argv = steps[label]
        h.require(argv.count(option) == 1 and argv.index(option) + 1 < len(argv), 'missing/duplicate command argument')
        value = argv[argv.index(option) + 1]
        path = PurePosixPath(value)
        h.require((path.is_absolute() or re.match(r'^[A-Za-z]:/', value)) and '..' not in path.parts,
                  'original command path is not absolute/canonical')
        return value

    # CI paths are only logical bindings. Read the hash-bound archive above,
    # never execute recorded commands or require the original CI filesystem.
    root = PurePosixPath(argument('full-pack', '--out')).parent
    final, old = str(root / 'app-final.bin'), str(root / 'work/base-final.bin')
    full, packet = (str(root / assets[kind]['fileName']) for kind in ('full', 'patch'))
    full_out, patch_out = str(root / 'work/full-candidate.bin'), str(root / 'work/patch-candidate.bin')
    recovery_file = str(root / recovery['fileName'])
    app = argument('finalize', '--app')
    base_source = argument('base-verify', '--input')
    tool = argument('patch-pack', '--bsdiff-exe')
    h.require(PurePosixPath(tool).name == proof['patchComparison']['tool']['fileName']
              and PurePosixPath(app).name == proof['build']['app']['fileName'] == 'X-Track-App-GCC.bin',
              'preparation command tool/GCC binding mismatch')
    version, sha = proof['versionName'], proof['finalImage']['sha256']

    def command(label, script, argv, reproducible=False):
        actual = steps[label]
        if reproducible and len(actual) >= 2 and actual[-2] == '--reproduce-from':
            reference = argument(label, '--reproduce-from')
            h.require(PurePosixPath(reference).name == assets[label.split('-')[0]]['fileName'], 'wrong reproduction asset')
            actual = actual[:-2]
        h.require(actual == ['-B', script, *argv], 'preparation command/input binding mismatch: ' + label)

    def verify(label, file, kind, fields, digest, extra=()):
        command(label, BYTE_CHECK, ['--input', file, '--kind', kind, '--version', fields['version_name'],
                                   '--sha256', digest, *extra])
        h.require(json.loads(logs[label]) == dict(ok=True, kind=kind, sha256=digest, **fields),
                  'original byte-check result mismatch: ' + label)

    verify('base-verify', base_source, proof['base']['kind'], base, proof['base']['imageSha256'])
    command('base-extract', 'Tools/jlink/prepare-bootstrap-app.py', ['prepare', '--input', base_source,
            '--input-kind', proof['base']['kind'], '--output', old])
    command('finalize', 'Tools/etu_pack.py', ['finalize', '--app', app, '--out', final,
            '--ver-name', version, '--build-ts', str(proof['build']['buildTimestamp'])])
    verify('finalized-verify', final, 'app', target, sha,
           ['--placeholder', app, '--placeholder-sha256', proof['build']['app']['sha256']])
    command('full-pack', 'Tools/etu_pack.py', ['pack-full', '--app', final, '--out', full, '--ver-name', version], True)
    command('full-apply', 'Tools/etu_unpack.py', [full, '--out', full_out, '--verify-fw-header'])
    verify('full-outer-verify', final, 'app', target, sha, ['--package', full])
    command('patch-pack', 'Tools/etu_pack.py', ['pack-patch', '--old', old, '--new', final, '--out', packet,
            '--ver-name', version, '--base-ver-name', base['version_name'], '--bsdiff-exe', tool], True)
    command('patch-apply', 'Tools/etu_unpack.py', [packet, '--old', old, '--out', patch_out, '--verify-fw-header'])
    verify('patch-outer-verify', final, 'app', target, sha, ['--package', packet, '--base-image', old])
    command('recovery-create', 'Tools/jlink/prepare-bootstrap-app.py', ['prepare', '--input', final,
            '--input-kind', 'app', '--output', str(root / 'work/recovery-app.bin'), '--recovery-output', recovery_file])
    verify('recovery-verify', recovery_file, 'recovery', target, sha)
    for label, marker in (('base-extract', 'P1_5_APP_PREPARE=PASS'), ('finalize', 'finalize OK:'),
                          ('full-pack', 'pack-full OK:'), ('patch-pack', 'pack-patch OK:'),
                          ('recovery-create', 'P1_5_APP_PREPARE=PASS')):
        h.require(marker in logs[label], 'missing successful preparation output: ' + label)
    expected = {
        'full-apply': [f'unpack(full) OK: {full_out}',
                       f"candidate_len={target['image_len']} target_vcode={target['version_code']}", f'image_sha256={sha}'],
        'patch-apply': [f'unpack(patch) OK: {patch_out}',
                        f"old_len={base['image_len']} candidate_len={target['image_len']} target_vcode={target['version_code']} base_vcode={base['version_code']}",
                        'base_sha8(etu)={0} old_sha8={0}'.format(proof['base']['imageSha256'][:16]), f'candidate_sha256={sha}'],
    }
    for label, lines in expected.items():
        h.require([line.strip().replace('\\', '/') for line in logs[label].splitlines()] == lines,
                  'original apply result mismatch: ' + label)
