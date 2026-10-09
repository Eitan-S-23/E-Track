#define P34_PIPELINE_SYNC_HELPERS_ONLY 1
#include <test_ota_pipeline_sync.c>

enum { BAD_OFFSET = 11u * 4096u, PREFIX_END = 13u * 4096u };
enum {
    CONTROL, MISSING_PAGES, PROGRAM_IO, RESTORE_IO, READ_IO,
    MAPPED_MISMATCH, JOURNAL_IO, CALLBACK_ABORT, CALLBACK_END,
    CALLBACK_CONFLICT, MODE_COUNT
};

static const char *mode_names[] = {
    "control", "missing_pages", "program_io", "restore_io", "read_io",
    "mapped_mismatch", "journal_io", "callback_abort", "callback_end",
    "callback_conflict"
};
static unsigned model_mode, injected, frames_seen, invalid_frames, errors_seen;
static int mutate_source;
static tx_view_t first_error;
static const uint8_t *original;
static uint32_t original_len;
static uint8_t original_sha[32];

static int capture_send(const uint8_t *frame, uint16_t len)
{
    tx_view_t view;
    /* Consume each frame before reusing the existing bounded fixture slot. */
    te.tx_count = 0u;
    (void)env_send(frame, len);
    ++frames_seen;
    if (!last_tx(&view))
        ++invalid_frames;
    else if (view.cmd >= OTA_BLE_CMD_ACK_BEGIN2 && view.cmd <= OTA_BLE_CMD_ACK_ABORT2 &&
             tx_status(&view) != OTA_BLE_STATUS_OK)
    {
        if (errors_seen++ == 0u) first_error = view;
    }
    return 0;
}

static void callback_command(unsigned mode, ota_pipeline_t *owned)
{
    uint8_t payload[136];
    size_t len;
    write_u32le(payload, owned->epoch);
    if (mode == CALLBACK_ABORT)
        len = ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_ABORT2,
            session.session_id, 400u, payload, 4u);
    else if (mode == CALLBACK_END)
    {
        uint16_t seq = (uint16_t)(session.pipeline_first_seq +
            (original_len - session.pipeline_resume_off + 127u) / 128u);
        memcpy(payload + 4u, original_sha, 32u);
        len = ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_END2,
            session.session_id, seq, payload, 36u);
    }
    else
    {
        uint16_t seq = (uint16_t)(session.pipeline_first_seq +
            (BAD_OFFSET - session.pipeline_resume_off) / 128u);
        write_u32le(payload + 4u, BAD_OFFSET);
        memcpy(payload + 8u, original + BAD_OFFSET, 128u);
        payload[8] ^= 1u;
        len = ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_DATA2,
            session.session_id, seq, payload, sizeof(payload));
    }
    deliver(len, 0);
    ota_ble_session_receive_pending(&session);
}

static int modeled_program(void *ctx, uint32_t address, const uint8_t *src, uint32_t len)
{
    const uint32_t base = OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET;
    const uint32_t journal = OTA_EXT_STAGING + OTA_STAGING_BITMAP_OFFSET + 11u / 8u;
    uint32_t page;
    if (model_mode == JOURNAL_IO && injected && address == journal && len == 1u)
        return -1;
    if (address != base + BAD_OFFSET || injected)
        return flash_program(ctx, address, src, len);

    {
        uint8_t before[OTA_STAGING_BLOCK_SIZE];
        ota_pipeline_t *owned = session.pipeline;
        unsigned releases = te.overlay_release_count;
        ++injected;
        check("twelfth block source has the exact original bytes",
            len == sizeof(before) && memcmp(src, original + BAD_OFFSET, len) == 0);
        if (len != sizeof(before) || owned == NULL) return -1;
        memcpy(before, src, len);
        check("twelfth program pins both source and overlay", owned->pending && owned->in_start);
        check("nested poll cannot finish an owned synchronous operation",
            ota_pipeline_poll(owned, te.now_ms) == OTA_PIPELINE_BUSY);
        if (model_mode >= CALLBACK_ABORT)
        {
            callback_command(model_mode, owned);
            check("callback cancellation enters draining, not freed state",
                session.state == OTA_BLE_SESSION_DRAINING);
        }
        else
        {
            uint32_t off;
            for (off = BAD_OFFSET + 4096u; off < PREFIX_END; off += 128u)
            {
                deliver(data_sync(original, off, 128u), 0);
                ota_ble_session_receive_pending(&session);
            }
            check("thirteenth block accepted during twelfth program",
                owned->accepted_off == PREFIX_END);
        }
        if (mutate_source && model_mode == CONTROL) ((uint8_t *)src)[17] ^= 1u;
        check("borrowed source unchanged across receive callback", memcmp(before, src, len) == 0);
        check("callback cannot release overlay or report durable progress",
            session.pipeline == owned && te.overlay_release_count == releases &&
            !ota_pipeline_can_release(owned) && session.progress.durable_off == BAD_OFFSET &&
            te.activate_calls == 0u && te.reset_calls == 0u && session.rx_ring.dropped == 0u);
    }
    for (page = 0u; page < len; page += 256u)
    {
        if (model_mode == MISSING_PAGES && (page == 0x500u || page == 0x700u)) continue;
        if (model_mode == PROGRAM_IO && page == 0x500u) return -1;
        if (flash_program(ctx, address + page, src + page, 256u) != 0) return -1;
    }
    /* Models the combined HAL program/restore result, not a real NOR driver. */
    return model_mode == RESTORE_IO ? -1 : 0;
}

