#ifndef E_TRACK_HAL_OTA_PACKAGE_H
#define E_TRACK_HAL_OTA_PACKAGE_H

#include "OTA/ota_package.h"
#include "OTA/ota_patch.h"

namespace HAL
{

bool OTA_OverlayAcquireLiveMap();
void OTA_OverlayReleaseLiveMap();
bool OTA_OverlayIsOtaOwned();

ota_package_result_t OTA_PackageApplyStaging(
    uint32_t package_len,
    uint32_t current_vcode,
    ota_package_info_t *out_info);

/* 差分包：基版为当前运行 App 镜像（内部 flash XIP 直读），
 * base_image_len / base_image_sha8 由调用方从当前镜像 fw_header 取得。 */
ota_patch_result_t OTA_PatchApplyStaging(
    uint32_t package_len,
    uint32_t current_vcode,
    uint32_t base_image_len,
    const uint8_t base_image_sha8[OTA_PATCH_BASE_SHA8_SIZE],
    ota_patch_info_t *out_info);

#if defined(P2_2_TEST_ENABLE)
bool OTA_PackageEvidenceRun();
#endif

#if defined(P2_3_TEST_ENABLE)
bool OTA_PatchEvidenceRun();
#endif

}

#if defined(P2_2_TEST_ENABLE)
extern "C" void HAL_OTA_PackageEvidenceReady(void);
extern "C" void HAL_OTA_PackageEvidenceDone(void);
#endif

#if defined(P2_3_TEST_ENABLE)
extern "C" void HAL_OTA_PatchEvidenceReady(void);
extern "C" void HAL_OTA_PatchEvidenceDone(void);
#endif

#endif
