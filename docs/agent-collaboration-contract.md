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

## User Intervention Notifications

When the current session uses cc-connect, distinguish an out-of-chat action from
requesting a chat reply (user clarifications, 2026-10-09 and 2026-10-10). The bridge already sends an
automatic completion @mention for a normal final reply. Do not send an additional
manual reminder for a final report, handoff or approval question delivered with
that reply, even when it asks for a response. A project still being unfinished
does not turn a final reply into a mid-task intervention.

Only when the current execution is being kept open, an already-authorized user
action blocks its next step, and the user can perform it outside chat without
sending a chat reply, request that action through cc-connect with a real platform
@mention of the requesting user in that same session. All three conditions are
required. Examples include reinserting an SD card, reconnecting a cable or
handling an already-authorized phone dialog. After checking the send receipt,
observe the actual action/state change; do not require an "OK" reply in chat.

Requests requiring a chat reply never use manual @mentions. Authorization,
permission, a choice, confirmation or missing information requested in chat must
be asked in a normal final reply: end the current execution, let the bridge send
its automatic completion notification, and resume after the user's answer.
Keeping another task or worker running does not create an exception. Existing
standing authority does not require another permission request; continue
independent safe work until the normal final reply.

| Situation | Notification |
| --- | --- |
| Normal final report | Automatic completion only; no manual @mention |
| Final handoff or approval question | Automatic completion only; no manual @mention |
| Mid-task SD card, cable or phone action without a chat reply | Manual real @mention plus send receipt |
| Authorization or permission requested in chat | End with the question; automatic completion only; no manual @mention |
| Choice, confirmation or missing information requested in chat | End with the question; automatic completion only; no manual @mention |
| Approval while another task or worker is still running | End with the question; automatic completion only; no manual @mention |
| Ordinary progress or autonomous work | No manual @mention |

For a required mid-task reminder:

- Use the current session's project, session key and requester identity, not
  IDs copied from another conversation. Never print credentials or session keys.
- Use the existing `cc-connect send --project <current-project> --session
  <current-session> --stdin` route. For Feishu, include a real mention such as
  `<at user_id="CURRENT_REQUESTER_OPEN_ID">requester</at>` in the message body,
  replacing the placeholder with the actual requester ID. A plain `@name`, a
  normal reply or a local progress message does not satisfy this mid-task
  reminder requirement; this is not a reason to duplicate a final notification.
- State the exact action needed and why, plus any real timing constraint.
  Prepare the required observation route before asking for a short device window;
  do not ask the user to leave an App mid-transfer just to acknowledge a message.
- Check the send receipt. If delivery fails or the route is unavailable, report
  that fact in the current conversation; do not claim the user was notified or
  silently wait. Keep controllable notification files and receipts project-local.
- Do not send test reminders or repeat an unchanged pending request on each
  poll. Ordinary progress and work that can continue autonomously need no
  manual @mention.

The clarification and duplicate-notification lesson are recorded in
[PROJECT-06](agent-collaboration/project-workflow.md#project-06-only-manual-mentions-for-mid-task-blockers).

## Reuse Before Custom Tooling

Applies before creating or substantially extending supporting tools: flashing,
debugging, builds, collection, packaging, archiving and recovery. Product work
must not silently turn into a general-purpose tooling project.

1. Identify the next user-visible result and its necessary prerequisites. Separate
   explicit user constraints, existing contracts and demonstrated safety risks
   from agent preferences. For example, uninterrupted power does not itself mean
   no MCU reset; same-context resume is not an automatic flashing requirement.
   Do not remove a real constraint merely to make an existing tool fit.
2. Read the project's supported route and check installed/vendor tools first.
   Prefer existing applicable evidence, then documentation/help and the smallest
   authorized discriminating check. Unknown capability is not a proved gap. Do
   not run a destructive trial, replay a successful operation or expand device
   authority just to qualify a tool.
3. When the tool covers the requirement, use it. A small wrapper for arguments,
   output containment, deadlines, logs and verification is appropriate; replacing
   its protocol, Flash algorithm or state machine is a different decision.
4. Before a custom replacement, record in the existing task note: required missing
   capability; tool/version and original evidence of the gap; why configuration
   or a thin adapter is insufficient; smallest replacement scope; comparison with
   the standard route's remaining effort/risk; verification oracle and exit rule.
   If evidence is missing, investigate that gap instead of implementing a driver.
   This is a short engineering decision, not another mandatory approval ceremony.
5. Reassess before support work needs another new controller, recovery layer or
   audit harness, or becomes the obstacle to the next product measurement. Compare
   remaining work rather than sunk effort; retire unsupported self-imposed
   constraints and switch to a qualified simpler route. Preserve failed evidence
   and safely close owned processes; do not abandon an unresolved device state.
6. Report preparation, installed changes and measured benefit separately. More
   tooling tests or a reviewed design are not product progress or speed evidence.
   Once necessary safety checks pass, run the prepared bounded experiment rather
   than perfecting optional infrastructure first. Reviewers must question the
   necessity of the route, not only correctness within its chosen constraints.

| Situation | Required decision |
| --- | --- |
| Existing tool meets real constraints; only invocation/logging is missing | Reuse it with a thin adapter |
| Tool behavior is unknown or a host collector failed | Check capability or repair collection; do not infer a missing Flash algorithm |
| A sourced safety requirement cannot be met by the existing route | Retain the requirement; justify the smallest alternative and its tests |
| Agent-preferred no-reset mode drives a replacement without a demonstrated need | Reassess that preference before writing more tooling |
| Support-tool scope keeps growing without the planned product measurement | Recompare routes and stop the unnecessary branch, not the safety checks |

This does not weaken write boundaries, backup/integrity checks, device ownership,
recovery admission, frozen evidence or approval rules. It neither bans justified
custom tools nor mandates a new hardware comparison when existing evidence is
sufficient. Apply the rule to future work; do not rerun completed experiments to
document it. The motivating incident is recorded as
[PROJECT-04](agent-collaboration/project-workflow.md#project-04-reuse-tools-before-replacing-them).

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
