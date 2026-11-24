#include "runtime.h"
#include <assert.h>
#include <stdio.h>

typedef struct { uint32_t tick, step, epoch, hz, samples, fail_at; } source;
static int sample(void *ctx, re_sample *out)
{
    source *s = ctx;
    ++s->samples;
    if (s->fail_at && s->samples >= s->fail_at) return -1;
    out->ticks = s->tick; out->epoch = s->epoch; out->hz = s->hz;
    s->tick += s->step;
    return 0;
}
static source fresh(void)
{
    source s = {1234, 100, 7, 288000000, 0, 0};
    return s;
}
int main(void)
{
    source s = fresh();
    re_clock c = {&s, sample};
    re_deadline d;
    unsigned i, before;
    assert(re_begin_limited(&c, 7, s.hz, 576000000, 100000, &d) == 0);
    before = s.tick;
    assert(re_wait_minimum(&c, &d, 1440) == 0 && s.tick-before >= 1440);
    /* A whole BCB capture can exceed the observer's 4096 samples without
       resetting either the counter, cumulative deadline or finite poll bound. */
    for (i = 0; i < 5500; ++i) assert(re_wait_minimum(&c, &d, 1440) == 0);
    assert(d.polls > 4096 && d.polls < 100000 && d.start.ticks == 1234);
    s = fresh(); s.step = 0;
    assert(re_begin_limited(&c, 7, s.hz, 100000, 17, &d) == 0);
    assert(re_wait_minimum(&c, &d, 1440) == -1 && d.failed && s.samples == 18);
    before = s.samples;
    assert(re_wait_minimum(&c, &d, 1440) == -1 && s.samples == before);
    s = fresh(); s.tick = 0xffffff00;
    assert(re_begin(&c, 7, s.hz, 100000, &d) == 0);
    assert(re_wait_minimum(&c, &d, 1440) == 0 && d.previous >= 1440);
    s = fresh();
    assert(re_begin(&c, 7, s.hz, 100000, &d) == 0); s.epoch = 8;
    assert(re_wait_minimum(&c, &d, 1440) == -1 && d.failed);
    s = fresh();
    assert(re_begin(&c, 7, s.hz, 100000, &d) == 0); s.hz = 144000000;
    assert(re_wait_minimum(&c, &d, 1440) == -1 && d.failed);
    s = fresh();
    assert(re_begin(&c, 7, s.hz, 1000, &d) == 0);
    assert(re_wait_minimum(&c, &d, 950) == -1 && d.failed);
    s = fresh();
    assert(re_begin(&c, 7, s.hz, 100000, &d) == 0); s.tick = 0;
    assert(re_wait_minimum(&c, &d, 1440) == -1 && d.failed);
    s = fresh(); s.fail_at = 4;
    assert(re_begin(&c, 7, s.hz, 100000, &d) == 0);
    assert(re_wait_minimum(&c, &d, 1440) == -1 && d.failed);
    s = fresh();
    assert(re_begin(&c, 7, s.hz, 100000, &d) == 0);
    assert(re_wait_minimum(&c, &d, 0) == -1 && d.failed);
    assert(re_begin_limited(&c, 7, s.hz, 100000, 0, &d) == -1);
    before = s.samples;
    assert(re_wait_minimum(&c, &d, 1440) == -1 && s.samples == before);
    assert(re_begin_limited(&c, 7, s.hz, 100000, 1000001, &d) == -1);
    puts("ENTRY_TIMING_HOST_PASS scenarios=12 pauses=5501");
    return 0;
}
