#include "OTA/ota_sd.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum
{
    OP_ERASE = 1,
    OP_PROGRAM = 2,
    MAX_OPS = 4096
};

typedef struct operation_t
{
    int type;
    uint32_t address;
    uint32_t len;
} operation_t;

typedef struct reader_fixture_t
{
    uint8_t *data;
    uint32_t len;
} reader_fixture_t;

typedef struct flash_fixture_t
{
    uint8_t bytes[OTA_EXT_STAGING_LENGTH];
    operation_t operations[MAX_OPS];
    uint32_t operation_count;
} flash_fixture_t;

static flash_fixture_t flash_fixture;
static int checks;
static int failures;

static const uint8_t current_sha8[OTA_SD_BASE_SHA8_SIZE] = {
    0x30, 0x81, 0xFA, 0x0A, 0xFC, 0x5B, 0xB2, 0xF3
};

static const uint8_t toy_full_sha256[32] = {
    0xD8, 0xE2, 0x6E, 0x51, 0xCF, 0x57, 0x45, 0x70,
    0xD6, 0x98, 0x42, 0xB6, 0xDC, 0xC9, 0x26, 0xC7,
    0xBE, 0xCB, 0x2F, 0x05, 0x0A, 0x2F, 0x99, 0x67,
    0x02, 0xC1, 0x07, 0x5F, 0xC1, 0x61, 0x7B, 0xFC
};

static void check(const char *name, int condition)
{
    ++checks;
    printf("  %-68s %s\n", name, condition ? "PASS" : "FAIL");
    if (!condition)
    {
        ++failures;
    }
}

static uint32_t read_u32le(const uint8_t *src)
{
    return (uint32_t)src[0] |
           ((uint32_t)src[1] << 8) |
           ((uint32_t)src[2] << 16) |
           ((uint32_t)src[3] << 24);
}

static void write_u16le(uint8_t *dst, uint16_t value)
{
    dst[0] = (uint8_t)value;
    dst[1] = (uint8_t)(value >> 8);
}

static void write_u32le(uint8_t *dst, uint32_t value)
{
    dst[0] = (uint8_t)value;
    dst[1] = (uint8_t)(value >> 8);
    dst[2] = (uint8_t)(value >> 16);
    dst[3] = (uint8_t)(value >> 24);
}

static uint8_t *load_file(const char *path, uint32_t *out_len)
{
    FILE *file = fopen(path, "rb");
    long size;
    uint8_t *data;

    if (file == NULL || fseek(file, 0, SEEK_END) != 0)
    {
        if (file != NULL)
        {
            fclose(file);
        }
        return NULL;
    }
    size = ftell(file);
    if (size <= 0 || (unsigned long)size > (unsigned long)UINT32_MAX ||
        fseek(file, 0, SEEK_SET) != 0)
    {
        fclose(file);
        return NULL;
    }
    data = (uint8_t *)malloc((size_t)size);
    if (data == NULL || fread(data, 1u, (size_t)size, file) != (size_t)size)
    {
        free(data);
        fclose(file);
        return NULL;
    }
    fclose(file);
    *out_len = (uint32_t)size;
    return data;
}

static int reader_read(void *ctx, uint32_t offset,
                       uint8_t *dst, uint32_t len)
{
    reader_fixture_t *reader = (reader_fixture_t *)ctx;

    if (dst == NULL || offset > reader->len || len > reader->len - offset)
    {
        return -1;
    }
    memcpy(dst, reader->data + offset, len);
    return 0;
}

static int reader_size(void *ctx, uint32_t *out_len)
{
    reader_fixture_t *reader = (reader_fixture_t *)ctx;

    if (reader == NULL || out_len == NULL)
    {
        return -1;
    }
    *out_len = reader->len;
    return 0;
}

static void package_sha256(const uint8_t *data, uint32_t len,
                           uint8_t out[OTA_SD_SHA256_SIZE])
{
    boot_sha256_ctx_t sha256;

    boot_sha256_init(&sha256);
    boot_sha256_update(&sha256, data, len);
    boot_sha256_final(&sha256, out);
}

static int flash_range_ok(uint32_t address, uint32_t len)
{
    return address >= OTA_EXT_STAGING &&
           len <= OTA_EXT_STAGING_LENGTH &&
           address - OTA_EXT_STAGING <= OTA_EXT_STAGING_LENGTH - len;
}

