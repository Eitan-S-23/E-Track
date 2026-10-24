# P38-RUNTIME-ADMISSION-02

D1's exact record command passed the v2 frozen gate, then failed at the
App-origin runtime stamp check before publishing ready.json. Its original
exit 1, raw stderr, result, 22-record events prefix and healthy counters are
preserved. upgradeStarts=upgradeEnds=0. No start notification was sent and no
OTA, MCU write/reset, or D2/D3/final command occurred. Private ADB and logcat
closed with no cleanup errors; the read-only ADB key hash is unchanged.

Root cause is the preparation request, not a demonstrated product defect:
ci-request-001 selected ota_link_candidate=baseline. Tools/flutter/dev_apk.py
ota_link_candidate returns no defines for baseline; only runtime enables
OTA_P34_RUNTIME_CONFIG. OtaExperimentRuntime in ota_experiment_config.dart
therefore ignores files/p34-experiment.json in this APK. main.dart emits the
expected stamp only when that runtime config exists in memory. Successful
file write/readback and GET_INFO queries did not prove runtime consumption.

Preserve the runtime stamp gate. Request ota_link_candidate=runtime on the
same delivery commit, independently check actual build metadata/defines,
signature and installed bytes, and require the App's stamp before any OTA.
The schema-1 runtime retains baseline GATT/write/window/batch policy; do not
select runtime-pipeline, enable optimizations, or change product code.

Operator sequencing issue: an auxiliary host lifetime check rejected the
remaining network window, but the subsequent read-only collector launcher
was called without branching on that exit. No user start was allowed. Future
launches must be conditional on every prerequisite exit, not merely ordered
after it. network-006 later reached its original finite deadline and closed;
do not extend/reuse its expired endpoint or rewrite this contract.

The result is EVIDENCE_GAP with a preparation/harness finding. The validator
only accepts approved command exit codes in matrix.commands, so the failed
exit is bound as explicit raw failed-command evidence, not falsified as exit
0. Software/admission commands succeeded; no physical criterion is PASS.
