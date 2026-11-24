#include "source_mailbox.h"
#include "boot_crypto.h"
#include <string.h>

static void barrier(void)
{
#if defined(__arm__) || defined(__thumb__)
    __asm volatile("dmb" ::: "memory");
#else
    __asm volatile("" ::: "memory");
#endif
}

int rr_source_init(rr_source *s, rr_source_mailbox *b, uint32_t length,
                   const uint32_t generation[2], uint32_t timeout,
                   uint32_t (*now)(void *), void *ctx)
{
    if (!s || !b || !generation || !now || length < 0x460u || length > 0xf0000u ||
        !timeout || timeout > 0x7fffffffu || !(generation[0] | generation[1])) return -1;
    memset(s,0,sizeof(*s));
    s->box = b; s->source_length = length; s->timeout_ticks = timeout;
    s->now = now; s->clock_ctx = ctx;
    s->generation[0] = generation[0]; s->generation[1] = generation[1];
    b->request_commit = 0; b->response_commit = 0;
    b->generation[0] = generation[0]; b->generation[1] = generation[1];
    barrier();
    return 0;
}

static int fetch(rr_source *s, uint32_t offset)
{
    rr_source_mailbox *b = s->box;
    uint32_t len = s->source_length-offset, started, attempt, i, crc;
    if (len > 4096u) len = 4096u;
    if (s->sequence == UINT32_MAX) return -1;
    s->cache_length = 0;
    b->request_commit = 0;
    b->response_commit = 0;
    b->request_offset = offset; b->request_length = len;
    ++s->sequence;
    barrier();
    b->request_commit = s->sequence;
    barrier();
    started = s->now(s->clock_ctx);
    for (attempt = 0; attempt < 20000000u; ++attempt) {
        if ((uint32_t)(s->now(s->clock_ctx)-started) >= s->timeout_ticks) return -1;
        if (b->response_commit != s->sequence) continue;
        barrier();
        if (b->response_generation[0] != s->generation[0] ||
            b->response_generation[1] != s->generation[1] ||
            b->response_offset != offset || b->response_length != len) return -1;
        crc = b->response_crc;
        for (i = 0; i < len; ++i) s->cache[i] = b->response_data[i];
        barrier();
        if (b->response_commit != s->sequence || b->response_crc != crc ||
            b->response_generation[0] != s->generation[0] ||
            b->response_generation[1] != s->generation[1] ||
            b->response_offset != offset || b->response_length != len ||
            boot_crc32(s->cache,len) != crc) return -1;
        s->cache_offset = offset; s->cache_length = len;
        return 0;
    }
    return -1;
}

int rr_source_read(void *ctx, uint32_t offset, uint8_t *dst, uint32_t length)
{
    rr_source *s = ctx;
    uint32_t copied = 0, take, position, within;
    if (!s) return -1;
    if (s->failed || !dst || !length || length > 4096u ||
        offset > s->source_length || length > s->source_length-offset) {
        s->failed = 1; return -1;
    }
    while (copied < length) {
        position = offset+copied;
        if (!s->cache_length || position < s->cache_offset ||
            position-s->cache_offset >= s->cache_length)
            if (fetch(s, position & ~4095u) != 0) {
                s->failed = 1; return -1;
            }
        within = position-s->cache_offset;
        take = s->cache_length-within;
        if (take > length-copied) take = length-copied;
        memcpy(dst+copied,s->cache+within,take);
        copied += take;
    }
    return 0;
}
