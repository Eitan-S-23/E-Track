/* Deterministic streaming/unaligned vectors for the unchanged SHA implementation. */
#include "boot_crypto.h"
#include <stdio.h>
#include <string.h>

static unsigned char input[617494];

int main(void)
{
    static const size_t lengths[] = {0, 1, 55, 56, 63, 64, 65, 255, 256, 257,
                                    4095, 4096, 617492};
    static const size_t chunks[] = {1, 7, 63, 64, 65, 256, 4096, 617492};
    size_t i, j, alignment, at, k;
    for (i = 0; i < sizeof(input); ++i) input[i] = (unsigned char)(i * 17u + 3u);
    for (i = 0; i < sizeof(lengths) / sizeof(lengths[0]); ++i)
    for (j = 0; j < sizeof(chunks) / sizeof(chunks[0]); ++j)
    for (alignment = 0; alignment < 2; ++alignment)
    {
        boot_sha256_ctx_t ctx;
        unsigned char digest[32];
        boot_sha256_init(&ctx);
        boot_sha256_update(&ctx, NULL, 0);
        for (at = 0; at < lengths[i]; at += k)
        {
            k = lengths[i] - at;
            if (k > chunks[j]) k = chunks[j];
            boot_sha256_update(&ctx, input + alignment + at, k);
        }
        boot_sha256_final(&ctx, digest);
        for (k = 0; k < sizeof(ctx); ++k)
            if (((unsigned char *)&ctx)[k] != 0) return 2;
        printf("%lu %lu %lu ", (unsigned long)lengths[i],
               (unsigned long)chunks[j], (unsigned long)alignment);
        for (k = 0; k < sizeof(digest); ++k) printf("%02x", digest[k]);
        putchar('\n');
    }
    return 0;
}
