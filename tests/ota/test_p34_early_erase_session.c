#if !defined(P34_STAGING_EARLY_ERASE) || !P34_STAGING_EARLY_ERASE
#error This test requires the development-only early-erase candidate
#endif

#define main original_session_tests
#include "test_ota_ble_session.c"
#undef main

static const uint8_t *injected_package;
static uint32_t inject_frames;
static uint32_t inject_prefix;
static uint32_t injected_peak;

static int erase_with_rx(void *ctx, uint32_t address)
{
    uint32_t i;
    uint32_t count = inject_frames;
    if (address != OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET + 4096u || !count)
    {
        return flash_erase(ctx, address);
    }
    inject_frames = 0;
    check("early erase runs before accepting or programming second-block DATA",
          session.progress.durable_off == 4096u &&
          session.receiver->segment_bitmap == 0u &&
          count_programs_in(address, 4096u) == 0u);
    /* ISR only: never recursively pump while the synchronous erase is active. */
    for (i = 0; i < count; ++i)
    {
        uint32_t segment = i < 27u ? i + 1u : (count == 31u ? i + 1u : i - 27u);
        uint32_t off = 4096u + segment * 128u;
        size_t len = build_data_frame((uint16_t)(43u + segment), session.session_id,
                                     off, injected_package + off, 128u);
        size_t j;
        for (j = i == 0 ? inject_prefix : 0; j < len; ++j)
        {
            ota_ble_session_isr_feed(&session, wire[j]);
        }
    }
    injected_peak = ota_ble_ring_count(&session.rx_ring);
    if (count == 55u) te.now_ms += 501u;
    return flash_erase(ctx, address);
}

static void receive_during_erase(uint32_t frames, uint32_t prefix)
{
    uint8_t sha[32];
    tx_view_t v;
    uint8_t *pkg;
    uint32_t first = OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET;
    uint32_t dropped;
    size_t j;
    begin_case();
    pkg = make_full_package(8192u);
    check("concurrent receive package allocated", pkg != NULL);
    if (!pkg) return;
    sha256_of(pkg, 8192u, sha);
    wire_len = (uint16_t)build_begin_frame(10u, 8192u, sha, pkg, 1u);
    feed_idle(wire_len);
    send_segments(4096u, pkg, 0u, 11u);
    check("first block is durable before injected erase stall",
          session.progress.durable_off == 4096u && count_erase_at(first) == 1u);

    injected_package = pkg;
    inject_frames = frames;
    inject_prefix = prefix;
    session.receiver->io.erase_4k = erase_with_rx;
    wire_len = (uint16_t)build_data_frame(43u, session.session_id, 4096u, pkg + 4096u, 128u);
    feed_isr(wire_len);
    (void)build_data_frame(44u, session.session_id, 4224u, pkg + 4224u, 128u);
    for (j = 0; j < prefix; ++j) ota_ble_session_isr_feed(&session, wire[j]);
    pump_once();
    dropped = session.rx_ring.dropped;
    check("queued or truncated frames cannot create false durable progress",
          session.progress.durable_off == 4096u &&
          flash_fixture.bytes[OTA_STAGING_BITMAP_OFFSET] == 0xFEu &&
          count_programs_in(first + 4096u, 4096u) == 0u &&
          memcmp(flash_fixture.bytes + OTA_STAGING_PAYLOAD_OFFSET, pkg, 4096u) == 0);
    if (frames == 27u)
    {
        check("window28 including a split frame fits without drops",
              injected_peak == 27u * 142u && dropped == 0u &&
              session.progress.segment_bitmap == 0x0FFFFFFFu);
        send_segments(8192u, pkg, 4096u + 28u * 128u, 71u);
    }
    else
    {
        uint32_t attempts;
        check("window32 or timeout retransmission exposes actual overflow",
              injected_peak == 4095u && dropped == frames * 142u - 4095u);
        te.now_ms += 30001u;
        pump_once();
        check("stalled incomplete transfer times out without activation",
              !ota_ble_session_active(&session) && te.activate_calls == 0u &&
              te.overlay_acquire_count == te.overlay_release_count);
        /* Teardown retains a partial demux frame. The existing sender retries
         * the identical BEGIN after timeout/CRC rejection; do not reset it here. */
        for (attempts = 0; attempts < 3u && !ota_ble_session_active(&session); ++attempts)
        {
            wire_len = (uint16_t)build_begin_frame(100u, 8192u, sha, pkg, 1u);
            feed_idle(wire_len);
        }
        printf("ERASE_RX_RESUME begin_attempts=%u\n", (unsigned)attempts);
        check("bounded BEGIN replay resumes only the durable block",
              last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_OK &&
              tx_durable_off(&v, 2u) == 4096u && tx_bitmap(&v, 2u) == 0u);
        send_segments(8192u, pkg, 4096u, 101u);
    }
    wire_len = (uint16_t)build_end_frame(session.expected_seq, session.session_id, sha);
    feed_isr(wire_len);
    pump_once();
    check("normal or resumed transfer passes whole-package SHA and END",
          last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_END &&
          tx_status(&v) == OTA_BLE_STATUS_OK && te.activate_calls == 1u &&
          memcmp(flash_fixture.bytes + OTA_STAGING_PAYLOAD_OFFSET, pkg, 8192u) == 0);
    check("old durable prefix is never erased again", count_erase_at(first) == 1u);
    printf("ERASE_RX frames=%u split=%u peak=%u dropped=%u\n",
           (unsigned)frames, (unsigned)prefix, (unsigned)injected_peak, (unsigned)dropped);
    free(pkg);
}

int main(void)
{
    (void)original_session_tests();
    receive_during_erase(27u, 0u);
    receive_during_erase(27u, 71u);
    receive_during_erase(27u, 141u);
    receive_during_erase(31u, 71u);
    receive_during_erase(55u, 141u);
    printf("EARLY_ERASE_SESSION_%s checks=%d failures=%d\n",
           failures ? "FAIL" : "PASS", checks, failures);
    return failures ? 1 : 0;
}
