#ifndef E_TRACK_BOOT_SLOT_H
#define E_TRACK_BOOT_SLOT_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define BOOT_SLOT_HEADER_SIZE 32u

typedef enum
{
    BOOT_SLOT_CANDIDATE = 1,
    BOOT_SLOT_BACKUP = 2,
    BOOT_SLOT_STAGING = 3,
    BOOT_SLOT_RECOVERY = 4
} boot_slot_type_t;

typedef struct
{
    uint8_t slot_type;
    uint32_t payload_len;
    uint32_t payload_crc32;
    uint32_t version_code;
    uint8_t sha8[8];
} boot_slot_header_t;

typedef enum
{
    BOOT_SLOT_OK = 0,
    BOOT_SLOT_ERR_ARGUMENT,
    BOOT_SLOT_ERR_MAGIC,
    BOOT_SLOT_ERR_COMMIT,
    BOOT_SLOT_ERR_TYPE,
    BOOT_SLOT_ERR_PADDING,
    BOOT_SLOT_ERR_LENGTH
} boot_slot_result_t;

boot_slot_result_t boot_slot_header_parse(const uint8_t raw[BOOT_SLOT_HEADER_SIZE],
                                          boot_slot_type_t expected_type,
                                          boot_slot_header_t *out);
const char *boot_slot_result_name(boot_slot_result_t result);

#ifdef __cplusplus
}
#endif

#endif
