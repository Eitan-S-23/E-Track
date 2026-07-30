#include "OTA/ota_package.h"

#include "OTA/ota_keys.h"
#include "boot_crypto.h"
#include "boot_fw_header.h"
#include "LzmaDec.h"
#include "tiny_AES_decrypt.h"

#include <stddef.h>
#include <stdint.h>
#include <string.h>

enum
{
    ETU_HEADER_LEN_OFF = 4,
    ETU_FLAGS_OFF = 6,
    ETU_ALGORITHM_OFF = 8,
    ETU_KEY_ID_OFF = 12,
    ETU_NONCE_OFF = 16,
    ETU_PAYLOAD_LEN_OFF = 32,
    ETU_PAYLOAD_CRC_OFF = 36,
    ETU_TARGET_VCODE_OFF = 40,
    ETU_BASE_VCODE_OFF = 44,
    ETU_HARDWARE_REV_OFF = 48,
    ETU_LAYOUT_ID_OFF = 50,
    ETU_MIN_BOOT_OFF = 51,
    ETU_BASE_SHA8_OFF = 52,
    ETU_HEADER_CRC_OFF = 60,
    ETU_HEADER_CRC_LEN = 60,
    LZMA_ALONE_HEADER_SIZE = 13,
    LZMA_DICTIONARY_MIN = 4096,
    LZMA_DICTIONARY_MAX = 16384,
    ARENA_ALIGNMENT = 8
};

typedef struct ota_outer_header_t
{
    uint32_t key_id;
    uint32_t payload_len;
    uint32_t payload_crc32;
    uint32_t target_vcode;
    uint8_t nonce[16];
} ota_outer_header_t;

typedef struct ota_arena_t
{
    ISzAlloc allocator;
    uint8_t *base;
    size_t capacity;
    size_t used;
    size_t peak;
} ota_arena_t;

typedef struct ota_workspace_state_t
{
    ota_arena_t arena;
    AES_ctx aes;
    CLzmaDec lzma;
    uint8_t key[OTA_AES128_KEY_SIZE];
    uint8_t counter[16];
    uint8_t keystream[16];
    uint8_t keystream_pos;
    uint8_t input[OTA_PACKAGE_INPUT_SIZE];
    uint8_t output[OTA_PACKAGE_OUTPUT_SIZE];
    uint8_t verify[OTA_PACKAGE_OUTPUT_SIZE];
    uint32_t input_pos;
    uint32_t input_len;
    uint32_t cipher_read;
} ota_workspace_state_t;

typedef struct ota_candidate_reader_t
{
    const ota_package_io_t *io;
} ota_candidate_reader_t;

static uint16_t read_u16le(const uint8_t *src)
{
    return (uint16_t)((uint16_t)src[0] | ((uint16_t)src[1] << 8));
}

static uint32_t read_u32le(const uint8_t *src)
{
    return (uint32_t)src[0] |
           ((uint32_t)src[1] << 8) |
           ((uint32_t)src[2] << 16) |
           ((uint32_t)src[3] << 24);
}

static uint64_t read_u64le(const uint8_t *src)
{
    uint64_t value = 0u;
    uint32_t index;

    for (index = 0u; index < 8u; ++index)
    {
        value |= (uint64_t)src[index] << (index * 8u);
    }
    return value;
}

static int all_zero(const uint8_t *src, uint32_t len)
{
    uint32_t index;

    for (index = 0u; index < len; ++index)
    {
        if (src[index] != 0u)
        {
            return 0;
        }
    }
    return 1;
}

static void secure_zero(void *memory, size_t len)
{
    volatile uint8_t *bytes = (volatile uint8_t *)memory;

    while (len != 0u)
    {
        *bytes++ = 0u;
        --len;
    }
}

static size_t align_up(size_t value, size_t alignment)
{
    return (value + alignment - 1u) & ~(alignment - 1u);
}

