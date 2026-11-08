"""Explicit P51 benchmark admission and existing semantic/recording adapters."""
from collections import deque
import copy
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import time
from urllib.parse import urlencode, urlsplit
import zipfile

import observation as obs
from observation import h, r, s
import live_phone
import public_proxy

BUDGET = dict(maxCells=2, maxRecordings=32, maxAttempts=64, totalSeconds=18000,
    minimumSpanSeconds=14400, nextBlockReserveSeconds=3000, nextCellReserveSeconds=1800,
    recorderBytes=128*1024*1024, transferReserveBytes=64*1024*1024, sealReserveBytes=4*1024*1024)
APP_ID = 'com.wen.gaia.gaia.p51benchmark'
LINK_PROFILE = 'adaptive-v2-candidate'
SIGNER = '9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579'
INSPECTION_TOOLS = dict(java='b3afe83e1ab067da4c56f1a7b2ba4c14ec832d694333f35b2b45178e9ac596ef',
    aapt='db0ba2050b8f6b37185d2ba458d6e25b565aefa3f3b96040adf0a82c3469ce3c',
    signer='00ef9948f843fe395d2440ae3ef41405b8040a6d5d46493bd1902ac0ee6deae7')
CONTROL_LABELS = {
    'p51-arm-timing': 'Start acknowledged raw link timing recording',
    'p35-reconnect': s.RECORDER_RECONNECT, 'p35-stop': s.RECORDER_STOP,
    'p35-check': '\u68c0\u67e5\u66f4\u65b0', 'p35-download': '\u4e0b\u8f7d\u56fa\u4ef6',
    'p35-start': '\u5f00\u59cb BLE \u4f20\u8f93',
}


def network_plan(plan):
    return dict(plan['mcu'], reference_service=dict(baseVersion=30320, targetVersion=30321,
        appVersion=plan['phone']['app']['version_code'], releaseId='p51-benchmark-30320-30321',
        purpose='P51 fixed-load benchmark only'))


def workflow_archive(delivery, workflow, name):
    run = h.read_json(h.pinned(delivery['workflowRun']))
    source = delivery['source']
    h.require(re.fullmatch(r'[0-9a-f]{40}', source) and run['head_sha'] == source and
        run['repository']['full_name'] == run['head_repository']['full_name'] == 'Eitan-S-23/E-Track' and
        run['repository']['id'] == run['head_repository']['id'] and run['status'] == 'completed' and
        run['conclusion'] == 'success' and run['event'] == 'workflow_dispatch' and
        run['path'] == '.github/workflows/'+workflow and type(run['id']) is int and run['id'] > 0 and
        type(run['run_attempt']) is int and run['run_attempt'] > 0, 'unrelated or unsuccessful artifact workflow')
    artifact = delivery['artifact']
    raw = h.pinned(delivery['archive']).read_bytes()
    expected_name = name.format(run=run['id'], attempt=run['run_attempt'])
    h.require(artifact['name'] == expected_name and type(artifact['id']) is int and artifact['id'] > 0 and
        artifact['workflow_run']['id'] == run['id'] and artifact['workflow_run']['head_sha'] == source and
        artifact['digest'] == 'sha256:'+hashlib.sha256(raw).hexdigest() and artifact['size_in_bytes'] == len(raw),
        'artifact/run/archive identity mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        h.require(len(names) == len(set(names)) <= 10000 and
            sum(item.file_size for item in archive.infolist()) <= 300*1024*1024 and archive.testzip() is None,
            'invalid original artifact archive')
        files = {item.filename: archive.read(item) for item in archive.infolist() if not item.is_dir()}
    return run, files


def source_originals():
    owner = h.host.load('p51_benchmark_source_admission', h.ROOT/'Tools/ota/p51-benchmark-inputs.py')
    return owner.resolve(h.read_json(h.ROOT/owner.MANIFEST))


def workflow_jobs(delivery, run):
    jobs = h.read_json(h.pinned(delivery['workflowJobs']))
    h.require(jobs['total_count'] == len(jobs['jobs']) and 0 < len(jobs['jobs']) <= 100 and
        all(job['run_id'] == run['id'] and job['run_attempt'] == run['run_attempt']
            for job in jobs['jobs']), 'incomplete or unrelated workflow job originals')
    return jobs['jobs']


