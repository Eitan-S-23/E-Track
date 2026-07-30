#include "OTA/ota_keys.h"

#if defined(OTA_AES_KEY_1_WORD0) || defined(OTA_AES_KEY_1_WORD1) || \
    defined(OTA_AES_KEY_1_WORD2) || defined(OTA_AES_KEY_1_WORD3)
#if !defined(OTA_AES_KEY_1_WORD0) || !defined(OTA_AES_KEY_1_WORD1) || \
    !defined(OTA_AES_KEY_1_WORD2) || !defined(OTA_AES_KEY_1_WORD3)
#error "Define all four OTA_AES_KEY_1_WORDx values or none of them"
#endif
#define OTA_KEY_1_IS_DEVELOPMENT 0
#else
#define OTA_AES_KEY_1_WORD0 0x2B7E1516u
#define OTA_AES_KEY_1_WORD1 0x28AED2A6u
#define OTA_AES_KEY_1_WORD2 0xABF71588u
#define OTA_AES_KEY_1_WORD3 0x09CF4F3Cu
#define OTA_KEY_1_IS_DEVELOPMENT 1
#endif

static void put_be32(uint8_t *dst, uint32_t value)
{
    dst[0] = (uint8_t)(value >> 24);
    dst[1] = (uint8_t)(value >> 16);
    dst[2] = (uint8_t)(value >> 8);
    dst[3] = (uint8_t)value;
}

int ota_keys_get_aes128(uint32_t key_id,
                        uint8_t key[OTA_AES128_KEY_SIZE])
{
    if (key_id != 1u || key == 0)
    {
        return -1;
    }

    put_be32(key, OTA_AES_KEY_1_WORD0);
    put_be32(key + 4u, OTA_AES_KEY_1_WORD1);
    put_be32(key + 8u, OTA_AES_KEY_1_WORD2);
    put_be32(key + 12u, OTA_AES_KEY_1_WORD3);
    return 0;
}

int ota_keys_uses_development_key(void)
{
    return OTA_KEY_1_IS_DEVELOPMENT;
}
