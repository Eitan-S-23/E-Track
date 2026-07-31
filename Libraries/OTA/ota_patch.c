/* P2-3 差分包（flags=0x0007）流式合成。
 *
 * 集成方式为本卡核心约束（复审报告修正 2）：
 *   old   = 基版镜像按块读（MCU 侧为内部 flash XIP 直读），不复制整镜像到 RAM;
 *   patch = QSPI staging 流式 reader（4KiB 密文滑窗原地解密 + LZMA 增量解压）;
 *   new   = 1KiB 块写 QSPI candidate，写后立即回读比对。
 * 因此不调用 vendor 的 bspatch()/bspatch_patch()/vfopen()/lzma_decompress_read():
 * 前者把 new 当完整 RAM 数组（bspatch.c:72/78/89 直接写 new+newpos，且从不调用
 * stream->write），后三者把完整 patch 当连续内存。vendor 目录零改动，只复用
 * LzmaDec 与 AES 块原语。
 *
 * 校验顺序严格照契约 §2.4 ①-⑩ 与 §2.3 注（158 行），不重排、不省略。
 */
#include "OTA/ota_patch.h"

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
    /* 40B 规范化内层头字段偏移（契约 §2.3）。 */
    PH_HCRC_OFF = 0,
    PH_PSIZE_OFF = 4,
    PH_OSIZE_OFF = 8,
    PH_NSIZE_OFF = 12,
    PH_OCRC_OFF = 16,
    PH_NCRC_OFF = 20,
    PH_PROPS_OFF = 24,
    PH_PAD_OFF = 29,
    PH_PAD_LEN = 3,
    PH_ORIGINAL_SIZE_OFF = 32,
    LZMA_DICTIONARY_MIN = 4096,
    LZMA_DICTIONARY_MAX = 16384,
    /* bsdiff 控制三元组：3 × 8B sign-magnitude（offtin 语义）。 */
    PATCH_CONTROL_SIZE = 24,
    PATCH_OFFT_SIZE = 8,
    ARENA_ALIGNMENT = 8
};

typedef struct ota_patch_header_t
{
    uint32_t key_id;
    uint32_t payload_len;
    uint32_t payload_crc32;
    uint32_t target_vcode;
    uint32_t base_vcode;
    uint8_t nonce[16];
} ota_patch_header_t;

typedef struct ota_patch_inner_t
{
    uint32_t ph_psize;
    uint32_t ph_osize;
    uint32_t ph_nsize;
    uint32_t ph_ocrc;
    uint32_t ph_ncrc;
    uint8_t ph_lzma_props[LZMA_PROPS_SIZE];
    uint64_t ph_original_size;
    uint32_t control_group_count;
} ota_patch_inner_t;

typedef struct ota_arena_t
{
    ISzAlloc allocator;
    uint8_t *base;
    size_t capacity;
    size_t used;
    size_t peak;
} ota_arena_t;

/* 工作集与 ota_package.c 的 ota_workspace_state_t 逐字段同构（见 research §7.2:
 * 两份实现刻意保持机械可合并，后续统一提取 ota_stream 时无语义合并风险），
 * 差异仅为多出 patch 指令流缓冲 stream/work。 */
typedef struct ota_patch_state_t
{
    ota_arena_t arena;
    AES_ctx aes;
    CLzmaDec lzma;
    uint8_t key[OTA_AES128_KEY_SIZE];
    uint8_t counter[16];
    uint8_t keystream[16];
    uint8_t keystream_pos;
    /* staging 密文滑窗，原地解密为明文。 */
    uint8_t input[OTA_PATCH_INPUT_SIZE];
    /* LZMA 解压输出：bsdiff 指令流（控制字 / diff / extra）。 */
    uint8_t stream[OTA_PATCH_STREAM_SIZE];
    /* diff/extra 合成缓冲，也用于 candidate 回读比对。 */
    uint8_t work[OTA_PATCH_WORK_SIZE];
    uint8_t verify[OTA_PATCH_WORK_SIZE];
    uint32_t input_pos;
    uint32_t input_len;
    uint32_t cipher_read;
    uint32_t stream_pos;
    uint32_t stream_len;
    /* 已解压的 bsdiff 流字节数，对 ph_original_size。 */
    uint64_t decoded_total;
    uint64_t decoded_consumed;
    uint64_t decoded_limit;
    ELzmaStatus lzma_status;
    uint8_t lzma_done;
} ota_patch_state_t;

typedef struct ota_patch_reader_t
{
    const ota_patch_io_t *io;
} ota_patch_reader_t;

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