static void *arena_alloc(ISzAllocPtr allocator, size_t size)
{
    ota_arena_t *arena = (ota_arena_t *)allocator;
    size_t aligned_size;
    void *result;

    if (size == 0u)
    {
        return 0;
    }
    aligned_size = align_up(size, ARENA_ALIGNMENT);
    if (aligned_size > arena->capacity - arena->used)
    {
        return 0;
    }
    result = arena->base + arena->used;
    arena->used += aligned_size;
    if (arena->used > arena->peak)
    {
        arena->peak = arena->used;
    }
    return result;
}

static void arena_free(ISzAllocPtr allocator, void *address)
{
    (void)allocator;
    (void)address;
}

static void increment_counter(uint8_t counter[16])
{
    int index;

    for (index = 15; index >= 0; --index)
    {
        ++counter[index];
        if (counter[index] != 0u)
        {
            break;
        }
    }
}

static void aes_stream_init(ota_workspace_state_t *state,
                            const uint8_t nonce[16])
{
    AES_init_ctx(&state->aes, state->key);
    memcpy(state->counter, nonce, sizeof(state->counter));
    state->keystream_pos = sizeof(state->keystream);
}

static void aes_stream_xcrypt(ota_workspace_state_t *state,
                              uint8_t *data, uint32_t len)
{
    uint32_t index;

    for (index = 0u; index < len; ++index)
    {
        if (state->keystream_pos >= sizeof(state->keystream))
        {
            memcpy(state->keystream, state->counter,
                   sizeof(state->keystream));
            AES_encrypt_block(&state->aes, state->keystream);
            increment_counter(state->counter);
            state->keystream_pos = 0u;
        }
        data[index] ^= state->keystream[state->keystream_pos++];
    }
}

static ota_package_result_t parse_outer_header(
    const uint8_t raw[OTA_PACKAGE_HEADER_SIZE],
    const ota_package_device_t *device,
    uint32_t package_len,
    ota_outer_header_t *header)
{
    uint32_t payload_len;

    if (memcmp(raw, "ETU1", 4u) != 0)
    {
        return OTA_PACKAGE_ERR_MAGIC;
    }
    if (read_u16le(raw + ETU_HEADER_LEN_OFF) != OTA_PACKAGE_HEADER_SIZE)
    {
        return OTA_PACKAGE_ERR_HEADER_LENGTH;
    }
    if (boot_crc32(raw, ETU_HEADER_CRC_LEN) !=
        read_u32le(raw + ETU_HEADER_CRC_OFF))
    {
        return OTA_PACKAGE_ERR_HEADER_CRC;
    }
    if (read_u16le(raw + ETU_FLAGS_OFF) != OTA_PACKAGE_FULL_FLAGS)
    {
        return OTA_PACKAGE_ERR_FLAGS;
    }
    if (read_u32le(raw + ETU_ALGORITHM_OFF) != 1u)
    {
        return OTA_PACKAGE_ERR_ALGORITHM;
    }
    if (read_u32le(raw + ETU_KEY_ID_OFF) != 1u)
    {
        return OTA_PACKAGE_ERR_KEY;
    }
    if (read_u16le(raw + ETU_HARDWARE_REV_OFF) != device->hardware_rev)
    {
        return OTA_PACKAGE_ERR_HARDWARE;
    }
    if (raw[ETU_LAYOUT_ID_OFF] != device->layout_id)
    {
        return OTA_PACKAGE_ERR_LAYOUT;
    }
    if (raw[ETU_MIN_BOOT_OFF] > device->boot_version)
    {
        return OTA_PACKAGE_ERR_MIN_BOOT;
    }
    if (read_u32le(raw + ETU_TARGET_VCODE_OFF) <= device->current_vcode)
    {
        return OTA_PACKAGE_ERR_VERSION;
    }
    if (read_u32le(raw + ETU_BASE_VCODE_OFF) != 0u ||
        !all_zero(raw + ETU_BASE_SHA8_OFF, 8u))
    {
        return OTA_PACKAGE_ERR_BASE;
    }

    payload_len = read_u32le(raw + ETU_PAYLOAD_LEN_OFF);
    if (payload_len == 0u ||
        payload_len > OTA_ETU_MAX_LENGTH - OTA_PACKAGE_HEADER_SIZE ||
        package_len != OTA_PACKAGE_HEADER_SIZE + payload_len)
    {
        return OTA_PACKAGE_ERR_PACKAGE_LENGTH;
    }

    header->key_id = read_u32le(raw + ETU_KEY_ID_OFF);
    header->payload_len = payload_len;
    header->payload_crc32 = read_u32le(raw + ETU_PAYLOAD_CRC_OFF);
    header->target_vcode = read_u32le(raw + ETU_TARGET_VCODE_OFF);
    memcpy(header->nonce, raw + ETU_NONCE_OFF, sizeof(header->nonce));
    return OTA_PACKAGE_OK;
}

