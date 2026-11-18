# MCU Companion Candidate Preparation

## Scope

The owner requested local preparation only and will perform the final Git push.
No push, Actions dispatch, Cloudflare upload/registration, channel publication,
phone operation or MCU operation was performed during this preparation.

- Local branch: `prep/firmware-companion-3.3.30`.
- Worktree: `.worktrees/firmware-companion-candidate-20261118`.
- Fresh remote candidate base: `a977c848e03a2798a7b5c46319cd126a292395b4`.
- Reviewed companion source: `3028a0570bdbc1ed115b8de92bfde47933d1dd4c`.
- Companion delta base: `278042636699067dd95c61160d2e1900d9dcbe33`.
- New firmware identity: `3.3.30` / `30330`, following candidate `3.3.29`.

Only the companion MCU/paired-simulator changes, six source-bound host test files,
the firmware release request and this note are included. App `1.0.82+108`, the
existing publishing workflow, Boot, OTA implementation and resource bindings are
preserved. The existing companion control contract already matches the reviewed
source and is not replaced.

The three overlapping firmware files were merged against the recorded delta
base. Existing long-filename/scrolling fixes and BLE V2-only ACK handling remain.
The sole textual conflict was concurrent header additions in `FirmwareUpdate.cpp`;
both the existing file-browser header and the two companion headers are retained.

## Local Validation

- Companion control: 24 tests passed.
- Production-method safety/consent/recorder tests: 18 tests passed, including
  the original unsafe-boundary negative controls.
- Main-menu encoder/Back regression: 1 test passed, retaining original-red proof.
- Original-candidate and protected-build-profile checks: 74 tests passed.
- Scoped byte comparison and whitespace checks pass.

These are development checks, not formal acceptance or physical OTA evidence.
The synthetic keyed-build case is not a native firmware build. Fresh GCC firmware
compilation, package verification and backend ingestion remain for the owner's
Actions run. D0-D5 and whole-card acceptance are not closed by this preparation.

The first local candidate check had two Windows CRLF extraction failures. Only
the local App workflow template's line endings were formatted to its existing Git
LF bytes; no template content, workflow or assertion changed. The failure and
the complete green rerun are retained separately under
`.cache/firmware-companion-prep-20261118/` in the primary checkout.

## Final Owner Push

From any shell on this machine:

```sh
git -C "D:\github\my\E-Track\.worktrees\firmware-companion-candidate-20261118" push origin HEAD:refs/heads/release/candidates
```

Do not add force-push flags. This new versioned push is expected to trigger
`Original Admin Candidates`: firmware required, App not required. Its existing
firmware environment may wait for owner approval, then compiles/packages/verifies
and uploads/registers the normal full/recovery candidate. Stable/Beta promotion
and selected delta generation remain operator-controlled.

Manual dispatch of this workflow is checks-only; it is not a substitute for the
versioned push. After pushing, verify the exact pushed SHA, successful firmware
job, `3.3.30` candidate identity and registration receipt before calling it delivered.
