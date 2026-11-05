"""Real archived bytes and synthetic-key packaging, never protected CI admission."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('p51_package', ROOT / 'Tools/ota/p51-package.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
AREA = m.checked(Path(os.environ.get('P51_TEST_AREA', ROOT / '.cache/p51-packaging-impl-20261104-01/tests')))


class CandidateInputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / 'Tools/ota/p51-candidate-inputs.json').read_bytes())
        cls.data = m.resolve_inputs(cls.manifest)

    def test_exact_original_and_header_only_candidate(self):
        self.assertEqual(m.sha(self.data['base']), self.manifest['packet']['members']['base']['sha256'])
        self.assertEqual(m.sha(self.data['target']), self.manifest['targetSha256'])
        self.assertEqual(self.data['base'][:0x400] + self.data['base'][0x460:],
                         self.data['target'][:0x400] + self.data['target'][0x460:])
        self.assertEqual(len(self.data['boot']), 14800)
        self.assertEqual(self.data['row']['etu_bytes'], 1048576)

    def test_wrong_version_rejected(self):
        bad = copy.deepcopy(self.manifest)
        bad['targetVersion'] = '3.3.15'
        with self.assertRaisesRegex(ValueError, 'recipe'):
            m.resolve_inputs(bad)

    def test_wrong_archive_bytes_rejected(self):
        bad = copy.deepcopy(self.manifest)
        bad['packet']['parts'][0]['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'identity'):
            m.resolve_inputs(bad)

    def test_path_escape_rejected(self):
        for path in ('../outside', 'D:/outside', 'D:outside', '/outside', 'a/../b', 'a\\b', '//server/share'):
            with self.assertRaises(ValueError):
                m.read(dict(path=path, bytes=1, sha256='0' * 64))

    def test_wrong_boot_rejected(self):
        bad = copy.deepcopy(self.manifest)
        bad['boot']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'identity'):
            m.resolve_inputs(bad)

    def test_wrong_target_rejected(self):
        bad = copy.deepcopy(self.manifest)
        bad['targetSha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'target identity'):
            m.resolve_inputs(bad)

    def test_wrong_reference_rejected(self):
        bad = copy.deepcopy(self.manifest)
        bad['reference']['stream']['bytes'] -= 1
        with self.assertRaisesRegex(ValueError, 'identity'):
            m.resolve_inputs(bad)

    def test_failed_native_command_preserves_redacted_originals(self):
        AREA.mkdir(parents=True, exist_ok=True)
        out = m.checked(Path(tempfile.mkdtemp(prefix='failed-native-', dir=AREA)))
        evidence = m.checked(out / 'evidence/native')
        key = '0123456789AbCdEf0123456789abcdef'
        env = dict(os.environ, P51_TEST_DIAGNOSTIC=key)
        command = [sys.executable, '-I', '-S', '-B', '-c',
            "import os,sys;print('compile stage');print('error: '+os.environ['P51_TEST_DIAGNOSTIC']+' 0x89AbCdEfu',file=sys.stderr);sys.exit(1)"]
        with mock.patch.dict(m.os.environ, {'OTA_AES_KEY': key}):
            with self.assertRaisesRegex(ValueError, 'Native process failed'):
                m.native_command('compile', command, env, evidence)
        stderr = (evidence / 'compile.stderr.txt').read_text()
        self.assertNotIn(key, stderr)
        self.assertNotIn('89ABCDEF', stderr)
        self.assertNotIn('89AbCdEf', stderr)
        self.assertIn('error:', stderr)
        self.assertEqual(json.loads((evidence / 'compile.process.json').read_bytes())['exitCode'], 1)
        self.assertEqual((evidence / 'compile.stdout.txt').read_text(), 'compile stage\n')

    def test_native_timeout_closes_compiler_descendants_before_private_cleanup(self):
        AREA.mkdir(parents=True, exist_ok=True)
        out = m.checked(Path(tempfile.mkdtemp(prefix='timeout-native-', dir=AREA)))
        evidence = m.checked(out / 'evidence/native')
        code = "import subprocess,sys,time;p=subprocess.Popen([sys.executable,'-I','-S','-B','-c','import time;time.sleep(30)']);print(p.pid,flush=True);time.sleep(30)"
        with self.assertRaisesRegex(ValueError, 'Native process failed'):
            m.native_command('timeout', [sys.executable, '-I', '-S', '-B', '-c', code], dict(os.environ), evidence, timeout=1)
        receipt = json.loads((evidence / 'timeout.process.json').read_bytes())
        self.assertTrue(receipt['timeout'] and receipt['treeCleanupComplete'])
        self.assertFalse((out / 'private/native-active.json').exists())
        pid = int((evidence / 'timeout.stdout.txt').read_text().strip())
        if os.name == 'nt':
            import ctypes
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.OpenProcess.restype = ctypes.c_void_p
            handle = kernel.OpenProcess(0x100000, False, pid)
            if handle:
                try:
                    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
                    self.assertEqual(kernel.WaitForSingleObject(handle, 0), 0)
                finally:
                    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
                    kernel.CloseHandle(handle)
        else:
            proc = Path('/proc') / str(pid) / 'stat'
            self.assertTrue(not proc.exists() or proc.read_text().split(') ')[1].split()[0] == 'Z')

    def test_real_roundtrip_and_native_negatives_with_fixture_key(self):
        self.assertFalse(os.environ.get('OTA_AES_KEY'), 'Do not inject a protected key into host tests')
        AREA.mkdir(parents=True, exist_ok=True)
        out = m.checked(Path(tempfile.mkdtemp(prefix='native-', dir=AREA)))
        private = m.checked(out / 'private')
        private.mkdir()
        key = bytes.fromhex('01' * 16)
        m.save(private / 'key.h', ''.join('#define OTA_AES_KEY_1_WORD%d 0x01010101u\n' % i for i in range(4)).encode())
        m.save(out / 'inputs/base.bin', self.data['base'])
        result = m.package(self.data, key, out / 'prepared')
        self.assertEqual(result['referenceBytes'], 1048576)
        self.assertEqual((out / 'prepared/patch.etu').read_bytes(), (out / 'prepared/reference-1MiB.etu').read_bytes())
        cc = os.environ.get('P51_TEST_CC') or shutil.which('gcc')
        self.assertIsNotNone(cc, 'Native compiler required; do not turn a skipped check into PASS')
        native = m.native_verify(self.data, out / 'prepared', private, cc)
        self.assertEqual(len(native['checks']), 5)
        m.save_json(out / 'SELFTEST-ONLY.json', dict(protectedKey=False, installable=False, publishable=False,
                                                    result=result, native=native))
        with self.assertRaisesRegex(ValueError, 'Preserve'):
            m.package(self.data, key, out / 'prepared')

    def test_new_source_images_reject_wrong_pair_source_and_build(self):
        raw = bytearray(self.data['base'])
        raw[0x400:0x460] = b'\xff' * 96
        raw = bytes(raw)
        build = dict(versionName='3.4.2', versionCode=30402, buildTimestamp=1790000000,
                     app=dict(sizeBytes=len(raw), sha256=m.sha(raw)))
        base, target = m.source_images(raw, build, '3.4.1', '3.4.2')
        self.assertEqual(base[:0x400] + base[0x460:], raw[:0x400] + raw[0x460:])
        self.assertEqual(target[:0x400] + target[0x460:], base[:0x400] + base[0x460:])
        for old, new in [('3.3.16', '3.4.2'), ('3.4.2', '3.4.2'), ('3.4.3', '3.4.2'),
                         ('3.4', '3.4.2'), ('3.4.1', '3.4.2-x'), ('3.4.1', '429496.99.99')]:
            with self.subTest(old=old, new=new), self.assertRaises(ValueError):
                m.source_images(raw, build, old, new)
        for change in [dict(app=dict(sizeBytes=len(raw), sha256='0'*64)), dict(versionCode=30403),
                       dict(buildTimestamp=-1), dict(buildTimestamp=True)]:
            with self.assertRaises(ValueError):
                m.source_images(raw, dict(build, **change), '3.4.1', '3.4.2')
        with self.assertRaises(ValueError):
            m.source_images(self.data['base'], build, '3.4.1', '3.4.2')

    def test_new_source_exact_reference_and_all_native_assets(self):
        self.assertFalse(os.environ.get('OTA_AES_KEY'))
        AREA.mkdir(parents=True, exist_ok=True)
        out = m.checked(Path(tempfile.mkdtemp(prefix='new-source-', dir=AREA)))
        config = json.loads((ROOT / 'Tools/ota/p51-new-source-inputs.json').read_bytes())
        boot, original = m.source_boot(config)
        self.assertEqual(boot, self.data['boot'])
        raw = bytearray(self.data['base'])
        raw[0x400:0x460] = b'\xff' * 96
        raw[0x1000] ^= 1  # Synthetic distinct source bytes, never a UI/CI firmware claim.
        raw = bytes(raw)
        build = dict(versionName='3.4.2', versionCode=30402, buildTimestamp=1790000000,
                     app=dict(sizeBytes=len(raw), sha256=m.sha(raw)))
        base, target = m.source_images(raw, build, '3.4.1', '3.4.2')
        # Optional original measurements avoid replaying a known failed encoding
        # campaign. The search still charges every selected cache entry to its budget.
        cache = os.environ.get('P51_TEST_REFERENCE_CACHE')
        if cache:
            for path in m.checked(Path(cache)).glob('measure-*.json'):
                record = json.loads(path.read_bytes())
                self.assertEqual(record['base_sha256'], m.sha(base))
                self.assertEqual(record['target_sha256'], m.sha(target))
                m.save(out / 'evidence/reference/logs' / path.name, path.read_bytes())
        row, compressed = m.source_reference(base, target, config, out / 'evidence/reference')
        self.assertEqual(104 + len(compressed), 1048576)
        plain = m.encoding.strict_lzma(bytes.fromhex(row['props_hex']), compressed, row['decoded_bytes'])
        self.assertEqual(m.unpack.bspatch_apply(base, len(target), plain), target)
        for invalid in (compressed[:-1], compressed + b'garbage'):
            with self.assertRaises((AssertionError, ValueError, m.encoding.lzma.LZMAError)):
                m.encoding.strict_lzma(bytes.fromhex(row['props_hex']), invalid, row['decoded_bytes'])
        data = dict(base=base, target=target, boot=boot, row=row, compressed=compressed)
        private = m.checked(out / 'private')
        private.mkdir()
        key = bytes.fromhex('01' * 16)
        m.save(private / 'key.h', ''.join('#define OTA_AES_KEY_1_WORD%d 0x01010101u\n' % i for i in range(4)).encode())
        m.save(out / 'inputs/base.bin', base)
        result = m.package(data, key, out / 'prepared')
        cc = os.environ.get('P51_TEST_CC') or shutil.which('gcc')
        self.assertIsNotNone(cc)
        native = m.native_verify(data, out / 'prepared', private, cc, all_assets=True)
        self.assertEqual(len(native['checks']), 11)
        self.assertTrue(all(c['observation']['passed'] for c in native['checks']))
        m.save_json(out / 'SELFTEST-ONLY.json', dict(protectedKey=False, installable=False,
            source='synthetic modified archived bytes; NOT a protected new-source build',
            versions='fixture values only, not reserved', build=build, row=row, result=result, native=native))

    def test_source_pipeline_request_drift_and_metadata_bindings(self):
        self.assertFalse(os.environ.get('OTA_AES_KEY'))
        AREA.mkdir(parents=True, exist_ok=True)
        fixture = m.checked(Path(tempfile.mkdtemp(prefix='pipeline-', dir=AREA)))
        out = m.checked(fixture / '.cache/p51-candidate')
        config_bytes = (ROOT / 'Tools/ota/p51-new-source-inputs.json').read_bytes()
        config = json.loads(config_bytes)
        boot, original = m.source_boot(config)
        owner = dict(commitSha='a'*40, runId='123', runAttempt='1')
        e = dict(GITHUB_SHA='a'*40, GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='1',
                 GITHUB_WORKFLOW_SHA='a'*40, INPUT_CANDIDATE_BASE_VERSION='3.4.1',
                 INPUT_VERSION_NAME='3.4.2', OTA_AES_KEY='bc'*16, INPUT_CANDIDATE_FULL_BASE_VERSION='3.4.0')
        raw = bytearray(self.data['base'])
        raw[0x400:0x460] = b'\xff' * 96
        raw[0x1000] ^= 1
        raw = bytes(raw)
        key = bytes.fromhex(e['OTA_AES_KEY'])
        header = ''.join('#define OTA_AES_KEY_1_WORD%d 0xbcbcbcbcu\n' % i for i in range(4)).encode()
        build = dict(commitSha=owner['commitSha'], versionName='3.4.2', versionCode=30402,
                     buildTimestamp=1790000000, app=dict(fileName='X-Track-App-GCC.bin',
                     sizeBytes=len(raw), sha256=m.sha(raw)), boot=dict(fileName='X-Track-Boot.bin',
                     sizeBytes=4, sha256=m.sha(b'boot')),
                     keyBinding=dict(schemaVersion=1, keyId=1, source='approved-ci-key-v1',
                     keySha256=m.sha(key), headerSha256=m.sha(header),
                     keySourceSha256=m.sha((ROOT / 'Libraries/OTA/ota_keys.c').read_bytes())),
                     buildConfiguration=self.data['build']['buildConfiguration'])
        request = dict(build=build, owner=owner, workflowCommit=e['GITHUB_WORKFLOW_SHA'],
            configSha256=m.sha(config_bytes), reviewedProductBaseline=config['reviewedProductBaseline'],
            baseVersion='3.4.1', targetVersion='3.4.2', fullBaseVersion='3.4.0')
        m.save(out / 'inputs/boot.bin', boot)
        m.save(out / 'private/key.h', header)
        m.save_json(out / 'private/owner.json', owner)
        m.save_json(out / 'keyed-build/gcc-build-inputs.json', build)
        artifacts = []
        for path, blob in [('app/X-Track-App-GCC.bin', raw), ('app/X-Track-App-GCC.elf', b'synthetic ELF'),
                           ('app/X-Track-App-GCC.map', b'synthetic MAP'), ('boot/X-Track-Boot.bin', b'boot')]:
            m.save(out / 'keyed-build' / path, blob)
            artifacts.append(dict(path=path, sizeBytes=len(blob), sha256=m.sha(blob)))
        m.save_json(out / 'keyed-build/keyed-build-evidence.json', dict(commitSha=owner['commitSha'],
                    keyBinding=build['keyBinding'], buildConfiguration=build['buildConfiguration'], artifacts=artifacts))
        options = build['buildConfiguration']['cmakeOptions']
        cache = 'CMAKE_BUILD_TYPE:STRING=Release\nKEIL_GCC_COMPILER_CACHE:STRING=OFF\n' + ''.join(
            '%s:STRING=%s\n' % (k,v) for k,v in options.items())
        m.save(out / 'keyed-build/CMakeCache.txt', cache.encode())
        m.save_json(out / 'keyed-build/compile_commands.json', [dict(command='arm-none-eabi-gcc ' +
            ' '.join('-D' + d for d in build['buildConfiguration']['appCompileDefinitions']) +
            ' -o CMakeFiles/X_Track_App_GCC.dir/keys.o')])
        def replace_request(value):
            m.checked(out / 'inputs/source-build.json').write_bytes((json.dumps(value)+'\n').encode())
        with mock.patch.dict(m.os.environ, e):
            for field, value in [('owner', dict(owner, runAttempt='2')), ('workflowCommit', 'b'*40),
                                 ('configSha256', '0'*64), ('reviewedProductBaseline', 'b'*40),
                                 ('baseVersion', '3.4.0'), ('targetVersion', '3.4.3'), ('fullBaseVersion', '3.4.1')]:
                replace_request(dict(request, **{field:value}))
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'ownership/drift'):
                    m.package_source(config, out, key, 'gcc')
            replace_request(request)
            with self.assertRaisesRegex(ValueError, 'key input mismatch'):
                m.package_source(config, out, bytes.fromhex('de'*16), 'gcc')
            base, target = m.source_images(raw, build, '3.4.1', '3.4.2')
            # Search itself already executed above. This adapter integration reuses its
            # exact recipe, re-encodes and re-verifies it, never a CI evidence fixture.
            patch_raw, props, compressed = m.encoding.encode(base, target, 209108, 7, 3)
            row = dict(count=209108, seed=7, salt=3, decoded_bytes=len(patch_raw), props_hex=props.hex(),
                       compressed_sha256=m.sha(compressed), raw_sha256=m.sha(patch_raw))
            with mock.patch.object(m.encoding, 'search_adaptive', return_value=row):
                m.package_source(config, out, key, os.environ.get('P51_TEST_CC') or shutil.which('gcc'))
        script = fixture / 'metadata.mjs'
        module = (ROOT / '.github/scripts/firmware-candidate.mjs').as_uri()
        body = 'import assert from "node:assert/strict";\nimport {readFile,writeFile} from "node:fs/promises";\n'
        body += 'import { sourceMetadata } from %s;\n' % json.dumps(module)
        body += 'const root=%s, env=%s, config=%s, build=%s;\n' % (
            json.dumps(str(fixture)), json.dumps(e), json.dumps(config), json.dumps(build))
        body += """
