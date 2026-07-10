# VCDIFF Compatibility Runbook

This document records the `v1.0.13` through `v1.0.16` incremental-update failure and the release rules that prevent it from recurring.

## Scope / Trigger

Use this runbook when touching any of these areas:

- Android incremental update decoding in `lib/services/app_update_service.dart`
- The local patched package in `third_party/vcdiff_decoder`
- VCDIFF generation in `.github/scripts/create_vcdiff_patch.py`
- GitHub Actions release metadata in `.github/workflows/build.yml`
- Cloudflare D1/R2 candidate publishing for Android APK updates

Do not use local Flutter, Gradle, APK packaging, or signing commands to validate release artifacts. Use GitHub Actions and remote release assets.

## Incident Summary

`v1.0.14+40` generated a small `39 -> 40` VCDIFF patch and served it correctly from R2, but the Android client failed during local synthesis with:

```text
InvalidFormatException: Near cache slot 1 is uninitialized
```

That was not a Cloudflare, R2, CDN, or hash problem. It was a client decoder compatibility problem.

The first fix removed the top-level `VCD_APPHEADER` from xdelta3 output. That fixed one incompatibility, but it did not prove that the Dart decoder could execute all xdelta3 address modes. The real client still failed because the upstream `vcdiff_decoder` package mishandled VCDIFF address caches.

## Root Cause

xdelta3 generated standard VCDIFF that used near/same address cache modes. The upstream Dart `vcdiff_decoder` package was not compatible enough for these APK deltas:

- It treated a near cache value of `0` as "uninitialized". In RFC 3284, near cache entries start at `0`, and `0` can be a valid base address.
- Its same-cache sizing was wrong for the RFC default cache shape. The logical same cache has `3` modes and `3 * 256` entries.
- Therefore "patch downloads from R2", "patch SHA matches", and "no VCD_APPHEADER" were necessary but not sufficient verification.

The fix was to vendor a Trace-local patched decoder at `third_party/vcdiff_decoder` and point `pubspec.yaml` / `pubspec.lock` at that path package.

## Version Boundary

The safe VCDIFF source boundary is:

```text
TRACE_VCDIFF_MIN_SOURCE_VERSION_CODE=41
```

Meaning:

- `versionCode <= 40` clients must not receive VCDIFF patches. They contain the buggy decoder and need one full APK transition.
- `v1.0.15+41` is the full-transition repair release. It contains the patched decoder and intentionally has no patches from older versions.
- `v1.0.16+42` is the first post-repair incremental test release. It contains `41 -> 42` VCDIFF only.
- Do not lower the default in `.github/workflows/build.yml` unless you first prove the installed source clients can decode the generated patch.

## Required Contracts

### VCDIFF File Header

Generated VCDIFF files must start with:

```text
d6 c3 c4 00 00
```

Byte layout:

- Bytes `0..2`: VCDIFF magic `d6 c3 c4`
- Byte `3`: VCDIFF version, expected `00`
- Byte `4`: header indicator, expected `00`

The `VCD_APPHEADER` flag is bit `0x04` on byte `4`. It must be absent before upload.

### CI Generation

`.github/scripts/create_vcdiff_patch.py` owns VCDIFF generation and normalization:

```text
xdelta3 -e -S none -s <old.apk> <new.apk> <patch.vcdiff>
strip_vcdiff_app_header(...)
assert_vcdiff_without_app_header(...)
```

`.github/workflows/build.yml` must keep:

```bash
vcdiff_min_source_version_code="${TRACE_VCDIFF_MIN_SOURCE_VERSION_CODE:-41}"
```

The workflow should generate patches only for source releases at or above that version code.

### Client Decoder

The Android app must use:

```yaml
vcdiff_decoder:
  path: third_party/vcdiff_decoder
```

Do not silently switch back to `vcdiff_decoder: ^0.1.0`. That reintroduces the address-cache failure.

## Validation Matrix

| Scenario | Expected Result | Required Check |
| --- | --- | --- |
| Client `39` or `40` asks latest after `v1.0.15` | Update available, no patch, full URL present | Public latest has `patches` count `0` and `fullDownloadUrl` set |
| Client `41` asks latest after `v1.0.16` | Update available with `41 -> 42` VCDIFF | Public latest returns patch from versionCode `41` |
| Client `42` asks latest after `v1.0.16` | No update | Public latest returns `NO_UPDATE` |
| Patch download | Served from R2, SHA matches | `X-Trace-Asset-Source: r2` and SHA-256 equals manifest |
| Patch header | Decoder-compatible VCDIFF | First five bytes `d6 c3 c4 00 00`, byte `4 & 0x04 == 0` |
| D1 candidate | Patch metadata is registered only for safe sources | `patches.from_version_code >= 41` |

