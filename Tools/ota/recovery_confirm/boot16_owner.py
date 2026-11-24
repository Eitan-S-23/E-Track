"""One caller-owned native session, no implicit retry, reset or failure cleanup."""
import time

import p34_boot16_probe as prior
from .boot16_program import Body
from .online_log import OnlineLog
from .mutation_audit import SealedGate


def execute(dap, observation, persist, initial, paths, record, remaining,
            image, map_bytes, plan, archive, *, direction='activate', retained=None,
            clock=time.monotonic, sleep=time.sleep, guard=prior.base.guarded,
            body_type=Body):
    result = dict(result='FAILED', close_returned=False, reset_performed=False,
                  boot_executed=False, eeprom_observed=False, nor_payload_written=False)
    logs = body = None
    normal = False
    original_close = observation.close
    def close():
        try:
            if (direction == 'restore' or body and body.control and body.control.mutation_attempted) and not normal:
                dap.power_changed = False
                dap.metadata['dp_restore_deferred_for_halt'] = True
                if dap.ready: dap.metadata['retained_dp_ctrlstat'] = dap._power_ready()
        finally:
            original_close()
    observation.close = close
    try:
        observation.connect()
        prior.cli.require(dap.original_csw == dap.word_csw == 0x23000052, 'qualified AP format required')
        acquisition, restore = prior.setup.dp_plan(dap.metadata)
        logs = OnlineLog(dap, SealedGate(paths, dap.metadata, record), persist,
                         remaining, initial_rows=initial, clock=clock)
        logs.switch(read_allowed=lambda _: False, expected_stores=[], expected_dp_writes=acquisition)
        body = body_type(dap, logs, remaining, archive, image, map_bytes, plan,
            direction=direction, retained=retained, checkpoint=archive.checkpoint,
            clock=clock, sleep=sleep, guard=guard)
        result['body'] = body.run()
        prior.cli.require(remaining() > 120, 'post-body archive/close reserve lost')
        result['archives'] = guard(archive.verify, 'after', body.desired, image, seconds=min(30, remaining()-90))
        prior.cli.require(remaining() > 90, 'post-body close reserve lost')
        prior.cli.require(body.post_verified and body.control.pause_restored and
            body.results['health']['result'] == 'R2_RUNTIME_HEALTH_OBSERVED', 'complete Boot16 exit required')
        logs.prepare_close()
        normal = True
    except BaseException as error:
        result['error'] = type(error).__name__+': '+str(error)
    finally:
        try: observation.close()
        except BaseException as error:
            normal = False
            result['close_error'] = type(error).__name__+': '+str(error)
        result.update(close_returned=dap.close_returned, dap=dict(dap.metadata), native_ap_error=dap.sdk.error)
        if body:
            result.update(phase=body.phase, boot_may_have_changed=body.boot_may_have_changed,
                release_started=body.release_started, post_verified=body.post_verified,
                sectors=body.sectors, component_results=body.results, body_error=body.error)
            if body.control:
                c = body.control
                result.update(before=c.before, context=c.context_before, control_error=c.error,
                    mutation_attempted=c.mutation_attempted, release_attempted=c.release_attempted,
                    release_returned=c.release_returned, pause_restored=c.pause_restored)
        if normal:
            try:
                result['final_trace'] = guard(lambda: logs.finish(read_allowed=lambda _: False,
                    expected_stores=[], expected_dp_writes=restore), seconds=min(60, remaining()))
                unchanged = not dap.power_changed and dap.original_dp & 0xf0000000 == 0xf0000000
                prior.cli.require(dap.close_returned and dap.metadata['tar_restored'] and dap.metadata['csw_restored']
                    and (dap.metadata['dp_restored'] or unchanged), 'native/AP close incomplete')
                result.update(result='BOOT16_PROGRAMMED_VERIFIED_CLOSED', logs=list(logs.gate.records),
                              direction=direction, native_close_audited=True)
            except BaseException as error:
                result['final_audit_error'] = type(error).__name__+': '+str(error)
        if logs: result.update(log_mode=logs.mode, log_error=logs.error, sealed=list(logs.gate.records))
    return result
