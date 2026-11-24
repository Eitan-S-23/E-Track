#include <stddef.h>
#include <stdint.h>
#include "OTA/ota_ble_session.h"

/* Offline ABI probe, compiled with the running image's original C flags. */
#define FIELD(member) offsetof(ota_ble_session_t, member), \
    sizeof(((ota_ble_session_t *)0)->member)

const uint32_t p34_session_layout[] = {
    0x50334C59u, sizeof(ota_ble_session_t), 21u,
    FIELD(state), FIELD(session_id), FIELD(next_session_id),
    FIELD(expected_seq), FIELD(total_len), FIELD(package_sha256),
    FIELD(target_vcode), FIELD(pkg_kind),
    FIELD(progress.durable_off), FIELD(progress.segment_bitmap),
    FIELD(progress.resumed), FIELD(progress.complete),
    FIELD(last_frame_ms), FIELD(last_data_ms), FIELD(last_liveness_ms),
    FIELD(last_ack_cmd), FIELD(last_ack_seq), FIELD(receiver), FIELD(isr_active),
    FIELD(tx_frame), FIELD(demux.parser.bad_frames)
};
