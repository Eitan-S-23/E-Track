#include "ota_pipeline_sync.h"

#if defined(P34_OTA_PIPELINE_SYNC) && P34_OTA_PIPELINE_SYNC
static int sync_start(void *ctx, uint32_t operation, uint32_t address,
    const uint8_t *src, uint32_t len)
{
    ota_staging_io_t *io = (ota_staging_io_t *)ctx;
    const uint32_t base = OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET;
    const uint32_t capacity = OTA_EXT_STAGING_LENGTH - OTA_STAGING_PAYLOAD_OFFSET;
    int result;
    if (io == 0 || address < base || len == 0u || len > capacity ||
        address - base > capacity - len) return OTA_PIPELINE_ERR_PARAM;
    if (operation == OTA_PIPELINE_ERASE)
    {
        if (src != 0 || len != OTA_STAGING_BLOCK_SIZE ||
            address % OTA_STAGING_BLOCK_SIZE != 0u) return OTA_PIPELINE_ERR_PARAM;
        result = io->erase_4k(io->ctx, address);
    }
    else if (operation == OTA_PIPELINE_PROGRAM)
    {
        if (src == 0 || len > OTA_PIPELINE_PROGRAM_SIZE ||
            address % OTA_STAGING_BLOCK_SIZE != 0u) return OTA_PIPELINE_ERR_PARAM;
        result = io->program(io->ctx, address, src, len);
    }
    else return OTA_PIPELINE_ERR_PARAM;
    return result == 0 ? OTA_PIPELINE_OK : OTA_PIPELINE_ERR_IO;
}

static int sync_poll(void *ctx)
{
    (void)ctx;
    return OTA_PIPELINE_OK;
}

static void sync_cancel(void *ctx)
{
    (void)ctx;
}

int ota_pipeline_sync_init(ota_pipeline_io_t *out, ota_staging_io_t *staging)
{
    if (out == 0) return OTA_PIPELINE_ERR_PARAM;
    out->ctx = 0;
    out->start = 0;
    out->poll = 0;
    out->cancel = 0;
    if (staging == 0 || staging->erase_4k == 0 || staging->program == 0)
        return OTA_PIPELINE_ERR_PARAM;
    out->ctx = staging;
    out->start = sync_start;
    out->poll = sync_poll;
    out->cancel = sync_cancel;
    return OTA_PIPELINE_OK;
}
#endif
