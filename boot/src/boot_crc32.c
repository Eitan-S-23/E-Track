#include "boot_crypto.h"

/* Development App opt-in only; unchanged bitwise path remains the default. */
#ifndef CONFIG_OTA_APP_CRC32_NIBBLE
#define CONFIG_OTA_APP_CRC32_NIBBLE 0
#endif

#if CONFIG_OTA_APP_CRC32_NIBBLE
static const uint32_t crc32_nibbles[16] = {
    0x00000000u, 0x1DB71064u, 0x3B6E20C8u, 0x26D930ACu,
    0x76DC4190u, 0x6B6B51F4u, 0x4DB26158u, 0x5005713Cu,
    0xEDB88320u, 0xF00F9344u, 0xD6D6A3E8u, 0xCB61B38Cu,
    0x9B64C2B0u, 0x86D3D2D4u, 0xA00AE278u, 0xBDBDF21Cu
};
#endif

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
#if CONFIG_OTA_APP_CRC32_NIBBLE
        value = (value >> 4) ^ crc32_nibbles[value & 0xFu];
        value = (value >> 4) ^ crc32_nibbles[value & 0xFu];
#else
        uint32_t bit;

        for (bit = 0u; bit < 8u; ++bit)
        {
            value = (value & 1u) != 0u
                        ? (value >> 1) ^ 0xEDB88320u
                        : value >> 1;
        }
#endif
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
