#include "bcb_reader.h"
#include <string.h>

static int scl(const rr_bcb_bus *b, int high)
{
    unsigned limit;
    b->scl(b->ctx, high);
    for (limit = 0; limit < 8192u; ++limit) {
        if (b->pause(b->ctx) != 0) return -1;
        if (!high || b->read_scl(b->ctx)) return 0;
    }
    return -1;
}

static int start(const rr_bcb_bus *b)
{
    b->sda(b->ctx, 1);
    if (b->pause(b->ctx) != 0 || scl(b, 1) != 0) return -1;
    b->sda(b->ctx, 0);
    if (b->pause(b->ctx) != 0) return -1;
    return scl(b, 0);
}

static int stop(const rr_bcb_bus *b)
{
    int result;
    b->sda(b->ctx, 0);
    result = b->pause(b->ctx);
    if (result == 0) result = scl(b, 1);
    /* On timeout, release both lines and retain failure, not fake a STOP. */
    b->scl(b->ctx, 1);
    b->sda(b->ctx, 1);
    if (result == 0) result = b->pause(b->ctx);
    return result;
}

static int send(const rr_bcb_bus *b, uint8_t value)
{
    unsigned i;
    int acknowledged;
    for (i = 0; i < 8u; ++i) {
        b->sda(b->ctx, (value & 0x80u) != 0);
        if (b->pause(b->ctx) != 0 || scl(b, 1) != 0 || scl(b, 0) != 0) return -1;
        value <<= 1;
    }
    b->sda(b->ctx, 1);
    if (b->pause(b->ctx) != 0 || scl(b, 1) != 0) return -1;
    acknowledged = !b->read_sda(b->ctx);
    if (scl(b, 0) != 0) return -1;
    return acknowledged ? 0 : -1;
}

static int receive(const rr_bcb_bus *b, uint8_t *value, int ack)
{
    uint8_t data = 0;
    unsigned i;
    b->sda(b->ctx, 1);
    if (b->pause(b->ctx) != 0) return -1;
    for (i = 0; i < 8u; ++i) {
        if (scl(b, 1) != 0) return -1;
        data = (uint8_t)((data << 1) | (b->read_sda(b->ctx) ? 1u : 0u));
        if (scl(b, 0) != 0) return -1;
    }
    b->sda(b->ctx, !ack);
    if (b->pause(b->ctx) != 0 || scl(b, 1) != 0 || scl(b, 0) != 0) return -1;
    b->sda(b->ctx, 1);
    *value = data;
    return 0;
}

static int read_block(const rr_bcb_bus *b, unsigned slot, uint8_t *dst)
{
    unsigned i;
    if (slot > 1u) return -1;
    /* Random read sends only device address and pointer before repeated START.
     * No data byte is transmitted to EEPROM after the pointer. */
    if (start(b) != 0 || send(b, 0xa0u) != 0 || send(b, slot ? 0x40u : 0u) != 0 ||
        start(b) != 0 || send(b, 0xa1u) != 0) {
        (void)stop(b); return -1;
    }
    for (i = 0; i < BCB_SIZE; ++i)
        if (receive(b, dst+i, i+1u < BCB_SIZE) != 0) {
            (void)stop(b); return -1;
        }
    return stop(b);
}

/* The original HAL has no context pointer. Capture is intentionally serialized
 * and non-reentrant; this pointer is used only for in-memory arbitration. */
static const rr_bcb_observation *snapshot;

static int snapshot_read(uint8_t reg, uint8_t *dst, uint16_t len)
{
    if (!snapshot || len != BCB_SIZE || (reg != BCB_A_ADDR && reg != BCB_B_ADDR)) return -1;
    memcpy(dst, snapshot->raw[0][reg == BCB_B_ADDR], len);
    return 0;
}

int rr_bcb_capture(const rr_bcb_bus *bus, rr_bcb_observation *out)
{
    unsigned pass, slot;
    bcb_hal_t hal;
    if (!bus || !out || !bus->sda || !bus->scl || !bus->read_sda || !bus->read_scl || !bus->pause)
        return -1;
    memset(out, 0, sizeof(*out));
    out->active = BCB_ARBITER_ERROR;
    for (pass = 0; pass < 2u; ++pass)
        for (slot = 0; slot < 2u; ++slot) {
            if (read_block(bus, slot, out->raw[pass][slot]) != 0) return -1;
            ++out->completed;
        }
    if (memcmp(out->raw[0], out->raw[1], sizeof(out->raw[0])) != 0) return -2;
    out->stable = 1;
    snapshot = out;
    hal.read_buffer = snapshot_read;
    hal.write_buffer = 0;
    out->active = bcb_arbiter(&hal, &out->value);
    snapshot = 0;
    return out->active == BCB_ARBITER_ERROR ? -1 : 0;
}
