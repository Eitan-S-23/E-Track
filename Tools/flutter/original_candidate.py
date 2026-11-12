"""Original-App candidate identity and full-only manifest, with no build fallback."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'com.wen.gaia.gaia'
SIGNER = '3cecee6330a930e020b454b6d4a79568f4494ca324ae7bcf2c1914e51b04ab47'
PUBLIC_KEY = 'TZNxTj9lyvlyE87On6hS1O73NO8QMxYh5/ahv0WoqPw='
PUBLIC_ORIGIN = 'https://trace-update-public-staging.pages.dev'
ABIS = {'arm64-v8a', 'armeabi-v7a'}


def version(text):
    matches = re.findall(r'^version:\s*((?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*))\+([1-9]\d*)\s*$', text, re.M)
    if len(matches) != 1 or not 102 <= int(matches[0][1]) <= 2100000000:
        raise ValueError('Expected integrated App version 102 or newer')
    return matches[0][0], int(matches[0][1])


def inspect_apk(raw, badging, signatures, expected):
    name, code = expected
    package = re.search(r"^package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'", badging, re.M)
    if not package or package.groups() != (PACKAGE, str(code), name):
        raise ValueError('APK package or version differs from the exact source')
    abis = re.search(r'^native-code:\s*(.*)$', badging, re.M)
    if not abis or set(re.findall(r"'([^']+)'", abis[1])) != ABIS:
        raise ValueError('Expected both original ARM ABIs, without additional ABIs')
    certificates = set(re.findall(r'certificate SHA-256 digest:\s*([0-9a-fA-F]{64})', signatures))
    if not re.search(r'^Number of signers: 1\s*$', signatures, re.M) or {v.lower() for v in certificates} != {SIGNER}:
        raise ValueError('APK is not signed solely by the original App certificate')
    required = [PUBLIC_ORIGIN + '/api/public/latest', PUBLIC_ORIGIN + '/api/public/firmware/latest',
                PUBLIC_KEY, 'adaptive-v2-candidate', '/api/public/version-inventory']
    libraries = []
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate APK archive entry')
        expected_libraries = {'lib/' + abi + '/libapp.so' for abi in ABIS}
        if {member for member in names if member.endswith('/libapp.so')} != expected_libraries:
            raise ValueError('Unexpected App library set')
        for member in sorted(expected_libraries):
            info = archive.getinfo(member)
            if info.file_size > 100 * 1024 * 1024:
                raise ValueError('Oversized App library')
            library = archive.read(member)
            if not all(value.encode() in library for value in required):
                raise ValueError('Original endpoints, trusted key, BLE V2 or inventory code missing: ' + member)
            if b'e-track-firmware-p41-public.pages.dev' in library:
                raise ValueError('Isolated historical test endpoint found in original-App candidate')
            libraries.append(member)
    return dict(versionName=name, versionCode=code, package=PACKAGE, signerSha256=SIGNER,
                sha256=hashlib.sha256(raw).hexdigest(), sizeBytes=len(raw), libraries=libraries,
                originalBackend=True, bleV2Only=True, inventory=True)


def checked(value):
    path = Path(value)
    path = (path if path.is_absolute() else ROOT / path).resolve()
    path.relative_to(ROOT)
    return path


def save(path, value):
    path = checked(path)
    checked(path.parent).mkdir(parents=True, exist_ok=True)
    with checked(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('verify', 'manifest'))
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--badging', type=Path)
    parser.add_argument('--signatures', type=Path)
    args = parser.parse_args()
    out = checked(args.out)
    if out.exists():
        raise ValueError('Preserve the existing candidate output')
    apk = checked(args.apk)
    expected = version((ROOT / 'app/bluetooth_flutter_Trace/pubspec.yaml').read_text(encoding='utf-8'))
    if args.action == 'verify':
        if not args.badging or not args.signatures:
            parser.error('Native aapt and apksigner reports are required')
        result = inspect_apk(apk.read_bytes(), checked(args.badging).read_text(encoding='utf-8'),
                             checked(args.signatures).read_text(encoding='utf-8'), expected)
    else:
        name, code = expected
        result = dict(schemaVersion=1, platform='android', versionName=name, versionCode=code,
                      releaseTag='v' + name, apkAssetName=apk.name,
                      apkSha256=hashlib.sha256(apk.read_bytes()).hexdigest(), apkSize=apk.stat().st_size, patches=[])
    save(out, result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
