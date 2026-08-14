#include "OTA/ota_sd.h"

#include <stddef.h>
#include <string.h>

enum
{
    ETU_HEADER_LEN_OFF = 4,
    ETU_FLAGS_OFF = 6,
    ETU_ALGORITHM_OFF = 8,
    ETU_KEY_ID_OFF = 12,
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
    ETU_ALGORITHM_V1 = 1,
    ETU_KEY_V1 = 1,
    ETU_PATCH_INNER_HEADER_SIZE = 40,
    OTA_SD_HASH_CHUNK_SIZE = 512
};

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

static int ascii_equal_ci(char actual, char expected)
{
    if (actual >= 'A' && actual <= 'Z')
    {
        actual = (char)(actual - 'A' + 'a');
    }
    return actual == expected;
}

static ota_sd_result_t check_reader_size(const ota_sd_reader_t *reader,
                                         uint32_t expected_len)
{
    uint32_t actual_len = 0u;

    if (reader == NULL || reader->size == NULL)
    {
        return OTA_SD_ERR_ARGUMENT;
    }
    if (reader->size(reader->ctx, &actual_len) != 0)
    {
        return OTA_SD_ERR_READ;
    }
    return actual_len == expected_len ? OTA_SD_OK
                                      : OTA_SD_ERR_FILE_CHANGED;
}

static ota_sd_result_t read_exact(const ota_sd_reader_t *reader,
                                  uint32_t expected_len,
                                  uint32_t offset,
                                  uint8_t *dst,
                                  uint32_t len)
{
    ota_sd_result_t size_result;

    if (reader->read(reader->ctx, offset, dst, len) == 0)
    {
        return OTA_SD_OK;
    }
    size_result = check_reader_size(reader, expected_len);
    return size_result == OTA_SD_ERR_FILE_CHANGED
               ? OTA_SD_ERR_FILE_CHANGED
               : OTA_SD_ERR_READ;
}

static void update_payload_crc(ota_sd_transfer_t *transfer,
                               uint32_t offset,
                               const uint8_t *data,
                               uint32_t len)
{
    uint32_t payload_start = OTA_SD_HEADER_SIZE;
    uint32_t data_end = offset + len;
    uint32_t crc_start;

    if (data_end <= payload_start)
    {
        return;
    }
    crc_start = offset < payload_start ? payload_start : offset;
    boot_crc32_update(&transfer->payload_crc32,
                      data + (crc_start - offset),
                      data_end - crc_start);
}

static ota_sd_result_t fail_transfer(ota_sd_transfer_t *transfer,
                                     ota_sd_result_t result)
{
    transfer->phase = OTA_SD_PHASE_ERROR;
    transfer->result = result;
    return result;
}

static void reset_hashes(ota_sd_transfer_t *transfer)
{
    boot_sha256_init(&transfer->sha256);
    boot_crc32_init(&transfer->package_crc32);
    boot_crc32_init(&transfer->payload_crc32);
    transfer->stream_offset = 0u;
}

static ota_sd_result_t finish_first_pass(ota_sd_transfer_t *transfer)
{
    ota_sd_result_t result;
    uint32_t payload_crc;

    result = check_reader_size(&transfer->reader,
                               transfer->info.package_len);
    if (result != OTA_SD_OK)
    {
        return fail_transfer(transfer, result);
    }
    boot_sha256_final(&transfer->sha256, transfer->package_sha256);
    transfer->verified_package_crc32 =
        boot_crc32_final(&transfer->package_crc32);
    payload_crc = boot_crc32_final(&transfer->payload_crc32);
    transfer->verified_payload_crc32 = payload_crc;
    if (memcmp(transfer->package_sha256,
               transfer->expected_package_sha256,
               OTA_SD_SHA256_SIZE) != 0)
    {
        return fail_transfer(transfer, OTA_SD_ERR_FILE_CHANGED);
    }
    if (payload_crc != transfer->info.payload_crc32)
    {
        return fail_transfer(transfer, OTA_SD_ERR_PAYLOAD_CRC);
    }

    result = check_reader_size(&transfer->reader,
                               transfer->info.package_len);
    if (result != OTA_SD_OK)
    {
        return fail_transfer(transfer, result);
    }
    transfer->staging_result = ota_staging_begin(
        &transfer->receiver,
        &transfer->staging_io,
        transfer->package_sha256,
        transfer->info.package_len,
        &transfer->staging_progress);
    if (transfer->staging_result != OTA_STAGING_OK)
    {
        return fail_transfer(transfer, OTA_SD_ERR_STAGING);
    }

    reset_hashes(transfer);
    transfer->phase = OTA_SD_PHASE_STAGE;
    return OTA_SD_IN_PROGRESS;
}

