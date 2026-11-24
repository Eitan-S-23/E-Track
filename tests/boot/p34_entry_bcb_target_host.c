#define main original_reader_campaign_not_run
#include "p34_bcb_reader_host.c"
#undef main
#include "bcb_target.h"
#include "dispatch.h"
#include <stdlib.h>

static unsigned scenario, samples, pin_changes, idle_checks, barriers;
static int failed;
const re_profile re_compiled_profile = {0};
void re_terminal(void) { assert(0); }
void re_platform_report_barrier(void)
{
    assert(re_bcb_observation_report.started && !re_bcb_observation_report.complete);
    ++barriers;
}
int re_platform_snapshot(re_hw_snapshot *h)
{
    ++samples;
    memset(h, 0, sizeof(*h));
    h->ticks = scenario == 6 ? 1234u : samples * 720u + (scenario == 11 ? 0xffffff00u : 1234u);
    h->primask = h->trace_enabled = h->counter_enabled = 1;
    h->msp = 0x20065c00; h->vtor = 0x20060000;
    if (scenario == 1 && samples >= 1000) { h->clock[1] = 1; failed = 1; }
    if (scenario == 4) h->primask = 0;
    if (scenario == 5) h->msp = 0x20064000;
    return 0;
}
int re_bcb_pin_config_ok(int idle)
{
    if (idle) ++idle_checks;
    return scenario != 2 && !(idle && scenario == 3);
}
int re_bcb_pin_set(unsigned pin, int high)
{
    assert(!failed && (pin == 6 || pin == 7) && (high == 0 || high == 1));
    ++pin_changes;
    if (scenario == 8 && pin_changes == 5) { failed = 1; return -1; }
    if (pin == 6) scl(0, high); else sda(0, high);
    return 0;
}
int re_bcb_pin_read(unsigned pin)
{
    assert(!failed && (pin == 6 || pin == 7));
    if (scenario == 9 && cursor == 2) { failed = 1; return -1; }
    return pin == 6 ? read_scl(0) : read_sda(0);
}
int main(int argc, char **argv)
{
    re_profile p = {0};
    re_bcb_report before;
    unsigned old_samples, old_changes;
    assert(argc == 2);
    scenario = (unsigned)atoi(argv[1]); assert(scenario < 12);
    prepare(8, 7, scenario == 10);
    p.epoch = 3; p.hz = 288000000; p.budget = 576000000;
    p.entry_qualified = p.media_qualified = p.clock_qualified = p.ownership_qualified = 1;
    memset(p.operation, 0x27, 32);
    if (scenario == 7) p.entry_qualified = 0;
    re_bcb_dispatch_once(&p);
    assert(re_bcb_observation_report.started == 1 &&
           re_bcb_observation_report.complete == RE_REPORT_COMPLETE && barriers == 1);
    if (scenario == 0 || scenario == 11) {
        assert(re_bcb_observation_report.result == 0 && re_bcb_observation_report.stable);
        assert(re_bcb_observation_report.completed == 4 && re_bcb_observation_report.active == BCB_ARBITER_A);
        assert(cursor == 2060 && edge_count == 2420 && idle_checks == 1);
    } else {
        assert(re_bcb_observation_report.result != 0 && !re_bcb_observation_report.stable);
        if (scenario == 2 || scenario == 3 || scenario == 4 || scenario == 5 || scenario == 7)
            assert(pin_changes == 0);
        if (scenario == 7) assert(samples == 0 && idle_checks == 0);
    }
    before = re_bcb_observation_report; old_samples = samples; old_changes = pin_changes;
    re_bcb_dispatch_once(&p);
    assert(samples == old_samples && pin_changes == old_changes && barriers == 1);
    assert(memcmp(&before, (const void *)&re_bcb_observation_report, sizeof(before)) == 0);
    printf("ENTRY_BCB_TARGET_HOST_PASS scenario=%u\n", scenario);
    printf("BCB_REPORT_HEX=");
    {
        const unsigned char *bytes = (const unsigned char *)&before;
        unsigned i;
        assert(sizeof(before) == 316);
        for (i = 0; i < sizeof(before); ++i) printf("%02x", bytes[i]);
    }
    putchar('\n');
    return 0;
}
