#include "OTA/ota_keys.h"
#include "OTA/ota_package.h"
#include "boot_crypto.h"
#include "tiny_AES_decrypt.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum
{
    TEST_PACKAGE_CAPACITY = OTA_ETU_MAX_LENGTH,
    TEST_BCB_SIZE = 128,
    TEST_HEADER_CRC_OFF = 60,
    TEST_PAYLOAD_OFF = 64
};

typedef struct fixture_t
{
    uint8_t package[TEST_PACKAGE_CAPACITY];
    uint8_t candidate[OTA_APP_LENGTH];
    uint8_t workspace[OTA_PACKAGE_WORKSPACE_SIZE];
    uint8_t bcb[TEST_BCB_SIZE];
    uint8_t bcb_before[TEST_BCB_SIZE];
    uint32_t package_len;
    uint32_t prepare_count;
    uint32_t program_count;
    uint32_t read_count;
    uint32_t max_write_end;
    uint32_t max_write_len;
    uint32_t acquire_count;
    uint32_t release_count;
    uint32_t prepared_len;
    uint32_t fail_package_read_at;
    uint8_t fail_prepare;
    uint8_t fail_program;
    uint8_t fail_candidate_read;
    uint8_t corrupt_candidate_read;
    uint8_t fail_workspace;
    uint8_t short_workspace;
    uint8_t workspace_zeroed;
} fixture_t;

static fixture_t fixture;
static uint8_t *golden_package;
static uint32_t golden_package_len;
static uint8_t *golden_image;
static uint32_t golden_image_len;
static int checks;
static int failures;

static const uint8_t expected_image_sha256[32] = {
    0x5B, 0x50, 0x8E, 0xEA, 0x3C, 0x36, 0x04, 0xEF,
    0x42, 0xB5, 0x89, 0x5D, 0x44, 0xB1, 0xDF, 0x54,
    0x0A, 0x21, 0xE9, 0x10, 0xBD, 0x00, 0xB1, 0x84,
    0xFF, 0x31, 0xAB, 0x80, 0xF0, 0xC8, 0x24, 0xDF
};

static void check(const char *name, int condition)
{
    ++checks;
    printf("  %-70s %s\n", name, condition ? "PASS" : "FAIL");
    if (!condition)
    {
        ++failures;
    }
}

static uint16_t get_u16le(const uint8_t *src)
{
    return (uint16_t)((uint16_t)src[0] | ((uint16_t)src[1] << 8));
}

static uint32_t get_u32le(const uint8_t *src)
{
    return (uint32_t)src[0] |
           ((uint32_t)src[1] << 8) |
           ((uint32_t)src[2] << 16) |
           ((uint32_t)src[3] << 24);
}

static void put_u16le(uint8_t *dst, uint16_t value)
{
    dst[0] = (uint8_t)value;
    dst[1] = (uint8_t)(value >> 8);
}

static void put_u32le(uint8_t *dst, uint32_t value)
{
    dst[0] = (uint8_t)value;
    dst[1] = (uint8_t)(value >> 8);
    dst[2] = (uint8_t)(value >> 16);
    dst[3] = (uint8_t)(value >> 24);
}

static void put_u64le(uint8_t *dst, uint64_t value)
{
    uint32_t index;

    for (index = 0u; index < 8u; ++index)
    {
        dst[index] = (uint8_t)(value >> (index * 8u));
    }
}

static uint8_t *load_file(const char *path, uint32_t *length)
{
    FILE *file = fopen(path, "rb");
    long size;
    uint8_t *data;

    if (file == 0 || fseek(file, 0, SEEK_END) != 0)
    {
        if (file != 0)
        {
            fclose(file);
        }
        return 0;
    }
    size = ftell(file);
    if (size <= 0 || (unsigned long)size > (unsigned long)UINT32_MAX ||
        fseek(file, 0, SEEK_SET) != 0)
    {
        fclose(file);
        return 0;
    }
    data = (uint8_t *)malloc((size_t)size);
    if (data == 0 || fread(data, 1u, (size_t)size, file) != (size_t)size)
    {
        free(data);
        fclose(file);
        return 0;
    }
    fclose(file);
    *length = (uint32_t)size;
    return data;
}

