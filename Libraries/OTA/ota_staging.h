#ifndef E_TRACK_OTA_STAGING_H
#define E_TRACK_OTA_STAGING_H

#include <stdint.h>

#include "ota_layout.h"

#ifdef __cplusplus
extern "C" {
#endif

#define OTA_STAGING_ETSL_SIZE 32u
#define OTA_STAGING_ETRJ_SIZE 44u
#define OTA_STAGING_BITMAP_SIZE 64u
#define OTA_STAGING_BLOCK_SIZE 4096u
#define OTA_STAGING_SEGMENT_SIZE 128u
#define OTA_STAGING_SEGMENTS_PER_BLOCK 32u

#define OTA_STAGING_ETSL_OFFSET 0x000u
#define OTA_STAGING_ETRJ_OFFSET 0x040u
#define OTA_STAGING_BITMAP_OFFSET 0x070u
#define OTA_STAGING_PAYLOAD_OFFSET OTA_SLOT_HEADER_SIZE
#define OTA_STAGING_COMMIT_MARKER 0x434F4D54u

typedef enum ota_staging_result_t
{
    OTA_STAGING_OK = 0,
    OTA_STAGING_DUPLICATE = 1,
    OTA_STAGING_BLOCK_COMMITTED = 2,
    OTA_STAGING_PACKAGE_COMPLETE = 3,
    OTA_STAGING_INTERRUPTED = 4,
    OTA_STAGING_ERR_PARAM = -1,
    OTA_STAGING_ERR_RANGE = -2,
    OTA_STAGING_ERR_IO = -3,
    OTA_STAGING_ERR_VERIFY = -4,
    OTA_STAGING_ERR_STATE = -5,
    OTA_STAGING_ERR_DATA = -6
} ota_staging_result_t;

typedef enum ota_staging_checkpoint_t
{
    OTA_STAGING_CP_ETRJ_READBACK = 1,
    OTA_STAGING_CP_BEFORE_BLOCK_ERASE = 2,
    OTA_STAGING_CP_AFTER_BLOCK_READBACK = 3,
    OTA_STAGING_CP_BITMAP_READBACK = 4,
    OTA_STAGING_CP_ETSL_READBACK = 5,
    OTA_STAGING_CP_MARKER_READBACK = 6
} ota_staging_checkpoint_t;

typedef struct ota_staging_io_t
{
    void *ctx;
    int (*read)(void *ctx, uint32_t address, uint8_t *dst, uint32_t len);
    int (*erase_4k)(void *ctx, uint32_t address);
    int (*program)(void *ctx, uint32_t address,
                   const uint8_t *src, uint32_t len);
    int (*checkpoint)(void *ctx, uint32_t checkpoint,
                      uint32_t arg0, uint32_t arg1);
} ota_staging_io_t;

typedef struct ota_staging_progress_t
{
    uint32_t durable_off;
    uint32_t segment_bitmap;
    uint8_t resumed;
    uint8_t complete;
} ota_staging_progress_t;

typedef struct ota_staging_receiver_t
{
    ota_staging_io_t io;
    uint8_t package_sha256[32];
    uint32_t total_len;
    uint32_t durable_off;
    uint32_t segment_bitmap;
    uint32_t guard;
    uint8_t block[OTA_STAGING_BLOCK_SIZE];
} ota_staging_receiver_t;

uint32_t ota_staging_crc32(const uint8_t *data, uint32_t len);

ota_staging_result_t ota_staging_begin(
    ota_staging_receiver_t *receiver,
    const ota_staging_io_t *io,
    const uint8_t package_sha256[32],
    uint32_t total_len,
    ota_staging_progress_t *progress);

ota_staging_result_t ota_staging_receive(
    ota_staging_receiver_t *receiver,
    uint32_t offset,
    const uint8_t *data,
    uint32_t len,
    ota_staging_progress_t *progress);

ota_staging_result_t ota_staging_finalize(
    ota_staging_receiver_t *receiver,
    uint32_t payload_crc32,
    uint32_t target_vcode);

#ifdef __cplusplus
}
#endif

#endif
