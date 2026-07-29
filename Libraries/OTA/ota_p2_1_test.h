#ifndef E_TRACK_OTA_P2_1_TEST_H
#define E_TRACK_OTA_P2_1_TEST_H

#include <stdint.h>

#include "ota_layout.h"

#define OTA_P2_1_CONTROL_SIZE 128u
#define OTA_P2_1_CONTROL_ADDRESS \
    (OTA_RAM_ORIGIN + OTA_RAM_LENGTH - OTA_P2_1_CONTROL_SIZE)

#define OTA_P2_1_COMMAND_MAGIC 0x43313250u
#define OTA_P2_1_DONE_MAGIC 0x44313250u
#define OTA_P2_1_VERSION 1u
#define OTA_P2_1_OPCODE_REENTRY 1u
#define OTA_P2_1_COOKIE 0x21E71D29u

#define OTA_P2_1_OFF_MAGIC 0u
#define OTA_P2_1_OFF_VERSION 4u
#define OTA_P2_1_OFF_OPCODE 8u
#define OTA_P2_1_OFF_OPCODE_INVERSE 12u
#define OTA_P2_1_OFF_COOKIE 16u
#define OTA_P2_1_OFF_COOKIE_INVERSE 20u
#define OTA_P2_1_OFF_SESSION_SHA256 24u
#define OTA_P2_1_OFF_COMMAND_CRC32 56u
#define OTA_P2_1_COMMAND_CRC_OFFSET OTA_P2_1_OFF_VERSION
#define OTA_P2_1_COMMAND_CRC_LENGTH 52u

#define OTA_P2_1_OFF_STATUS 60u
#define OTA_P2_1_OFF_CHECKPOINT 64u
#define OTA_P2_1_OFF_RESUMED 68u
#define OTA_P2_1_OFF_DURABLE_BEFORE 72u
#define OTA_P2_1_OFF_DURABLE_AFTER 76u
#define OTA_P2_1_OFF_SEGMENT_BITMAP 80u
#define OTA_P2_1_OFF_PERSISTENT_BITMAP 84u
#define OTA_P2_1_OFF_HEADER_ERASES 88u
#define OTA_P2_1_OFF_DATA_ERASES 92u
#define OTA_P2_1_OFF_DATA_PROGRAMS 96u
#define OTA_P2_1_OFF_DETAIL 100u
#define OTA_P2_1_OFF_RESULT_CRC32 124u
#define OTA_P2_1_RESULT_CRC_OFFSET OTA_P2_1_OFF_STATUS
#define OTA_P2_1_RESULT_CRC_LENGTH 64u

enum
{
    OTA_P2_1_STATUS_ARMED = 0,
    OTA_P2_1_STATUS_RUNNING = 1,
    OTA_P2_1_STATUS_CHECKPOINT = 2,
    OTA_P2_1_STATUS_PASS = 3,
    OTA_P2_1_STATUS_FAIL = 4
};

#if defined(P2_1_TEST_ENABLE)
static inline volatile uint8_t *ota_p2_1_control(void)
{
    return (volatile uint8_t *)(uintptr_t)OTA_P2_1_CONTROL_ADDRESS;
}

static inline uint32_t ota_p2_1_read_u32(uint32_t offset)
{
    volatile uint8_t *control = ota_p2_1_control();
    return (uint32_t)control[offset] |
           ((uint32_t)control[offset + 1u] << 8) |
           ((uint32_t)control[offset + 2u] << 16) |
           ((uint32_t)control[offset + 3u] << 24);
}

static inline void ota_p2_1_write_u32(uint32_t offset, uint32_t value)
{
    volatile uint8_t *control = ota_p2_1_control();
    control[offset] = (uint8_t)value;
    control[offset + 1u] = (uint8_t)(value >> 8);
    control[offset + 2u] = (uint8_t)(value >> 16);
    control[offset + 3u] = (uint8_t)(value >> 24);
}
#endif

#endif
