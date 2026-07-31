#ifndef E_TRACK_OTA_PATCH_H
#define E_TRACK_OTA_PATCH_H

#include <stdint.h>

#include "OTA/ota_layout.h"

#ifdef __cplusplus
extern "C" {
#endif

/* 差分包冻结组合：bit0 AES + bit1 LZMA + bit2 差分（契约 §2.1）。 */
#define OTA_PATCH_FLAGS 0x0007u
#define OTA_PATCH_HEADER_SIZE 64u
/* 40B 规范化内层头（契约 §2.3），逐字段解析，禁 struct memcpy。 */
#define OTA_PATCH_INNER_HEADER_SIZE 40u
#define OTA_PATCH_WORKSPACE_SIZE OTA_OVERLAY_WORKSPACE_LENGTH
/* staging 活跃窗口；密文原地解密，不双倍计算（契约 §520）。 */
#define OTA_PATCH_INPUT_SIZE 4096u
/* LZMA 解压输出缓冲：承载 bsdiff 指令流（控制字/diff/extra）。 */
#define OTA_PATCH_STREAM_SIZE 1024u
/* bspatch 差分/extra 写缓冲：与解压缓冲分开，流式写 candidate。 */
#define OTA_PATCH_WORK_SIZE 1024u
/* 基版镜像身份长度：SHA-256 前 8B（契约 §2.1 off52）。 */
#define OTA_PATCH_BASE_SHA8_SIZE 8u

typedef enum ota_patch_result_t
{
    OTA_PATCH_OK = 0,
    OTA_PATCH_ERR_ARGUMENT = -1,
    OTA_PATCH_ERR_READ = -2,
    OTA_PATCH_ERR_MAGIC = -3,
    OTA_PATCH_ERR_HEADER_LENGTH = -4,
    OTA_PATCH_ERR_HEADER_CRC = -5,
    OTA_PATCH_ERR_FLAGS = -6,
    OTA_PATCH_ERR_ALGORITHM = -7,
    OTA_PATCH_ERR_KEY = -8,
    OTA_PATCH_ERR_HARDWARE = -9,
    OTA_PATCH_ERR_LAYOUT = -10,
    OTA_PATCH_ERR_MIN_BOOT = -11,
    OTA_PATCH_ERR_VERSION = -12,
    OTA_PATCH_ERR_BASE_VCODE = -13,
    OTA_PATCH_ERR_BASE_SHA8 = -14,
    OTA_PATCH_ERR_PACKAGE_LENGTH = -15,
    OTA_PATCH_ERR_PAYLOAD_CRC = -16,
    OTA_PATCH_ERR_WORKSPACE = -17,
    OTA_PATCH_ERR_INNER_CRC = -18,
    OTA_PATCH_ERR_INNER_PSIZE = -19,
    OTA_PATCH_ERR_INNER_PAD = -20,
    OTA_PATCH_ERR_LZMA_PROPERTIES = -21,
    OTA_PATCH_ERR_BASE_LENGTH = -22,
    OTA_PATCH_ERR_BASE_CRC = -23,
    OTA_PATCH_ERR_IMAGE_LENGTH = -24,
    OTA_PATCH_ERR_CANDIDATE_PREPARE = -25,
    OTA_PATCH_ERR_LZMA_DATA = -26,
    OTA_PATCH_ERR_PATCH_CONTROL = -27,
    OTA_PATCH_ERR_DECODED_LENGTH = -28,
    OTA_PATCH_ERR_CANDIDATE_WRITE = -29,
    OTA_PATCH_ERR_CANDIDATE_VERIFY = -30,
    OTA_PATCH_ERR_RESULT_CRC = -31,
    OTA_PATCH_ERR_FW_HEADER = -32,
    OTA_PATCH_ERR_IMAGE_METADATA = -33
} ota_patch_result_t;

typedef struct ota_patch_device_t
{
    uint32_t current_vcode;
    uint32_t hardware_rev;
    uint8_t layout_id;
    uint8_t boot_version;
    /* 当前运行镜像长度（= fw_header.image_len），对 ph_osize 交叉校验。 */
    uint32_t base_image_len;
    /* 当前运行镜像整镜像 SHA-256 前 8B，对外层 base_sha8（契约 §2.4 ⑧）。 */
    uint8_t base_image_sha8[OTA_PATCH_BASE_SHA8_SIZE];
} ota_patch_device_t;

/* 回调契约与 ota_package_io_t 同语义；base_read 额外提供基版镜像读取。
 * MCU 侧 base_read 为内部 flash XIP 直读，按块 memcpy 到 1KiB 工作缓冲，
 * 不得把整个基版镜像复制到 RAM（契约 §512）。 */
typedef struct ota_patch_io_t
{
    void *ctx;
    int (*package_read)(void *ctx, uint32_t offset,
                        uint8_t *dst, uint32_t len);
    int (*base_read)(void *ctx, uint32_t offset,
                     uint8_t *dst, uint32_t len);
    int (*candidate_prepare)(void *ctx, uint32_t image_len);
    int (*candidate_program)(void *ctx, uint32_t offset,
                             const uint8_t *src, uint32_t len);
    int (*candidate_read)(void *ctx, uint32_t offset,
                          uint8_t *dst, uint32_t len);
    int (*workspace_acquire)(void *ctx, uint8_t **workspace,
                             uint32_t *workspace_len);
    void (*workspace_release)(void *ctx, uint8_t *workspace,
                              uint32_t workspace_len);
} ota_patch_io_t;

typedef struct ota_patch_info_t
{
    uint32_t package_len;
    uint32_t payload_len;
    uint32_t payload_crc32;
    uint32_t target_vcode;
    uint32_t base_vcode;
    /* 内层头实测值（契约 §2.3）。 */
    uint32_t patch_stream_len;
    uint32_t base_len;
    uint32_t base_crc32;
    uint32_t image_len;
    uint32_t image_crc32;
    uint32_t decoded_len;
    uint32_t workspace_peak;
    uint8_t image_sha256[32];
} ota_patch_info_t;

ota_patch_result_t ota_patch_apply(
    const ota_patch_io_t *io,
    const ota_patch_device_t *device,
    uint32_t package_len,
    ota_patch_info_t *out_info);

const char *ota_patch_result_name(ota_patch_result_t result);

#ifdef __cplusplus
}
#endif

#endif