const meta = await sourceMetadata(root, env, config, build);
assert.equal(meta.mode, "new-source");
assert.equal(meta.sourceCompilations, 1);
assert.equal(meta.derivation, "one-keyed-source-build/three-fw-header-finalizations");
assert.equal(meta.bleFullCell.suppliedFullStart.versionName, "3.4.0");
assert.notEqual(meta.bleFullCell.suppliedFullStart.sha256, meta.baseImageSha256);
assert.equal(meta.source.reviewedProductBaseline, config.reviewedProductBaseline);
assert.equal(meta.source.actualCheckout, env.GITHUB_SHA);
assert.equal(meta.ordinaryBuiltBoot.candidateBoot, false);
assert.equal(meta.boot.kind, "external-approved-group16");
assert.equal(meta.boot.firmwareRebuilt, false);
assert.equal(meta.bleFullCell.actualDeviceBinding, "NOT_RUN");
const file=root+"/.cache/p51-candidate/prepared/full.etu";
const bytes=await readFile(file);
const bad=Buffer.from(bytes); bad[bad.length-1]^=1;
await writeFile(file,bad);
await assert.rejects(sourceMetadata(root,env,config,build),/identity mismatch/);
await writeFile(file,bytes);
await writeFile(root+"/SELFTEST-metadata.json",JSON.stringify(meta,null,2));
console.log("source_metadata_bound_and_drift_rejected");
"""
        m.save(script, body.encode())
        env = {k:v for k,v in os.environ.items() if not k.startswith(('OTA_', 'GH_', 'GITHUB_TOKEN', 'TRACE_', 'CF_', 'CLOUDFLARE_'))}
        m.native_command('metadata', [shutil.which('node'), str(script)], env, out / 'evidence/native')
        m.save_json(fixture / 'SELFTEST-ONLY.json', dict(protectedCI=False, protectedKey=False,
                    installable=False, sourceBuild='compiler receipt double and synthetic bytes',
                    referenceSearch='exact integration recipe replay; actual search in separate test'))


class StartStateSupplement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / 'Tools/ota/p51-start-state-inputs.json').read_bytes())
        cls.data = m.resolve_supplement(cls.config)

    def test_original_archive_and_start_headers_are_exact(self):
        for rec, image in zip(self.config['images'], self.data['images']):
            self.assertEqual(m.sha(image), rec['sha256'])
            self.assertEqual(len(image), 615132)
            fields = m.recovery.validate_app(image)
            self.assertEqual((fields['version_code'], fields['build_ts']), (rec['versionCode'], 1793820855))
        self.assertEqual(self.data['originalOwner']['commitSha'], '1430c8ff7f3bcd9a35bfe158ba697b99021f75f2')

    def test_wrong_archive_image_version_source_and_mixed_contract_rejected(self):
        bads = []
        for field in ('archive', 'artifact'):
            bad = copy.deepcopy(self.config)
            bad[field]['sha256'] = '0'*64
            bads.append(bad)
        for field, value in [('sourceCommit', 'a'*40), ('originalRun', 1), ('originalAttempt', 2),
                             ('originalArtifact', 1), ('buildTimestamp', 1), ('mode', 'new-source')]:
            bads.append(dict(self.config, **{field:value}))
        for field, value in [('sha256', '0'*64), ('versionCode', 30319), ('versionName', '3.3.19'),
                             ('fileName', 'full.etu'), ('member', 'prepared/app-final.bin')]:
            bad = copy.deepcopy(self.config)
            bad['images'][0][field] = value
            bads.append(bad)
        for bad in bads:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                m.resolve_supplement(bad)

    def test_protected_original_binding_rejects_fixture_key_before_outputs(self):
        AREA.mkdir(parents=True, exist_ok=True)
        out = m.checked(Path(tempfile.mkdtemp(prefix='supplement-key-reject-', dir=AREA)))
        with self.assertRaisesRegex(ValueError, 'key binding mismatch'):
            m.package_supplement(self.config, self.data, out, bytes.fromhex('01'*16), 'gcc')
        self.assertFalse((out / 'prepared').exists())
        self.assertFalse((out / 'evidence').exists())

    def test_real_supplement_adapter_rejects_mixed_owner_and_key_before_packaging(self):
        self._check_real_supplement_adapter_rejections()

    def test_real_supplement_adapter_isolated_from_ambient_base_versions(self):
        fields = ('INPUT_CANDIDATE_BASE_VERSION', 'INPUT_CANDIDATE_FULL_BASE_VERSION')
        contexts = [dict(), dict.fromkeys(fields, ''), {fields[0]: '3.3.18'},
                    dict(zip(fields, ('3.3.18', '3.3.17')))]
        original = dict(m.os.environ)
        for ambient in contexts:
            with self.subTest(ambient=ambient), mock.patch.dict(m.os.environ, {}):
                for field in fields:
                    m.os.environ.pop(field, None)
                m.os.environ.update(ambient)
                expected = dict(m.os.environ)
                self._check_real_supplement_adapter_rejections()
                self.assertEqual(dict(m.os.environ), expected)
            self.assertEqual(dict(m.os.environ), original)

    def _check_real_supplement_adapter_rejections(self):
        AREA.mkdir(parents=True, exist_ok=True)
        out = m.checked(Path(tempfile.mkdtemp(prefix='supplement-adapter-', dir=AREA)))
        argv = ['p51-package.py', 'supplement-inputs', '--root-out', str(out)]
        with mock.patch.object(m.sys, 'argv', argv):
            m.main()
        owner = dict(commitSha='a'*40, runId='456', runAttempt='2')
        m.save_json(out / 'evidence/input-binding.json', dict(owner=owner,
            manifestSha256=m.sha((ROOT / 'Tools/ota/p51-start-state-inputs.json').read_bytes())))
        m.save_json(out / 'private/owner.json', owner)
        m.save(out / 'private/key.h', b'public fixture, deliberately not the original protected key')
        env = dict(GITHUB_SHA='a'*40, GITHUB_RUN_ID='456', GITHUB_RUN_ATTEMPT='2', GITHUB_WORKFLOW_SHA='a'*40,
            INPUT_CANDIDATE_MODE='start-state-supplement', INPUT_VERSION_NAME='3.3.19', INPUT_PACKAGE_CANDIDATE='true',
            INPUT_CANDIDATE_BASE_VERSION='', INPUT_CANDIDATE_FULL_BASE_VERSION='',
            INPUT_PUBLISH='false', INPUT_REHEARSAL='false', INPUT_CHECK_BINDINGS='false', OTA_BOOT_CHAIN_READY='false',
            FIRMWARE_RELEASE_MODE='artifact-candidate-supplement',
            FIRMWARE_CANDIDATE_CONTEXT='firmware-rehearsal/artifact-only-start-state-v1', OTA_AES_KEY='01'*16)
        argv[1] = 'supplement-package'
        for field,value in [('GITHUB_RUN_ATTEMPT','3'), ('GITHUB_WORKFLOW_SHA','b'*40),
                             ('INPUT_PUBLISH','true'), ('INPUT_REHEARSAL','true'), ('OTA_BOOT_CHAIN_READY','true'),
                             ('INPUT_CANDIDATE_BASE_VERSION','3.3.18'), ('INPUT_CANDIDATE_FULL_BASE_VERSION','3.3.17')]:
            with mock.patch.object(m.sys, 'argv', argv), mock.patch.dict(m.os.environ,dict(env,**{field:value})), \
                    mock.patch.object(m,'package_supplement') as package:
                with self.assertRaisesRegex(ValueError,'runner drift'):
                    m.main()
                package.assert_not_called()
        with mock.patch.object(m.sys,'argv',argv), mock.patch.dict(m.os.environ,env), \
                mock.patch.object(m,'package_supplement') as package:
            with self.assertRaisesRegex(ValueError,'key binding mismatch'):
                m.main()
            package.assert_not_called()
        self.assertFalse((out / 'prepared').exists())

    def test_real_full_roundtrips_native_negatives_and_distinct_metadata_owners(self):
        self.assertFalse(os.environ.get('OTA_AES_KEY'))
        AREA.mkdir(parents=True, exist_ok=True)
        fixture = m.checked(Path(tempfile.mkdtemp(prefix='supplement-fixture-', dir=AREA)))
        out = m.checked(fixture / '.cache/p51-candidate')
        private = m.checked(out / 'private')
        private.mkdir(parents=True)
        key = bytes.fromhex('01'*16)
        header = ''.join('#define OTA_AES_KEY_1_WORD%d 0x01010101u\n' % i for i in range(4)).encode()
        m.save(private / 'key.h', header)
        # Only the in-memory key-binding proof is a double; images/codecs/decoder
        # are real. This never represents protected key/CI/candidate admission.
        data = copy.deepcopy(self.data)
        data['build']['keyBinding'].update(keySha256=m.sha(key), headerSha256=m.sha(header))
        config_bytes = (ROOT / 'Tools/ota/p51-start-state-inputs.json').read_bytes()
        m.save(out / 'inputs/manifest.json', config_bytes)
        m.save_json(out / 'inputs/supplement-build.json', data['build'])
        m.save_json(out / 'inputs/supplement-source.json', dict(originalOwner=data['originalOwner'],
            configSha256=m.sha(config_bytes), images=self.config['images'], build=data['build'],
            boot=data['originalMetadata']['boot'], elfMapRelationship=data['originalMetadata']['elfMapRelationship']))
        e = dict(GITHUB_ACTIONS='true', GITHUB_EVENT_NAME='workflow_dispatch', GITHUB_REPOSITORY='Eitan-S-23/E-Track',
            GITHUB_SHA='a'*40, INPUT_CANDIDATE_REVIEWED_COMMIT='a'*40, GITHUB_RUN_ID='456', GITHUB_RUN_ATTEMPT='2',
            INPUT_PACKAGE_CANDIDATE='true', INPUT_PUBLISH='false', INPUT_REHEARSAL='false', INPUT_CHECK_BINDINGS='false',
            OTA_BOOT_CHAIN_READY='false', INPUT_VERSION_NAME='3.3.19', INPUT_FIRMWARE_BUILD_PROFILE='p34-v2-candidate',
            INPUT_CANDIDATE_MODE='start-state-supplement', FIRMWARE_RELEASE_MODE='artifact-candidate-supplement',
            FIRMWARE_CANDIDATE_CONTEXT='firmware-rehearsal/artifact-only-start-state-v1', GITHUB_REF='refs/heads/fixture-only',
            GITHUB_WORKFLOW_SHA='a'*40, GITHUB_WORKFLOW_REF='Eitan-S-23/E-Track/.github/workflows/firmware-build.yml@refs/heads/fixture-only')
        owner = dict(commitSha=e['GITHUB_SHA'], runId=e['GITHUB_RUN_ID'], runAttempt=e['GITHUB_RUN_ATTEMPT'])
        m.save_json(private / 'owner.json', owner)
        cc = os.environ.get('P51_TEST_CC') or shutil.which('gcc')
        self.assertIsNotNone(cc)
        with mock.patch.object(m.encoding, 'search_adaptive', side_effect=AssertionError('no search')), \
                mock.patch.object(m, 'source_images', side_effect=AssertionError('no finalization')):
            m.package_supplement(self.config, data, out, key, cc)
        report = json.loads((out / 'evidence/supplement-verification.json').read_bytes())
        self.assertEqual(len(report['native']['checks']), 8)
        self.assertEqual(sorted(p.name for p in (out / 'prepared').iterdir()),
                         ['initialize-30317-full.etu', 'initialize-30318-full.etu'])
        with self.assertRaisesRegex(ValueError, 'Preserve'):
            m.package_supplement(self.config, data, out, key, cc)
        # A wrong expected image must fail the actual decoder's byte oracle.
        wrong = m.checked(out / 'inputs/initialize-30318.bin')
        env = {k:v for k,v in os.environ.items() if not k.startswith(('OTA_', 'GH_', 'GITHUB_TOKEN', 'TRACE_', 'CF_', 'CLOUDFLARE_'))}
        decoder = private / ('init-30317-decoder.exe' if os.name == 'nt' else 'init-30317-decoder')
        with self.assertRaisesRegex(ValueError, 'Native process failed'):
            m.native_command('wrong-expected-image', [str(decoder), str(out / 'prepared/initialize-30317-full.etu'),
                str(out / 'inputs/base.bin'), str(wrong), 'ok'], env, out / 'evidence/native')
        script = fixture / 'metadata.mjs'
        body = 'import assert from "node:assert/strict";import {readFile,writeFile} from "node:fs/promises";\n'
        body += 'import {supplementMetadata,cleanupCandidate} from %s;\n' % json.dumps((ROOT / '.github/scripts/firmware-candidate.mjs').as_uri())
        body += 'const root=%s,env=%s,config=%s;\n' % (json.dumps(str(fixture)),json.dumps(e),json.dumps(self.config))
        body += """
