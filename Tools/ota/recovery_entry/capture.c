#include "capture.h"

typedef struct {
    const re_clock *clock;
    const re_capture_pins *pins;
    re_deadline deadline;
    int failed;
} capture_owner;

static int cap_owned(capture_owner *s)
{
    if (s->failed || s->pins->owned(s->pins->ctx) != 1 ||
        !re_alive(s->clock, &s->deadline)) {
        s->failed = 1;
        return 0;
    }
    return 1;
}
static void cap_sda(void *ctx, int high)
{
    capture_owner *s = ctx;
    if (cap_owned(s)) s->pins->sda(s->pins->ctx, high);
}
static void cap_scl(void *ctx, int high)
{
    capture_owner *s = ctx;
    if (cap_owned(s)) s->pins->scl(s->pins->ctx, high);
}
static int cap_read_sda(void *ctx)
{
    capture_owner *s = ctx;
    return cap_owned(s) ? s->pins->read_sda(s->pins->ctx) : 0;
}
static int cap_read_scl(void *ctx)
{
    capture_owner *s = ctx;
    return cap_owned(s) ? s->pins->read_scl(s->pins->ctx) : 0;
}
static int cap_pause(void *ctx)
{
    capture_owner *s = ctx;
    if (!cap_owned(s) || re_wait_minimum(s->clock, &s->deadline, 1440u) != 0) {
        s->failed = 1;
        return -1;
    }
    return 0;
}

int re_capture_once(re_session *session, const re_profile *p, const re_clock *clock,
                    const re_capture_pins *pins, rr_bcb_observation *out)
{
    capture_owner s;
    rr_bcb_bus bus;
    int result;
    unsigned i;
    uint8_t operation = 0;
    if (!session || session->consumed) return -1;
    session->consumed = 1;
    if (!out) return -1;
    out->stable = 0; out->completed = 0; out->active = BCB_ARBITER_ERROR;
    if (!p || !pins || !pins->owned || !pins->sda || !pins->scl ||
        !pins->read_sda || !pins->read_scl || p->entry_qualified != 1 ||
        p->media_qualified != 1 || p->clock_qualified != 1 || p->ownership_qualified != 1 ||
        p->hz != 288000000u || !p->budget || p->budget > 576000000u) return -1;
    for (i = 0; i < 32; ++i) operation |= p->operation[i];
    if (!operation) return -1;
    s.clock = clock; s.pins = pins; s.failed = 0;
    if (pins->owned(pins->ctx) != 1 ||
        re_begin_limited(clock, p->epoch, p->hz, p->budget, 1000000u, &s.deadline) != 0) return -1;
    bus.ctx = &s; bus.sda = cap_sda; bus.scl = cap_scl;
    bus.read_sda = cap_read_sda; bus.read_scl = cap_read_scl; bus.pause = cap_pause;
    result = rr_bcb_capture(&bus, out);
    if (!cap_owned(&s)) {
        out->stable = 0; out->active = BCB_ARBITER_ERROR;
        return -1;
    }
    return result;
}
