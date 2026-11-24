#include "bcb_target.h"
#include "dispatch.h"

static re_session session;
volatile re_bcb_report re_bcb_observation_report;

void re_bcb_dispatch_once(const re_profile *p)
{
    rr_bcb_observation observation = {0};
    unsigned i, pass, slot;
    int result;
    if (re_bcb_observation_report.started || session.consumed) return;
    re_bcb_observation_report.started = 1;
    if (p) {
        re_bcb_observation_report.epoch = p->epoch;
        for (i = 0; i < 32; ++i) re_bcb_observation_report.operation[i] = p->operation[i];
    }
    result = re_capture_target_once(&session, p, &observation);
    re_bcb_observation_report.result = (uint32_t)result;
    re_bcb_observation_report.completed = observation.completed;
    re_bcb_observation_report.stable = observation.stable;
    re_bcb_observation_report.active = (uint32_t)observation.active;
    for (pass = 0; pass < 2; ++pass)
        for (slot = 0; slot < 2; ++slot)
            for (i = 0; i < BCB_SIZE; ++i)
                re_bcb_observation_report.raw[pass][slot][i] = observation.raw[pass][slot][i];
    re_platform_report_barrier();
    re_bcb_observation_report.complete = RE_REPORT_COMPLETE;
}
void re_bcb_entry_dispatch(void)
{
    re_bcb_dispatch_once(&re_compiled_profile);
    re_terminal();
}