## Good / Base / Bad Cases

Good:

```text
v1.0.15+41: full-transition repair release, zero VCDIFF patches from old clients.
v1.0.16+42: first repaired incremental test, one patch from 41 to 42.
```

Base:

```text
GitHub Actions builds APK, creates Release, uploads APK/manifest/patch to R2, registers D1 candidate.
Operator publishes candidate to stable/beta only after D1/R2/public latest verification.
```

Bad:

```text
v1.0.14+40: R2 and SHA were correct, but installed client still failed with "Near cache slot ... is uninitialized".
```

Do not treat a small patch size as proof that incremental update works.

## Verification Commands

Check latest workflow:

```powershell
gh run list --repo Eitan-S-23/Trace --workflow build.yml --branch main --limit 5 --json databaseId,status,conclusion,headSha,displayTitle,createdAt,url
```

Check release assets:

```powershell
gh release view v1.0.16 --repo Eitan-S-23/Trace --json tagName,targetCommitish,assets,publishedAt
```

Check D1 release and patch records:

```powershell
Set-Location D:\github\my\bluetooth_flutter_Trace\cloudflare\update-service\worker

node node_modules\wrangler\bin\wrangler.js d1 execute trace-update-staging --env staging --remote --command "SELECT id, release_tag, version_code, state, run_id FROM releases WHERE release_tag='v1.0.16';"

node node_modules\wrangler\bin\wrangler.js d1 execute trace-update-staging --env staging --remote --command "SELECT p.patch_format, p.from_version_code, a.file_name, p.patch_size_bytes FROM patches p JOIN release_assets a ON a.id=p.asset_id WHERE p.to_release_id='rel_trace_android_v1_0_16' ORDER BY p.from_version_code;"
```

Check patch header:

```powershell
$dir = Join-Path $env:TEMP 'trace-vcdiff-check'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
gh release download v1.0.16 --repo Eitan-S-23/Trace --pattern '*.vcdiff' --dir $dir --clobber
Get-ChildItem -LiteralPath $dir -Filter '*.vcdiff' | ForEach-Object {
  $bytes = [System.IO.File]::ReadAllBytes($_.FullName)
  [pscustomobject]@{
    Name = $_.Name
    FirstFiveBytes = (($bytes[0..4] | ForEach-Object { $_.ToString('x2') }) -join ' ')
    HeaderByte = ('0x{0:x2}' -f $bytes[4])
    HasAppHeader = (($bytes[4] -band 0x04) -ne 0)
  }
}
```

Publish a normal repaired incremental candidate:

```powershell
Set-Location D:\github\my\bluetooth_flutter_Trace
.\cloudflare\update-service\scripts\publish-staging-release.ps1 -ReleaseTag v1.0.16 -Channels stable,beta -SkipBackfill -Yes -ActorEmail codex-staging -VerifyFromVersionCode 41
```

Publish a full-transition repair candidate with no patches:

```powershell
.\cloudflare\update-service\scripts\publish-staging-release.ps1 -ReleaseTag v1.0.15 -Channels stable,beta -SkipBackfill -SkipVerify -Yes -ActorEmail codex-staging
```

Then manually verify that old clients see no patches and do see a full download URL.

## Wrong vs Correct

Wrong:

```text
The patch is 10 KB, served from R2, and has a matching SHA, so incremental update is fixed.
```

Correct:

```text
The patch is served from R2, SHA matches, has no VCD_APPHEADER, and is only offered to clients whose installed version includes the patched decoder. Public latest and D1 confirm the source version boundary.
```

Wrong:

```text
Lower TRACE_VCDIFF_MIN_SOURCE_VERSION_CODE so old clients can receive small patches.
```

Correct:

```text
Old clients use one full APK transition. Only clients at versionCode 41 or newer receive VCDIFF.
```

Wrong:

```text
Replace an existing GitHub Release asset under the same tag to retry quickly.
```

Correct:

```text
Bump pubspec.yaml, create a new tag, let GitHub Actions create a new immutable release, then publish the new D1 candidate.
```

## Operational Notes

- `Node fetch failed ... trying curl fallback` from the publish wrapper can be benign if the script completes and prints verified stable/beta results.
- A publish wrapper failure after channel publication can still have changed D1 channel pointers. Always query `channels` before retrying.
- `HEAD` is not a reliable verification method for signed download endpoints. Use GET verification or the wrapper's download check.
- Keep `TRACE_UPDATE_SERVICE_URL` as the Worker URL for CI registration and `TRACE_PUBLIC_UPDATE_SERVICE_URL` as the Pages URL compiled into clients.
- If an installed client reports `Near cache slot ... is uninitialized`, do not debug Cloudflare first. Check whether that client version predates the patched decoder.
