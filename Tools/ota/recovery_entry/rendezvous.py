"""Original-App WFI rendezvous policy; no reset, resume or RAM execution API.

Transport methods must bound their own calls. A failed/uncertain mutation is
retained for reconciliation, never followed by a best-effort reset or resume.
"""
import time

from .probe import require

WFI = 0x08045a78
WFI_BYTES = bytes.fromhex("30bfa9e7")
WFI_COMPARATOR = 0x48045a79
WDT_PAUSE = 0x1000


def stopped_context_ok(context):
    return (context["halted"] is True and context["pc"] == WFI and
            context["xpsr"] & 0x010001ff == 0x01000000 and
            context["control"] in (0, 4) and context["vtor"] == 0x08010000 and
            not context["lockup"] and not context["reset_sticky"])


def stopped_media_observation(samples):
    """Classify stopped observations, never authorize reset from RAM alone."""
    require(len(samples) == 2, "two stopped observations required")
    reasons = set()
    for state in samples:
        raw = state["raw"]
        if state["recorder_active"] != 0 or state["recorder_file_handle_present"]:
            reasons.add("recorder_active_or_open")
        if not state["sd_cache_owners_match"]:
            reasons.add("cache_owner")
        for name in ("sd_data_cache_status", "sd_fat_cache_status"):
            status = raw[name] & 0xff
            if status & ~3:
                reasons.add("unknown_cache_status")
            if status & 1:
                reasons.add("dirty_cache")
        if state["sd_last_error"] or state["sd_transfer_error"] or state["sd_stop_flag"]:
            reasons.add("sd_error_or_stop")
        if state["sd_ready_mirror"] != 1 or not state["sd_data0_sampled_high"]:
            reasons.add("sd_not_ready")
        # R1 includes READY_FOR_DATA and TRAN, but also independent error bits.
        if (raw["sdio2_cmd"] & 0x3f != 13 or raw["sdio2_rspcmd"] & 0x3f != 13 or
                raw["sdio2_rsp1"] != 0x900 or raw["sdio2_sts"] != 0 or
                raw["sdio2_dtcnt"] != 0 or raw["sd_dma_count"] != 0):
            reasons.add("sd_command_or_transfer")
        if state["ble_state"] or state["ble_isr_active"] or state["overlay_owner"]:
            reasons.add("ota_owner")
        if not state["eeprom_pins_sampled_released"]:
            reasons.add("eeprom_not_released")
    return dict(observed_blockers=sorted(reasons), media_safe_reset_proven=False,
                nor_settled_proven=False, other_file_writers_excluded=False,
                historical_filesystem_integrity_proven=False, device_execute_ready=False)


def acquire(transport, emit, *, seconds=10, clock=time.monotonic, sleep=time.sleep):
    require(type(seconds) in (int, float) and 0 < seconds <= 15, "finite rendezvous deadline required")
    started = clock()
    result = dict(result="FAILED", mutation_attempted=False, pause_verified=False,
                  breakpoint_attempted=False, breakpoint_disarmed=False,
                  halt_observed=False, automatic_resume=False, reset_performed=False,
                  device_execute_ready=False)

    def deadline():
        require(0 <= clock()-started < seconds, "rendezvous deadline expired")

    try:
        deadline()
        before = transport.initial()
        result["before"] = before
        require(before["wfi_bytes"] == WFI_BYTES.hex(), "live exact WFI bytes required")
        require(before["vtor"] == 0x08010000 and before["halted"] is False and
                not before["lockup"] and not before["reset_sticky"], "unqualified initial core")
        require(before["fp_ctrl"] == 0x261 and before["comparators"] == [0]*6,
                "unowned FPB v1 configuration")
        require(before["dhcsr_control"] == 1, "unexpected debug control bits")
        require(before["wwdt_ctrl"] & 0x80 == 0, "active window watchdog not qualified")
        deadline()
        original_pause = before["debug_apb1_frz"]
        result["mutation_attempted"] = True
        emit("wdt-halt-pause-attempt", original=original_pause, value=original_pause | WDT_PAUSE)
        transport.set_halt_pause(original_pause | WDT_PAUSE)
        require(transport.read_halt_pause() == original_pause | WDT_PAUSE, "halt pause readback mismatch")
        result["pause_verified"] = True
        deadline()
        result["breakpoint_attempted"] = True
        emit("wfi-breakpoint-attempt", address=WFI, comparator=WFI_COMPARATOR)
        transport.arm_wfi()
        require(transport.read_comparator() == WFI_COMPARATOR, "WFI comparator readback mismatch")
        while True:
            deadline()
            status = transport.status()
            require(not status["lockup"] and not status["reset_sticky"], "core changed during rendezvous")
            if status["halted"]:
                result["halt_observed"] = True
                break
            sleep(.01)
        context = transport.context()
        result["context"] = context
        require(stopped_context_ok(context), "unexpected stopped context; retain without resume")
        require(transport.read_halt_pause() == original_pause | WDT_PAUSE, "halt pause changed")
        # Removing our comparator does not resume the core. Retain WDT pause.
        transport.disarm_wfi()
        require(transport.read_comparator() == 0, "WFI comparator removal mismatch")
        result["breakpoint_disarmed"] = True
        deadline()
        samples = []
        for _ in range(2):
            deadline()
            samples.append(transport.media())
        deadline()
        require(transport.context() == context, "stopped context changed during observation")
        require(transport.read_halt_pause() == original_pause | WDT_PAUSE, "retained halt pause changed")
        deadline()
        result["state_samples"] = samples
        result["media"] = stopped_media_observation(samples)
        result["result"] = "APP_WFI_HALTED_RETAINED_NOT_RESET"
        emit("halt-retained", pc=WFI, watchdog_pause=True, media=result["media"])
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
        emit("rendezvous-failed-retain", error=result["error"],
             breakpoint_attempted=result["breakpoint_attempted"], pause_verified=result["pause_verified"])
    result["elapsed_seconds"] = clock()-started
    return result