static uint32_t read_u32be(const uint8_t *src)
{
    return ((uint32_t)src[0] << 24) |
           ((uint32_t)src[1] << 16) |
           ((uint32_t)src[2] << 8) |
           (uint32_t)src[3];
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

static void aes_stream_init(ota_patch_state_t *state,
                            const uint8_t nonce[16])
{
    AES_init_ctx(&state->aes, state->key);
    memcpy(state->counter, nonce, sizeof(state->counter));
    state->keystream_pos = sizeof(state->keystream);
}

static void rewind_payload_stream(ota_patch_state_t *state,
                                  const ota_patch_header_t *header)
{
    aes_stream_init(state, header->nonce);
    state->input_pos = 0u;
    state->input_len = 0u;
    state->cipher_read = 0u;
    state->stream_pos = 0u;
    state->stream_len = 0u;
}

static void begin_decode_pass(ota_patch_state_t *state,
                              uint64_t decoded_limit)
{
    LzmaDec_Init(&state->lzma);
    state->stream_pos = 0u;
    state->stream_len = 0u;
    state->decoded_total = 0u;
    state->decoded_consumed = 0u;
    state->decoded_limit = decoded_limit;
    state->lzma_status = LZMA_STATUS_NOT_SPECIFIED;
    state->lzma_done = 0u;
}

static void aes_stream_xcrypt(ota_patch_state_t *state,
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

/* 外层头逐字段解析 + 契约 §2.4 ①-⑨ 有序拒绝（⑩ payload CRC 另行流式复核）。 */
static ota_patch_result_t parse_outer_header(
    const uint8_t raw[OTA_PATCH_HEADER_SIZE],
    const ota_patch_device_t *device,
    uint32_t package_len,
    ota_patch_header_t *header)
{
    uint32_t payload_len;

    if (memcmp(raw, "ETU1", 4u) != 0)
    {
        return OTA_PATCH_ERR_MAGIC;
    }
    if (read_u16le(raw + ETU_HEADER_LEN_OFF) != OTA_PATCH_HEADER_SIZE)
    {
        return OTA_PATCH_ERR_HEADER_LENGTH;
    }
    if (boot_crc32(raw, ETU_HEADER_CRC_LEN) !=
        read_u32le(raw + ETU_HEADER_CRC_OFF))
    {
        return OTA_PATCH_ERR_HEADER_CRC;
    }
    if (read_u16le(raw + ETU_FLAGS_OFF) != OTA_PATCH_FLAGS)
    {
        return OTA_PATCH_ERR_FLAGS;
    }
    if (read_u32le(raw + ETU_ALGORITHM_OFF) != 1u)
    {
        return OTA_PATCH_ERR_ALGORITHM;
    }
    if (read_u32le(raw + ETU_KEY_ID_OFF) != 1u)
    {
        return OTA_PATCH_ERR_KEY;
    }
    if (read_u16le(raw + ETU_HARDWARE_REV_OFF) != device->hardware_rev)
    {
        return OTA_PATCH_ERR_HARDWARE;
    }
    if (raw[ETU_LAYOUT_ID_OFF] != device->layout_id)
    {
        return OTA_PATCH_ERR_LAYOUT;
    }
    if (raw[ETU_MIN_BOOT_OFF] > device->boot_version)
    {
        return OTA_PATCH_ERR_MIN_BOOT;
    }
    if (read_u32le(raw + ETU_TARGET_VCODE_OFF) <= device->current_vcode)
    {
        return OTA_PATCH_ERR_VERSION;
    }
    /* ⑧ 差分基准身份：base_vcode 必须等于当前版本码，base_sha8 必须等于
     * 当前运行镜像 SHA-256 前 8B（防"同版本码不同构建"）。 */
    if (read_u32le(raw + ETU_BASE_VCODE_OFF) != device->current_vcode)
    {
        return OTA_PATCH_ERR_BASE_VCODE;
    }
    if (memcmp(raw + ETU_BASE_SHA8_OFF, device->base_image_sha8,
               OTA_PATCH_BASE_SHA8_SIZE) != 0)
    {
        return OTA_PATCH_ERR_BASE_SHA8;
    }

    payload_len = read_u32le(raw + ETU_PAYLOAD_LEN_OFF);
    if (payload_len <= OTA_PATCH_INNER_HEADER_SIZE ||
        payload_len > OTA_ETU_MAX_LENGTH - OTA_PATCH_HEADER_SIZE ||
        package_len != OTA_PATCH_HEADER_SIZE + payload_len)
    {
        return OTA_PATCH_ERR_PACKAGE_LENGTH;
    }

    header->key_id = read_u32le(raw + ETU_KEY_ID_OFF);
    header->payload_len = payload_len;
    header->payload_crc32 = read_u32le(raw + ETU_PAYLOAD_CRC_OFF);
    header->target_vcode = read_u32le(raw + ETU_TARGET_VCODE_OFF);
    header->base_vcode = read_u32le(raw + ETU_BASE_VCODE_OFF);
    memcpy(header->nonce, raw + ETU_NONCE_OFF, sizeof(header->nonce));
    return OTA_PATCH_OK;
}

/* ⑩ 覆盖加密后 payload 的 CRC32；此阶段不得擦写 candidate。 */
static ota_patch_result_t validate_payload_crc(
    const ota_patch_io_t *io,
    const ota_patch_header_t *header)
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
        if (io->package_read(io->ctx, OTA_PATCH_HEADER_SIZE + offset,
                             buffer, take) != 0)
        {
            return OTA_PATCH_ERR_READ;
        }
        boot_crc32_update(&crc, buffer, take);
        offset += take;
    }
    return boot_crc32_final(&crc) == header->payload_crc32
               ? OTA_PATCH_OK
               : OTA_PATCH_ERR_PAYLOAD_CRC;
}

/* 密文滑窗：从 staging 读 4KiB 密文，原地 AES-CTR 解密为明文。
 * 与 ota_package.c 的 stream_append 逐行同构。 */
static int stream_append(const ota_patch_io_t *io,
                         const ota_patch_header_t *header,
                         ota_patch_state_t *state)
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
                         OTA_PATCH_HEADER_SIZE + state->cipher_read,
                         state->input + state->input_len, take) != 0)
    {
        return -1;
    }
    aes_stream_xcrypt(state, state->input + state->input_len, take);
    state->input_len += take;
    state->cipher_read += take;
    return 1;
}

