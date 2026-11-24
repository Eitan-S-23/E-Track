#ifndef RE_SUPERVISOR_H
#define RE_SUPERVISOR_H
#include "runtime.h"

typedef struct {
    uint32_t clock[5], ticks, trace_enabled, counter_enabled;
    uint32_t ipsr, control, primask, msp, vtor, fpccr, dma_active, qspi_dma;
} re_hw_snapshot;
typedef struct {
    uint32_t epoch, hz, budget;
    uint32_t clock[5];
    uint8_t operation[32];
    /* Pre-qualified evidence, NOT authentication or a physical state detector. */
    uint32_t entry_qualified, media_qualified, clock_qualified, ownership_qualified;
} re_profile;
typedef struct { uint32_t consumed; } re_session;

/* Pure comparison shared by fixed NOR and BCB adapters; not an ownership proof. */
int re_snapshot_matches(const re_profile *, const re_hw_snapshot *);

/* Session storage belongs to the one-shot supervisor, initialized only during
   qualified bootstrap. Never reinitialize it to retry an uncertain operation. */
re_observation re_supervise_once(re_session *, const re_profile *,
                                 const uint8_t operation[32], uint8_t *status);
/* Fixed platform primitives. No timebase reset or arbitrary memory operation. */
int re_platform_snapshot(re_hw_snapshot *);
int re_platform_read32(uint32_t offset, uint32_t *);
int re_platform_write32(uint32_t offset, uint32_t value);
int re_platform_read8(uint32_t offset, uint8_t *);
void re_platform_report_barrier(void);
#endif
