#include "boot_crypto.h"

#include <string.h>

#define ROTR32(value, bits) (((value) >> (bits)) | ((value) << (32u - (bits))))

static const uint32_t k_sha256[64] = {
    0x428A2F98u, 0x71374491u, 0xB5C0FBCFu, 0xE9B5DBA5u,
    0x3956C25Bu, 0x59F111F1u, 0x923F82A4u, 0xAB1C5ED5u,
    0xD807AA98u, 0x12835B01u, 0x243185BEu, 0x550C7DC3u,
    0x72BE5D74u, 0x80DEB1FEu, 0x9BDC06A7u, 0xC19BF174u,
    0xE49B69C1u, 0xEFBE4786u, 0x0FC19DC6u, 0x240CA1CCu,
    0x2DE92C6Fu, 0x4A7484AAu, 0x5CB0A9DCu, 0x76F988DAu,
    0x983E5152u, 0xA831C66Du, 0xB00327C8u, 0xBF597FC7u,
    0xC6E00BF3u, 0xD5A79147u, 0x06CA6351u, 0x14292967u,
    0x27B70A85u, 0x2E1B2138u, 0x4D2C6DFCu, 0x53380D13u,
    0x650A7354u, 0x766A0ABBu, 0x81C2C92Eu, 0x92722C85u,
    0xA2BFE8A1u, 0xA81A664Bu, 0xC24B8B70u, 0xC76C51A3u,
    0xD192E819u, 0xD6990624u, 0xF40E3585u, 0x106AA070u,
    0x19A4C116u, 0x1E376C08u, 0x2748774Cu, 0x34B0BCB5u,
    0x391C0CB3u, 0x4ED8AA4Au, 0x5B9CCA4Fu, 0x682E6FF3u,
    0x748F82EEu, 0x78A5636Fu, 0x84C87814u, 0x8CC70208u,
    0x90BEFFFAu, 0xA4506CEBu, 0xBEF9A3F7u, 0xC67178F2u
};

static uint32_t read_be32(const uint8_t *src)
{
    return ((uint32_t)src[0] << 24) |
           ((uint32_t)src[1] << 16) |
           ((uint32_t)src[2] << 8) |
           (uint32_t)src[3];
}

static void write_be32(uint8_t *dst, uint32_t value)
{
    dst[0] = (uint8_t)(value >> 24);
    dst[1] = (uint8_t)(value >> 16);
    dst[2] = (uint8_t)(value >> 8);
    dst[3] = (uint8_t)value;
}

static void sha256_transform(boot_sha256_ctx_t *ctx, const uint8_t block[64])
{
    uint32_t w[64];
    uint32_t a;
    uint32_t b;
    uint32_t c;
    uint32_t d;
    uint32_t e;
    uint32_t f;
    uint32_t g;
    uint32_t h;
    uint32_t i;

    for (i = 0u; i < 16u; ++i)
    {
        w[i] = read_be32(block + (i * 4u));
    }
    for (i = 16u; i < 64u; ++i)
    {
        uint32_t s0 = ROTR32(w[i - 15u], 7u) ^ ROTR32(w[i - 15u], 18u) ^
                      (w[i - 15u] >> 3u);
        uint32_t s1 = ROTR32(w[i - 2u], 17u) ^ ROTR32(w[i - 2u], 19u) ^
                      (w[i - 2u] >> 10u);
        w[i] = w[i - 16u] + s0 + w[i - 7u] + s1;
    }

    a = ctx->state[0];
    b = ctx->state[1];
    c = ctx->state[2];
    d = ctx->state[3];
    e = ctx->state[4];
    f = ctx->state[5];
    g = ctx->state[6];
    h = ctx->state[7];

    for (i = 0u; i < 64u; ++i)
    {
        uint32_t sum1 = ROTR32(e, 6u) ^ ROTR32(e, 11u) ^ ROTR32(e, 25u);
        uint32_t choice = (e & f) ^ ((~e) & g);
        uint32_t temp1 = h + sum1 + choice + k_sha256[i] + w[i];
        uint32_t sum0 = ROTR32(a, 2u) ^ ROTR32(a, 13u) ^ ROTR32(a, 22u);
        uint32_t majority = (a & b) ^ (a & c) ^ (b & c);
        uint32_t temp2 = sum0 + majority;

        h = g;
        g = f;
        f = e;
        e = d + temp1;
        d = c;
        c = b;
        b = a;
        a = temp1 + temp2;
    }

    ctx->state[0] += a;
    ctx->state[1] += b;
    ctx->state[2] += c;
    ctx->state[3] += d;
    ctx->state[4] += e;
    ctx->state[5] += f;
    ctx->state[6] += g;
    ctx->state[7] += h;
}

void boot_sha256_init(boot_sha256_ctx_t *ctx)
{
    if (ctx == NULL)
    {
        return;
    }

    ctx->state[0] = 0x6A09E667u;
    ctx->state[1] = 0xBB67AE85u;
    ctx->state[2] = 0x3C6EF372u;
    ctx->state[3] = 0xA54FF53Au;
    ctx->state[4] = 0x510E527Fu;
    ctx->state[5] = 0x9B05688Cu;
    ctx->state[6] = 0x1F83D9ABu;
    ctx->state[7] = 0x5BE0CD19u;
    ctx->total_len = 0u;
    ctx->block_len = 0u;
}

void boot_sha256_update(boot_sha256_ctx_t *ctx, const uint8_t *data, size_t len)
{
    size_t offset = 0u;

    if (ctx == NULL || (data == NULL && len != 0u))
    {
        return;
    }

    ctx->total_len += len;
    while (offset < len)
    {
        size_t room = sizeof(ctx->block) - ctx->block_len;
        size_t take = (len - offset < room) ? len - offset : room;

        memcpy(ctx->block + ctx->block_len, data + offset, take);
        ctx->block_len += take;
        offset += take;
        if (ctx->block_len == sizeof(ctx->block))
        {
            sha256_transform(ctx, ctx->block);
            ctx->block_len = 0u;
        }
    }
}

void boot_sha256_final(boot_sha256_ctx_t *ctx, uint8_t digest[32])
{
    uint64_t bit_len;
    uint32_t i;

    if (ctx == NULL || digest == NULL)
    {
        return;
    }

    bit_len = ctx->total_len * 8u;
    ctx->block[ctx->block_len++] = 0x80u;

    if (ctx->block_len > 56u)
    {
        memset(ctx->block + ctx->block_len, 0, sizeof(ctx->block) - ctx->block_len);
        sha256_transform(ctx, ctx->block);
        ctx->block_len = 0u;
    }

    memset(ctx->block + ctx->block_len, 0, 56u - ctx->block_len);
    ctx->block[56] = (uint8_t)(bit_len >> 56);
    ctx->block[57] = (uint8_t)(bit_len >> 48);
    ctx->block[58] = (uint8_t)(bit_len >> 40);
    ctx->block[59] = (uint8_t)(bit_len >> 32);
    ctx->block[60] = (uint8_t)(bit_len >> 24);
    ctx->block[61] = (uint8_t)(bit_len >> 16);
    ctx->block[62] = (uint8_t)(bit_len >> 8);
    ctx->block[63] = (uint8_t)bit_len;
    sha256_transform(ctx, ctx->block);

    for (i = 0u; i < 8u; ++i)
    {
        write_be32(digest + (i * 4u), ctx->state[i]);
    }

    memset(ctx, 0, sizeof(*ctx));
}
