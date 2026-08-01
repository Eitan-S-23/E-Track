#include "OtaUpdate.h"

#include "Version.h"

#if defined(OTA_TARGET_APP)
#include "HAL/HAL_OTA_Package.h"
#include "HAL/HAL_OTA_Staging.h"
#include "boot_fw_header.h"
#endif

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !defined(OTA_TARGET_APP) && !defined(_WIN32)
#error "OtaUpdate is only valid for the OTA App target or simulator"
#endif

namespace
{
    bool PackageInfoMatches(const ota_sd_package_info_t& left,
                            const ota_sd_package_info_t& right)
    {
        return left.kind == right.kind &&
               left.flags == right.flags &&
               left.package_len == right.package_len &&
               left.payload_len == right.payload_len &&
               left.payload_crc32 == right.payload_crc32 &&
               left.target_vcode == right.target_vcode &&
               left.base_vcode == right.base_vcode &&
               memcmp(left.base_image_sha8, right.base_image_sha8,
                      OTA_SD_BASE_SHA8_SIZE) == 0;
    }

#if defined(_WIN32)
    struct SimulatorStaging
    {
        uint8_t* bytes;
        bool initialized;
    };

    SimulatorStaging simulatorStaging = { nullptr, false };

    bool SimulatorStagingEnsure()
    {
        if (simulatorStaging.initialized)
        {
            return simulatorStaging.bytes != nullptr;
        }
        simulatorStaging.initialized = true;
        simulatorStaging.bytes =
            (uint8_t*)malloc((size_t)OTA_EXT_STAGING_LENGTH);
        if (simulatorStaging.bytes != nullptr)
        {
            memset(simulatorStaging.bytes, 0xFF,
                   (size_t)OTA_EXT_STAGING_LENGTH);
        }
        return simulatorStaging.bytes != nullptr;
    }

    bool SimulatorRangeOk(uint32_t address, uint32_t len)
    {
        return address >= OTA_EXT_STAGING &&
               len <= OTA_EXT_STAGING_LENGTH &&
               address - OTA_EXT_STAGING <=
                   OTA_EXT_STAGING_LENGTH - len;
    }

    int SimulatorRead(void* ctx, uint32_t address,
                      uint8_t* dst, uint32_t len)
    {
        (void)ctx;
        if (dst == nullptr || !SimulatorStagingEnsure() ||
            !SimulatorRangeOk(address, len))
        {
            return -1;
        }
        memcpy(dst,
               simulatorStaging.bytes + address - OTA_EXT_STAGING,
               len);
        return 0;
    }

    int SimulatorErase(void* ctx, uint32_t address)
    {
        (void)ctx;
        if (!SimulatorStagingEnsure() ||
            !SimulatorRangeOk(address, OTA_STAGING_BLOCK_SIZE) ||
            (address & (OTA_STAGING_BLOCK_SIZE - 1u)) != 0u)
        {
            return -1;
        }
        memset(simulatorStaging.bytes + address - OTA_EXT_STAGING,
               0xFF, OTA_STAGING_BLOCK_SIZE);
        return 0;
    }

    int SimulatorProgram(void* ctx, uint32_t address,
                         const uint8_t* src, uint32_t len)
    {
        uint8_t* dst;
        uint32_t index;

        (void)ctx;
        if (src == nullptr || len == 0u || !SimulatorStagingEnsure() ||
            !SimulatorRangeOk(address, len))
        {
            return -1;
        }
        dst = simulatorStaging.bytes + address - OTA_EXT_STAGING;
        for (index = 0u; index < len; ++index)
        {
            if ((dst[index] & src[index]) != src[index])
            {
                return -1;
            }
        }
        for (index = 0u; index < len; ++index)
        {
            dst[index] &= src[index];
        }
        return 0;
    }

    uint32_t ParseSimulatorVersion()
    {
        const char* cursor = VERSION_SOFTWARE;
        uint32_t parts[3] = { 0u, 0u, 0u };
        uint32_t index;

        while (*cursor != '\0' && (*cursor < '0' || *cursor > '9'))
        {
            ++cursor;
        }
        for (index = 0u; index < 3u && *cursor != '\0'; ++index)
        {
            uint32_t value = 0u;
            while (*cursor >= '0' && *cursor <= '9')
            {
                value = value * 10u + (uint32_t)(*cursor - '0');
                ++cursor;
            }
            parts[index] = value;
            if (*cursor != '.')
            {
                break;
            }
            ++cursor;
        }
        return parts[0] * 10000u + parts[1] * 100u + parts[2];
    }
#else
    int CurrentImageRead(void* ctx, uint32_t offset,
                         uint8_t* dst, size_t len)
    {
        (void)ctx;
        if (dst == nullptr || offset > OTA_APP_LENGTH ||
            len > (size_t)(OTA_APP_LENGTH - offset))
        {
            return -1;
        }
        memcpy(dst,
               (const void*)(uintptr_t)(OTA_APP_ORIGIN + offset),
               len);
        return 0;
    }