static void record_operation(int type, uint32_t address, uint32_t len)
{
    if (flash_fixture.operation_count < MAX_OPS)
    {
        operation_t *operation =
            &flash_fixture.operations[flash_fixture.operation_count++];
        operation->type = type;
        operation->address = address;
        operation->len = len;
    }
}

static int flash_read(void *ctx, uint32_t address,
                      uint8_t *dst, uint32_t len)
{
    (void)ctx;
    if (dst == NULL || !flash_range_ok(address, len))
    {
        return -1;
    }
    memcpy(dst, flash_fixture.bytes + address - OTA_EXT_STAGING, len);
    return 0;
}

static int flash_erase(void *ctx, uint32_t address)
{
    (void)ctx;
    if (!flash_range_ok(address, OTA_STAGING_BLOCK_SIZE) ||
        (address & (OTA_STAGING_BLOCK_SIZE - 1u)) != 0u)
    {
        return -1;
    }
    record_operation(OP_ERASE, address, OTA_STAGING_BLOCK_SIZE);
    memset(flash_fixture.bytes + address - OTA_EXT_STAGING, 0xFF,
           OTA_STAGING_BLOCK_SIZE);
    return 0;
}

static int flash_program(void *ctx, uint32_t address,
                         const uint8_t *src, uint32_t len)
{
    uint32_t index;
    uint8_t *dst;

    (void)ctx;
    if (src == NULL || len == 0u || !flash_range_ok(address, len))
    {
        return -1;
    }
    dst = flash_fixture.bytes + address - OTA_EXT_STAGING;
    for (index = 0u; index < len; ++index)
    {
        if ((dst[index] & src[index]) != src[index])
        {
            return -1;
        }
    }
    record_operation(OP_PROGRAM, address, len);
    for (index = 0u; index < len; ++index)
    {
        dst[index] &= src[index];
    }
    return 0;
}

static ota_staging_io_t make_staging_io(void)
{
    ota_staging_io_t io;

    memset(&io, 0, sizeof(io));
    io.read = flash_read;
    io.erase_4k = flash_erase;
    io.program = flash_program;
    return io;
}

static ota_sd_device_t make_device(void)
{
    ota_sd_device_t device;

    memset(&device, 0, sizeof(device));
    device.current_vcode = 20700u;
    device.hardware_rev = 1u;
    device.layout_id = 1u;
    device.boot_version = 1u;
    memcpy(device.base_image_sha8, current_sha8,
           sizeof(device.base_image_sha8));
    return device;
}

static ota_sd_reader_t make_reader(reader_fixture_t *fixture)
{
    ota_sd_reader_t reader;

    memset(&reader, 0, sizeof(reader));
    reader.ctx = fixture;
    reader.read = reader_read;
    reader.size = reader_size;
    return reader;
}

static void reset_flash(void)
{
    memset(&flash_fixture, 0, sizeof(flash_fixture));
    memset(flash_fixture.bytes, 0xFF, sizeof(flash_fixture.bytes));
}

static uint32_t count_operations(int type, uint32_t address)
{
    uint32_t count = 0u;
    uint32_t index;

    for (index = 0u; index < flash_fixture.operation_count; ++index)
    {
        operation_t *operation = &flash_fixture.operations[index];
        if (operation->type == type && operation->address == address)
        {
            ++count;
        }
    }
    return count;
}

static int find_operation(int type, uint32_t address, uint32_t len)
{
    uint32_t index;

    for (index = 0u; index < flash_fixture.operation_count; ++index)
    {
        operation_t *operation = &flash_fixture.operations[index];
        if (operation->type == type && operation->address == address &&
            operation->len == len)
        {
            return (int)index;
        }
    }
    return -1;
}

static void fix_header_crc(uint8_t *package)
{
    write_u32le(package + 60u, boot_crc32(package, 60u));
}

