#include "ota_pipeline.h"

#if defined(P34_OTA_PIPELINE) && P34_OTA_PIPELINE
#include <string.h>

#define PIPE_GUARD 0x50325045u
enum { PIPE_IDLE, PIPE_ERASE, PIPE_PROGRAM, PIPE_VERIFY };

static uint32_t block_length(const ota_pipeline_t *pipe, uint32_t offset)
{
    uint32_t left = pipe->store.total_len - offset;
    return left < OTA_STAGING_BLOCK_SIZE ? left : OTA_STAGING_BLOCK_SIZE;
}

static unsigned slot_index(uint32_t offset)
{
    return (unsigned)((offset / OTA_STAGING_BLOCK_SIZE) % OTA_PIPELINE_BLOCKS);
}

static uint8_t *slot_data(ota_pipeline_t *pipe, unsigned index)
{
    return index == 0u ? pipe->store.block : (uint8_t *)pipe->second_block;
}

static uint32_t credit_end(const ota_pipeline_t *pipe)
{
    uint32_t end = pipe->store.durable_off + OTA_PIPELINE_BLOCKS * OTA_STAGING_BLOCK_SIZE;
    return end < pipe->store.total_len ? end : pipe->store.total_len;
}

static void encode_u32(uint8_t *out, uint32_t value)
{
    out[0] = (uint8_t)value;
    out[1] = (uint8_t)(value >> 8);
    out[2] = (uint8_t)(value >> 16);
    out[3] = (uint8_t)(value >> 24);
}

int ota_pipeline_capabilities(uint32_t nonce, uint8_t out[OTA_PIPELINE_CAPS_BYTES])
{
    if (nonce == 0u || out == 0) return OTA_PIPELINE_ERR_PARAM;
    memcpy(out, "P2BL", 4u);
    out[4] = OTA_PIPELINE_VERSION;
    out[5] = OTA_PIPELINE_BLOCKS;
    out[6] = (uint8_t)OTA_STAGING_SEGMENT_SIZE;
    out[7] = 0u;
    encode_u32(out + 8u, nonce);
    encode_u32(out + 12u, OTA_PIPELINE_MAX_IN_FLIGHT);
    return OTA_PIPELINE_OK;
}

int ota_pipeline_ack_encode(const ota_pipeline_t *pipe, uint8_t out[OTA_PIPELINE_ACK_BYTES])
{
    ota_pipeline_ack_t ack;
    int result;
    if (out == 0) return OTA_PIPELINE_ERR_PARAM;
    result = ota_pipeline_snapshot(pipe, &ack);
    if (result != OTA_PIPELINE_OK) return result;
    encode_u32(out, ack.epoch);
    encode_u32(out + 4u, ack.durable_off);
    encode_u32(out + 8u, ack.accepted_off);
    encode_u32(out + 12u, ack.credit_end);
    return OTA_PIPELINE_OK;
}

static int fail(ota_pipeline_t *pipe, int error)
{
    if (!pipe->stopped)
    {
        pipe->stopped = 1u;
        pipe->error = error;
        if (pipe->pending) pipe->io.cancel(pipe->io.ctx);
    }
    return pipe->error;
}

int ota_pipeline_can_release(const ota_pipeline_t *pipe)
{
    return pipe != 0 && (pipe->guard != PIPE_GUARD || !pipe->pending);
}

int ota_pipeline_begin(ota_pipeline_t *pipe, const ota_staging_io_t *store_io,
    const ota_pipeline_io_t *payload_io, uint32_t epoch,
    const uint8_t sha256[32], uint32_t total_len)
{
    ota_staging_progress_t progress;
    if (pipe == 0 || payload_io == 0 || payload_io->start == 0 ||
        payload_io->poll == 0 || payload_io->cancel == 0 || epoch == 0u)
        return OTA_PIPELINE_ERR_PARAM;
    if (!ota_pipeline_can_release(pipe)) return OTA_PIPELINE_BUSY;
    memset(pipe, 0, sizeof(*pipe));
    pipe->guard = PIPE_GUARD;
    pipe->stopped = 1u;
    pipe->error = OTA_PIPELINE_ERR_IO;
    if (ota_staging_begin(&pipe->store, store_io, sha256, total_len, &progress) != OTA_STAGING_OK)
        return pipe->error;
    pipe->io = *payload_io;
    pipe->epoch = epoch;
    pipe->accepted_off = progress.durable_off;
    pipe->stopped = 0u;
    pipe->error = 0;
    return OTA_PIPELINE_OK;
}

