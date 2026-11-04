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
            with mock.patch.object(m.encoding, 'search', return_value=row):
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


if __name__ == '__main__':
    unittest.main()
