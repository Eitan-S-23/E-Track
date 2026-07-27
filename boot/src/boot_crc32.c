#include "boot_crypto.h"

void boot_crc32_init(boot_crc32_ctx_t *ctx)
{
    if (ctx != NULL)
    {
        ctx->value = 0xFFFFFFFFu;
    }
}

void boot_crc32_update(boot_crc32_ctx_t *ctx, const uint8_t *data, size_t len)
{
    size_t i;

    if (ctx == NULL || (data == NULL && len != 0u))
    {
        return;
    }

    for (i = 0u; i < len; ++i)
    {
        uint32_t value = ctx->value ^ data[i];
        uint32_t bit;

        for (bit = 0u; bit < 8u; ++bit)
        {
            value = (value & 1u) != 0u
                        ? (value >> 1) ^ 0xEDB88320u
                        : value >> 1;
        }
        ctx->value = value;
    }
}

uint32_t boot_crc32_final(const boot_crc32_ctx_t *ctx)
{
    return ctx == NULL ? 0u : ctx->value ^ 0xFFFFFFFFu;
}

uint32_t boot_crc32(const uint8_t *data, size_t len)
{
    boot_crc32_ctx_t ctx;

    boot_crc32_init(&ctx);
    boot_crc32_update(&ctx, data, len);
    return boot_crc32_final(&ctx);
}
