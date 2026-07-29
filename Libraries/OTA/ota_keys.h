#ifndef E_TRACK_OTA_KEYS_H
#define E_TRACK_OTA_KEYS_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define OTA_AES128_KEY_SIZE 16u

int ota_keys_get_aes128(uint32_t key_id,
                        uint8_t key[OTA_AES128_KEY_SIZE]);
int ota_keys_uses_development_key(void);

#ifdef __cplusplus
}
#endif

#endif
