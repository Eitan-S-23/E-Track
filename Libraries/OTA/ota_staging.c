#include "ota_staging.h"

#include <string.h>

enum
{
    OTA_STAGING_SLOT_TYPE = 3,
    OTA_STAGING_RECEIVER_GUARD = 0x53544752u
};

static void put_u32le(uint8_t *dst, uint32_t value)
{
    dst[0] = (uint8_t)value;
    dst[1] = (uint8_t)(value >> 8);
    dst[2] = (uint8_t)(value >> 16);
    dst[3] = (uint8_t)(value >> 24);
}

static uint32_t get_u32le(const uint8_t *src)
{
    return (uint32_t)src[0] |
           ((uint32_t)src[1] << 8) |
           ((uint32_t)src[2] << 16) |
           ((uint32_t)src[3] << 24);
}

uint32_t ota_staging_crc32(const uint8_t *data, uint32_t len)
{
    uint32_t crc = 0xFFFFFFFFu;
    uint32_t index;

    if (data == 0 && len != 0u)
    {
        return 0u;
    }
    for (index = 0u; index < len; ++index)
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

static int io_valid(const ota_staging_io_t *io)
{
    return io != 0 && io->read != 0 && io->erase_4k != 0 &&
           io->program != 0;
}

static ota_staging_result_t read_exact(const ota_staging_io_t *io,
                                       uint32_t address,
                                       uint8_t *dst,
                                       uint32_t len)
{
    if (io->read(io->ctx, address, dst, len) != 0)
    {
        return OTA_STAGING_ERR_IO;
    }
    return OTA_STAGING_OK;
}

static ota_staging_result_t program_exact(const ota_staging_io_t *io,
                                          uint32_t address,
                                          const uint8_t *src,
                                          uint32_t len)
{
    if (io->program(io->ctx, address, src, len) != 0)
    {
        return OTA_STAGING_ERR_IO;
    }
    return OTA_STAGING_OK;
}

static ota_staging_result_t verify_region(const ota_staging_io_t *io,
                                          uint32_t address,
                                          const uint8_t *expected,
                                          uint32_t len)
{
    uint8_t observed[128];
    uint32_t offset = 0u;

    while (offset < len)
    {
        uint32_t take = len - offset;

        if (take > sizeof(observed))
        {
            take = sizeof(observed);
        }
        if (io->read(io->ctx, address + offset, observed, take) != 0)
        {
            return OTA_STAGING_ERR_IO;
        }
        if (memcmp(observed, expected + offset, take) != 0)
        {
            return OTA_STAGING_ERR_VERIFY;
        }
        offset += take;
    }
    return OTA_STAGING_OK;
}

static ota_staging_result_t checkpoint(const ota_staging_io_t *io,
                                       uint32_t point,
                                       uint32_t arg0,
                                       uint32_t arg1)
{
    if (io->checkpoint != 0 &&
        io->checkpoint(io->ctx, point, arg0, arg1) != 0)
    {
        return OTA_STAGING_INTERRUPTED;
    }
    return OTA_STAGING_OK;
}

static uint32_t required_blocks(uint32_t total_len)
{
    return (total_len + OTA_STAGING_BLOCK_SIZE - 1u) /
           OTA_STAGING_BLOCK_SIZE;
}

static int bitmap_bit_is_clear(const uint8_t bitmap[OTA_STAGING_BITMAP_SIZE],
                               uint32_t block)
{
    return (bitmap[block >> 3] & (uint8_t)(1u << (block & 7u))) == 0u;
}

static ota_staging_result_t bitmap_durable_off(
    const uint8_t bitmap[OTA_STAGING_BITMAP_SIZE],
    uint32_t total_len,
    uint32_t *durable_off)
{
    uint32_t blocks = required_blocks(total_len);
    uint32_t first_pending = blocks;
    uint32_t block;

    for (block = 0u; block < blocks; ++block)
    {
        if (!bitmap_bit_is_clear(bitmap, block))
        {
            first_pending = block;
            break;
        }
    }
    for (block = first_pending + (first_pending < blocks ? 1u : 0u);
         block < blocks; ++block)
    {
        if (bitmap_bit_is_clear(bitmap, block))
        {
            return OTA_STAGING_ERR_STATE;
        }
    }
    for (block = blocks; block < OTA_STAGING_BITMAP_SIZE * 8u; ++block)
    {
        if (bitmap_bit_is_clear(bitmap, block))
        {
            return OTA_STAGING_ERR_STATE;
        }
    }

    *durable_off = first_pending == blocks
                       ? total_len
                       : first_pending * OTA_STAGING_BLOCK_SIZE;
    return OTA_STAGING_OK;
}

static void encode_etrj(uint8_t raw[OTA_STAGING_ETRJ_SIZE],
                        const uint8_t package_sha256[32],
                        uint32_t total_len)
{
    memcpy(raw, "ETRJ", 4u);
    memcpy(raw + 4u, package_sha256, 32u);
    put_u32le(raw + 36u, total_len);
    put_u32le(raw + 40u, ota_staging_crc32(raw, 40u));
}

static int etrj_matches(const uint8_t raw[OTA_STAGING_ETRJ_SIZE],
                        const uint8_t package_sha256[32],
                        uint32_t total_len)
{
    return memcmp(raw, "ETRJ", 4u) == 0 &&
           memcmp(raw + 4u, package_sha256, 32u) == 0 &&
           get_u32le(raw + 36u) == total_len &&
           get_u32le(raw + 40u) == ota_staging_crc32(raw, 40u);
}

static ota_staging_result_t load_matching_session(
    const ota_staging_io_t *io,
    const uint8_t package_sha256[32],
    uint32_t total_len,
    uint8_t bitmap[OTA_STAGING_BITMAP_SIZE],
    uint32_t *durable_off,
    int *matches)
{
    uint8_t etrj[OTA_STAGING_ETRJ_SIZE];
    ota_staging_result_t result;

    result = read_exact(io, OTA_EXT_STAGING + OTA_STAGING_ETRJ_OFFSET,
                        etrj, sizeof(etrj));
    if (result != OTA_STAGING_OK)
    {
        return result;
    }
    *matches = etrj_matches(etrj, package_sha256, total_len);
    if (!*matches)
    {
        return OTA_STAGING_OK;
    }
    result = read_exact(io, OTA_EXT_STAGING + OTA_STAGING_BITMAP_OFFSET,
                        bitmap, OTA_STAGING_BITMAP_SIZE);
    if (result != OTA_STAGING_OK)
    {
        return result;
    }
    result = bitmap_durable_off(bitmap, total_len, durable_off);
    if (result == OTA_STAGING_ERR_STATE)
    {
        *matches = 0;
        return OTA_STAGING_OK;
    }
    return result;
}

static ota_staging_result_t rebuild_session(
    const ota_staging_io_t *io,
    const uint8_t package_sha256[32],
    uint32_t total_len)
{
    uint8_t etrj[OTA_STAGING_ETRJ_SIZE];
    uint8_t erased[OTA_STAGING_BITMAP_SIZE];
    uint8_t marker[4];
    ota_staging_result_t result;
    uint32_t index;

    if (io->erase_4k(io->ctx, OTA_EXT_STAGING) != 0)
    {
        return OTA_STAGING_ERR_IO;
    }
    encode_etrj(etrj, package_sha256, total_len);
    result = program_exact(io, OTA_EXT_STAGING + OTA_STAGING_ETRJ_OFFSET,
                           etrj, sizeof(etrj));
    if (result != OTA_STAGING_OK)
    {
        return result;
    }
    result = verify_region(io, OTA_EXT_STAGING + OTA_STAGING_ETRJ_OFFSET,
                           etrj, sizeof(etrj));
    if (result != OTA_STAGING_OK)
    {
        return result;
    }
    result = read_exact(io, OTA_EXT_STAGING + OTA_STAGING_BITMAP_OFFSET,
                        erased, sizeof(erased));
    if (result != OTA_STAGING_OK)
    {
        return result;
    }
    for (index = 0u; index < sizeof(erased); ++index)
    {
        if (erased[index] != 0xFFu)
        {
            return OTA_STAGING_ERR_VERIFY;
        }
    }
    result = read_exact(io, OTA_EXT_STAGING + 28u, marker, sizeof(marker));
    if (result != OTA_STAGING_OK)
    {
        return result;
    }
    if (get_u32le(marker) != UINT32_MAX)
    {
        return OTA_STAGING_ERR_VERIFY;
    }
    return checkpoint(io, OTA_STAGING_CP_ETRJ_READBACK, total_len, 0u);
}

static void set_progress(const ota_staging_receiver_t *receiver,
                         int resumed,
                         ota_staging_progress_t *progress)
{
    if (progress == 0)
    {
        return;
    }
    progress->durable_off = receiver->durable_off;
    progress->segment_bitmap = receiver->segment_bitmap;
    progress->resumed = (uint8_t)(resumed != 0);
    progress->complete = (uint8_t)(receiver->durable_off ==
                                   receiver->total_len);
}

ota_staging_result_t ota_staging_begin(
    ota_staging_receiver_t *receiver,
    const ota_staging_io_t *io,
    const uint8_t package_sha256[32],
    uint32_t total_len,
    ota_staging_progress_t *progress)
{
    uint8_t bitmap[OTA_STAGING_BITMAP_SIZE];
    uint32_t durable_off = 0u;
    int matches = 0;
    ota_staging_result_t result;

    if (receiver == 0 || !io_valid(io) || package_sha256 == 0)
    {
        return OTA_STAGING_ERR_PARAM;
    }
    if (total_len == 0u || total_len > OTA_ETU_MAX_LENGTH ||
        total_len > OTA_EXT_STAGING_LENGTH - OTA_STAGING_PAYLOAD_OFFSET)
    {
        return OTA_STAGING_ERR_RANGE;
    }

    result = load_matching_session(io, package_sha256, total_len,
                                   bitmap, &durable_off, &matches);
    if (result != OTA_STAGING_OK)
    {
        return result;
    }
    if (!matches)
    {
        result = rebuild_session(io, package_sha256, total_len);
        if (result != OTA_STAGING_OK)
        {
            return result;
        }
        durable_off = 0u;
    }

    memset(receiver, 0, sizeof(*receiver));
    receiver->io = *io;
    memcpy(receiver->package_sha256, package_sha256, 32u);
    receiver->total_len = total_len;
    receiver->durable_off = durable_off;
    receiver->guard = OTA_STAGING_RECEIVER_GUARD;
    memset(receiver->block, 0xFF, sizeof(receiver->block));
    set_progress(receiver, matches, progress);
    return OTA_STAGING_OK;
}

static uint32_t current_block_length(const ota_staging_receiver_t *receiver)
{
    uint32_t remaining = receiver->total_len - receiver->durable_off;

    return remaining > OTA_STAGING_BLOCK_SIZE
               ? OTA_STAGING_BLOCK_SIZE
               : remaining;
}

static uint32_t required_segment_mask(uint32_t block_len)
{
    uint32_t segments = (block_len + OTA_STAGING_SEGMENT_SIZE - 1u) /
                        OTA_STAGING_SEGMENT_SIZE;

    return segments == OTA_STAGING_SEGMENTS_PER_BLOCK
               ? UINT32_MAX
               : (1u << segments) - 1u;
}

static void discard_ram_block(ota_staging_receiver_t *receiver)
{
    receiver->segment_bitmap = 0u;
    memset(receiver->block, 0xFF, sizeof(receiver->block));
}

static ota_staging_result_t clear_persistent_block_bit(
    ota_staging_receiver_t *receiver,
    uint32_t block)
{
    uint32_t address = OTA_EXT_STAGING + OTA_STAGING_BITMAP_OFFSET +
                       (block >> 3);
    uint8_t observed;
    uint8_t committed;
    uint8_t mask = (uint8_t)(1u << (block & 7u));
    ota_staging_result_t result;

    result = read_exact(&receiver->io, address, &observed, 1u);
    if (result != OTA_STAGING_OK)
    {
        return result;
    }
    if ((observed & mask) == 0u)
    {
        return OTA_STAGING_ERR_STATE;
    }
    committed = (uint8_t)(observed & (uint8_t)~mask);
    result = program_exact(&receiver->io, address, &committed, 1u);
    if (result != OTA_STAGING_OK)
    {
        return result;
    }
    result = verify_region(&receiver->io, address, &committed, 1u);
    if (result != OTA_STAGING_OK)
    {
        return result;
    }
    return checkpoint(&receiver->io, OTA_STAGING_CP_BITMAP_READBACK,
                      block, committed);
}

static ota_staging_result_t commit_current_block(
    ota_staging_receiver_t *receiver)
{
    uint32_t block = receiver->durable_off / OTA_STAGING_BLOCK_SIZE;
    uint32_t block_len = current_block_length(receiver);
    uint32_t address = OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET +
                       block * OTA_STAGING_BLOCK_SIZE;
    ota_staging_result_t result;

    result = checkpoint(&receiver->io, OTA_STAGING_CP_BEFORE_BLOCK_ERASE,
                        block, receiver->durable_off);
    if (result != OTA_STAGING_OK)
    {
        return result;
    }
    if (receiver->io.erase_4k(receiver->io.ctx, address) != 0)
    {
        discard_ram_block(receiver);
        return OTA_STAGING_ERR_IO;
    }
    result = program_exact(&receiver->io, address, receiver->block, block_len);
    if (result != OTA_STAGING_OK)
    {
        discard_ram_block(receiver);
        return result;
    }
    result = verify_region(&receiver->io, address, receiver->block, block_len);
    if (result != OTA_STAGING_OK)
    {
        discard_ram_block(receiver);
        return result;
    }
    result = checkpoint(&receiver->io,
                        OTA_STAGING_CP_AFTER_BLOCK_READBACK,
                        block, receiver->durable_off);
    if (result != OTA_STAGING_OK)
    {
        return result;
    }
    result = clear_persistent_block_bit(receiver, block);
    if (result != OTA_STAGING_OK)
    {
        discard_ram_block(receiver);
        return result;
    }

    receiver->durable_off += block_len;
    discard_ram_block(receiver);
    return receiver->durable_off == receiver->total_len
               ? OTA_STAGING_PACKAGE_COMPLETE
               : OTA_STAGING_BLOCK_COMMITTED;
}

ota_staging_result_t ota_staging_receive(
    ota_staging_receiver_t *receiver,
    uint32_t offset,
    const uint8_t *data,
    uint32_t len,
    ota_staging_progress_t *progress)
{
    uint32_t expected_len;
    uint32_t block_offset;
    uint32_t segment;
    uint32_t segment_mask;
    ota_staging_result_t result;

    if (receiver == 0 || receiver->guard != OTA_STAGING_RECEIVER_GUARD ||
        data == 0 || len == 0u)
    {
        return OTA_STAGING_ERR_PARAM;
    }
    if ((offset & (OTA_STAGING_SEGMENT_SIZE - 1u)) != 0u ||
        offset >= receiver->total_len || len > receiver->total_len - offset)
    {
        return OTA_STAGING_ERR_RANGE;
    }
    expected_len = receiver->total_len - offset;
    if (expected_len > OTA_STAGING_SEGMENT_SIZE)
    {
        expected_len = OTA_STAGING_SEGMENT_SIZE;
    }
    if (len != expected_len)
    {
        return OTA_STAGING_ERR_RANGE;
    }
    if (offset < receiver->durable_off)
    {
        set_progress(receiver, 1, progress);
        return OTA_STAGING_DUPLICATE;
    }
    if (receiver->durable_off == receiver->total_len ||
        offset - receiver->durable_off >= OTA_STAGING_BLOCK_SIZE)
    {
        return OTA_STAGING_ERR_RANGE;
    }

    block_offset = offset - receiver->durable_off;
    segment = block_offset / OTA_STAGING_SEGMENT_SIZE;
    segment_mask = 1u << segment;
    if ((receiver->segment_bitmap & segment_mask) != 0u)
    {
        if (memcmp(receiver->block + block_offset, data, len) != 0)
        {
            return OTA_STAGING_ERR_DATA;
        }
        set_progress(receiver, 1, progress);
        return OTA_STAGING_DUPLICATE;
    }

    memcpy(receiver->block + block_offset, data, len);
    receiver->segment_bitmap |= segment_mask;
    if ((receiver->segment_bitmap &
         required_segment_mask(current_block_length(receiver))) !=
        required_segment_mask(current_block_length(receiver)))
    {
        set_progress(receiver, 0, progress);
        return OTA_STAGING_OK;
    }

    result = commit_current_block(receiver);
    set_progress(receiver, 0, progress);
    return result;
}

static void encode_etsl(uint8_t raw[28],
                        const ota_staging_receiver_t *receiver,
                        uint32_t payload_crc32,
                        uint32_t target_vcode)
{
    memset(raw, 0xFF, 28u);
    memcpy(raw, "ETSL", 4u);
    raw[4] = OTA_STAGING_SLOT_TYPE;
    put_u32le(raw + 8u, receiver->total_len);
    put_u32le(raw + 12u, payload_crc32);
    put_u32le(raw + 16u, target_vcode);
    memcpy(raw + 20u, receiver->package_sha256, 8u);
}

static int all_ff(const uint8_t *data, uint32_t len)
{
    uint32_t index;

    for (index = 0u; index < len; ++index)
    {
        if (data[index] != 0xFFu)
        {
            return 0;
        }
    }
    return 1;
}

ota_staging_result_t ota_staging_finalize(
    ota_staging_receiver_t *receiver,
    uint32_t payload_crc32,
    uint32_t target_vcode)
{
    uint8_t desired[28];
    uint8_t observed[OTA_STAGING_ETSL_SIZE];
    uint8_t bitmap[OTA_STAGING_BITMAP_SIZE];
    uint32_t durable_off = 0u;
    int matches = 0;
    ota_staging_result_t result;
    uint8_t marker[4];

    if (receiver == 0 || receiver->guard != OTA_STAGING_RECEIVER_GUARD)
    {
        return OTA_STAGING_ERR_PARAM;
    }
    if (receiver->durable_off != receiver->total_len)
    {
        return OTA_STAGING_ERR_STATE;
    }
    result = load_matching_session(&receiver->io, receiver->package_sha256,
                                   receiver->total_len, bitmap,
                                   &durable_off, &matches);
    if (result != OTA_STAGING_OK)
    {
        return result;
    }
    if (!matches || durable_off != receiver->total_len)
    {
        return OTA_STAGING_ERR_STATE;
    }

    encode_etsl(desired, receiver, payload_crc32, target_vcode);
    result = read_exact(&receiver->io, OTA_EXT_STAGING,
                        observed, sizeof(observed));
    if (result != OTA_STAGING_OK)
    {
        return result;
    }
    if (get_u32le(observed + 28u) == OTA_STAGING_COMMIT_MARKER)
    {
        return memcmp(observed, desired, sizeof(desired)) == 0
                   ? OTA_STAGING_OK
                   : OTA_STAGING_ERR_STATE;
    }
    if (get_u32le(observed + 28u) != UINT32_MAX)
    {
        return OTA_STAGING_ERR_STATE;
    }
    if (memcmp(observed, desired, sizeof(desired)) != 0)
    {
        if (!all_ff(observed, sizeof(desired)))
        {
            return OTA_STAGING_ERR_STATE;
        }
        result = program_exact(&receiver->io, OTA_EXT_STAGING,
                               desired, sizeof(desired));
        if (result != OTA_STAGING_OK)
        {
            return result;
        }
        result = verify_region(&receiver->io, OTA_EXT_STAGING,
                               desired, sizeof(desired));
        if (result != OTA_STAGING_OK)
        {
            return result;
        }
    }
    result = checkpoint(&receiver->io, OTA_STAGING_CP_ETSL_READBACK,
                        receiver->total_len, payload_crc32);
    if (result != OTA_STAGING_OK)
    {
        return result;
    }

    put_u32le(marker, OTA_STAGING_COMMIT_MARKER);
    result = program_exact(&receiver->io, OTA_EXT_STAGING + 28u,
                           marker, sizeof(marker));
    if (result != OTA_STAGING_OK)
    {
        return result;
    }
    result = verify_region(&receiver->io, OTA_EXT_STAGING + 28u,
                           marker, sizeof(marker));
    if (result != OTA_STAGING_OK)
    {
        return result;
    }
    return checkpoint(&receiver->io, OTA_STAGING_CP_MARKER_READBACK,
                      receiver->total_len, target_vcode);
}
