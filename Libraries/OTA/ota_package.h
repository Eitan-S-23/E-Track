#ifndef E_TRACK_OTA_PACKAGE_H
#define E_TRACK_OTA_PACKAGE_H

#include <stdint.h>

#include "OTA/ota_layout.h"

#ifdef __cplusplus
extern "C" {
#endif

#define OTA_PACKAGE_HEADER_SIZE 64u
#define OTA_PACKAGE_FULL_FLAGS 0x000Bu
#define OTA_PACKAGE_WORKSPACE_SIZE OTA_OVERLAY_WORKSPACE_LENGTH
#define OTA_PACKAGE_INPUT_SIZE 4096u
#define OTA_PACKAGE_OUTPUT_SIZE 1024u

typedef enum ota_package_result_t
{
    OTA_PACKAGE_OK = 0,
    OTA_PACKAGE_ERR_ARGUMENT = -1,
    OTA_PACKAGE_ERR_READ = -2,
    OTA_PACKAGE_ERR_MAGIC = -3,
    OTA_PACKAGE_ERR_HEADER_LENGTH = -4,
    OTA_PACKAGE_ERR_HEADER_CRC = -5,
    OTA_PACKAGE_ERR_FLAGS = -6,
    OTA_PACKAGE_ERR_ALGORITHM = -7,
    OTA_PACKAGE_ERR_KEY = -8,
    OTA_PACKAGE_ERR_HARDWARE = -9,
    OTA_PACKAGE_ERR_LAYOUT = -10,
    OTA_PACKAGE_ERR_MIN_BOOT = -11,
    OTA_PACKAGE_ERR_VERSION = -12,
    OTA_PACKAGE_ERR_BASE = -13,
    OTA_PACKAGE_ERR_PACKAGE_LENGTH = -14,
    OTA_PACKAGE_ERR_PAYLOAD_CRC = -15,
    OTA_PACKAGE_ERR_WORKSPACE = -16,
    OTA_PACKAGE_ERR_LZMA_PROPERTIES = -17,
    OTA_PACKAGE_ERR_IMAGE_LENGTH = -18,
    OTA_PACKAGE_ERR_CANDIDATE_PREPARE = -19,
    OTA_PACKAGE_ERR_LZMA_DATA = -20,
    OTA_PACKAGE_ERR_CANDIDATE_WRITE = -21,
    OTA_PACKAGE_ERR_CANDIDATE_VERIFY = -22,
    OTA_PACKAGE_ERR_FW_HEADER = -23,
    OTA_PACKAGE_ERR_IMAGE_METADATA = -24
} ota_package_result_t;

typedef struct ota_package_device_t
{
    uint32_t current_vcode;
    uint32_t hardware_rev;
    uint8_t layout_id;
    uint8_t boot_version;
} ota_package_device_t;

typedef struct ota_package_io_t
{
    void *ctx;
    int (*package_read)(void *ctx, uint32_t offset,
                        uint8_t *dst, uint32_t len);
    int (*candidate_prepare)(void *ctx, uint32_t image_len);
    int (*candidate_program)(void *ctx, uint32_t offset,
                             const uint8_t *src, uint32_t len);
    int (*candidate_read)(void *ctx, uint32_t offset,
                          uint8_t *dst, uint32_t len);
    int (*workspace_acquire)(void *ctx, uint8_t **workspace,
                             uint32_t *workspace_len);
    void (*workspace_release)(void *ctx, uint8_t *workspace,
                              uint32_t workspace_len);
} ota_package_io_t;

typedef struct ota_package_info_t
{
    uint32_t package_len;
    uint32_t payload_len;
    uint32_t payload_crc32;
    uint32_t target_vcode;
    uint32_t image_len;
    uint32_t workspace_peak;
    uint8_t image_sha256[32];
} ota_package_info_t;

ota_package_result_t ota_package_apply_full(
    const ota_package_io_t *io,
    const ota_package_device_t *device,
    uint32_t package_len,
    ota_package_info_t *out_info);

const char *ota_package_result_name(ota_package_result_t result);

#ifdef __cplusplus
}
#endif

#endif
