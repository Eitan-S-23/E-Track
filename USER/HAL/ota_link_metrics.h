#ifndef E_TRACK_OTA_LINK_METRICS_H
#define E_TRACK_OTA_LINK_METRICS_H

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define OTA_METRICS_MAGIC 0x50334d31u
#define OTA_METRICS_SCHEMA 1u

enum ota_metrics_phase {
    OTA_METRICS_PAYLOAD_READ, OTA_METRICS_PAYLOAD_PROGRAM,
    OTA_METRICS_PAYLOAD_ERASE, OTA_METRICS_PAYLOAD_VERIFY,
    OTA_METRICS_JOURNAL_READ, OTA_METRICS_JOURNAL_PROGRAM,
    OTA_METRICS_JOURNAL_ERASE, OTA_METRICS_JOURNAL_VERIFY,
    OTA_METRICS_UART_RX_IRQ, OTA_METRICS_ACK_TX,
    OTA_METRICS_PHASES
};

typedef struct ota_metrics_phase_t {
    uint32_t calls, errors, bytes_requested, cycles_lo, cycles_hi, max_cycles;
} ota_metrics_phase_t;

/* Fixed little-endian u32 ABI. UART counters are copied with IRQs masked at
 * freeze. Only the UART hook writes RX fields. No control or wire state lives here. */
typedef struct ota_link_metrics_t {
    uint32_t magic, schema, size;
    volatile uint32_t ready, active;
    uint32_t run, clock_hz, clock_ok, overflow;
    uint32_t uart_baud_actual, retained_baud, total_len, terminal;
    uint32_t protocol, session, epoch, initial_durable, final_durable;
    uint32_t start_ms, end_ms;
    uint32_t rx_bytes, rx_ring_peak, overlay_dropped, hw_dropped;
    uint32_t uart_errors, uart_error_flags, parser_bad_frames, package_crc32;
    uint8_t package_sha256[32];
    uint32_t first_error[8];
    ota_metrics_phase_t phase[OTA_METRICS_PHASES];
    uint32_t crc32;
} ota_link_metrics_t;

typedef char ota_metrics_layout[(sizeof(ota_link_metrics_t) == 420u) ? 1 : -1];

static inline uint32_t ota_metrics_crc(const void *data, size_t len)
{
    const uint8_t *p = (const uint8_t *)data;
    uint32_t crc = UINT32_MAX;
    size_t i;
    unsigned bit;
    for (i = 0; i < len; ++i) {
        crc ^= p[i];
        for (bit = 0; bit < 8u; ++bit)
            crc = (crc >> 1) ^ ((crc & 1u) ? 0xedb88320u : 0u);
    }
    return crc ^ UINT32_MAX;
}

static inline void ota_metrics_sum(ota_link_metrics_t *m, uint32_t *value, uint32_t n)
{
    if (n > UINT32_MAX - *value) {
        *value = UINT32_MAX;
        m->overflow = 1u;
    } else *value += n;
}

static inline void ota_metrics_reset(ota_link_metrics_t *m, uint32_t run,
    uint32_t hz, uint32_t clock_ok, uint32_t baud, uint32_t retained, uint32_t ms)
{
    memset(m, 0, sizeof(*m));
    m->magic = OTA_METRICS_MAGIC;
    m->schema = OTA_METRICS_SCHEMA;
    m->size = sizeof(*m);
    m->run = run;
    m->clock_hz = hz;
    m->clock_ok = clock_ok && hz >= 1000u ? 1u : 0u;
    m->uart_baud_actual = baud;
    m->retained_baud = retained;
    m->initial_durable = UINT32_MAX;
    m->terminal = UINT32_MAX;
    m->start_ms = ms;
    m->active = 1u;
}

static inline void ota_metrics_add(ota_link_metrics_t *m, unsigned phase,
    uint32_t cycles, uint32_t elapsed_ms, uint32_t bytes, int result)
{
    ota_metrics_phase_t *p;
    uint32_t before;
    if (!m->active || phase >= OTA_METRICS_PHASES) return;
    if (m->clock_hz < 1000u || elapsed_ms >= UINT32_MAX / (m->clock_hz / 1000u))
        m->clock_ok = 0u; /* Reject a possibly aliased full DWT wrap. */
    p = &m->phase[phase];
    ota_metrics_sum(m, &p->calls, 1u);
    ota_metrics_sum(m, &p->errors, result != 0 ? 1u : 0u);
    ota_metrics_sum(m, &p->bytes_requested, bytes);
    before = p->cycles_lo;
    p->cycles_lo += cycles;
    if (p->cycles_lo < before) {
        if (p->cycles_hi == UINT32_MAX) {
            p->cycles_lo = UINT32_MAX;
            m->overflow = 1u;
        } else ++p->cycles_hi;
    }
    if (cycles > p->max_cycles) p->max_cycles = cycles;
}

static inline void ota_metrics_first_error(ota_link_metrics_t *m, const uint32_t error[8])
{
    if (m->active && m->first_error[1] == 0u && error[1] != 0u)
        memcpy(m->first_error, error, sizeof(m->first_error));
}

static inline void ota_metrics_freeze(ota_link_metrics_t *m, uint32_t ms)
{
    if (!m->active) return;
    m->end_ms = ms;
    m->active = 0u;
    if (m->terminal != 0u) m->terminal = 1u;
    m->ready = 1u;
    m->crc32 = ota_metrics_crc(m, offsetof(ota_link_metrics_t, crc32));
}

#endif