static ota_package_result_t validate_payload_crc(
    const ota_package_io_t *io,
    const ota_outer_header_t *header)
{
    uint8_t buffer[256];
    boot_crc32_ctx_t crc;
    uint32_t offset = 0u;

    boot_crc32_init(&crc);
    while (offset < header->payload_len)
    {
        uint32_t take = header->payload_len - offset;
        if (take > sizeof(buffer))
        {
            take = sizeof(buffer);
        }
        if (io->package_read(io->ctx, OTA_PACKAGE_HEADER_SIZE + offset,
                             buffer, take) != 0)
        {
            return OTA_PACKAGE_ERR_READ;
        }
        boot_crc32_update(&crc, buffer, take);
        offset += take;
    }
    return boot_crc32_final(&crc) == header->payload_crc32
               ? OTA_PACKAGE_OK
               : OTA_PACKAGE_ERR_PAYLOAD_CRC;
}

static int stream_append(const ota_package_io_t *io,
                         const ota_outer_header_t *header,
                         ota_workspace_state_t *state)
{
    uint32_t remain;
    uint32_t take;

    if (state->input_pos != 0u)
    {
        if (state->input_pos < state->input_len)
        {
            memmove(state->input, state->input + state->input_pos,
                    state->input_len - state->input_pos);
            state->input_len -= state->input_pos;
        }
        else
        {
            state->input_len = 0u;
        }
        state->input_pos = 0u;
    }
    if (state->cipher_read >= header->payload_len ||
        state->input_len >= sizeof(state->input))
    {
        return 0;
    }

    remain = header->payload_len - state->cipher_read;
    take = (uint32_t)sizeof(state->input) - state->input_len;
    if (take > remain)
    {
        take = remain;
    }
    if (io->package_read(io->ctx,
                         OTA_PACKAGE_HEADER_SIZE + state->cipher_read,
                         state->input + state->input_len, take) != 0)
    {
        return -1;
    }
    aes_stream_xcrypt(state, state->input + state->input_len, take);
    state->input_len += take;
    state->cipher_read += take;
    return 1;
}

static int stream_read_exact(const ota_package_io_t *io,
                             const ota_outer_header_t *header,
                             ota_workspace_state_t *state,
                             uint8_t *dst, uint32_t len)
{
    uint32_t copied = 0u;

    while (copied < len)
    {
        uint32_t available;
        uint32_t take;

        if (state->input_pos == state->input_len &&
            stream_append(io, header, state) <= 0)
        {
            return -1;
        }
        available = state->input_len - state->input_pos;
        take = len - copied;
        if (take > available)
        {
            take = available;
        }
        memcpy(dst + copied, state->input + state->input_pos, take);
        state->input_pos += take;
        copied += take;
    }
    return 0;
}

