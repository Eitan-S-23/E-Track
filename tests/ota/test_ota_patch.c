/* P2-3 差分包宿主测试：正常链逐字节一致 + 每个拒绝分支。
 * 夹具风格与 tests/ota/test_ota_package.c 保持一致。 */
#include "OTA/ota_keys.h"
#include "OTA/ota_patch.h"
#include "boot_crypto.h"
#include "tiny_AES_decrypt.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum
{
    TEST_PACKAGE_CAPACITY = 4096,
    TEST_BCB_SIZE = 128,
    TEST_HEADER_CRC_OFF = 60,
    TEST_PAYLOAD_OFF = 64,
    TEST_INNER_SIZE = 40
};

typedef struct fixture_t
{
    uint8_t package[TEST_PACKAGE_CAPACITY];
    uint8_t base[OTA_APP_LENGTH];
    uint8_t candidate[OTA_APP_LENGTH];
    uint8_t workspace[OTA_PATCH_WORKSPACE_SIZE];
    uint8_t bcb[TEST_BCB_SIZE];
    uint8_t bcb_before[TEST_BCB_SIZE];
    uint32_t package_len;
    uint32_t base_len;
    uint32_t prepare_count;
    uint32_t program_count;
    uint32_t base_read_count;
    uint32_t max_write_end;
    uint32_t max_write_len;
    uint32_t acquire_count;
    uint32_t release_count;
    uint32_t prepared_len;
    uint32_t fail_package_read_at;
    uint8_t fail_prepare;
    uint8_t fail_program;
    uint8_t fail_base_read;
    uint8_t fail_candidate_read;
    uint8_t corrupt_candidate_read;
    uint8_t fail_workspace;
    uint8_t short_workspace;
    uint8_t workspace_zeroed;
} fixture_t;

static fixture_t fixture;
static uint8_t *golden_package;
static uint32_t golden_package_len;
static uint8_t *golden_base;
static uint32_t golden_base_len;
static uint8_t *golden_image;
static uint32_t golden_image_len;
static uint8_t *vendor_package;
static uint32_t vendor_package_len;
static uint8_t *vendor_image;
static uint32_t vendor_image_len;
static uint8_t *invalid_control_package;
static uint32_t invalid_control_package_len;
static int checks;
static int failures;

/* toy-new.bin 的 fw_header.image_sha256（双零法），与 expected.json 一致。 */
static const uint8_t expected_image_sha256[32] = {
    0x5B, 0x50, 0x8E, 0xEA, 0x3C, 0x36, 0x04, 0xEF,
    0x42, 0xB5, 0x89, 0x5D, 0x44, 0xB1, 0xDF, 0x54,
    0x0A, 0x21, 0xE9, 0x10, 0xBD, 0x00, 0xB1, 0x84,
    0xFF, 0x31, 0xAB, 0x80, 0xF0, 0xC8, 0x24, 0xDF
};