def native_originals(verification, files):
    native = verification['native']
    expected_sources = ('Tools/ota/p34-acceptance/reference_host.c', 'Libraries/OTA/ota_patch.c',
        'Libraries/OTA/ota_keys.c', 'boot/src/boot_crc32.c', 'boot/src/boot_sha256.c', 'boot/src/boot_fw_header.c',
        'bsdiff_lzma_AES128-main/bspatch/lzma/LzmaDec.c', 'bsdiff_lzma_AES128-main/bspatch/AES128_CTR/aes_core.c',
        'Libraries/OTA/ota_package.c')
    h.require(native['sources'] == {name: hashlib.sha256((h.ROOT/name).read_bytes()).hexdigest()
        for name in expected_sources}, 'native decoder source drift')
    compiled = None
    for name, observation in [('compile', None)]+[(row['case'], row['observation']) for row in native['checks']]:
        prefix = 'evidence/native/'+name
        process = json.loads(files[prefix+'.process.json'])
        stdout, stderr = files[prefix+'.stdout.txt'], files[prefix+'.stderr.txt']
        h.require(process['stage'] == name and type(process['exitCode']) is int and process['exitCode'] == 0 and
            process['timeout'] is False and process['signal'] is None and process['treeCleanupComplete'] is True and
            process['interrupted'] is None and process['cleanupErrors'] == [] and not stderr,
            'native original failed or incomplete: '+name)
        root = PurePosixPath(process['cwd'].replace('\\', '/'))
        h.require(root.is_absolute() and '..' not in root.parts, 'native original working directory')
        area = root/'.cache/p51-candidate'
        argv = [arg.replace('\\', '/') for arg in process['argv']]
        if name == 'compile':
            h.require(not stdout and argv[-2:] == ['-o', str(area/'private/decoder')] and
                all(flag in argv for flag in ('-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-DP51_ALL_ASSETS=1', '-DOTA_PATCH_COALESCE_WRITES=1', '-DCONFIG_OTA_APP_CRC32_NIBBLE=1')) and
                argv[argv.index('-include')+1] == str(area/'private/key.h') and
                all(str(root/source) in argv for source in expected_sources), 'native compiler/input relationship')
            compiled = argv[-1]
        else:
            base = area/('private/wrong-base.bin' if name == 'wrong-base-image' else 'inputs/base.bin')
            h.require(argv == [compiled, str(area/'private'/(name+'.etu')), str(base),
                str(area/'prepared/app-final.bin'), observation['result']] and
                json.loads(stdout) == json.loads(files[prefix+'.observation.json']) == observation,
                'native command/output case mismatch: '+name)