static ota_package_result_t parse_lzma_alone_header(
    const uint8_t raw[LZMA_ALONE_HEADER_SIZE],
    CLzmaProps *properties,
    uint32_t *image_len)
{
    uint64_t decoded_len;
    uint32_t dictionary;

    if (LzmaProps_Decode(properties, raw, LZMA_PROPS_SIZE) != SZ_OK ||
        properties->lc != 2u || properties->lp != 0u ||
        properties->pb != 0u)
    {
        return OTA_PACKAGE_ERR_LZMA_PROPERTIES;
    }
    dictionary = read_u32le(raw + 1u);
    if (dictionary < LZMA_DICTIONARY_MIN ||
        dictionary > LZMA_DICTIONARY_MAX)
    {
        return OTA_PACKAGE_ERR_LZMA_PROPERTIES;
    }
    decoded_len = read_u64le(raw + LZMA_PROPS_SIZE);
    if (decoded_len > UINT32_MAX ||
        decoded_len < OTA_FW_HEADER_OFFSET + OTA_FW_HEADER_SIZE ||
        decoded_len > OTA_APP_LENGTH)
    {
        return OTA_PACKAGE_ERR_IMAGE_LENGTH;
    }
    *image_len = (uint32_t)decoded_len;
    return OTA_PACKAGE_OK;
}

static ota_package_result_t write_candidate_chunk(
    const ota_package_io_t *io,
    uint32_t image_len,
    uint32_t offset,
    ota_workspace_state_t *state,
    uint32_t len)
{
    if (len == 0u || len > sizeof(state->output) ||
        offset > image_len || len > image_len - offset ||
        offset > OTA_APP_LENGTH || len > OTA_APP_LENGTH - offset)
    {
        return OTA_PACKAGE_ERR_IMAGE_LENGTH;
    }
    if (io->candidate_program(io->ctx, offset, state->output, len) != 0)
    {
        return OTA_PACKAGE_ERR_CANDIDATE_WRITE;
    }
    if (io->candidate_read(io->ctx, offset, state->verify, len) != 0 ||
        memcmp(state->output, state->verify, len) != 0)
    {
        return OTA_PACKAGE_ERR_CANDIDATE_VERIFY;
    }
    return OTA_PACKAGE_OK;
}

