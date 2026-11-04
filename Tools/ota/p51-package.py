"""Artifact-only P5 candidate adapter; existing codecs/owned host commands only."""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import secrets
import signal
import struct
import subprocess
import sys
import sysconfig
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'Tools'), str(ROOT / '.agents/skills/e-track-flutter-debug/scripts'),
                str(ROOT / '.cache/p51-candidate/python'),
                sysconfig.get_path('platlib'), sysconfig.get_path('purelib')]
import host_io
import etu_pack as pack
import etu_unpack as unpack


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


encoding = load('p51_encoding', 'Tools/ota/p34-acceptance/encoding.py')
recovery = load('p51_recovery', 'Tools/jlink/prepare-bootstrap-app.py')
sha = lambda data: hashlib.sha256(data).hexdigest()
STAGE = 'admission'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def checked(path):
    return host_io.checked_output(ROOT, Path(path))


def verified(data, record):
    require(len(data) == record['bytes'] and sha(data) == record['sha256'].lower(), 'Input byte identity mismatch')
    return data


def read(record):
    name = record['path']
    require(isinstance(name, str) and name and ':' not in name and '\\' not in name and
            not name.startswith('/') and not any(p in ('', '.', '..') for p in name.split('/')),
            'Input must be portable worktree-relative POSIX path')
    relative = Path(name)
    return verified(checked(ROOT / relative).read_bytes(), record)


def save(path, data):
    path = checked(path)
    checked(path.parent).mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)


def save_json(path, value):
    save(path, (json.dumps(value, indent=2) + '\n').encode())


def redacted(data):
    text = data.decode('utf8', 'replace') if isinstance(data, bytes) else (data or '')
    key = os.environ.get('OTA_AES_KEY', '')
    if len(key) == 32:
        for secret in [key, *[key[i:i + 8] for i in range(0, 32, 8)]]:
            text = re.sub(re.escape(secret), '[REDACTED_KEY]', text, flags=re.IGNORECASE)
    return text


