#include "writer.h"
#include "boot_crypto.h"
#include <string.h>

#define RR_BASE 0x200000u
#define RR_LIMIT 0x300000u
#define RR_MAX 0xf0000u

static int range_ok(uint32_t address, uint32_t length)
{
    return address >= RR_BASE && address < RR_LIMIT && length != 0u &&
           length <= RR_LIMIT - address;
}

static int page_write(const rr_io *io, uint32_t address,
                      const uint8_t *data, uint32_t length)
{
    if (!range_ok(address, length) || length > 256u ||
        length > 256u - (address & 255u))
        return RR_ARGUMENT;
    return io->program(io->ctx, address, data, length) == 0 ? RR_OK : RR_IO;
}

static int erase_checked(const rr_io *io, rr_workspace *w, uint32_t address)
{
    uint32_t offset, i;
    if (!range_ok(address, 4096u) || (address & 4095u))
        return RR_ARGUMENT;
    if (io->erase(io->ctx, address) != 0)
        return RR_IO;
    for (offset = 0; offset < 4096u; offset += 256u) {
        if (io->read(io->ctx, address+offset, w->check, 256u) != 0)
            return RR_IO;
        for (i = 0; i < 256u; ++i)
            if (w->check[i] != 0xffu)
                return RR_VERIFY;
    }
    return RR_OK;
}

typedef struct {
    const rr_io *io;
    rr_workspace *w;
    int external;
    int captured;
} reader_context;

static int image_read(void *ctx, uint32_t offset, uint8_t *dst, size_t len)
{
    reader_context *r = (reader_context *)ctx;
    int result;
    if (offset > r->w->length || len > r->w->length-offset)
        return -1;
    result = r->external ? r->io->read(r->io->ctx, RR_BASE+4096u+offset, dst, (uint32_t)len)
                         : r->io->source(r->io->ctx, offset, dst, (uint32_t)len);
    if (result == 0 && !r->external && !r->captured && offset == 0x400u && len == 96u) {
        memcpy(r->w->captured_header, dst, 96u);
        r->captured = 1;
    }
    return result;
}

static int validate(reader_context *ctx, boot_fw_header_t *header)
{
    boot_image_reader_t reader;
    boot_fw_expectations_t expected;
    reader.read = image_read;
    reader.ctx = ctx;
    boot_fw_default_expectations(&expected);
    return boot_fw_header_validate(&reader, &expected, header) == BOOT_FW_OK &&
           header->image_len == ctx->w->length;
}

static void put32(uint8_t *p, uint32_t n)
{
    unsigned i;
    for (i = 0; i < 4; ++i) p[i] = (uint8_t)(n >> (8u*i));
}

static int verify_payload(const rr_io *io, rr_workspace *w)
{
    uint32_t offset, take;
    uint8_t digest[32];
    boot_sha256_ctx_t sha;
    boot_sha256_init(&sha);
    for (offset = 0; offset < w->length; offset += take) {
        take = w->length-offset;
        if (take > 256u) take = 256u;
        if (io->read(io->ctx, RR_BASE+4096u+offset, w->check, take) != 0)
            return RR_IO;
        boot_sha256_update(&sha, w->check, take);
    }
    boot_sha256_final(&sha, digest);
    return memcmp(digest, w->pinned, 32u) == 0 ? RR_OK : RR_VERIFY;
}

