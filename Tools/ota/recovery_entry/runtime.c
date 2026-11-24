#include "runtime.h"

int re_begin(const re_clock *clock, uint32_t epoch, uint32_t hz,
             uint32_t budget, re_deadline *d)
{
    return re_begin_limited(clock, epoch, hz, budget, 4096u, d);
}

int re_begin_limited(const re_clock *clock, uint32_t epoch, uint32_t hz,
                     uint32_t budget, uint32_t poll_limit, re_deadline *d)
{
    if (!d) return -1;
    d->failed = 1;
    if (!clock || !clock->sample || !epoch || !hz || !budget || !poll_limit ||
        poll_limit > 1000000u ||
        budget > 0x7fffffffu || clock->sample(clock->ctx, &d->start) != 0 ||
        d->start.epoch != epoch || d->start.hz != hz) return -1;
    d->budget = budget; d->previous = 0; d->polls = 0;
    d->poll_limit = poll_limit; d->failed = 0;
    return 0;
}

int re_alive(const re_clock *clock, re_deadline *d)
{
    re_sample now;
    uint32_t elapsed;
    if (!d || d->failed) return 0;
    if (!clock || !clock->sample || ++d->polls > d->poll_limit ||
        clock->sample(clock->ctx, &now) != 0 || now.epoch != d->start.epoch ||
        now.hz != d->start.hz) goto fail;
    elapsed = now.ticks - d->start.ticks;
    if (elapsed < d->previous || elapsed >= d->budget) goto fail;
    d->previous = elapsed;
    return 1;
fail:
    d->failed = 1;
    return 0;
}

int re_wait_minimum(const re_clock *clock, re_deadline *d, uint32_t ticks)
{
    uint32_t begun;
    if (!d || d->failed) return -1;
    if (!ticks || ticks >= d->budget) { d->failed = 1; return -1; }
    if (!re_alive(clock, d)) return -1;
    begun = d->previous;
    do {
        if (!re_alive(clock, d)) return -1;
    } while (d->previous - begun < ticks);
    return 0;
}

re_observation re_observe(const re_status_io *io, const re_clock *clock,
                          uint32_t epoch, uint32_t hz, uint32_t budget,
                          uint8_t *raw_status)
{
    re_deadline d;
    uint32_t ctrl, fifo, done, i;
    uint8_t status;
    /* QSPI command registers only: address=0, one opcode byte, one RX byte,
       opcode=05 / mode111. No W1C, reset, XIP or writer-state operation. */
    static const uint32_t values[4] = {0u, 0x01000000u, 1u, 0x05000000u};
    if (!io || !io->owned || !io->read32 || !io->write32 || !io->read8 ||
        !raw_status || io->owned(io->ctx) != 1 ||
        re_begin(clock, epoch, hz, budget, &d) != 0) return RE_OBS_UNKNOWN;
    if (io->read32(io->ctx, 0x10u, &ctrl) != 0 ||
        io->read32(io->ctx, 0x18u, &fifo) != 0 ||
        io->read32(io->ctx, 0x24u, &done) != 0) return RE_OBS_UNKNOWN;
    /* This strict initial profile rejects stale completion/RX data. These
       registers alone do not prove absence of an in-flight command or DMA. */
    if ((ctrl & ~0x80u) != 3u || fifo != 4u || done != 0u) return RE_OBS_UNKNOWN;
    for (i = 0; i < 4; ++i) {
        if (!re_alive(clock, &d) || io->owned(io->ctx) != 1 ||
            io->write32(io->ctx, i * 4u, values[i]) != 0) return RE_OBS_UNKNOWN;
    }
    while (re_alive(clock, &d)) {
        if (io->owned(io->ctx) != 1 || io->read32(io->ctx, 0x24u, &done) != 0 ||
            io->read32(io->ctx, 0x18u, &fifo) != 0) return RE_OBS_UNKNOWN;
        if ((done & 1u) && (fifo & 2u)) {
            if (io->read8(io->ctx, 0x100u, &status) != 0 ||
                !re_alive(clock, &d) || io->owned(io->ctx) != 1) return RE_OBS_UNKNOWN;
            *raw_status = status;
            return (status & 1u) ? RE_OBS_BUSY : RE_OBS_IDLE_STATUS_ONLY;
        }
    }
    return RE_OBS_UNKNOWN;
}