static ota_sd_result_t finish_second_pass(ota_sd_transfer_t *transfer)
{
    uint8_t digest[32];
    ota_sd_result_t result;
    uint32_t package_crc;
    uint32_t payload_crc;

    result = check_reader_size(&transfer->reader,
                               transfer->info.package_len);
    if (result != OTA_SD_OK)
    {
        return fail_transfer(transfer, result);
    }
    boot_sha256_final(&transfer->sha256, digest);
    package_crc = boot_crc32_final(&transfer->package_crc32);
    payload_crc = boot_crc32_final(&transfer->payload_crc32);
    if (memcmp(digest, transfer->package_sha256, sizeof(digest)) != 0 ||
        package_crc != transfer->verified_package_crc32 ||
        payload_crc != transfer->verified_payload_crc32)
    {
        return fail_transfer(transfer, OTA_SD_ERR_FILE_CHANGED);
    }

    transfer->phase = OTA_SD_PHASE_FINALIZE;
    result = check_reader_size(&transfer->reader,
                               transfer->info.package_len);
    if (result != OTA_SD_OK)
    {
        return fail_transfer(transfer, result);
    }
    transfer->staging_result = ota_staging_finalize(
        &transfer->receiver,
        transfer->verified_package_crc32,
        transfer->info.target_vcode);
    if (transfer->staging_result != OTA_STAGING_OK)
    {
        return fail_transfer(transfer, OTA_SD_ERR_STAGING);
    }
    transfer->phase = OTA_SD_PHASE_COMPLETE;
    transfer->result = OTA_SD_STAGED;
    return OTA_SD_STAGED;
}

int ota_sd_has_etu_extension(const char *name)
{
    size_t len;
    const char *ext;

    if (name == NULL)
    {
        return 0;
    }
    len = strlen(name);
    if (len < 4u)
    {
        return 0;
    }
    ext = name + len - 4u;
    return ext[0] == '.' &&
           ascii_equal_ci(ext[1], 'e') &&
           ascii_equal_ci(ext[2], 't') &&
           ascii_equal_ci(ext[3], 'u');
}

