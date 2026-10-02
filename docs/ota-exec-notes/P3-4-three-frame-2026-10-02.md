# P3-4 Three-Frame Development Prototype

Base: installed radio/recorder APK source24ce23842d80241731eee335e60688447a55380b.
Scope: default-off transport constructor option `dataBatchFrames: 3`. The service
continues to construct the default single-frame transport; no runtime config,
APK installation, firmware change or hardware measurement is included here.

Measured motivation: combined radio transfer293036B in26.006960s,
11.003515KiB/s; installation/reconnect22.155833s. Original report SHA-256
5d667bf1239320546c44feaa7cfc47f8d9ee8139ff3d1ed2fc4ab7f7fd1f1577.
App partition:15.907716s DATA writes,9.199132s last-send-to-durable,
zero inferred full-credit waits. Geometry shortlist: three full DATA frames
occupy426 bytes, hence two writes at244-byte GATT payload, not three.

## Invariants

- Reserve no more than actual free credit, three frames and the current block.
- Preserve each DATA frame, CRC, sequence, offset, retry and SHA validation.
- Register a frame for ACK association immediately before dispatching the chunk
  containing its last bytes, not when reserving its sequence number.
- Record each frame's send-end after its completing chunk settles. Original
  early ACK samples remain invalid rather than acquiring invented latency.
- Retain one stream owner and the existing timeout/late-write poison machinery.
- On cancellation, finish only the currently partial frame. Do not dispatch the
  remainder of the planned batch. Never insert ABORT into a partial DATA frame.
- Retransmissions remain on the existing single-frame path.

## Development Verification

The existing complete transport tests must remain green. New cases cover default
geometry, three-frame geometry, MTU23/145/247, windows1/2/3/4/28, partial-frame
cancellation, reserved-frame forged ACKs, timeout poisoning and ordinary resume.
CI uses the scoped development workflow on `dev/flutter/p3-4-three-frame-20261002`.
This document is not an independent acceptance verdict or a measured speedup.

## Before Hardware

Do not enable this option from App runtime configuration yet. First finish
sender failure-matrix review and add a versioned observation contract: the old
one-GATT-write-per-segment timing partition rejects batched samples by design.
Prepare configuration, recorder, exporter and analyzer together before requesting
another same-signer development APK. Retain verified firmware30249 meanwhile.