static int stream_read_exact(const ota_patch_io_t *io,
                             const ota_patch_header_t *header,
                             ota_patch_state_t *state,
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

/* 内层 40B 头逐字段解析（禁 struct memcpy）+ 契约 §158 第 1/2 步。 */
static ota_patch_result_t parse_inner_header(
    const uint8_t raw[OTA_PATCH_INNER_HEADER_SIZE],
    const ota_patch_header_t *outer,
    ota_patch_inner_t *inner)
{
    uint8_t zeroed[OTA_PATCH_INNER_HEADER_SIZE];
    uint32_t index;

    /* 1. ph_hcrc：本字段按全零参与，CRC32 覆盖规范化 40B 全头，BE 存储。 */
    memcpy(zeroed, raw, sizeof(zeroed));
    for (index = 0u; index < 4u; ++index)
    {
        zeroed[PH_HCRC_OFF + index] = 0u;
    }
    if (boot_crc32(zeroed, sizeof(zeroed)) != read_u32be(raw + PH_HCRC_OFF))
    {
        return OTA_PATCH_ERR_INNER_CRC;
    }

    /* 2. ph_psize 与 .etu payload_len-40 一致。 */
    inner->ph_psize = read_u32be(raw + PH_PSIZE_OFF);
    if (inner->ph_psize !=
        outer->payload_len - OTA_PATCH_INNER_HEADER_SIZE)
    {
        return OTA_PATCH_ERR_INNER_PSIZE;
    }

    for (index = 0u; index < PH_PAD_LEN; ++index)
    {
        if (raw[PH_PAD_OFF + index] != 0u)
        {
            return OTA_PATCH_ERR_INNER_PAD;
        }
    }

    inner->ph_osize = read_u32le(raw + PH_OSIZE_OFF);
    inner->ph_nsize = read_u32le(raw + PH_NSIZE_OFF);
    inner->ph_ocrc = read_u32be(raw + PH_OCRC_OFF);
    inner->ph_ncrc = read_u32be(raw + PH_NCRC_OFF);
    memcpy(inner->ph_lzma_props, raw + PH_PROPS_OFF,
           sizeof(inner->ph_lzma_props));
    inner->ph_original_size = read_u64le(raw + PH_ORIGINAL_SIZE_OFF);
    return OTA_PATCH_OK;
}

static ota_patch_result_t validate_inner_properties(
    ota_patch_inner_t *inner,
    CLzmaProps *properties)
{
    uint32_t dictionary;

    if (LzmaProps_Decode(properties, inner->ph_lzma_props,
                         LZMA_PROPS_SIZE) != SZ_OK ||
        properties->lc != 2u || properties->lp != 0u ||
        properties->pb != 0u)
    {
        return OTA_PATCH_ERR_LZMA_PROPERTIES;
    }
    dictionary = read_u32le(inner->ph_lzma_props + 1u);
    if (dictionary < LZMA_DICTIONARY_MIN ||
        dictionary > LZMA_DICTIONARY_MAX)
    {
        return OTA_PATCH_ERR_LZMA_PROPERTIES;
    }
    /* 目标镜像必须容纳 fw_header 且不超 candidate 净容量。 */
    if (inner->ph_nsize < OTA_FW_HEADER_OFFSET + OTA_FW_HEADER_SIZE ||
        inner->ph_nsize > OTA_APP_LENGTH)
    {
        return OTA_PATCH_ERR_IMAGE_LENGTH;
    }
    /* bsdiff 流结构 = N 组 {24B 控制} + 交错的 diff/extra 数据，且全部 diff+extra
     * 字节数恰好等于 ph_nsize。故解压长度必满足
     *   ph_original_size = 24*N + ph_nsize，N >= 1
     * 即差值非负、可被 24 整除、且至少一组控制。原版 bsdiff 可生成
     * [0,0,z] oldpos-only 组，但每个输出组仍对应制包扫描进展，因此仓库 vendor
     * 的合法上界为 N <= ph_nsize。该上界同时限制恶意流的解压量与控制循环次数。 */
    if (inner->ph_original_size < (uint64_t)inner->ph_nsize +
                                      PATCH_CONTROL_SIZE)
    {
        return OTA_PATCH_ERR_DECODED_LENGTH;
    }
    {
        uint64_t control_bytes =
            inner->ph_original_size - (uint64_t)inner->ph_nsize;

        uint64_t control_groups;

        if ((control_bytes % PATCH_CONTROL_SIZE) != 0u)
        {
            return OTA_PATCH_ERR_DECODED_LENGTH;
        }
        control_groups = control_bytes / PATCH_CONTROL_SIZE;
        if (control_groups == 0u ||
            control_groups > (uint64_t)inner->ph_nsize)
        {
            return OTA_PATCH_ERR_DECODED_LENGTH;
        }
        inner->control_group_count = (uint32_t)control_groups;
    }
    return OTA_PATCH_OK;
}

/* 契约 §158 第 4 步：bspatch 前用基版校验 ph_osize / ph_ocrc。
 * 基版按 1KiB 块读（MCU 侧为 XIP 直读），不把整镜像复制进 RAM。
 * 该步在 candidate_prepare 之前执行，错基版永不擦写 candidate。 */
static ota_patch_result_t validate_base_image(
    const ota_patch_io_t *io,
    const ota_patch_device_t *device,
    const ota_patch_inner_t *inner,
    ota_patch_state_t *state)
{
    boot_crc32_ctx_t crc;
    uint32_t offset = 0u;

    if (inner->ph_osize == 0u || inner->ph_osize > OTA_APP_LENGTH ||
        inner->ph_osize != device->base_image_len)
    {
        return OTA_PATCH_ERR_BASE_LENGTH;
    }
    boot_crc32_init(&crc);
    while (offset < inner->ph_osize)
    {
        uint32_t take = inner->ph_osize - offset;

        if (take > sizeof(state->work))
        {
            take = (uint32_t)sizeof(state->work);
        }
        if (io->base_read(io->ctx, offset, state->work, take) != 0)
        {
            return OTA_PATCH_ERR_READ;
        }
        boot_crc32_update(&crc, state->work, take);
        offset += take;
    }
    return boot_crc32_final(&crc) == inner->ph_ocrc
               ? OTA_PATCH_OK
               : OTA_PATCH_ERR_BASE_CRC;
}

/* bsdiff 控制字为 sign-magnitude 编码（bit63 符号位 + 低 63 位绝对值），
 * 不是补码。必须逐字节按 vendor offtin 公式还原。 */
static int64_t offtin(const uint8_t *buf)
{
    int64_t value;

    value = (int64_t)(buf[7] & 0x7F);
    value = value * 256 + (int64_t)buf[6];
    value = value * 256 + (int64_t)buf[5];
    value = value * 256 + (int64_t)buf[4];
    value = value * 256 + (int64_t)buf[3];
    value = value * 256 + (int64_t)buf[2];
    value = value * 256 + (int64_t)buf[1];
    value = value * 256 + (int64_t)buf[0];
    if ((buf[7] & 0x80) != 0u)
    {
        value = -value;
    }
    return value;
}

static int add_i64_checked(int64_t left, int64_t right, int64_t *result)
{
    if ((right > 0 && left > INT64_MAX - right) ||
        (right < 0 && left < INT64_MIN - right))
    {
        return -1;
    }
    *result = left + right;
    return 0;
}

/* patch 指令流内层 reader：按需驱动 LzmaDec 增量解压，把 bsdiff 流按 len 拷出。
 * len 只会是 8（控制字）或 <= 1KiB 的数据分块，故 1KiB 缓冲足够，
 * 不随 ctrl[0]/ctrl[1] 增长（这是"不 malloc(old_size)"的实质）。 */
static ota_patch_result_t patch_stream_fill(
    const ota_patch_io_t *io,
    const ota_patch_header_t *header,
    ota_patch_state_t *state)
{
    SizeT source_len;
    SizeT dest_len;
    SRes lzma_result;
    uint64_t remain;
    int append_result;

    state->stream_pos = 0u;
    state->stream_len = 0u;
    if (state->decoded_total >= state->decoded_limit)
    {
        return OTA_PATCH_ERR_LZMA_DATA;
    }
    remain = state->decoded_limit - state->decoded_total;

    /* 保证解码器有足够输入；LZMA_REQUIRED_INPUT_MAX 为单步所需上界。 */
    if (state->input_len - state->input_pos < LZMA_REQUIRED_INPUT_MAX &&
        state->cipher_read < header->payload_len)
    {
        append_result = stream_append(io, header, state);
        if (append_result < 0)
        {
            return OTA_PATCH_ERR_READ;
        }
    }
    if (state->input_pos == state->input_len)
    {
        append_result = stream_append(io, header, state);
        if (append_result < 0)
        {
            return OTA_PATCH_ERR_READ;
        }
        if (append_result == 0)
        {
            return OTA_PATCH_ERR_LZMA_DATA;
        }
    }

    source_len = state->input_len - state->input_pos;
    dest_len = sizeof(state->stream);
    if ((uint64_t)dest_len > remain)
    {
        dest_len = (SizeT)remain;
    }
    lzma_result = LzmaDec_DecodeToBuf(
        &state->lzma, state->stream, &dest_len,
        state->input + state->input_pos, &source_len,
        LZMA_FINISH_ANY, &state->lzma_status);
    state->input_pos += (uint32_t)source_len;
    if (lzma_result != SZ_OK)
    {
        return OTA_PATCH_ERR_LZMA_DATA;
    }
    state->stream_len = (uint32_t)dest_len;
    state->decoded_total += (uint64_t)dest_len;
    if (state->lzma_status == LZMA_STATUS_FINISHED_WITH_MARK ||
        (state->lzma_status == LZMA_STATUS_MAYBE_FINISHED_WITHOUT_MARK &&
         state->cipher_read == header->payload_len &&
         state->input_pos == state->input_len))
    {
        state->lzma_done = 1u;
    }
    if (dest_len == 0u)
    {
        /* 既无输出又无输入推进且密文已耗尽 → 流损坏/截断。 */
        if (source_len == 0u && state->cipher_read >= header->payload_len)
        {
            return OTA_PATCH_ERR_LZMA_DATA;
        }
    }
    return OTA_PATCH_OK;
}

/* Drive the LZMA stream to its end without writing candidate data. The one-byte
 * headroom in decoded_limit lets an overlong stream be observed and rejected
 * instead of being mistaken for a valid stream that ends at the declared size. */
static ota_patch_result_t finish_decoded_stream(
    const ota_patch_io_t *io,
    const ota_patch_header_t *header,
    ota_patch_state_t *state,
    uint64_t expected_length)
{
    while (!state->lzma_done)
    {
        ota_patch_result_t result =
            patch_stream_fill(io, header, state);

        if (result != OTA_PATCH_OK)
        {
            return result;
        }
        if (state->decoded_total > expected_length)
        {
            return OTA_PATCH_ERR_DECODED_LENGTH;
        }
    }
    if (state->decoded_total != expected_length)
    {
        return OTA_PATCH_ERR_DECODED_LENGTH;
    }
    if (state->cipher_read != header->payload_len ||
        state->input_pos != state->input_len)
    {
        return OTA_PATCH_ERR_LZMA_DATA;
    }
    return OTA_PATCH_OK;
}

static ota_patch_result_t patch_stream_read(
    const ota_patch_io_t *io,
    const ota_patch_header_t *header,
    ota_patch_state_t *state,
    uint8_t *dst, uint32_t len)
{
    uint32_t copied = 0u;

    while (copied < len)
    {
        uint32_t available;
        uint32_t take;

        if (state->stream_pos == state->stream_len)
        {
            ota_patch_result_t result =
                patch_stream_fill(io, header, state);

            if (result != OTA_PATCH_OK)
            {
                return result;
            }
            if (state->stream_len == 0u)
            {
                continue;
            }
        }
        available = state->stream_len - state->stream_pos;
        take = len - copied;
        if (take > available)
        {
            take = available;
        }
        memcpy(dst + copied, state->stream + state->stream_pos, take);
        state->stream_pos += take;
        state->decoded_consumed += (uint64_t)take;
        copied += take;
    }
    return OTA_PATCH_OK;
}

/* 1KiB 块写 candidate + 立即回读比对，offset/len 逐次做溢出安全钳制。 */
static ota_patch_result_t write_candidate_chunk(
    const ota_patch_io_t *io,
    uint32_t image_len,
    uint32_t offset,
    ota_patch_state_t *state,
    uint32_t len)
{
    if (len == 0u || len > sizeof(state->work) ||
        offset > image_len || len > image_len - offset ||
        offset > OTA_APP_LENGTH || len > OTA_APP_LENGTH - offset)
    {
        return OTA_PATCH_ERR_IMAGE_LENGTH;
    }
    if (io->candidate_program(io->ctx, offset, state->work, len) != 0)
    {
        return OTA_PATCH_ERR_CANDIDATE_WRITE;
    }
    if (io->candidate_read(io->ctx, offset, state->verify, len) != 0 ||
        memcmp(state->work, state->verify, len) != 0)
    {
        return OTA_PATCH_ERR_CANDIDATE_VERIFY;
    }
    return OTA_PATCH_OK;
}

/* diff 段：解压出的差分字节 + 基版对应字节，逐 1KiB 块合成并写 candidate。
 * 基版越界部分按 0 处理，与 vendor bspatch.c:77 的
 * (oldpos+i>=0)&&(oldpos+i<oldsize) 语义一致。 */
static ota_patch_result_t synthesize_diff(
    const ota_patch_io_t *io,
    const ota_patch_header_t *header,
    const ota_patch_inner_t *inner,
    ota_patch_state_t *state,
    int64_t oldpos,
    uint32_t newpos,
    uint32_t len)
{
    uint32_t done = 0u;

    while (done < len)
    {
        ota_patch_result_t result;
        uint32_t take = len - done;
        int64_t block_oldpos = oldpos + (int64_t)done;
        uint32_t index;

        if (take > sizeof(state->work))
        {
            take = (uint32_t)sizeof(state->work);
        }
        result = patch_stream_read(io, header, state, state->work, take);
        if (result != OTA_PATCH_OK)
        {
            return result;
        }
        /* 仅当基版窗口与本块有交集时才读基版，避免整段越界时的无效读。 */
        if (block_oldpos < (int64_t)inner->ph_osize &&
            block_oldpos + (int64_t)take > 0)
        {
            uint32_t base_offset;
            uint32_t base_skip;
            uint32_t base_take;

            if (block_oldpos < 0)
            {
                base_skip = (uint32_t)(-block_oldpos);
                base_offset = 0u;
            }
            else
            {
                base_skip = 0u;
                base_offset = (uint32_t)block_oldpos;
            }
            base_take = take - base_skip;
            if (base_take > inner->ph_osize - base_offset)
            {
                base_take = inner->ph_osize - base_offset;
            }
            if (io->base_read(io->ctx, base_offset, state->verify,
                              base_take) != 0)
            {
                return OTA_PATCH_ERR_READ;
            }
            for (index = 0u; index < base_take; ++index)
            {
                state->work[base_skip + index] =
                    (uint8_t)(state->work[base_skip + index] +
                              state->verify[index]);
            }
        }
        result = write_candidate_chunk(io, inner->ph_nsize,
                                      newpos + done, state, take);
        if (result != OTA_PATCH_OK)
        {
            return result;
        }
        done += take;
    }
    return OTA_PATCH_OK;
}

/* extra 段：解压出的新增字节直写 candidate，不叠加基版。 */
static ota_patch_result_t synthesize_extra(
    const ota_patch_io_t *io,
    const ota_patch_header_t *header,
    const ota_patch_inner_t *inner,
    ota_patch_state_t *state,
    uint32_t newpos,
    uint32_t len)
{
    uint32_t done = 0u;

    while (done < len)
    {
        ota_patch_result_t result;
        uint32_t take = len - done;

        if (take > sizeof(state->work))
        {
            take = (uint32_t)sizeof(state->work);
        }
        result = patch_stream_read(io, header, state, state->work, take);
        if (result != OTA_PATCH_OK)
        {
            return result;
        }
        result = write_candidate_chunk(io, inner->ph_nsize,
                                      newpos + done, state, take);
        if (result != OTA_PATCH_OK)
        {
            return result;
        }
        done += take;
    }
    return OTA_PATCH_OK;
}

/* bspatch 主循环（vendor bspatch.c:57-95 的流式等价实现）。 */
static ota_patch_result_t synthesize_candidate(
    const ota_patch_io_t *io,
    const ota_patch_header_t *header,
    const ota_patch_inner_t *inner,
    ota_patch_state_t *state)
{
    uint8_t control[PATCH_CONTROL_SIZE];
    int64_t oldpos = 0;
    uint32_t newpos = 0u;
    uint32_t control_groups = 0u;

    while (newpos < inner->ph_nsize)
    {
        ota_patch_result_t result;
        int64_t ctrl[3];
        int64_t oldpos_after_diff;
        int64_t oldpos_after_seek;
        uint32_t index;

        if (control_groups >= inner->control_group_count)
        {
            return OTA_PATCH_ERR_PATCH_CONTROL;
        }
        result = patch_stream_read(io, header, state, control,
                                   sizeof(control));
        if (result != OTA_PATCH_OK)
        {
            return result;
        }
        for (index = 0u; index < 3u; ++index)
        {
            ctrl[index] = offtin(control + index * PATCH_OFFT_SIZE);
        }
        ++control_groups;

        /* sanity-check 与 vendor 一致：diff/extra 长度非负、不超 INT_MAX、
         * 不越过 ph_nsize。原版 bsdiff 合法产生 [0,0,z] 以仅移动 oldpos；
         * 只拒绝 [0,0,0] 这种三项均无进展的控制组。 */
        if (ctrl[0] < 0 || ctrl[0] > INT32_MAX ||
            ctrl[1] < 0 || ctrl[1] > INT32_MAX ||
            (uint64_t)newpos + (uint64_t)ctrl[0] > inner->ph_nsize)
        {
            return OTA_PATCH_ERR_PATCH_CONTROL;
        }
        if (ctrl[0] == 0 && ctrl[1] == 0 && ctrl[2] == 0)
        {
            return OTA_PATCH_ERR_PATCH_CONTROL;
        }
        if (add_i64_checked(oldpos, ctrl[0], &oldpos_after_diff) != 0)
        {
            return OTA_PATCH_ERR_PATCH_CONTROL;
        }
        if (ctrl[0] != 0)
        {
            result = synthesize_diff(io, header, inner, state, oldpos,
                                     newpos, (uint32_t)ctrl[0]);
            if (result != OTA_PATCH_OK)
            {
                return result;
            }
        }
        newpos += (uint32_t)ctrl[0];
        oldpos = oldpos_after_diff;

        if ((uint64_t)newpos + (uint64_t)ctrl[1] > inner->ph_nsize)
        {
            return OTA_PATCH_ERR_PATCH_CONTROL;
        }
        if (ctrl[1] != 0)
        {
            result = synthesize_extra(io, header, inner, state, newpos,
                                      (uint32_t)ctrl[1]);
            if (result != OTA_PATCH_OK)
            {
                return result;
            }
        }
        newpos += (uint32_t)ctrl[1];
        if (add_i64_checked(oldpos, ctrl[2], &oldpos_after_seek) != 0)
        {
            return OTA_PATCH_ERR_PATCH_CONTROL;
        }
        oldpos = oldpos_after_seek;
    }

    if (control_groups != inner->control_group_count ||
        state->decoded_consumed != inner->ph_original_size ||
        state->stream_pos != state->stream_len)
    {
        return OTA_PATCH_ERR_PATCH_CONTROL;
    }
    return finish_decoded_stream(io, header, state,
                                 inner->ph_original_size);
}

/* 契约 §158 第 5 步：合成后用 candidate 回读复核 ph_nsize / ph_ncrc。 */
static ota_patch_result_t validate_candidate_crc(
    const ota_patch_io_t *io,
    const ota_patch_inner_t *inner,
    ota_patch_state_t *state)
{
    boot_crc32_ctx_t crc;
    uint32_t offset = 0u;

    boot_crc32_init(&crc);
    while (offset < inner->ph_nsize)
    {
        uint32_t take = inner->ph_nsize - offset;

        if (take > sizeof(state->verify))
        {
            take = (uint32_t)sizeof(state->verify);
        }
        if (io->candidate_read(io->ctx, offset, state->verify, take) != 0)
        {
            return OTA_PATCH_ERR_READ;
        }
        boot_crc32_update(&crc, state->verify, take);
        offset += take;
    }
    return boot_crc32_final(&crc) == inner->ph_ncrc
               ? OTA_PATCH_OK
               : OTA_PATCH_ERR_RESULT_CRC;
}

static int candidate_image_read(void *ctx, uint32_t offset,
                                uint8_t *dst, size_t len)
{
    ota_patch_reader_t *reader = (ota_patch_reader_t *)ctx;

    if (len > UINT32_MAX)
    {
        return -1;
    }
    return reader->io->candidate_read(reader->io->ctx, offset, dst,
                                      (uint32_t)len);
}

/* 复用 Boot 的 fw_header 校验器（CRC / 双零法 SHA / 身份 / boot 版本），
 * 与 P2-2 同源；toy 向量前 8B 为哨兵，故关闭向量表检查。 */
static ota_patch_result_t validate_candidate_image(
    const ota_patch_io_t *io,
    const ota_patch_device_t *device,
    const ota_patch_header_t *outer,
    const ota_patch_inner_t *inner,
    ota_patch_info_t *info)
{
    ota_patch_reader_t reader_ctx;
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
        return OTA_PATCH_ERR_FW_HEADER;
    }
    if (header.version_code != outer->target_vcode ||
        header.image_len != inner->ph_nsize)
    {
        return OTA_PATCH_ERR_IMAGE_METADATA;
    }
    info->image_len = header.image_len;
    memcpy(info->image_sha256, header.image_sha256,
           sizeof(info->image_sha256));
    return OTA_PATCH_OK;
}