    bool CurrentImageRawSha8(uint32_t imageLen,
                             uint8_t out[OTA_SD_BASE_SHA8_SIZE])
    {
        boot_sha256_ctx_t sha;
        uint8_t block[256];
        uint8_t digest[32];
        uint32_t offset = 0u;

        if (imageLen == 0u || imageLen > OTA_APP_LENGTH)
        {
            return false;
        }
        boot_sha256_init(&sha);
        while (offset < imageLen)
        {
            uint32_t take = imageLen - offset;
            if (take > sizeof(block))
            {
                take = sizeof(block);
            }
            if (CurrentImageRead(nullptr, offset, block, take) != 0)
            {
                return false;
            }
            boot_sha256_update(&sha, block, take);
            offset += take;
        }
        boot_sha256_final(&sha, digest);
        memcpy(out, digest, OTA_SD_BASE_SHA8_SIZE);
        return true;
    }
#endif
}

using namespace OtaUpdate;

Session::Session()
    : fileOpen(false),
      deviceReady(false),
      confirmationValid(false),
      currentImageLen(0u),
      filePosition(0u),
      confirmedPackageLen(0u)
{
    memset(&file, 0, sizeof(file));
    memset(&device, 0, sizeof(device));
    memset(&packageInfo, 0, sizeof(packageInfo));
    memset(&transfer, 0, sizeof(transfer));
    memset(confirmedPackageSha256, 0, sizeof(confirmedPackageSha256));
    selectedPath[0] = '\0';
    lastError[0] = '\0';
}

Session::~Session()
{
    Close();
}

bool Session::InitializeDevice()
{
    Close();
    deviceReady = false;
    memset(&device, 0, sizeof(device));
    device.hardware_rev = 1u;
    device.layout_id = 1u;
    device.boot_version = 1u;

#if defined(_WIN32)
    static const uint8_t toyOldSha8[OTA_SD_BASE_SHA8_SIZE] = {
        0x30, 0x81, 0xFA, 0x0A, 0xFC, 0x5B, 0xB2, 0xF3
    };

    if (!SimulatorStagingEnsure())
    {
        SetError("device", "sim_staging");
        return false;
    }
    device.current_vcode = ParseSimulatorVersion();
    currentImageLen = 4096u;
    memcpy(device.base_image_sha8, toyOldSha8, sizeof(toyOldSha8));
#else
    boot_image_reader_t reader;
    boot_fw_expectations_t expectations;
    boot_fw_header_t header;
    boot_fw_result_t result;

    reader.read = CurrentImageRead;
    reader.ctx = nullptr;
    boot_fw_default_expectations(&expectations);
    result = boot_fw_header_validate(&reader, &expectations, &header);
    if (result != BOOT_FW_OK)
    {
        SetError("device", boot_fw_result_name(result));
        return false;
    }
    device.current_vcode = header.version_code;
    currentImageLen = header.image_len;
    if (!CurrentImageRawSha8(currentImageLen, device.base_image_sha8))
    {
        SetError("device", "raw_sha");
        return false;
    }
#endif

    deviceReady = true;
    lastError[0] = '\0';
    return true;
}

ota_sd_result_t Session::Inspect(const char* path,
                                 ota_sd_package_info_t* outInfo)
{
    ota_sd_reader_t reader;
    ota_sd_package_info_t inspectedInfo;
    uint8_t inspectedSha256[OTA_SD_SHA256_SIZE];
    ota_sd_result_t result;
    uint32_t size;

    if (!deviceReady || path == nullptr || path[0] == '\0' ||
        strlen(path) >= sizeof(selectedPath))
    {
        SetError("inspect", "argument");
        return OTA_SD_ERR_ARGUMENT;
    }
    InvalidateConfirmation();
    CloseFile();
    strcpy(selectedPath, path);
    if (!OpenSelectedFile(&size))
    {
        return OTA_SD_ERR_READ;
    }
    if (size < OTA_SD_HEADER_SIZE || size > OTA_ETU_MAX_LENGTH)
    {
        SetError("inspect", "package_length");
        CloseFile();
        return OTA_SD_ERR_PACKAGE_LENGTH;
    }
    reader.ctx = this;
    reader.read = ReadSelectedFile;
    reader.size = GetSelectedFileSize;
    memset(&inspectedInfo, 0, sizeof(inspectedInfo));
    result = ota_sd_inspect_reader(&reader, size, &device, &inspectedInfo);
    if (result == OTA_SD_OK)
    {
        result = ota_sd_hash_reader(&reader, size, inspectedSha256);
    }
    CloseFile();
    if (result != OTA_SD_OK)
    {
        SetError("inspect", ota_sd_result_name(result));
        return result;
    }
    packageInfo = inspectedInfo;
    confirmedPackageLen = size;
    memcpy(confirmedPackageSha256, inspectedSha256,
           sizeof(confirmedPackageSha256));
    confirmationValid = true;
    if (outInfo != nullptr)
    {
        *outInfo = packageInfo;
    }
    lastError[0] = '\0';
    return OTA_SD_OK;
}

