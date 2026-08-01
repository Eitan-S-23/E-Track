#include "App/Utils/OtaUpdate/OtaUpdate.h"

#include <algorithm>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <new>
#include <string>
#include <vector>

namespace
{
    const char* kSelectedPath = "/firmware.etu";

    struct BackingFile
    {
        std::vector<uint8_t> bytes;
        uint32_t visibleSize;
        bool available;
        uint32_t openCount;
        uint32_t closeCount;
    };

    struct CachedHandle
    {
        std::vector<uint8_t> bytes;
        uint32_t cachedSize;
        uint32_t position;
    };

    BackingFile backingFile;

    bool LoadFile(const char* path, std::vector<uint8_t>* out)
    {
        std::ifstream file(path, std::ios::binary | std::ios::ate);
        std::streamsize size;

        if (out == nullptr || !file)
        {
            return false;
        }
        size = file.tellg();
        if (size <= 0 || !file.seekg(0, std::ios::beg))
        {
            return false;
        }
        out->resize((size_t)size);
        return file.read((char*)out->data(), size).good();
    }

    void SetBackingFile(const std::vector<uint8_t>& bytes,
                        uint32_t visibleSize)
    {
        backingFile.bytes = bytes;
        backingFile.visibleSize = visibleSize;
        backingFile.available = true;
    }

    ota_sd_result_t RunToSecondPass(OtaUpdate::Session* session)
    {
        ota_sd_result_t result = OTA_SD_IN_PROGRESS;
        uint32_t guard = 0u;

        while (result == OTA_SD_IN_PROGRESS &&
               session->ProgressPercent() < 45u && guard++ < 100000u)
        {
            result = session->Step(256u);
        }
        return result;
    }

    ota_sd_result_t RunUntilDone(OtaUpdate::Session* session)
    {
        ota_sd_result_t result = OTA_SD_IN_PROGRESS;
        uint32_t guard = 0u;

        while (result == OTA_SD_IN_PROGRESS && guard++ < 100000u)
        {
            result = session->Step(256u);
        }
        return result;
    }

    bool PrepareTransfer(OtaUpdate::Session* session,
                         const std::vector<uint8_t>& original)
    {
        ota_sd_package_info_t info;

        SetBackingFile(original, (uint32_t)original.size());
        return session->InitializeDevice() &&
               session->Inspect(kSelectedPath, &info) == OTA_SD_OK &&
               session->Begin(kSelectedPath) == OTA_SD_OK;
    }

    int RunConfirmReplacement(const std::vector<uint8_t>& original,
                              const std::vector<uint8_t>& replacement)
    {
        OtaUpdate::Session session;
        ota_sd_package_info_t info;
        ota_sd_result_t result;

        SetBackingFile(original, (uint32_t)original.size());
        if (!session.InitializeDevice() ||
            session.Inspect(kSelectedPath, &info) != OTA_SD_OK)
        {
            return 10;
        }
        SetBackingFile(replacement, (uint32_t)replacement.size());
        result = session.Begin(kSelectedPath);
        std::printf("CONFIRM_REPLACE result=%s opens=%lu closes=%lu\n",
                    ota_sd_result_name(result),
                    (unsigned long)backingFile.openCount,
                    (unsigned long)backingFile.closeCount);
        return result == OTA_SD_ERR_FILE_CHANGED ? 0 : 11;
    }

    int RunLengthChange(const std::vector<uint8_t>& original, bool append)
    {
        OtaUpdate::Session session;
        ota_sd_result_t result;

        if (!PrepareTransfer(&session, original))
        {
            return 20;
        }
        result = RunToSecondPass(&session);
        if (result != OTA_SD_IN_PROGRESS || session.ProgressPercent() < 45u)
        {
            return 21;
        }
        if (append)
        {
            backingFile.bytes.push_back(0x5Au);
            backingFile.visibleSize = (uint32_t)original.size() + 1u;
        }
        else
        {
            backingFile.visibleSize = (uint32_t)original.size() - 1u;
        }
        result = RunUntilDone(&session);
        std::printf("%s result=%s error=%s opens=%lu closes=%lu\n",
                    append ? "APPEND_1B" : "TRUNCATE_1B",
                    ota_sd_result_name(result), session.LastError(),
                    (unsigned long)backingFile.openCount,
                    (unsigned long)backingFile.closeCount);
        return result == OTA_SD_ERR_FILE_CHANGED &&
                       std::strcmp(session.LastError(),
                                   "stage:file_changed") == 0
                   ? 0
                   : 22;
    }

    int RunSecondPassReplacement(const std::vector<uint8_t>& original,
                                 const std::vector<uint8_t>& replacement)
    {
        OtaUpdate::Session session;
        ota_sd_result_t result;

        if (!PrepareTransfer(&session, original))
        {
            return 30;
        }
        result = RunToSecondPass(&session);
        if (result != OTA_SD_IN_PROGRESS || session.ProgressPercent() < 45u)
        {
            return 31;
        }
        SetBackingFile(replacement, (uint32_t)replacement.size());
        result = RunUntilDone(&session);
        std::printf("SECOND_PASS_REPLACE result=%s error=%s opens=%lu closes=%lu\n",
                    ota_sd_result_name(result), session.LastError(),
                    (unsigned long)backingFile.openCount,
                    (unsigned long)backingFile.closeCount);
        return result == OTA_SD_ERR_FILE_CHANGED ? 0 : 32;
    }

