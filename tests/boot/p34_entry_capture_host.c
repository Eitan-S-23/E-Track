/* Reuse the original wire fixture, not its closed 5499-case test campaign. */
#define main original_reader_campaign_not_run
#include "p34_bcb_reader_host.c"
#undef main
#include "capture.h"

static uint32_t tick, samples, fail_sample, step, mutations;
static int fault_seen, lose_owner;
static int clock_sample(void *ctx, re_sample *out)
{
    (void)ctx;
    ++samples;
    out->ticks = tick; tick += step;
    out->hz = 288000000u;
    out->epoch = samples >= fail_sample ? 4 : 3;
    if (samples >= fail_sample) fault_seen = 1;
    return 0;
}
static int pin_owned(void *ctx) { (void)ctx; return !lose_owner; }
static void pin_sda(void *ctx, int high)
{
    assert(!fault_seen && !lose_owner);
    ++mutations; sda(ctx, high);
}
static void pin_scl(void *ctx, int high)
{
    assert(!fault_seen && !lose_owner);
    ++mutations; scl(ctx, high);
}
static re_profile reset_capture(void)
{
    re_profile p = {0};
    prepare(8, 7, 0);
    tick = 12345; samples = mutations = 0; fail_sample = 0xffffffffu;
    step = 720; fault_seen = lose_owner = 0;
    p.epoch = 3; p.hz = 288000000; p.budget = 576000000;
    p.entry_qualified = p.media_qualified = p.clock_qualified = p.ownership_qualified = 1;
    memset(p.operation, 0x27, sizeof(p.operation));
    return p;
}
int main(void)
{
    re_capture_pins pins = {0, pin_owned, pin_sda, pin_scl, read_sda, read_scl};
    re_clock clock = {0, clock_sample};
    rr_bcb_observation out;
    re_session session;
    re_profile p;
    unsigned kind, before_mutations, before_samples;
    for (kind = 0; kind < 8; ++kind) {
        p = reset_capture(); session.consumed = 0;
        if (kind == 1) fail_sample = 1000;
        if (kind == 2) step = 0;
        if (kind == 3) lose_owner = 1;
        if (kind == 4) p.media_qualified = 0;
        if (kind == 5) tick = 0xfffffe00u;
        if (kind == 6) p.budget = 2000;
        if (kind == 7) prepare(8, 7, 1);
        if (kind == 0 || kind == 5) {
            assert(re_capture_once(&session, &p, &clock, &pins, &out) == 0);
            assert(out.stable && out.completed == 4 && out.value.cur_vcode == 30275);
            assert(cursor == 2060 && edge_count == 2420);
            assert(samples > 4096 && samples < 1000000);
        } else {
            assert(re_capture_once(&session, &p, &clock, &pins, &out) != 0 && !out.stable);
            if (kind == 3 || kind == 4) assert(mutations == 0);
        }
        before_mutations = mutations; before_samples = samples;
        assert(session.consumed == 1);
        assert(re_capture_once(&session, &p, &clock, &pins, &out) == -1);
        assert(mutations == before_mutations && samples == before_samples);
    }
    puts("ENTRY_CAPTURE_HOST_PASS scenarios=8; original campaign not rerun");
    return 0;
}
