#ifndef E_TRACK_HAL_OTA_PACKAGE_H
#define E_TRACK_HAL_OTA_PACKAGE_H

#include "OTA/ota_package.h"

namespace HAL
{

bool OTA_OverlayAcquireLiveMap();
void OTA_OverlayReleaseLiveMap();
bool OTA_OverlayIsOtaOwned();

ota_package_result_t OTA_PackageApplyStaging(
    uint32_t package_len,
    uint32_t current_vcode,
    ota_package_info_t *out_info);

#if defined(P2_2_TEST_ENABLE)
bool OTA_PackageEvidenceRun();
#endif

}

#if defined(P2_2_TEST_ENABLE)
extern "C" void HAL_OTA_PackageEvidenceReady(void);
extern "C" void HAL_OTA_PackageEvidenceDone(void);
#endif

#endif
