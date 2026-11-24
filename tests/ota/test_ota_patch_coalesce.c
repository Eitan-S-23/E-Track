/* Public-API PATCH storage oracle. Decoder, crypto and validation are real. */
#include "OTA/ota_patch.h"
#include "boot_crypto.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct
{
    uint8_t *bytes;
    uint32_t len;
} blob_t;

typedef union
{
    uint64_t alignment;
    uint8_t bytes[OTA_PATCH_WORKSPACE_SIZE + 32u];
} workspace_t;

typedef struct
{
    blob_t package, base, target;
    uint8_t candidate[OTA_APP_LENGTH + 32u];
    workspace_t workspace;
    uint32_t prepared, prepares, programs, programmed, max_write, last_write;
    uint32_t readbacks, final_reads, install_base_reads, install_package_reads;
    uint32_t acquires, releases, pending_off, pending_len;
    uint32_t fail_at, after_fault;
    const char *fail_kind;
    int faulted, order_ok, shape_ok, wiped;
} fixture_t;

static fixture_t f;

static int load_blob(const char *path, blob_t *out)
{
    FILE *file = fopen(path, "rb");
    long len;
    if (!file) return -1;
    if (fseek(file, 0, SEEK_END) || (len = ftell(file)) <= 0 ||
        len > 0x200000 || fseek(file, 0, SEEK_SET))
    {
        fclose(file);
        return -1;
    }
    out->bytes = (uint8_t *)malloc((size_t)len);
    if (!out->bytes || fread(out->bytes, 1u, (size_t)len, file) != (size_t)len)
    {
        fclose(file);
        return -1;
    }
    out->len = (uint32_t)len;
    return fclose(file) == 0 ? 0 : -1;
}

static int read_blob(const blob_t *blob, uint32_t off, uint8_t *dst, uint32_t len)
{
    if (!dst || off > blob->len || len > blob->len - off) return -1;
    memcpy(dst, blob->bytes + off, len);
    return 0;
}

static int storage_entry(int is_readback)
{
    if (f.faulted)
    {
        ++f.after_fault;
        return -1;
    }
    if (f.pending_len && !is_readback)
    {
        f.order_ok = 0;
        return -1;
    }
    return 0;
}

static int inject(const char *kind, uint32_t count)
{
    if (strcmp(f.fail_kind, kind) == 0 && count == f.fail_at)
    {
        f.faulted = 1;
        return 1;
    }
    return 0;
}

static int package_read(void *ctx, uint32_t off, uint8_t *dst, uint32_t len)
{
    (void)ctx;
    if (storage_entry(0)) return -1;
    if (f.prepares && inject("package", ++f.install_package_reads)) return -1;
    return read_blob(&f.package, off, dst, len);
}

static int base_read(void *ctx, uint32_t off, uint8_t *dst, uint32_t len)
{
    (void)ctx;
    if (storage_entry(0)) return -1;
    if (f.prepares && inject("base", ++f.install_base_reads)) return -1;
    return read_blob(&f.base, off, dst, len);
}

static int candidate_prepare(void *ctx, uint32_t len)
{
    (void)ctx;
    if (storage_entry(0) || f.prepares || !len || len > OTA_APP_LENGTH) return -1;
    ++f.prepares;
    f.prepared = len;
    memset(f.candidate + 16u, 0xFF, len);
    return 0;
}

static int candidate_program(void *ctx, uint32_t off, const uint8_t *src, uint32_t len)
{
    uint32_t i;
    (void)ctx;
    if (storage_entry(0)) return -1;
    ++f.programs;
    if (!src || !len || len > OTA_PATCH_WORK_SIZE || off != f.programmed ||
        off > f.prepared || len > f.prepared - off)
    {
        f.order_ok = 0;
        return -1;
    }
#if OTA_PATCH_COALESCE_WRITES
    if (len != OTA_PATCH_WORK_SIZE && off + len != f.prepared) f.shape_ok = 0;
#endif
    if (inject("program", f.programs)) return -1;
    for (i = 0u; i < len; ++i)
    {
        uint8_t *dst = f.candidate + 16u + off + i;
        if ((*dst & src[i]) != src[i])
        {
            f.order_ok = 0;
            return -1;
        }
        *dst &= src[i];
    }
    f.programmed += len;
    f.last_write = len;
    if (len > f.max_write) f.max_write = len;
    f.pending_off = off;
    f.pending_len = len;
    return 0;
}

static int candidate_read(void *ctx, uint32_t off, uint8_t *dst, uint32_t len)
{
    int readback = f.pending_len != 0u;
    (void)ctx;
    if (storage_entry(readback) || !dst || off > f.prepared ||
        len > f.prepared - off) return -1;
    if (readback)
    {
        ++f.readbacks;
        if (off != f.pending_off || len != f.pending_len) f.order_ok = 0;
        f.pending_len = 0u;
        if (inject("readback", f.readbacks)) return -1;
    }
    else if (inject("final-read", ++f.final_reads)) return -1;
    memcpy(dst, f.candidate + 16u + off, len);
    if (readback && inject("corrupt", f.readbacks)) dst[len - 1u] ^= 1u;
    return 0;
}

