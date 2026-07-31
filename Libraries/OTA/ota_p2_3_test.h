#ifndef E_TRACK_OTA_P2_3_TEST_H
#define E_TRACK_OTA_P2_3_TEST_H

#include <stdint.h>

#include "ota_layout.h"

#define OTA_P2_3_CONTROL_SIZE 2048u
#define OTA_P2_3_CONTROL_ADDRESS \
    (OTA_RAM_ORIGIN + OTA_RAM_LENGTH - OTA_P2_3_CONTROL_SIZE)
#define OTA_P2_3_PACKAGE_OFFSET 1024u
#define OTA_P2_3_PACKAGE_CAPACITY 1024u

#define OTA_P2_3_COMMAND_MAGIC 0x43333250u
#define OTA_P2_3_DONE_MAGIC 0x44333250u
#define OTA_P2_3_VERSION 1u
#define OTA_P2_3_OPCODE_APPLY 1u
#define OTA_P2_3_COOKIE 0x33E71D29u

#define OTA_P2_3_OFF_MAGIC 0u
#define OTA_P2_3_OFF_VERSION 4u
#define OTA_P2_3_OFF_OPCODE 8u
#define OTA_P2_3_OFF_OPCODE_INVERSE 12u
#define OTA_P2_3_OFF_COOKIE 16u
#define OTA_P2_3_OFF_COOKIE_INVERSE 20u
#define OTA_P2_3_OFF_PACKAGE_LEN 24u
#define OTA_P2_3_OFF_CURRENT_VCODE 28u
#define OTA_P2_3_OFF_EXPECTED_RESULT 32u
#define OTA_P2_3_OFF_PACKAGE_CRC32 36u
#define OTA_P2_3_OFF_COMMAND_CRC32 40u
#define OTA_P2_3_COMMAND_CRC_OFFSET 4u
#define OTA_P2_3_COMMAND_CRC_LENGTH 36u

#define OTA_P2_3_OFF_STATUS 44u
#define OTA_P2_3_OFF_ACTUAL_RESULT 48u
#define OTA_P2_3_OFF_DETAIL 52u
#define OTA_P2_3_OFF_TARGET_VCODE 56u
#define OTA_P2_3_OFF_IMAGE_LEN 60u
#define OTA_P2_3_OFF_WORKSPACE_PEAK 64u
#define OTA_P2_3_OFF_PAYLOAD_LEN 68u
#define OTA_P2_3_OFF_PAYLOAD_CRC32 72u
#define OTA_P2_3_OFF_CANDIDATE_PREPARES 76u
#define OTA_P2_3_OFF_CANDIDATE_PROGRAMS 80u
#define OTA_P2_3_OFF_CANDIDATE_BYTES 84u
#define OTA_P2_3_OFF_STAGING_ERASES 88u
#define OTA_P2_3_OFF_STAGING_PROGRAMS 92u
#define OTA_P2_3_OFF_WORKSPACE_ZERO 96u
#define OTA_P2_3_OFF_CANDIDATE_HEADER_ERASED 100u
#define OTA_P2_3_OFF_BCB_EQUAL 104u
#define OTA_P2_3_OFF_ACTUAL_PACKAGE_CRC32 108u
/* 差分专属：内层头实测值与基版身份，供真机取证复核。 */
#define OTA_P2_3_OFF_BASE_VCODE 112u
#define OTA_P2_3_OFF_BASE_LEN 116u
#define OTA_P2_3_OFF_BASE_CRC32 120u
#define OTA_P2_3_OFF_IMAGE_CRC32 124u
#define OTA_P2_3_OFF_PATCH_STREAM_LEN 128u
#define OTA_P2_3_OFF_DECODED_LEN 132u
#define OTA_P2_3_OFF_IMAGE_SHA256 144u
#define OTA_P2_3_OFF_BASE_SHA8 176u
#define OTA_P2_3_OFF_BCB_BEFORE 256u
#define OTA_P2_3_OFF_BCB_AFTER 384u
#define OTA_P2_3_BCB_SNAPSHOT_SIZE 128u
#define OTA_P2_3_OFF_RESULT_CRC32 512u
#define OTA_P2_3_RESULT_CRC_OFFSET 44u
#define OTA_P2_3_RESULT_CRC_LENGTH 468u

enum
{
    OTA_P2_3_STATUS_ARMED = 0,
    OTA_P2_3_STATUS_RUNNING = 1,
    OTA_P2_3_STATUS_PASS = 2,
    OTA_P2_3_STATUS_FAIL = 3
};

#if defined(P2_3_TEST_ENABLE)
static inline volatile uint8_t *ota_p2_3_control(void)
{
    return (volatile uint8_t *)(uintptr_t)OTA_P2_3_CONTROL_ADDRESS;
}

static inline uint32_t ota_p2_3_read_u32(uint32_t offset)
{
    volatile uint8_t *control = ota_p2_3_control();
    return (uint32_t)control[offset] |
           ((uint32_t)control[offset + 1u] << 8) |
           ((uint32_t)control[offset + 2u] << 16) |
           ((uint32_t)control[offset + 3u] << 24);
}

static inline void ota_p2_3_write_u32(uint32_t offset, uint32_t value)
{
    volatile uint8_t *control = ota_p2_3_control();
    control[offset] = (uint8_t)value;
    control[offset + 1u] = (uint8_t)(value >> 8);
    control[offset + 2u] = (uint8_t)(value >> 16);
    control[offset + 3u] = (uint8_t)(value >> 24);
}
#endif

#endif
