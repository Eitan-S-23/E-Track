#ifndef E_TRACK_HAL_OTA_STAGING_H
#define E_TRACK_HAL_OTA_STAGING_H

#include "OTA/ota_staging.h"

namespace HAL
{

void OTA_StagingGetIo(ota_staging_io_t *io);

#if defined(P2_1_TEST_ENABLE)
bool OTA_StagingEvidenceRun();
#endif

}

#if defined(P2_1_TEST_ENABLE)
extern "C" void HAL_OTA_StagingEvidenceCheckpoint(void);
extern "C" void HAL_OTA_StagingEvidenceDone(void);
#endif

#endif