def package_binding(plan):
    config = plan['benchmark']
    delivery = h.read_json(h.pinned(config['package_delivery']))
    h.require(delivery['outcome'] == 'PROTECTED_BENCHMARK_ARCHIVE_RETRIEVED', 'protected package delivery required')
    run, files = workflow_archive(delivery, 'firmware-build.yml', 'p51-benchmark-{run}-{attempt}')
    active = [job for job in workflow_jobs(delivery, run) if job['conclusion'] != 'skipped']
    h.require(len(active) == 1 and active[0]['name'] ==
        'Protected P5 candidate artifacts (no release or device operation)' and
        active[0]['status'] == 'completed' and active[0]['conclusion'] == 'success',
        'protected artifact-only packaging job required')
    metadata = h.read_json(h.pinned(config['metadata']))
    proof = h.read_json(h.pinned(config['source_proof']))
    verification = h.read_json(h.pinned(config['verification']))
    for pin, name in ((config['metadata'], 'prepared/benchmark-metadata.json'),
        (config['source_proof'], 'inputs/benchmark-source.json'),
        (config['verification'], 'evidence/benchmark-verification.json'), (plan['mcu']['package'], 'prepared/patch.etu')):
        h.require(h.pinned(pin).read_bytes() == files[name], 'package input differs from original CI archive: '+name)
    original = source_originals()
    h.require(proof == original['proof'] and metadata['runner'] == dict(commitSha=run['head_sha'],
        runId=str(run['id']), runAttempt=str(run['run_attempt'])), 'original GCC/key or protected package lineage mismatch')
    for name in ('base', 'target', 'boot'):
        h.require(files['inputs/'+name+'.bin'] == original[name], 'archived source bytes mismatch')
    h.require(metadata['schema'] == 'p51-archived-benchmark-v1' and
        metadata['packagePurpose'] == 'fixed-load-benchmark' and metadata['representativeFunctionalSample'] is False and
        metadata['productionPublishable'] is False and metadata['isFormalRelease'] is False and
        metadata['sourceCompilations'] == metadata['finalizations'] == 0 and
        metadata['sourceProofSha256'] == config['source_proof']['sha256'] and
        metadata['verificationSha256'] == config['verification']['sha256'] and
        metadata['originalSourceProof'] == proof and metadata['assets'] == verification['assets'] and
        verification['fullByteEqual'] and verification['patchByteEqual'] and verification['recoveryByteEqual'] and
        verification['native']['warnings'] == verification['native']['errors'] == 0 and
        len(verification['native']['checks']) == 11 and all(row['observation']['passed'] for row in verification['native']['checks']),
        'protected benchmark preparation proof required')
    for field, version, key in (('current', 30320, 'base'), ('target', 30321, 'target')):
        image = plan['firmware'][field]
        prefix = 'base' if key == 'base' else 'target'
        h.require(image['version'] == version and image['sha256'] == proof[key]['sha256'] ==
            metadata[prefix + 'ImageSha256'], 'benchmark finalized identity mismatch')
        raw = h.pinned(plan['mcu']['images'][key]['image']).read_bytes()
        h.require(len(raw) == proof[key]['bytes'] and hashlib.sha256(raw).hexdigest() == image['sha256'],
            'benchmark finalized bytes mismatch')
    assets = [row for row in metadata['assets'] if row['fileName'] == 'patch.etu' and row['kind'] == 'patch']
    h.require(len(assets) == 1 and assets[0]['sizeBytes'] == plan['mcu']['package']['bytes'] == 1048576 and
        assets[0]['sha256'] == plan['mcu']['package']['sha256'], 'benchmark package identity mismatch')
    h.pinned(plan['mcu']['package'])
    native_cases = [('positive', 'ok'), ('payload-crc', 'payload_crc'), ('truncated', 'package_length'),
        ('same-version', 'version'), ('wrong-base-sha', 'base_sha8'), ('wrong-base-image', 'base_sha8'),
        ('full-positive', 'ok'), ('full-crc', 'payload_crc'), ('full-truncated', 'package_length'),
        ('recovery-positive', 'ok'), ('recovery-crc', 'recovery_trailer')]
    for row, (case, expected) in zip(verification['native']['checks'], native_cases):
        observed = row['observation']
        h.require(row['case'] == case and observed['result'] == expected and
            (observed['byte_identical'] if expected == 'ok' else observed['prepares'] == 0),
            'benchmark native case/integrity mismatch')
    for asset in metadata['assets']:
        raw = files['prepared/'+asset['fileName']]
        h.require(len(raw) == asset['sizeBytes'] and hashlib.sha256(raw).hexdigest() == asset['sha256'],
            'benchmark original asset mismatch')
    native_originals(verification, files)
    return assets[0]


def inspection_command(pin):
    receipt = h.read_json(h.pinned(pin))
    h.require(receipt['exit_code'] == 0 and receipt['exit_status'] == 'exited' and
        receipt['stopped_while_running'] is False and receipt['cleanup_complete'] is True and
        receipt['cleanup_errors'] == [] and not h.pinned(receipt['stderr']).read_bytes(),
        'APK inspection did not finish successfully')
    return receipt['argv'], h.pinned(receipt['stdout']).read_text(encoding='utf-8')