def native_command(label, argv, env, evidence, timeout=90):
    global STAGE
    STAGE = label
    # The supported launcher waits for stdin until the whole tree is job-owned.
    owned = load('p51_owned', 'Tools/flutter/dev_checks.py')
    job = owned.WindowsJob() if os.name == 'nt' else None
    options = dict(cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    options.update(creationflags=subprocess.CREATE_NO_WINDOW) if job else options.update(start_new_session=True)
    private = checked(evidence.parent.parent / 'private')
    active = checked(private / 'native-active.json')
    save_json(active, dict(stage=label, argv=argv))
    process = None
    stdout = stderr = b''
    code = None
    expired = False
    interrupted = None
    cleanup_complete = False
    cleanup_errors = []
    try:
        process = subprocess.Popen([sys.executable, '-I', '-S', '-B', '-X', 'utf8', '-c', owned.WINDOWS_LAUNCHER], **options)
        if job:
            job.assign(process)
        stdout, stderr = process.communicate(input=(json.dumps(argv) + '\n').encode(), timeout=timeout)
        code = process.returncode
    except subprocess.TimeoutExpired:
        expired = True
    except BaseException as error:
        interrupted = error
    finally:
        try:
            if job:
                job.terminate()
            elif process:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if process:
                stdout, stderr = process.communicate(timeout=10)
                code = process.returncode
            cleanup_complete = True
        except BaseException as error:
            cleanup_errors.append(type(error).__name__)
        finally:
            if job:
                try:
                    job.close()
                except BaseException as error:
                    cleanup_errors.append(type(error).__name__)
                    cleanup_complete = False
    save(evidence / (label + '.stdout.txt'), redacted(stdout).encode())
    save(evidence / (label + '.stderr.txt'), redacted(stderr).encode())
    save_json(evidence / (label + '.process.json'), dict(stage=label, argv=argv, exitCode=code,
        signal=-code if code is not None and code < 0 else None, timeout=expired, limitSeconds=timeout,
        treeCleanupComplete=cleanup_complete, owner='WindowsJob' if job else 'POSIX process group',
        interrupted=type(interrupted).__name__ if interrupted else None, cleanupErrors=cleanup_errors))
    if cleanup_complete:
        active.unlink()
    if interrupted:
        raise interrupted
    require(cleanup_complete, 'Native process-tree closure unconfirmed')
    require(not expired and code == 0, 'Native process failed')
    return stdout or b'', stderr or b''


def resolve_inputs(manifest):
    require(manifest['schema'] == 'p51-candidate-inputs-v1' and manifest['task'] == 'P5-1', 'Candidate schema')
    require(manifest['repository'] == 'Eitan-S-23/E-Track', 'Candidate repository')
    require(manifest['targetVersion'] == '3.3.16' and manifest['originalVersion'] == '3.3.13'
            and manifest['targetTimestamp'] == 1793038630, 'Candidate finalization recipe')
    p = manifest['packet']
    original_index = json.loads(read(p['index']))
    require(p['sha256'] == original_index['sha256'] and p['bytes'] == original_index['bytes'], 'Packet lineage')
    packet = verified(b''.join(read(v) for v in p['parts']), p)
    with zipfile.ZipFile(io.BytesIO(packet)) as z:
        require(len(z.namelist()) == len(set(z.namelist())), 'Duplicate packet member')
        index = json.loads(z.read('index.json'))['files']
        objects = {}
        for name, v in p['objects'].items():
            require(index[v['originalPath']] == dict(bytes=v['bytes'], sha256=v['sha256']), 'Packet object lineage')
            objects[name] = verified(z.read('objects/' + v['sha256']), v)
    artifact = json.loads(objects['artifact'])
    require(artifact['id'] == manifest['originalArtifact'] and artifact['workflow_run']['id'] == manifest['originalRun']
            and artifact['workflow_run']['head_sha'] == manifest['sourceCommit']
            and artifact['name'] == 'p41-rehearsal-%s-%s' % (manifest['originalRun'], manifest['originalAttempt'])
            and artifact['digest'] == 'sha256:' + p['objects']['archive']['sha256'], 'Original CI artifact binding')
    with zipfile.ZipFile(io.BytesIO(objects['archive'])) as z:
        require(len(z.namelist()) == len(set(z.namelist())), 'Duplicate CI member')
        files = {name: verified(z.read(v['member']), v) for name, v in p['members'].items()}
    build, verification = json.loads(files['build']), json.loads(files['verification'])
    require(build['commitSha'] == manifest['sourceCommit'] and build['versionName'] == manifest['originalVersion']
            and build['app']['sha256'] == sha(files['app']) and verification['build'] == build
            and verification['finalImage']['sha256'] == sha(files['base'])
            and str(verification['runId']) == str(manifest['originalRun'])
            and verification['ok'] and verification['fullByteEqual'] and verification['patchByteEqual']
            and verification['recoveryVerified'], 'Original compiled/finalized identity')
    evidence = json.loads(files['keyedEvidence'])
    require(evidence['commitSha'] == build['commitSha'] and evidence['keyBinding'] == build['keyBinding']
            and evidence['buildConfiguration'] == build['buildConfiguration'], 'Original key/compiler evidence')
    require(files['app'][0x400:0x460] == b'\xff' * 96, 'Original App is not an unfinalized GCC artifact')
    base = files['base']
    require(base == files['app'][:0x400] + pack.build_fw_header(files['app'], manifest['originalVersion'],
            build['buildTimestamp']) + files['app'][0x460:], 'Original finalization not reproducible')
    require(recovery.validate_app(base)['version_name'] == manifest['originalVersion'], 'Original App header')
    target = base[:0x400] + pack.build_fw_header(base, manifest['targetVersion'], manifest['targetTimestamp']) + base[0x460:]
    require(sha(target) == manifest['targetSha256'] and recovery.validate_app(target)['version_code'] == 30316,
            'Header-only target identity')
    boot_bytes = resolve_boot(manifest)
    row = json.loads(read(manifest['reference']['selection']))
    compressed = read(manifest['reference']['stream'])
    require(row['base_sha256'] == sha(base) and row['target_sha256'] == sha(target)
            and row['compressed_sha256'] == sha(compressed) and row['compressed_bytes'] == len(compressed)
            and row['etu_bytes'] == 1048576 == 104 + len(compressed), 'Reference identity/length')
    props = bytes.fromhex(row['props_hex'])
    raw = encoding.strict_lzma(props, compressed, row['decoded_bytes'])
    require(sha(raw) == row['raw_sha256'] and unpack.bspatch_apply(base, len(target), raw) == target,
            'Reference decompression/patch identity')
    require(raw == encoding.patch_stream(base, target, row['count'], row['seed'], row['salt']), 'Reference progression witness')
    return dict(base=base, target=target, boot=boot_bytes, build=build, buildOriginal=files['build'], row=row, compressed=compressed,
                artifact=artifact, manifest=manifest)


def resolve_boot(manifest):
    """Same approved external Boot proof for both modes; never the ordinary build."""
    boot = manifest['boot']
    boot_build = json.loads(read(boot['build']))
    require(boot['group'] == boot_build['group'] == 16 and boot['skipIdentical'] and boot_build['skipIdentical']
            and not boot['instrumented'] and not boot_build['instrumented'] and boot_build['retainedReproduced'], 'Boot configuration')
    boot_bytes = read(boot['image'])[:boot['bytes']]
    verified(boot_bytes, boot)
    require(boot_build['artifacts'][0]['sha256'] == sha(boot_bytes), 'Boot reproduced artifact identity')
    with zipfile.ZipFile(io.BytesIO(read(boot['source']))) as z:
        index = json.loads(z.read('index.json'))
        evidence_names = {'evidence/' + build + '/' + name for build in ('baseline', 'instrumented')
                          for name in ('source-inputs.json', 'result.json', 'configure.stdout',
                                       'configure.stderr', 'build.stdout', 'build.stderr')}
        require(set(z.namelist()) == set(index) | evidence_names | {'index.json'}, 'Boot source archive inventory')
        for name, record in index.items():
            verified(z.read(name), record)
        require(json.loads(z.read('evidence/baseline/result.json')) == boot_build, 'Boot source/build lineage')
        verified(z.read('evidence/baseline/source-inputs.json'), boot_build['source'])
    return boot_bytes


def source_boot(config):
    require(config['schema'] == 'p51-new-source-inputs-v2' and config['mode'] == 'new-source', 'New-source schema')
    binding = config['bootBinding']
    require(binding['manifest'] == 'Tools/ota/p51-candidate-inputs.json', 'External Boot binding path')
    manifest_bytes = checked(ROOT / binding['manifest']).read_bytes()
    require(sha(manifest_bytes) == binding['manifestSha256'], 'External Boot manifest drift')
    manifest = json.loads(manifest_bytes)
    return resolve_boot(manifest), manifest


def source_images(raw, build, base_version, target_version):
    """Reuse the actual finalizer, once per header, not two source compilations."""
    for name in (base_version, target_version):
        require(isinstance(name, str) and len(name) <= 16 and
                re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]?)\.(0|[1-9][0-9]?)', name), 'Canonical version pair')
    require(30316 < pack.parse_version_name(base_version) < pack.parse_version_name(target_version) <= 0xffffffff,
            'Fresh forward version pair')
    require(build['versionName'] == target_version and build['versionCode'] == pack.parse_version_name(target_version),
            'Build target version mismatch')
    require(len(raw) == build['app']['sizeBytes'] and sha(raw) == build['app']['sha256'], 'Source App identity mismatch')
    require(raw[0x400:0x460] == b'\xff' * 96, 'Source App must have an unfinalized header')
    timestamp = build['buildTimestamp']
    require(type(timestamp) is int and 0 <= timestamp <= 0xffffffff, 'Build timestamp uint32')
    images = []
    for version in (base_version, target_version):
        image = raw[:0x400] + pack.build_fw_header(raw, version, timestamp) + raw[0x460:]
        fields = recovery.validate_app(image)
        require(fields['version_name'] == version and fields['version_code'] == pack.parse_version_name(version),
                'Finalizer identity')
        images.append(image)
    return tuple(images)


