# Project Workflow Decisions

Owner: root session. User decisions: 2026-09-22. Scope: entire E-Track project.
Normative sources: [collaboration contract](../agent-collaboration-contract.md)
and [device experiment policy](../device-experiment-policy.md).

## PROJECT-01: Shared Rules Are Project-Wide

DECIDED. The first skill/feedback delivery was commit
`73a3563af99ac5a9e0931126be1bc508490cb049` on
`docs/flutter-debug-skill-feedback-20260922`, with working files only in a P3-4
worktree. Although its wording was generic, that was not project-wide integration.

Direction: publish root AGENTS routing, the generic contract, this shared index
and the [Flutter debugging skill](../../.agents/skills/e-track-flutter-debug/SKILL.md)
on main. Root and app CLAUDE files already import AGENTS; do not fork duplicate rules.
Existing agents/worktrees must receive the published revision before new work.
Keep task state/evidence outside normative acceptance profiles and preserve dirty
product changes when integrating only governance files.

Verification: resolve root/app entry points and shared links, validate the skill,
and run profile-ownership plus governance CI regressions. Root owns integration;
every recipient owns loading that revision, not rediscovering prior rejected routes.

## PROJECT-02: Task-Bounded OTA Work, Not Tiny Quotas

DECIDED. Replace agent-created per-OTA/per-reset caps with the finite task matrix
and risk-based stopping conditions in the device policy. The user explicitly
requested less restrictive execution and continuation until real intervention.
This is not a GitHub storage/billing change or an unlimited hardware allowance.

Direction: plan candidate preparation and screening together, act serially on the
one device, and automatically perform justified in-scope recovery/verification.
Preserve actual attempts and resolve uncertain outcomes before repeating them.
Do not modify historical ledgers or treat collector repair as a reason to redo OTA.

## PROJECT-03: Equivalent P3-4 Comparison State

DECIDED, conditional execution. Returning to 3.2.6 is unnecessary for coding,
host tests or all possible link diagnostics. It is necessary for a controlled
repeat of the existing admitted 30206-to-30207 FULL package: current 30207 is not
an equivalent initial version/BCB/staging state. The user authorizes that return
if needed. Root must first establish a supported complete-state restoration,
not just overwrite App or invent BCB bytes. Restore only when the next prepared
experiment needs it, and retain a verified target at the end.

Known evidence: the 284643-byte baseline completed at 115200 with approximately
1.038 KiB/s; discovery and platform-write timing dominate the observed App path.
That package is not the 1 MiB reference and MCU UART/staging timing is not yet
isolated. 115200 is a control, not a selected ceiling or proof higher baud cannot help.

Prepared sender candidates are in commit
`fbc3b5aae468e9ab382ac018c1247de43d890491` on
`dev/flutter/p3-4-batched-link-candidates`, documented at
`docs/ota-exec-notes/P3-4-batch-optimization-2026-09-22.md` in that commit.
Both-host development tests passed; candidate APKs and optimized physical
throughput were not produced by that checks-only run. These source-pinned task
facts are a handoff, not independent acceptance or a mainline product merge.
