#ifndef E_TRACK_OTA_LAYOUT_H
#define E_TRACK_OTA_LAYOUT_H

/* Derived from docs/ota-binary-contracts.md sections 0.4 and 10. */
#define OTA_BOOT_ORIGIN       0x08000000
#define OTA_BOOT_LENGTH       0x10000
#define OTA_APP_ORIGIN        0x08010000
#define OTA_APP_LENGTH        0xF0000
#define OTA_FW_HEADER_OFFSET  0x400
#define OTA_FW_HEADER_SIZE    96
#define OTA_VECTOR_MAX        0x400
#define OTA_RAM_ORIGIN        0x20000000
#define OTA_RAM_LENGTH        0x58000
#define OTA_OVERLAY_ORIGIN    0x20058000
#define OTA_OVERLAY_LENGTH    0x28000
#define OTA_VTOR_EVIDENCE_SIZE 8

#define OTA_APP_VECTOR_OFFSET (OTA_APP_ORIGIN - OTA_BOOT_ORIGIN)

#if (OTA_BOOT_ORIGIN + OTA_BOOT_LENGTH) != OTA_APP_ORIGIN
#error "Boot and App flash regions must be contiguous"
#endif

#if OTA_FW_HEADER_OFFSET != OTA_VECTOR_MAX
#error "The firmware header must start immediately after the vector budget"
#endif

#if (OTA_RAM_ORIGIN + OTA_RAM_LENGTH) != OTA_OVERLAY_ORIGIN
#error "Main RAM and OTA overlay regions must be contiguous"
#endif

#endif