int ota_pipeline_snapshot(const ota_pipeline_t *pipe, ota_pipeline_ack_t *ack)
{
    if (pipe == 0 || ack == 0 || pipe->guard != PIPE_GUARD) return OTA_PIPELINE_ERR_PARAM;
    if (pipe->stopped)
        return pipe->error < 0 ? pipe->error : OTA_PIPELINE_ERR_STOPPED;
    ack->epoch = pipe->epoch;
    ack->durable_off = pipe->store.durable_off;
    ack->accepted_off = pipe->accepted_off;
    ack->credit_end = credit_end(pipe);
    return OTA_PIPELINE_OK;
}

int ota_pipeline_receive(ota_pipeline_t *pipe, uint32_t epoch, uint32_t offset,
    const uint8_t *data, uint32_t len)
{
    uint32_t expected, start;
    unsigned index;
    ota_pipeline_slot_t *slot;
    if (pipe == 0 || pipe->guard != PIPE_GUARD || data == 0) return OTA_PIPELINE_ERR_PARAM;
    if (pipe->stopped) return pipe->error;
    if (epoch != pipe->epoch) return OTA_PIPELINE_ERR_EPOCH;
    if (offset >= pipe->store.total_len || offset % OTA_STAGING_SEGMENT_SIZE != 0u)
        return OTA_PIPELINE_ERR_PARAM;
    expected = pipe->store.total_len - offset;
    if (expected > OTA_STAGING_SEGMENT_SIZE) expected = OTA_STAGING_SEGMENT_SIZE;
    if (len != expected) return OTA_PIPELINE_ERR_PARAM;
    if (offset < pipe->store.durable_off) return OTA_PIPELINE_DUPLICATE;
    if (offset > pipe->accepted_off || offset + len > credit_end(pipe))
        return OTA_PIPELINE_ERR_CREDIT;
    start = offset & ~(OTA_STAGING_BLOCK_SIZE - 1u);
    index = slot_index(offset);
    slot = &pipe->slots[index];
    if (offset < pipe->accepted_off)
    {
        if (slot->offset != start || offset + len > start + slot->received ||
            memcmp(slot_data(pipe, index) + offset - start, data, len) != 0)
            return fail(pipe, OTA_PIPELINE_ERR_DATA);
        return OTA_PIPELINE_DUPLICATE;
    }
    if (slot->received == 0u) slot->offset = start;
    if (slot->offset != start || slot->ready || slot->received != offset - start)
        return fail(pipe, OTA_PIPELINE_ERR_DATA);
    memcpy(slot_data(pipe, index) + slot->received, data, len);
    slot->received += len;
    pipe->accepted_off += len;
    slot->ready = slot->received == block_length(pipe, start) ? 1u : 0u;
    return OTA_PIPELINE_OK;
}

void ota_pipeline_abort(ota_pipeline_t *pipe)
{
    if (pipe != 0 && pipe->guard == PIPE_GUARD) (void)fail(pipe, OTA_PIPELINE_ERR_STOPPED);
}

static int operation_done(ota_pipeline_t *pipe)
{
    if (pipe->phase == PIPE_ERASE)
    {
        pipe->phase = PIPE_PROGRAM;
        pipe->cursor = 0u;
    }
    else if (pipe->phase == PIPE_PROGRAM)
    {
        pipe->cursor += pipe->operation_len;
        if (pipe->cursor == block_length(pipe, pipe->store.durable_off)) pipe->phase = PIPE_VERIFY;
    }
    return OTA_PIPELINE_BUSY;
}

