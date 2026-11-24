/* Reuse the real host fixture without modifying the source-pinned old suite. */
#define main original_session_tests
#include "../../tests/ota/test_ota_ble_session.c"
#undef main

int main(void)
{
    uint8_t *pkg;
    uint8_t sha[32];
    uint8_t journal[OTA_STAGING_BLOCK_SIZE];
    uint32_t operations, trial, seg, i;
    tx_view_t reply;
    int original = original_session_tests();
    if (original != 0) return original;
    begin_case();
    pkg = make_full_package(8192u);
    if (pkg == NULL) return 1;
    sha256_of(pkg, 8192u, sha);
    wire_len = (uint16_t)build_begin_frame(0u, 8192u, sha, pkg, 1u);
    feed_idle(wire_len);
    wire_len = (uint16_t)build_abort_frame(1u, session.session_id);
    feed_isr(wire_len);
    pump_once();
    memcpy(journal, flash_fixture.bytes, sizeof(journal));
    operations = flash_fixture.operation_count;

    for (trial = 0; trial < 4u; ++trial)
    {
        wire_len = (uint16_t)build_begin_frame(0u, 8192u, sha, pkg, 1u);
        feed_idle(wire_len);
        check("probe BEGIN resumes an empty matching journal",
              session.progress.durable_off == 0u && session.progress.segment_bitmap == 0u &&
              ota_ble_session_active(&session));
        for (seg = 0; seg < 31u; ++seg)
        {
            wire_len = (uint16_t)build_data_frame((uint16_t)(seg + 1u), session.session_id,
                        seg * 128u, pkg + seg * 128u, 128u);
            for (i = 0; i < wire_len; ++i)
            {
                if (trial % 2u == 1u && seg == 3u && i == 26u) continue;
                ota_ble_session_isr_feed(&session, wire[i]);
            }
            pump_once();
        }
        check("31 probe segments never become durable", session.progress.durable_off == 0u);
        check("single-byte loss is visible to the real parser",
              trial % 2u == 0u || session.demux.parser.bad_frames > 0u);
        wire_len = (uint16_t)build_abort_frame(32u, session.session_id);
        feed_isr(wire_len);
        pump_once();
        check("probe ends with ABORT and an idle receiver", last_tx(&reply) &&
              reply.cmd == OTA_BLE_CMD_ACK_ABORT && tx_status(&reply) == OTA_BLE_STATUS_ABORTED &&
              !ota_ble_session_active(&session) && !ota_ble_session_isr_active(&session));
        check("probe leaves the original journal unchanged", memcmp(journal, flash_fixture.bytes, sizeof(journal)) == 0);
        for (i = operations; i < flash_fixture.operation_count; ++i)
        {
            check("probe performs no NOR program or erase",
                  flash_fixture.operations[i].type != OP_PROGRAM && flash_fixture.operations[i].type != OP_ERASE);
        }
        operations = flash_fixture.operation_count;
    }
    free(pkg);
    printf("UART_PROBE_FIXTURE checks=%d failures=%d\n", checks, failures);
    return failures ? 1 : 0;
}