def source_reference(base, target, config, out):
    """Legal progressing reference search; no padding or default-key witness."""
    reference = config['reference']
    require(reference['totalBytes'] == 1048576 and type(reference['seed']) is int
            and 0 <= reference['seed'] <= 0xffffffff and type(reference['budget']) is int
            and 2 <= reference['budget'] <= 256, 'Bounded reference configuration')
    encoding.OUT, encoding.pack, encoding.unpack = checked(out), pack, unpack
    encoding.save_json = lambda name, value: save_json(checked(out) / name, value)
    row = encoding.search(base, target, reference['seed'], reference['budget'])
    raw, props, compressed = encoding.encode(base, target, row['count'], row['seed'], row['salt'])
    require(104 + len(compressed) == 1048576 and sha(compressed) == row['compressed_sha256']
            and sha(raw) == row['raw_sha256'], 'Reference selected identity')
    require(encoding.strict_lzma(props, compressed, len(raw)) == raw
            and unpack.bspatch_apply(base, len(target), raw) == target, 'Reference full-consumption/byte identity')
    save_json(checked(out) / 'selection.json', row)
    save(checked(out) / 'reference.lzma', compressed)
    return row, compressed


def package_source(config, out, key, cc):
    out = checked(out)
    boot, original = source_boot(config)
    request = json.loads((out / 'inputs/source-build.json').read_bytes())
    owner = {k: os.environ[v] for k, v in (('commitSha', 'GITHUB_SHA'), ('runId', 'GITHUB_RUN_ID'),
                                           ('runAttempt', 'GITHUB_RUN_ATTEMPT'))}
    build = request['build']
    require(request['owner'] == owner and request['workflowCommit'] == os.environ['GITHUB_WORKFLOW_SHA']
            and request['reviewedProductBaseline'] == config['reviewedProductBaseline']
            and request['configSha256'] == sha((ROOT / 'Tools/ota/p51-new-source-inputs.json').read_bytes())
            and build['commitSha'] == owner['commitSha']
            and request['baseVersion'] == os.environ['INPUT_CANDIDATE_BASE_VERSION']
            and request['targetVersion'] == os.environ['INPUT_VERSION_NAME']
            and request.get('fullBaseVersion', '') == os.environ.get('INPUT_CANDIDATE_FULL_BASE_VERSION', ''),
            'Source request ownership/drift')
    require((out / 'inputs/boot.bin').read_bytes() == boot, 'Source admitted Boot drift')
    header = ''.join('#define OTA_AES_KEY_1_WORD%d 0x%su\n' % (i, key.hex()[i*8:i*8+8]) for i in range(4)).encode()
    require(build['keyBinding']['source'] == 'approved-ci-key-v1'
            and build['keyBinding']['keySha256'] == sha(key)
            and build['keyBinding']['headerSha256'] == sha(header)
            and build['keyBinding']['keySourceSha256'] == sha((ROOT / 'Libraries/OTA/ota_keys.c').read_bytes())
            and (out / 'private/key.h').read_bytes() == header, 'Compiled/packaging key input mismatch')
    keyed = out / 'keyed-build'
    require(json.loads((keyed / 'gcc-build-inputs.json').read_bytes()) == build, 'Keyed build receipt drift')
    evidence = json.loads((keyed / 'keyed-build-evidence.json').read_bytes())
    require(evidence['commitSha'] == owner['commitSha'] and evidence['keyBinding'] == build['keyBinding']
            and evidence['buildConfiguration'] == build['buildConfiguration'], 'Keyed compiler evidence mismatch')
    for record in evidence['artifacts']:
        verified(checked(keyed / record['path']).read_bytes(), dict(bytes=record['sizeBytes'], sha256=record['sha256']))
    raw = checked(keyed / 'app/X-Track-App-GCC.bin').read_bytes()
    base, target = source_images(raw, build, request['baseVersion'], request['targetVersion'])
    full_base = None
    if request.get('fullBaseVersion'):
        require(request['fullBaseVersion'] != request['baseVersion'], 'Full-cell start must differ from patch base')
        full_base, same_target = source_images(raw, build, request['fullBaseVersion'], request['targetVersion'])
        require(same_target == target, 'Full-cell target identity drift')
        save(out / 'inputs/full-base.bin', full_base)
    save(out / 'inputs/base.bin', base)
    save(out / 'inputs/target.bin', target)
    row, compressed = source_reference(base, target, config, out / 'evidence/reference')
    data = dict(base=base, target=target, boot=boot, row=row, compressed=compressed)
    if full_base is not None:
        data['fullBase'] = full_base
    result = package(data, key, out / 'prepared')
    save(out / 'prepared/app-start.bin', base)
    if full_base is not None:
        save(out / 'prepared/app-start-full.bin', full_base)
    result['native'] = native_verify(data, out / 'prepared', out / 'private', cc, all_assets=True)
    identity = lambda image, version: dict(versionName=version, versionCode=pack.parse_version_name(version),
        sizeBytes=len(image), sha256=sha(image), headerSha256=sha(image[0x400:0x460]), buildTimestamp=build['buildTimestamp'])
    save_json(out / 'evidence/source-images.json', dict(base=identity(base, request['baseVersion']),
        target=identity(target, request['targetVersion']), raw=build['app'], sourceCompilations=1,
        fullBase=identity(full_base, request['fullBaseVersion']) if full_base is not None else None,
        headerOnlyDerivation=True, headerOffset=1024, headerBytes=96,
        boot=dict(sha256=sha(boot), sizeBytes=len(boot), group=16, source=original['boot']['source'],
                  build=original['boot']['build'], evidenceCommit=original['bootEvidenceCommit'])))
    result['assets'] = [dict(fileName=name, sizeBytes=len(blob), sha256=sha(blob)) for name in
        ('app-start.bin', 'app-final.bin', 'X-Track-Boot.bin', 'full.etu', 'patch.etu', 'reference-1MiB.etu', 'recovery.bin',
         *(['app-start-full.bin'] if full_base is not None else []))
        for blob in [(out / 'prepared' / name).read_bytes()]]
    save_json(out / 'evidence/verification.json', result)


