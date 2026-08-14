#ifndef E_TRACK_OTA_UPDATE_H
#define E_TRACK_OTA_UPDATE_H

#include "OTA/ota_sd.h"
#include "lvgl/lvgl.h"

namespace OtaUpdate
{

class Session
{
public:
    Session();
    ~Session();

    bool InitializeDevice();
    ota_sd_result_t Inspect(const char* path,
                            ota_sd_package_info_t* outInfo);
    ota_sd_result_t Begin(const char* path);
    ota_sd_result_t Step(uint32_t byteBudget);
    bool Apply();
    /* P2-5：candidate 合成校验成功后，执行当前版自拷 backup + candidate/backup
     * 槽头(marker-last) + BCB=STAGED 原子提交并读回。成功返回 OTA_SD_OK。
     * 前置约束：仅当 Apply() 已成功绑定本次 candidate（candidateReady）时允许；
     * Begin/Close/Apply 失败会清除 candidate-ready，禁止仅凭 transfer.phase
     * ==COMPLETE 提交旧 candidate。 */
    ota_sd_result_t Stage();
    void Close();

    uint32_t CurrentVersionCode() const;
    const ota_sd_package_info_t& PackageInfo() const;
    uint8_t ProgressPercent() const;
    const char* LastError() const;

    /* P2-5：注入模拟器 BCB 状态（仅 _WIN32 宿主测试；生产走 HAL）。 */
#if defined(_WIN32)
    void SetSimulatorBcbState(uint8_t state);
#endif

    static void FormatVersion(uint32_t versionCode,
                              char* out, size_t outSize);

private:
    lv_fs_file_t file;
    bool fileOpen;
    bool deviceReady;
    bool confirmationValid;
    bool candidateReady;
    uint32_t candidateTargetVcode;
    uint32_t candidateImageLen;
    uint8_t candidateImageSha8[OTA_SD_BASE_SHA8_SIZE];
#if defined(_WIN32)
    uint8_t simulatorBcbState;
#endif
    ota_sd_device_t device;
    ota_sd_package_info_t packageInfo;
    ota_sd_transfer_t transfer;
    uint32_t currentImageLen;
    uint32_t filePosition;
    uint32_t confirmedPackageLen;
    uint8_t confirmedPackageSha256[OTA_SD_SHA256_SIZE];
    char selectedPath[256];
    char lastError[64];

    bool OpenSelectedFile(uint32_t* outSize);
    void CloseFile();
    void InvalidateConfirmation();
    void InvalidateCandidate();
    ota_sd_result_t RequireConfirmedBcb();  /* P2-5：任何擦写前的前置门 */
    void SetError(const char* stage, const char* detail);
    bool LoadStagingIo(ota_staging_io_t* io);

    static int ReadSelectedFile(void* ctx, uint32_t offset,
                                uint8_t* dst, uint32_t len);
    static int GetSelectedFileSize(void* ctx, uint32_t* outLen);
};

}

#endif
