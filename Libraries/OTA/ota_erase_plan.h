#ifndef E_TRACK_OTA_ERASE_PLAN_H
#define E_TRACK_OTA_ERASE_PLAN_H

#include <stdint.h>
#include "OTA/ota_layout.h"

#define OTA_ERASE_BLOCK_SIZE 0x10000u

/* The caller invalidates its slot header separately before planning payload. */
static inline uint32_t ota_erase_next_size(uint32_t address,
                                           uint32_t remaining,
                                           int allow_block)
{
    if (remaining == 0u ||
        (address & (OTA_SLOT_HEADER_SIZE - 1u)) != 0u ||
        (remaining & (OTA_SLOT_HEADER_SIZE - 1u)) != 0u ||
        remaining > UINT32_MAX - address)
    {
        return 0u;
    }
    if (allow_block && (address & (OTA_ERASE_BLOCK_SIZE - 1u)) == 0u &&
        remaining >= OTA_ERASE_BLOCK_SIZE)
    {
        return OTA_ERASE_BLOCK_SIZE;
    }
    return OTA_SLOT_HEADER_SIZE;
}

#endif