static ota_package_result_t decode_candidate(
    const ota_package_io_t *io,
    const ota_outer_header_t *header,
    ota_workspace_state_t *state,
    uint32_t image_len)
{
    uint32_t output_offset = 0u;
    ELzmaStatus status = LZMA_STATUS_NOT_SPECIFIED;

    LzmaDec_Init(&state->lzma);
    while (output_offset < image_len)
    {
        SizeT source_len;
        SizeT dest_len;
        SRes lzma_result;
        ota_package_result_t write_result;
        uint32_t remain = image_len - output_offset;
        int append_result;

        if (state->input_len - state->input_pos < LZMA_REQUIRED_INPUT_MAX &&
            state->cipher_read < header->payload_len)
        {
            append_result = stream_append(io, header, state);
            if (append_result < 0)
            {
                return OTA_PACKAGE_ERR_READ;
            }
        }
        if (state->input_pos == state->input_len)
        {
            append_result = stream_append(io, header, state);
            if (append_result < 0)
            {
                return OTA_PACKAGE_ERR_READ;
            }
            if (append_result == 0)
            {
                return OTA_PACKAGE_ERR_LZMA_DATA;
            }
        }

        source_len = state->input_len - state->input_pos;
        dest_len = remain;
        if (dest_len > sizeof(state->output))
        {
            dest_len = sizeof(state->output);
        }
        lzma_result = LzmaDec_DecodeToBuf(
            &state->lzma, state->output, &dest_len,
            state->input + state->input_pos, &source_len,
            LZMA_FINISH_ANY, &status);
        state->input_pos += (uint32_t)source_len;
        if (lzma_result != SZ_OK)
        {
            return OTA_PACKAGE_ERR_LZMA_DATA;
        }
        if (dest_len != 0u)
        {
            write_result = write_candidate_chunk(
                io, image_len, output_offset, state, (uint32_t)dest_len);
            if (write_result != OTA_PACKAGE_OK)
            {
                return write_result;
            }
            output_offset += (uint32_t)dest_len;
        }
        if (status == LZMA_STATUS_FINISHED_WITH_MARK &&
            output_offset != image_len)
        {
            return OTA_PACKAGE_ERR_IMAGE_LENGTH;
        }
        if (source_len == 0u && dest_len == 0u &&
            state->cipher_read >= header->payload_len)
        {
            return OTA_PACKAGE_ERR_LZMA_DATA;
        }
    }

    for (;;)
    {
        SizeT source_len;
        SizeT dest_len = 0u;
        SRes lzma_result;
        int append_result;

        if (state->input_pos == state->input_len &&
            state->cipher_read < header->payload_len)
        {
            append_result = stream_append(io, header, state);
            if (append_result < 0)
            {
                return OTA_PACKAGE_ERR_READ;
            }
        }
        source_len = state->input_len - state->input_pos;
        if (source_len == 0u)
        {
            if (status == LZMA_STATUS_MAYBE_FINISHED_WITHOUT_MARK)
            {
                break;
            }
            return OTA_PACKAGE_ERR_LZMA_DATA;
        }
        lzma_result = LzmaDec_DecodeToBuf(
            &state->lzma, state->output, &dest_len,
            state->input + state->input_pos, &source_len,
            LZMA_FINISH_END, &status);
        state->input_pos += (uint32_t)source_len;
        if (lzma_result != SZ_OK || dest_len != 0u)
        {
            return OTA_PACKAGE_ERR_LZMA_DATA;
        }
        if (status == LZMA_STATUS_FINISHED_WITH_MARK ||
            status == LZMA_STATUS_MAYBE_FINISHED_WITHOUT_MARK)
        {
            break;
        }
        if (source_len == 0u &&
            state->cipher_read >= header->payload_len)
        {
            return OTA_PACKAGE_ERR_LZMA_DATA;
        }
    }

    if (state->cipher_read != header->payload_len ||
        state->input_pos != state->input_len)
    {
        return OTA_PACKAGE_ERR_LZMA_DATA;
    }
    return OTA_PACKAGE_OK;
}

static int candidate_image_read(void *ctx, uint32_t offset,
                                uint8_t *dst, size_t len)
{
    ota_candidate_reader_t *reader = (ota_candidate_reader_t *)ctx;

    if (len > UINT32_MAX)
    {
        return -1;
    }
    return reader->io->candidate_read(reader->io->ctx, offset, dst,
                                      (uint32_t)len);
}

static ota_package_result_t validate_candidate_image(
    const ota_package_io_t *io,
    const ota_package_device_t *device,
    const ota_outer_header_t *outer,
    uint32_t image_len,
    ota_package_info_t *info)
{
    ota_candidate_reader_t reader_ctx;
    boot_image_reader_t reader;
    boot_fw_expectations_t expectations;
    boot_fw_header_t header;

    reader_ctx.io = io;
    reader.read = candidate_image_read;
    reader.ctx = &reader_ctx;
    expectations.hardware_rev = device->hardware_rev;
    expectations.layout_id = device->layout_id;
    expectations.boot_version = device->boot_version;
    expectations.ram_start = OTA_RAM_ORIGIN;
    expectations.ram_end = OTA_OVERLAY_ORIGIN + OTA_OVERLAY_LENGTH;
    expectations.app_start = OTA_APP_ORIGIN;
    expectations.app_end = OTA_APP_ORIGIN + OTA_APP_LENGTH;

    if (boot_fw_header_validate_ex(&reader, &expectations, 0u,
                                   &header) != BOOT_FW_OK)
    {
        return OTA_PACKAGE_ERR_FW_HEADER;
    }
    if (header.version_code != outer->target_vcode ||
        header.image_len != image_len)
    {
        return OTA_PACKAGE_ERR_IMAGE_METADATA;
    }
    info->image_len = header.image_len;
    memcpy(info->image_sha256, header.image_sha256,
           sizeof(info->image_sha256));
    return OTA_PACKAGE_OK;
}