int rr_run(const rr_io *io, rr_workspace *w, uint32_t length, const uint8_t pinned_sha[32])
{
    reader_context reader;
    boot_sha256_ctx_t sha, chunk_sha;
    boot_crc32_ctx_t crc;
    boot_fw_header_t verified;
    uint8_t digest[32], metadata[32];
    uint32_t offset, take, index, page, size;
    int rc;
    if (!io || !w || !pinned_sha || !io->source || !io->read || !io->erase || !io->program ||
        length < 0x460u || length > RR_MAX)
        return RR_ARGUMENT;
    w->length = length;
    memcpy(w->pinned, pinned_sha, 32u);
    reader.io = io; reader.w = w; reader.external = 0; reader.captured = 0;
    if (!validate(&reader, &w->header) || !reader.captured)
        return RR_SOURCE;
    boot_sha256_init(&sha);
    boot_crc32_init(&crc);
    /* Only this pre-write pass populates the manifest. It is never regenerated
     * from the second delivery, including on an error return. */
    for (offset = 0, index = 0; offset < length; offset += take, ++index) {
        take = length-offset;
        if (take > 4096u) take = 4096u;
        if (io->source(io->ctx, offset, w->block, take) != 0)
            return RR_SOURCE;
        if (offset == 0 && memcmp(w->block+0x400u, w->captured_header, 96u) != 0)
            return RR_SOURCE;
        boot_sha256_update(&sha, w->block, take);
        boot_crc32_update(&crc, w->block, take);
        boot_sha256_init(&chunk_sha);
        boot_sha256_update(&chunk_sha, w->block, take);
        boot_sha256_final(&chunk_sha, w->chunks[index]);
    }
    boot_sha256_final(&sha, digest);
    if (memcmp(digest, w->pinned, 32u) != 0)
        return RR_SOURCE;
    w->payload_crc = boot_crc32_final(&crc);
    rc = erase_checked(io, w, RR_BASE);
    if (rc != RR_OK) return rc;
    for (offset = 0, index = 0; offset < length; offset += take, ++index) {
        take = length-offset;
        if (take > 4096u) take = 4096u;
        if (io->source(io->ctx, offset, w->block, take) != 0)
            return RR_SOURCE;
        boot_sha256_init(&chunk_sha);
        boot_sha256_update(&chunk_sha, w->block, take);
        boot_sha256_final(&chunk_sha, digest);
        if (memcmp(digest, w->chunks[index], 32u) != 0)
            return RR_SOURCE;
        rc = erase_checked(io, w, RR_BASE+4096u+offset);
        if (rc != RR_OK) return rc;
        for (page = 0; page < take; page += size) {
            size = take-page;
            if (size > 256u) size = 256u;
            rc = page_write(io, RR_BASE+4096u+offset+page, w->block+page, size);
            if (rc != RR_OK) return rc;
            if (io->read(io->ctx, RR_BASE+4096u+offset+page, w->check, size) != 0)
                return RR_IO;
            if (memcmp(w->check, w->block+page, size) != 0)
                return RR_VERIFY;
        }
    }
    rc = verify_payload(io, w);
    if (rc != RR_OK) return rc;
    reader.external = 1;
    if (!validate(&reader, &verified) || verified.version_code != w->header.version_code ||
        memcmp(verified.image_sha256, w->header.image_sha256, 32u) != 0)
        return RR_VERIFY;
    memset(metadata, 0xff, sizeof(metadata));
    memcpy(metadata, "ETSL", 4u); metadata[4] = 4u;
    put32(metadata+8, length); put32(metadata+12, w->payload_crc);
    put32(metadata+16, w->header.version_code);
    memcpy(metadata+20, w->header.image_sha256, 8u);
    rc = page_write(io, RR_BASE, metadata, 28u);
    if (rc != RR_OK) return rc;
    if (io->read(io->ctx, RR_BASE, w->check, 32u) != 0) return RR_IO;
    if (memcmp(metadata, w->check, 32u) != 0) return RR_VERIFY;
    memcpy(metadata+28, "TMOC", 4u);
    rc = page_write(io, RR_BASE+28u, metadata+28, 4u);
    if (rc != RR_OK) return rc;
    if (io->read(io->ctx, RR_BASE, w->check, 32u) != 0) return RR_IO;
    if (memcmp(metadata, w->check, 32u) != 0) return RR_VERIFY;
    return verify_payload(io, w);
}
