#ifndef E_TRACK_OTA_HALF_ERASE_PLAN_H
#define E_TRACK_OTA_HALF_ERASE_PLAN_H

#include "OTA/ota_erase_plan.h"

#define OTA_ERASE_HALF_BLOCK_SIZE 0x8000u

/* Only select complete aligned spans; header invalidation stays with the caller. */
static inline uint32_t ota_erase_next_size_mixed(uint32_t address,
                                                uint32_t remaining,
                                                int allow_block,
                                                int allow_half_block)
{
    uint32_t step = ota_erase_next_size(address, remaining, allow_block);
    if (step == OTA_SLOT_HEADER_SIZE && allow_half_block &&
        (address & (OTA_ERASE_HALF_BLOCK_SIZE - 1u)) == 0u &&
        remaining >= OTA_ERASE_HALF_BLOCK_SIZE)
    {
        return OTA_ERASE_HALF_BLOCK_SIZE;
    }
    return step;
}

#endif
