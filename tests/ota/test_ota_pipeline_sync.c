#define main legacy_main
#include "test_ota_ble_session.c"
#undef main
#include "OTA/ota_pipeline_sync.h"

static union { uint64_t align; uint8_t bytes[40960]; } workspace2;
static ota_pipeline_io_t sync_io;
static uint8_t queued[24u * OTA_BLE_MAX_FRAME];
static size_t queued_len;
static unsigned fault, operations, blackout;
static uint32_t ring_peak;

static uint8_t *workspace_get(uint32_t *size)
{
    *size = sizeof(workspace2.bytes);
    return workspace2.bytes;
}

static void deliver(size_t len, int pump)
{
    size_t i;
    for (i = 0u; i < len; ++i)
        if (ota_ble_session_isr_active(&session)) ota_ble_session_isr_feed(&session, wire[i]);
        else ota_ble_session_feed_idle(&session, NULL, NULL, wire[i]);
    if (pump) pump_once();
}

static void during_io(void)
{
    size_t i;
    if (!queued_len) return;
    ++blackout;
    for (i = 0; i < queued_len; ++i) ota_ble_session_isr_feed(&session, queued[i]);
    ring_peak = ota_ble_ring_count(&session.rx_ring);
    queued_len = 0;
    /* Model an erase blackout below the sender timeout, not actual timing. */
    te.now_ms += 300u;
}

static int erase_sync(void *ctx, uint32_t address)
{
    int result = flash_erase(ctx, address);
    if (address >= OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET)
    {
        ++operations;
        during_io();
        if (fault == operations) return -1;
    }
    return result;
}

static int program_sync(void *ctx, uint32_t address, const uint8_t *src, uint32_t len)
{
    int result = flash_program(ctx, address, src, len);
    if (address >= OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET)
    {
        ++operations;
        during_io();
        if (fault == operations) return -1;
    }
    return result;
}

static void setup_sync(void)
{
    make_staging_io();
    staging_io.erase_4k = erase_sync;
    staging_io.program = program_sync;
    begin_case();
    session.env.overlay_workspace = workspace_get;
    check("initialize real synchronous adapter", ota_pipeline_sync_init(&sync_io, &staging_io) == 0);
    session.env.pipeline_io = &sync_io;
    fault = operations = blackout = ring_peak = 0;
    queued_len = 0;
}

static void open_sync(uint32_t epoch, const uint8_t *pkg, uint32_t len, const uint8_t sha[32])
{
    uint8_t payload[105];
    write_u32le(payload, epoch);
    deliver(ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_CAPS2,
        0u, 7u, payload, 4u), 1);
    payload[0] = 2u;
    write_u32le(payload + 1u, len);
    memcpy(payload + 5u, sha, 32u);
    memcpy(payload + 37u, pkg, 64u);
    write_u32le(payload + 101u, epoch);
    deliver(ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_BEGIN2,
        0u, 10u, payload, sizeof(payload)), 1);
    check("negotiated synchronous receiver active", session.pipeline != NULL);
}

static size_t data_sync(const uint8_t *pkg, uint32_t off, uint32_t len)
{
    uint8_t payload[136];
    uint16_t seq = (uint16_t)(session.pipeline_first_seq +
        (off - session.pipeline_resume_off) / 128u);
    write_u32le(payload, session.pipeline_ack.epoch);
    write_u32le(payload + 4u, off);
    memcpy(payload + 8u, pkg + off, len);
    return ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_DATA2,
        session.session_id, seq, payload, (uint16_t)(len + 8u));
}

static void send_sync(const uint8_t *pkg, uint32_t from, uint32_t end)
{
    uint32_t off;
    for (off = from; off < end && session.pipeline != NULL; off += 128u)
        deliver(data_sync(pkg, off, end - off < 128u ? end - off : 128u), 1);
}

static void drain_sync(uint32_t durable)
{
    unsigned budget = 100u;
    while (session.pipeline && session.progress.durable_off < durable && budget-- != 0) pump_once();
    check("bounded synchronous drain", budget != 0);
}

