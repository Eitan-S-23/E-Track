#ifndef E_TRACK_P34_STAGING_ERASE_H
#define E_TRACK_P34_STAGING_ERASE_H

#include "OTA/ota_staging.h"
#include "OTA/ota_erase_plan.h"

struct OtaStagingEraseAhead
{
    uint32_t next;
    uint32_t end;

    void reset() { next = end = 0u; }

    uint32_t size(uint32_t address, bool allow) const
    {
        const uint32_t limit = OTA_EXT_STAGING + OTA_EXT_STAGING_LENGTH;
        if (address < OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET ||
            address > limit - OTA_STAGING_BLOCK_SIZE ||
            (address & (OTA_STAGING_BLOCK_SIZE - 1u)) != 0u)
            return UINT32_MAX;
        if (allow && address == next && end <= limit &&
            end > address && end - address >= OTA_STAGING_BLOCK_SIZE)
            return 0u;
        return ota_erase_next_size(address, limit - address, allow);
    }

    // Consume before programming: retrying this sector must erase it again.
    void consume(uint32_t address, uint32_t erased)
    {
        if (erased != 0u)
            end = address + erased;
        next = address + OTA_STAGING_BLOCK_SIZE;
    }
};

#endif
