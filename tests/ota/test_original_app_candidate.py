"""Credential-free regressions for the original-App APK identity guard."""
import importlib.util
import io
from pathlib import Path
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('original_candidate', ROOT / 'Tools/flutter/original_candidate.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def artifact(drop=None, extra=b'', duplicate=False):
    stream = io.BytesIO()
    required = [m.PUBLIC_ORIGIN + '/api/public/latest', m.PUBLIC_ORIGIN + '/api/public/firmware/latest',
                m.PUBLIC_KEY, 'adaptive-v2-candidate', '/api/public/version-inventory']
    with zipfile.ZipFile(stream, 'w') as archive:
        for abi in m.ABIS:
            archive.writestr('lib/' + abi + '/libapp.so', '\n'.join(v for v in required if v != drop).encode() + extra)
        if duplicate:
            archive.writestr('lib/x86_64/libapp.so', b'not-an-original-abi')
    return stream.getvalue()


class OriginalAppCandidateTests(unittest.TestCase):
    def setUp(self):
        self.badging = "package: name='com.wen.gaia.gaia' versionCode='103' versionName='1.0.77'\nnative-code: 'armeabi-v7a' 'arm64-v8a'\n"
        self.signatures = 'Number of signers: 1\nV2 Signer: certificate SHA-256 digest: ' + m.SIGNER + '\n'

    def inspect(self, raw=None, badging=None, signatures=None):
        return m.inspect_apk(raw or artifact(), badging or self.badging, signatures or self.signatures, ('1.0.77', 103))

    def test_original_identity_and_both_libraries(self):
        self.assertEqual(len(self.inspect()['libraries']), 2)

    def test_wrong_signer(self):
        with self.assertRaises(ValueError):
            self.inspect(signatures=self.signatures.replace(m.SIGNER, '9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579'))

    def test_test_package_suffix(self):
        with self.assertRaises(ValueError):
            self.inspect(badging=self.badging.replace(m.PACKAGE, m.PACKAGE + '.test'))

    def test_wrong_version(self):
        with self.assertRaises(ValueError):
            self.inspect(badging=self.badging.replace("versionCode='103'", "versionCode='102'"))

    def test_missing_compiled_contract(self):
        for value in [m.PUBLIC_KEY, 'adaptive-v2-candidate', '/api/public/version-inventory', m.PUBLIC_ORIGIN + '/api/public/latest']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.inspect(raw=artifact(drop=value))

    def test_test_endpoint_rejected(self):
        with self.assertRaises(ValueError):
            self.inspect(raw=artifact(extra=b'e-track-firmware-p41-public.pages.dev'))

    def test_unexpected_abi(self):
        with self.assertRaises(ValueError):
            self.inspect(raw=artifact(duplicate=True))

    def test_version_parser(self):
        self.assertEqual(m.version('version: 1.0.77+103\r\n'), ('1.0.77', 103))
        for value in ['version: 1.0.75+101', 'version: 1.0.77+0103', 'version: 1.0.77', 'version: 1.0.77+103\nversion: 1.0.78+104']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                m.version(value)


if __name__ == '__main__':
    unittest.main()