ota_sd_result_t Session::Begin(const char* path)
{
    ota_sd_reader_t reader;
    ota_staging_io_t stagingIo;
    ota_sd_result_t result;
    uint8_t confirmedSha256[OTA_SD_SHA256_SIZE];
    uint32_t confirmedSize;
    uint32_t size;

    if (!deviceReady || path == nullptr || path[0] == '\0' ||
        strlen(path) >= sizeof(selectedPath))
    {
        SetError("begin", "argument");
        return OTA_SD_ERR_ARGUMENT;
    }
    if (!confirmationValid || strcmp(path, selectedPath) != 0)
    {
        SetError("begin", "confirmation");
        return OTA_SD_ERR_FILE_CHANGED;
    }
    confirmedSize = confirmedPackageLen;
    memcpy(confirmedSha256, confirmedPackageSha256,
           sizeof(confirmedSha256));
    confirmationValid = false;
    CloseFile();
    if (!OpenSelectedFile(&size))
    {
        CloseFile();
        return OTA_SD_ERR_READ;
    }
    if (size != confirmedSize)
    {
        SetError("begin", "file_changed");
        CloseFile();
        return OTA_SD_ERR_FILE_CHANGED;
    }
    if (!LoadStagingIo(&stagingIo))
    {
        CloseFile();
        return OTA_SD_ERR_STAGING;
    }
    reader.ctx = this;
    reader.read = ReadSelectedFile;
    reader.size = GetSelectedFileSize;
    result = ota_sd_transfer_begin(&transfer, &reader, &stagingIo,
                                   size, confirmedSha256, &device);
    if (result != OTA_SD_OK)
    {
        SetError("begin", ota_sd_result_name(result));
        CloseFile();
        return result;
    }
    if (!PackageInfoMatches(packageInfo, transfer.info))
    {
        memset(&transfer, 0, sizeof(transfer));
        SetError("begin", "file_changed");
        CloseFile();
        return OTA_SD_ERR_FILE_CHANGED;
    }
    InvalidateConfirmation();
    lastError[0] = '\0';
    return OTA_SD_OK;
}

ota_sd_result_t Session::Step(uint32_t byteBudget)
{
    ota_sd_result_t result = ota_sd_transfer_step(&transfer, byteBudget);

    if (result < 0)
    {
        SetError("stage", ota_sd_result_name(result));
        CloseFile();
    }
    else if (result == OTA_SD_STAGED)
    {
        CloseFile();
    }
    return result;
}

bool Session::Apply()
{
    CloseFile();
    if (transfer.phase != OTA_SD_PHASE_COMPLETE)
    {
        SetError("apply", "not_staged");
        return false;
    }

#if defined(_WIN32)
    lastError[0] = '\0';
    return true;
#else
    if (packageInfo.kind == OTA_SD_KIND_FULL)
    {
        ota_package_info_t info;
        ota_package_result_t result;

        memset(&info, 0, sizeof(info));
        result = HAL::OTA_PackageApplyStaging(
            packageInfo.package_len, device.current_vcode, &info);
        if (result != OTA_PACKAGE_OK ||
            info.target_vcode != packageInfo.target_vcode)
        {
            SetError("full", ota_package_result_name(result));
            return false;
        }
    }
    else if (packageInfo.kind == OTA_SD_KIND_PATCH)
    {
        ota_patch_info_t info;
        ota_patch_result_t result;

        memset(&info, 0, sizeof(info));
        result = HAL::OTA_PatchApplyStaging(
            packageInfo.package_len, device.current_vcode,
            currentImageLen, device.base_image_sha8, &info);
        if (result != OTA_PATCH_OK ||
            info.target_vcode != packageInfo.target_vcode)
        {
            SetError("patch", ota_patch_result_name(result));
            return false;
        }
    }
    else
    {
        SetError("apply", "kind");
        return false;
    }
    lastError[0] = '\0';
    return true;
#endif
}

void Session::Close()
{
    CloseFile();
    memset(&transfer, 0, sizeof(transfer));
    InvalidateConfirmation();
    selectedPath[0] = '\0';
}

