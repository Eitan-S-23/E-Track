#ifndef E_TRACK_SYSTEM_FIRMWARE_INFO_H
#define E_TRACK_SYSTEM_FIRMWARE_INFO_H

#include "boot_fw_header.h"
#include <stdio.h>

namespace OtaUpdate
{
// Display identity comes from the running image, never a selected update package.
static inline bool FormatFirmwareInfo(const boot_image_reader_t* reader,
                                      const char* name, char* out, size_t size)
{
    if (name == NULL || out == NULL || size == 0u)
    {
        return false;
    }
    boot_fw_expectations_t expected;
    boot_fw_header_t header;
    boot_fw_default_expectations(&expected);
    const bool valid = boot_fw_header_validate(reader, &expected, &header) == BOOT_FW_OK;
    const int written = snprintf(out, size, "%s %s", name,
                                 valid ? header.version_name : "(unknown)");
    return valid && written >= 0 && (size_t)written < size;
}
}

#endif
