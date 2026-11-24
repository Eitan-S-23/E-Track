#include "bcb_target.h"

typedef struct { const re_profile *profile; int failed, entered; } target_owner;

static int tgt_qualified(target_owner *s, re_hw_snapshot *h)
{
    if (s->failed || re_platform_snapshot(h) != 0 || !re_snapshot_matches(s->profile, h) ||
        !re_bcb_pin_config_ok(!s->entered)) {
        s->failed = 1;
        return 0;
    }
    s->entered = 1;
    return 1;
}
static int tgt_sample(void *ctx, re_sample *out)
{
    target_owner *s = ctx;
    re_hw_snapshot h;
    if (!tgt_qualified(s, &h)) return -1;
    out->ticks = h.ticks; out->hz = s->profile->hz; out->epoch = s->profile->epoch;
    return 0;
}
static int tgt_owned(void *ctx)
{
    re_hw_snapshot h;
    return tgt_qualified(ctx, &h);
}
static void tgt_sda(void *ctx, int high)
{
    target_owner *s = ctx;
    if (!tgt_owned(s) || re_bcb_pin_set(7, high) != 0) s->failed = 1;
}
static void tgt_scl(void *ctx, int high)
{
    target_owner *s = ctx;
    if (!tgt_owned(s) || re_bcb_pin_set(6, high) != 0) s->failed = 1;
}
static int tgt_read_sda(void *ctx)
{
    target_owner *s = ctx;
    int value;
    if (!tgt_owned(s)) return 0;
    value = re_bcb_pin_read(7);
    if (value < 0) { s->failed = 1; return 0; }
    return value;
}
static int tgt_read_scl(void *ctx)
{
    target_owner *s = ctx;
    int value;
    if (!tgt_owned(s)) return 0;
    value = re_bcb_pin_read(6);
    if (value < 0) { s->failed = 1; return 0; }
    return value;
}

int re_capture_target_once(re_session *session, const re_profile *p, rr_bcb_observation *out)
{
    target_owner owner = {p, 0, 0};
    re_clock clock = {&owner, tgt_sample};
    re_capture_pins pins = {&owner, tgt_owned, tgt_sda, tgt_scl, tgt_read_sda, tgt_read_scl};
    return re_capture_once(session, p, &clock, &pins, out);
}