def apk_binding(plan):
    app = plan['phone']['app']
    h.require(app['id'] == APP_ID and app['release'] is True and
        type(app['version_code']) is int and app['version_code'] > 0 and
        app['sha256'] == plan['apk']['sha256'], 'dedicated release-mode benchmark APK required')
    apk = h.pinned(plan['apk'])
    h.require(zipfile.is_zipfile(apk), 'actual APK ZIP required')
    with zipfile.ZipFile(apk) as archive:
        h.require(len(archive.namelist()) == len(set(archive.namelist())) and
            sum(item.file_size for item in archive.infolist()) <= 300*1024*1024 and
            archive.testzip() is None and archive.read('AndroidManifest.xml')[:4] == b'\x03\x00\x08\x00',
            'actual binary Android manifest required')
        for abi in ('arm64-v8a', 'armeabi-v7a'):
            native = archive.read('lib/'+abi+'/libapp.so')
            h.require(native.startswith(b'\x7fELF') and plan['firmware']['latest_url'].encode() in native and
                LINK_PROFILE.encode() in native, 'compiled APK endpoint/profile absent')
    build = h.read_json(h.pinned(plan['benchmark']['app_build']))
    h.require(build['schema'] == 'p51-benchmark-apk-v1' and build['apk'] == plan['apk'] and
        build['app'] == app and build['latestUrl'] == plan['firmware']['latest_url'] and
        build['publishRelease'] is False and build['linkProfile'] == LINK_PROFILE,
        'benchmark APK endpoint/profile binding mismatch')
    run, files = workflow_archive(build, 'build.yml', 'android-apk')
    # This dedicated build is dispatched once; the unversioned APK artifact
    # name cannot establish which attempt produced an artifact after a rerun.
    h.require(run['run_attempt'] == 1, 'benchmark APK requires its first original workflow attempt')
    h.require(files['ble-monitor-android.apk'] == apk.read_bytes(), 'APK differs from CI artifact')
    request = h.read_json(h.pinned(build['dispatch']))
    inputs = request['body']['inputs']
    h.require(request['method'] == 'POST' and request['route'] == '/actions/workflows/build.yml/dispatches' and
        request['body']['ref'] == run['head_branch'] and inputs['publish_release'] == 'false' and
        inputs['replace_existing_release'] == 'false' and inputs['firmware_latest_url'] == build['latestUrl'] and
        inputs['release_ota_link_profile'] == LINK_PROFILE and inputs['release_application_id_suffix'] == '.p51benchmark',
        'original APK dispatch differs from the declared build')
    jobs = workflow_jobs(build, run)
    for name in ('Build Android APK', 'Build Windows EXE'):
        matches = [job for job in jobs if job['name'] == name]
        h.require(len(matches) == 1 and matches[0]['status'] == 'completed' and matches[0]['conclusion'] == 'success',
            'both real App build/test hosts must pass')
    h.require(all(job['conclusion'] == 'skipped' for job in jobs
        if job['name'] in ('Create GitHub Release', 'Deploy GitHub Pages')), 'benchmark must not publish or deploy')
    logs = h.pinned(build['workflowLog']).read_text(encoding='utf-8')
    h.require('OTA build intent: '+LINK_PROFILE in logs and
        'Release application id suffix enabled: .p51benchmark' in logs, 'APK compiled-profile/variant originals missing')
    inspection = h.read_json(h.pinned(build['inspection']))
    h.require(inspection['apk'] == plan['apk'], 'APK inspection input differs')
    tools = {name: h.pinned(inspection['tools'][name]) for name in INSPECTION_TOOLS}
    h.require(all(inspection['tools'][name]['sha256'] == digest for name, digest in INSPECTION_TOOLS.items()),
        'unqualified APK inspection tool')
    argv, badging = inspection_command(inspection['badging'])
    h.require(argv == [str(tools['aapt']), 'dump', 'badging', str(apk)], 'APK badging command input mismatch')
    found = re.search(r"^package: name='([^']+)' versionCode='(\d+)' versionName='([^']+)'", badging, re.M)
    h.require(found and found[1] == APP_ID and int(found[2]) == app['version_code'] and
        'application-debuggable' not in badging, 'actual APK ID/version/release mode mismatch')
    argv, signature = inspection_command(inspection['signature'])
    h.require(argv[0] == str(tools['java']) and argv[argv.index('-jar'):] ==
        ['-jar', str(tools['signer']), 'verify', '--verbose', '--print-certs', str(apk)] and
        re.findall(r'certificate SHA-256 digest: ([0-9a-f]{64})', signature) == [SIGNER] and
        'Number of signers: 1' in signature, 'APK signature/source inspection mismatch')
    return build


