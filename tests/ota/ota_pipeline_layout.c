#include "OTA/ota_pipeline.h"
#include "OTA/ota_ble_session.h"
#include <stddef.h>

const uint32_t ota_pipeline_layout[] = {
    sizeof(ota_pipeline_t), sizeof(ota_staging_receiver_t),
    offsetof(ota_pipeline_t, store) + offsetof(ota_staging_receiver_t, block),
    offsetof(ota_pipeline_t, second_block), OTA_PIPELINE_MAX_IN_FLIGHT
};
typedef char pipeline_fits_overlay[(sizeof(ota_pipeline_t) + 4096u <= 40960u) ? 1 : -1];

const uint32_t ota_pipeline_session_layout[] = {
    sizeof(ota_ble_session_t), sizeof(ota_ble_env_t), OTA_BLE_MAX_FRAME,
    sizeof(ota_pipeline_t) + CONFIG_OTA_BLE_RX_RING_SIZE
};