static int workspace_acquire(void *ctx, uint8_t **dst, uint32_t *len)
{
    (void)ctx;
    if (f.acquires++) return -1;
    *dst = f.workspace.bytes + 16u;
    *len = OTA_PATCH_WORKSPACE_SIZE;
    return 0;
}

static void workspace_release(void *ctx, uint8_t *dst, uint32_t len)
{
    uint32_t i;
    (void)ctx;
    ++f.releases;
    f.wiped = dst == f.workspace.bytes + 16u && len == OTA_PATCH_WORKSPACE_SIZE;
    for (i = 0u; i < len && i < OTA_PATCH_WORKSPACE_SIZE; ++i)
        if (dst[i]) f.wiped = 0;
}

static int guards_intact(void)
{
    uint32_t i;
    for (i = 0u; i < 16u; ++i)
    {
        if (f.workspace.bytes[i] != 0xA5 ||
            f.workspace.bytes[OTA_PATCH_WORKSPACE_SIZE + 16u + i] != 0xA5 ||
            f.candidate[i] != 0xA5 ||
            f.candidate[OTA_APP_LENGTH + 16u + i] != 0xA5) return 0;
    }
    for (i = f.prepared; i < OTA_APP_LENGTH; ++i)
        if (f.candidate[16u + i] != 0xA5) return 0;
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
    uint8_t digest[32];
    char *end;
    unsigned long fail_at;
    int equal, guards, lifecycle, metadata, passed;
    if (argc != 7)
    {
        fprintf(stderr, "usage: patch_oracle PACKAGE BASE TARGET RESULT FAULT N\n");
        return 2;
    }
    fail_at = strtoul(argv[6], &end, 10);
    if (*end || fail_at > UINT32_MAX ||
        load_blob(argv[1], &f.package) || load_blob(argv[2], &f.base) ||
        load_blob(argv[3], &f.target) || f.base.len < 0x460u ||
        f.base.len > OTA_APP_LENGTH || f.target.len > OTA_APP_LENGTH) return 2;
    f.fail_kind = argv[5];
    f.fail_at = (uint32_t)fail_at;
    f.order_ok = f.shape_ok = 1;
    memset(f.candidate, 0xA5, sizeof(f.candidate));
    memset(f.workspace.bytes, 0xA5, sizeof(f.workspace.bytes));
    memset(&device, 0, sizeof(device));
    memset(&info, 0, sizeof(info));
    io.ctx = &f;
    io.package_read = package_read;
    io.base_read = base_read;
    io.candidate_prepare = candidate_prepare;
    io.candidate_program = candidate_program;
    io.candidate_read = candidate_read;
    io.workspace_acquire = workspace_acquire;
    io.workspace_release = workspace_release;
    device.current_vcode = u32le(f.base.bytes + 0x408u);
    device.hardware_rev = device.layout_id = device.boot_version = 1u;
    device.base_image_len = f.base.len;
    boot_sha256_init(&sha);
    boot_sha256_update(&sha, f.base.bytes, f.base.len);
    boot_sha256_final(&sha, digest);
    memcpy(device.base_image_sha8, digest, sizeof(device.base_image_sha8));
    result = ota_patch_apply(&io, &device, f.package.len, &info);
    equal = f.programmed == f.target.len && info.image_len == f.target.len &&
            memcmp(f.candidate + 16u, f.target.bytes, f.target.len) == 0;
    guards = guards_intact();
    lifecycle = f.acquires == f.releases && f.acquires <= 1u && (!f.acquires || f.wiped);
    metadata = result == OTA_PATCH_OK || (info.image_len == 0u &&
               info.target_vcode == 0u && info.workspace_peak == 0u);
    passed = strcmp(ota_patch_result_name(result), argv[4]) == 0 &&
             guards && lifecycle && metadata && f.order_ok && f.shape_ok &&
             f.pending_len == 0u && f.after_fault == 0u &&
             (strcmp(f.fail_kind, "none") == 0 || f.faulted) &&
             (result != OTA_PATCH_OK || (equal && info.workspace_peak != 0u &&
                                        info.workspace_peak <= OTA_PATCH_WORKSPACE_SIZE));
    printf("{\"result\":\"%s\",\"passed\":%d,\"coalesce\":%d,"
           "\"byte_identical\":%d,\"guards_ok\":%d,\"lifecycle_ok\":%d,"
           "\"failure_metadata_ok\":%d,\"order_ok\":%d,\"shape_ok\":%d,"
           "\"programs\":%u,\"programmed\":%u,\"max_write\":%u,\"last_write\":%u,"
           "\"readbacks\":%u,\"final_reads\":%u,\"after_fault\":%u,"
           "\"faulted\":%d,\"prepares\":%u,\"workspace_peak\":%u}\n",
           ota_patch_result_name(result), passed, OTA_PATCH_COALESCE_WRITES,
           equal, guards, lifecycle, metadata, f.order_ok, f.shape_ok,
           (unsigned)f.programs, (unsigned)f.programmed, (unsigned)f.max_write,
           (unsigned)f.last_write, (unsigned)f.readbacks, (unsigned)f.final_reads,
           (unsigned)f.after_fault, f.faulted, (unsigned)f.prepares,
           (unsigned)info.workspace_peak);
    free(f.package.bytes);
    free(f.base.bytes);
    free(f.target.bytes);
    return passed ? 0 : 1;
}
