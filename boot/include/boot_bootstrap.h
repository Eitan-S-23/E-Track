#ifndef E_TRACK_BOOT_BOOTSTRAP_H
#define E_TRACK_BOOT_BOOTSTRAP_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* J-Link writes this command into the Boot NOLOAD overlay before reset. */
#define BOOT_BOOTSTRAP_COMMAND_MAGIC       0x424A5445u
#define BOOT_BOOTSTRAP_DONE_MAGIC          0x444A5445u
#define BOOT_BOOTSTRAP_COMMAND_VERSION     1u
#define BOOT_BOOTSTRAP_COMMAND_COOKIE      0x51A7B007u
#define BOOT_BOOTSTRAP_COMMAND_SIZE        128u

#define BOOT_BOOTSTRAP_OFF_MAGIC           0u
#define BOOT_BOOTSTRAP_OFF_VERSION         4u
#define BOOT_BOOTSTRAP_OFF_OPCODE          8u
#define BOOT_BOOTSTRAP_OFF_OPCODE_INVERSE  12u
#define BOOT_BOOTSTRAP_OFF_COOKIE          16u
#define BOOT_BOOTSTRAP_OFF_COOKIE_INVERSE  20u
#define BOOT_BOOTSTRAP_OFF_ARG0            24u
#define BOOT_BOOTSTRAP_OFF_ARG1            28u
#define BOOT_BOOTSTRAP_OFF_COMMAND_CRC32   32u
#define BOOT_BOOTSTRAP_COMMAND_CRC_LENGTH  32u

#define BOOT_BOOTSTRAP_OFF_STATUS          36u
#define BOOT_BOOTSTRAP_OFF_DETAIL          40u
#define BOOT_BOOTSTRAP_OFF_PROGRESS        44u
#define BOOT_BOOTSTRAP_OFF_TOTAL           48u
#define BOOT_BOOTSTRAP_OFF_ACTIVE          52u
#define BOOT_BOOTSTRAP_OFF_STATE           56u
#define BOOT_BOOTSTRAP_OFF_BOOT_TRY        60u
#define BOOT_BOOTSTRAP_OFF_COPY_PHASE      64u
#define BOOT_BOOTSTRAP_OFF_RESUME_BLOCK    68u
#define BOOT_BOOTSTRAP_OFF_CUR_VCODE       72u
#define BOOT_BOOTSTRAP_OFF_CAND_VCODE      76u
#define BOOT_BOOTSTRAP_OFF_BACKUP_VCODE    80u
#define BOOT_BOOTSTRAP_OFF_IMAGE_VCODE     84u
#define BOOT_BOOTSTRAP_OFF_IMAGE_LEN       88u
#define BOOT_BOOTSTRAP_OFF_IMAGE_CRC32     92u
#define BOOT_BOOTSTRAP_OFF_RESULT_CRC32    96u
#define BOOT_BOOTSTRAP_RESULT_CRC_OFFSET   36u
#define BOOT_BOOTSTRAP_RESULT_CRC_LENGTH   60u

#define BOOT_BOOTSTRAP_OPCODE_CLEAR_BCB    1u
#define BOOT_BOOTSTRAP_OPCODE_INSTALL_SLOT 2u
#define BOOT_BOOTSTRAP_OPCODE_STAGE_SLOTS  3u
#define BOOT_BOOTSTRAP_OPCODE_SNAPSHOT_BCB 4u

#define BOOT_BOOTSTRAP_SLOT_CANDIDATE      1u
#define BOOT_BOOTSTRAP_SLOT_BACKUP         2u
#define BOOT_BOOTSTRAP_SLOT_RECOVERY       4u

#define BOOT_BOOTSTRAP_STATUS_ARMED        0u
#define BOOT_BOOTSTRAP_STATUS_RUNNING      1u
#define BOOT_BOOTSTRAP_STATUS_PASS         2u
#define BOOT_BOOTSTRAP_STATUS_FAIL         3u

#define BOOT_BOOTSTRAP_DETAIL_NONE             0u
#define BOOT_BOOTSTRAP_DETAIL_COMMAND          1u
#define BOOT_BOOTSTRAP_DETAIL_EEPROM           2u
#define BOOT_BOOTSTRAP_DETAIL_QSPI_INIT        3u
#define BOOT_BOOTSTRAP_DETAIL_BCB_LOCKED       4u
#define BOOT_BOOTSTRAP_DETAIL_APP_INVALID      5u
#define BOOT_BOOTSTRAP_DETAIL_SLOT_ARGUMENT    6u
#define BOOT_BOOTSTRAP_DETAIL_SLOT_ERASE       7u
#define BOOT_BOOTSTRAP_DETAIL_SLOT_PROGRAM     8u
#define BOOT_BOOTSTRAP_DETAIL_SLOT_VERIFY      9u
#define BOOT_BOOTSTRAP_DETAIL_SLOT_HEADER      10u
#define BOOT_BOOTSTRAP_DETAIL_STAGE_VALIDATE   11u
#define BOOT_BOOTSTRAP_DETAIL_STAGE_COMMIT     12u

typedef enum
{
    BOOT_BOOTSTRAP_NO_REQUEST = 0,
    BOOT_BOOTSTRAP_HOLD = 1
} boot_bootstrap_result_t;

typedef struct
{
    uint8_t bytes[BOOT_BOOTSTRAP_COMMAND_SIZE];
} boot_bootstrap_command_t;

typedef struct
{
    int (*eeprom_write)(void *ctx, uint8_t address,
                        const uint8_t *src, uint16_t len);
    int (*eeprom_read)(void *ctx, uint8_t address,
                       uint8_t *dst, uint16_t len);
    int (*internal_read)(void *ctx, uint32_t address,
                         uint8_t *dst, size_t len);
    int (*external_init)(void *ctx);
    int (*external_erase_4k)(void *ctx, uint32_t address);
    int (*external_program)(void *ctx, uint32_t address,
                            const uint8_t *src, size_t len);
    int (*external_read)(void *ctx, uint32_t address,
                         uint8_t *dst, size_t len);
    void *ctx;
} boot_bootstrap_io_t;

extern volatile boot_bootstrap_command_t g_boot_bootstrap_command;

boot_bootstrap_result_t boot_bootstrap_process(const boot_bootstrap_io_t *io);

#ifdef __cplusplus
}
#endif

#endif
