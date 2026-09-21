# Actionable Agent Collaboration

## Scope

Applies when implementation, review, acceptance or root agents ask for a decision,
report a defect or return remediation feedback. Use the existing task note or
issue list; do not create an approval workflow for every question. This contract
does not change product criteria, operating permissions or acceptance independence.

The responder owns reducing uncertainty enough for the recipient to act. A bare
"check the spec", "improve robustness", "not sufficient" or "try again" is not
an answer. A document link alone is sufficient only when it points to an already
resolved, directly applicable decision and states how it applies here.

## Question Packet

Keep a stable question/finding ID and include only decision-relevant information:

- Task, role, revision/artifact and exact decision needed.
- Expected behavior/invariant and actual observation, with file/function or raw
  evidence anchors; distinguish observation from hypothesis.
- What was already attempted and why rejected paths must not be repeated.
- Recommended option, credible alternative if useful, and affected scope/cost.
- Current authorization, quota and output boundary when a proposed action has
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
    no weakened deadline or new OTA/reset quota. Do not modify a running
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