def materialize(manifest, out):
    out = checked(out)
    require(not out.exists(), 'Preserve prior input attempt')
    data = resolve_inputs(manifest)
    for name in ('base', 'target', 'boot'):
        save(out / (name + '.bin'), data[name])
    save(out / 'build.json', data['buildOriginal'])
    save_json(out / 'manifest.json', manifest)
    return data


def envelope(plaintext, key, target, base=None):
    nonce = secrets.token_bytes(16)
    payload = pack.aes_ctr_xcrypt(key, nonce, plaintext, True)
    flags = 7 if base is not None else 11
    return pack.build_etu_header(flags, nonce, payload, struct.unpack_from('<I', target, 0x408)[0],
        0 if base is None else struct.unpack_from('<I', base, 0x408)[0],
        bytes(8) if base is None else hashlib.sha256(base).digest()[:8]) + payload


def package(data, key, out):
    out = checked(out)
    require(not out.exists(), 'Preserve prior package attempt')
    base, target, row, compressed = (data[k] for k in ('base', 'target', 'row', 'compressed'))
    native = bytearray(40)
    struct.pack_into('>I', native, 4, len(compressed))
    struct.pack_into('<II', native, 8, len(base), len(target))
    struct.pack_into('>II', native, 16, pack.crc32(base), pack.crc32(target))
    native[24:29] = bytes.fromhex(row['props_hex'])
    struct.pack_into('<Q', native, 32, row['decoded_bytes'])
    inner = pack.normalize_patch_header(bytes(native), len(compressed), base, target)
    patch = envelope(inner + compressed, key, target, base)
    full = envelope(pack.lzma_alone_encode(target), key, target)
    pack.check_limits(len(target), len(full), 'candidate-full')
    pack.check_limits(len(target), len(patch), 'candidate-patch')
    require(len(patch) == 1048576, 'Exact reference size')
    for name, blob in [('app-final.bin', target), ('X-Track-Boot.bin', data['boot']),
                       ('full.etu', full), ('patch.etu', patch), ('reference-1MiB.etu', patch)]:
        save(out / name, blob)
    # Reuse the recovery owner rather than recreating its binary header.
    for name in ('recovery-app.bin', 'recovery.bin'):
        require(not checked(out / name).exists(), 'Preserve recovery output')
    with contextlib.redirect_stdout(io.StringIO()):
        require(recovery.cmd_prepare(argparse.Namespace(
            input=out / 'app-final.bin', input_kind='app', output=out / 'recovery-app.bin',
            recovery_output=out / 'recovery.bin')) == 0, 'Recovery preparation')
    recovered, kind = recovery.split_asset((out / 'recovery.bin').read_bytes(), 'recovery')
    require(kind == 'recovery' and recovered == target, 'Recovery byte identity')
    for name, old in [('full.etu', None), ('patch.etu', base)]:
        blob = (out / name).read_bytes()
        header = unpack.parse_etu_header(blob)
        plain = pack.aes_ctr_xcrypt(key, header['nonce'], blob[64:], False)
        if old is None:
            candidate = unpack.lzma_decompress_stream(plain[:5], struct.unpack_from('<Q', plain, 5)[0], plain[13:])
        else:
            info = unpack.parse_patch_header(plain[:40])
            candidate = unpack.bspatch_apply(old, len(target), encoding.strict_lzma(
                plain[24:29], plain[40:], struct.unpack_from('<Q', plain, 32)[0]))
            require(info is not None, 'Patch header verification')
        require(candidate == target, 'ETU byte roundtrip')
    return dict(fullByteEqual=True, patchByteEqual=True, recoveryByteEqual=True,
                referenceBytes=len(patch), referenceAliasesPatch=True)