def validate(plan):
    config = plan.get('benchmark')
    h.require(isinstance(config, dict) and config.get('purpose') == 'fixed-load-benchmark'
        and config.get('controls') == 'semantic-v1' and config.get('budget') == BUDGET
        and plan['kind'] == 'patch' and 'functional_sample' not in plan,
        'explicit benchmark-only execution input required')
    apk_binding(plan)
    asset = package_binding(plan)
    ready = h.read_json(h.pinned(config['fixture_ready']))
    parsed = urlsplit(ready['origin'])
    if 'public_proxy' in ready:
        public_proxy.validate_publication(ready['public_proxy'], ready)
    origin_ok = ready['origin'] == public_proxy.ORIGIN if 'public_proxy' in ready else \
        re.fullmatch(r'[a-z0-9-]+\.trycloudflare\.com', parsed.netloc)
    h.require(parsed.scheme == 'https' and origin_ok and
        not parsed.path and not parsed.query and not parsed.fragment and
        plan['firmware']['latest_url'] == ready['origin'] + live_phone.service.LATEST_PATH and
        plan['firmware']['release_id'] == 'p51-benchmark-30320-30321' and
        ready['package']['sha256'] == asset['sha256'] and ready['package']['bytes'] == 1048576,
        'immutable benchmark fixture/compiled endpoint binding required')
    h.pinned(ready['package'])
    # The existing service verifies the actual ETU outer type/base/target/CRC,
    # independently of successful JSON claims and without accessing the AES key.
    live_phone.service.V2ServiceState(live_phone.service_config(network_plan(plan), ready['origin']), str(h.ROOT))
    return config


def check_fixture(plan, out):
    out = h.fresh(out)
    env = h.environment(out)
    ready_path = h.pinned(plan['benchmark']['fixture_ready'])
    ready = h.read_json(ready_path)
    status = h.read_json(h.checked(ready_path.parent.parent / 'status.json'))
    now = time.monotonic_ns()
    h.require(status['ready'] == plan['benchmark']['fixture_ready'] and
        0 <= now-status['monotonicNs'] <= 5_000_000_000 and
        status['deadlineMonotonicNs']-now >= (BUDGET['totalSeconds']+180)*1_000_000_000,
        'benchmark fixture lifetime is stale or insufficient for the complete campaign')
    h.pinned(status['source'])
    if 'public_proxy' in ready:
        public_proxy.validate_publication(ready['public_proxy'], ready)
    query = live_phone.service_query(network_plan(plan))
    count = 0
    def read(url, limit):
        nonlocal count
        count += 1
        return h.command(out, 'read-%02d' % count, [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
            Path(live_phone.__file__), '--https-read'], env, seconds=35,
            stdin=json.dumps(dict(url=url, timeout=30, limit=limit)).encode())
    latest = json.loads(read(plan['firmware']['latest_url'] + '?' + urlencode(query), 8*1024*1024))
    asset = latest.get('asset', {})
    fw = plan['firmware']
    h.require(latest.get('updateAvailable') is True and latest.get('releaseId') == fw['release_id'] and
        latest.get('versionCode') == fw['target']['version'] and latest.get('targetImageSha256') == fw['target']['sha256'] and
        asset.get('kind') == 'patch' and asset.get('sizeBytes') == fw['package']['bytes'] and
        asset.get('sha256') == fw['package']['sha256'] and asset.get('baseVersionCode') == fw['current']['version'] and
        asset.get('baseImageSha256') == fw['current']['sha256'] and
        urlsplit(asset.get('downloadUrl', '')).netloc == urlsplit(ready['origin']).netloc and
        urlsplit(asset.get('downloadUrl', '')).scheme == 'https', 'live isolated fixture identity changed')
    raw = read(asset['downloadUrl'], fw['package']['bytes']+1)
    h.require(raw == h.pinned(fw['package']).read_bytes(), 'live benchmark bytes changed')
    h.save(out / 'result.json', dict(origin=ready['origin'], package=fw['package'], byteEqual=True,
        normalChannelMutations=0, signedUrlOriginals='read-01.stdout; private temporary fixture token'))


def recording_slots(existing):
    h.require(type(existing) is int and 0 <= existing <= 32, 'invalid original archive count')
    return 32-existing


def has_reserve(used, remaining_seconds):
    h.require(type(used) is int and 0 <= used <= BUDGET['recorderBytes'] and
        type(remaining_seconds) in (int, float) and math.isfinite(remaining_seconds), 'invalid recording capacity/time')
    return used + BUDGET['transferReserveBytes'] + BUDGET['sealReserveBytes'] <= BUDGET['recorderBytes'] and \
        remaining_seconds > BUDGET['nextCellReserveSeconds']


def free_phone_bytes(raw):
    rows = raw.decode('utf-8', 'strict').splitlines()
    fields = rows[-1].split() if len(rows) == 2 else []
    h.require(len(fields) == 6 and fields[3].isdigit() and fields[4].endswith('%'), 'unrecognized phone free-space result')
    return int(fields[3])*1024


