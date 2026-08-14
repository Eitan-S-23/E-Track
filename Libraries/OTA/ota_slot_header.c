/*
 * ota_slot_header.c —— 外部槽头（ETSL）写端辅助，与 P1-1/P1-3 已验收的
 * boot/src/boot_slot.c 读端按同一冻结契约（docs/ota-binary-contracts.md §4.1/
 * §4.3）保持一致。boot 读端口保持零改动，本文件仅供 App 侧与宿主测试使用，
 * 字段布局唯一依据仍为契约文档。
 */
#include "OTA/ota_slot_header.h"

#include "OTA/ota_layout.h"

#include <string.h>

/* 契约 §4.1：32B 槽头，小端。 */
#define QSLOT_TYPE_OFF      4u
#define QSLOT_PAD_OFF       5u
#define QSLOT_PAYLOAD_LEN_OFF  8u
#define QSLOT_PAYLOAD_CRC_OFF 12u
#define QSLOT_VCODE_OFF     16u
#define QSLOT_SHA8_OFF      20u
#define QSLOT_MARKER_OFF    28u

static uint32_t read_le32(const uint8_t *src)
{
    uint32_t value;
    unsigned shift;
    unsigned byte;

    value = 0u;
    for (shift = 0u, byte = 0u; byte < 4u; ++byte, shift += 8u)
    {
        value |= (uint32_t)src[byte] << shift;
    }
    return value;
}

static void write_le32(uint8_t *dst, uint32_t value)
{
    unsigned byte;

    for (byte = 0u; byte < 4u; ++byte)
    {
        dst[byte] = (uint8_t)(value >> (byte * 8u));
    }
}

void ota_slot_header_serialize_partial(
    const ota_slot_header_t *slot,
    uint8_t out[OTA_SLOT_HEADER_BYTES])
{
    memset(out, 0xFF, OTA_SLOT_HEADER_BYTES);
    if (slot == 0)
    {
        return;
    }
    memcpy(out, "ETSL", 4u);
    out[QSLOT_TYPE_OFF] = slot->slot_type;
    out[QSLOT_PAD_OFF] = 0xFFu;
    out[QSLOT_PAD_OFF + 1u] = 0xFFu;
    out[QSLOT_PAD_OFF + 2u] = 0xFFu;
    write_le32(out + QSLOT_PAYLOAD_LEN_OFF, slot->payload_len);
    write_le32(out + QSLOT_PAYLOAD_CRC_OFF, slot->payload_crc32);
    write_le32(out + QSLOT_VCODE_OFF, slot->version_code);
    memcpy(out + QSLOT_SHA8_OFF, slot->sha8,
           sizeof(slot->sha8));
    /* off 28..31 保持 0xFF（marker 擦除态），调用方最后单独写 */
}

void ota_slot_header_write_marker(uint8_t raw[OTA_SLOT_HEADER_BYTES])
{
    if (raw == 0)
    {
        return;
    }
    write_le32(raw + QSLOT_MARKER_OFF, OTA_SLOT_MARKER_COMMIT);
}

int ota_slot_header_parse(const uint8_t raw[OTA_SLOT_HEADER_BYTES],
                          uint8_t expected_type,
                          ota_slot_header_t *out)
{
    ota_slot_header_t parsed;
    uint32_t max_len;
    uint32_t marker;
    unsigned byte;

    if (raw == 0 || expected_type < OTA_SLOT_TYPE_CANDIDATE ||
        expected_type > OTA_SLOT_TYPE_RECOVERY)
    {
        return -1;
    }
    if (memcmp(raw, "ETSL", 4u) != 0)
    {
        return -1;
    }
    if (raw[QSLOT_TYPE_OFF] != expected_type)
    {
        return -1;
    }
    /* pad off 5..7 必须擦除态 */
    for (byte = 0u; byte < 3u; ++byte)
    {
        if (raw[QSLOT_PAD_OFF + byte] != 0xFFu)
        {
            return -1;
        }
    }
    marker = read_le32(raw + QSLOT_MARKER_OFF);
    if (marker != OTA_SLOT_MARKER_COMMIT &&
        marker != OTA_SLOT_MARKER_ERASED)
    {
        return -1;
    }
    /* staging 槽 0x180000，其余槽 0xF0000（契约 §4.1 与 §0.5） */
    max_len = expected_type == OTA_SLOT_TYPE_STAGING
                  ? OTA_ETU_MAX_LENGTH
                  : OTA_APP_LENGTH;

    parsed.slot_type = raw[QSLOT_TYPE_OFF];
    parsed.payload_len = read_le32(raw + QSLOT_PAYLOAD_LEN_OFF);
    parsed.payload_crc32 = read_le32(raw + QSLOT_PAYLOAD_CRC_OFF);
    parsed.version_code = read_le32(raw + QSLOT_VCODE_OFF);
    memcpy(parsed.sha8, raw + QSLOT_SHA8_OFF, sizeof(parsed.sha8));
    parsed.committed = (marker == OTA_SLOT_MARKER_COMMIT) ? 1 : 0;
    if (parsed.payload_len == 0u || parsed.payload_len > max_len)
    {
        return -1;
    }
    if (out != 0)
    {
        *out = parsed;
    }
    return 0;
}