static uint8_t *make_large_full_package(uint32_t package_len)
{
    uint8_t *package;
    uint32_t payload_len;
    uint32_t index;

    if (package_len <= OTA_SD_HEADER_SIZE)
    {
        return NULL;
    }
    package = (uint8_t *)calloc(1u, package_len);
    if (package == NULL)
    {
        return NULL;
    }
    payload_len = package_len - OTA_SD_HEADER_SIZE;
    memcpy(package, "ETU1", 4u);
    write_u16le(package + 4u, OTA_SD_HEADER_SIZE);
    write_u16le(package + 6u, OTA_SD_FULL_FLAGS);
    write_u32le(package + 8u, 1u);
    write_u32le(package + 12u, 1u);
    write_u32le(package + 32u, payload_len);
    write_u32le(package + 40u, 20800u);
    write_u16le(package + 48u, 1u);
    package[50] = 1u;
    package[51] = 1u;
    for (index = OTA_SD_HEADER_SIZE; index < package_len; ++index)
    {
        package[index] = (uint8_t)(index * 29u + 7u);
    }
    write_u32le(package + 36u,
                boot_crc32(package + OTA_SD_HEADER_SIZE, payload_len));
    fix_header_crc(package);
    return package;
}

static ota_sd_result_t run_transfer(ota_sd_transfer_t *transfer,
                                    uint32_t budget)
{
    ota_sd_result_t result = OTA_SD_IN_PROGRESS;
    uint32_t guard = 0u;

    while (result == OTA_SD_IN_PROGRESS && guard++ < 100000u)
    {
        result = ota_sd_transfer_step(transfer, budget);
    }
    return result;
}

static ota_sd_result_t run_first_pass(ota_sd_transfer_t *transfer,
                                      uint32_t budget)
{
    ota_sd_result_t result = OTA_SD_IN_PROGRESS;

    while (transfer->phase == OTA_SD_PHASE_HASH &&
           result == OTA_SD_IN_PROGRESS)
    {
        result = ota_sd_transfer_step(transfer, budget);
    }
    return result;
}

static void test_extension_and_header_matrix(void)
{
    uint8_t *full;
    uint8_t *patch;
    uint8_t *copy;
    uint32_t full_len = 0u;
    uint32_t patch_len = 0u;
    ota_sd_device_t device = make_device();
    ota_sd_package_info_t info;

    full = load_file("tests/ota-vectors/toy-full.etu", &full_len);
    patch = load_file("tests/ota-vectors/toy-patch.etu", &patch_len);
    check("case-insensitive .etu filtering accepts only the final extension",
          ota_sd_has_etu_extension("full.etu") &&
              ota_sd_has_etu_extension("PATCH.ETU") &&
              !ota_sd_has_etu_extension("bad.etu.tmp") &&
              !ota_sd_has_etu_extension("etu"));
    check("golden full and patch vectors are available",
          full != NULL && patch != NULL);
    if (full == NULL || patch == NULL)
    {
        free(full);
        free(patch);
        return;
    }

    check("full header reports target 2.8.0 and zero base identity",
          ota_sd_inspect_header(full, full_len, &device, &info) == OTA_SD_OK &&
              info.kind == OTA_SD_KIND_FULL &&
              info.target_vcode == 20800u && info.base_vcode == 0u);
    check("patch header requires the current 2.7.0 raw-image identity",
          ota_sd_inspect_header(patch, patch_len, &device, &info) == OTA_SD_OK &&
              info.kind == OTA_SD_KIND_PATCH &&
              info.target_vcode == 20800u && info.base_vcode == 20700u);

    copy = (uint8_t *)malloc(full_len);
    if (copy == NULL)
    {
        free(full);
        free(patch);
        return;
    }
    memcpy(copy, full, full_len);
    copy[0] = 'X';
    check("bad magic is rejected before other header fields",
          ota_sd_inspect_header(copy, full_len, &device, &info) ==
              OTA_SD_ERR_MAGIC);
    memcpy(copy, full, full_len);
    write_u16le(copy + 6u, 0x0003u);
    fix_header_crc(copy);
    check("non-frozen flag combinations are rejected",
          ota_sd_inspect_header(copy, full_len, &device, &info) ==
              OTA_SD_ERR_FLAGS);
    memcpy(copy, full, full_len);
    write_u32le(copy + 40u, device.current_vcode);
    fix_header_crc(copy);
    check("target version equal to the running version is rejected",
          ota_sd_inspect_header(copy, full_len, &device, &info) ==
              OTA_SD_ERR_VERSION);
    memcpy(copy, full, full_len);
    copy[60] ^= 0x01u;
    check("outer-header CRC corruption is rejected",
          ota_sd_inspect_header(copy, full_len, &device, &info) ==
              OTA_SD_ERR_HEADER_CRC);
    check("declared payload length must match the exact file length",
          ota_sd_inspect_header(full, full_len - 1u, &device, &info) ==
              OTA_SD_ERR_PACKAGE_LENGTH);
    device.base_image_sha8[0] ^= 0x01u;
    check("patch base SHA mismatch is rejected before staging",
          ota_sd_inspect_header(patch, patch_len, &device, &info) ==
              OTA_SD_ERR_BASE);

    free(copy);
    free(full);
    free(patch);
}