static void reset_fixture(void)
{
    uint32_t index;

    memset(&fixture, 0, sizeof(fixture));
    memcpy(fixture.package, golden_package, golden_package_len);
    fixture.package_len = golden_package_len;
    memset(fixture.candidate, 0xA5, sizeof(fixture.candidate));
    for (index = 0u; index < sizeof(fixture.bcb); ++index)
    {
        fixture.bcb[index] = (uint8_t)(index * 29u + 7u);
    }
    memcpy(fixture.bcb_before, fixture.bcb, sizeof(fixture.bcb));
    fixture.fail_package_read_at = UINT32_MAX;
}

static int package_read(void *ctx, uint32_t offset,
                        uint8_t *dst, uint32_t len)
{
    fixture_t *state = (fixture_t *)ctx;

    if (dst == 0 || offset > state->package_len ||
        len > state->package_len - offset ||
        (state->fail_package_read_at != UINT32_MAX &&
         offset <= state->fail_package_read_at &&
         len > state->fail_package_read_at - offset))
    {
        return -1;
    }
    memcpy(dst, state->package + offset, len);
    return 0;
}

static int candidate_prepare(void *ctx, uint32_t image_len)
{
    fixture_t *state = (fixture_t *)ctx;

    ++state->prepare_count;
    state->prepared_len = image_len;
    if (state->fail_prepare || image_len == 0u || image_len > OTA_APP_LENGTH)
    {
        return -1;
    }
    memset(state->candidate, 0xFF, image_len);
    return 0;
}

static int candidate_program(void *ctx, uint32_t offset,
                             const uint8_t *src, uint32_t len)
{
    fixture_t *state = (fixture_t *)ctx;
    uint32_t index;

    ++state->program_count;
    if (state->fail_program || src == 0 || len == 0u ||
        offset > state->prepared_len || len > state->prepared_len - offset)
    {
        return -1;
    }
    for (index = 0u; index < len; ++index)
    {
        if ((state->candidate[offset + index] & src[index]) != src[index])
        {
            return -1;
        }
        state->candidate[offset + index] &= src[index];
    }
    if (offset + len > state->max_write_end)
    {
        state->max_write_end = offset + len;
    }
    if (len > state->max_write_len)
    {
        state->max_write_len = len;
    }
    return 0;
}

static int candidate_read(void *ctx, uint32_t offset,
                          uint8_t *dst, uint32_t len)
{
    fixture_t *state = (fixture_t *)ctx;

    ++state->read_count;
    if (state->fail_candidate_read || dst == 0 ||
        offset > state->prepared_len || len > state->prepared_len - offset)
    {
        return -1;
    }
    memcpy(dst, state->candidate + offset, len);
    if (state->corrupt_candidate_read && len != 0u)
    {
        dst[0] ^= 0x01u;
        state->corrupt_candidate_read = 0u;
    }
    return 0;
}

static int workspace_acquire(void *ctx, uint8_t **workspace,
                             uint32_t *workspace_len)
{
    fixture_t *state = (fixture_t *)ctx;

    ++state->acquire_count;
    if (state->fail_workspace || workspace == 0 || workspace_len == 0)
    {
        return -1;
    }
    memset(state->workspace, 0xA5, sizeof(state->workspace));
    *workspace = state->workspace;
    *workspace_len = state->short_workspace
                         ? OTA_PACKAGE_WORKSPACE_SIZE - 1u
                         : OTA_PACKAGE_WORKSPACE_SIZE;
    return 0;
}

static void workspace_release(void *ctx, uint8_t *workspace,
                              uint32_t workspace_len)
{
    fixture_t *state = (fixture_t *)ctx;
    uint32_t index;

    ++state->release_count;
    state->workspace_zeroed = 1u;
    for (index = 0u; index < workspace_len; ++index)
    {
        if (workspace[index] != 0u)
        {
            state->workspace_zeroed = 0u;
            break;
        }
    }
}

static ota_package_io_t fixture_io(void)
{
    ota_package_io_t io;

    io.ctx = &fixture;
    io.package_read = package_read;
    io.candidate_prepare = candidate_prepare;
    io.candidate_program = candidate_program;
    io.candidate_read = candidate_read;
    io.workspace_acquire = workspace_acquire;
    io.workspace_release = workspace_release;
    return io;
}

static ota_package_device_t default_device(void)
{
    ota_package_device_t device;

    device.current_vcode = 20700u;
    device.hardware_rev = 1u;
    device.layout_id = 1u;
    device.boot_version = 1u;
    return device;
}

static void fix_header_crc(void)
{
    put_u32le(fixture.package + TEST_HEADER_CRC_OFF,
              boot_crc32(fixture.package, TEST_HEADER_CRC_OFF));
}