static ota_staging_result_t modeled_verify(void *ctx, uint32_t address,
                                           const uint8_t *expected, uint32_t len)
{
    uint8_t readback[OTA_STAGING_BLOCK_SIZE];
    const uint32_t bad = OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET + BAD_OFFSET;
    if (address == bad && model_mode == READ_IO) return OTA_STAGING_ERR_IO;
    if (len > sizeof(readback) || flash_read(ctx, address, readback, len) != 0)
        return OTA_STAGING_ERR_IO;
    if (address == bad && model_mode == MAPPED_MISMATCH) readback[17] ^= 1u;
    return memcmp(readback, expected, len) == 0 ? OTA_STAGING_OK : OTA_STAGING_ERR_VERIFY;
}

static void close_prefix(void)
{
    uint8_t payload[4];
    if (session.pipeline == NULL) return;
    write_u32le(payload, session.pipeline_ack.epoch);
    deliver(ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_ABORT2,
        session.session_id, 500u, payload, sizeof(payload)), 1);
    pump_once();
    check("incomplete prefix closes without END or activation",
        session.pipeline == NULL && te.activate_calls == 0u && te.reset_calls == 0u &&
        te.overlay_acquire_count == te.overlay_release_count);
}

static void run_case(unsigned mode)
{
    const uint8_t *payload = flash_fixture.bytes + OTA_STAGING_PAYLOAD_OFFSET;
    uint32_t off;
    unsigned wanted;
    setup_sync();
    session.env.send = capture_send;
    staging_io.program = modeled_program;
    staging_io.verify = modeled_verify;
    model_mode = mode;
    injected = frames_seen = invalid_frames = errors_seen = 0u;
    memset(&first_error, 0, sizeof(first_error));
    printf("CASE %s\n", mode_names[mode]);
    open_sync(1000u + mode, original, original_len, original_sha);
    if (!session.pipeline) return;
#if defined(P34_TEST_STOPPED_ACK) && P34_TEST_STOPPED_ACK
    if (mode == CONTROL)
    {
        uint8_t bytes[OTA_PIPELINE_ACK_BYTES], unchanged[OTA_PIPELINE_ACK_BYTES];
        ota_pipeline_ack_t ack;
        memset(bytes, 0xA5, sizeof(bytes));
        memcpy(unchanged, bytes, sizeof(bytes));
        session.pipeline->stopped = 1u;
        session.pipeline->error = 0;
        check("stopped receiver cannot return a success snapshot without fields",
            ota_pipeline_snapshot(session.pipeline, &ack) == OTA_PIPELINE_ERR_STOPPED);
        check("stopped receiver cannot encode uninitialized ACK bytes",
            ota_pipeline_ack_encode(session.pipeline, bytes) == OTA_PIPELINE_ERR_STOPPED &&
            memcmp(bytes, unchanged, sizeof(bytes)) == 0);
        session.pipeline->stopped = 0u;
    }
#endif
    for (off = 0u; off < BAD_OFFSET; off += 4096u)
    {
        send_sync(original, off, off + 4096u);
        drain_sync(off + 4096u);
    }
    check("eleven committed blocks match the original package",
        session.progress.durable_off == BAD_OFFSET && memcmp(payload, original, BAD_OFFSET) == 0);
    send_sync(original, BAD_OFFSET, BAD_OFFSET + 4096u);
    drain_sync(PREFIX_END);
    check("twelfth-block callback occurred exactly once", injected == 1u);
    check("every captured model frame has valid length and CRC",
        frames_seen != 0u && invalid_frames == 0u);
    check("old committed prefix survives every failure", memcmp(payload, original, BAD_OFFSET) == 0);
    check("no prefix test activates or resets firmware", te.activate_calls == 0u && te.reset_calls == 0u);
    if (mode != CONTROL)
    {
        wanted = mode == CALLBACK_ABORT || mode == CALLBACK_CONFLICT ? OTA_BLE_STATUS_ABORTED :
            mode == CALLBACK_END ? OTA_BLE_STATUS_ERR_STATE : OTA_BLE_STATUS_ERR_FLASH;
        check("failed block stays uncommitted with durable at 45056",
            session.pipeline == NULL && session.progress.durable_off == BAD_OFFSET &&
            (flash_fixture.bytes[OTA_STAGING_BITMAP_OFFSET + 1u] & 8u) != 0u);
        check("first model error retains its real status and epoch",
            errors_seen != 0u && tx_status(&first_error) == wanted &&
            first_error.len == OTA_BLE_LEN_ACK_OTHER2 &&
            read_u32le(first_error.payload + 1u) == 1000u + mode &&
            read_u32le(first_error.payload + 5u) == BAD_OFFSET);
        if (mode == MISSING_PAGES)
        {
            unsigned differences = 0u;
            for (off = BAD_OFFSET; off < BAD_OFFSET + 4096u; ++off)
                if (payload[off] != original[off]) ++differences;
            check("model recreates original two FF pages and 511 byte differences",
                differences == 511u && payload[0xB500u] == 0xFFu && payload[0xB700u] == 0xFFu);
        }
        model_mode = CONTROL;
        open_sync(2000u + mode, original, original_len, original_sha);
        check("new epoch reloads journal rather than volatile accepted credit",
            session.pipeline != NULL && session.pipeline_ack.durable_off == BAD_OFFSET &&
            session.pipeline_ack.accepted_off == BAD_OFFSET);
        if (session.pipeline)
        {
            send_sync(original, BAD_OFFSET, PREFIX_END);
            drain_sync(PREFIX_END);
            check("resume erases the uncommitted twelfth block again",
                count_erase_at(OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET + BAD_OFFSET) == 2u);
        }
    }
    check("healthy or recovered thirteen-block prefix is byte-exact",
        session.progress.durable_off == PREFIX_END && memcmp(payload, original, PREFIX_END) == 0);
    printf("MODEL_RESULT mode=%s durable=%lu first_status=%lu frames=%u\n",
        mode_names[mode], (unsigned long)session.progress.durable_off,
        errors_seen ? (unsigned long)tx_status(&first_error) : 0ul, frames_seen);
    close_prefix();
}

