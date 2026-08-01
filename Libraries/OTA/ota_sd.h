#ifndef E_TRACK_OTA_SD_H
#define E_TRACK_OTA_SD_H

#include <stdint.h>

#include "OTA/ota_staging.h"
#include "boot_crypto.h"

#ifdef __cplusplus
extern "C" {
#endif

#define OTA_SD_HEADER_SIZE 64u
#define OTA_SD_FULL_FLAGS 0x000Bu
#define OTA_SD_PATCH_FLAGS 0x0007u
#define OTA_SD_BASE_SHA8_SIZE 8u
#define OTA_SD_SHA256_SIZE 32u
#define OTA_SD_TRANSFER_CHUNK_SIZE OTA_STAGING_SEGMENT_SIZE

typedef enum ota_sd_kind_t
{
    OTA_SD_KIND_FULL = 1,
    OTA_SD_KIND_PATCH = 2
} ota_sd_kind_t;

typedef enum ota_sd_result_t
{
    OTA_SD_OK = 0,
    OTA_SD_IN_PROGRESS = 1,
    OTA_SD_STAGED = 2,
    OTA_SD_ERR_ARGUMENT = -1,
    OTA_SD_ERR_READ = -2,
    OTA_SD_ERR_MAGIC = -3,
    OTA_SD_ERR_HEADER_LENGTH = -4,
    OTA_SD_ERR_HEADER_CRC = -5,
    OTA_SD_ERR_FLAGS = -6,
    OTA_SD_ERR_ALGORITHM = -7,
    OTA_SD_ERR_KEY = -8,
    OTA_SD_ERR_HARDWARE = -9,
    OTA_SD_ERR_LAYOUT = -10,
    OTA_SD_ERR_MIN_BOOT = -11,
    OTA_SD_ERR_VERSION = -12,
    OTA_SD_ERR_BASE = -13,
    OTA_SD_ERR_PACKAGE_LENGTH = -14,
    OTA_SD_ERR_PAYLOAD_CRC = -15,
    OTA_SD_ERR_STAGING = -16,
    OTA_SD_ERR_FILE_CHANGED = -17
} ota_sd_result_t;

typedef enum ota_sd_phase_t
{
    OTA_SD_PHASE_IDLE = 0,
    OTA_SD_PHASE_HASH = 1,
    OTA_SD_PHASE_STAGE = 2,
    OTA_SD_PHASE_FINALIZE = 3,
    OTA_SD_PHASE_COMPLETE = 4,
    OTA_SD_PHASE_ERROR = 5
} ota_sd_phase_t;

typedef struct ota_sd_device_t
{
    uint32_t current_vcode;
    uint32_t hardware_rev;
    uint8_t layout_id;
    uint8_t boot_version;
    uint8_t base_image_sha8[OTA_SD_BASE_SHA8_SIZE];
} ota_sd_device_t;

typedef struct ota_sd_package_info_t
{
    ota_sd_kind_t kind;
    uint16_t flags;
    uint32_t package_len;
    uint32_t payload_len;
    uint32_t payload_crc32;
    uint32_t target_vcode;
    uint32_t base_vcode;
    uint8_t base_image_sha8[OTA_SD_BASE_SHA8_SIZE];
} ota_sd_package_info_t;

typedef struct ota_sd_reader_t
{
    void *ctx;
    int (*read)(void *ctx, uint32_t offset, uint8_t *dst, uint32_t len);
    int (*size)(void *ctx, uint32_t *out_len);
} ota_sd_reader_t;

typedef struct ota_sd_transfer_t
{
    ota_sd_reader_t reader;
    ota_staging_io_t staging_io;
    ota_sd_device_t device;
    ota_sd_package_info_t info;
    ota_staging_receiver_t receiver;
    ota_staging_progress_t staging_progress;
    boot_sha256_ctx_t sha256;
    boot_crc32_ctx_t package_crc32;
    boot_crc32_ctx_t payload_crc32;
    uint8_t expected_package_sha256[OTA_SD_SHA256_SIZE];
    uint8_t package_sha256[OTA_SD_SHA256_SIZE];
    uint8_t chunk[OTA_SD_TRANSFER_CHUNK_SIZE];
    uint32_t stream_offset;
    uint32_t verified_package_crc32;
    uint32_t verified_payload_crc32;
    ota_sd_phase_t phase;
    ota_sd_result_t result;
    ota_staging_result_t staging_result;
} ota_sd_transfer_t;

int ota_sd_has_etu_extension(const char *name);

ota_sd_result_t ota_sd_inspect_header(
    const uint8_t raw[OTA_SD_HEADER_SIZE],
    uint32_t package_len,
    const ota_sd_device_t *device,
    ota_sd_package_info_t *out_info);

ota_sd_result_t ota_sd_inspect_reader(
    const ota_sd_reader_t *reader,
    uint32_t package_len,
    const ota_sd_device_t *device,
    ota_sd_package_info_t *out_info);

ota_sd_result_t ota_sd_hash_reader(
    const ota_sd_reader_t *reader,
    uint32_t package_len,
    uint8_t out_sha256[OTA_SD_SHA256_SIZE]);

ota_sd_result_t ota_sd_transfer_begin(
    ota_sd_transfer_t *transfer,
    const ota_sd_reader_t *reader,
    const ota_staging_io_t *staging_io,
    uint32_t package_len,
    const uint8_t expected_package_sha256[OTA_SD_SHA256_SIZE],
    const ota_sd_device_t *device);

ota_sd_result_t ota_sd_transfer_step(
    ota_sd_transfer_t *transfer,
    uint32_t byte_budget);

uint8_t ota_sd_transfer_percent(const ota_sd_transfer_t *transfer);
const char *ota_sd_result_name(ota_sd_result_t result);

#ifdef __cplusplus
}
#endif

#endif
