#include "ota_link_metrics.h"
#include "OTA/ota_ble_session.h"
#include <stdio.h>

static unsigned checks, failures;
#define CHECK(x) do { ++checks; if (!(x)) { ++failures; printf("FAIL line=%u\n", (unsigned)__LINE__); } } while (0)

static void print_metrics(const ota_link_metrics_t *m)
{
    unsigned i;
    printf("METRICS_CHECKS=%u failures=%u\nP34_METRICS ", checks, failures);
    for (i = 0u; i < sizeof(*m); ++i) printf("%02x", ((const uint8_t *)m)[i]);
    printf("\n");
}

static int test_core(void)
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
    print_metrics(&m);
    return failures != 0u;
}

/* Real session/staging/crypto, in-memory NOR and synthetic timing only.
 * Callback selection is the regression; these cycles are not MCU measurements. */
static ota_link_metrics_t path_metrics;
static ota_ble_session_t session;
static uint8_t storage[OTA_STAGING_PAYLOAD_OFFSET + 8192u];
static union { uint64_t alignment; uint8_t bytes[40960]; } workspace;
static unsigned activated;
static uint8_t last_ack, last_status;

static int in_range(uint32_t address, uint32_t len)
{
    return address >= OTA_EXT_STAGING && len <= sizeof(storage) &&
        address - OTA_EXT_STAGING <= sizeof(storage) - len;
}

static void add_io(unsigned phase, uint32_t address, uint32_t len, int result)
{
    if (address < OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET) phase += 4u;
    ota_metrics_add(&path_metrics, phase, 2880u, 0u, len, result);
}

static int read_memory(void *ctx, uint32_t address, uint8_t *dst, uint32_t len)
{
    (void)ctx;
    if (!in_range(address, len)) return -1;
    memcpy(dst, storage + address - OTA_EXT_STAGING, len);
    add_io(OTA_METRICS_PAYLOAD_READ, address, len, 0);
    return 0;
}

static int erase_memory(void *ctx, uint32_t address)
{
    (void)ctx;
    if (!in_range(address, 4096u) || (address & 4095u)) return -1;
    memset(storage + address - OTA_EXT_STAGING, 0xff, 4096u);
    add_io(OTA_METRICS_PAYLOAD_ERASE, address, 4096u, 0);
    return 0;
}

static int program_memory(void *ctx, uint32_t address, const uint8_t *src, uint32_t len)
{
    uint32_t i;
    uint8_t *dst;
    (void)ctx;
    if (!in_range(address, len)) return -1;
    dst = storage + address - OTA_EXT_STAGING;
    for (i = 0u; i < len; ++i) if ((dst[i] & src[i]) != src[i]) return -1;
    for (i = 0u; i < len; ++i) dst[i] &= src[i];
    add_io(OTA_METRICS_PAYLOAD_PROGRAM, address, len, 0);
    return 0;
}

static ota_staging_result_t verify_memory(void *ctx, uint32_t address,
                                         const uint8_t *expected, uint32_t len)
{
    ota_staging_result_t result;
    (void)ctx;
    if (!in_range(address, len)) return OTA_STAGING_ERR_IO;
    result = memcmp(storage + address - OTA_EXT_STAGING, expected, len) == 0
        ? OTA_STAGING_OK : OTA_STAGING_ERR_VERIFY;
    add_io(OTA_METRICS_PAYLOAD_VERIFY, address, len, result);
    return result;
}

static int yes(void) { return 1; }
static int no(void) { return 0; }
static void release_workspace(void) { }
static uint32_t now_ms(void) { return 10u; }
static uint8_t *get_workspace(uint32_t *size)
{
    *size = sizeof(workspace.bytes);
    return workspace.bytes;
}

static int get_device(ota_sd_device_t *device)
{
    memset(device, 0, sizeof(*device));
    device->current_vcode = 20700u;
    device->hardware_rev = device->layout_id = device->boot_version = 1u;
    return 1;
}

static int send_ack(const uint8_t *frame, uint16_t len)
{
    CHECK(len >= OTA_BLE_HEADER_SIZE + 1u + OTA_BLE_CRC_SIZE);
    last_ack = frame[2];
    last_status = frame[OTA_BLE_HEADER_SIZE];
    ota_metrics_add(&path_metrics, OTA_METRICS_ACK_TX, 2880u, 0u, len, 0);
    return 0;
}

static int activate(uint32_t version, uint32_t len, ota_sd_kind_t kind)
{
    CHECK(version == 20800u && len == 8192u && kind == OTA_SD_KIND_FULL);
    ++activated;
    return 0; /* No device reset or installation exists in this host fixture. */
}

static void put_u32(uint8_t *dst, uint32_t n)
{
    unsigned i;
    for (i = 0u; i < 4u; ++i) dst[i] = (uint8_t)(n >> (8u * i));
}

static void feed(uint8_t cmd, uint16_t seq, const uint8_t *payload, uint16_t len)
{
    uint8_t wire[OTA_BLE_MAX_FRAME];
    size_t i, size = ota_ble_frame_encode(wire, sizeof(wire), cmd, session.session_id, seq, payload, len);
    CHECK(size > 0u);
    path_metrics.rx_bytes += (uint32_t)size;
    ota_metrics_add(&path_metrics, OTA_METRICS_UART_RX_IRQ, 2880u, 0u, (uint32_t)size, 0);
    for (i = 0u; i < size; ++i) {
        if (ota_ble_session_isr_active(&session)) ota_ble_session_isr_feed(&session, wire[i]);
        else ota_ble_session_feed_idle(&session, NULL, NULL, wire[i]);
    }
    ota_ble_session_pump(&session);
    CHECK(last_status == OTA_BLE_STATUS_OK);
}

