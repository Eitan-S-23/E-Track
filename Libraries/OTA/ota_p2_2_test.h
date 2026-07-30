#ifndef E_TRACK_OTA_P2_2_TEST_H
#define E_TRACK_OTA_P2_2_TEST_H

#include <stdint.h>

#include "ota_layout.h"

#define OTA_P2_2_CONTROL_SIZE 2048u
#define OTA_P2_2_CONTROL_ADDRESS \
    (OTA_RAM_ORIGIN + OTA_RAM_LENGTH - OTA_P2_2_CONTROL_SIZE)
#define OTA_P2_2_PACKAGE_OFFSET 1024u
#define OTA_P2_2_PACKAGE_CAPACITY 1024u

#define OTA_P2_2_COMMAND_MAGIC 0x43323250u
#define OTA_P2_2_DONE_MAGIC 0x44323250u
#define OTA_P2_2_VERSION 1u
#define OTA_P2_2_OPCODE_APPLY 1u
#define OTA_P2_2_COOKIE 0x22E71D29u

#define OTA_P2_2_OFF_MAGIC 0u
#define OTA_P2_2_OFF_VERSION 4u
#define OTA_P2_2_OFF_OPCODE 8u
#define OTA_P2_2_OFF_OPCODE_INVERSE 12u
#define OTA_P2_2_OFF_COOKIE 16u
#define OTA_P2_2_OFF_COOKIE_INVERSE 20u
#define OTA_P2_2_OFF_PACKAGE_LEN 24u
#define OTA_P2_2_OFF_CURRENT_VCODE 28u
#define OTA_P2_2_OFF_EXPECTED_RESULT 32u
#define OTA_P2_2_OFF_PACKAGE_CRC32 36u
#define OTA_P2_2_OFF_COMMAND_CRC32 40u
#define OTA_P2_2_COMMAND_CRC_OFFSET 4u
#define OTA_P2_2_COMMAND_CRC_LENGTH 36u

#define OTA_P2_2_OFF_STATUS 44u
#define OTA_P2_2_OFF_ACTUAL_RESULT 48u
#define OTA_P2_2_OFF_DETAIL 52u
#define OTA_P2_2_OFF_TARGET_VCODE 56u
#define OTA_P2_2_OFF_IMAGE_LEN 60u
#define OTA_P2_2_OFF_WORKSPACE_PEAK 64u
#define OTA_P2_2_OFF_PAYLOAD_LEN 68u
#define OTA_P2_2_OFF_PAYLOAD_CRC32 72u
#define OTA_P2_2_OFF_CANDIDATE_PREPARES 76u
#define OTA_P2_2_OFF_CANDIDATE_PROGRAMS 80u
#define OTA_P2_2_OFF_CANDIDATE_BYTES 84u
#define OTA_P2_2_OFF_STAGING_ERASES 88u
#define OTA_P2_2_OFF_STAGING_PROGRAMS 92u
#define OTA_P2_2_OFF_WORKSPACE_ZERO 96u
#define OTA_P2_2_OFF_CANDIDATE_HEADER_ERASED 100u
#define OTA_P2_2_OFF_BCB_EQUAL 104u
#define OTA_P2_2_OFF_ACTUAL_PACKAGE_CRC32 108u
#define OTA_P2_2_OFF_IMAGE_SHA256 112u
#define OTA_P2_2_OFF_BCB_BEFORE 256u
#define OTA_P2_2_OFF_BCB_AFTER 384u
#define OTA_P2_2_BCB_SNAPSHOT_SIZE 128u
#define OTA_P2_2_OFF_RESULT_CRC32 512u
#define OTA_P2_2_RESULT_CRC_OFFSET 44u
#define OTA_P2_2_RESULT_CRC_LENGTH 468u

enum
{
    OTA_P2_2_STATUS_ARMED = 0,
    OTA_P2_2_STATUS_RUNNING = 1,
    OTA_P2_2_STATUS_PASS = 2,
    OTA_P2_2_STATUS_FAIL = 3
};

#if defined(P2_2_TEST_ENABLE)
static inline volatile uint8_t *ota_p2_2_control(void)
{
    return (volatile uint8_t *)(uintptr_t)OTA_P2_2_CONTROL_ADDRESS;
}

static inline uint32_t ota_p2_2_read_u32(uint32_t offset)
{
    volatile uint8_t *control = ota_p2_2_control();
    return (uint32_t)control[offset] |
           ((uint32_t)control[offset + 1u] << 8) |
           ((uint32_t)control[offset + 2u] << 16) |
           ((uint32_t)control[offset + 3u] << 24);
}

static inline void ota_p2_2_write_u32(uint32_t offset, uint32_t value)
{
    volatile uint8_t *control = ota_p2_2_control();
    control[offset] = (uint8_t)value;
    control[offset + 1u] = (uint8_t)(value >> 8);
    control[offset + 2u] = (uint8_t)(value >> 16);
    control[offset + 3u] = (uint8_t)(value >> 24);
}
#endif

#endif