ota_sd_result_t ota_sd_inspect_header(
    const uint8_t raw[OTA_SD_HEADER_SIZE],
    uint32_t package_len,
    const ota_sd_device_t *device,
    ota_sd_package_info_t *out_info)
{
    ota_sd_package_info_t info;
    uint16_t flags;

    if (raw == NULL || device == NULL || out_info == NULL)
    {
        return OTA_SD_ERR_ARGUMENT;
    }
    if (memcmp(raw, "ETU1", 4u) != 0)
    {
        return OTA_SD_ERR_MAGIC;
    }
    if (read_u16le(raw + ETU_HEADER_LEN_OFF) != OTA_SD_HEADER_SIZE)
    {
        return OTA_SD_ERR_HEADER_LENGTH;
    }
    if (boot_crc32(raw, ETU_HEADER_CRC_LEN) !=
        read_u32le(raw + ETU_HEADER_CRC_OFF))
    {
        return OTA_SD_ERR_HEADER_CRC;
    }

    flags = read_u16le(raw + ETU_FLAGS_OFF);
    if (flags != OTA_SD_FULL_FLAGS && flags != OTA_SD_PATCH_FLAGS)
    {
        return OTA_SD_ERR_FLAGS;
    }
    if (read_u32le(raw + ETU_ALGORITHM_OFF) != ETU_ALGORITHM_V1)
    {
        return OTA_SD_ERR_ALGORITHM;
    }
    if (read_u32le(raw + ETU_KEY_ID_OFF) != ETU_KEY_V1)
    {
        return OTA_SD_ERR_KEY;
    }
    if (read_u16le(raw + ETU_HARDWARE_REV_OFF) != device->hardware_rev)
    {
        return OTA_SD_ERR_HARDWARE;
    }
    if (raw[ETU_LAYOUT_ID_OFF] != device->layout_id)
    {
        return OTA_SD_ERR_LAYOUT;
    }
    if (raw[ETU_MIN_BOOT_OFF] > device->boot_version)
    {
        return OTA_SD_ERR_MIN_BOOT;
    }

    memset(&info, 0, sizeof(info));
    info.flags = flags;
    info.kind = flags == OTA_SD_FULL_FLAGS ? OTA_SD_KIND_FULL
                                           : OTA_SD_KIND_PATCH;
    info.package_len = package_len;
    info.payload_len = read_u32le(raw + ETU_PAYLOAD_LEN_OFF);
    info.payload_crc32 = read_u32le(raw + ETU_PAYLOAD_CRC_OFF);
    info.target_vcode = read_u32le(raw + ETU_TARGET_VCODE_OFF);
    info.base_vcode = read_u32le(raw + ETU_BASE_VCODE_OFF);
    memcpy(info.base_image_sha8, raw + ETU_BASE_SHA8_OFF,
           sizeof(info.base_image_sha8));

    if (info.target_vcode <= device->current_vcode)
    {
        return OTA_SD_ERR_VERSION;
    }
    if (info.kind == OTA_SD_KIND_FULL)
    {
        if (info.base_vcode != 0u ||
            !all_zero(info.base_image_sha8,
                      sizeof(info.base_image_sha8)))
        {
            return OTA_SD_ERR_BASE;
        }
        if (info.payload_len == 0u)
        {
            return OTA_SD_ERR_PACKAGE_LENGTH;
        }
    }
    else
    {
        if (info.base_vcode != device->current_vcode ||
            memcmp(info.base_image_sha8, device->base_image_sha8,
                   sizeof(info.base_image_sha8)) != 0)
        {
            return OTA_SD_ERR_BASE;
        }
        if (info.payload_len <= ETU_PATCH_INNER_HEADER_SIZE)
        {
            return OTA_SD_ERR_PACKAGE_LENGTH;
        }
    }
    if (info.payload_len > OTA_ETU_MAX_LENGTH - OTA_SD_HEADER_SIZE ||
        package_len != OTA_SD_HEADER_SIZE + info.payload_len)
    {
        return OTA_SD_ERR_PACKAGE_LENGTH;
    }

    *out_info = info;
    return OTA_SD_OK;
}

ota_sd_result_t ota_sd_inspect_reader(
    const ota_sd_reader_t *reader,
    uint32_t package_len,
    const ota_sd_device_t *device,
    ota_sd_package_info_t *out_info)
{
    uint8_t raw[OTA_SD_HEADER_SIZE];
    ota_sd_result_t result;

    if (reader == NULL || reader->read == NULL || reader->size == NULL)
    {
        return OTA_SD_ERR_ARGUMENT;
    }
    if (package_len < OTA_SD_HEADER_SIZE)
    {
        return OTA_SD_ERR_PACKAGE_LENGTH;
    }
    result = check_reader_size(reader, package_len);
    if (result != OTA_SD_OK)
    {
        return result;
    }
    result = read_exact(reader, package_len, 0u, raw, sizeof(raw));
    if (result != OTA_SD_OK)
    {
        return result;
    }
    result = check_reader_size(reader, package_len);
    if (result != OTA_SD_OK)
    {
        return result;
    }
    return ota_sd_inspect_header(raw, package_len, device, out_info);
}

