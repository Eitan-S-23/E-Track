#include "boot_crypto.h"
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

void reference_init(boot_crc32_ctx_t *ctx);
void reference_update(boot_crc32_ctx_t *ctx, const uint8_t *data, size_t len);
uint32_t reference_final(const boot_crc32_ctx_t *ctx);
uint32_t reference_crc(const uint8_t *data, size_t len);

static unsigned checks;
static uint8_t data[65536];
static volatile uint32_t sink;
#define CHECK(x) do { ++checks; if (!(x)) { \
    fprintf(stderr, "CRC_FAIL line=%d\n", __LINE__); exit(1); \
} } while (0)

int main(void)
{
    size_t i, len;
    uint32_t seed = 0x12345678u;
    clock_t start;
    double slow, fast;
    boot_crc32_ctx_t a, b;
    CHECK(boot_crc32((const uint8_t *)"123456789", 9) == 0xCBF43926u);
    CHECK(boot_crc32(NULL, 0) == 0);
    CHECK(boot_crc32_final(NULL) == 0);
    boot_crc32_init(NULL);
    boot_crc32_update(NULL, data, 1);
    boot_crc32_init(&a);
    boot_crc32_update(&a, NULL, 1);
    CHECK(a.value == 0xFFFFFFFFu);
    for (i = 0; i < sizeof(data); ++i)
    {
        seed = seed * 1664525u + 1013904223u;
        data[i] = (uint8_t)(seed >> 24);
    }
    for (len = 0; len <= 4096; ++len)
    {
        CHECK(boot_crc32(data, len) == reference_crc(data, len));
        a.value = b.value = seed ^ (uint32_t)len;
        boot_crc32_update(&a, data, len);
        reference_update(&b, data, len);
        CHECK(a.value == b.value);
    }
    for (len = 1; len <= 513; ++len)
    {
        boot_crc32_init(&a);
        reference_init(&b);
        for (i = 0; i < sizeof(data);)
        {
            size_t take = sizeof(data) - i;
            if (take > len) take = len;
            boot_crc32_update(&a, data+i, take);
            reference_update(&b, data+i, take);
            i += take;
        }
        CHECK(boot_crc32_final(&a) == reference_final(&b));
        CHECK(boot_crc32_final(&a) == reference_crc(data, sizeof(data)));
    }
    start = clock();
    for (i = 0; i < 256; ++i) sink ^= reference_crc(data, sizeof(data));
    slow = (double)(clock()-start)/CLOCKS_PER_SEC;
    start = clock();
    for (i = 0; i < 256; ++i) sink ^= boot_crc32(data, sizeof(data));
    fast = (double)(clock()-start)/CLOCKS_PER_SEC;
    printf("CRC_EQUIVALENCE_PASS checks=%u reference_seconds=%.6f candidate_seconds=%.6f host_only=1\n",
           checks, slow, fast);
    return 0;
}
