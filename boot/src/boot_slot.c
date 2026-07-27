#include "boot_slot.h"

#include "OTA/ota_layout.h"

#include <string.h>

#define BOOT_SLOT_COMMIT_MARKER 0x434F4D54u

static uint32_t read_le32(const uint8_t *src)
{
    return (uint32_t)src[0] |
           ((uint32_t)src[1] << 8) |
           ((uint32_t)src[2] << 16) |
           ((uint32_t)src[3] << 24);
}

boot_slot_result_t boot_slot_header_parse(const uint8_t raw[BOOT_SLOT_HEADER_SIZE],
                                          boot_slot_type_t expected_type,
                                          boot_slot_header_t *out)
{
    boot_slot_header_t parsed;
    uint32_t max_len;

    if (raw == NULL || expected_type < BOOT_SLOT_CANDIDATE ||
        expected_type > BOOT_SLOT_RECOVERY)
    {
        return BOOT_SLOT_ERR_ARGUMENT;
    }
    if (memcmp(raw, "ETSL", 4u) != 0)
    {
        return BOOT_SLOT_ERR_MAGIC;
    }
    if (read_le32(raw + 28u) != BOOT_SLOT_COMMIT_MARKER)
    {
        return BOOT_SLOT_ERR_COMMIT;
    }
    if (raw[4] != (uint8_t)expected_type)
    {
        return BOOT_SLOT_ERR_TYPE;
    }
    if (raw[5] != 0xFFu || raw[6] != 0xFFu || raw[7] != 0xFFu)
    {
        return BOOT_SLOT_ERR_PADDING;
    }

    parsed.slot_type = raw[4];
    parsed.payload_len = read_le32(raw + 8u);
    parsed.payload_crc32 = read_le32(raw + 12u);
    parsed.version_code = read_le32(raw + 16u);
    memcpy(parsed.sha8, raw + 20u, sizeof(parsed.sha8));

    max_len = expected_type == BOOT_SLOT_STAGING
                  ? OTA_ETU_MAX_LENGTH
                  : OTA_APP_LENGTH;
    if (parsed.payload_len == 0u || parsed.payload_len > max_len)
    {
        return BOOT_SLOT_ERR_LENGTH;
    }

    if (out != NULL)
    {
        *out = parsed;
    }
    return BOOT_SLOT_OK;
}

const char *boot_slot_result_name(boot_slot_result_t result)
{
    static const char *const names[] = {
        "ok",
        "argument",
        "magic",
        "commit",
        "type",
        "padding",
        "length"
    };

    if ((unsigned)result >= sizeof(names) / sizeof(names[0]))
    {
        return "unknown";
    }
    return names[result];
}