int main(int argc, char **argv)
{
    FILE *file;
    long length;
    uint8_t *bytes;
    unsigned mode;
    (void)legacy_main;
    (void)transfer_and_faults;
    (void)invalid_adapter_calls;
    if (argc != 2 && (argc != 3 || strcmp(argv[2], "--mutate-source") != 0)) return 2;
    mutate_source = argc == 3;
    file = fopen(argv[1], "rb");
    if (!file || fseek(file, 0, SEEK_END) != 0) return 2;
    length = ftell(file);
    if (length < 0 || (unsigned long)length < PREFIX_END ||
        (unsigned long)length > OTA_ETU_MAX_LENGTH || fseek(file, 0, SEEK_SET) != 0) return 2;
    bytes = (uint8_t *)malloc((size_t)length);
    if (!bytes || fread(bytes, 1u, (size_t)length, file) != (size_t)length) return 2;
    fclose(file);
    original = bytes;
    original_len = (uint32_t)length;
    sha256_of(bytes, original_len, original_sha);
    for (mode = 0u; mode < (mutate_source ? 1u : MODE_COUNT); ++mode) run_case(mode);
    free(bytes);
    printf("RECEIVER_FAILURE checks=%d failures=%d cases=%u mutation=%d\n",
        checks, failures, mutate_source ? 1u : MODE_COUNT, mutate_source);
    return failures ? 1 : 0;
}
