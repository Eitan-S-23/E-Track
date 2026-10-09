#ifndef E_TRACK_P34_LINK_PROFILE_H
#define E_TRACK_P34_LINK_PROFILE_H

#include <stdint.h>
#include <string.h>

#define P34_PROFILE_MAGIC 0x50334250u
#define P34_PROFILE_SCHEMA 2u
#define P34_BAUD_WORD_MAGIC 0x50340000u

enum p34_profile_phase
{
    P34_PAYLOAD_READ,
    P34_PAYLOAD_PROGRAM,
    P34_PAYLOAD_ERASE,
    P34_JOURNAL_READ,
    P34_JOURNAL_PROGRAM,
    P34_JOURNAL_ERASE,
    P34_ACK_TX_CALL,
    P34_PUMP_WORK,
    P34_PAYLOAD_VERIFY,
    P34_JOURNAL_VERIFY,
    P34_PROFILE_PHASE_COUNT
};

typedef struct p34_phase_t
{
    uint32_t calls;
    uint32_t errors;
    uint32_t bytes_requested;
    uint32_t cycles_lo;
    uint32_t cycles_hi;
    uint32_t max_cycles;
} p34_phase_t;

/* All fields are u32 for identical host/ARM layout. Main owns timing fields;
 * the UART ISR owns RX fields. Publish the frozen copy with IRQs masked. */
typedef struct p34_profile_t
{
    uint32_t magic;
    uint32_t schema;
    uint32_t size;
    uint32_t ready;
    uint32_t run;
    uint32_t clock_hz;
    uint32_t clock_ok;
    volatile uint32_t active;
    uint32_t uart_baud_actual;
    uint32_t retained_baud;
    uint32_t total_len;
    uint32_t terminal; /* 0 = admitted END activation, 1 = incomplete teardown */
    volatile uint32_t rx_session_bytes;
    volatile uint32_t hw_queue_peak;
    volatile uint32_t rx_ring_peak;
    volatile uint32_t overlay_dropped;
    uint32_t hw_buffer_dropped;
    uint32_t uart_error_events;
    uint32_t uart_error_flags;
    uint32_t parser_bad_frames;
    uint32_t pump_entries;
    uint32_t pump_gap_max_cycles;
    uint32_t pump_gap_cycles_lo;
    uint32_t pump_gap_cycles_hi;
    p34_phase_t phase[P34_PROFILE_PHASE_COUNT];
} p34_profile_t;

typedef char p34_profile_layout_check[(sizeof(p34_profile_t) == 336u) ? 1 : -1];

static uint32_t p34_baud_word(uint32_t baud)
{
    uint32_t slot = baud == 115200u ? 5u : baud == 460800u ? 7u : baud == 921600u ? 8u : 0u;
    return slot == 0u ? 0u : P34_BAUD_WORD_MAGIC | ((slot ^ 0xffu) << 8) | slot;
}

static uint32_t p34_baud_from_word(uint32_t word)
{
    uint32_t slot = word & 0xffu;
    uint32_t baud = slot == 5u ? 115200u : slot == 7u ? 460800u : slot == 8u ? 921600u : 0u;
    return baud != 0u && p34_baud_word(baud) == word ? baud : 0u;
}

static void p34_add_cycles(uint32_t *lo, uint32_t *hi, uint32_t cycles)
{
    uint32_t before = *lo;
    *lo += cycles;
    if (*lo < before)
    {
        ++*hi;
    }
}

static void p34_profile_reset(p34_profile_t *value, uint32_t run, uint32_t hz,
                               uint32_t clock_ok, uint32_t actual_baud, uint32_t retained_baud)
{
    memset(value, 0, sizeof(*value));
    value->magic = P34_PROFILE_MAGIC;
    value->schema = P34_PROFILE_SCHEMA;
    value->size = sizeof(*value);
    value->run = run;
    value->clock_hz = hz;
    value->clock_ok = clock_ok;
    value->uart_baud_actual = actual_baud;
    value->retained_baud = retained_baud;
    value->active = 1u;
}

static void p34_profile_add(p34_profile_t *value, unsigned phase, uint32_t cycles,
                            uint32_t elapsed_ms, uint32_t bytes, int result)
{
    p34_phase_t *item;
    if (!value->active || phase >= P34_PROFILE_PHASE_COUNT)
    {
        return;
    }
    /* A single interval cannot span a complete DWT wrap. Never publish an
     * aliased interval as a valid low latency after a long stall. */
    if (value->clock_hz < 1000u || elapsed_ms >= UINT32_MAX / (value->clock_hz / 1000u))
    {
        value->clock_ok = 0u;
    }
    item = &value->phase[phase];
    ++item->calls;
    item->errors += result != 0 ? 1u : 0u;
    item->bytes_requested += bytes;
    p34_add_cycles(&item->cycles_lo, &item->cycles_hi, cycles);
    if (cycles > item->max_cycles)
    {
        item->max_cycles = cycles;
    }
}

static void p34_profile_freeze(p34_profile_t *value, p34_profile_t *frozen,
                               uint32_t total_len, uint32_t terminal)
{
    if (!value->active)
    {
        return;
    }
    value->total_len = total_len;
    value->terminal = terminal;
    value->active = 0u;
    *frozen = *value;
    /* The platform publishes ready=1 only after its memory barrier. */
    frozen->ready = 0u;
}

#endif
