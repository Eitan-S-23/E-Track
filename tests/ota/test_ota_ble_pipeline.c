#define main legacy_session_main
#include "test_ota_ble_session.c"
#undef main

/* Real parser/session/staging, asynchronous payload port, no device access. */
static struct
{
    int pending, hold, ticks, cancel, immutable, unsafe_read;
    uint32_t operation, address, len, starts, fail_at;
    const uint8_t *src;
    uint8_t copy[OTA_PIPELINE_PAGE_SIZE];
} async_flash;

static int payload_start(void *ctx, uint32_t operation, uint32_t address,
    const uint8_t *src, uint32_t len)
{
    (void)ctx;
    if (async_flash.pending) return OTA_PIPELINE_ERR_IO;
    async_flash.pending = 1;
    async_flash.operation = operation;
    async_flash.address = address;
    async_flash.len = len;
    async_flash.src = src;
    async_flash.ticks = 2;
    ++async_flash.starts;
    if (src != NULL) memcpy(async_flash.copy, src, len);
    return OTA_PIPELINE_BUSY;
}

static int payload_poll(void *ctx)
{
    int result;
    (void)ctx;
    if (!async_flash.pending) return OTA_PIPELINE_ERR_IO;
    if (async_flash.src != NULL &&
        memcmp(async_flash.copy, async_flash.src, async_flash.len) != 0)
        async_flash.immutable = 0;
    if (async_flash.hold || --async_flash.ticks > 0) return OTA_PIPELINE_BUSY;
    async_flash.pending = 0;
    result = async_flash.operation == OTA_PIPELINE_ERASE
        ? flash_erase(NULL, async_flash.address)
        : flash_program(NULL, async_flash.address, async_flash.src, async_flash.len);
    if (async_flash.fail_at == async_flash.starts) result = -1;
    return result == 0 ? OTA_PIPELINE_OK : OTA_PIPELINE_ERR_IO;
}

static void payload_cancel(void *ctx)
{
    (void)ctx;
    ++async_flash.cancel;
}

static int guarded_read(void *ctx, uint32_t address, uint8_t *dst, uint32_t len)
{
    if (async_flash.pending)
    {
        ++async_flash.unsafe_read;
        return -1;
    }
    return flash_read(ctx, address, dst, len);
}

static int guarded_erase(void *ctx, uint32_t address)
{
    if (async_flash.pending)
    {
        ++async_flash.unsafe_read;
        return -1;
    }
    return flash_erase(ctx, address);
}

static int guarded_program(void *ctx, uint32_t address, const uint8_t *src, uint32_t len)
{
    if (async_flash.pending)
    {
        ++async_flash.unsafe_read;
        return -1;
    }
    return flash_program(ctx, address, src, len);
}

static const ota_pipeline_io_t payload_io = {NULL, payload_start, payload_poll, payload_cancel};

static union
{
    uint64_t alignment;
    uint8_t bytes[40960];
} pipeline_workspace;

static uint8_t *aligned_workspace(uint32_t *size)
{
    *size = te.workspace_size;
    return pipeline_workspace.bytes;
}

static void setup2(void)
{
    memset(&async_flash, 0, sizeof(async_flash));
    async_flash.immutable = 1;
    make_staging_io();
    staging_io.read = guarded_read;
    staging_io.erase_4k = guarded_erase;
    staging_io.program = guarded_program;
    begin_case();
    session.env.pipeline_io = &payload_io;
    session.env.overlay_workspace = aligned_workspace;
}

static void deliver2(size_t len, size_t fragment)
{
    size_t i;
    for (i = 0u; i < len; ++i)
    {
        if (ota_ble_session_isr_active(&session))
            ota_ble_session_isr_feed(&session, wire[i]);
        else
            ota_ble_session_feed_idle(&session, NULL, NULL, wire[i]);
        if (fragment != 0u && (i + 1u) % fragment == 0u) pump_once();
    }
    pump_once();
}

static void caps2(uint32_t epoch)
{
    uint8_t payload[4];
    write_u32le(payload, epoch);
    deliver2(ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_CAPS2,
        0u, 7u, payload, sizeof(payload)), 1u);
}