def idle_base(row, firmware):
    r.bound(row, dict(firmware=firmware))
    h.require(row['phase'] == 'idle' and row['protocol'] is None and row['session'] == row['durable'] == 0 and
        not row['packageVerified'] and row['packageBytes'] == 0 and row['releaseId'] is None and
        row['freshConnection'] and row['linkConnected'], 'restoration did not leave an idle fresh base')


class MCU(obs.state_chain.m.MCU):
    def __init__(self, plan, out, *, deadline):
        h.require(type(deadline) in (int, float) and math.isfinite(deadline), 'finite benchmark MCU deadline required')
        self.absolute_deadline = deadline
        super().__init__(plan, out)

    def execute(self, commands, reads, label, *, seconds=180, deadline=None):
        end = self.absolute_deadline if deadline is None else min(deadline, self.absolute_deadline)
        self.remaining(seconds, end)
        mutates = any(isinstance(command, str) and
            not command.startswith(('sleep ', 'regs', 'mem')) for command in commands)
        if mutates:
            # Leave the native command its full existing allowance plus the
            # preceding ownership check, rather than cutting a flash short.
            h.require(end-time.monotonic() > seconds+30, 'insufficient full MCU mutation/ownership allowance')
        return super().execute(commands, reads, label, seconds=seconds, deadline=end)


