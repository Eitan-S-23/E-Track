/* Only storage I/O is emulated. The patch decoder and Boot validator are real. */
#include "OTA/ota_patch.h"
#include "boot_crypto.h"
#include "boot_fw_header.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    uint8_t *bytes;
    uint32_t length;
} blob_t;

typedef union {
    uint64_t alignment;
    uint8_t bytes[OTA_PATCH_WORKSPACE_SIZE + 32u];
} workspace_t;

typedef struct {
    blob_t package;
    blob_t base;
    blob_t expected;
    uint8_t candidate[OTA_APP_LENGTH + 32u];
    workspace_t workspace;
    uint32_t prepared;
    uint32_t prepares;
    uint32_t program_calls;
    uint32_t programmed;
    uint32_t max_write;
    uint32_t base_reads;
    uint32_t package_reads;
    uint32_t acquires;
    uint32_t releases;
    int workspace_zeroed;
} fixture_t;

static fixture_t state;

static int load_blob(const char *name, blob_t *out)
{
    FILE *file = fopen(name, "rb");
    long size;
    if (!file) return -1;
    if (fseek(file, 0, SEEK_END) || (size = ftell(file)) <= 0 ||
        size > 0x200000 || fseek(file, 0, SEEK_SET)) {
        fclose(file);
        return -1;
    }
    out->bytes = (uint8_t *)malloc((size_t)size);
    if (!out->bytes || fread(out->bytes, 1u, (size_t)size, file) != (size_t)size) {
        fclose(file);
        return -1;
    }
    out->length = (uint32_t)size;
    return fclose(file) == 0 ? 0 : -1;
}

static int blob_read(const blob_t *blob, uint32_t off, uint8_t *dst, uint32_t len)
{
    if (!dst || off > blob->length || len > blob->length - off) return -1;
    memcpy(dst, blob->bytes + off, len);
    return 0;
}

static int package_read(void *ctx, uint32_t off, uint8_t *dst, uint32_t len)
{
    fixture_t *s = (fixture_t *)ctx;
    ++s->package_reads;
    return blob_read(&s->package, off, dst, len);
}

static int base_read(void *ctx, uint32_t off, uint8_t *dst, uint32_t len)
{
    fixture_t *s = (fixture_t *)ctx;
    ++s->base_reads;
    return blob_read(&s->base, off, dst, len);
}

static int candidate_prepare(void *ctx, uint32_t length)
{
    fixture_t *s = (fixture_t *)ctx;
    if (!length || length > OTA_APP_LENGTH || s->prepares) return -1;
    ++s->prepares;
    s->prepared = length;
    memset(s->candidate + 16u, 0xFF, length);
    return 0;
}

static int candidate_program(void *ctx, uint32_t off, const uint8_t *src, uint32_t len)
{
    fixture_t *s = (fixture_t *)ctx;
    uint32_t i;
    if (!src || !len || len > OTA_PATCH_WORK_SIZE || off != s->programmed ||
        off > s->prepared || len > s->prepared - off) return -1;
    for (i = 0; i < len; ++i) {
        uint8_t *dst = s->candidate + 16u + off + i;
        if ((*dst & src[i]) != src[i]) return -1;
        *dst &= src[i];
    }
    s->programmed += len;
    ++s->program_calls;
    if (len > s->max_write) s->max_write = len;
    return 0;
}

static int candidate_read(void *ctx, uint32_t off, uint8_t *dst, uint32_t len)
{
    fixture_t *s = (fixture_t *)ctx;
    if (!dst || off > s->prepared || len > s->prepared - off) return -1;
    memcpy(dst, s->candidate + 16u + off, len);
    return 0;
}

static int candidate_boot_read(void *ctx, uint32_t off, uint8_t *dst, size_t len)
{
    if (len > UINT32_MAX) return -1;
    return candidate_read(ctx, off, dst, (uint32_t)len);
}

static int workspace_acquire(void *ctx, uint8_t **buffer, uint32_t *length)
{
    fixture_t *s = (fixture_t *)ctx;
    if (s->acquires) return -1;
    ++s->acquires;
    *buffer = s->workspace.bytes + 16u;
    *length = OTA_PATCH_WORKSPACE_SIZE;
    return 0;
}

static void workspace_release(void *ctx, uint8_t *buffer, uint32_t length)
{
    fixture_t *s = (fixture_t *)ctx;
    uint32_t i;
    ++s->releases;
    s->workspace_zeroed = buffer == s->workspace.bytes + 16u &&
                          length == OTA_PATCH_WORKSPACE_SIZE;
    for (i = 0; i < length && i < OTA_PATCH_WORKSPACE_SIZE; ++i)
        if (buffer[i]) s->workspace_zeroed = 0;
}

