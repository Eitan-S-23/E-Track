#include "boot_fw_header.h"

#include "boot_crypto.h"

#include <string.h>

enum
{
    FW_MAGIC_OFF = 0,
    FW_HEADER_VERSION_OFF = 4,
    FW_VERSION_CODE_OFF = 8,
    FW_VERSION_NAME_OFF = 12,
    FW_VERSION_NAME_LEN = 16,
    FW_BUILD_TIMESTAMP_OFF = 28,
    FW_HARDWARE_REV_OFF = 32,
    FW_IMAGE_LEN_OFF = 36,
    FW_IMAGE_SHA_OFF = 40,
    FW_IMAGE_SHA_LEN = 32,
    FW_LAYOUT_ID_OFF = 72,
    FW_MIN_BOOT_VERSION_OFF = 73,
    FW_PADDING_OFF = 74,
    FW_PADDING_LEN = 18,
    FW_HEADER_CRC_OFF = 92,
    FW_HEADER_CRC_REGION_LEN = 92,
    FW_HASH_CHUNK_SIZE = 256
};

static uint32_t read_le32(const uint8_t *src)
{
    return (uint32_t)src[0] |
           ((uint32_t)src[1] << 8) |
           ((uint32_t)src[2] << 16) |
           ((uint32_t)src[3] << 24);
}

static int all_value(const uint8_t *src, size_t len, uint8_t value)
{
    size_t i;

    for (i = 0u; i < len; ++i)
    {
        if (src[i] != value)
        {
            return 0;
        }
    }
    return 1;
}

static int is_zero_padded_string(const uint8_t *src, size_t len)
{
    size_t i;

    for (i = 0u; i < len; ++i)
    {
        if (src[i] == 0u)
        {
            break;
        }
    }
    if (i == 0u || i == len)
    {
        return 0;
    }
    return all_value(src + i, len - i, 0u);
}

static void zero_overlap(uint8_t *chunk,
                         uint32_t chunk_offset,
                         size_t chunk_len,
                         uint32_t zero_offset,
                         uint32_t zero_len)
{
    uint32_t chunk_end = chunk_offset + (uint32_t)chunk_len;
    uint32_t zero_end = zero_offset + zero_len;
    uint32_t start;
    uint32_t end;

    if (chunk_end <= zero_offset || zero_end <= chunk_offset)
    {
        return;
    }

    start = chunk_offset > zero_offset ? chunk_offset : zero_offset;
    end = chunk_end < zero_end ? chunk_end : zero_end;
    memset(chunk + (start - chunk_offset), 0, end - start);
}

void boot_fw_default_expectations(boot_fw_expectations_t *out)
{
    if (out == NULL)
    {
        return;
    }

    out->hardware_rev = BOOT_FW_HARDWARE_REV;
    out->layout_id = BOOT_FW_LAYOUT_ID;
    out->boot_version = BOOT_VERSION;
    out->ram_start = OTA_RAM_ORIGIN;
    out->ram_end = OTA_OVERLAY_ORIGIN + OTA_OVERLAY_LENGTH;
    out->app_start = OTA_APP_ORIGIN;
    out->app_end = OTA_APP_ORIGIN + OTA_APP_LENGTH;
}