class Observer(obs.Observer):
    def __init__(self, plan, out, known_captures=None):
        p = copy.deepcopy(plan['phone'])
        p['ui'] = {key: {'resource-id': 'p35-' + key} for key in ('start', 'resume', 'stop')}
        p['ui']['arm'] = {'resource-id': 'p51-arm-timing'}
        super().__init__(p, out, plan['notify_cli'])
        self.firmware, self.known_captures = plan['firmware'], dict(known_captures or {})
        self.queue, self.last_state_at = deque(maxlen=1), None
        self.transfer_start_attempted = False
        self.minimum_slots = 15 if plan.get('_long_execution') and not self.known_captures else 1

    def cmd(self, args, *, seconds=None, success_codes=(0,)):
        remaining = self.stage_deadline-time.monotonic()
        h.require(remaining > 0, 'benchmark stage expired')
        return self.phone.cmd(args, seconds=min(remaining, self.p['limits']['command_seconds'], seconds or 30), success_codes=success_codes)

    def pump(self):
        if self.stream_capture is None or self.cursor is None:
            return
        previous = len(self.live)
        self.pump_stream()
        if len(self.live) > previous:
            self.last_state_at = time.monotonic()
            self.queue.append(self.live[-1])

    def tap(self, wanted=None, *, label=None, token=False, bootstrap=False):
        h.require(not self.mutation_unknown, 'previous UI action unresolved; no repeated tap')
        if self.capture_id is None and not bootstrap:
            h.require(wanted in (s.HOME, s.DEVICES, s.CONNECT) or wanted is None and token and label,
                'only navigation may precede recording; business controls require telemetry')
            return s.Smoke.tap(self, wanted, label=label, token=token)
        h.require(label is None and not token, 'active recording requires an explicit semantic control')
        control = self.control_role(wanted)
        # Keep logical selectors for Android's bootstrap and one-shot accounting;
        # only native lookup is adapted, never the raw hierarchy or stored logs.
        return r.Android.tap(self, wanted, bootstrap=bootstrap, resolve_control=self.resolve_control,
            before_tap=lambda: self.admit_control(control, bootstrap=bootstrap))

    def control_role(self, wanted):
        r.selector(wanted)
        h.require(set(wanted) == {'resource-id'} and wanted['resource-id'] in CONTROL_LABELS and
            self.p['app']['id'] == APP_ID, 'unsupported benchmark control or App; no selector fallback')
        return wanted['resource-id']

    def admit_control(self, control, *, bootstrap=False):
        if control == 'p51-arm-timing':
            r.require(bootstrap and self.capture_id is None and not self.arm_attempted and
                not self.stop_attempted, 'recording arm is not a fresh one-shot action', 'UNRESOLVED_STATE')
            return
        r.require(not bootstrap and self.capture_id is not None and self.arm_attempted and
            not self.capture_resolved and self.decoder.closed is None and self.live,
            'active control requires an owned open recording', 'UNRESOLVED_STATE')
        row = self.live[-1]
        r.require(row['captureId'] == self.capture_id and row['healthy'] and
            row['deviceAddress'].lower() == self.p['device']['address'],
            'active control has unhealthy or foreign recording state', 'UNRESOLVED_STATE')
        allowed = {'idle', 'readyToInstall', 'completed', 'failed', 'cancelled'}
        if control == 'p35-start':
            allowed = {'readyToInstall'}
            r.bound(row, dict(firmware=self.firmware), package=True)
            r.require(row['freshConnection'] and row['linkConnected'] and row['session'] == row['durable'] == 0,
                'benchmark start requires a fresh zero-durable package owner', 'UNRESOLVED_STATE')
        elif control == 'p35-download':
            allowed = {'idle'}
        elif control == 'p35-check':
            allowed = {'idle', 'readyToInstall', 'completed'}
        elif control == 'p35-stop':
            r.require(not self.stop_attempted, 'recording stop already attempted; no replay', 'UNRESOLVED_STATE')
        r.require(row['phase'] in allowed, 'OTA state does not permit this control', 'DEVICE_BUSY')

    def resolve_control(self, xml, wanted, package):
        control = self.control_role(wanted)
        r.require(package == APP_ID and s.has_label(xml, package, s.FIRMWARE),
            'benchmark firmware page is not visible', 'UI_UNAVAILABLE')
        if control == 'p51-arm-timing':
            r.require(not s.recorder_active(xml, package),
                'existing recording active; preserve and reconcile', 'UNRESOLVED_STATE')
        else:
            r.require(s.has_label(xml, package, s.RECORDER_STOP) and
                not s.has_label(xml, package, CONTROL_LABELS['p51-arm-timing']) and
                s.closed_recorder_status(xml, package) is None,
                'native toolbar is not an active recorder', 'UNRESOLVED_STATE')
        try:
            point = s.semantic_control(xml, package, CONTROL_LABELS[control])
        except r.Stop as error:
            if error.code != 'UI_WAIT':
                raise
            toolbar = control in {'p51-arm-timing', 'p35-reconnect', 'p35-stop'}
            raise r.Stop('UI_UNAVAILABLE', 'required toolbar role unavailable' if toolbar else
                'control missing; no blind coordinates') from error
        self.record('semantic-control-resolved', role=control, label=CONTROL_LABELS[control],
            hierarchySha256=hashlib.sha256(xml).hexdigest())
        return point

    def check_recording_arm(self):
        self.admit_control('p51-arm-timing', bootstrap=True)
        return self.resolve_control(self.ui(), self.p['ui']['arm'], self.p['app']['id'])

    def scroll(self, *args, **kwargs):
        h.require(self.capture_id is None and not self.arm_attempted, 'navigation swipe only before recording')
        return s.Smoke.scroll(self, *args, **kwargs)

    def navigate(self):
        return s.Smoke.navigate(self)

    def ask(self, label, message, *, asynchronous=False):
        control = {'recording-arm': 'p51-arm-timing', 'recording-stop': 'p35-stop',
            'stop-existing-recording': 'p35-stop', 'fresh-identity': 'p35-reconnect', 'start-ble': 'p35-start'}.get(label)
        h.require(control is not None, 'unsupported autonomous control; no guessed action')
        if label == 'start-ble':
            self.pump()
            r.bound(self.live[-1], dict(firmware=self.firmware), package=True)
        self.tap({'resource-id': control}, bootstrap=label == 'recording-arm')

    def start_recording(self):
        super().start_recording()
        self.mutation_unknown = False
        self.pump()
        self.last_state_at = time.monotonic()
        self.queue.append(self.live[-1])

    def fresh_identity(self, *args, **kwargs):
        row = super().fresh_identity(*args, **kwargs)
        self.mutation_unknown = False
        return row

    def original(self, capture_id, destination):
        pin = self.known_captures.get(capture_id)
        if pin is None:
            raw = super().original(capture_id, destination)
            s.sealed_file(raw, capture_id)
            self.known_captures[capture_id] = h.record(h.checked(destination))
            return raw
        raw = h.pinned(pin).read_bytes()
        s.sealed_file(raw, capture_id)
        remote = '/sdcard/Android/data/' + self.p['app']['id'] + '/files/p35-observations/' + capture_id + '.jsonl'
        size = self.cmd(['shell', 'wc', '-c', remote]).split()
        digest = self.cmd(['shell', 'sha256sum', remote]).split()
        h.require(size and size[0].isdigit() and int(size[0]) == len(raw) == pin['bytes'] and
            digest and digest[0].decode() == pin['sha256'], 'previous phone/local archive changed')
        self.record('sealed-original-reused', captureId=capture_id, original=pin,
            requested=str(h.checked(destination)), phoneLengthAndHashChecked=True)
        return raw

    def old_captures(self):
        existing = len(self.capture_names())
        slots = recording_slots(existing)
        h.require(slots >= self.minimum_slots, 'not enough existing App archive slots; do not delete originals')
        host_required = (slots*4 + existing*2)*BUDGET['recorderBytes'] + 2*1024*1024*1024
        phone_required = slots*2*BUDGET['recorderBytes'] + 512*1024*1024
        host_free = shutil.disk_usage(h.ROOT).free
        phone_free = free_phone_bytes(self.cmd(['shell', 'df', '-k', '/sdcard']))
        self.record('campaign-storage-admission', existingCaptures=existing, remainingSlots=slots,
            hostFreeBytes=host_free, hostRequiredBytes=host_required,
            phoneFreeBytes=phone_free, phoneRequiredBytes=phone_required)
        h.require(host_free >= host_required and phone_free >= phone_required, 'insufficient complete campaign archive capacity')
        super().old_captures()
        h.require(len(self.previous_captures) == existing, 'capture store changed during capacity admission')

    def next_transfer(self):
        self.pump()
        used = self.stream_capture.paths['stdout'].stat().st_size
        remaining = self.recording_deadline-time.monotonic()
        self.record('next-transfer-reserve', bytesUsed=used, remainingSeconds=remaining, budget=BUDGET)
        return has_reserve(used, remaining)

    def ready_package(self, firmware):
        self.phase('benchmark-package-download', 300)
        self.pump()
        after = self.live[-1]['seq']
        self.tap({'resource-id': 'p35-check'})
        def metadata():
            self.pump()
            rows = [row for row in self.live if row['seq'] > after]
            h.require(not any(row['phase'] in ('failed', 'cancelled') for row in rows), 'benchmark latest failed')
            for row in reversed(rows):
                if row['phase'] not in ('idle', 'readyToInstall') or row['releaseId'] != firmware['release_id']:
                    continue
                r.bound(row, dict(firmware=firmware))
                h.require(row['targetVersionCode'] == firmware['target']['version'] and
                    row['targetImageSha256'] == firmware['target']['sha256'] and row['latestUrl'] == firmware['latest_url'] and
                    row['packageSha256'] == firmware['package']['sha256'] and row['packageBytes'] == firmware['package']['bytes'],
                    'benchmark latest metadata mismatch')
                return row
        row = self.wait(metadata)
        self.mutation_unknown = False
        if row['phase'] != 'readyToInstall':
            self.tap({'resource-id': 'p35-download'})
        def downloaded():
            self.pump()
            row = self.live[-1]
            h.require(row['phase'] not in ('failed', 'cancelled'), 'benchmark download failed')
            if row['phase'] != 'readyToInstall':
                return None
            r.bound(row, dict(firmware=firmware), package=True)
            h.require(row['freshConnection'] and row['linkConnected'] and row['session'] == row['durable'] == 0,
                'benchmark package is not a fresh zero-durable start')
            return row
        ready = self.wait(downloaded)
        self.mutation_unknown = False
        return ready

    def clear_at_target(self, completed):
        r.bound(completed, dict(firmware=self.firmware), package=True, final=True)
        h.require(completed['phase'] == 'completed' and completed['freshConnection'] and completed['linkConnected'],
            'only an observed completed upgrade permits idle cleanup')
        self.mutation_unknown = False
        self.phase('target-no-update-idle', 180)
        self.tap({'resource-id': 'p35-check'})
        def idle():
            self.pump()
            row = self.live[-1]
            if row['seq'] <= completed['seq'] or row['phase'] != 'idle':
                return None
            r.bound(row, dict(firmware=self.firmware), final=True)
            h.require(row['latestUrl'] == self.firmware['latest_url'] and row['releaseId'] is None and
                row['protocol'] is None and row['session'] == row['durable'] == 0 and
                not row['packageVerified'] and row['packageBytes'] == 0, 'target NO_UPDATE did not clear session')
            return row
        row = self.wait(idle)
        self.mutation_unknown = False
        self.idle_services()
        self.record('target-no-update-idle-confirmed', state=row)
        return row