static int guards_intact(void)
{
    uint32_t i;
    for (i = 0; i < 16u; ++i) {
        if (state.workspace.bytes[i] != 0xA5 ||
            state.workspace.bytes[OTA_PATCH_WORKSPACE_SIZE + 16u + i] != 0xA5 ||
            state.candidate[i] != 0xA5 ||
            state.candidate[OTA_APP_LENGTH + 16u + i] != 0xA5) return 0;
    }
    for (i = state.prepared; i < OTA_APP_LENGTH; ++i)
        if (state.candidate[16u + i] != 0xA5) return 0;
    return 1;
}

static uint32_t u32le(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

int main(int argc, char **argv)
{
    ota_patch_io_t io;
    ota_patch_device_t device;
    ota_patch_info_t info;
    ota_patch_result_t result;
    boot_sha256_ctx_t sha;
    uint8_t hash[32];
    int equal = 0, boot_ok = 0, matched, guards, lifecycle, passed;
    if (argc != 5) {
        fprintf(stderr, "usage: patch_host PACKAGE BASE EXPECTED EXPECTED_RESULT\n");
        return 2;
    }
    if (load_blob(argv[1], &state.package) || load_blob(argv[2], &state.base) ||
        load_blob(argv[3], &state.expected) || state.base.length < 0x460u) {
        fprintf(stderr, "cannot read input or base too short\n");
        return 2;
    }
    memset(state.candidate, 0xA5, sizeof(state.candidate));
    memset(state.workspace.bytes, 0xA5, sizeof(state.workspace.bytes));
    memset(&device, 0, sizeof(device));
    memset(&info, 0, sizeof(info));
    io.ctx = &state;
    io.package_read = package_read;
    io.base_read = base_read;
    io.candidate_prepare = candidate_prepare;
    io.candidate_program = candidate_program;
    io.candidate_read = candidate_read;
    io.workspace_acquire = workspace_acquire;
    io.workspace_release = workspace_release;
    device.current_vcode = u32le(state.base.bytes + 0x408u);
    device.hardware_rev = 1u;
    device.layout_id = 1u;
    device.boot_version = 1u;
    device.base_image_len = state.base.length;
    boot_sha256_init(&sha);
    boot_sha256_update(&sha, state.base.bytes, state.base.length);
    boot_sha256_final(&sha, hash);
    memcpy(device.base_image_sha8, hash, sizeof(device.base_image_sha8));
    result = ota_patch_apply(&io, &device, state.package.length, &info);
    matched = strcmp(ota_patch_result_name(result), argv[4]) == 0;
    guards = guards_intact();
    lifecycle = state.acquires == state.releases && state.acquires <= 1u &&
                (!state.acquires || state.workspace_zeroed);
    if (result == OTA_PATCH_OK) {
        boot_image_reader_t reader;
        boot_fw_expectations_t expectations;
        reader.ctx = &state;
        reader.read = candidate_boot_read;
        boot_fw_default_expectations(&expectations);
        boot_ok = boot_fw_header_validate(&reader, &expectations, NULL) == BOOT_FW_OK;
        equal = info.image_len == state.expected.length &&
                state.prepared == state.expected.length &&
                state.programmed == state.expected.length &&
                memcmp(state.candidate + 16u, state.expected.bytes, state.expected.length) == 0;
    }
    passed = matched && guards && lifecycle &&
             (result != OTA_PATCH_OK || (equal && boot_ok));
    printf("{\"result\":\"%s\",\"result_code\":%d,\"passed\":%s,"
           "\"byte_identical\":%s,\"boot_ok\":%s,\"guards_ok\":%s,"
           "\"workspace_lifecycle_ok\":%s,\"package_bytes\":%u,"
           "\"image_bytes\":%u,\"decoded_bytes\":%u,\"workspace_peak\":%u,"
           "\"prepares\":%u,\"program_calls\":%u,\"programmed_bytes\":%u,"
           "\"max_write\":%u,\"base_reads\":%u,\"package_reads\":%u}\n",
           ota_patch_result_name(result), (int)result, passed ? "true" : "false",
           equal ? "true" : "false", boot_ok ? "true" : "false", guards ? "true" : "false",
           lifecycle ? "true" : "false", (unsigned)state.package.length,
           (unsigned)info.image_len, (unsigned)info.decoded_len, (unsigned)info.workspace_peak,
           (unsigned)state.prepares, (unsigned)state.program_calls, (unsigned)state.programmed,
           (unsigned)state.max_write, (unsigned)state.base_reads, (unsigned)state.package_reads);
    free(state.package.bytes);
    free(state.base.bytes);
    free(state.expected.bytes);
    return passed ? 0 : 1;
}
