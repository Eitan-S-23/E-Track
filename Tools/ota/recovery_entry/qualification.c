#include "supervisor.h"

int re_snapshot_matches(const re_profile *p, const re_hw_snapshot *h)
{
    unsigned i;
    if (!p || !h) return 0;
    for (i = 0; i < 5; ++i) if (h->clock[i] != p->clock[i]) return 0;
    return !h->ipsr && !(h->control & 7u) && h->primask == 1u &&
        h->msp >= 0x200640d8u && h->msp <= 0x20066000u && !(h->msp & 7u) &&
        h->vtor == 0x20060000u && !(h->fpccr & 1u) && !h->dma_active && !h->qspi_dma &&
        h->trace_enabled && h->counter_enabled;
}