boot_fw_result_t boot_fw_header_validate_ex(
    const boot_image_reader_t *reader,
    const boot_fw_expectations_t *expected,
    uint32_t validation_flags,
    boot_fw_header_t *out_header)
{
    uint8_t raw[OTA_FW_HEADER_SIZE];
    uint8_t hash_chunk[FW_HASH_CHUNK_SIZE];
    uint8_t digest[FW_IMAGE_SHA_LEN];
    uint8_t vectors[8];
    boot_sha256_ctx_t sha;
    boot_fw_header_t parsed;
    uint32_t stored_crc;
    uint32_t offset;
    size_t i;

    if (reader == NULL || reader->read == NULL || expected == NULL ||
        (validation_flags & ~BOOT_FW_VALIDATE_VECTORS) != 0u ||
        expected->ram_start >= expected->ram_end ||
        expected->app_start >= expected->app_end)
    {
        return BOOT_FW_ERR_ARGUMENT;
    }

    if (reader->read(reader->ctx, OTA_FW_HEADER_OFFSET, raw, sizeof(raw)) != 0)
    {
        return BOOT_FW_ERR_READ;
    }
    if (memcmp(raw + FW_MAGIC_OFF, "ETFW", 4u) != 0)
    {
        return BOOT_FW_ERR_MAGIC;
    }

    stored_crc = read_le32(raw + FW_HEADER_CRC_OFF);
    if (boot_crc32(raw, FW_HEADER_CRC_REGION_LEN) != stored_crc)
    {
        return BOOT_FW_ERR_HEADER_CRC;
    }

    memset(&parsed, 0, sizeof(parsed));
    parsed.header_version = read_le32(raw + FW_HEADER_VERSION_OFF);
    parsed.version_code = read_le32(raw + FW_VERSION_CODE_OFF);
    memcpy(parsed.version_name, raw + FW_VERSION_NAME_OFF, FW_VERSION_NAME_LEN);
    parsed.version_name[FW_VERSION_NAME_LEN] = '\0';
    parsed.build_timestamp = read_le32(raw + FW_BUILD_TIMESTAMP_OFF);
    parsed.hardware_rev = read_le32(raw + FW_HARDWARE_REV_OFF);
    parsed.image_len = read_le32(raw + FW_IMAGE_LEN_OFF);
    memcpy(parsed.image_sha256, raw + FW_IMAGE_SHA_OFF, FW_IMAGE_SHA_LEN);
    parsed.layout_id = raw[FW_LAYOUT_ID_OFF];
    parsed.min_boot_version = raw[FW_MIN_BOOT_VERSION_OFF];

    if (parsed.header_version != BOOT_FW_HEADER_VERSION)
    {
        return BOOT_FW_ERR_HEADER_VERSION;
    }
    if (parsed.image_len < OTA_FW_HEADER_OFFSET + OTA_FW_HEADER_SIZE ||
        parsed.image_len > OTA_APP_LENGTH)
    {
        return BOOT_FW_ERR_IMAGE_LENGTH;
    }
    boot_sha256_init(&sha);
    offset = 0u;
    while (offset < parsed.image_len)
    {
        size_t take = parsed.image_len - offset;
        if (take > sizeof(hash_chunk))
        {
            take = sizeof(hash_chunk);
        }
        if (reader->read(reader->ctx, offset, hash_chunk, take) != 0)
        {
            return BOOT_FW_ERR_READ;
        }

        zero_overlap(hash_chunk, offset, take,
                     OTA_FW_HEADER_OFFSET + FW_IMAGE_SHA_OFF,
                     FW_IMAGE_SHA_LEN);
        zero_overlap(hash_chunk, offset, take,
                     OTA_FW_HEADER_OFFSET + FW_HEADER_CRC_OFF,
                     sizeof(uint32_t));
        boot_sha256_update(&sha, hash_chunk, take);
        offset += (uint32_t)take;
    }
    boot_sha256_final(&sha, digest);

    for (i = 0u; i < sizeof(digest); ++i)
    {
        if (digest[i] != parsed.image_sha256[i])
        {
            return BOOT_FW_ERR_IMAGE_SHA;
        }
    }
    if (parsed.hardware_rev != expected->hardware_rev)
    {
        return BOOT_FW_ERR_HARDWARE_REV;
    }
    if (parsed.layout_id != expected->layout_id)
    {
        return BOOT_FW_ERR_LAYOUT_ID;
    }
    if (parsed.min_boot_version > expected->boot_version)
    {
        return BOOT_FW_ERR_MIN_BOOT_VERSION;
    }

    if ((validation_flags & BOOT_FW_VALIDATE_VECTORS) != 0u)
    {
        if (reader->read(reader->ctx, 0u, vectors, sizeof(vectors)) != 0)
        {
            return BOOT_FW_ERR_READ;
        }
        parsed.initial_msp = read_le32(vectors);
        parsed.reset_handler = read_le32(vectors + 4u);

        if (parsed.initial_msp < expected->ram_start ||
            parsed.initial_msp > expected->ram_end)
        {
            return BOOT_FW_ERR_VECTOR_MSP;
        }
        if ((parsed.reset_handler & 1u) == 0u ||
            (parsed.reset_handler & ~1u) < expected->app_start ||
            (parsed.reset_handler & ~1u) >= expected->app_end)
        {
            return BOOT_FW_ERR_VECTOR_RESET;
        }
    }
    if (!is_zero_padded_string(raw + FW_VERSION_NAME_OFF, FW_VERSION_NAME_LEN))
    {
        return BOOT_FW_ERR_VERSION_NAME;
    }
    if (!all_value(raw + FW_PADDING_OFF, FW_PADDING_LEN, 0xFFu))
    {
        return BOOT_FW_ERR_PADDING;
    }

    if (out_header != NULL)
    {
        *out_header = parsed;
    }
    return BOOT_FW_OK;
}

boot_fw_result_t boot_fw_header_validate(const boot_image_reader_t *reader,
                                         const boot_fw_expectations_t *expected,
                                         boot_fw_header_t *out_header)
{
    return boot_fw_header_validate_ex(reader, expected,
                                      BOOT_FW_VALIDATE_VECTORS,
                                      out_header);
}

const char *boot_fw_result_name(boot_fw_result_t result)
{
    static const char *const names[] = {
        "ok",
        "argument",
        "read",
        "magic",
        "header_version",
        "header_crc",
        "image_length",
        "version_name",
        "padding",
        "image_sha",
        "hardware_rev",
        "layout_id",
        "min_boot_version",
        "vector_msp",
        "vector_reset"
    };

    if ((unsigned)result >= sizeof(names) / sizeof(names[0]))
    {
        return "unknown";
    }
    return names[result];
}
