#include "dispatch.h"

static re_session session;
volatile re_report re_observation_report;

void re_dispatch_once(const re_profile *p)
{
    unsigned i;
    uint8_t status = 0;
    re_observation observation;
    /* One invocation per qualified bootstrap, including rejected requests.
       Re-entry neither issues I/O nor overwrites an earlier diagnostic. */
    if (re_observation_report.started || session.consumed) return;
    re_observation_report.started = 1;
    if (p) {
        re_observation_report.epoch = p->epoch;
        for (i = 0; i < 32; ++i) re_observation_report.operation[i] = p->operation[i];
    }
    observation = re_supervise_once(&session, p, p ? p->operation : 0, &status);
    re_observation_report.observation = (uint32_t)observation;
    re_observation_report.status = status;
    re_observation_report.status_valid = observation != RE_OBS_UNKNOWN;
    /* All fields are volatile; publish completion last. An exception before
       this store leaves an incomplete report, not an inferred idle result. */
    re_platform_report_barrier();
    re_observation_report.complete = RE_REPORT_COMPLETE;
}

void re_entry_dispatch(void)
{
    re_dispatch_once(&re_compiled_profile);
    re_terminal();
}