ota_patch_result_t ota_patch_apply(
    const ota_patch_io_t *io,
    const ota_patch_device_t *device,
    uint32_t package_len,
    ota_patch_info_t *out_info)
{
    uint8_t raw_header[OTA_PATCH_HEADER_SIZE];
    uint8_t raw_inner[OTA_PATCH_INNER_HEADER_SIZE];
    ota_patch_header_t outer;
    ota_patch_inner_t inner;
    ota_patch_info_t info;
    ota_patch_result_t result;
    uint8_t *workspace = 0;
    uint32_t workspace_len = 0u;
    uintptr_t aligned_address;
    size_t prefix;
    ota_patch_state_t *state;
    CLzmaProps properties;

    if (io == 0 || device == 0 || package_len < OTA_PATCH_HEADER_SIZE ||
        package_len > OTA_ETU_MAX_LENGTH || io->package_read == 0 ||
        io->base_read == 0 || io->candidate_prepare == 0 ||
        io->candidate_program == 0 || io->candidate_read == 0 ||
        io->workspace_acquire == 0 || io->workspace_release == 0)
    {
        return OTA_PATCH_ERR_ARGUMENT;
    }
    memset(&info, 0, sizeof(info));
    memset(&outer, 0, sizeof(outer));
    memset(&inner, 0, sizeof(inner));

    /* ① 外层头读取与 §2.4 ①-⑨ 有序校验。 */
    if (io->package_read(io->ctx, 0u, raw_header,
                         sizeof(raw_header)) != 0)
    {
        return OTA_PATCH_ERR_READ;
    }
    result = parse_outer_header(raw_header, device, package_len, &outer);
    if (result != OTA_PATCH_OK)
    {
        return result;
    }
    /* ⑩ 加密后 payload CRC；此前后均未擦写 candidate。 */
    result = validate_payload_crc(io, &outer);
    if (result != OTA_PATCH_OK)
    {
        return result;
    }

    /* 取得 OTA_EXCLUSIVE 之后才允许启动 LZMA/bspatch（契约 §531）。 */
    if (io->workspace_acquire(io->ctx, &workspace, &workspace_len) != 0)
    {
        return OTA_PATCH_ERR_WORKSPACE;
    }
    if (workspace == 0 || workspace_len < OTA_PATCH_WORKSPACE_SIZE)
    {
        if (workspace != 0)
        {
            secure_zero(workspace, workspace_len);
        }
        io->workspace_release(io->ctx, workspace, workspace_len);
        return OTA_PATCH_ERR_WORKSPACE;
    }

    secure_zero(workspace, workspace_len);
    aligned_address = ((uintptr_t)workspace + ARENA_ALIGNMENT - 1u) &
                      ~(uintptr_t)(ARENA_ALIGNMENT - 1u);
    prefix = (size_t)(aligned_address - (uintptr_t)workspace);
    if (prefix > workspace_len ||
        sizeof(ota_patch_state_t) > workspace_len - prefix)
    {
        result = OTA_PATCH_ERR_WORKSPACE;
        goto cleanup;
    }
    state = (ota_patch_state_t *)aligned_address;
    prefix += align_up(sizeof(*state), ARENA_ALIGNMENT);
    if (prefix > workspace_len)
    {
        result = OTA_PATCH_ERR_WORKSPACE;
        goto cleanup;
    }
    state->arena.allocator.Alloc = arena_alloc;
    state->arena.allocator.Free = arena_free;
    state->arena.base = workspace + prefix;
    state->arena.capacity = workspace_len - prefix;
    if (ota_keys_get_aes128(outer.key_id, state->key) != 0)
    {
        result = OTA_PATCH_ERR_KEY;
        goto cleanup;
    }
    rewind_payload_stream(state, &outer);

    /* 内层 40B 头：契约 §158 第 1/2 步（ph_hcrc 置零重算 → ph_psize）。 */
    if (stream_read_exact(io, &outer, state, raw_inner,
                          sizeof(raw_inner)) != 0)
    {
        result = OTA_PATCH_ERR_READ;
        goto cleanup;
    }
    result = parse_inner_header(raw_inner, &outer, &inner);
    if (result != OTA_PATCH_OK)
    {
        goto cleanup;
    }
    result = validate_inner_properties(&inner, &properties);
    if (result != OTA_PATCH_OK)
    {
        goto cleanup;
    }

    LzmaDec_Construct(&state->lzma);
    if (LzmaDec_Allocate(&state->lzma, inner.ph_lzma_props,
                         LZMA_PROPS_SIZE,
                         &state->arena.allocator) != SZ_OK)
    {
        result = OTA_PATCH_ERR_WORKSPACE;
        goto cleanup;
    }
    if (state->arena.peak > state->arena.capacity)
    {
        result = OTA_PATCH_ERR_WORKSPACE;
        goto cleanup;
    }

    /* 契约 §158 第 3 步：先完整解压但不合成，确认实际解压长度与流终止。
     * decoded_limit 留 1B 探针空间，以识别声明长度之后仍有输出的流。 */
    begin_decode_pass(state, inner.ph_original_size + 1u);
    result = finish_decoded_stream(io, &outer, state,
                                   inner.ph_original_size);
    if (result != OTA_PATCH_OK)
    {
        goto cleanup;
    }

    /* 契约 §158 第 4 步：长度已验证后，再用基版核 ph_osize / ph_ocrc。
     * 仍位于 candidate_prepare 之前，错基版不擦 candidate。 */
    result = validate_base_image(io, device, &inner, state);
    if (result != OTA_PATCH_OK)
    {
        goto cleanup;
    }

    /* 第二遍重绕 payload 与 LZMA 状态，再执行实际流式 bspatch。 */
    rewind_payload_stream(state, &outer);
    if (stream_read_exact(io, &outer, state, raw_header,
                          OTA_PATCH_INNER_HEADER_SIZE) != 0)
    {
        result = OTA_PATCH_ERR_READ;
        goto cleanup;
    }
    if (memcmp(raw_header, raw_inner, OTA_PATCH_INNER_HEADER_SIZE) != 0)
    {
        result = OTA_PATCH_ERR_READ;
        goto cleanup;
    }
    begin_decode_pass(state, inner.ph_original_size + 1u);

    if (io->candidate_prepare(io->ctx, inner.ph_nsize) != 0)
    {
        result = OTA_PATCH_ERR_CANDIDATE_PREPARE;
        goto cleanup;
    }
    result = synthesize_candidate(io, &outer, &inner, state);
    if (result != OTA_PATCH_OK)
    {
        goto cleanup;
    }
    /* 契约 §158 第 5 步：ph_nsize / ph_ncrc 对 candidate。 */
    result = validate_candidate_crc(io, &inner, state);
    if (result != OTA_PATCH_OK)
    {
        goto cleanup;
    }

    info.package_len = package_len;
    info.payload_len = outer.payload_len;
    info.payload_crc32 = outer.payload_crc32;
    info.target_vcode = outer.target_vcode;
    info.base_vcode = outer.base_vcode;
    info.patch_stream_len = inner.ph_psize;
    info.base_len = inner.ph_osize;
    info.base_crc32 = inner.ph_ocrc;
    info.image_crc32 = inner.ph_ncrc;
    info.decoded_len = (uint32_t)state->decoded_total;
    info.workspace_peak = (uint32_t)(prefix + state->arena.peak);
    result = validate_candidate_image(io, device, &outer, &inner, &info);
    if (result == OTA_PATCH_OK && out_info != 0)
    {
        *out_info = info;
    }

cleanup:
    /* 出口统一清零 key / counter / LZMA 状态 / I-O 数据后 release。 */
    secure_zero(workspace, workspace_len);
    io->workspace_release(io->ctx, workspace, workspace_len);
    return result;
}