static void fix_payload_crc(void)
{
    uint32_t payload_len = get_u32le(fixture.package + 32u);

    put_u32le(fixture.package + 36u,
              boot_crc32(fixture.package + TEST_PAYLOAD_OFF, payload_len));
    fix_header_crc();
}

static int xcrypt_payload(void)
{
    AES_ctx aes;
    uint8_t key[OTA_AES128_KEY_SIZE];
    uint8_t counter[16];
    uint32_t payload_len = get_u32le(fixture.package + 32u);

    if (ota_keys_get_aes128(1u, key) != 0)
    {
        return -1;
    }
    memcpy(counter, fixture.package + 16u, sizeof(counter));
    AES_init_ctx(&aes, key);
    AES_CTR_decrypt(&aes, fixture.package + TEST_PAYLOAD_OFF,
                    payload_len, counter);
    memset(key, 0, sizeof(key));
    return 0;
}

static ota_package_result_t apply_with_device(
    ota_package_device_t *device, ota_package_info_t *info)
{
    ota_package_io_t io = fixture_io();

    return ota_package_apply_full(&io, device, fixture.package_len, info);
}

static ota_package_result_t apply_default(ota_package_info_t *info)
{
    ota_package_device_t device = default_device();

    return apply_with_device(&device, info);
}

static void check_bcb_unchanged(const char *name)
{
    char label[96];

    snprintf(label, sizeof(label), "%s leaves BCB byte-identical", name);
    check(label, memcmp(fixture.bcb, fixture.bcb_before,
                        sizeof(fixture.bcb)) == 0);
}

static void expect_rejection(const char *name,
                             ota_package_result_t expected,
                             int before_candidate)
{
    ota_package_result_t result = apply_default(0);
    char label[96];

    snprintf(label, sizeof(label), "%s returns %s", name,
             ota_package_result_name(expected));
    check(label, result == expected);
    if (before_candidate)
    {
        snprintf(label, sizeof(label), "%s performs no candidate prepare/write",
                 name);
        check(label, fixture.prepare_count == 0u &&
                     fixture.program_count == 0u);
    }
    check_bcb_unchanged(name);
}

static void test_golden(void)
{
    ota_package_info_t info;
    ota_package_result_t result;

    reset_fixture();
    memset(&info, 0, sizeof(info));
    result = apply_default(&info);
    check("toy-full returns success", result == OTA_PACKAGE_OK);
    check("toy-full output matches toy-new byte-for-byte",
          fixture.prepared_len == golden_image_len &&
          memcmp(fixture.candidate, golden_image, golden_image_len) == 0);
    check("toy-full metadata lengths and vcode match",
          info.package_len == 748u && info.payload_len == 684u &&
          info.payload_crc32 == 0xB8D54B65u &&
          info.target_vcode == 20800u && info.image_len == 4096u);
    check("toy-full fw_header double-zero SHA matches expected",
          memcmp(info.image_sha256, expected_image_sha256,
                 sizeof(expected_image_sha256)) == 0);
    check("toy-full writes bounded 1KiB chunks",
          fixture.prepare_count == 1u && fixture.program_count == 4u &&
          fixture.max_write_len == OTA_PACKAGE_OUTPUT_SIZE &&
          fixture.max_write_end == golden_image_len);
    check("toy-full workspace stays within fixed 40KiB arena",
          info.workspace_peak != 0u &&
          info.workspace_peak <= OTA_PACKAGE_WORKSPACE_SIZE);
    check("toy-full workspace is acquired, wiped, and released once",
          fixture.acquire_count == 1u && fixture.release_count == 1u &&
          fixture.workspace_zeroed == 1u);
    check_bcb_unchanged("toy-full");
}