static void test_full_transfer_and_marker_last(void)
{
    uint8_t *package;
    uint32_t package_len = 0u;
    uint32_t package_crc;
    reader_fixture_t reader_fixture;
    ota_sd_reader_t reader;
    ota_staging_io_t staging_io = make_staging_io();
    ota_sd_device_t device = make_device();
    ota_sd_transfer_t transfer;
    ota_sd_result_t result;
    int fields_program;
    int marker_program;

    package = load_file("tests/ota-vectors/toy-full.etu", &package_len);
    if (package == NULL)
    {
        check("toy full transfer fixture loads", 0);
        return;
    }
    reader_fixture.data = package;
    reader_fixture.len = package_len;
    reader = make_reader(&reader_fixture);
    reset_flash();
    check("two-pass transfer begins after a fresh header inspection",
          ota_sd_transfer_begin(&transfer, &reader, &staging_io,
                                package_len, toy_full_sha256,
                                &device) == OTA_SD_OK);
    result = run_transfer(&transfer, 256u);
    check("golden full package reaches marker-last staged state",
          result == OTA_SD_STAGED && transfer.phase == OTA_SD_PHASE_COMPLETE &&
              ota_sd_transfer_percent(&transfer) == 100u);
    check("first pass SHA-256 matches the frozen whole-package identity",
          memcmp(transfer.package_sha256, toy_full_sha256,
                 sizeof(toy_full_sha256)) == 0);
    package_crc = boot_crc32(package, package_len);
    check("ETSL stores whole-package length, CRC, target, and SHA8",
          memcmp(flash_fixture.bytes, "ETSL", 4u) == 0 &&
              read_u32le(flash_fixture.bytes + 8u) == package_len &&
              read_u32le(flash_fixture.bytes + 12u) == package_crc &&
              read_u32le(flash_fixture.bytes + 16u) == 20800u &&
              memcmp(flash_fixture.bytes + 20u, toy_full_sha256, 8u) == 0);
    check("staging payload is byte-exact after the second SD pass",
          memcmp(flash_fixture.bytes + OTA_STAGING_PAYLOAD_OFFSET,
                 package, package_len) == 0);
    fields_program = find_operation(OP_PROGRAM, OTA_EXT_STAGING, 28u);
    marker_program = find_operation(OP_PROGRAM, OTA_EXT_STAGING + 28u, 4u);
    check("commit marker is a separate program after all ETSL fields",
          fields_program >= 0 && marker_program > fields_program &&
              read_u32le(flash_fixture.bytes + 28u) ==
                  OTA_STAGING_COMMIT_MARKER);
    free(package);
}

static void test_payload_crc_and_between_pass_change(void)
{
    uint8_t *package;
    uint32_t package_len = 0u;
    reader_fixture_t reader_fixture;
    ota_sd_reader_t reader;
    ota_staging_io_t staging_io = make_staging_io();
    ota_sd_device_t device = make_device();
    ota_sd_transfer_t transfer;
    ota_sd_result_t result = OTA_SD_IN_PROGRESS;
    uint8_t expected_sha256[OTA_SD_SHA256_SIZE];

    package = load_file("tests/ota-vectors/toy-full.etu", &package_len);
    if (package == NULL)
    {
        check("payload mutation fixture loads", 0);
        return;
    }
    reader_fixture.data = package;
    reader_fixture.len = package_len;
    reader = make_reader(&reader_fixture);

    package[OTA_SD_HEADER_SIZE + 3u] ^= 0x01u;
    package_sha256(package, package_len, expected_sha256);
    reset_flash();
    ota_sd_transfer_begin(&transfer, &reader, &staging_io,
                          package_len, expected_sha256, &device);
    check("encrypted-payload CRC fails during pass one before flash staging",
          run_transfer(&transfer, 256u) == OTA_SD_ERR_PAYLOAD_CRC &&
              count_operations(OP_ERASE, OTA_EXT_STAGING) == 0u);
    package[OTA_SD_HEADER_SIZE + 3u] ^= 0x01u;

    package_sha256(package, package_len, expected_sha256);
    reset_flash();
    ota_sd_transfer_begin(&transfer, &reader, &staging_io,
                          package_len, expected_sha256, &device);
    result = run_first_pass(&transfer, 256u);
    package[100u] ^= 0x01u;
    result = run_transfer(&transfer, 256u);
    check("a file changed between hash and staging passes fails closed",
          result == OTA_SD_ERR_FILE_CHANGED &&
              read_u32le(flash_fixture.bytes + 28u) == UINT32_MAX);
    package[100u] ^= 0x01u;
    free(package);
}

