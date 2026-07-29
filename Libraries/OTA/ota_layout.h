#ifndef E_TRACK_OTA_LAYOUT_H
#define E_TRACK_OTA_LAYOUT_H

/* Derived from docs/ota-binary-contracts.md sections 0.4, 0.5, and 10. */
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
#define OTA_OVERLAY_WORKSPACE_LENGTH 0xA000
#define OTA_VTOR_EVIDENCE_SIZE 8
#define OTA_EXT_CANDIDATE     0x000000
#define OTA_EXT_BACKUP        0x100000
#define OTA_EXT_RECOVERY      0x200000
#define OTA_EXT_STAGING       0x300000
#define OTA_EXT_SELFTEST      0x7F0000
#define OTA_EXT_WINDOW_LENGTH 0x800000
#define OTA_EXT_SLOT_LENGTH   0x100000
#define OTA_EXT_STAGING_LENGTH 0x200000
#define OTA_EXT_SELFTEST_LENGTH 0x10000
#define OTA_SLOT_HEADER_SIZE  0x1000
#define OTA_ETU_MAX_LENGTH    0x180000

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

#if OTA_OVERLAY_WORKSPACE_LENGTH > OTA_OVERLAY_LENGTH
#error "The OTA workspace must fit inside the shared overlay region"
#endif

#if (OTA_EXT_CANDIDATE + OTA_EXT_SLOT_LENGTH) != OTA_EXT_BACKUP || \
    (OTA_EXT_BACKUP + OTA_EXT_SLOT_LENGTH) != OTA_EXT_RECOVERY || \
    (OTA_EXT_RECOVERY + OTA_EXT_SLOT_LENGTH) != OTA_EXT_STAGING
#error "External OTA slots must remain contiguous"
#endif

#if (OTA_EXT_STAGING + OTA_EXT_STAGING_LENGTH) > OTA_EXT_SELFTEST
#error "The staging slot must not overlap the QSPI self-test reservation"
#endif

#if (OTA_EXT_SELFTEST + OTA_EXT_SELFTEST_LENGTH) != OTA_EXT_WINDOW_LENGTH
#error "The QSPI self-test reservation must end at the contracted 8 MiB window"
#endif

#endif