/* toy-old.bin 整文件 SHA-256 前 8B = 外层头 base_sha8。 */
static const uint8_t base_image_sha8[OTA_PATCH_BASE_SHA8_SIZE] = {
    0x30, 0x81, 0xFA, 0x0A, 0xFC, 0x5B, 0xB2, 0xF3
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

static void put_u32be(uint8_t *dst, uint32_t value)
{
    dst[0] = (uint8_t)(value >> 24);
    dst[1] = (uint8_t)(value >> 16);
    dst[2] = (uint8_t)(value >> 8);
    dst[3] = (uint8_t)value;
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
    memcpy(fixture.base, golden_base, golden_base_len);
    fixture.base_len = golden_base_len;
    memset(fixture.candidate, 0xA5, sizeof(fixture.candidate));
    for (index = 0u; index < sizeof(fixture.bcb); ++index)
    {
        fixture.bcb[index] = (uint8_t)(index * 29u + 7u);
    }
    memcpy(fixture.bcb_before, fixture.bcb, sizeof(fixture.bcb));
    fixture.fail_package_read_at = UINT32_MAX;
}

static void reset_fixture_with_package(const uint8_t *package,
                                       uint32_t package_len)
{
    reset_fixture();
    memcpy(fixture.package, package, package_len);
    fixture.package_len = package_len;
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

/* 基版读：MCU 侧等价于内部 flash XIP 直读，按块取，不整镜像入 RAM。 */
static int base_read(void *ctx, uint32_t offset,
                     uint8_t *dst, uint32_t len)
{
    fixture_t *state = (fixture_t *)ctx;

    ++state->base_read_count;
    if (state->fail_base_read || dst == 0 || offset > state->base_len ||
        len > state->base_len - offset)
    {
        return -1;
    }
    memcpy(dst, state->base + offset, len);
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

/* 模拟 NOR flash 语义：只能把 1 写成 0，不可未擦写就覆盖。 */
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
                         ? OTA_PATCH_WORKSPACE_SIZE - 1u
                         : OTA_PATCH_WORKSPACE_SIZE;
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

static ota_patch_io_t fixture_io(void)
{
    ota_patch_io_t io;

    io.ctx = &fixture;
    io.package_read = package_read;
    io.base_read = base_read;
    io.candidate_prepare = candidate_prepare;
    io.candidate_program = candidate_program;
    io.candidate_read = candidate_read;
    io.workspace_acquire = workspace_acquire;
    io.workspace_release = workspace_release;
    return io;
}

static ota_patch_device_t default_device(void)
{
    ota_patch_device_t device;

    device.current_vcode = 20700u;
    device.hardware_rev = 1u;
    device.layout_id = 1u;
    device.boot_version = 1u;
    device.base_image_len = golden_base_len;
    memcpy(device.base_image_sha8, base_image_sha8,
           sizeof(device.base_image_sha8));
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

/* 就地把 payload 在密文/明文之间翻转（AES-CTR 自反）。 */
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

/* 内层头改写：解密 → 回调修改明文 40B 头 → 重算 ph_hcrc → 重加密 → 修外层 CRC。 */
typedef void (*inner_mutator_fn)(uint8_t *inner);

static int mutate_inner(inner_mutator_fn mutate, int fix_inner_crc)
{
    uint8_t *inner = fixture.package + TEST_PAYLOAD_OFF;
    uint8_t zeroed[TEST_INNER_SIZE];
    uint32_t index;

    if (xcrypt_payload() != 0)
    {
        return -1;
    }
    mutate(inner);
    if (fix_inner_crc)
    {
        memcpy(zeroed, inner, sizeof(zeroed));
        for (index = 0u; index < 4u; ++index)
        {
            zeroed[index] = 0u;
        }
        put_u32be(inner, boot_crc32(zeroed, sizeof(zeroed)));
    }
    if (xcrypt_payload() != 0)
    {
        return -1;
    }
    fix_payload_crc();
    return 0;
}

static ota_patch_result_t apply_with_device(
    ota_patch_device_t *device, ota_patch_info_t *info)
{
    ota_patch_io_t io = fixture_io();

    return ota_patch_apply(&io, device, fixture.package_len, info);
}

static ota_patch_result_t apply_default(ota_patch_info_t *info)
{
    ota_patch_device_t device = default_device();

    return apply_with_device(&device, info);
}

static void check_bcb_unchanged(const char *name)
{
    char label[128];

    snprintf(label, sizeof(label), "%s leaves BCB byte-identical", name);
    check(label, memcmp(fixture.bcb, fixture.bcb_before,
                        sizeof(fixture.bcb)) == 0);
}

static void expect_rejection(const char *name,
                             ota_patch_result_t expected,
                             int before_candidate)
{
    ota_patch_result_t result = apply_default(0);
    char label[128];

    snprintf(label, sizeof(label), "%s returns %s", name,
             ota_patch_result_name(expected));
    check(label, result == expected);
    if (before_candidate)
    {
        snprintf(label, sizeof(label),
                 "%s performs no candidate prepare/write", name);
        check(label, fixture.prepare_count == 0u &&
                     fixture.program_count == 0u);
    }
    check_bcb_unchanged(name);
}

static void test_golden(void)
{
    ota_patch_info_t info;
    ota_patch_result_t result;

    reset_fixture();
    memset(&info, 0, sizeof(info));
    result = apply_default(&info);
    check("toy-patch returns success", result == OTA_PATCH_OK);
    check("toy-patch output matches toy-new byte-for-byte",
          fixture.prepared_len == golden_image_len &&
          memcmp(fixture.candidate, golden_image, golden_image_len) == 0);
    check("toy-patch outer metadata matches expected.json",
          info.package_len == 213u && info.payload_len == 149u &&
          info.payload_crc32 == 0x59B94A78u &&
          info.target_vcode == 20800u && info.base_vcode == 20700u);
    check("toy-patch inner header fields match expected.json",
          info.patch_stream_len == 109u && info.base_len == 4096u &&
          info.base_crc32 == 0x37562FA9u &&
          info.image_crc32 == 0x46C4F6E1u &&
          info.decoded_len == 4120u && info.image_len == 4096u);
    check("toy-patch fw_header double-zero SHA matches expected",
          memcmp(info.image_sha256, expected_image_sha256,
                 sizeof(expected_image_sha256)) == 0);
    check("toy-patch writes bounded 1KiB chunks",
          fixture.prepare_count == 1u &&
          fixture.max_write_len == OTA_PATCH_WORK_SIZE &&
          fixture.max_write_end == golden_image_len);
    check("toy-patch workspace stays within fixed 40KiB arena",
          info.workspace_peak != 0u &&
          info.workspace_peak <= OTA_PATCH_WORKSPACE_SIZE);
    check("toy-patch workspace is acquired, wiped, and released once",
          fixture.acquire_count == 1u && fixture.release_count == 1u &&
          fixture.workspace_zeroed == 1u);
    check("toy-patch reads base image in bounded blocks, never whole",
          fixture.base_read_count >= 2u);
    check_bcb_unchanged("toy-patch");
    printf("  [info] workspace_peak=%u bytes, ceiling=%u bytes\n",
           (unsigned)info.workspace_peak,
           (unsigned)OTA_PATCH_WORKSPACE_SIZE);
    printf("  [info] work buffer=%u, stream buffer=%u, input window=%u\n",
           (unsigned)OTA_PATCH_WORK_SIZE, (unsigned)OTA_PATCH_STREAM_SIZE,
           (unsigned)OTA_PATCH_INPUT_SIZE);
}

/* Repository bsdiff.exe regression: the decoded stream has 11 control groups,
 * including nine legal [0,0,-256] groups that move only oldpos. This must go
 * through the public ota_patch_apply() API, not an internal helper. */
static void test_vendor_multicontrol(void)
{
    ota_patch_info_t info;
    ota_patch_result_t result;

    reset_fixture_with_package(vendor_package, vendor_package_len);
    memset(&info, 0, sizeof(info));
    result = apply_default(&info);
    check("vendor multi-control patch returns success",
          result == OTA_PATCH_OK);
    check("vendor multi-control output matches expected image byte-for-byte",
          fixture.prepared_len == vendor_image_len &&
          memcmp(fixture.candidate, vendor_image, vendor_image_len) == 0);
    check("vendor multi-control metadata reports full decoded stream",
          info.target_vcode == 20802u && info.base_vcode == 20700u &&
          info.decoded_len == 4360u && info.image_len == vendor_image_len);
    check("vendor multi-control path performs six bounded writes",
          fixture.program_count == 6u &&
          fixture.max_write_len == OTA_PATCH_WORK_SIZE &&
          fixture.max_write_end == vendor_image_len);
    check("vendor multi-control path stays inside fixed workspace",
          info.workspace_peak != 0u &&
          info.workspace_peak <= OTA_PATCH_WORKSPACE_SIZE);
    check_bcb_unchanged("vendor multi-control patch");
}

static void test_outer_rejections(void)
{
    ota_patch_device_t device;

    reset_fixture();
    fixture.package[0] ^= 0x01u;
    expect_rejection("bad magic", OTA_PATCH_ERR_MAGIC, 1);

    reset_fixture();
    put_u16le(fixture.package + 4u, 63u);
    fix_header_crc();
    expect_rejection("bad header_len", OTA_PATCH_ERR_HEADER_LENGTH, 1);

    reset_fixture();
    fixture.package[10] ^= 0x01u;
    expect_rejection("bad header CRC", OTA_PATCH_ERR_HEADER_CRC, 1);

    reset_fixture();
    put_u16le(fixture.package + 6u, 0x000Bu);
    fix_header_crc();
    expect_rejection("full-package flags in P2-3", OTA_PATCH_ERR_FLAGS, 1);

    reset_fixture();
    put_u32le(fixture.package + 8u, 2u);
    fix_header_crc();
    expect_rejection("unsupported algorithm", OTA_PATCH_ERR_ALGORITHM, 1);

    reset_fixture();
    put_u32le(fixture.package + 12u, 2u);
    fix_header_crc();
    expect_rejection("unsupported key", OTA_PATCH_ERR_KEY, 1);

    reset_fixture();
    put_u16le(fixture.package + 48u, 2u);
    fix_header_crc();
    expect_rejection("hardware mismatch", OTA_PATCH_ERR_HARDWARE, 1);

    reset_fixture();
    fixture.package[50] = 2u;
    fix_header_crc();
    expect_rejection("layout mismatch", OTA_PATCH_ERR_LAYOUT, 1);

    reset_fixture();
    fixture.package[51] = 2u;
    fix_header_crc();
    expect_rejection("min_boot_ver above device", OTA_PATCH_ERR_MIN_BOOT, 1);

    /* target_vcode == cur_vcode 与 < cur_vcode 都必须按降级拒绝。 */
    reset_fixture();
    device = default_device();
    device.current_vcode = 20800u;
    check("equal target_vcode is rejected as downgrade",
          apply_with_device(&device, 0) == OTA_PATCH_ERR_VERSION);
    check("equal target_vcode performs no candidate write",
          fixture.prepare_count == 0u && fixture.program_count == 0u);
    check_bcb_unchanged("equal target_vcode");

    reset_fixture();
    device = default_device();
    device.current_vcode = 20900u;
    check("newer device vcode is rejected as downgrade",
          apply_with_device(&device, 0) == OTA_PATCH_ERR_VERSION);
    check_bcb_unchanged("newer device vcode");

    /* ⑧ 差分基准身份：base_vcode 必须 == cur_vcode。 */
    reset_fixture();
    put_u32le(fixture.package + 44u, 20600u);
    fix_header_crc();
    expect_rejection("base_vcode not equal to current",
                     OTA_PATCH_ERR_BASE_VCODE, 1);

    reset_fixture();
    put_u32le(fixture.package + 44u, 0u);
    fix_header_crc();
    expect_rejection("zero base_vcode (full-package form)",
                     OTA_PATCH_ERR_BASE_VCODE, 1);

    /* ⑧ base_sha8 必须 == 当前镜像 SHA-256 前 8B（防同版本码不同构建）。 */
    reset_fixture();
    fixture.package[52] ^= 0x01u;
    fix_header_crc();
    expect_rejection("base_sha8 mismatch", OTA_PATCH_ERR_BASE_SHA8, 1);

    reset_fixture();
    memset(fixture.package + 52u, 0, 8u);
    fix_header_crc();
    expect_rejection("all-zero base_sha8 (full-package form)",
                     OTA_PATCH_ERR_BASE_SHA8, 1);

    reset_fixture();
    device = default_device();
    device.base_image_sha8[7] ^= 0x01u;
    check("device image identity mismatch is rejected",
          apply_with_device(&device, 0) == OTA_PATCH_ERR_BASE_SHA8);
    check_bcb_unchanged("device image identity mismatch");

    /* ⑨ 包长/payload_len 一致性与下界。 */
    reset_fixture();
    put_u32le(fixture.package + 32u, 148u);
    fix_header_crc();
    expect_rejection("payload_len disagrees with package_len",
                     OTA_PATCH_ERR_PACKAGE_LENGTH, 1);

    reset_fixture();
    put_u32le(fixture.package + 32u, TEST_INNER_SIZE);
    fixture.package_len = TEST_PAYLOAD_OFF + TEST_INNER_SIZE;
    fix_header_crc();
    expect_rejection("payload_len leaves no patch stream",
                     OTA_PATCH_ERR_PACKAGE_LENGTH, 1);

    /* ⑩ 密文 payload CRC。 */
    reset_fixture();
    fixture.package[TEST_PAYLOAD_OFF + 100u] ^= 0x01u;
    fix_header_crc();
    expect_rejection("payload CRC mismatch", OTA_PATCH_ERR_PAYLOAD_CRC, 1);

    reset_fixture();
    fixture.fail_package_read_at = 0u;
    expect_rejection("outer header read failure", OTA_PATCH_ERR_READ, 1);

    reset_fixture();
    fixture.fail_package_read_at = TEST_PAYLOAD_OFF + 8u;
    expect_rejection("payload read failure during CRC",
                     OTA_PATCH_ERR_READ, 1);
}

static void mutate_inner_hcrc(uint8_t *inner)
{
    inner[3] ^= 0x01u;
}

static void mutate_inner_psize(uint8_t *inner)
{
    put_u32be(inner + 4u, 108u);
}

static void mutate_inner_pad(uint8_t *inner)
{
    inner[29] = 0x01u;
}

static void mutate_inner_osize(uint8_t *inner)
{
    put_u32le(inner + 8u, 2048u);
}

static void mutate_inner_osize_zero(uint8_t *inner)
{
    put_u32le(inner + 8u, 0u);
}

static void mutate_inner_ocrc(uint8_t *inner)
{
    put_u32be(inner + 16u, 0xDEADBEEFu);
}

static void mutate_inner_ncrc(uint8_t *inner)
{
    put_u32be(inner + 20u, 0xDEADBEEFu);
}

static void mutate_inner_nsize_small(uint8_t *inner)
{
    put_u32le(inner + 12u, 0x400u);
}

static void mutate_inner_nsize_huge(uint8_t *inner)
{
    put_u32le(inner + 12u, OTA_APP_LENGTH + 1u);
}

static void mutate_inner_props_lc(uint8_t *inner)
{
    /* lc=3,lp=0,pb=0 → 非冻结组合。 */
    inner[24] = 3u;
}

static void mutate_inner_dictionary_small(uint8_t *inner)
{
    put_u32le(inner + 25u, 2048u);
}

static void mutate_inner_dictionary_large(uint8_t *inner)
{
    put_u32le(inner + 25u, 32768u);
}

static void mutate_inner_original_size_short(uint8_t *inner)
{
    put_u64le(inner + 32u, 4119u);
}

static void mutate_inner_original_size_unaligned(uint8_t *inner)
{
    /* 4096 + 25：控制字节数不是 24 的整数倍。 */
    put_u64le(inner + 32u, 4121u);
}

static void mutate_inner_original_size_long(uint8_t *inner)
{
    /* 结构上合法（4096 + 24*2）但与实际 LZMA 流长度不符。 */
    put_u64le(inner + 32u, 4144u);
}

static void expect_inner_rejection(const char *name,
                                   inner_mutator_fn mutate,
                                   int fix_inner_crc,
                                   ota_patch_result_t expected,
                                   int before_candidate)
{
    reset_fixture();
    if (mutate_inner(mutate, fix_inner_crc) != 0)
    {
        check(name, 0);
        return;
    }
    expect_rejection(name, expected, before_candidate);
}

static void test_inner_rejections(void)
{
    /* 契约 §158 第 1 步：ph_hcrc 置零重算。 */
    expect_inner_rejection("inner header CRC mismatch",
                           mutate_inner_hcrc, 0,
                           OTA_PATCH_ERR_INNER_CRC, 1);

    /* 第 2 步：ph_psize == payload_len - 40。 */
    expect_inner_rejection("ph_psize disagrees with payload_len",
                           mutate_inner_psize, 1,
                           OTA_PATCH_ERR_INNER_PSIZE, 1);

    expect_inner_rejection("inner pad must be explicit zero",
                           mutate_inner_pad, 1,
                           OTA_PATCH_ERR_INNER_PAD, 1);

    /* LZMA props 冻结值与字典范围。 */
    expect_inner_rejection("non-frozen LZMA lc",
                           mutate_inner_props_lc, 1,
                           OTA_PATCH_ERR_LZMA_PROPERTIES, 1);
    expect_inner_rejection("dictionary below 4KiB",
                           mutate_inner_dictionary_small, 1,
                           OTA_PATCH_ERR_LZMA_PROPERTIES, 1);
    expect_inner_rejection("dictionary above 16KiB",
                           mutate_inner_dictionary_large, 1,
                           OTA_PATCH_ERR_LZMA_PROPERTIES, 1);

    /* ph_nsize 边界：必须容纳 fw_header 且不超 candidate 净容量。 */
    expect_inner_rejection("ph_nsize cannot hold fw_header",
                           mutate_inner_nsize_small, 1,
                           OTA_PATCH_ERR_IMAGE_LENGTH, 1);
    expect_inner_rejection("ph_nsize exceeds candidate capacity",
                           mutate_inner_nsize_huge, 1,
                           OTA_PATCH_ERR_IMAGE_LENGTH, 1);

    /* ph_original_size 结构约束：>= nsize+24、控制字节 24 对齐。 */
    expect_inner_rejection("ph_original_size below nsize+control",
                           mutate_inner_original_size_short, 1,
                           OTA_PATCH_ERR_DECODED_LENGTH, 1);
    expect_inner_rejection("ph_original_size control bytes unaligned",
                           mutate_inner_original_size_unaligned, 1,
                           OTA_PATCH_ERR_DECODED_LENGTH, 1);

    /* 第 4 步：ph_osize / ph_ocrc 对基版，且必须在擦 candidate 之前。 */
    expect_inner_rejection("ph_osize disagrees with base image length",
                           mutate_inner_osize, 1,
                           OTA_PATCH_ERR_BASE_LENGTH, 1);
    expect_inner_rejection("zero ph_osize",
                           mutate_inner_osize_zero, 1,
                           OTA_PATCH_ERR_BASE_LENGTH, 1);
    expect_inner_rejection("ph_ocrc disagrees with base image",
                           mutate_inner_ocrc, 1,
                           OTA_PATCH_ERR_BASE_CRC, 1);

    /* 基版被改动（同长度、不同内容）必须被 ph_ocrc 二重兜底拦住。 */
    reset_fixture();
    fixture.base[2048] ^= 0x01u;
    expect_rejection("modified base image caught by ph_ocrc",
                     OTA_PATCH_ERR_BASE_CRC, 1);

    reset_fixture();
    fixture.fail_base_read = 1u;
    expect_rejection("base read failure before prepare",
                     OTA_PATCH_ERR_READ, 1);

    /* 第 3 步必须先于第 4 步和 candidate_prepare：实际解压长度不符时，
     * 不得读取基版，也不得擦写 candidate。 */
    reset_fixture();
    if (mutate_inner(mutate_inner_original_size_long, 1) != 0)
    {
        check("ph_original_size longer than actual stream", 0);
    }
    else
    {
        check("ph_original_size longer than actual stream returns decoded_length",
              apply_default(0) == OTA_PATCH_ERR_DECODED_LENGTH);
        check("decoded_length rejection precedes base validation",
              fixture.base_read_count == 0u);
        check("decoded_length rejection precedes candidate prepare",
              fixture.prepare_count == 0u && fixture.program_count == 0u);
        check_bcb_unchanged("ph_original_size longer than actual stream");
    }

    /* 第 5 步：合成后 ph_ncrc 对 candidate。 */
    expect_inner_rejection("ph_ncrc disagrees with synthesized candidate",
                           mutate_inner_ncrc, 1,
                           OTA_PATCH_ERR_RESULT_CRC, 0);
}

static void test_stream_and_flash_failures(void)
{
    /* LZMA 流损坏：改密文的压缩流区（内层头之后）。 */
    reset_fixture();
    fixture.package[TEST_PAYLOAD_OFF + TEST_INNER_SIZE + 40u] ^= 0xFFu;
    fix_payload_crc();
    expect_rejection("corrupt LZMA stream", OTA_PATCH_ERR_LZMA_DATA, 1);

    reset_fixture();
    fixture.fail_prepare = 1u;
    check("candidate prepare failure is reported",
          apply_default(0) == OTA_PATCH_ERR_CANDIDATE_PREPARE);
    check("candidate prepare failure writes nothing",
          fixture.program_count == 0u);
    check_bcb_unchanged("candidate prepare failure");

    reset_fixture();
    fixture.fail_program = 1u;
    check("candidate program failure is reported",
          apply_default(0) == OTA_PATCH_ERR_CANDIDATE_WRITE);
    check_bcb_unchanged("candidate program failure");

    reset_fixture();
    fixture.corrupt_candidate_read = 1u;
    check("candidate readback mismatch is reported",
          apply_default(0) == OTA_PATCH_ERR_CANDIDATE_VERIFY);
    check_bcb_unchanged("candidate readback mismatch");

    reset_fixture();
    fixture.fail_candidate_read = 1u;
    check("candidate read failure is reported",
          apply_default(0) == OTA_PATCH_ERR_CANDIDATE_VERIFY);
    check_bcb_unchanged("candidate read failure");
}

static void test_final_image_rejections(void)
{
    ota_patch_device_t device;

    /* Outer and device hardware agree on rev 2, while the synthesized image's
     * valid fw_header remains rev 1. The shared Boot validator must reject it. */
    reset_fixture();
    put_u16le(fixture.package + 48u, 2u);
    fix_header_crc();
    device = default_device();
    device.hardware_rev = 2u;
    check("candidate fw_header mismatch returns fw_header",
          apply_with_device(&device, 0) == OTA_PATCH_ERR_FW_HEADER);
    check("fw_header rejection occurs after candidate synthesis",
          fixture.prepare_count == 1u && fixture.program_count != 0u);
    check_bcb_unchanged("candidate fw_header mismatch");

    /* The candidate header is internally valid, but its version_code=20800
     * disagrees with the authenticated outer target_vcode=20801. */
    reset_fixture();
    put_u32le(fixture.package + 40u, 20801u);
    fix_header_crc();
    check("candidate version mismatch returns image_metadata",
          apply_default(0) == OTA_PATCH_ERR_IMAGE_METADATA);
    check("image_metadata rejection occurs after candidate synthesis",
          fixture.prepare_count == 1u && fixture.program_count != 0u);
    check_bcb_unchanged("candidate version metadata mismatch");
}

static void test_workspace_and_arguments(void)
{
    ota_patch_io_t io;
    ota_patch_device_t device = default_device();

    /* 未取得 OTA_EXCLUSIVE 不得启动 LZMA/bspatch（契约 §531）。 */
    reset_fixture();
    fixture.fail_workspace = 1u;
    check("workspace acquire failure is reported",
          apply_default(0) == OTA_PATCH_ERR_WORKSPACE);
    check("workspace acquire failure writes no candidate",
          fixture.prepare_count == 0u && fixture.program_count == 0u);
    check_bcb_unchanged("workspace acquire failure");

    reset_fixture();
    fixture.short_workspace = 1u;
    check("short workspace is refused",
          apply_default(0) == OTA_PATCH_ERR_WORKSPACE);
    check("short workspace is wiped and released",
          fixture.release_count == 1u && fixture.workspace_zeroed == 1u);
    check("short workspace writes no candidate",
          fixture.prepare_count == 0u && fixture.program_count == 0u);

    reset_fixture();
    check("null io is rejected",
          ota_patch_apply(0, &device, fixture.package_len, 0) ==
              OTA_PATCH_ERR_ARGUMENT);

    io = fixture_io();
    check("null device is rejected",
          ota_patch_apply(&io, 0, fixture.package_len, 0) ==
              OTA_PATCH_ERR_ARGUMENT);

    io = fixture_io();
    io.base_read = 0;
    check("missing base_read callback is rejected",
          ota_patch_apply(&io, &device, fixture.package_len, 0) ==
              OTA_PATCH_ERR_ARGUMENT);

    io = fixture_io();
    check("undersized package_len is rejected",
          ota_patch_apply(&io, &device, OTA_PATCH_HEADER_SIZE - 1u, 0) ==
              OTA_PATCH_ERR_ARGUMENT);

    io = fixture_io();
    check("oversized package_len is rejected",
          ota_patch_apply(&io, &device, OTA_ETU_MAX_LENGTH + 1u, 0) ==
              OTA_PATCH_ERR_ARGUMENT);
    check("argument rejections never touch candidate or BCB",
          fixture.prepare_count == 0u && fixture.program_count == 0u &&
          memcmp(fixture.bcb, fixture.bcb_before,
                 sizeof(fixture.bcb)) == 0);
}

/* 控制三元组 sanity：静态坏包的首组是 [0,0,0]，解码长度与头部均合法，
 * 因而会真实到达公开 apply API 的 PATCH_CONTROL 分支。 */
static void test_control_sanity(void)
{
    reset_fixture_with_package(invalid_control_package,
                               invalid_control_package_len);
    check("all-zero non-progress control returns patch_control",
          apply_default(0) == OTA_PATCH_ERR_PATCH_CONTROL);
    check("patch_control rejection prepares but never writes candidate",
          fixture.prepare_count == 1u && fixture.program_count == 0u);
    check_bcb_unchanged("all-zero non-progress control");

    reset_fixture();
    /* 截断 payload：LZMA 流提前结束，合成必须报错而不是继续写。 */
    put_u32le(fixture.package + 32u, 120u);
    fixture.package_len = TEST_PAYLOAD_OFF + 120u;
    fix_payload_crc();
    check("truncated patch stream is rejected",
          apply_default(0) == OTA_PATCH_ERR_INNER_PSIZE);
    check("truncated patch stream writes no candidate",
          fixture.prepare_count == 0u && fixture.program_count == 0u);
    check_bcb_unchanged("truncated patch stream");

    /* 保持 ph_psize 自洽但截断实际数据：payload CRC 会先拦住；
     * 若强行修正 CRC，则解压阶段必须以 lzma_data 失败。 */
    reset_fixture();
    {
        uint8_t *inner = fixture.package + TEST_PAYLOAD_OFF;
        uint8_t zeroed[TEST_INNER_SIZE];
        uint32_t index;

        if (xcrypt_payload() == 0)
        {
            put_u32be(inner + 4u, 60u);
            memcpy(zeroed, inner, sizeof(zeroed));
            for (index = 0u; index < 4u; ++index)
            {
                zeroed[index] = 0u;
            }
            put_u32be(inner, boot_crc32(zeroed, sizeof(zeroed)));
            (void)xcrypt_payload();
            put_u32le(fixture.package + 32u, TEST_INNER_SIZE + 60u);
            fixture.package_len = TEST_PAYLOAD_OFF + TEST_INNER_SIZE + 60u;
            fix_payload_crc();
            check("short LZMA stream fails during validation pass",
                  apply_default(0) == OTA_PATCH_ERR_LZMA_DATA);
            check("short LZMA stream is rejected before base/candidate",
                  fixture.base_read_count == 0u &&
                  fixture.prepare_count == 0u && fixture.program_count == 0u);
            check_bcb_unchanged("short LZMA stream");
        }
        else
        {
            check("short LZMA stream fails during validation pass", 0);
        }
    }
}

int main(void)
{
    golden_package = load_file("tests/ota-vectors/toy-patch.etu",
                               &golden_package_len);
    golden_base = load_file("tests/ota-vectors/toy-old.bin",
                            &golden_base_len);
    golden_image = load_file("tests/ota-vectors/toy-new.bin",
                             &golden_image_len);
    vendor_package = load_file("tests/ota-vectors/p2-3-vendor-oldpos.etu",
                               &vendor_package_len);
    vendor_image = load_file(
        "tests/ota-vectors/p2-3-vendor-oldpos-new.bin",
        &vendor_image_len);
    invalid_control_package = load_file(
        "tests/ota-vectors/p2-3-invalid-control.etu",
        &invalid_control_package_len);
    if (golden_package == 0 || golden_base == 0 || golden_image == 0 ||
        vendor_package == 0 || vendor_image == 0 ||
        invalid_control_package == 0 ||
        golden_package_len > TEST_PACKAGE_CAPACITY ||
        vendor_package_len > TEST_PACKAGE_CAPACITY ||
        invalid_control_package_len > TEST_PACKAGE_CAPACITY ||
        golden_base_len > OTA_APP_LENGTH ||
        golden_image_len > OTA_APP_LENGTH ||
        vendor_image_len > OTA_APP_LENGTH)
    {
        printf("failed to load golden vectors from tests/ota-vectors\n");
        return 1;
    }

    printf("P2-3 patch package tests\n");
    printf(" golden vectors\n");
    test_golden();
    printf(" vendor multi-control regression\n");
    test_vendor_multicontrol();
    printf(" outer header rejections\n");
    test_outer_rejections();
    printf(" inner header rejections\n");
    test_inner_rejections();
    printf(" stream and flash failures\n");
    test_stream_and_flash_failures();
    printf(" final image rejections\n");
    test_final_image_rejections();
    printf(" workspace and argument handling\n");
    test_workspace_and_arguments();
    printf(" control sanity\n");
    test_control_sanity();

    printf("\n%d/%d checks passed\n", checks - failures, checks);
    free(golden_package);
    free(golden_base);
    free(golden_image);
    free(vendor_package);
    free(vendor_image);
    free(invalid_control_package);
    return failures == 0 ? 0 : 1;
}
