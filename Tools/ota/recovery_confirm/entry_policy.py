"""Offline entry/settlement reasoning only. No hardware or execution adapter.

Inputs are hypothetical trusted evidence facts, not an authentication mechanism.
Passing this model does not establish that any such facts hold on the device.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Binding:
    operation: str
    board_uid: str
    probe: str
    epoch: str
    boot_sha: str
    app_sha: str
    bcb_pair_sha: str


@dataclass(frozen=True)
class Settlement:
    epoch: str
    # Must be an upper bound on the last possible STOP, not request submission.
    last_possible_stop_us: int | None
    observed_us: int
    max_write_us: int | None
    part_evidence: str | None
    clock_evidence: str | None
    ack_semantics_evidence: str | None
    ready_ack_us: int | None
    exclusive: bool
    protocol_idle: bool
    power_stable: bool


def binding_reason(plan: Binding, actual: Binding) -> str:
    for field in Binding.__dataclass_fields__:
        expected, observed = getattr(plan, field), getattr(actual, field)
        if not isinstance(expected, str) or not expected or not isinstance(observed, str) or not observed:
            return "UNKNOWN_BINDING"
        if expected != observed:
            return "BINDING_MISMATCH_" + field.upper()
    return "BOUND_IN_MODEL"


def settlement_reason(expected_epoch: str, evidence: Settlement) -> str:
    if not expected_epoch or evidence.epoch != expected_epoch:
        return "UNKNOWN_EPOCH"
    if not all(isinstance(x, str) and x for x in (
            evidence.part_evidence, evidence.clock_evidence, evidence.ack_semantics_evidence)):
        return "UNKNOWN_TIMING_BASIS"
    if evidence.exclusive is not True or evidence.protocol_idle is not True or evidence.power_stable is not True:
        return "UNKNOWN_BUS_OWNERSHIP"
    stop, limit, now, ack = (evidence.last_possible_stop_us, evidence.max_write_us,
                             evidence.observed_us, evidence.ready_ack_us)
    if any(type(x) is not int for x in (stop, limit, now)) or stop < 0 or limit <= 0 or now < stop:
        return "UNKNOWN_STOP_OR_CLOCK"
    horizon = stop + limit
    if now < horizon:
        return "WAIT_NO_CLASSIFICATION"
    if type(ack) is not int or not horizon <= ack <= now:
        return "UNKNOWN_READY_AFTER_HORIZON"
    return "SETTLED_IN_MODEL"


def route_result(plan: Binding, actual: Binding, evidence: Settlement,
                 result_code: str, *, observations_equal: bool, exact_target_pair: bool) -> str:
    if binding_reason(plan, actual) != "BOUND_IN_MODEL":
        return "STOP_BINDING_UNCERTAIN"
    if settlement_reason(plan.epoch, evidence) != "SETTLED_IN_MODEL":
        return "HOLD_NO_RETRY_OR_RESET"
    # In particular, RC_REJECTED from the already-complete inconsistent-read
    # branch is not permission to retry confirmation.
    if result_code in ("RC_REJECTED", "RC_UNKNOWN") or observations_equal is not True:
        return "STOP_READ_ONLY_RECONCILIATION"
    if result_code in ("RC_CONFIRMED", "RC_ALREADY") and exact_target_pair is True:
        return "COMPLETION_CLASSIFIABLE_IN_MODEL"
    if result_code == "RC_NOT_CONFIRMED":
        return "STOP_NOT_CONFIRMED_NO_RETRY"
    return "STOP_UNEXPECTED_RESULT"
