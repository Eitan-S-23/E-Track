#ifndef E_TRACK_BOOT_FW_HEADER_H
#define E_TRACK_BOOT_FW_HEADER_H

#include <stddef.h>
#include <stdint.h>

#include "OTA/ota_layout.h"

#ifdef __cplusplus
extern "C" {
#endif

#define BOOT_FW_HEADER_VERSION 1u
#define BOOT_FW_HARDWARE_REV   1u
#define BOOT_FW_LAYOUT_ID      1u
#define BOOT_VERSION           1u

typedef int (*boot_image_read_fn)(void *ctx, uint32_t offset, uint8_t *dst, size_t len);

typedef struct
{
    boot_image_read_fn read;
    void *ctx;
} boot_image_reader_t;

typedef struct
{
    uint32_t hardware_rev;
    uint8_t layout_id;
    uint8_t boot_version;
    uint32_t ram_start;
    uint32_t ram_end;
    uint32_t app_start;
    uint32_t app_end;
} boot_fw_expectations_t;

typedef struct
{
    uint32_t header_version;
    uint32_t version_code;
    char version_name[17];
    uint32_t build_timestamp;
    uint32_t hardware_rev;
    uint32_t image_len;
    uint8_t image_sha256[32];
    uint8_t layout_id;
    uint8_t min_boot_version;
    uint32_t initial_msp;
    uint32_t reset_handler;
} boot_fw_header_t;

typedef enum
{
    BOOT_FW_OK = 0,
    BOOT_FW_ERR_ARGUMENT,
    BOOT_FW_ERR_READ,
    BOOT_FW_ERR_MAGIC,
    BOOT_FW_ERR_HEADER_VERSION,
    BOOT_FW_ERR_HEADER_CRC,
    BOOT_FW_ERR_IMAGE_LENGTH,
    BOOT_FW_ERR_VERSION_NAME,
    BOOT_FW_ERR_PADDING,
    BOOT_FW_ERR_IMAGE_SHA,
    BOOT_FW_ERR_HARDWARE_REV,
    BOOT_FW_ERR_LAYOUT_ID,
    BOOT_FW_ERR_MIN_BOOT_VERSION,
    BOOT_FW_ERR_VECTOR_MSP,
    BOOT_FW_ERR_VECTOR_RESET
} boot_fw_result_t;

#define BOOT_FW_VALIDATE_VECTORS 0x00000001u

void boot_fw_default_expectations(boot_fw_expectations_t *out);
boot_fw_result_t boot_fw_header_validate_ex(
    const boot_image_reader_t *reader,
    const boot_fw_expectations_t *expected,
    uint32_t validation_flags,
    boot_fw_header_t *out_header);
boot_fw_result_t boot_fw_header_validate(const boot_image_reader_t *reader,
                                         const boot_fw_expectations_t *expected,
                                         boot_fw_header_t *out_header);
const char *boot_fw_result_name(boot_fw_result_t result);

#ifdef __cplusplus
}
#endif

#endif