def native_verify(data, out, private, cc, all_assets=False):
    out, private = checked(out), checked(private)
    exe = checked(private / ('decoder.exe' if os.name == 'nt' else 'decoder'))
    sources = ['Tools/ota/p34-acceptance/reference_host.c', 'Libraries/OTA/ota_patch.c', 'Libraries/OTA/ota_keys.c',
               'boot/src/boot_crc32.c', 'boot/src/boot_sha256.c', 'boot/src/boot_fw_header.c',
               'bsdiff_lzma_AES128-main/bspatch/lzma/LzmaDec.c', 'bsdiff_lzma_AES128-main/bspatch/AES128_CTR/aes_core.c']
    includes = ['Libraries', 'boot/include', 'bsdiff_lzma_AES128-main/bspatch/lzma',
                'bsdiff_lzma_AES128-main/bspatch/AES128_CTR']
    if all_assets:
        sources.append('Libraries/OTA/ota_package.c')
    temp = checked(private / 'tmp')
    temp.mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('OTA_', 'GH_', 'GITHUB_TOKEN', 'TRACE_', 'CF_', 'CLOUDFLARE_'))}
    env.update(TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp))
    evidence = checked(private.parent / 'evidence/native')
    stdout, stderr = native_command('compile', [cc, '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
        '-DOTA_PATCH_COALESCE_WRITES=1', '-DCONFIG_OTA_APP_CRC32_NIBBLE=1',
        *(['-DP51_ALL_ASSETS=1'] if all_assets else []), '-include', str(private / 'key.h'),
        *['-I' + str(ROOT / p) for p in includes], *[str(ROOT / p) for p in sources], '-o', str(exe)],
        env, evidence)
    require(not stdout and not stderr, 'Native compile produced unexpected diagnostics')
    checks = []
    blob = (out / 'patch.etu').read_bytes()
    bad_crc = bytearray(blob)
    bad_crc[-1] ^= 1

    def change(off, value):
        b = bytearray(blob)
        b[off:off + len(value)] = value
        struct.pack_into('<I', b, 60, pack.crc32(b[:60]))
        return bytes(b)

    cases = [('positive', blob, 'ok'), ('payload-crc', bytes(bad_crc), 'payload_crc'),
             ('truncated', blob[:-1], 'package_length'),
             ('same-version', change(40, data['base'][0x408:0x40c]), 'version'),
             ('wrong-base-sha', change(52, bytes([blob[52] ^ 1])), 'base_sha8')]
    if all_assets:
        wrong_base = bytearray(data['base'])
        wrong_base[-1] ^= 1
        save(private / 'wrong-base.bin', wrong_base)
        cases += [('wrong-base-image', blob, 'base_sha8')]
        full = (out / 'full.etu').read_bytes()
        if data.get('fullBase') is not None:
            cases += [('full-other-start', full, 'ok')]
        corrupt_full = bytearray(full)
        corrupt_full[-1] ^= 1
        cases += [('full-positive', full, 'ok'), ('full-crc', bytes(corrupt_full), 'payload_crc'),
                  ('full-truncated', full[:-1], 'package_length'),
                  ('recovery-positive', (out / 'recovery.bin').read_bytes(), 'ok')]
        bad_recovery = bytearray((out / 'recovery.bin').read_bytes())
        bad_recovery[-1] ^= 1
        cases += [('recovery-crc', bytes(bad_recovery), 'recovery_trailer')]
    for name, value, expected in cases:
        file = checked(private / (name + '.etu'))
        save(file, value)
        base_file = private / 'wrong-base.bin' if name == 'wrong-base-image' else private.parent / 'inputs/base.bin'
        if name == 'full-other-start':
            base_file = private.parent / 'inputs/full-base.bin'
        stdout, stderr = native_command(name, [str(exe), str(file), str(base_file),
            str(out / 'app-final.bin'), expected], env, evidence)
        require(not stderr, 'Native decoder produced unexpected diagnostics')
        observed = json.loads(redacted(stdout))
        save_json(evidence / (name + '.observation.json'), observed)
        require(observed['passed'] and observed['result'] == expected and
                (observed['byte_identical'] if expected == 'ok' else observed['prepares'] == 0), 'Native oracle mismatch')
        checks.append(dict(case=name, observation=observed))
    return dict(warnings=0, errors=0, checks=checks,
                sources={p: sha((ROOT / p).read_bytes()) for p in sources})


