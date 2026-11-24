#include "writer.c"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>

static uint8_t image[RR_MAX], nor[0x100000];
static rr_workspace workspace;
static uint32_t image_len, mutations, fault_at;
static int mode, fired;

static int source(void *ctx, uint32_t offset, uint8_t *dst, uint32_t len)
{
    (void)ctx;
    assert(offset <= image_len && len <= image_len-offset);
    memcpy(dst, image+offset, len);
    if (mode == 9 && mutations && !fired) {
        dst[0] ^= 1u; fired = 1; fault_at = mutations;
    }
    return 0;
}

static int read_nor(void *ctx, uint32_t address, uint8_t *dst, uint32_t len)
{
    (void)ctx;
    assert(range_ok(address, len));
    if (mode == 10 && !fired) {
        fired = 1; fault_at = mutations; return -1;
    }
    memcpy(dst, nor+address-RR_BASE, len);
    return 0;
}

static int erase(void *ctx, uint32_t address)
{
    (void)ctx;
    assert(range_ok(address, 4096u) && !(address & 4095u));
    ++mutations;
    memset(nor+address-RR_BASE, 0xff, 4096u);
    if (!fired && ((mode == 1 && address == RR_BASE) ||
                   (mode == 11 && address != RR_BASE))) {
        nor[address-RR_BASE] = 0; fired = 1; fault_at = mutations;
    }
    if (!fired && mode == 5) {
        fired = 1; fault_at = mutations; return -1;
    }
    return 0;
}

static int program(void *ctx, uint32_t address, const uint8_t *src, uint32_t len)
{
    uint32_t i;
    (void)ctx;
    assert(range_ok(address, len) && len <= 256u-(address & 255u));
    ++mutations;
    for (i = 0; i < len; ++i) nor[address-RR_BASE+i] &= src[i];
    if (!fired && ((mode == 2 && address >= RR_BASE+4096u) ||
                   (mode == 3 && address == RR_BASE))) {
        nor[address-RR_BASE] ^= 1u; fired = 1; fault_at = mutations;
    }
    if (!fired && mode == 4 && address == RR_BASE+28u) {
        nor[4096u] ^= 1u; fired = 1; fault_at = mutations;
    }
    if (!fired && ((mode == 6 && address >= RR_BASE+4096u) ||
                   (mode == 7 && address == RR_BASE) ||
                   (mode == 8 && address == RR_BASE+28u))) {
        fired = 1; fault_at = mutations; return -1;
    }
    return 0;
}

int main(int argc, char **argv)
{
    FILE *f;
    rr_io io = {NULL, source, read_nor, erase, program};
    boot_sha256_ctx_t sha;
    uint8_t pinned[32];
    int rc;
    unsigned cases = 0;
    uint32_t i, rounded;
    if (argc != 2 || (f = fopen(argv[1], "rb")) == NULL) return 2;
    image_len = (uint32_t)fread(image, 1, sizeof(image), f);
    assert(!ferror(f) && fgetc(f) == EOF && image_len >= 0x460u);
    fclose(f);
    boot_sha256_init(&sha); boot_sha256_update(&sha, image, image_len);
    boot_sha256_final(&sha, pinned);
    for (mode = 0; mode <= 11; ++mode) {
        memset(nor, 0xa5, sizeof(nor));
        mutations = fault_at = 0; fired = 0;
        rc = rr_run(&io, &workspace, image_len, pinned);
        if (mode == 0) {
            assert(rc == RR_OK && memcmp(nor+4096u, image, image_len) == 0);
            assert(memcmp(nor+28, "TMOC", 4) == 0);
            rounded = (4096u+image_len+4095u) & ~4095u;
            for (i = rounded; i < sizeof(nor); ++i) assert(nor[i] == 0xa5u);
        } else {
            assert(rc != RR_OK && fired && mutations == fault_at);
        }
        printf("CASE mode=%d rc=%d writes=%lu\n", mode, rc, (unsigned long)mutations);
        ++cases;
    }
    mode = 0; mutations = 0;
    assert(!range_ok(RR_BASE-1u, 1u));
    assert(!range_ok(RR_LIMIT, 1u));
    assert(!range_ok(RR_LIMIT-1u, 2u));
    assert(!range_ok(RR_BASE, UINT32_MAX));
    assert(page_write(&io, RR_BASE+255u, image, 2u) == RR_ARGUMENT);
    assert(page_write(&io, RR_BASE, image, 257u) == RR_ARGUMENT);
    assert(erase_checked(&io, &workspace, RR_BASE+1u) == RR_ARGUMENT);
    assert(erase_checked(&io, &workspace, RR_LIMIT) == RR_ARGUMENT);
    assert(rr_run(&io, &workspace, UINT32_MAX, pinned) == RR_ARGUMENT);
    assert(rr_run(&io, &workspace, 0, pinned) == RR_ARGUMENT);
    pinned[0] ^= 1u;
    assert(rr_run(&io, &workspace, image_len, pinned) == RR_SOURCE);
    assert(mutations == 0);
    cases += 11;
    printf("RAM_WRITER_HOST_PASS cases=%u workspace=%lu\n", cases, (unsigned long)sizeof(workspace));
    return 0;
}
