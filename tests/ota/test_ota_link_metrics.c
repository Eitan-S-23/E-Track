#include "ota_link_metrics.h"
#include <stdio.h>

static unsigned checks, failures;
#define CHECK(x) do { ++checks; if (!(x)) { ++failures; printf("FAIL line=%u\n", (unsigned)__LINE__); } } while (0)

int main(void)
{
    ota_link_metrics_t m;
    unsigned i;
    const uint32_t error[8] = {4u, 3u, 0x2000u, 4096u, (uint32_t)-1, UINT32_MAX, 0u, 0u};
    uint32_t other[8] = {1u, 4u};
    ota_metrics_reset(&m, 1u, 288000000u, 1u, 921600u, 921600u, 10u);
    CHECK(sizeof(m) == 420u && m.ready == 0u && m.active == 1u && m.clock_ok == 1u);
    CHECK(m.initial_durable == UINT32_MAX && m.terminal == UINT32_MAX);
    ota_metrics_add(&m, OTA_METRICS_PAYLOAD_PROGRAM, 2880u, 0u, 4096u, -1);
    CHECK(m.phase[1].calls == 1u && m.phase[1].errors == 1u && m.phase[1].bytes_requested == 4096u);
    CHECK(m.phase[1].cycles_lo == 2880u && m.phase[1].max_cycles == 2880u);
    m.phase[1].cycles_lo = UINT32_MAX - 1u;
    ota_metrics_add(&m, 1u, 3u, 0u, 0u, 0);
    CHECK(m.phase[1].cycles_hi == 1u && m.phase[1].cycles_lo == 1u);
    m.phase[1].calls = UINT32_MAX;
    ota_metrics_add(&m, 1u, 3u, 0u, 0u, 0);
    CHECK(m.phase[1].calls == UINT32_MAX && m.overflow == 1u);
    ota_metrics_first_error(&m, error);
    ota_metrics_first_error(&m, other);
    CHECK(memcmp(m.first_error, error, sizeof(error)) == 0);
    ota_metrics_freeze(&m, 20u);
    CHECK(m.active == 0u && m.ready == 1u && m.terminal == 1u);
    CHECK(m.crc32 == ota_metrics_crc(&m, offsetof(ota_link_metrics_t, crc32)));
    ota_metrics_add(&m, 0u, 20u, 0u, 20u, 0);
    ota_metrics_freeze(&m, 30u);
    CHECK(m.phase[0].calls == 0u && m.end_ms == 20u);
    ota_metrics_reset(&m, 2u, 288000000u, 1u, 921600u, 0u, UINT32_MAX - 5u);
    CHECK(m.overflow == 0u && m.first_error[1] == 0u && m.phase[1].calls == 0u);
    ota_metrics_add(&m, 0u, 1u, 15000u, 1u, 0);
    CHECK(m.clock_ok == 0u);
    ota_metrics_reset(&m, 3u, 0u, 1u, 921600u, 0u, 0u);
    ota_metrics_add(&m, 0u, 1u, 1u, 1u, 0);
    CHECK(m.clock_ok == 0u);
    ota_metrics_reset(&m, 4u, 288000000u, 1u, 921600u, 0u, 10u);
    m.phase[0].cycles_lo = UINT32_MAX;
    m.phase[0].cycles_hi = UINT32_MAX;
    ota_metrics_add(&m, 0u, 1u, 0u, 0u, 0);
    CHECK(m.overflow == 1u && m.phase[0].cycles_lo == UINT32_MAX && m.phase[0].cycles_hi == UINT32_MAX);
    ota_metrics_reset(&m, 5u, 288000000u, 1u, 921600u, 921600u, 10u);
    m.total_len = m.final_durable = 1048576u;
    m.initial_durable = 0u;
    m.protocol = 2u; m.session = 7u; m.epoch = 123u; m.terminal = 0u;
    memset(m.package_sha256, 0xaa, sizeof(m.package_sha256));
    for (i = 0u; i < OTA_METRICS_PHASES; ++i) ota_metrics_add(&m, i, 2880u + i, 0u, 128u, 0);
    m.rx_bytes = 128u;
    ota_metrics_freeze(&m, 20u);
    printf("METRICS_CHECKS=%u failures=%u\nP34_METRICS ", checks, failures);
    for (i = 0u; i < sizeof(m); ++i) printf("%02x", ((const uint8_t *)&m)[i]);
    printf("\n");
    return failures != 0u;
}
