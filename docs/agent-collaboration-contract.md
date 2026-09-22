# Actionable Agent Collaboration

## Scope

Applies project-wide: firmware, Flutter, simulator, cloud services, tooling and
governance, in every task and worktree. It covers implementation, review,
acceptance and root agents, not just OTA or P3-4. Use the existing task note or
issue list; do not create an approval workflow for every question. This contract
does not change product criteria, operating permissions or acceptance independence.

The responder owns reducing uncertainty enough for the recipient to act. A bare
"check the spec", "improve robustness", "not sufficient" or "try again" is not
an answer. A document link alone is sufficient only when it points to an already
resolved, directly applicable decision and states how it applies here.

## Shared Storage And Delivery

- Rules live in this root-level document. The shared directory is
  [docs/agent-collaboration/](agent-collaboration/index.md), with a single index
  linking topic records. Use it for project-wide decisions and cross-task lessons;
  keep task-specific findings in the existing task note and link that note from
  the index when another agent needs it. Do not duplicate a task's full evidence.
- Each handoff identifies the topic/finding ID, owner, relevant commit or artifact,
  facts versus hypotheses, rejected routes, next action and verification oracle.
  Update the same record by ID; preserve superseded decisions and their reasons.
  Chat carries notifications, not the only copy of a decision.
- Deliver reusable rules and the index to `main` under actual commit/push authority.
  A private `.cache` path or an unmerged task branch alone is not project delivery.
  An unmerged handoff must name its branch, exact commit and repository-relative
  path so another agent can read `git show COMMIT:PATH`; label it pending integration.
- At task entry and handoff, read the project's current rules and applicable index
  entries. For an older worktree, the root session supplies the published revision;
  read it from Git or the authorized project root before new work. Do not silently
  reinterpret a frozen acceptance bundle using newer governance.
- Each worktree still has its own writable boundary. If the canonical index is
  outside it, send the scoped record/commit to the root session for integration;
  do not write outside that boundary, mutate another agent's index, or copy their
  unrelated source changes. Active agents need a handoff/reload notification; a
  Git push does not refresh their already-loaded context.
- The shared index and topic records are operational history, not normative rules
  or executable runners. Keep them outside acceptance input profiles, like the
  task board. Put normative changes here or in the relevant governed contract;
  a task note cannot grant permissions or redefine acceptance criteria.

## Question Packet

Keep a stable question/finding ID and include only decision-relevant information:

- Task, role, revision/artifact and exact decision needed.
- Expected behavior/invariant and actual observation, with file/function or raw
  evidence anchors; distinguish observation from hypothesis.
- What was already attempted and why rejected paths must not be repeated.
- Recommended option, credible alternative if useful, and affected scope/cost.
- Current authorization, experiment plan and output boundary when a proposed action has
  external/device effects. State which independent safe work can continue.

Missing context is not grounds to bounce the entire task back. Ask for the smallest
missing observation and name who will obtain it using an available approved route.

## Response Contract

Use `DECIDED`, `NEED_EVIDENCE` or `OUT_OF_SCOPE` and supply the applicable fields.
This is a content contract, not a requirement to emit long boilerplate.

| Field | Required content |
| --- | --- |
| ID and disposition | Answer the actual question; classify a finding as required fix, non-blocking suggestion, harness/evidence issue or scope decision |
| Basis | Exact rule and code/evidence anchors; known facts, uncertainty and what was not checked |
| Direction | Preferred minimal repair/implementation route, affected entry points or existing component to reuse, and why it addresses the evidence |
| Invariants | Behavior, compatibility, lifecycle, permissions and frozen criteria that must not change; explicitly reject the tempting wrong route when relevant |
| Verification | Smallest useful command/test/observation, its input/output binding and success/failure oracle; include a regression or negative case |
| Owner and next action | Who acts next, what can proceed now, and the precise condition for escalation or return |

`NEED_EVIDENCE` must name a bounded discriminating probe and the next action for
each meaningful outcome. Do not state an unverified root cause as fact, demand
unrelated full reruns, or send the implementer to search the whole repository.
`OUT_OF_SCOPE` must name the decision owner, exact scope change and recommended
disposition; it must not silently authorize that change or block unrelated work.

Answer repeated questions by checking whether evidence/constraints changed,
pointing to the stable prior decision and clarifying the missing implication.
Do not make the implementer rediscover the same rejected approach. Consolidate
related findings and incomplete checks into one batch, as required by the
[acceptance execution contract](acceptance-execution-contract.md), section 7.3.

## Independence And Closeout

Review/acceptance agents may identify concrete functions, recommend a design and
provide test oracles without becoming the implementation author. Independence
does not require withholding useful guidance. They must not edit production code,
silently change the approved criterion or claim that a suggested fix was executed.
If they implement a fix, disclose the role change and obtain a different independent
reviewer for that affected scope.

The implementation reply links the selected change and real self-test result to
each ID, or explains with new evidence why a recommendation is inapplicable. The
reviewer checks that batch and its affected dependencies, not an invented larger
scope. Mark an issue resolved only when its oracle is met; a proposed patch,
successful parser, upload step or permission receipt is not product acceptance.

## Worked Example

Bad response to a failed USB collector:

    "ADB is unstable. Improve error handling and repeat the upgrade."

Actionable response:

    ID: HOST-01. DECIDED, harness issue, not a proved firmware failure.
    Basis: the owned supervisor's closed receipt reports WinError 5 replacing
    state.json.tmp; the subsequent ADB client gets connection refused. The
    installed-package check succeeded earlier; no new install is justified.
    Direction: use a bounded atomic-replacement retry in the state writer,
    preserving the same already-fsynced temporary file. Test the helper with
    a real Windows read handle that temporarily denies delete sharing.
    Invariants: no repeated command/reservation, no overwritten old evidence,
    no weakened deadline or replay of a successful OTA. Do not modify a running
    source-pinned helper or call this a phone/firmware fix.
    Verification: the delayed release allows one replacement; permanent denial
    and unrelated I/O errors fail explicitly; the owned worker remains alive
    through the temporary conflict and exits normally at its bound.
    Owner/next: implementation updates and self-tests the host adapter. Root
    reuses the existing App snapshot if OTA already succeeded, or resumes the
    unspent observation only within the applicable scope.

When the cause is not yet known:

    ID: LINK-02. NEED_EVIDENCE; UART is one hypothesis, not the conclusion.
    Owner: implementation collects existing App discovery/GATT/ACK summaries
    and package/MTU/write-mode bindings; root supplies any missing original log.
    Probe: parse the preserved input once using the current strict parser.
    If repeated discovery is material, prepare connection-generation-bound
    reuse and invalidation tests. If platform writes dominate, investigate
    supported write mode and pacing before a measured baud comparison.
    Do not add overlapping timing sums or discard invalid ACK samples. No
    device reset, new transfer or criterion change is granted by this answer.

These examples guide reasoning. They are not constant diagnoses or mandatory
implementation shapes for unrelated failures.