static void test_outer_rejections(void)
{
    ota_package_device_t device;

    reset_fixture();
    fixture.package[0] ^= 0x01u;
    expect_rejection("bad magic", OTA_PACKAGE_ERR_MAGIC, 1);

    reset_fixture();
    put_u16le(fixture.package + 4u, 63u);
    fix_header_crc();
    expect_rejection("bad header_len", OTA_PACKAGE_ERR_HEADER_LENGTH, 1);

    reset_fixture();
    fixture.package[10] ^= 0x01u;
    expect_rejection("bad header CRC", OTA_PACKAGE_ERR_HEADER_CRC, 1);

    reset_fixture();
    put_u16le(fixture.package + 6u, 0x0007u);
    fix_header_crc();
    expect_rejection("patch flags in P2-2", OTA_PACKAGE_ERR_FLAGS, 1);

    reset_fixture();
    put_u32le(fixture.package + 8u, 2u);
    fix_header_crc();
    expect_rejection("unsupported algorithm", OTA_PACKAGE_ERR_ALGORITHM, 1);

    reset_fixture();
    put_u32le(fixture.package + 12u, 2u);
    fix_header_crc();
    expect_rejection("unsupported key", OTA_PACKAGE_ERR_KEY, 1);

    reset_fixture();
    put_u16le(fixture.package + 48u, 2u);
    fix_header_crc();
    expect_rejection("hardware mismatch", OTA_PACKAGE_ERR_HARDWARE, 1);

    reset_fixture();
    fixture.package[50] = 2u;
    fix_header_crc();
    expect_rejection("layout mismatch", OTA_PACKAGE_ERR_LAYOUT, 1);

    reset_fixture();
    fixture.package[51] = 2u;
    fix_header_crc();
    expect_rejection("minimum boot mismatch", OTA_PACKAGE_ERR_MIN_BOOT, 1);

    reset_fixture();
    device = default_device();
    device.current_vcode = 20800u;
    check("equal-version package is rejected",
          apply_with_device(&device, 0) == OTA_PACKAGE_ERR_VERSION);
    check("equal-version rejection performs no candidate operation",
          fixture.prepare_count == 0u && fixture.program_count == 0u);
    check_bcb_unchanged("equal-version package");

    reset_fixture();
    put_u32le(fixture.package + 44u, 20700u);
    fix_header_crc();
    expect_rejection("full package nonzero base_vcode",
                     OTA_PACKAGE_ERR_BASE, 1);

    reset_fixture();
    fixture.package[52] = 1u;
    fix_header_crc();
    expect_rejection("full package nonzero base_sha8",
                     OTA_PACKAGE_ERR_BASE, 1);

    reset_fixture();
    put_u32le(fixture.package + 32u,
              get_u32le(fixture.package + 32u) + 1u);
    fix_header_crc();
    expect_rejection("payload length mismatch",
                     OTA_PACKAGE_ERR_PACKAGE_LENGTH, 1);

    reset_fixture();
    put_u32le(fixture.package + 36u,
              get_u32le(fixture.package + 36u) ^ 1u);
    fix_header_crc();
    expect_rejection("stored payload CRC mismatch",
                     OTA_PACKAGE_ERR_PAYLOAD_CRC, 1);

    reset_fixture();
    fixture.package[TEST_PAYLOAD_OFF + 20u] ^= 1u;
    expect_rejection("ciphertext corruption",
                     OTA_PACKAGE_ERR_PAYLOAD_CRC, 1);

    reset_fixture();
    fixture.fail_package_read_at = TEST_PAYLOAD_OFF + 100u;
    expect_rejection("payload read error", OTA_PACKAGE_ERR_READ, 1);
}

static void test_workspace_and_lzma_rejections(void)
{
    reset_fixture();
    fixture.fail_workspace = 1u;
    expect_rejection("workspace acquire failure",
                     OTA_PACKAGE_ERR_WORKSPACE, 1);

    reset_fixture();
    fixture.short_workspace = 1u;
    expect_rejection("short workspace", OTA_PACKAGE_ERR_WORKSPACE, 1);
    check("short workspace is wiped and released",
          fixture.acquire_count == 1u && fixture.release_count == 1u &&
          fixture.workspace_zeroed == 1u);

    reset_fixture();
    check("decrypt properties fixture", xcrypt_payload() == 0);
    fixture.package[TEST_PAYLOAD_OFF] = 3u;
    check("reencrypt bad properties fixture", xcrypt_payload() == 0);
    fix_payload_crc();
    expect_rejection("unsupported lc/lp/pb",
                     OTA_PACKAGE_ERR_LZMA_PROPERTIES, 1);

    reset_fixture();
    check("decrypt dictionary fixture", xcrypt_payload() == 0);
    put_u32le(fixture.package + TEST_PAYLOAD_OFF + 1u, 32768u);
    check("reencrypt large dictionary fixture", xcrypt_payload() == 0);
    fix_payload_crc();
    expect_rejection("dictionary over 16KiB",
                     OTA_PACKAGE_ERR_LZMA_PROPERTIES, 1);

    reset_fixture();
    check("decrypt output length fixture", xcrypt_payload() == 0);
    put_u64le(fixture.package + TEST_PAYLOAD_OFF + 5u,
              (uint64_t)OTA_APP_LENGTH + 1u);
    check("reencrypt oversized output fixture", xcrypt_payload() == 0);
    fix_payload_crc();
    expect_rejection("output length over app limit",
                     OTA_PACKAGE_ERR_IMAGE_LENGTH, 1);

    reset_fixture();
    check("decrypt damaged LZMA fixture", xcrypt_payload() == 0);
    fixture.package[TEST_PAYLOAD_OFF + 13u] ^= 0xFFu;
    check("reencrypt damaged LZMA fixture", xcrypt_payload() == 0);
    fix_payload_crc();
    expect_rejection("damaged LZMA stream",
                     OTA_PACKAGE_ERR_LZMA_DATA, 0);
}

