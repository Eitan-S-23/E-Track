#ifndef OTA_INSTALL_COST_H
#define OTA_INSTALL_COST_H

#include <stdint.h>
#include <string.h>

enum ota_cost_kind_t
{
    OTA_COST_PACKAGE_READ,
    OTA_COST_BASE_READ,
    OTA_COST_CANDIDATE_READ,
    OTA_COST_SLOT_READ,
    OTA_COST_ERASE,
    OTA_COST_PROGRAM,
    OTA_COST_RESTORE,
    OTA_COST_KINDS
};

typedef struct ota_cost_bucket_t
{
    uint32_t calls;
    uint32_t failures;
    uint64_t bytes;
    uint64_t ticks;
} ota_cost_bucket_t;

typedef struct ota_cost_stats_t
{
    uint32_t start;
    uint32_t invalid;
    ota_cost_bucket_t io[OTA_COST_KINDS];
} ota_cost_stats_t;

static inline void ota_cost_begin(ota_cost_stats_t *s, uint32_t now)
{
    memset(s, 0, sizeof(*s));
    s->start = now;
}

static inline void ota_cost_add(ota_cost_stats_t *s, unsigned kind,
                                uint32_t start, uint32_t end,
                                uint32_t bytes, int result)
{
    if (kind >= OTA_COST_KINDS || s->io[kind].calls == UINT32_MAX)
    {
        if (s->invalid != UINT32_MAX)
            ++s->invalid;
        return;
    }
    ota_cost_bucket_t *b = &s->io[kind];
    ++b->calls;
    b->failures += result != 0 ? 1u : 0u;
    b->bytes += bytes;
    b->ticks += (uint32_t)(end - start);
}

/* Non-overlapping port intervals, on the same millis clock as the phase.
 * Residual includes software work and uninstrumented ports, not just decode. */
static inline int ota_cost_finish(const ota_cost_stats_t *s, uint32_t now,
                                  uint32_t *residual)
{
    uint64_t sum = 0;
    unsigned i;
    for (i = 0; i < OTA_COST_KINDS; ++i)
    {
        if (UINT64_MAX - sum < s->io[i].ticks)
            return 0;
        sum += s->io[i].ticks;
    }
    if (s->invalid || sum > (uint32_t)(now - s->start))
        return 0;
    *residual = (uint32_t)(now - s->start) - (uint32_t)sum;
    return 1;
}

#endif
