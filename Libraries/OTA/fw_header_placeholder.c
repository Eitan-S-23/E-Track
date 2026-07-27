#include <stdint.h>

#include "ota_layout.h"

#if defined(__CC_ARM)
#define OTA_FW_HEADER_ATTR __attribute__((used, section(".fw_header")))
#elif defined(__GNUC__)
#define OTA_FW_HEADER_ATTR __attribute__((used, section(".fw_header")))
#else
#error "Unsupported compiler for OTA firmware header placement"
#endif

#define OTA_FF_4  0xFF, 0xFF, 0xFF, 0xFF
#define OTA_FF_16 OTA_FF_4, OTA_FF_4, OTA_FF_4, OTA_FF_4
#define OTA_FF_32 OTA_FF_16, OTA_FF_16
#define OTA_FF_64 OTA_FF_32, OTA_FF_32

OTA_FW_HEADER_ATTR
const uint8_t g_ota_fw_header_placeholder[OTA_FW_HEADER_SIZE] = {
    OTA_FF_64, OTA_FF_32
};

typedef char ota_fw_header_size_must_match[
    (sizeof(g_ota_fw_header_placeholder) == OTA_FW_HEADER_SIZE) ? 1 : -1
];

#undef OTA_FF_64
#undef OTA_FF_32
#undef OTA_FF_16
#undef OTA_FF_4
#undef OTA_FW_HEADER_ATTR
