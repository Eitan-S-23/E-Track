#ifndef E_TRACK_OTA_P1_6_TEST_H
#define E_TRACK_OTA_P1_6_TEST_H

#include <stdint.h>

#include "ota_layout.h"

#ifdef __cplusplus
extern "C" {
#endif

#define OTA_P1_6_CONTROL_SIZE 512u
#define OTA_P1_6_CONTROL_ADDRESS \
    (OTA_RAM_ORIGIN + OTA_RAM_LENGTH - OTA_P1_6_CONTROL_SIZE)

#if OTA_P1_6_CONTROL_ADDRESS < OTA_RAM_ORIGIN || \
    (OTA_P1_6_CONTROL_ADDRESS + OTA_P1_6_CONTROL_SIZE) != \
        (OTA_RAM_ORIGIN + OTA_RAM_LENGTH)
#error "P1-6 control block must occupy the tail of main RAM"
#endif

#define OTA_P1_6_COMMAND_MAGIC 0x43365045u
#define OTA_P1_6_ARM_MAGIC 0x41365045u
#define OTA_P1_6_DONE_MAGIC 0x44365045u
#define OTA_P1_6_VERSION 1u
#define OTA_P1_6_COOKIE 0x16E71D29u
#define OTA_P1_6_WILDCARD UINT32_MAX

#define OTA_P1_6_OFF_MAGIC 0u
#define OTA_P1_6_OFF_VERSION 4u
#define OTA_P1_6_OFF_OPCODE 8u
#define OTA_P1_6_OFF_OPCODE_INVERSE 12u
#define OTA_P1_6_OFF_COOKIE 16u
#define OTA_P1_6_OFF_COOKIE_INVERSE 20u
#define OTA_P1_6_OFF_ARG0 24u
#define OTA_P1_6_OFF_ARG1 28u
#define OTA_P1_6_OFF_ARG2 32u
#define OTA_P1_6_OFF_ARG3 36u
#define OTA_P1_6_OFF_COMMAND_CRC32 40u
#define OTA_P1_6_COMMAND_CRC_LENGTH 40u

#define OTA_P1_6_OFF_STATUS 44u
#define OTA_P1_6_OFF_DETAIL 48u
#define OTA_P1_6_OFF_PROGRESS 52u
#define OTA_P1_6_OFF_TOTAL 56u
#define OTA_P1_6_OFF_TARGET_CHECKPOINT 60u
#define OTA_P1_6_OFF_TARGET_ARG0 64u
#define OTA_P1_6_OFF_TARGET_ARG1 68u
#define OTA_P1_6_TARGET_CRC_LENGTH 12u
#define OTA_P1_6_OFF_OBSERVED_CHECKPOINT 72u
#define OTA_P1_6_OFF_OBSERVED_ARG0 76u
#define OTA_P1_6_OFF_OBSERVED_ARG1 80u
#define OTA_P1_6_OFF_HIT_COUNT 84u
#define OTA_P1_6_OFF_ACTIVE 88u
#define OTA_P1_6_OFF_STATE 92u
#define OTA_P1_6_OFF_BOOT_TRY 96u
#define OTA_P1_6_OFF_COPY_PHASE 100u
#define OTA_P1_6_OFF_RESUME_BLOCK 104u
#define OTA_P1_6_OFF_SEQ 108u
#define OTA_P1_6_OFF_CUR_VCODE 112u
#define OTA_P1_6_OFF_CAND_VCODE 116u
#define OTA_P1_6_OFF_BACKUP_VCODE 120u
#define OTA_P1_6_OFF_APP_VCODE 124u
#define OTA_P1_6_OFF_APP_LEN 128u
#define OTA_P1_6_OFF_APP_HEADER_CRC32 132u
#define OTA_P1_6_OFF_APP_SHA256 136u
#define OTA_P1_6_OFF_SLOT_TYPE 168u
#define OTA_P1_6_OFF_SLOT_VCODE 172u
#define OTA_P1_6_OFF_SLOT_LEN 176u
#define OTA_P1_6_OFF_SLOT_CRC32 180u
#define OTA_P1_6_OFF_SLOT_SHA8 184u
#define OTA_P1_6_OFF_BCB_A_RAW 192u
#define OTA_P1_6_OFF_BCB_B_RAW 256u
#define OTA_P1_6_OFF_CORRUPT_OFFSET 320u
#define OTA_P1_6_OFF_CORRUPT_OLD_NEW 324u
#define OTA_P1_6_OFF_SLOT_HEADER_RAW 336u
#define OTA_P1_6_OFF_TARGET_CRC32 420u
#define OTA_P1_6_OFF_APP_RESULT 424u
#define OTA_P1_6_OFF_RESULT_CRC32 508u
#define OTA_P1_6_RESULT_CRC_OFFSET OTA_P1_6_OFF_STATUS
#define OTA_P1_6_RESULT_CRC_LENGTH \
    (OTA_P1_6_OFF_RESULT_CRC32 - OTA_P1_6_RESULT_CRC_OFFSET)

enum
{
    OTA_P1_6_OPCODE_CLEAR_BCB = 1,
    OTA_P1_6_OPCODE_INSTALL_SLOT = 2,
    OTA_P1_6_OPCODE_STAGE_SLOTS = 3,
    OTA_P1_6_OPCODE_SNAPSHOT = 4,
    OTA_P1_6_OPCODE_CORRUPT_SLOT = 5
};

enum
{
    OTA_P1_6_SNAPSHOT_BCB_ONLY = 1
};

enum
{
    OTA_P1_6_APP_RESULT_UNKNOWN = 0,
    OTA_P1_6_APP_RESULT_VALID = 1,
    OTA_P1_6_APP_RESULT_INVALID = 2
};

enum
{
    OTA_P1_6_STATUS_ARMED = 0,
    OTA_P1_6_STATUS_RUNNING = 1,
    OTA_P1_6_STATUS_PASS = 2,
    OTA_P1_6_STATUS_FAIL = 3,
    OTA_P1_6_STATUS_CHECKPOINT = 4
};

enum
{
    OTA_P1_6_DETAIL_NONE = 0,
    OTA_P1_6_DETAIL_COMMAND = 1,
    OTA_P1_6_DETAIL_EEPROM = 2,
    OTA_P1_6_DETAIL_QSPI_INIT = 3,
    OTA_P1_6_DETAIL_BCB_LOCKED = 4,
    OTA_P1_6_DETAIL_APP_INVALID = 5,
    OTA_P1_6_DETAIL_SLOT_ARGUMENT = 6,
    OTA_P1_6_DETAIL_SLOT_ERASE = 7,
    OTA_P1_6_DETAIL_SLOT_PROGRAM = 8,
    OTA_P1_6_DETAIL_SLOT_VERIFY = 9,
    OTA_P1_6_DETAIL_SLOT_HEADER = 10,
    OTA_P1_6_DETAIL_STAGE_VALIDATE = 11,
    OTA_P1_6_DETAIL_STAGE_COMMIT = 12,
    OTA_P1_6_DETAIL_SNAPSHOT = 13,
    OTA_P1_6_DETAIL_CORRUPT = 14
};

enum
{
    OTA_P1_6_SLOT_CANDIDATE = 1,
    OTA_P1_6_SLOT_BACKUP = 2,
    OTA_P1_6_SLOT_RECOVERY = 4
};

enum
{
    OTA_P1_6_CP_CANDIDATE_VALIDATED = 1,
    OTA_P1_6_CP_APPLYING_COMMITTED = 2,
    OTA_P1_6_CP_COPY_BEFORE_ERASE = 3,
    OTA_P1_6_CP_COPY_AFTER_ERASE = 4,
    OTA_P1_6_CP_COPY_AFTER_READBACK = 5,
    OTA_P1_6_CP_COPY_RESUME_COMMITTED = 6,
    OTA_P1_6_CP_APPLY_COPY_COMPLETE = 7,
    OTA_P1_6_CP_TEST_BOOT_COMMITTED = 8,
    OTA_P1_6_CP_TRY_DECREMENT_COMMITTED = 9,
    OTA_P1_6_CP_ROLLBACK_COMMITTED = 10,
    OTA_P1_6_CP_ROLLBACK_CONFIRMED = 11,
    OTA_P1_6_CP_APP_CONFIRMED = 12,
    OTA_P1_6_CP_PHYSICAL_RECOVERY = 13
};

#if defined(P1_6_TEST_ENABLE)
static inline volatile uint8_t *ota_p1_6_control(void)
{
    return (volatile uint8_t *)(uintptr_t)OTA_P1_6_CONTROL_ADDRESS;
}

static inline uint32_t ota_p1_6_read_u32(uint32_t offset)
{
    volatile uint8_t *control = ota_p1_6_control();
    return (uint32_t)control[offset] |
           ((uint32_t)control[offset + 1u] << 8) |
           ((uint32_t)control[offset + 2u] << 16) |
           ((uint32_t)control[offset + 3u] << 24);
}

static inline void ota_p1_6_write_u32(uint32_t offset, uint32_t value)
{
    volatile uint8_t *control = ota_p1_6_control();
    control[offset] = (uint8_t)value;
    control[offset + 1u] = (uint8_t)(value >> 8);
    control[offset + 2u] = (uint8_t)(value >> 16);
    control[offset + 3u] = (uint8_t)(value >> 24);
}

static inline uint32_t ota_p1_6_crc32(const volatile uint8_t *data,
                                      uint32_t length)
{
    uint32_t crc = 0xFFFFFFFFu;
    uint32_t index;

    for (index = 0u; index < length; ++index)
    {
        uint32_t value = crc ^ data[index];
        uint32_t bit;

        for (bit = 0u; bit < 8u; ++bit)
        {
            value = (value & 1u) != 0u
                        ? (value >> 1) ^ 0xEDB88320u
                        : value >> 1;
        }
        crc = value;
    }
    return crc ^ 0xFFFFFFFFu;
}

static inline int ota_p1_6_checkpoint_matches(uint32_t checkpoint,
                                               uint32_t arg0,
                                               uint32_t arg1)
{
    uint32_t target_arg0;
    uint32_t target_arg1;

    if (ota_p1_6_read_u32(OTA_P1_6_OFF_MAGIC) != OTA_P1_6_ARM_MAGIC ||
        ota_p1_6_read_u32(OTA_P1_6_OFF_VERSION) != OTA_P1_6_VERSION ||
        ota_p1_6_read_u32(OTA_P1_6_OFF_STATUS) != OTA_P1_6_STATUS_ARMED ||
        ota_p1_6_read_u32(OTA_P1_6_OFF_COOKIE) != OTA_P1_6_COOKIE ||
        (ota_p1_6_read_u32(OTA_P1_6_OFF_COOKIE) ^
         ota_p1_6_read_u32(OTA_P1_6_OFF_COOKIE_INVERSE)) != UINT32_MAX ||
        ota_p1_6_read_u32(OTA_P1_6_OFF_TARGET_CHECKPOINT) != checkpoint ||
        ota_p1_6_read_u32(OTA_P1_6_OFF_TARGET_CRC32) !=
            ota_p1_6_crc32(ota_p1_6_control() + OTA_P1_6_OFF_TARGET_CHECKPOINT,
                           OTA_P1_6_TARGET_CRC_LENGTH))
    {
        return 0;
    }

    target_arg0 = ota_p1_6_read_u32(OTA_P1_6_OFF_TARGET_ARG0);
    target_arg1 = ota_p1_6_read_u32(OTA_P1_6_OFF_TARGET_ARG1);
    return (target_arg0 == OTA_P1_6_WILDCARD || target_arg0 == arg0) &&
           (target_arg1 == OTA_P1_6_WILDCARD || target_arg1 == arg1);
}

static inline void ota_p1_6_checkpoint(uint32_t checkpoint,
                                       uint32_t arg0,
                                       uint32_t arg1)
{
    if (!ota_p1_6_checkpoint_matches(checkpoint, arg0, arg1))
    {
        return;
    }

    ota_p1_6_write_u32(OTA_P1_6_OFF_OBSERVED_CHECKPOINT, checkpoint);
    ota_p1_6_write_u32(OTA_P1_6_OFF_OBSERVED_ARG0, arg0);
    ota_p1_6_write_u32(OTA_P1_6_OFF_OBSERVED_ARG1, arg1);
    ota_p1_6_write_u32(
        OTA_P1_6_OFF_HIT_COUNT,
        ota_p1_6_read_u32(OTA_P1_6_OFF_HIT_COUNT) + 1u);
    ota_p1_6_write_u32(OTA_P1_6_OFF_STATUS,
                       OTA_P1_6_STATUS_CHECKPOINT);
    __asm volatile("dsb 0xF" ::: "memory");
    while (ota_p1_6_read_u32(OTA_P1_6_OFF_MAGIC) == OTA_P1_6_ARM_MAGIC &&
           ota_p1_6_read_u32(OTA_P1_6_OFF_STATUS) ==
               OTA_P1_6_STATUS_CHECKPOINT)
    {
        __asm volatile("nop");
    }
    __asm volatile("dsb 0xF\nisb 0xF" ::: "memory");
}
#else
#define ota_p1_6_checkpoint_matches(checkpoint, arg0, arg1) (0)
#define ota_p1_6_checkpoint(checkpoint, arg0, arg1) ((void)0)
#endif

#ifdef __cplusplus
}
#endif

#endif