static void finish_sync(const uint8_t sha[32])
{
    uint8_t payload[36];
    tx_view_t v = {0};
    uint16_t seq = (uint16_t)(session.pipeline_first_seq +
        (session.total_len - session.pipeline_resume_off + 127u) / 128u);
    write_u32le(payload, session.pipeline_ack.epoch);
    memcpy(payload + 4u, sha, 32u);
    deliver(ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_END2,
        session.session_id, seq, payload, sizeof(payload)), 1);
    check("synchronous END runs SHA CRC finalize activation", last_tx(&v) &&
        v.cmd == OTA_BLE_CMD_ACK_END2 && tx_status(&v) == 0 && te.activate_calls == 1u && te.reset_calls == 1u);
}

static void transfer_and_faults(void)
{
    uint8_t *pkg = make_full_package(9000u);
    uint8_t sha[32];
    unsigned mode;
    if (!pkg) exit(2);
    sha256_of(pkg, 9000u, sha);
    for (mode = 0; mode <= 6; ++mode)
    {
        uint32_t off, prefix;
        setup_sync();
        open_sync(123u + mode, pkg, 9000u, sha);
        fault = mode;
        send_sync(pkg, 0u, 3968u);
        /* The remaining 24 physical frames fit even while the caller blocks. */
        for (off = 4096u; off < 7168u; off += 128u)
        {
            size_t n = data_sync(pkg, off, 128u);
            memcpy(queued + queued_len, wire, n);
            queued_len += n;
        }
        send_sync(pkg, 3968u, 4096u);
        check("24 v2 frames fit the blackout ring", blackout == 1u && ring_peak == 3504u);
        if (session.pipeline) pump_once();
        if (session.pipeline) send_sync(pkg, 7168u, 9000u);
        drain_sync(9000u);
        if (mode)
        {
            check("uncertain physical result ends session without activation",
                !session.pipeline && te.activate_calls == 0u && te.reset_calls == 0u);
            prefix = ((mode - 1u) / 2u) * 4096u;
            check("failure keeps only earlier committed prefix", session.progress.durable_off == prefix);
            fault = 0;
            open_sync(223u + mode, pkg, 9000u, sha);
            check("new epoch resumes durable only", session.pipeline_ack.accepted_off == prefix);
            send_sync(pkg, prefix, 9000u);
            drain_sync(9000u);
        }
        finish_sync(sha);
        check("payload exact including short tail",
            memcmp(flash_fixture.bytes + OTA_STAGING_PAYLOAD_OFFSET, pkg, 9000u) == 0);
        check("overlay released exactly once per admission",
            te.overlay_acquire_count == te.overlay_release_count);
        if (!mode) check("one existing write per block, not 16 XIP restores", operations == 6u);
    }
    free(pkg);
}

static void invalid_adapter_calls(void)
{
    ota_pipeline_io_t io;
    uint8_t byte = 0;
    unsigned before;
    setup_sync();
    before = flash_fixture.operation_count;
    check("missing port fails closed", ota_pipeline_sync_init(&io, NULL) < 0 && io.start == NULL);
    check("metadata excluded from payload port", sync_io.start(sync_io.ctx,
        OTA_PIPELINE_ERASE, OTA_EXT_STAGING, NULL, 4096u) < 0);
    check("address wrap rejected", sync_io.start(sync_io.ctx, OTA_PIPELINE_PROGRAM,
        0xffffff00u, &byte, 4096u) < 0);
    check("misaligned program rejected", sync_io.start(sync_io.ctx, OTA_PIPELINE_PROGRAM,
        OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET + 1u, &byte, 1u) < 0);
    check("invalid operation rejected", sync_io.start(sync_io.ctx, 9u,
        OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET, &byte, 1u) < 0);
    check("invalid calls have no IO effects", flash_fixture.operation_count == before);
}

#ifndef P34_PIPELINE_SYNC_HELPERS_ONLY
int main(void)
{
    (void)legacy_main();
    transfer_and_faults();
    invalid_adapter_calls();
    printf("PIPELINE_SYNC checks=%d failures=%d\n", checks, failures);
    return failures ? 1 : 0;
}
#endif
