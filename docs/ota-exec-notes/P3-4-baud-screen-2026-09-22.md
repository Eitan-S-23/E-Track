# Single-App Baud Screening Preparation

This is development preparation for the user's 115200/460800/921600 comparison,
not measured performance, a production baud selection or independent acceptance.
The root task note is `docs/ota-exec-notes/P3-4-screening-2026-09-22.md` in the
authorized project root. Existing C0/C1/C2/C3 and C3-confirmation evidence remains
unchanged. No device reset/flash/OTA is performed by this source preparation.

## One APK, Immutable Per-Run Inputs

The explicit development workflow candidate `runtime` requires device observation
and a MAC target. It sets `OTA_P34_RUNTIME_CONFIG=true` only in the debug APK.
Production/default builds perform no runtime configuration I/O. Build with the
side-by-side `.p34baud` application ID; do not replace or clear the normal App.

Before launching the stopped debug App, the authorized host installs the bounded
JSON file at its application-support `files/p34-experiment.json`. The App reads
it once before constructing services. Missing/invalid configuration rejects OTA;
it does not fall back to the embedded URL or guess a baud. The file cannot change
an active process's settings. A next run uses a fresh process, not a new APK.
No automatic UI taps or background execution guarantee is added.

Required schema-1 fields:

| Field | Meaning |
| --- | --- |
| runId | Unique simple lowercase run label, up to 48 characters |
| target | MAC matching the observation build's explicit target |
| requestedBaud | 115200, 460800 or 921600; intent, not actual UART evidence |
| reuseGatt / withoutResponse | Boolean sender preferences, fixed for the process |
| firmwareLatestUrl | Credential-free HTTPS endpoint at `/api/public/firmware/latest` |
| packageBytes / packageSha256 | Exact full legal package bytes/hash |
| currentVersionCode / currentImageSha256 | Actual expected baseline raw identity |
| targetVersionCode / targetImageSha256 | Expected upgraded raw identity |

Unknown fields, invalid types, wrong target, unsupported rates, non-increasing
versions, credentials/query/fragment and malformed hashes reject. The configuration
is bounded to 8192 UTF-8 bytes and its original-byte SHA-256 is retained. The
original latest query parameters and upgrade input envelope remain unchanged.
The runtime URL changes only the approved diagnostic request destination.

`OTA_EXPERIMENT` is an original App-produced record containing the run ID,
configuration hash, requested profile and package/device identities. It omits URL
credentials and records only the endpoint host. It is stored at startup and before
an admitted upgrade. The immutable original upgrade-start envelope still binds
actual package/current/target fields. A mismatched runtime profile blocks BEGIN.
The observation extractor admits this explicit new prefix without weakening
footer, identity, credential, loss or completed-upgrade checks.

The APK's embedded `.invalid` endpoint is intentionally unusable: actual endpoint
selection requires a valid per-run configuration. This avoids rebuilding an APK
whenever an accountless tunnel expires. APK metadata remains build intent; live
configuration records and MCU readback are required before a physical test.

## Matched Hardware Group

The first screen has three rates, one transfer each after admission, with identical
sender choices, package bytes, MCU code/pump settings, MTU request, protocol guards,
foreground requirement and capture route. New diagnostics need a separately bound
firmware/package/recovery group; old 3.2.7 does not acquire runtime controls from
this App. 921600 communication, synchronized startup after upgrade and a supported
recovery route are prerequisites, not substitutes for its actual OTA measurement.

Report BEGIN-to-END ACK, apply and reconnect separately. UART RX/queue/overflow,
pump spacing, ACK TX and staging erase/program/verify/journal statistics are pending
firmware work, not zero-cost phases. PHY/connection parameters stay unknown unless
actually observed. Preserve 128-byte DATA, 4 KiB staging, advertised credit limits,
CRC/SHA, durable confirmation, retry/timeout and grounded RTS/CTS constraints.

Host and both-platform Flutter validation precede explicit debug APK dispatch.
No local Flutter/Gradle build, mainline commit/push, merge, release or deployment
is included. Hardware execution is prepared and source-bound separately by root.
