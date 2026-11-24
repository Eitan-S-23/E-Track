/* Exercise the real session/staging implementation, without changing it. */
#define main original_session_tests
#include "test_ota_ble_session.c"
#undef main

int main(void)
{
    uint8_t *pkg, sha[32], digest_before[32], digest_after[32];
    uint8_t *original_flash;
    boot_sha256_ctx_t saved;
    tx_view_t reply;
    uint32_t i, ops, acked = 0;
    int good = 1;

    make_staging_io();
    begin_case();
    pkg = make_full_package(8192u);
    original_flash = malloc(sizeof(flash_fixture.bytes));
    if (pkg == NULL || original_flash == NULL) return 1;
    sha256_of(pkg, 8192u, sha);
    wire_len = (uint16_t)build_begin_frame(0u, 8192u, sha, pkg, 1u);
    feed_idle(wire_len);
    check("BEGIN admits zero durable state", last_tx(&reply) &&
          tx_status(&reply) == OTA_BLE_STATUS_OK && session.progress.durable_off == 0u);
    ops = flash_fixture.operation_count;
    memcpy(original_flash, flash_fixture.bytes, sizeof(flash_fixture.bytes));
    for (i = 1u; i <= 16000u; ++i)
    {
        te.tx_count = 0u;
        wire_len = (uint16_t)build_data_frame((uint16_t)i, session.session_id, 0u, pkg, 128u);
        feed_isr(wire_len);
        te.now_ms = i;
        pump_once();
        good = good && last_tx(&reply) && reply.cmd == OTA_BLE_CMD_ACK_DATA &&
            reply.seq == i && tx_status(&reply) == OTA_BLE_STATUS_OK &&
            tx_durable_off(&reply, 1u) == 0u && tx_bitmap(&reply, 1u) == 1u;
        if (good) ++acked;
        if (i == 1u)
        {
            saved = session.sha;
            boot_sha256_final(&saved, digest_before);
        }
    }
    saved = session.sha;
    boot_sha256_final(&saved, digest_after);
    check("16000 new-sequence identical DATA receive exact ACKs", good && acked == 16000u);
    check("duplicates never hash the same segment twice", memcmp(digest_before, digest_after, 32u) == 0);
    check("duplicates have no NOR erase/program", flash_fixture.operation_count == ops);
    check("duplicates preserve the entire NOR fixture", memcmp(original_flash, flash_fixture.bytes,
          sizeof(flash_fixture.bytes)) == 0);
    check("the committing segment is never supplied", session.progress.segment_bitmap == 1u &&
          session.progress.durable_off == 0u && session.demux.parser.bad_frames == 0u);
    te.tx_count = 0u;
    wire_len = (uint16_t)build_abort_frame(16001u, session.session_id);
    feed_isr(wire_len);
    pump_once();
    check("ABORT confirmed without installation or reset", last_tx(&reply) &&
          reply.cmd == OTA_BLE_CMD_ACK_ABORT && tx_status(&reply) == OTA_BLE_STATUS_ABORTED &&
          te.activate_calls == 0u && te.reset_calls == 0u && !ota_ble_session_active(&session));
    check("ABORT releases overlay and preserves NOR", te.overlay_acquire_count == te.overlay_release_count &&
          flash_fixture.operation_count == ops &&
          memcmp(original_flash, flash_fixture.bytes, sizeof(flash_fixture.bytes)) == 0);
    free(pkg);
    free(original_flash);
    printf("CAPACITY_FIXTURE checks=%d failures=%d\n", checks, failures);
    return failures ? 1 : 0;
}
