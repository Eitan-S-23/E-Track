#ifndef E_TRACK_OTA_DEVICE_INFO_H
#define E_TRACK_OTA_DEVICE_INFO_H

#include <stdint.h>

#include "EEPROM/eeprom_bcb.h"
#include "boot_fw_header.h"

#ifdef __cplusplus
extern "C" {
#endif

/* P3-2 设备身份链：GET_INFO/INFO（合同 §5.2.1）与 BEGIN 的 .etu 头校验
 * 输入（ota_sd_device_t）共用的唯一身份快照来源。
 *
 * 权威依据（docs/ota-cross-system-contracts.md + 派工书）：
 * - model 冻结为 "E-Track\0"（OTA-XC-DEVICE-MODEL，7 ASCII + NUL）；
 * - hw_rev/layout_id/cur_vcode 取校验通过的 fw_header 实值；
 * - boot_ver 取 Boot 编译期常量 BOOT_VERSION（fw_header 只存 min_boot_ver）；
 * - image_sha256 = 全镜像 [0, image_len) 原始字节 SHA-256（raw 域，
 *   OTA-XC-IMAGE-IDENTITY；与 fw_header.image_sha256 双零域严格分离，
 *   raw 前 8B 即 .etu base_sha8 比较域）。
 *
 * BCB 语义（§3.2「镜像真伪始终以 fw_header SHA 为准」）：
 * - 仲裁 A/B/NONE 均可返回身份（NONE = 双块无效，fw_header 有效即可引导，
 *   身份权威不在 BCB；cur_vcode 与 fw_header 不一致时以 fw_header 为准）；
 * - 仲裁 ERROR（EEPROM IO 失败）fail closed，不产生 INFO。
 *
 * 本组件纯只读：不写 Flash/EEPROM/staging，不改 OTA 状态；平台依赖全部
 * 经 boot_image_reader_t / bcb_hal_t 注入，host 单元测试注入内存 stub
 * 即可全路径验证，生产构型不含任何测试符号。 */

typedef struct ota_device_info_t
{
    char model[8]; /* ASCIIZ，恒 "E-Track\0" */
    uint16_t hw_rev;
    uint8_t layout_id;
    uint8_t boot_ver;
    uint32_t cur_vcode;
    uint8_t image_sha256[32]; /* raw SHA-256（非 header 双零域） */
} ota_device_info_t;

/* 快照状态由调用方拥有（单实例、静态存储）；重启后整体清零即失效。 */
typedef struct ota_device_identity_t
{
    uint8_t valid; /* 快照已生成（fw_header 校验 + raw SHA 通过） */
    ota_device_info_t info;
    int fw_header_result; /* 诊断：boot_fw_header_validate 原始返回值 */
    int bcb_result;       /* 诊断：bcb_arbiter 原始返回值（每次调用刷新） */
} ota_device_identity_t;

typedef enum ota_device_result_t
{
    OTA_DEVICE_OK = 0,
    OTA_DEVICE_ERR_ARGUMENT = -1, /* 空指针入参 */
    OTA_DEVICE_ERR_FW_HEADER = -2, /* fw_header 校验失败（细分见 state->fw_header_result） */
    OTA_DEVICE_ERR_HW_RANGE = -3,  /* hw_rev 超出 wire u16 表达范围（fail closed 防常量漂移） */
    OTA_DEVICE_ERR_IMAGE_READ = -4, /* raw SHA 计算中镜像读取失败 */
    OTA_DEVICE_ERR_BCB_IO = -5    /* BCB 仲裁 IO 失败（fail closed） */
} ota_device_result_t;

/* 生成/复用设备身份快照并填充 *out。
 * - 快照无效时执行重计算（fw_header 完整校验 + 全镜像 raw SHA-256）；
 *   运行期 App 无法改写自身 Flash，快照缓存复用；重启清零后重建。
 * - 每次调用重新执行 BCB 仲裁（轻量 EEPROM 读）；IO 失败 fail closed。
 * - 成功返回 OTA_DEVICE_OK 且 *out 为完整快照；失败返回负错误码，
 *   *out 不写入（部分有效不得生成 INFO）。
 * 只读无副作用，可在任何上下文重复调用。 */
ota_device_result_t ota_device_identity_get(
    ota_device_identity_t *state,
    ota_device_info_t *out,
    const boot_image_reader_t *image_reader,
    const bcb_hal_t *bcb_hal);

#ifdef __cplusplus
}
#endif

#endif
