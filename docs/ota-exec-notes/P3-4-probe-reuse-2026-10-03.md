# P3-4 Bounded Reboot INFO Reuse

## Scope

Checks-only development, based on installed APK source
`70a41c848099b3051a5244abaae899bd9d6027d5`. No APK installation, firmware
transfer, release, Boot replacement or mainline change is part of this batch.
The original APK source checkout and root worktree/index remain unchanged.

## Evidence And Hypothesis

Verified UI-cadence trial 30253 -> 30254 transferred 293103 bytes in
20.528829 seconds (14.277629 KB/s); END ACK to target identity was21.232236
seconds. Zero DATA retransmits, invalid ACK samples or capture losses.
Original strict report SHA256:
`3765f27be89a02743e8b5887cf8c536acabc46f7e1f7a159712f78d03bc08a32`.
Compared with the prior CRC header-only successor, the observed transfer gain
is3.639273%, not yet a repeated stability result or a full-program apply bound.

The prior byte-bound HCI capture showed successful post-END connections followed
by unanswered INFO and local teardown before later successful verification.
This motivates retaining one valid fresh binding for up to three INFO calls.
It does not prove when the MCU became ready or promise a20-second result.

## Contract

- Schema6 requires boolean `reuseRebootInfoLink`; schema1-5 default false.
- The initial post-END disconnect and fresh exact discovery remain mandatory.
- Only a settled `TIMEOUT` is eligible for another INFO call. Write timeout,
  malformed/unknown errors and valid old identity do not gain a new retry path.
- At most three calls per binding, with the existing configured probe interval.
  Existing transport poison/resynchronization guards and outer total/attempt
  deadlines are unchanged; the helper never abandons a Future and retries it.
- Check cancellation/abandonment, physical link generation and GATT binding token
  before every call and after every reply. Late replies cannot verify a target.
- A valid old identity retires the probe as before; different hardware fails.
  Success still requires exact target version and raw image hash.
- Cleanup must not disconnect a replacement binding on the same link generation.

## Verification

Development CI runs analysis and the full Flutter test suite on Linux/Windows.
Tests cover opt-in/off discovery counts, persistent timeouts, old identity,
hardware mismatch, outer abandonment, late replies, invalid ownership and
non-retryable errors. This is self-test, not hardware performance acceptance.
Before any future device trial, bind schema6 in the host admission route, use
the same certificate/package, and prepare both original collectors and readback.