static void test_confirmation_identity_binding(void)
{
    uint8_t *confirmed_package;
    uint8_t *replacement_package;
    uint8_t confirmed_sha256[OTA_SD_SHA256_SIZE];
    uint32_t package_len = 0u;
    reader_fixture_t reader_fixture;
    ota_sd_reader_t reader;
    ota_staging_io_t staging_io = make_staging_io();
    ota_sd_device_t device = make_device();
    ota_sd_transfer_t transfer;
    ota_sd_result_t result;

    confirmed_package = load_file("tests/ota-vectors/toy-full.etu",
                                  &package_len);
    replacement_package = (uint8_t *)malloc(package_len);
    check("confirmation replacement fixtures are available",
          confirmed_package != NULL && replacement_package != NULL);
    if (confirmed_package == NULL || replacement_package == NULL)
    {
        free(confirmed_package);
        free(replacement_package);
        return;
    }
    memcpy(replacement_package, confirmed_package, package_len);
    replacement_package[OTA_SD_HEADER_SIZE + 7u] ^= 0x5Au;
    write_u32le(replacement_package + 36u,
                boot_crc32(replacement_package + OTA_SD_HEADER_SIZE,
                           package_len - OTA_SD_HEADER_SIZE));
    fix_header_crc(replacement_package);
    reader_fixture.data = confirmed_package;
    reader_fixture.len = package_len;
    reader = make_reader(&reader_fixture);
    result = ota_sd_hash_reader(&reader, package_len, confirmed_sha256);
    check("confirmation snapshot hashes the complete inspected package",
          result == OTA_SD_OK);
    reader_fixture.data = replacement_package;
    reset_flash();
    result = ota_sd_transfer_begin(&transfer, &reader, &staging_io,
                                   package_len, confirmed_sha256, &device);
    if (result == OTA_SD_OK)
    {
        result = run_transfer(&transfer, 256u);
    }
    check("a valid same-path replacement cannot reuse the prior confirmation",
          result == OTA_SD_ERR_FILE_CHANGED);
    check("confirmation identity mismatch fails before any staging erase",
          count_operations(OP_ERASE, OTA_EXT_STAGING) == 0u &&
              read_u32le(flash_fixture.bytes + 28u) == UINT32_MAX);

    free(confirmed_package);
    free(replacement_package);
}