    int RunUnavailableAfterFirstPass(const std::vector<uint8_t>& original)
    {
        OtaUpdate::Session session;
        ota_sd_result_t result;

        if (!PrepareTransfer(&session, original))
        {
            return 40;
        }
        result = RunToSecondPass(&session);
        if (result != OTA_SD_IN_PROGRESS || session.ProgressPercent() < 45u)
        {
            return 41;
        }
        backingFile.available = false;
        result = RunUntilDone(&session);
        std::printf("UNAVAILABLE result=%s error=%s opens=%lu closes=%lu\n",
                    ota_sd_result_name(result), session.LastError(),
                    (unsigned long)backingFile.openCount,
                    (unsigned long)backingFile.closeCount);
        return result == OTA_SD_ERR_READ &&
                       std::strcmp(session.LastError(), "stage:read") == 0 &&
                       backingFile.openCount == backingFile.closeCount
                   ? 0
                   : 42;
    }
}

extern "C" lv_fs_res_t lv_fs_open(lv_fs_file_t* file, const char* path,
                                    lv_fs_mode_t mode)
{
    CachedHandle* handle;

    if (file == nullptr || path == nullptr ||
        std::strcmp(path, kSelectedPath) != 0 || mode != LV_FS_MODE_RD ||
        !backingFile.available ||
        backingFile.visibleSize > backingFile.bytes.size())
    {
        return LV_FS_RES_NOT_EX;
    }
    handle = new (std::nothrow) CachedHandle;
    if (handle == nullptr)
    {
        return LV_FS_RES_OUT_OF_MEM;
    }
    handle->bytes.assign(backingFile.bytes.begin(),
                         backingFile.bytes.begin() + backingFile.visibleSize);
    handle->cachedSize = backingFile.visibleSize;
    handle->position = 0u;
    file->file_d = handle;
    ++backingFile.openCount;
    return LV_FS_RES_OK;
}

extern "C" lv_fs_res_t lv_fs_close(lv_fs_file_t* file)
{
    if (file == nullptr || file->file_d == nullptr)
    {
        return LV_FS_RES_INV_PARAM;
    }
    delete (CachedHandle*)file->file_d;
    file->file_d = nullptr;
    ++backingFile.closeCount;
    return LV_FS_RES_OK;
}

extern "C" lv_fs_res_t lv_fs_read(lv_fs_file_t* file, void* buf,
                                    uint32_t btr, uint32_t* br)
{
    CachedHandle* handle;
    uint32_t available;
    uint32_t take;

    if (file == nullptr || file->file_d == nullptr || buf == nullptr ||
        br == nullptr)
    {
        return LV_FS_RES_INV_PARAM;
    }
    handle = (CachedHandle*)file->file_d;
    available = handle->position < handle->cachedSize
                    ? handle->cachedSize - handle->position
                    : 0u;
    take = std::min(btr, available);
    if (take != 0u)
    {
        std::memcpy(buf, handle->bytes.data() + handle->position, take);
    }
    handle->position += take;
    *br = take;
    return LV_FS_RES_OK;
}

extern "C" lv_fs_res_t lv_fs_seek(lv_fs_file_t* file, uint32_t pos,
                                    lv_fs_whence_t whence)
{
    CachedHandle* handle;
    uint64_t target;

    if (file == nullptr || file->file_d == nullptr)
    {
        return LV_FS_RES_INV_PARAM;
    }
    handle = (CachedHandle*)file->file_d;
    if (whence == LV_FS_SEEK_SET)
    {
        target = pos;
    }
    else if (whence == LV_FS_SEEK_CUR)
    {
        target = (uint64_t)handle->position + pos;
    }
    else if (whence == LV_FS_SEEK_END)
    {
        target = (uint64_t)handle->cachedSize + pos;
    }
    else
    {
        return LV_FS_RES_INV_PARAM;
    }
    if (target > handle->cachedSize)
    {
        return LV_FS_RES_INV_PARAM;
    }
    handle->position = (uint32_t)target;
    return LV_FS_RES_OK;
}

extern "C" lv_fs_res_t lv_fs_tell(lv_fs_file_t* file, uint32_t* pos)
{
    if (file == nullptr || file->file_d == nullptr || pos == nullptr)
    {
        return LV_FS_RES_INV_PARAM;
    }
    *pos = ((CachedHandle*)file->file_d)->position;
    return LV_FS_RES_OK;
}

int main(int argc, char** argv)
{
    std::vector<uint8_t> original;
    std::vector<uint8_t> replacement;
    std::string scenario;

    if (argc != 4 || !LoadFile(argv[2], &original) ||
        !LoadFile(argv[3], &replacement) ||
        original.size() != replacement.size())
    {
        std::fprintf(stderr, "fixture setup failed\n");
        return 2;
    }
    scenario = argv[1];
    backingFile.openCount = 0u;
    backingFile.closeCount = 0u;
    if (scenario == "confirm-replace")
    {
        return RunConfirmReplacement(original, replacement);
    }
    if (scenario == "append")
    {
        return RunLengthChange(original, true);
    }
    if (scenario == "truncate")
    {
        return RunLengthChange(original, false);
    }
    if (scenario == "second-pass-replace")
    {
        return RunSecondPassReplacement(original, replacement);
    }
    if (scenario == "unavailable")
    {
        return RunUnavailableAfterFirstPass(original);
    }
    std::fprintf(stderr, "unknown scenario\n");
    return 3;
}
