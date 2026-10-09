# Shared Agent Records

Project-wide entry for all E-Track agents and components. Rules live in the
[collaboration contract](../agent-collaboration-contract.md), not in a task cache.
This index and its topic records are operational history, not acceptance inputs.

| Topic | Scope | Record |
| --- | --- | --- |
| PROJECT-WORKFLOW | All components, roles and worktrees | [Project workflow decisions](project-workflow.md) |
| PROJECT-TOOL-REUSE | Existing tools first, evidenced custom-tool exceptions and stopping unnecessary tool expansion; all agents | [PROJECT-04: group16 lesson](project-workflow.md#project-04-reuse-tools-before-replacing-them) |
| PROJECT-CANDIDATE-INSTALL | Prefer standard J-Link for candidate installation after state checks; reserve OTA for required observations, not redundant provisioning | [PROJECT-05: J-Link installation before OTA measurement](project-workflow.md#project-05-j-link-installation-before-ota-measurement) |
| PROJECT-USER-NOTIFICATIONS | Manual real mentions only for continued operations needing an out-of-chat action without a reply; chat authorization/decisions use the automatic completion reminder | [PROJECT-06: Mid-task reminders, not duplicate final notifications](project-workflow.md#project-06-only-manual-mentions-for-mid-task-blockers) |
| P3-4-PROGRESS | P3-4 operational status, next work, transfer/install timing and evidence; owner: Codex root, original card ownership unchanged; local evidence and remote delivery remain separate | [P3-4 project progress](../../P3-4项目进度表.md) |

Add one row when a durable cross-agent handoff is needed. Link an existing task
note instead of duplicating its evidence. Include an exact source commit when the
record has not yet reached main; do not use a machine-private path as its only
address. The topic owner updates the same stable IDs and reports integration.