static void begin2(uint32_t epoch, uint16_t seq, const uint8_t *pkg,
    uint32_t len, const uint8_t sha[32])
{
    uint8_t payload[OTA_BLE_LEN_BEGIN2];
    payload[0] = 2u;
    write_u32le(payload + 1u, len);
    memcpy(payload + 5u, sha, 32u);
    memcpy(payload + 37u, pkg, 64u);
    write_u32le(payload + 101u, epoch);
    deliver2(ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_BEGIN2,
        0u, seq, payload, sizeof(payload)), 3u);
}

static size_t data2(uint32_t epoch, uint8_t sid, uint16_t seq, uint32_t off,
    const uint8_t *data, uint32_t len)
{
    uint8_t payload[136];
    write_u32le(payload, epoch);
    write_u32le(payload + 4u, off);
    memcpy(payload + 8u, data, len);
    return ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_DATA2,
        sid, seq, payload, (uint16_t)(8u + len));
}

static void send2(const uint8_t *pkg, uint32_t from, uint32_t end)
{
    uint32_t off;
    for (off = from; off < end; off += 128u)
    {
        uint32_t len = end - off < 128u ? end - off : 128u;
        uint16_t seq = (uint16_t)(session.pipeline_first_seq +
            (off - session.pipeline_resume_off) / 128u);
        deliver2(data2(session.pipeline_ack.epoch, session.session_id,
            seq, off, pkg + off, len), 0u);
    }
}

static void abort2(uint32_t epoch, uint8_t sid)
{
    uint8_t payload[4];
    write_u32le(payload, epoch);
    deliver2(ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_ABORT2,
        sid, 400u, payload, sizeof(payload)), 0u);
}

static void end2(const uint8_t sha[32])
{
    uint8_t payload[36];
    uint16_t seq = (uint16_t)(session.pipeline_first_seq +
        (session.total_len - session.pipeline_resume_off + 127u) / 128u);
    write_u32le(payload, session.pipeline_ack.epoch);
    memcpy(payload + 4u, sha, 32u);
    deliver2(ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_END2,
        session.session_id, seq, payload, sizeof(payload)), 0u);
}

static void settle(uint32_t durable)
{
    unsigned budget = 1000u;
    while (session.pipeline != NULL && session.progress.durable_off < durable && budget-- != 0u)
        pump_once();
    check("bounded pump reaches requested durable frontier or terminal error", budget != 0u);
}

static void check_resources(void)
{
    check("no buffer mutation while hardware owns source", async_flash.immutable);
    check("no synchronous staging IO while payload port is busy", async_flash.unsafe_read == 0);
    check("overlay released exactly once after quiescence",
        te.overlay_acquire_count == te.overlay_release_count && !async_flash.pending);
}