int ota_pipeline_poll(ota_pipeline_t *pipe, uint32_t now_ms)
{
    int result;
    unsigned index;
    uint32_t address, len;
    const uint8_t *src = 0;
    if (pipe == 0 || pipe->guard != PIPE_GUARD) return OTA_PIPELINE_ERR_PARAM;
#if defined(P34_OTA_PIPELINE_WAIT_RX) && P34_OTA_PIPELINE_WAIT_RX
    /* Receive-only callbacks may abort, but cannot settle or restart this IO. */
    if (pipe->in_start) return OTA_PIPELINE_BUSY;
#endif
    if (pipe->pending)
    {
        result = pipe->io.poll(pipe->io.ctx);
        if (result == OTA_PIPELINE_BUSY)
        {
            if (!pipe->stopped && (uint32_t)(now_ms - pipe->operation_started) >= OTA_PIPELINE_OP_TIMEOUT_MS)
                (void)fail(pipe, OTA_PIPELINE_ERR_TIMEOUT);
            return pipe->stopped ? pipe->error : OTA_PIPELINE_BUSY;
        }
        pipe->pending = 0u;
        if (result != OTA_PIPELINE_OK) return fail(pipe, OTA_PIPELINE_ERR_IO);
        if (pipe->stopped) return pipe->error;
        return operation_done(pipe);
    }
    if (pipe->stopped) return pipe->error;
    if (pipe->store.durable_off == pipe->store.total_len) return OTA_PIPELINE_COMPLETE;
    index = slot_index(pipe->store.durable_off);
    if (pipe->phase == PIPE_IDLE)
    {
        if (!pipe->slots[index].ready) return OTA_PIPELINE_OK;
        if (pipe->slots[index].offset != pipe->store.durable_off) return fail(pipe, OTA_PIPELINE_ERR_DATA);
        pipe->phase = PIPE_ERASE;
    }
    if (pipe->phase == PIPE_VERIFY)
    {
        ota_staging_progress_t progress;
        result = (int)ota_staging_commit_buffer(&pipe->store, pipe->store.durable_off,
            slot_data(pipe, index), pipe->slots[index].received, &progress);
        if (result != OTA_STAGING_BLOCK_COMMITTED && result != OTA_STAGING_PACKAGE_COMPLETE)
            return fail(pipe, OTA_PIPELINE_ERR_IO);
        memset(&pipe->slots[index], 0, sizeof(pipe->slots[index]));
        pipe->phase = PIPE_IDLE;
        return result == OTA_STAGING_PACKAGE_COMPLETE ? OTA_PIPELINE_COMPLETE : OTA_PIPELINE_COMMITTED;
    }
    address = OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET + pipe->store.durable_off;
    len = OTA_STAGING_BLOCK_SIZE;
    if (pipe->phase == PIPE_PROGRAM)
    {
        len = block_length(pipe, pipe->store.durable_off) - pipe->cursor;
        if (len > OTA_PIPELINE_PROGRAM_SIZE) len = OTA_PIPELINE_PROGRAM_SIZE;
        address += pipe->cursor;
        src = slot_data(pipe, index) + pipe->cursor;
    }
    pipe->operation_len = len;
    pipe->operation_started = now_ms;
#if defined(P34_OTA_PIPELINE_WAIT_RX) && P34_OTA_PIPELINE_WAIT_RX
    pipe->pending = 1u;
    pipe->in_start = 1u;
#endif
    result = pipe->io.start(pipe->io.ctx,
        pipe->phase == PIPE_ERASE ? OTA_PIPELINE_ERASE : OTA_PIPELINE_PROGRAM, address, src, len);
#if defined(P34_OTA_PIPELINE_WAIT_RX) && P34_OTA_PIPELINE_WAIT_RX
    pipe->in_start = 0u;
#endif
    if (result == OTA_PIPELINE_BUSY)
    {
        pipe->pending = 1u;
        return OTA_PIPELINE_BUSY;
    }
#if defined(P34_OTA_PIPELINE_WAIT_RX) && P34_OTA_PIPELINE_WAIT_RX
    pipe->pending = 0u;
    if (pipe->stopped) return pipe->error;
#endif
    if (result != OTA_PIPELINE_OK) return fail(pipe, OTA_PIPELINE_ERR_IO);
    return operation_done(pipe);
}
#endif