ota_sd_result_t ota_sd_hash_reader(
    const ota_sd_reader_t *reader,
    uint32_t package_len,
    uint8_t out_sha256[OTA_SD_SHA256_SIZE])
{
    boot_sha256_ctx_t sha256;
    uint8_t chunk[OTA_SD_HASH_CHUNK_SIZE];
    ota_sd_result_t result;
    uint32_t offset = 0u;

    if (reader == NULL || reader->read == NULL || reader->size == NULL ||
        out_sha256 == NULL)
    {
        return OTA_SD_ERR_ARGUMENT;
    }
    if (package_len < OTA_SD_HEADER_SIZE || package_len > OTA_ETU_MAX_LENGTH)
    {
        return OTA_SD_ERR_PACKAGE_LENGTH;
    }
    result = check_reader_size(reader, package_len);
    if (result != OTA_SD_OK)
    {
        return result;
    }

    boot_sha256_init(&sha256);
    while (offset < package_len)
    {
        uint32_t take = package_len - offset;

        if (take > sizeof(chunk))
        {
            take = sizeof(chunk);
        }
        result = read_exact(reader, package_len, offset, chunk, take);
        if (result != OTA_SD_OK)
        {
            return result;
        }
        boot_sha256_update(&sha256, chunk, take);
        offset += take;
    }
    result = check_reader_size(reader, package_len);
    if (result != OTA_SD_OK)
    {
        return result;
    }
    boot_sha256_final(&sha256, out_sha256);
    return OTA_SD_OK;
}

ota_sd_result_t ota_sd_transfer_begin(
    ota_sd_transfer_t *transfer,
    const ota_sd_reader_t *reader,
    const ota_staging_io_t *staging_io,
    uint32_t package_len,
    const uint8_t expected_package_sha256[OTA_SD_SHA256_SIZE],
    const ota_sd_device_t *device)
{
    ota_sd_result_t result;

    if (transfer == NULL || reader == NULL || reader->read == NULL ||
        reader->size == NULL ||
        staging_io == NULL || staging_io->read == NULL ||
        staging_io->erase_4k == NULL || staging_io->program == NULL ||
        expected_package_sha256 == NULL || device == NULL)
    {
        return OTA_SD_ERR_ARGUMENT;
    }

    memset(transfer, 0, sizeof(*transfer));
    transfer->reader = *reader;
    transfer->staging_io = *staging_io;
    transfer->device = *device;
    memcpy(transfer->expected_package_sha256, expected_package_sha256,
           OTA_SD_SHA256_SIZE);
    result = ota_sd_inspect_reader(reader, package_len, device,
                                   &transfer->info);
    if (result != OTA_SD_OK)
    {
        transfer->phase = OTA_SD_PHASE_ERROR;
        transfer->result = result;
        return result;
    }

    reset_hashes(transfer);
    transfer->phase = OTA_SD_PHASE_HASH;
    transfer->result = OTA_SD_IN_PROGRESS;
    return OTA_SD_OK;
}