static void test_pipeline_transfer(void)
{
    uint8_t *pkg;
    uint8_t sha[32];
    tx_view_t v;
    uint32_t before;
    setup2();
    pkg = make_full_package(9000u);
    if (pkg == NULL) exit(2);
    sha256_of(pkg, 9000u, sha);
    begin2(123u, 65520u, pkg, 9000u, sha);
    check("BEGIN2 requires prior capability negotiation",
        last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_SESSION && te.overlay_acquire_count == 0u);
    caps2(123u);
    check("CAPS2 returns version, two blocks, segment, nonce and physical cap",
        last_tx(&v) && v.cmd == OTA_BLE_CMD_CAPS2_REPLY && v.len == 16u &&
        memcmp(v.payload, "P2BL\2\2\200\0", 8u) == 0 &&
        read_u32le(v.payload + 8u) == 123u && read_u32le(v.payload + 12u) == 24u);
    begin2(123u, 65520u, pkg, 9000u, sha);
    check("fragmented BEGIN2 opens with zero durable and two-block credit",
        last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_BEGIN2 && v.len == 18u &&
        tx_status(&v) == 0u && read_u32le(v.payload + 2u) == 123u &&
        read_u32le(v.payload + 6u) == 0u && read_u32le(v.payload + 14u) == 8192u);
    async_flash.hold = 1;
    send2(pkg, 0u, 8192u);
    check("second block accepted while first erase is still busy, seq wraps",
        session.pipeline_ack.accepted_off == 8192u && session.progress.durable_off == 0u &&
        async_flash.pending && session.expected_seq == 49u);
    check("DATA2 ACK has explicit epoch, durable, accepted and credit",
        last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_DATA2 && v.len == 17u &&
        read_u32le(v.payload + 1u) == 123u && read_u32le(v.payload + 5u) == 0u &&
        read_u32le(v.payload + 9u) == 8192u && read_u32le(v.payload + 13u) == 8192u);
    send2(pkg, 8192u, 8320u);
    check("third block rejected without consuming sequence credit",
        last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_OFFSET && session.expected_seq == 49u);
    before = flash_fixture.operation_count;
    begin2(123u, 65520u, pkg, 9000u, sha);
    check("lost BEGIN2 ACK replay does not reset buffers or do Flash IO",
        last_tx(&v) && tx_status(&v) == 0u && session.pipeline_ack.accepted_off == 8192u &&
        flash_fixture.operation_count == before && te.overlay_acquire_count == 1u);
    deliver2(data2(124u, session.session_id, 65521u, 0u, pkg, 128u), 0u);
    check("stale epoch is rejected without altering receive state",
        last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_SESSION && session.expected_seq == 49u);
    deliver2(data2(123u, 99u, 65521u, 0u, pkg, 128u), 0u);
    check("wrong session cannot borrow valid epoch",
        last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_SESSION);
    deliver2(data2(123u, session.session_id, 65522u, 0u, pkg, 128u), 0u);
    check("sequence remains bound to its original segment offset",
        last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_SEQ);
    deliver2(data2(123u, session.session_id, 65521u, 0u, pkg, 128u), 1u);
    check("fragmented identical retransmission does not rehash or rewrite",
        last_tx(&v) && tx_status(&v) == 0u && flash_fixture.operation_count == before);
    wire_len = (uint16_t)data2(123u, session.session_id, 65521u, 0u, pkg, 128u);
    wire[wire_len - 1u] ^= 1u;
    deliver2(wire_len, 7u);
    check("bad DATA2 CRC yields v2 NAK without advancing state",
        last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_DATA2 &&
        tx_status(&v) == OTA_BLE_STATUS_ERR_CRC && session.expected_seq == 49u);
    deliver2(build_abort_frame(1u, session.session_id), 0u);
    deliver2(build_begin_frame(1u, 9000u, sha, pkg, 1u), 0u);
    deliver2(build_get_info_frame(1u, 0u), 0u);
    check("late v1 controls cannot release, replace or inspect a busy v2 session",
        session.pipeline != NULL && !session.pipeline->stopped && te.overlay_release_count == 0u);
    async_flash.hold = 0;
    settle(4096u);
    check("first verified commit extends receive credit before second block is durable",
        session.progress.durable_off == 4096u && session.pipeline_ack.credit_end == 9000u);
    send2(pkg, 8192u, 9000u);
    settle(9000u);
    check("all three blocks and short final segment are durable", session.progress.durable_off == 9000u);
    end2(sha);
    check("END2 uses existing SHA, finalize, activate and reset path",
        last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_END2 && tx_status(&v) == 0u &&
        te.activate_calls == 1u && te.reset_calls == 1u && !ota_ble_session_active(&session));
    check("staged bytes and whole-package CRC match through seq wrap and duplicate",
        memcmp(flash_fixture.bytes + OTA_STAGING_PAYLOAD_OFFSET, pkg, 9000u) == 0 &&
        read_u32le(flash_fixture.bytes + 12u) == boot_crc32(pkg, 9000u));
    check_resources();
    free(pkg);
}

