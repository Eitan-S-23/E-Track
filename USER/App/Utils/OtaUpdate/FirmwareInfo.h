#ifndef E_TRACK_SYSTEM_FIRMWARE_INFO_H
#define E_TRACK_SYSTEM_FIRMWARE_INFO_H

#include "boot_fw_header.h"
#include <stdio.h>

namespace OtaUpdate
{
// The version field uses the running image, without branding or a selected update.
static inline bool FormatFirmwareVersion(const boot_image_reader_t* reader,
                                        char* out, size_t size)
{
    if (out == NULL || size == 0u)
    {
        return false;
    }
    boot_fw_expectations_t expected;
    boot_fw_header_t header;
    boot_fw_default_expectations(&expected);
    const bool valid = boot_fw_header_validate(reader, &expected, &header) == BOOT_FW_OK;
    const int written = snprintf(out, size, "%s", valid ? header.version_name : "(unknown)");
    return valid && written >= 0 && (size_t)written < size;
}
}

#endif
