#include "supervisor.h"

typedef struct { const re_profile *profile; uint32_t writes; int failed; } owner;

static int qualified(owner *s, re_hw_snapshot *h)
{
    if (s->failed || re_platform_snapshot(h) != 0 || !re_snapshot_matches(s->profile, h))
        goto fail;
    return 1;
fail:
    s->failed=1;
    return 0;
}

static int sample(void *ctx, re_sample *out)
{
    owner *s=ctx;
    re_hw_snapshot h;
    if (!qualified(s,&h)) return -1;
    out->epoch=s->profile->epoch; out->hz=s->profile->hz; out->ticks=h.ticks;
    return 0;
}
static int owned(void *ctx)
{
    re_hw_snapshot h;
    return qualified(ctx,&h);
}
static int read32(void *ctx, uint32_t off, uint32_t *v)
{
    owner *s=ctx;
    if (!owned(s) || re_platform_read32(off,v) != 0) { s->failed=1; return -1; }
    return 0;
}
static int write32(void *ctx, uint32_t off, uint32_t value)
{
    owner *s=ctx;
    static const uint32_t expected[4]={0u,0x01000000u,1u,0x05000000u};
    if (s->writes>=4u || off!=s->writes*4u || value!=expected[s->writes] || !owned(s))
        goto fail;
    ++s->writes;
    if (re_platform_write32(off,value)!=0) goto fail;
    return 0;
fail:
    s->failed=1;
    return -1;
}
static int read8(void *ctx, uint32_t off, uint8_t *v)
{
    owner *s=ctx;
    if (s->writes!=4u || off!=0x100u || !owned(s) || re_platform_read8(off,v)!=0) {
        s->failed=1; return -1;
    }
    return 0;
}

re_observation re_supervise_once(re_session *session, const re_profile *p,
                                 const uint8_t operation[32], uint8_t *status)
{
    unsigned i;
    uint8_t nonzero=0;
    owner s;
    re_clock clock;
    re_status_io io;
    if (!session || session->consumed) return RE_OBS_UNKNOWN;
    /* Consume even rejected calls; there is no reset/retry entry. */
    session->consumed=1;
    if (!p || !operation || !status || !p->epoch || p->hz!=288000000u ||
        !p->budget || p->budget>28800000u || p->entry_qualified!=1u ||
        p->media_qualified!=1u || p->clock_qualified!=1u || p->ownership_qualified!=1u)
        return RE_OBS_UNKNOWN;
    for (i=0;i<32;++i) {
        if (p->operation[i]!=operation[i]) return RE_OBS_UNKNOWN;
        nonzero|=operation[i];
    }
    if (!nonzero) return RE_OBS_UNKNOWN;
    s.profile=p; s.writes=0; s.failed=0;
    clock.ctx=&s; clock.sample=sample;
    io.ctx=&s; io.owned=owned; io.read32=read32; io.write32=write32; io.read8=read8;
    return re_observe(&io,&clock,p->epoch,p->hz,p->budget,status);
}
