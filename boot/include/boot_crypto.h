#ifndef E_TRACK_BOOT_CRYPTO_H
#define E_TRACK_BOOT_CRYPTO_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct
{
    uint32_t value;
} boot_crc32_ctx_t;

void boot_crc32_init(boot_crc32_ctx_t *ctx);
void boot_crc32_update(boot_crc32_ctx_t *ctx, const uint8_t *data, size_t len);
uint32_t boot_crc32_final(const boot_crc32_ctx_t *ctx);
uint32_t boot_crc32(const uint8_t *data, size_t len);

typedef struct
{
    uint32_t state[8];
    uint64_t total_len;
    uint8_t block[64];
    size_t block_len;
} boot_sha256_ctx_t;

void boot_sha256_init(boot_sha256_ctx_t *ctx);
void boot_sha256_update(boot_sha256_ctx_t *ctx, const uint8_t *data, size_t len);
void boot_sha256_final(boot_sha256_ctx_t *ctx, uint8_t digest[32]);

#ifdef __cplusplus
}
#endif

#endif
