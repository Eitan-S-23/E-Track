#ifndef E_TRACK_OTA_PIPELINE_H
#define E_TRACK_OTA_PIPELINE_H

#include "ota_staging.h"

#if defined(P34_OTA_PIPELINE) && P34_OTA_PIPELINE
#if defined(P34_STAGING_EARLY_ERASE) && P34_STAGING_EARLY_ERASE
#error Pipeline and the paused early-erase experiment are separate candidates
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define OTA_PIPELINE_VERSION 2u
#define OTA_PIPELINE_BLOCKS 2u
#define OTA_PIPELINE_OP_TIMEOUT_MS 4000u
#define OTA_PIPELINE_PAGE_SIZE 256u
#if defined(P34_OTA_PIPELINE_SYNC) && P34_OTA_PIPELINE_SYNC
/* Screening port reuses one legacy block write, including its page loop. */
#define OTA_PIPELINE_PROGRAM_SIZE OTA_STAGING_BLOCK_SIZE
#else
#define OTA_PIPELINE_PROGRAM_SIZE OTA_PIPELINE_PAGE_SIZE
#endif
#define OTA_PIPELINE_ACK_BYTES 16u
#define OTA_PIPELINE_CAPS_BYTES 16u
#define OTA_PIPELINE_MAX_IN_FLIGHT 24u

typedef enum ota_pipeline_result_t
{
    OTA_PIPELINE_OK = 0,
    OTA_PIPELINE_DUPLICATE = 1,
    OTA_PIPELINE_BUSY = 2,
    OTA_PIPELINE_COMMITTED = 3,
    OTA_PIPELINE_COMPLETE = 4,
    OTA_PIPELINE_ERR_PARAM = -1,
    OTA_PIPELINE_ERR_EPOCH = -2,
    OTA_PIPELINE_ERR_CREDIT = -3,
    OTA_PIPELINE_ERR_DATA = -4,
    OTA_PIPELINE_ERR_IO = -5,
    OTA_PIPELINE_ERR_TIMEOUT = -6,
    OTA_PIPELINE_ERR_STOPPED = -7
} ota_pipeline_result_t;

typedef enum ota_pipeline_operation_t
{
    OTA_PIPELINE_ERASE = 1,
    OTA_PIPELINE_PROGRAM = 2
} ota_pipeline_operation_t;

/* start/poll: OK means quiescent success, BUSY means operation owns src,
 * negative means quiescent failure. cancel only requests cancellation; poll
 * must settle before overlay reuse, even on timeout. Cooperative calls must
 * be bounded. The explicitly selected SYNC screening port instead inherits
 * the legacy blocking driver and never returns BUSY or retains src.
 * While BUSY, receive may run but must not touch mapped external Flash. */
typedef struct ota_pipeline_io_t
{
    void *ctx;
    int (*start)(void *ctx, uint32_t operation, uint32_t address,
                 const uint8_t *src, uint32_t len);
    int (*poll)(void *ctx);
    void (*cancel)(void *ctx);
} ota_pipeline_io_t;

typedef struct ota_pipeline_ack_t
{
    uint32_t epoch;
    uint32_t durable_off;
    uint32_t accepted_off;
    uint32_t credit_end;
} ota_pipeline_ack_t;

typedef struct ota_pipeline_slot_t
{
    uint32_t offset;
    uint32_t received;
    uint8_t ready;
} ota_pipeline_slot_t;

typedef struct ota_pipeline_t
{
    ota_staging_receiver_t store;
    uint32_t second_block[OTA_STAGING_BLOCK_SIZE / sizeof(uint32_t)];
    ota_pipeline_io_t io;
    ota_pipeline_slot_t slots[OTA_PIPELINE_BLOCKS];
    uint32_t guard;
    uint32_t epoch;
    uint32_t accepted_off;
    uint32_t cursor;
    uint32_t operation_started;
    uint32_t operation_len;
    int error;
    uint8_t phase;
    uint8_t pending;
    uint8_t stopped;
#if defined(P34_OTA_PIPELINE_WAIT_RX) && P34_OTA_PIPELINE_WAIT_RX
    uint8_t in_start;
#endif
} ota_pipeline_t;

/* Zero-initialize once. Never reinitialize while can_release() is false. */
int ota_pipeline_begin(ota_pipeline_t *pipe, const ota_staging_io_t *store_io,
    const ota_pipeline_io_t *payload_io, uint32_t epoch,
    const uint8_t sha256[32], uint32_t total_len);
int ota_pipeline_receive(ota_pipeline_t *pipe, uint32_t epoch, uint32_t offset,
    const uint8_t *data, uint32_t len);
int ota_pipeline_poll(ota_pipeline_t *pipe, uint32_t now_ms);
void ota_pipeline_abort(ota_pipeline_t *pipe);
int ota_pipeline_can_release(const ota_pipeline_t *pipe);
int ota_pipeline_snapshot(const ota_pipeline_t *pipe, ota_pipeline_ack_t *ack);
/* Payload codecs only; framing, session identity and CRC remain mandatory.
 * CAPS echoes a nonzero caller nonce; it neither opens a session nor grants credit. */
int ota_pipeline_capabilities(uint32_t nonce, uint8_t out[OTA_PIPELINE_CAPS_BYTES]);
int ota_pipeline_ack_encode(const ota_pipeline_t *pipe, uint8_t out[OTA_PIPELINE_ACK_BYTES]);

#ifdef __cplusplus
}
#endif
#endif
#endif