def main():
    global STAGE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['inputs', 'package', 'source-inputs', 'source-package', 'command'])
    parser.add_argument('--root-out', type=Path, required=True)
    parser.add_argument('--cc', default='gcc')
    parser.add_argument('--command-json', type=Path)
    args = parser.parse_args()
    require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
            'Explicit worktree and isolated Python required')
    out = checked(args.root_out)
    if args.mode == 'command':
        request = json.loads(checked(args.command_json).read_bytes())
        require(re.fullmatch(r'compiler-[1-9][0-9]*', request['label'])
                and request['argv'][0] in ('cmake', 'arm-none-eabi-size') and request['timeout'] == 600,
                'Bounded compiler request')
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(('OTA_', 'GH_', 'GITHUB_TOKEN', 'TRACE_', 'CF_', 'CLOUDFLARE_'))}
        native_command(request['label'], request['argv'], env, out / 'evidence/native', timeout=request['timeout'])
        return
    if args.mode.startswith('source-'):
        config = json.loads((ROOT / 'Tools/ota/p51-new-source-inputs.json').read_bytes())
        if args.mode == 'source-inputs':
            require(not (out / 'inputs').exists(), 'Preserve prior input attempt')
            boot, original = source_boot(config)
            save(out / 'inputs/boot.bin', boot)
            save_json(out / 'inputs/manifest.json', config)
            print('P51_NEW_SOURCE_BOOT_INPUTS_VERIFIED')
            return
        require(json.loads((out / 'inputs/manifest.json').read_bytes()) == config, 'Materialized source config drift')
        package_source(config, out, bytes.fromhex(os.environ['OTA_AES_KEY']), args.cc)
        print('P51_NEW_SOURCE_BYTES_VERIFIED; formal/hardware NOT_RUN')
        return
    manifest = json.loads((ROOT / 'Tools/ota/p51-candidate-inputs.json').read_bytes())
    if args.mode == 'inputs':
        materialize(manifest, out / 'inputs')
        print('P51_INPUTS_VERIFIED')
        return
    # The owning Node entry verifies protected admission and the original CI key.
    data = resolve_inputs(manifest)
    require(json.loads((out / 'inputs/manifest.json').read_bytes()) == manifest
            and (out / 'inputs/base.bin').read_bytes() == data['base'], 'Materialized input drift')
    key = bytes.fromhex(os.environ['OTA_AES_KEY'])
    owner = json.loads((out / 'private/owner.json').read_bytes())
    require(owner['commitSha'] == os.environ['GITHUB_SHA'] and owner['runId'] == os.environ['GITHUB_RUN_ID']
            and owner['runAttempt'] == os.environ['GITHUB_RUN_ATTEMPT'], 'Private owner mismatch')
    STAGE = 'package-roundtrips'
    result = package(data, key, out / 'prepared')
    result['native'] = native_verify(data, out / 'prepared', out / 'private', args.cc)
    save_json(out / 'evidence/verification.json', result)
    print('P51_PACKAGES_VERIFIED; physical acceptance NOT_RUN')


if __name__ == '__main__':
    def cancelled(signum, frame):
        raise InterruptedError('candidate cancelled')
    signal.signal(signal.SIGTERM, cancelled)
    try:
        main()
    except Exception as error:
        # No traceback or exception value can disclose protected environment data.
        print(json.dumps(dict(error='P51_PACKAGE_FAILED', stage=STAGE, exception=type(error).__name__,
                              originalInputsRetained=True)), file=sys.stderr)
        raise SystemExit(1)
