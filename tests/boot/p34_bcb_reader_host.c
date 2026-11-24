#include "bcb_reader.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static int bits[2060], edges[4096];
static unsigned cursor, edge_count, pauses, expire;
static int sda_high, scl_high, stuck;

static void sda(void *ctx, int high) { (void)ctx; sda_high = high; }
static void scl(void *ctx, int high)
{
    (void)ctx;
    if (high && !scl_high) {
        assert(edge_count < 4096u);
        edges[edge_count++] = sda_high;
    }
    scl_high = high;
}
static int read_sda(void *ctx) { (void)ctx; assert(cursor < 2060u); return bits[cursor++]; }
static int read_scl(void *ctx) { (void)ctx; return !stuck; }
static int pause_bus(void *ctx) { (void)ctx; return ++pauses >= expire ? -1 : 0; }

static void prepare(uint16_t aseq, uint16_t bseq, int change)
{
    unsigned pass, slot, i, bit, p = 0;
    bcb_t record;
    uint8_t raw[64];
    cursor = edge_count = pauses = 0; expire = 1000000u;
    sda_high = scl_high = 1; stuck = 0;
    for (pass = 0; pass < 2u; ++pass)
        for (slot = 0; slot < 2u; ++slot) {
            bcb_make_idle(&record, 30275u);
            record.state = BCB_STATE_CONFIRMED;
            record.seq = slot ? bseq : aseq;
            if (change && pass == 1u && slot == 0u) ++record.seq;
            bcb_serialize(&record, raw);
            bits[p++] = 0; bits[p++] = 0; bits[p++] = 0;
            for (i = 0; i < 64u; ++i)
                for (bit = 0; bit < 8u; ++bit) bits[p++] = (raw[i] >> (7u-bit)) & 1u;
        }
    assert(p == 2060u);
}

static unsigned byte_at(unsigned start)
{
    unsigned i, value = 0;
    for (i = 0; i < 8u; ++i) value = (value << 1) | (unsigned)edges[start+i];
    return value;
}

int main(void)
{
    rr_bcb_bus bus = {NULL, sda, scl, read_sda, read_scl, pause_bus};
    rr_bcb_observation out;
    unsigned i, j, normal_pauses, count = 0;
    const uint16_t seq[][2] = {{8,7},{7,8},{9,9},{65535,0},{0,65535}};
    const int active[] = {BCB_ARBITER_A,BCB_ARBITER_B,BCB_ARBITER_A,BCB_ARBITER_B,BCB_ARBITER_A};
    for (i = 0; i < 5u; ++i) {
        prepare(seq[i][0], seq[i][1], 0);
        assert(rr_bcb_capture(&bus, &out) == 0);
        assert(out.stable && out.completed == 4 && (int)out.active == active[i]);
        assert(out.value.cur_vcode == 30275u && cursor == 2060u && edge_count == 2420u);
        for (j = 0; j < 4u; ++j) {
            unsigned k, offset = j*605u;
            assert(byte_at(offset) == 0xa0u);
            assert(byte_at(offset+9u) == ((j & 1u) ? 0x40u : 0u));
            assert(byte_at(offset+19u) == 0xa1u);
            for (k = 0; k < 64u; ++k) assert(edges[offset+28u+k*9u+8u] == (k == 63u));
        }
        ++count;
    }
    normal_pauses = pauses;
    prepare(8,7,1);
    assert(rr_bcb_capture(&bus, &out) == -2 && !out.stable && out.completed == 4);
    ++count;
    for (i = 0; i < 4u; ++i) {
        prepare(8,7,0); bits[i*515u] = 1;
        assert(rr_bcb_capture(&bus, &out) == -1 && !out.stable && out.completed == i);
        assert(sda_high && scl_high); ++count;
    }
    /* Every pause boundary of a successful run is faulted independently. */
    for (i = 1; i <= normal_pauses; ++i) {
        prepare(8,7,0); expire = i;
        assert(rr_bcb_capture(&bus, &out) == -1 && !out.stable);
        assert(sda_high && scl_high);
    }
    count += normal_pauses;
    prepare(8,7,0); stuck = 1;
    assert(rr_bcb_capture(&bus, &out) == -1 && pauses < 17000u && cursor == 0);
    ++count;
    printf("BCB_READER_HOST_PASS checks=%u deadline_boundaries=%u\n", count, normal_pauses);
    return 0;
}
