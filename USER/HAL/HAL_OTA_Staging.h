#ifndef E_TRACK_HAL_OTA_STAGING_H
#define E_TRACK_HAL_OTA_STAGING_H

#include "OTA/ota_staging.h"

namespace HAL
{

enum OtaStagingOperation
{
    OTA_STAGING_OP_READ = 1,
    OTA_STAGING_OP_VERIFY = 2,
    OTA_STAGING_OP_ERASE = 3,
    OTA_STAGING_OP_PROGRAM = 4
};

enum OtaStagingErrorPhase
{
    OTA_STAGING_ERROR_NONE = 0,
    OTA_STAGING_ERROR_GUARD = 1,
    OTA_STAGING_ERROR_IO = 2,
    OTA_STAGING_ERROR_RESTORE = 3,
    OTA_STAGING_ERROR_VERIFY = 4
};

struct OtaStagingError
{
    uint32_t operation;
    uint32_t phase;
    uint32_t address;
    uint32_t length;
    int32_t result;
    uint32_t mismatch_address;
    uint8_t expected_byte;
    uint8_t observed_byte;
};

/* Read only between port calls on the owning thread. GetIo starts a new record.
 * mismatch_address is UINT32_MAX unless an actual differing byte was observed. */
bool OTA_StagingGetFirstError(OtaStagingError *error);
void OTA_StagingResetFirstError();
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