static void test_pipeline_cancel_faults(void)
{
    uint8_t *pkg;
    uint8_t sha[32];
    tx_view_t v;
    unsigned mode;
    pkg = make_full_package(5000u);
    if (pkg == NULL) exit(2);
    sha256_of(pkg, 5000u, sha);
    for (mode = 0u; mode < 5u; ++mode)
    {
        uint32_t count, header_erases;
        setup2();
        caps2(200u + mode);
        begin2(200u + mode, 10u, pkg, 5000u, sha);
        async_flash.hold = 1;
        send2(pkg, 0u, 4096u);
        count = te.tx_count;
        header_erases = count_erase_at(OTA_EXT_STAGING);
        if (mode == 0u) abort2(200u, session.session_id);
        if (mode == 1u)
        {
            pkg[100] ^= 1u;
            deliver2(data2(201u, session.session_id, 11u, 0u, pkg, 128u), 0u);
            pkg[100] ^= 1u;
        }
        if (mode == 2u)
        {
            te.now_ms += OTA_PIPELINE_OP_TIMEOUT_MS;
            pump_once();
        }
        if (mode == 3u) end2(sha);
        if (mode == 4u)
        {
            unsigned budget = 1000u;
            /* A busy page, not just erase, must retain its source after ABORT. */
            async_flash.hold = 0;
            while (async_flash.operation != OTA_PIPELINE_PROGRAM && budget-- != 0u) pump_once();
            check("bounded pump reaches an outstanding program page", budget != 0u);
            async_flash.hold = 1;
            abort2(204u, session.session_id);
        }
        check("cancel/error keeps active ownership while the operation is pending",
            session.state == OTA_BLE_SESSION_DRAINING && ota_ble_session_active(&session) &&
            ota_ble_session_isr_active(&session) && te.overlay_release_count == 0u &&
            async_flash.pending && async_flash.cancel == 1);
        if (mode == 0u || mode == 4u)
            check("ABORTED is not acknowledged before quiescence", te.tx_count == count);
        check("incomplete END/cancel never races header erase", count_erase_at(OTA_EXT_STAGING) == header_erases);
        begin2(200u + mode, 10u, pkg, 5000u, sha);
        check("BEGIN2 during drain cannot reuse buffers",
            last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_BUSY && te.overlay_acquire_count == 1u);
        async_flash.hold = 0;
        settle(5000u);
        check("drain finishes without committing an uncertain block",
            !ota_ble_session_active(&session) && session.progress.durable_off == 0u &&
            te.activate_calls == 0u && te.reset_calls == 0u);
        if (mode == 0u || mode == 4u)
            check("ABORTED is sent after hardware settles",
                last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_ABORT2 && tx_status(&v) == OTA_BLE_STATUS_ABORTED);
        check_resources();
    }
    free(pkg);
}

static void test_pipeline_resume(void)
{
    uint8_t *pkg;
    uint8_t sha[32];
    tx_view_t v;
    setup2();
    pkg = make_full_package(9000u);
    if (pkg == NULL) exit(2);
    sha256_of(pkg, 9000u, sha);
    caps2(301u);
    begin2(301u, 10u, pkg, 9000u, sha);
    send2(pkg, 0u, 4096u);
    settle(4096u);
    send2(pkg, 4096u, 4224u);
    abort2(301u, session.session_id);
    caps2(301u);
    begin2(301u, 60u, pkg, 9000u, sha);
    check("retired immediate epoch cannot be reopened",
        last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_SESSION);
    caps2(302u);
    begin2(302u, 60u, pkg, 9000u, sha);
    check("new generation resumes only durable prefix, not volatile data",
        last_tx(&v) && tx_status(&v) == 0u && session.pipeline_ack.accepted_off == 4096u &&
        session.pipeline_ack.durable_off == 4096u && session.pipeline_ack.epoch == 302u);
    abort2(301u, session.session_id);
    check("late ABORT with reused session byte but old epoch cannot stop resume",
        last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_SESSION && session.pipeline != NULL);
    send2(pkg, 4096u, 9000u);
    settle(9000u);
    end2(sha);
    check("resume rebuilds SHA/CRC prefix and completes exactly once",
        last_tx(&v) && tx_status(&v) == 0u && te.activate_calls == 1u && te.reset_calls == 1u &&
        count_erase_at(OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET) == 1u &&
        read_u32le(flash_fixture.bytes + 12u) == boot_crc32(pkg, 9000u));
    check_resources();
    free(pkg);
}