static int test_zero_verify(void)
{
    uint8_t package[8192] = {0}, sha[32], payload[OTA_BLE_MAX_PAYLOAD];
    uint32_t offset;
    uint16_t seq = 1u;
    boot_sha256_ctx_t digest;
    ota_staging_io_t io;
    ota_ble_env_t env;
    memset(&io, 0, sizeof(io));
    io.read = read_memory; io.program = program_memory;
    io.erase_4k = erase_memory; io.verify = verify_memory;
    memset(&env, 0, sizeof(env));
    env.now_ms = now_ms; env.send = send_ack; env.bcb_confirmed = yes;
    env.ota_disabled = no; env.overlay_acquire = yes;
    env.overlay_release = release_workspace; env.overlay_workspace = get_workspace;
    env.get_device = get_device; env.activate_staged = activate; env.staging_io = &io;
    memset(storage, 0xff, sizeof(storage));
    ota_ble_session_init(&session, &env);
    ota_metrics_reset(&path_metrics, 1u, 288000000u, 1u, 921600u, 921600u, 10u);

    /* Same legal ETU header construction as the existing P3-1 session fixture. */
    memcpy(package, "ETU1", 4u);
    package[4] = OTA_SD_HEADER_SIZE;
    package[6] = (uint8_t)OTA_SD_FULL_FLAGS;
    package[7] = (uint8_t)(OTA_SD_FULL_FLAGS >> 8);
    put_u32(package + 8u, 1u); put_u32(package + 12u, 1u);
    put_u32(package + 32u, sizeof(package) - OTA_SD_HEADER_SIZE);
    put_u32(package + 40u, 20800u);
    package[48] = package[50] = package[51] = 1u;
    for (offset = OTA_SD_HEADER_SIZE; offset < sizeof(package); ++offset)
        package[offset] = (uint8_t)(offset * 29u + 7u);
    put_u32(package + 36u, boot_crc32(package + OTA_SD_HEADER_SIZE, sizeof(package) - OTA_SD_HEADER_SIZE));
    put_u32(package + 60u, boot_crc32(package, 60u));
    boot_sha256_init(&digest);
    boot_sha256_update(&digest, package, sizeof(package));
    boot_sha256_final(&digest, sha);

    payload[0] = 1u;
    put_u32(payload + 1u, sizeof(package));
    memcpy(payload + 5u, sha, 32u); memcpy(payload + 37u, package, 64u);
    feed(OTA_BLE_CMD_BEGIN, seq++, payload, OTA_BLE_LEN_BEGIN);
    CHECK(last_ack == OTA_BLE_CMD_ACK_BEGIN && ota_ble_session_active(&session));
    CHECK(session.progress.durable_off == 0u);
    path_metrics.initial_durable = session.progress.durable_off;
    path_metrics.protocol = 1u; path_metrics.session = session.session_id;
    for (offset = 0u; offset < sizeof(package); offset += OTA_STAGING_SEGMENT_SIZE) {
        put_u32(payload, offset);
        memcpy(payload + 4u, package + offset, OTA_STAGING_SEGMENT_SIZE);
        feed(OTA_BLE_CMD_DATA, seq++, payload, 4u + OTA_STAGING_SEGMENT_SIZE);
    }
    feed(OTA_BLE_CMD_END, seq, sha, OTA_BLE_LEN_END);
    CHECK(last_ack == OTA_BLE_CMD_ACK_END && !ota_ble_session_active(&session) && activated == 1u);
    CHECK(session.progress.durable_off == sizeof(package));
    CHECK(boot_crc32_final(&session.pkg_crc) == boot_crc32(package, sizeof(package)));
    CHECK(memcmp(storage + OTA_STAGING_PAYLOAD_OFFSET, package, sizeof(package)) == 0);
    CHECK(memcmp(storage, "ETSL", 4u) == 0);
    CHECK(path_metrics.phase[OTA_METRICS_PAYLOAD_READ].calls == 0u);
    for (offset = OTA_METRICS_PAYLOAD_PROGRAM; offset <= OTA_METRICS_PAYLOAD_VERIFY; ++offset) {
        CHECK(path_metrics.phase[offset].calls == 2u);
        CHECK(path_metrics.phase[offset].bytes_requested == sizeof(package));
    }
    path_metrics.total_len = session.total_len;
    path_metrics.final_durable = session.progress.durable_off;
    path_metrics.package_crc32 = boot_crc32_final(&session.pkg_crc);
    memcpy(path_metrics.package_sha256, session.package_sha256, 32u);
    path_metrics.terminal = last_ack == OTA_BLE_CMD_ACK_END && last_status == OTA_BLE_STATUS_OK ? 0u : 1u;
    ota_metrics_freeze(&path_metrics, 20u);
    print_metrics(&path_metrics);
    return failures != 0u;
}

int main(int argc, char **argv)
{
    if (argc == 2 && strcmp(argv[1], "zero-verify") == 0) return test_zero_verify();
    return argc == 1 ? test_core() : 2;
}