ota_sd_result_t ota_sd_transfer_step(ota_sd_transfer_t *transfer,
                                     uint32_t byte_budget)
{
    ota_sd_result_t result;
    uint32_t processed = 0u;

    if (transfer == NULL)
    {
        return OTA_SD_ERR_ARGUMENT;
    }
    if (transfer->phase == OTA_SD_PHASE_COMPLETE)
    {
        return OTA_SD_STAGED;
    }
    if (transfer->phase == OTA_SD_PHASE_ERROR)
    {
        return transfer->result;
    }
    if (transfer->phase != OTA_SD_PHASE_HASH &&
        transfer->phase != OTA_SD_PHASE_STAGE)
    {
        return fail_transfer(transfer, OTA_SD_ERR_ARGUMENT);
    }
    if (byte_budget == 0u)
    {
        byte_budget = OTA_SD_TRANSFER_CHUNK_SIZE;
    }
    result = check_reader_size(&transfer->reader,
                               transfer->info.package_len);
    if (result != OTA_SD_OK)
    {
        return fail_transfer(transfer, result);
    }

    while (processed < byte_budget &&
           transfer->stream_offset < transfer->info.package_len)
    {
        uint32_t offset = transfer->stream_offset;
        uint32_t take = transfer->info.package_len - offset;

        if (take > sizeof(transfer->chunk))
        {
            take = sizeof(transfer->chunk);
        }
        result = read_exact(&transfer->reader,
                            transfer->info.package_len,
                            offset, transfer->chunk, take);
        if (result != OTA_SD_OK)
        {
            return fail_transfer(transfer, result);
        }
        boot_sha256_update(&transfer->sha256, transfer->chunk, take);
        boot_crc32_update(&transfer->package_crc32, transfer->chunk, take);
        update_payload_crc(transfer, offset, transfer->chunk, take);

        if (transfer->phase == OTA_SD_PHASE_STAGE &&
            offset >= transfer->staging_progress.durable_off)
        {
            transfer->staging_result = ota_staging_receive(
                &transfer->receiver, offset, transfer->chunk, take,
                &transfer->staging_progress);
            if (transfer->staging_result < 0 ||
                transfer->staging_result == OTA_STAGING_INTERRUPTED)
            {
                return fail_transfer(transfer, OTA_SD_ERR_STAGING);
            }
        }

        transfer->stream_offset += take;
        processed += take;
    }

    if (transfer->stream_offset != transfer->info.package_len)
    {
        return OTA_SD_IN_PROGRESS;
    }
    result = check_reader_size(&transfer->reader,
                               transfer->info.package_len);
    if (result != OTA_SD_OK)
    {
        return fail_transfer(transfer, result);
    }
    if (transfer->phase == OTA_SD_PHASE_HASH)
    {
        return finish_first_pass(transfer);
    }
    return finish_second_pass(transfer);
}

uint8_t ota_sd_transfer_percent(const ota_sd_transfer_t *transfer)
{
    uint64_t scaled;

    if (transfer == NULL || transfer->info.package_len == 0u)
    {
        return 0u;
    }
    if (transfer->phase == OTA_SD_PHASE_COMPLETE)
    {
        return 100u;
    }
    if (transfer->phase == OTA_SD_PHASE_FINALIZE)
    {
        return 95u;
    }
    if (transfer->phase == OTA_SD_PHASE_HASH)
    {
        scaled = (uint64_t)transfer->stream_offset * 45u;
        return (uint8_t)(scaled / transfer->info.package_len);
    }
    if (transfer->phase == OTA_SD_PHASE_STAGE)
    {
        scaled = (uint64_t)transfer->stream_offset * 45u;
        return (uint8_t)(45u + scaled / transfer->info.package_len);
    }
    return transfer->phase == OTA_SD_PHASE_ERROR ? 0u : 90u;
}

const char *ota_sd_result_name(ota_sd_result_t result)
{
    switch (result)
    {
    case OTA_SD_OK: return "ok";
    case OTA_SD_IN_PROGRESS: return "in_progress";
    case OTA_SD_STAGED: return "staged";
    case OTA_SD_ERR_ARGUMENT: return "argument";
    case OTA_SD_ERR_READ: return "read";
    case OTA_SD_ERR_MAGIC: return "magic";
    case OTA_SD_ERR_HEADER_LENGTH: return "header_length";
    case OTA_SD_ERR_HEADER_CRC: return "header_crc";
    case OTA_SD_ERR_FLAGS: return "flags";
    case OTA_SD_ERR_ALGORITHM: return "algorithm";
    case OTA_SD_ERR_KEY: return "key";
    case OTA_SD_ERR_HARDWARE: return "hardware";
    case OTA_SD_ERR_LAYOUT: return "layout";
    case OTA_SD_ERR_MIN_BOOT: return "min_boot";
    case OTA_SD_ERR_VERSION: return "version";
    case OTA_SD_ERR_BASE: return "base";
    case OTA_SD_ERR_PACKAGE_LENGTH: return "package_length";
    case OTA_SD_ERR_PAYLOAD_CRC: return "payload_crc";
    case OTA_SD_ERR_STAGING: return "staging";
    case OTA_SD_ERR_FILE_CHANGED: return "file_changed";
    case OTA_SD_ERR_STAGED_COMMIT: return "staged_commit";
    case OTA_SD_ERR_BUSY: return "busy";
    case OTA_SD_ERR_COMMIT_UNKNOWN: return "commit_unknown";
    default: return "unknown";
    }
}
