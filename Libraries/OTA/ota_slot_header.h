#ifndef E_TRACK_OTA_SLOT_HEADER_H
#define E_TRACK_OTA_SLOT_HEADER_H

/*
 * 外部槽头（ETSL）的 App 侧写端与读端自检。
 *
 * 冻结契约唯一依据：docs/ota-binary-contracts.md v1.1 §4.1（ETSL 32B）/ §4.3
 * （marker-last）。boot 读端（boot/src/boot_slot.c）保持不变；本头只服务
 * App 侧 backup/STAGED 提交（P2-5）与宿主测试。
 */

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define OTA_SLOT_HEADER_BYTES 32u

enum
{
    OTA_SLOT_TYPE_CANDIDATE = 1,
    OTA_SLOT_TYPE_BACKUP    = 2,
    OTA_SLOT_TYPE_STAGING   = 3,
    OTA_SLOT_TYPE_RECOVERY  = 4
};

/* 契约 §4.1：commit_marker 冻结值 u32 0x434F4D54（片上字节 54 4D 4F 43）；
 * 擦除态 0xFFFFFFFF = 未提交。 */
#define OTA_SLOT_MARKER_COMMIT 0x434F4D54u
#define OTA_SLOT_MARKER_ERASED 0xFFFFFFFFu

typedef struct ota_slot_header_t
{
    uint8_t  slot_type;      /* OTA_SLOT_TYPE_* */
    uint32_t payload_len;    /* 槽内 payload 字节数（本体位于槽起 + SLOT_HEADER_SIZE） */
    uint32_t payload_crc32;  /* payload 全镜像 CRC32-IEEE */
    uint32_t version_code;   /* 槽内镜像版本码 */
    uint8_t  sha8[8];        /* 镜像 SHA-256 前 8B */
    int      committed;      /* parse 后：commit_marker==MARKER_COMMIT 为 1 */
} ota_slot_header_t;

/* 按契约 §4.1 逐字段小端手填 32B；本函数把 off 4..27 填好，off 28..31 保持
 * 擦除态 0xFF（marker 待提交）。slice 内存 32B。 */
void ota_slot_header_serialize_partial(
    const ota_slot_header_t *slot,
    uint8_t out[OTA_SLOT_HEADER_BYTES]);

/* 只在内存中把 off 28..31 置为 commit_marker 值。真正“最后单独写”由调用方
 * 通过独立 flash_program 完成，本函数仅构造字节。 */
void ota_slot_header_write_marker(uint8_t raw[OTA_SLOT_HEADER_BYTES]);

/* 解析 32B；校验 magic/slot_type/pad/marker 合法值/payload_len 界（§4.1）。
 * committed 反映 marker 已提交。成功返回 0，否则 -1。 */
int ota_slot_header_parse(const uint8_t raw[OTA_SLOT_HEADER_BYTES],
                          uint8_t expected_type,
                          ota_slot_header_t *out);

#ifdef __cplusplus
}
#endif

#endif /* E_TRACK_OTA_SLOT_HEADER_H */