const meta=await supplementMetadata(root,env,config);
assert.notEqual(meta.runner.commitSha,meta.originalBuild.commitSha);
assert.equal(meta.originalBuild.runId,'41900439548');
assert.equal(meta.runner.runId,'456');
assert.equal(meta.workflow.commitSha,env.GITHUB_SHA);
assert.equal(meta.sourceCompilations,0);
assert.equal(meta.boot.includedInSupplement,false);
assert.equal(meta.target30319Regenerated,false);
const file=root+'/.cache/p51-candidate/prepared/initialize-30317-full.etu';
const bytes=await readFile(file);const bad=Buffer.from(bytes);bad[bad.length-1]^=1;
await writeFile(file,bad);
await assert.rejects(supplementMetadata(root,env,config),/identity drift/);
await writeFile(file,bytes);
const proofFile=root+'/.cache/p51-candidate/inputs/supplement-source.json';
const proofBytes=await readFile(proofFile);const proof=JSON.parse(proofBytes);
proof.boot.group=15;await writeFile(proofFile,JSON.stringify(proof));
await assert.rejects(supplementMetadata(root,env,config),/source drift/);
await writeFile(proofFile,proofBytes);
await writeFile(root+'/SELFTEST-metadata.json',JSON.stringify(meta,null,2));
await cleanupCandidate(root,env);
console.log('supplement_metadata_drift_rejected_private_absent');
"""
        m.save(script, body.encode())
        m.native_command('supplement-metadata', [shutil.which('node'), str(script)], env,
                         fixture / 'metadata-owner/evidence/native')
        self.assertFalse(private.exists())
        # Metadata process ownership lives separately from the now-idle decoder.
        m.save_json(fixture / 'SELFTEST-ONLY.json', dict(protectedCI=False, protectedKey=False, installable=False,
            key='existing public 01 fixture', binding='in-memory key proof double', verification=report))


class AdaptiveReferenceSearch(unittest.TestCase):
    def test_frontier_does_not_change_main_anchor_or_history(self):
        calls = []
        def measured(old, new, count, seed, salt, **kwargs):
            calls.append((count, seed, salt))
            length = ({8:127, 9:124, 10:132}.get(count, 100+3*count) if salt == 0
                      else {9:129, 10:128}.get(count, 100+3*count))
            return dict(count=count, seed=seed, salt=salt, etu_bytes=length)
        with mock.patch.object(m.encoding, 'TARGET', 128), mock.patch.object(m.encoding, 'measurement', measured), \
                mock.patch.object(m.encoding, 'save_json') as report:
            row = m.encoding.search_adaptive(b'base', bytes(32), 7, 32)
        self.assertEqual((row['count'], row['salt'], row['foundBy']), (10, 1, 'main'))
        self.assertEqual([count for count, _, salt in calls if salt == 1], [9, 10])
        main = report.call_args.args[1]['mainSamples']
        self.assertFalse(any(r['count'] == 8 for r in main))
        self.assertTrue(any(count == 8 and salt == 0 for count, _, salt in calls))

    def test_best_first_frontier_inspects_unmeasured_close_count(self):
        calls = []
        def measured(old, new, count, seed, salt, **kwargs):
            calls.append((count, seed, salt))
            length = 128 if count == 8 and salt == 0 else 100 + 3 * count
            return dict(count=count, seed=seed, salt=salt, etu_bytes=length)
        with mock.patch.object(m.encoding, 'TARGET', 128), mock.patch.object(m.encoding, 'measurement', measured), \
                mock.patch.object(m.encoding, 'save_json') as report:
            row = m.encoding.search_adaptive(b'base', bytes(32), 7, 32)
        self.assertEqual((row['count'], row['salt']), (8, 0))
        self.assertEqual(row['neighborMeasurements'], 1)
        self.assertEqual(len(calls), len(set(calls)))
        self.assertTrue(all(salt == 0 for _, _, salt in calls))
        self.assertEqual(report.call_args.args[1]['neighborMeasurements'], 1)

    def test_nonmonotonic_counts_recenter_after_salt_change(self):
        calls, reports = [], []
        def measured(old, new, count, seed, salt, **kwargs):
            calls.append((count, seed, salt))
            length = 100 + 3 * count if not salt else {9: 133, 7: 126, 8: 128}.get(count, 100 + 3 * count)
            if not salt and count == 10:
                length = 126  # Increasing count from 9 reduces compressed size.
            return dict(count=count, seed=seed, salt=salt, etu_bytes=length)
        with mock.patch.object(m.encoding, 'TARGET', 128), mock.patch.object(m.encoding, 'measurement', measured), \
                mock.patch.object(m.encoding, 'save_json', lambda name, row: reports.append(row)):
            row = m.encoding.search_adaptive(b'base', bytes(32), 7, 32)
        self.assertEqual((row['count'], row['salt']), (8, 1))
        self.assertEqual([c[0] for c in calls if c[2] == 1], [9, 7, 8])
        self.assertEqual(len(calls), len(set(calls)))
        self.assertEqual(row['measurements'], len(calls))
        self.assertEqual(reports[0]['outcome'], 'exact-witness')

    def test_budget_exhaustion_unique_cache_samples_and_safe_diagnostic(self):
        calls, reports = [], []
        def measured(old, new, count, seed, salt, **kwargs):
            calls.append((count, seed, salt))
            return dict(count=count, seed=seed, salt=salt, etu_bytes=127 if count == 0 else 129)
        config = dict(reference=dict(totalBytes=1048576, seed=7, budget=256))
        AREA.mkdir(parents=True, exist_ok=True)
        out = m.checked(Path(tempfile.mkdtemp(prefix='exhausted-', dir=AREA)))
        with mock.patch.object(m.encoding, 'TARGET', 128), mock.patch.object(m.encoding, 'measurement', measured), \
                mock.patch.object(m.encoding, 'save_json', lambda name, row: reports.append(row)), \
                mock.patch.object(m.encoding, 'search', side_effect=AssertionError('old search must not run')), \
                mock.patch.object(m.encoding, 'encode') as encode:
            # source_reference installs its own real report writer. Capture the typed
            # exception at the same adapter boundary used by source-package.
            with self.assertRaises(m.encoding.ReferenceSearchExhausted) as caught:
                m.source_reference(b'a', b'ab', config, out)
            encode.assert_not_called()
        diagnostic = m.failure_diagnostic(caught.exception)
        self.assertEqual(diagnostic['stage'], 'reference-search')
        self.assertEqual(diagnostic['reason'], 'REFERENCE_SEARCH_BUDGET_EXHAUSTED')
        self.assertEqual(diagnostic['measurements'], 256)
        self.assertEqual(len(calls), 256)
        self.assertEqual(len(set(calls)), 256)
        self.assertEqual(sum(seed == 7 for _, seed, _ in calls), 192)
        self.assertEqual(sum(seed == 8 for _, seed, _ in calls), 64)
        report = json.loads((out / 'search-report.json').read_bytes())
        self.assertEqual(report['outcome'], 'budget-exhausted')
        self.assertEqual(report['neighborMeasurements'], 26)
        self.assertEqual(report['neighborLimit'], 26)
        self.assertFalse((out / 'selection.json').exists())
        self.assertFalse((out / 'reference.lzma').exists())
        self.assertFalse((out / 'prepared').exists())
        self.assertNotIn('secret', json.dumps(m.failure_diagnostic(RuntimeError('secret'))))

    def test_endpoint_witness_and_unbracketed_failure(self):
        def measured(old, new, count, seed, salt, **kwargs):
            return dict(count=count, seed=seed, salt=salt, etu_bytes=128)
        with mock.patch.object(m.encoding, 'TARGET', 128), mock.patch.object(m.encoding, 'measurement', measured), \
                mock.patch.object(m.encoding, 'save_json') as report:
            row = m.encoding.search_adaptive(b'a', b'ab', 0, 2)
            self.assertEqual(row['measurements'], 2)
            self.assertEqual(row['count'], 0)
        with mock.patch.object(m.encoding, 'measurement', measured), mock.patch.object(m.encoding, 'save_json') as report:
            with self.assertRaisesRegex(RuntimeError, 'bracket'):
                m.encoding.search_adaptive(b'a', b'ab', 7, 2)
            self.assertEqual(report.call_args.args[1]['outcome'], 'initial-bracket-miss')
        for seed, budget in [(True, 256), (-1, 256), (2**32, 256), (7, True), (7, 257), (7, 1)]:
            with self.assertRaises(ValueError):
                m.encoding.search_adaptive(b'a', b'ab', seed, budget)

    def test_real_measurement_cache_input_and_parameter_identity(self):
        AREA.mkdir(parents=True, exist_ok=True)
        out = m.checked(Path(tempfile.mkdtemp(prefix='cache-', dir=AREA)))
        old, new = b'base bytes', b'target bytes'
        with mock.patch.object(m.encoding, 'OUT', out), mock.patch.object(m.encoding, 'pack', m.pack), \
                mock.patch.object(m.encoding, 'save_json', lambda name, value: m.save_json(out / name, value)):
            row = m.encoding.measurement(old, new, 3, 7, 2, strict_cache=True)
            path = m.checked(out / 'logs/measure-3-7-2.json')
            with mock.patch.object(m.encoding, 'encode', side_effect=AssertionError('must reuse cache')):
                self.assertEqual(m.encoding.measurement(old, new, 3, 7, 2, strict_cache=True), row)
            for old2, new2 in [(old + b'x', new), (old, new + b'x')]:
                with self.assertRaisesRegex(AssertionError, 'input identity'):
                    m.encoding.measurement(old2, new2, 3, 7, 2, strict_cache=True)
            for field, value in [('count', 4), ('seed', 8), ('salt', 3), ('groups', 8),
                                 ('decoded_bytes', 42), ('props_hex', '0300400000'), ('compressed_bytes', -1),
                                 ('etu_bytes', 99), ('raw_sha256', 'z' * 64)]:
                path.write_text(json.dumps(dict(row, **{field: value})), encoding='utf-8')
                with self.subTest(field=field), self.assertRaisesRegex(AssertionError, 'encoding'):
                    m.encoding.measurement(old, new, 3, 7, 2, strict_cache=True)
            path.write_text(json.dumps(row), encoding='utf-8')


if __name__ == '__main__':
    unittest.main()