uint32_t Session::CurrentVersionCode() const
{
    return device.current_vcode;
}

const ota_sd_package_info_t& Session::PackageInfo() const
{
    return packageInfo;
}

uint8_t Session::ProgressPercent() const
{
    return ota_sd_transfer_percent(&transfer);
}

const char* Session::LastError() const
{
    return lastError;
}

void Session::FormatVersion(uint32_t versionCode,
                            char* out, size_t outSize)
{
    uint32_t major;
    uint32_t minor;
    uint32_t patch;

    if (out == nullptr || outSize == 0u)
    {
        return;
    }
    major = versionCode / 10000u;
    minor = (versionCode / 100u) % 100u;
    patch = versionCode % 100u;
    snprintf(out, outSize, "%lu.%lu.%lu",
             (unsigned long)major,
             (unsigned long)minor,
             (unsigned long)patch);
    out[outSize - 1u] = '\0';
}

bool Session::OpenSelectedFile(uint32_t* outSize)
{
    uint32_t size = 0u;

    if (outSize == nullptr || selectedPath[0] == '\0' ||
        lv_fs_open(&file, selectedPath, LV_FS_MODE_RD) != LV_FS_RES_OK)
    {
        SetError("file", "open");
        return false;
    }
    fileOpen = true;
    filePosition = 0u;
    if (lv_fs_seek(&file, 0u, LV_FS_SEEK_END) != LV_FS_RES_OK ||
        lv_fs_tell(&file, &size) != LV_FS_RES_OK ||
        lv_fs_seek(&file, 0u, LV_FS_SEEK_SET) != LV_FS_RES_OK)
    {
        SetError("file", "size");
        CloseFile();
        return false;
    }
    *outSize = size;
    filePosition = 0u;
    return true;
}

void Session::InvalidateConfirmation()
{
    confirmationValid = false;
    confirmedPackageLen = 0u;
    memset(confirmedPackageSha256, 0, sizeof(confirmedPackageSha256));
}

void Session::CloseFile()
{
    if (fileOpen)
    {
        lv_fs_close(&file);
        fileOpen = false;
        filePosition = 0u;
    }
}

void Session::SetError(const char* stage, const char* detail)
{
    snprintf(lastError, sizeof(lastError), "%s:%s",
             stage != nullptr ? stage : "ota",
             detail != nullptr ? detail : "unknown");
    lastError[sizeof(lastError) - 1u] = '\0';
}

bool Session::LoadStagingIo(ota_staging_io_t* io)
{
    if (io == nullptr)
    {
        SetError("staging", "argument");
        return false;
    }
    memset(io, 0, sizeof(*io));
#if defined(_WIN32)
    if (!SimulatorStagingEnsure())
    {
        SetError("staging", "memory");
        return false;
    }
    io->read = SimulatorRead;
    io->erase_4k = SimulatorErase;
    io->program = SimulatorProgram;
#else
    HAL::OTA_StagingGetIo(io);
#endif
    return io->read != nullptr && io->erase_4k != nullptr &&
           io->program != nullptr;
}

int Session::ReadSelectedFile(void* ctx, uint32_t offset,
                              uint8_t* dst, uint32_t len)
{
    Session* session = (Session*)ctx;
    uint32_t bytesRead = 0u;

    if (session == nullptr || !session->fileOpen || dst == nullptr)
    {
        return -1;
    }
    if (session->filePosition != offset &&
        lv_fs_seek(&session->file, offset, LV_FS_SEEK_SET) != LV_FS_RES_OK)
    {
        return -1;
    }
    if (lv_fs_read(&session->file, dst, len, &bytesRead) != LV_FS_RES_OK ||
        bytesRead != len)
    {
        return -1;
    }
    session->filePosition = offset + len;
    return 0;
}

int Session::GetSelectedFileSize(void* ctx, uint32_t* outLen)
{
    Session* session = (Session*)ctx;
    uint32_t restoreOffset;
    uint32_t size = 0u;

    if (session == nullptr || !session->fileOpen || outLen == nullptr)
    {
        return -1;
    }
    restoreOffset = session->filePosition;
    // SdFat caches m_fileSize per handle, so reopen to reread the directory.
    session->CloseFile();
    if (!session->OpenSelectedFile(&size))
    {
        return -1;
    }
    if (restoreOffset > size)
    {
        restoreOffset = size;
    }
    if (restoreOffset != 0u &&
        lv_fs_seek(&session->file, restoreOffset, LV_FS_SEEK_SET) !=
            LV_FS_RES_OK)
    {
        session->SetError("file", "seek");
        session->CloseFile();
        return -1;
    }
    session->filePosition = restoreOffset;
    *outLen = size;
    return 0;
}
