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
    void Close();

    uint32_t CurrentVersionCode() const;
    const ota_sd_package_info_t& PackageInfo() const;
    uint8_t ProgressPercent() const;
    const char* LastError() const;

    static void FormatVersion(uint32_t versionCode,
                              char* out, size_t outSize);

private:
    lv_fs_file_t file;
    bool fileOpen;
    bool deviceReady;
    bool confirmationValid;
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
    void SetError(const char* stage, const char* detail);
    bool LoadStagingIo(ota_staging_io_t* io);

    static int ReadSelectedFile(void* ctx, uint32_t offset,
                                uint8_t* dst, uint32_t len);
    static int GetSelectedFileSize(void* ctx, uint32_t* outLen);
};

}

#endif
