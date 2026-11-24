#include "dispatch.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned reads, writes, barriers;
static int scenario;
const re_profile re_compiled_profile = {0};
void re_terminal(void) { assert(0); }
void re_platform_report_barrier(void)
{
    assert(re_observation_report.started == 1 && re_observation_report.complete == 0);
    ++barriers;
}
int re_platform_snapshot(re_hw_snapshot *h)
{
    ++reads;
    memset(h, 0, sizeof(*h));
    h->ticks = reads * 10u;
    h->primask = h->trace_enabled = h->counter_enabled = 1;
    h->msp = 0x20065e00; h->vtor = 0x20060000;
    if (scenario == 4 && reads >= 5) h->clock[0] = 1;
    return 0;
}
int re_platform_read32(uint32_t off, uint32_t *v)
{
    if (off == 0x10) *v = scenario == 5 ? 0 : 3;
    else if (off == 0x18) *v = 4u | (writes == 4 && scenario != 3 ? 2u : 0u);
    else if (off == 0x24) *v = writes == 4 && scenario != 3 ? 1 : 0;
    else assert(0);
    return 0;
}
int re_platform_write32(uint32_t off, uint32_t value)
{
    static const uint32_t expected[] = {0, 0x01000000, 1, 0x05000000};
    assert(writes < 4 && off == writes * 4 && value == expected[writes]);
    ++writes;
    return scenario == 6 ? -1 : 0;
}
int re_platform_read8(uint32_t off, uint8_t *value)
{
    assert(off == 0x100);
    *value = scenario == 1 ? 1 : 0;
    return 0;
}

int main(int argc, char **argv)
{
    re_profile p = {0};
    re_report before;
    unsigned old_reads, old_writes;
    assert(argc == 2);
    scenario = atoi(argv[1]);
    assert(scenario >= 0 && scenario <= 7);
    p.epoch = 3; p.hz = 288000000; p.budget = 100000;
    p.entry_qualified = p.media_qualified = p.clock_qualified = p.ownership_qualified = 1;
    memset(p.operation, 0x27, sizeof(p.operation));
    if (scenario == 2) p.entry_qualified = 0;
    re_dispatch_once(scenario == 7 ? 0 : &p);
    assert(re_observation_report.started == 1);
    assert(re_observation_report.complete == RE_REPORT_COMPLETE);
    assert(barriers == 1);
    assert(re_observation_report.status_valid == (scenario <= 1));
    assert(re_observation_report.observation == (scenario == 0 ? RE_OBS_IDLE_STATUS_ONLY :
                                               scenario == 1 ? RE_OBS_BUSY : RE_OBS_UNKNOWN));
    assert(re_observation_report.status == (scenario == 1 ? 1u : 0u));
    if (scenario == 2 || scenario == 7) assert(reads == 0 && writes == 0);
    if (scenario == 5) assert(writes == 0);
    if (scenario == 6) assert(writes == 1);
    before = re_observation_report; old_reads = reads; old_writes = writes;
    p.epoch = 9;
    re_dispatch_once(&p);
    assert(reads == old_reads && writes == old_writes);
    assert(barriers == 1);
    assert(memcmp(&before, (const void *)&re_observation_report, sizeof(before)) == 0);
    printf("ENTRY_DISPATCH_HOST_PASS scenario=%d\n", scenario);
    return 0;
}