ota_package_result_t ota_package_apply_full(
    const ota_package_io_t *io,
    const ota_package_device_t *device,
    uint32_t package_len,
    ota_package_info_t *out_info)
{
    uint8_t raw_header[OTA_PACKAGE_HEADER_SIZE];
    uint8_t lzma_header[LZMA_ALONE_HEADER_SIZE];
    ota_outer_header_t outer;
    ota_package_info_t info;
    ota_package_result_t result;
    uint8_t *workspace = 0;
    uint32_t workspace_len = 0u;
    uintptr_t aligned_address;
    size_t prefix;
    ota_workspace_state_t *state;
    CLzmaProps properties;
    uint32_t image_len = 0u;

    if (io == 0 || device == 0 || package_len < OTA_PACKAGE_HEADER_SIZE ||
        package_len > OTA_ETU_MAX_LENGTH || io->package_read == 0 ||
        io->candidate_prepare == 0 || io->candidate_program == 0 ||
        io->candidate_read == 0 || io->workspace_acquire == 0 ||
        io->workspace_release == 0)
    {
        return OTA_PACKAGE_ERR_ARGUMENT;
    }
    memset(&info, 0, sizeof(info));
    memset(&outer, 0, sizeof(outer));
    if (io->package_read(io->ctx, 0u, raw_header,
                         sizeof(raw_header)) != 0)
    {
        return OTA_PACKAGE_ERR_READ;
    }
    result = parse_outer_header(raw_header, device, package_len, &outer);
    if (result != OTA_PACKAGE_OK)
    {
        return result;
    }
    result = validate_payload_crc(io, &outer);
    if (result != OTA_PACKAGE_OK)
    {
        return result;
    }
    if (io->workspace_acquire(io->ctx, &workspace, &workspace_len) != 0)
    {
        return OTA_PACKAGE_ERR_WORKSPACE;
    }
    if (workspace == 0 || workspace_len < OTA_PACKAGE_WORKSPACE_SIZE)
    {
        if (workspace != 0)
        {
            secure_zero(workspace, workspace_len);
        }
        io->workspace_release(io->ctx, workspace, workspace_len);
        return OTA_PACKAGE_ERR_WORKSPACE;
    }

    secure_zero(workspace, workspace_len);
    aligned_address = ((uintptr_t)workspace + ARENA_ALIGNMENT - 1u) &
                      ~(uintptr_t)(ARENA_ALIGNMENT - 1u);
    prefix = (size_t)(aligned_address - (uintptr_t)workspace);
    if (prefix > workspace_len ||
        sizeof(ota_workspace_state_t) > workspace_len - prefix)
    {
        result = OTA_PACKAGE_ERR_WORKSPACE;
        goto cleanup;
    }
    state = (ota_workspace_state_t *)aligned_address;
    prefix += align_up(sizeof(*state), ARENA_ALIGNMENT);
    if (prefix > workspace_len)
    {
        result = OTA_PACKAGE_ERR_WORKSPACE;
        goto cleanup;
    }
    state->arena.allocator.Alloc = arena_alloc;
    state->arena.allocator.Free = arena_free;
    state->arena.base = workspace + prefix;
    state->arena.capacity = workspace_len - prefix;
    if (ota_keys_get_aes128(outer.key_id, state->key) != 0)
    {
        result = OTA_PACKAGE_ERR_KEY;
        goto cleanup;
    }
    aes_stream_init(state, outer.nonce);
    if (stream_read_exact(io, &outer, state, lzma_header,
                          sizeof(lzma_header)) != 0)
    {
        result = OTA_PACKAGE_ERR_READ;
        goto cleanup;
    }
    result = parse_lzma_alone_header(lzma_header, &properties, &image_len);
    if (result != OTA_PACKAGE_OK)
    {
        goto cleanup;
    }
    LzmaDec_Construct(&state->lzma);
    if (LzmaDec_Allocate(&state->lzma, lzma_header, LZMA_PROPS_SIZE,
                         &state->arena.allocator) != SZ_OK)
    {
        result = OTA_PACKAGE_ERR_WORKSPACE;
        goto cleanup;
    }
    if (state->arena.peak > state->arena.capacity)
    {
        result = OTA_PACKAGE_ERR_WORKSPACE;
        goto cleanup;
    }
    if (io->candidate_prepare(io->ctx, image_len) != 0)
    {
        result = OTA_PACKAGE_ERR_CANDIDATE_PREPARE;
        goto cleanup;
    }
    result = decode_candidate(io, &outer, state, image_len);
    if (result != OTA_PACKAGE_OK)
    {
        goto cleanup;
    }

    info.package_len = package_len;
    info.payload_len = outer.payload_len;
    info.payload_crc32 = outer.payload_crc32;
    info.target_vcode = outer.target_vcode;
    info.workspace_peak = (uint32_t)(prefix + state->arena.peak);
    result = validate_candidate_image(io, device, &outer, image_len, &info);
    if (result == OTA_PACKAGE_OK && out_info != 0)
    {
        *out_info = info;
    }

cleanup:
    secure_zero(workspace, workspace_len);
    io->workspace_release(io->ctx, workspace, workspace_len);
    return result;
}

