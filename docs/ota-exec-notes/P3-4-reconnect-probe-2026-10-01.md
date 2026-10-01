# P34 Reconnect Cadence Candidate

Development-only, based on installed diagnostic APK source
`aea62c6490a529a47f74dde86669dc3e3c7605ff`. No release, Boot change or successful
OTA replay is included. The canonical project governance was read from the
active root; this validation branch retains the installed APK's runtime-profile
workflow extensions and current development artifact rules.

## Evidence And Hypothesis

The completed30242 screen retained the exact image and confirmed state. Block
erase reduced FULL/backup commands to32/33 and their combined MCU ticks to13253,
but App installation/reconnect remained34.914724s. Four reconnect rounds included
two failed INFO waits of10.036514s/10.012001s, followed by a successful0.843295s
INFO. The old header-only30240 screen also needed four rounds. This motivates
testing cadence; the waits overlap firmware work and are not all recoverable.

## Contract

`OtaExperimentConfig.parse` adds an exact schema3 field set: all schema2 fields
plus integral `rebootInfoTimeoutMs` in500..10000 and `rebootProbeIntervalMs` in
100..3000. Schema3 is full-transfer-only with prefix0. Missing, extra, fractional,
wrong-type and out-of-bound fields fail closed. Schema1/2 expose null cadence
overrides and retain existing behavior. Disabled runtime configuration never
loads these settings.

The candidate physical profile is2000ms INFO and500ms interval. The immutable
configuration captured at upgrade admission supplies only post-END probing.
Normal INFO, transport recovery, data writes, credit, durable state and firmware
bytes are unchanged. The180s total window,20s per-round cap,5s disconnect bound,
abandonment/cancellation checks, generation-bound notification ownership and
exact hardware/version/full-hash verdict remain intact. A short ordinary INFO
timeout does not shorten the transport's poisoned-write recovery budget.

`OTA_EXPERIMENT` records the requested schema3 cadence with the config hash.
These fields are requests, not proof of achieved duration. No new wire command
or firmware capability is introduced.

## Verification

Configuration tests cover valid endpoints, old defaults, requested-value output,
wrong identity and malformed/prefix input. Real service tests suppress one
post-END INFO response, require a subsequent verified target inside the overall
window, and check the requested wait between INFO requests. Separate cases keep
schema2's ordinary wait and reject old or different-hardware identities under
schema3. Existing timeout, cancellation, delayed callback and recovery tests
remain required. CI results are pending; no timing improvement is claimed.

After both-host development checks, request a diagnostic APK explicitly. Before
physical use, bind its exact hash, add host schema3 observation validation and a
legal header-only successor from retained30242, then run one foreground screen.
Do not install an unverified APK or replay30242 to obtain a new trace.