static void test_between_pass_length_change(void)
{
    uint8_t *package;
    uint8_t expected_sha256[OTA_SD_SHA256_SIZE];
    uint32_t package_len = 0u;
    reader_fixture_t reader_fixture;
    ota_sd_reader_t reader;
    ota_staging_io_t staging_io = make_staging_io();
    ota_sd_device_t device = make_device();
    ota_sd_transfer_t transfer;
    ota_sd_result_t result;

    package = load_file("tests/ota-vectors/toy-full.etu", &package_len);
    check("length-change fixture is available", package != NULL);
    if (package == NULL)
    {
        return;
    }
    package_sha256(package, package_len, expected_sha256);
    reader_fixture.data = package;
    reader_fixture.len = package_len;
    reader = make_reader(&reader_fixture);

    reset_flash();
    result = ota_sd_transfer_begin(&transfer, &reader, &staging_io,
                                   package_len, expected_sha256, &device);
    if (result == OTA_SD_OK)
    {
        result = run_first_pass(&transfer, 256u);
    }
    reader_fixture.len = package_len + 1u;
    if (result == OTA_SD_IN_PROGRESS)
    {
        result = run_transfer(&transfer, 256u);
    }
    check("appending bytes between passes fails closed before marker commit",
          result == OTA_SD_ERR_FILE_CHANGED &&
              read_u32le(flash_fixture.bytes + 28u) == UINT32_MAX);

    reader_fixture.len = package_len;
    reset_flash();
    result = ota_sd_transfer_begin(&transfer, &reader, &staging_io,
                                   package_len, expected_sha256, &device);
    if (result == OTA_SD_OK)
    {
        result = run_first_pass(&transfer, 256u);
    }
    reader_fixture.len = package_len - 1u;
    if (result == OTA_SD_IN_PROGRESS)
    {
        result = run_transfer(&transfer, 256u);
    }
    check("truncating bytes between passes fails closed before marker commit",
          result == OTA_SD_ERR_FILE_CHANGED &&
              read_u32le(flash_fixture.bytes + 28u) == UINT32_MAX);

    free(package);
}

static void test_resume_from_durable_block(void)
{
    const uint32_t package_len = 5000u;
    uint8_t *package = make_large_full_package(package_len);
    reader_fixture_t reader_fixture;
    ota_sd_reader_t reader;
    ota_staging_io_t staging_io = make_staging_io();
    ota_sd_device_t device = make_device();
    ota_sd_transfer_t first;
    ota_sd_transfer_t resumed;
    ota_sd_result_t result = OTA_SD_IN_PROGRESS;
    uint8_t expected_sha256[OTA_SD_SHA256_SIZE];
    uint32_t first_data_address =
        OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET;
    uint32_t first_erases;
    uint8_t begin_resumed = 0u;

    check("large resume fixture is generated", package != NULL);
    if (package == NULL)
    {
        return;
    }
    reader_fixture.data = package;
    reader_fixture.len = package_len;
    reader = make_reader(&reader_fixture);
    package_sha256(package, package_len, expected_sha256);
    reset_flash();
    ota_sd_transfer_begin(&first, &reader, &staging_io,
                          package_len, expected_sha256, &device);
    while (first.phase == OTA_SD_PHASE_HASH &&
           result == OTA_SD_IN_PROGRESS)
    {
        result = ota_sd_transfer_step(&first, 512u);
    }
    while (first.staging_progress.durable_off < OTA_STAGING_BLOCK_SIZE &&
           result == OTA_SD_IN_PROGRESS)
    {
        result = ota_sd_transfer_step(&first, 128u);
    }
    first_erases = count_operations(OP_ERASE, first_data_address);
    check("first session durably commits exactly one 4 KiB block",
          first.staging_progress.durable_off == OTA_STAGING_BLOCK_SIZE &&
              first_erases == 1u &&
              read_u32le(flash_fixture.bytes + 28u) == UINT32_MAX);

    result = ota_sd_transfer_begin(&resumed, &reader, &staging_io,
                                   package_len, expected_sha256, &device);
    while (resumed.phase == OTA_SD_PHASE_HASH && result >= OTA_SD_OK)
    {
        result = ota_sd_transfer_step(&resumed, 512u);
    }
    begin_resumed = resumed.staging_progress.resumed;
    if (result == OTA_SD_IN_PROGRESS)
    {
        result = run_transfer(&resumed, 512u);
    }
    check("matching package SHA resumes from the durable block and completes",
          result == OTA_SD_STAGED && begin_resumed == 1u &&
              resumed.staging_progress.durable_off == package_len);
    check("resume never erases or rewrites the already durable first block",
          count_operations(OP_ERASE, first_data_address) == first_erases);
    free(package);
}

int main(void)
{
    printf("=== P2-4 OTA SD import tests ===\n");
    test_extension_and_header_matrix();
    test_full_transfer_and_marker_last();
    test_payload_crc_and_between_pass_change();
    test_confirmation_identity_binding();
    test_between_pass_length_change();
    test_resume_from_durable_block();
    printf("=== summary: %d checks, %d failure(s) ===\n", checks, failures);
    if (failures == 0)
    {
        printf("P2_4_OTA_SD=PASS checks=%d failures=0\n", checks);
    }
    return failures == 0 ? 0 : 1;
}