static void test_pipeline_admission_digest_failures(void)
{
    uint8_t *pkg;
    uint8_t sha[32], wrong[32];
    tx_view_t v;
    unsigned mode;
    pkg = make_full_package(1000u);
    if (pkg == NULL) exit(2);
    sha256_of(pkg, 1000u, sha);
    memcpy(wrong, sha, 32u);
    wrong[0] ^= 1u;
    setup2();
    session.env.pipeline_io = NULL;
    caps2(400u);
    check("no async port means no advertised CAPS2", te.tx_count == 0u);
    begin2(400u, 10u, pkg, 1000u, sha);
    check("no async port rejects BEGIN2 before any Flash work",
        last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_PROTO && flash_fixture.operation_count == 0u);
    for (mode = 0u; mode < 2u; ++mode)
    {
        setup2();
        caps2(401u + mode);
        begin2(401u + mode, 10u, pkg, 1000u, mode == 0u ? sha : wrong);
        send2(pkg, 0u, 1000u);
        settle(1000u);
        end2(wrong);
        check("SHA restatement or actual digest mismatch cannot finalize or activate",
            last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_END2 && tx_status(&v) == OTA_BLE_STATUS_ERR_SHA &&
            te.activate_calls == 0u && flash_fixture.bytes[OTA_STAGING_ETRJ_OFFSET] == 0xFFu);
        check_resources();
    }
    setup2();
    caps2(500u);
    begin2(500u, 10u, pkg, 1000u, sha);
    send2(pkg, 0u, 128u);
    te.now_ms += CONFIG_OTA_BLE_SESSION_TIMEOUT_MS;
    send2(pkg, 0u, 128u);
    check("valid duplicate traffic cannot defeat the no-durable-progress deadline",
        !ota_ble_session_active(&session) && session.progress.durable_off == 0u && te.activate_calls == 0u);
    check_resources();
    free(pkg);
}

static void test_pipeline_io_failures(void)
{
    uint8_t *pkg;
    uint8_t sha[32];
    unsigned operation;
    pkg = make_full_package(4096u);
    if (pkg == NULL) exit(2);
    sha256_of(pkg, 4096u, sha);
    for (operation = 1u; operation <= 17u; ++operation)
    {
        tx_view_t v;
        setup2();
        caps2(600u + operation);
        begin2(600u + operation, 10u, pkg, 4096u, sha);
        async_flash.fail_at = operation;
        send2(pkg, 0u, 4096u);
        settle(4096u);
        check("uncertain erase/page result never becomes durable or activates",
            last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_FLASH &&
            !ota_ble_session_active(&session) && session.progress.durable_off == 0u &&
            te.activate_calls == 0u && te.reset_calls == 0u);
        check_resources();
    }
    free(pkg);
}

static void test_pipeline_frame_lengths(void)
{
    static const struct {uint8_t cmd; uint16_t low, high;} cases[] = {
        {OTA_BLE_CMD_CAPS2, 4u, 4u}, {OTA_BLE_CMD_BEGIN2, 105u, 105u},
        {OTA_BLE_CMD_DATA2, 9u, 136u}, {OTA_BLE_CMD_END2, 36u, 36u},
        {OTA_BLE_CMD_ABORT2, 4u, 4u}, {OTA_BLE_CMD_DATA, 4u, 132u}
    };
    unsigned i, variant;
    for (i = 0u; i < sizeof(cases) / sizeof(cases[0]); ++i)
    {
        for (variant = 0u; variant < 4u; ++variant)
        {
            uint16_t len = variant == 0u ? cases[i].low : variant == 1u ? cases[i].high :
                variant == 2u ? (uint16_t)(cases[i].low - 1u) : (uint16_t)(cases[i].high + 1u);
            uint8_t payload[OTA_BLE_MAX_PAYLOAD] = {0};
            ota_ble_parser_t parser;
            ota_ble_frame_t frame;
            ota_ble_parse_result_t result = OTA_BLE_PARSE_IDLE;
            size_t j, n;
            memset(&parser, 0, sizeof(parser));
            ota_ble_parser_reset(&parser);
            n = ota_ble_frame_encode(wire, sizeof(wire), cases[i].cmd, 1u, 55u,
                payload, len <= OTA_BLE_MAX_PAYLOAD ? len : 0u);
            wire[6] = (uint8_t)len;
            wire[7] = (uint8_t)(len >> 8);
            for (j = 0u; j < n && result == OTA_BLE_PARSE_IDLE; ++j)
                result = ota_ble_parser_feed(&parser, wire[j], &frame);
            check("frame parser enforces v1/v2 command-specific lengths",
                result == (variant < 2u ? OTA_BLE_PARSE_FRAME : OTA_BLE_PARSE_ERR_FRAME));
        }
    }
}

int main(void)
{
    (void)legacy_session_main();
    test_pipeline_transfer();
    test_pipeline_cancel_faults();
    test_pipeline_resume();
    test_pipeline_admission_digest_failures();
    test_pipeline_io_failures();
    test_pipeline_frame_lengths();
    printf("PIPELINE_SESSION checks=%d failures=%d\n", checks, failures);
    return failures == 0 ? 0 : 1;
}