static void test_candidate_failures(void)
{
    reset_fixture();
    fixture.fail_prepare = 1u;
    expect_rejection("candidate prepare failure",
                     OTA_PACKAGE_ERR_CANDIDATE_PREPARE, 0);
    check("prepare failure writes no payload", fixture.program_count == 0u);

    reset_fixture();
    fixture.fail_program = 1u;
    expect_rejection("candidate program failure",
                     OTA_PACKAGE_ERR_CANDIDATE_WRITE, 0);

    reset_fixture();
    fixture.fail_candidate_read = 1u;
    expect_rejection("candidate readback failure",
                     OTA_PACKAGE_ERR_CANDIDATE_VERIFY, 0);

    reset_fixture();
    fixture.corrupt_candidate_read = 1u;
    expect_rejection("candidate readback corruption",
                     OTA_PACKAGE_ERR_CANDIDATE_VERIFY, 0);
}

static void test_final_metadata_rejection(void)
{
    reset_fixture();
    put_u32le(fixture.package + 40u, 20801u);
    fix_header_crc();
    expect_rejection("outer/fw_header vcode mismatch",
                     OTA_PACKAGE_ERR_IMAGE_METADATA, 0);
    check("metadata mismatch still wrote only declared image",
          fixture.max_write_end == golden_image_len);
}

static void test_api_guards(void)
{
    ota_package_io_t io;
    ota_package_device_t device = default_device();

    reset_fixture();
    io = fixture_io();
    check("null io is rejected",
          ota_package_apply_full(0, &device, fixture.package_len, 0) ==
              OTA_PACKAGE_ERR_ARGUMENT);
    check("null device is rejected",
          ota_package_apply_full(&io, 0, fixture.package_len, 0) ==
              OTA_PACKAGE_ERR_ARGUMENT);
    check("short package is rejected",
          ota_package_apply_full(&io, &device, 63u, 0) ==
              OTA_PACKAGE_ERR_ARGUMENT);
    check("result names expose stable diagnostics",
          strcmp(ota_package_result_name(OTA_PACKAGE_ERR_PAYLOAD_CRC),
                 "payload_crc") == 0 &&
          strcmp(ota_package_result_name((ota_package_result_t)-99),
                 "unknown") == 0);
    check("development key is explicit in default test build",
          ota_keys_uses_development_key() == 1);
}

int main(void)
{
    golden_package = load_file("tests/ota-vectors/toy-full.etu",
                               &golden_package_len);
    golden_image = load_file("tests/ota-vectors/toy-new.bin",
                             &golden_image_len);
    if (golden_package == 0 || golden_image == 0)
    {
        fprintf(stderr, "failed to load golden vectors\n");
        free(golden_package);
        free(golden_image);
        return 2;
    }
    check("golden package length is frozen", golden_package_len == 748u);
    check("golden image length is frozen", golden_image_len == 4096u);
    check("golden outer header remains full-package v1",
          get_u16le(golden_package + 6u) == OTA_PACKAGE_FULL_FLAGS);

    test_golden();
    test_outer_rejections();
    test_workspace_and_lzma_rejections();
    test_candidate_failures();
    test_final_metadata_rejection();
    test_api_guards();

    free(golden_package);
    free(golden_image);
    if (failures != 0)
    {
        fprintf(stderr, "P2_2_PACKAGE=FAIL checks=%d failures=%d\n",
                checks, failures);
        return 1;
    }
    printf("P2_2_PACKAGE=PASS checks=%d\n", checks);
    return 0;
}