const char *ota_package_result_name(ota_package_result_t result)
{
    switch (result)
    {
    case OTA_PACKAGE_OK: return "ok";
    case OTA_PACKAGE_ERR_ARGUMENT: return "argument";
    case OTA_PACKAGE_ERR_READ: return "read";
    case OTA_PACKAGE_ERR_MAGIC: return "magic";
    case OTA_PACKAGE_ERR_HEADER_LENGTH: return "header_length";
    case OTA_PACKAGE_ERR_HEADER_CRC: return "header_crc";
    case OTA_PACKAGE_ERR_FLAGS: return "flags";
    case OTA_PACKAGE_ERR_ALGORITHM: return "algorithm";
    case OTA_PACKAGE_ERR_KEY: return "key";
    case OTA_PACKAGE_ERR_HARDWARE: return "hardware";
    case OTA_PACKAGE_ERR_LAYOUT: return "layout";
    case OTA_PACKAGE_ERR_MIN_BOOT: return "min_boot";
    case OTA_PACKAGE_ERR_VERSION: return "version";
    case OTA_PACKAGE_ERR_BASE: return "base";
    case OTA_PACKAGE_ERR_PACKAGE_LENGTH: return "package_length";
    case OTA_PACKAGE_ERR_PAYLOAD_CRC: return "payload_crc";
    case OTA_PACKAGE_ERR_WORKSPACE: return "workspace";
    case OTA_PACKAGE_ERR_LZMA_PROPERTIES: return "lzma_properties";
    case OTA_PACKAGE_ERR_IMAGE_LENGTH: return "image_length";
    case OTA_PACKAGE_ERR_CANDIDATE_PREPARE: return "candidate_prepare";
    case OTA_PACKAGE_ERR_LZMA_DATA: return "lzma_data";
    case OTA_PACKAGE_ERR_CANDIDATE_WRITE: return "candidate_write";
    case OTA_PACKAGE_ERR_CANDIDATE_VERIFY: return "candidate_verify";
    case OTA_PACKAGE_ERR_FW_HEADER: return "fw_header";
    case OTA_PACKAGE_ERR_IMAGE_METADATA: return "image_metadata";
    default: return "unknown";
    }
}
