#ifndef E_TRACK_OTA_PIPELINE_SYNC_H
#define E_TRACK_OTA_PIPELINE_SYNC_H

#include "ota_pipeline.h"

#if defined(P34_OTA_PIPELINE_SYNC) && P34_OTA_PIPELINE_SYNC
#if !defined(P34_OTA_PIPELINE) || !P34_OTA_PIPELINE
#error Synchronous pipeline port requires the experimental pipeline
#endif
#ifdef __cplusplus
extern "C" {
#endif

/* Partial overlap only: UART ISR buffers bytes during existing blocking IO.
 * The underlying port must restore XIP before returning, as in legacy staging.
 * No physical operation or source-pointer ownership survives a callback. */
int ota_pipeline_sync_init(ota_pipeline_io_t *out, ota_staging_io_t *staging);

#ifdef __cplusplus
}
#endif
#endif
#endif