const char *ota_patch_result_name(ota_patch_result_t result)
{
    switch (result)
    {
    case OTA_PATCH_OK: return "ok";
    case OTA_PATCH_ERR_ARGUMENT: return "argument";
    case OTA_PATCH_ERR_READ: return "read";
    case OTA_PATCH_ERR_MAGIC: return "magic";
    case OTA_PATCH_ERR_HEADER_LENGTH: return "header_length";
    case OTA_PATCH_ERR_HEADER_CRC: return "header_crc";
    case OTA_PATCH_ERR_FLAGS: return "flags";
    case OTA_PATCH_ERR_ALGORITHM: return "algorithm";
    case OTA_PATCH_ERR_KEY: return "key";
    case OTA_PATCH_ERR_HARDWARE: return "hardware";
    case OTA_PATCH_ERR_LAYOUT: return "layout";
    case OTA_PATCH_ERR_MIN_BOOT: return "min_boot";
    case OTA_PATCH_ERR_VERSION: return "version";
    case OTA_PATCH_ERR_BASE_VCODE: return "base_vcode";
    case OTA_PATCH_ERR_BASE_SHA8: return "base_sha8";
    case OTA_PATCH_ERR_PACKAGE_LENGTH: return "package_length";
    case OTA_PATCH_ERR_PAYLOAD_CRC: return "payload_crc";
    case OTA_PATCH_ERR_WORKSPACE: return "workspace";
    case OTA_PATCH_ERR_INNER_CRC: return "inner_crc";
    case OTA_PATCH_ERR_INNER_PSIZE: return "inner_psize";
    case OTA_PATCH_ERR_INNER_PAD: return "inner_pad";
    case OTA_PATCH_ERR_LZMA_PROPERTIES: return "lzma_properties";
    case OTA_PATCH_ERR_BASE_LENGTH: return "base_length";
    case OTA_PATCH_ERR_BASE_CRC: return "base_crc";
    case OTA_PATCH_ERR_IMAGE_LENGTH: return "image_length";
    case OTA_PATCH_ERR_CANDIDATE_PREPARE: return "candidate_prepare";
    case OTA_PATCH_ERR_LZMA_DATA: return "lzma_data";
    case OTA_PATCH_ERR_PATCH_CONTROL: return "patch_control";
    case OTA_PATCH_ERR_DECODED_LENGTH: return "decoded_length";
    case OTA_PATCH_ERR_CANDIDATE_WRITE: return "candidate_write";
    case OTA_PATCH_ERR_CANDIDATE_VERIFY: return "candidate_verify";
    case OTA_PATCH_ERR_RESULT_CRC: return "result_crc";
    case OTA_PATCH_ERR_FW_HEADER: return "fw_header";
    case OTA_PATCH_ERR_IMAGE_METADATA: return "image_metadata";
    default: return "unknown";
    }
}
