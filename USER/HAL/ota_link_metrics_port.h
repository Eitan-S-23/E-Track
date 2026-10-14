#ifndef E_TRACK_OTA_LINK_METRICS_PORT_H
#define E_TRACK_OTA_LINK_METRICS_PORT_H

#include "ota_link_metrics.h"

extern "C" {
ota_link_metrics_t g_ota_link_metrics;
volatile uint32_t g_ota_metrics_publish_bytes;
}
static ota_staging_io_t s_metrics_io;
static uint32_t s_metrics_bad_start;

static uint32_t metrics_actual_baud(void)
{
    crm_clocks_freq_type cf;
    usart_type *u = BT_SERIAL.getUSART();
    uint32_t div = (uint32_t)u->baudr_bit.div;
    if (div == 0u) return 0u;
    crm_clocks_freq_get(&cf);
    return (u == USART1 || u == USART6 ? cf.apb2_freq : cf.apb1_freq) / div;
}

static void metrics_add(unsigned phase, uint32_t start, uint32_t ms,
                        uint32_t bytes, int result)
{
    if (SystemCoreClock != g_ota_link_metrics.clock_hz) g_ota_link_metrics.clock_ok = 0u;
    ota_metrics_add(&g_ota_link_metrics, phase, p34_clock() - start,
                    millis() - ms, bytes, result);
}

static unsigned metrics_phase(uint32_t address, unsigned payload)
{
    return payload + (address < OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET ? 4u : 0u);
}

static int metrics_read(void *ctx, uint32_t address, uint8_t *dst, uint32_t len)
{
    uint32_t start = p34_clock(), ms = millis();
    int result = s_metrics_io.read(ctx, address, dst, len);
    metrics_add(metrics_phase(address, OTA_METRICS_PAYLOAD_READ), start, ms, len, result);
    return result;
}

static int metrics_program(void *ctx, uint32_t address, const uint8_t *src, uint32_t len)
{
    uint32_t start = p34_clock(), ms = millis();
    int result = s_metrics_io.program(ctx, address, src, len);
    metrics_add(metrics_phase(address, OTA_METRICS_PAYLOAD_PROGRAM), start, ms, len, result);
    return result;
}

static int metrics_erase(void *ctx, uint32_t address)
{
    uint32_t start = p34_clock(), ms = millis();
    int result = s_metrics_io.erase_4k(ctx, address);
    metrics_add(metrics_phase(address, OTA_METRICS_PAYLOAD_ERASE), start, ms, 4096u, result);
    return result;
}

static ota_staging_result_t metrics_verify(void *ctx, uint32_t address,
                                           const uint8_t *expected, uint32_t len)
{
    uint32_t start = p34_clock(), ms = millis();
    ota_staging_result_t result = s_metrics_io.verify(ctx, address, expected, len);
    metrics_add(metrics_phase(address, OTA_METRICS_PAYLOAD_VERIFY), start, ms, len, (int)result);
    return result;
}

static void metrics_bind(void)
{
    s_metrics_io = s_ble_staging_io;
    s_ble_staging_io.read = metrics_read;
    s_ble_staging_io.program = metrics_program;
    s_ble_staging_io.erase_4k = metrics_erase;
    if (s_metrics_io.verify != NULL) s_ble_staging_io.verify = metrics_verify;
}

static void metrics_begin(void)
{
    uint32_t primask = __get_PRIMASK();
    uint32_t run = g_ota_link_metrics.run + 1u;
    __disable_irq();
    BT_SERIAL.resetRxDiagnostics();
    HAL::OTA_StagingResetFirstError();
    ota_metrics_reset(&g_ota_link_metrics, run, SystemCoreClock, s_p34_clock_ok,
        metrics_actual_baud(), p34_baud_from_word(ertc_bpr_data_read(ERTC_DT20)), millis());
    if (run == 0u) g_ota_link_metrics.overflow = 1u;
    s_metrics_bad_start = s_ble_session.demux.parser.bad_frames;
    g_ota_metrics_publish_bytes = 0u;
    __set_PRIMASK(primask);
}

static void metrics_finish(void)
{
    if (!g_ota_link_metrics.active) return;
    uint32_t primask = __get_PRIMASK();
    __disable_irq();
    g_ota_link_metrics.total_len = s_ble_session.total_len;
    g_ota_link_metrics.final_durable = s_ble_session.progress.durable_off;
    memcpy(g_ota_link_metrics.package_sha256, s_ble_session.package_sha256, 32u);
    g_ota_link_metrics.package_crc32 = boot_crc32_final(&s_ble_session.pkg_crc);
    g_ota_link_metrics.hw_dropped = BT_SERIAL.rxBufferDropped();
    g_ota_link_metrics.uart_errors = BT_SERIAL.rxErrorEvents();
    g_ota_link_metrics.uart_error_flags = BT_SERIAL.rxErrorFlags();
    ota_metrics_phase_t *rx = &g_ota_link_metrics.phase[OTA_METRICS_UART_RX_IRQ];
    rx->calls = BT_SERIAL.rxIrqCalls();
    rx->errors = g_ota_link_metrics.uart_errors;
    rx->bytes_requested = g_ota_link_metrics.rx_bytes;
    rx->cycles_lo = BT_SERIAL.rxIrqCyclesLo();
    rx->cycles_hi = BT_SERIAL.rxIrqCyclesHi();
    rx->max_cycles = BT_SERIAL.rxIrqMax();
    if (BT_SERIAL.rxTimingOverflow() || rx->errors == UINT32_MAX ||
        g_ota_link_metrics.hw_dropped == UINT32_MAX) g_ota_link_metrics.overflow = 1u;
    g_ota_link_metrics.parser_bad_frames = s_ble_session.demux.parser.bad_frames - s_metrics_bad_start;
    HAL::OtaStagingError error;
    if (HAL::OTA_StagingGetFirstError(&error)) {
        const uint32_t words[8] = {error.operation, error.phase, error.address, error.length,
            (uint32_t)error.result, error.mismatch_address, error.expected_byte, error.observed_byte};
        ota_metrics_first_error(&g_ota_link_metrics, words);
    }
    ota_metrics_freeze(&g_ota_link_metrics, millis());
    __DMB();
    __set_PRIMASK(primask);

    /* One nonblocking record before activation/reboot. It fits the existing
     * 1024-byte RTT ring; loss is explicit, never inferred as zero cost. */
    char line[sizeof(g_ota_link_metrics) * 2u + 14u];
    const char hex[] = "0123456789abcdef";
    const uint8_t *bytes = (const uint8_t *)&g_ota_link_metrics;
    const unsigned prefix = sizeof("P34_METRICS ") - 1u;
    memcpy(line, "P34_METRICS ", prefix);
    for (unsigned i = 0u; i < sizeof(g_ota_link_metrics); ++i) {
        line[prefix + i * 2u] = hex[bytes[i] >> 4];
        line[prefix + i * 2u + 1u] = hex[bytes[i] & 15u];
    }
    line[prefix + sizeof(g_ota_link_metrics) * 2u] = '\n';
    g_ota_metrics_publish_bytes = SEGGER_RTT_Write(0, line, prefix + sizeof(g_ota_link_metrics) * 2u + 1u);
}

#endif
