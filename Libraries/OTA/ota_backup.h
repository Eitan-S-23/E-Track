#ifndef E_TRACK_OTA_BACKUP_H
#define E_TRACK_OTA_BACKUP_H

/*
 * P2-5 backup 自拷与 STAGED 提交事务（App 侧）。
 *
 * 冻结契约唯一依据：docs/ota-binary-contracts.md v1.1
 *   - §3.1/§3.2 BCB 字段与 seq 仲裁；§3.4 backup 槽锁定
 *   - §4.1/§4.3 ETSL 槽头与 marker-last 擦写序
 *   - §0.4/§0.5 槽地址与容量上限
 *   - PLAN-OTA.md §4：“当前版自拷 backup(读回 CRC)→BCB=STAGED→提示重启”；
 *     TEST_BOOT 期间拒绝新 OTA；仅 CONFIRMED 态允许自拷。
 *
 * 出口不变式：只有全部步骤成功才提交 BCB=STAGED 并返回 OTA_BACKUP_OK。
 * 提交前（BCB 未写）的任何失败保证活动 BCB 仍为 CONFIRMED；一旦 EEPROM 写
 * 已发生，读回故障属于“已提交但观测失败”，必须经后续仲裁归类为
 * verified STAGED / verified CONFIRMED / unknown，见 ota_backup_commit_state_t。
 * 未知态（OTA_BACKUP_ERR_COMMIT_AMBIGUOUS）禁止上层覆盖 candidate/backup。
 */

#include <stdint.h>

#include "EEPROM/eeprom_bcb.h"

#ifdef __cplusplus
extern "C" {
#endif

/* 外部 flash 直读/擦/写端口（HAL 接 QSPI，宿主测试接 RAM 仿真）。
 * 本模块不判断具体外设；地址为外部 flash 绝对地址。 */
typedef struct ota_backup_io_t
{
    void *ctx;
    /* 当前内部 App 镜像 XIP 直读（offset 相对 APP_ORIGIN）。失败返回非 0。 */
    int (*app_read)(void *ctx, uint32_t offset,
                    uint8_t *dst, uint32_t len);
    /* 外部 flash 直读（XIP map）。失败返回非 0。 */
    int (*flash_read)(void *ctx, uint32_t address,
                      uint8_t *dst, uint32_t len);
    /* 外部 flash 擦 4KB 扇区（address 必须 4KB 对齐）。失败返回非 0。 */
    int (*flash_erase_4k)(void *ctx, uint32_t address);
    /* 外部 flash 写（address 须落在本模块按槽界放行的区域）。失败返回非 0。 */
    int (*flash_program)(void *ctx, uint32_t address,
                         const uint8_t *src, uint32_t len);
} ota_backup_io_t;

typedef enum ota_backup_result_t
{
    OTA_BACKUP_OK                  = 0,
    OTA_BACKUP_ERR_ARGUMENT        = -1,
    OTA_BACKUP_ERR_STATE           = -2,  /* 活动 BCB 非 CONFIRMED / 状态不合法 */
    OTA_BACKUP_ERR_EEPROM          = -3,  /* BCB 仲裁 I/O 失败或双块均坏 */
    OTA_BACKUP_ERR_APP_HEADER      = -4,  /* 当前内部 App fw_header 无效/越界 */
    OTA_BACKUP_ERR_CANDIDATE_READ  = -5,  /* candidate 读取失败 */
    OTA_BACKUP_ERR_CANDIDATE_HEADER= -6,  /* candidate fw_header 无效/越界 */
    OTA_BACKUP_ERR_CANDIDATE_CRC   = -7,  /* candidate 复核不一致（CRC/元数据/降级） */
    OTA_BACKUP_ERR_ERASE           = -8,
    OTA_BACKUP_ERR_WRITE           = -9,
    OTA_BACKUP_ERR_READBACK        = -10,
    OTA_BACKUP_ERR_SLOT_HEADER     = -11, /* 槽头字段或 marker 写/读回失败 */
    OTA_BACKUP_ERR_SLOT_VERIFY     = -12, /* 提交前双槽复核失败 */
    OTA_BACKUP_ERR_COMMIT          = -13, /* BCB=STAGED 提交失败（复裁为仍 CONFIRMED，可重试） */
    OTA_BACKUP_ERR_VERIFY          = -14, /* STAGED 提交后读回不一致（复裁 unknown 时见 AMBIGUOUS） */
    OTA_BACKUP_ERR_DISABLED        = -15, /* QSPI 白名单外 / 访问失败，OTA 禁用 */
    OTA_BACKUP_ERR_COMMIT_AMBIGUOUS= -16  /* 提交后复裁 unknown：禁止覆盖 candidate/backup */
} ota_backup_result_t;

/* BCB 提交后的确定性分类（阻断 6）。EEPROM 写一旦开始，读回失败不代表
 * "未提交"；提交方必须重新仲裁分类后再决定上层动作。 */
typedef enum ota_backup_commit_state_t
{
    OTA_BACKUP_COMMIT_NONE = 0,          /* 尚未进入提交步骤（前置失败） */
    OTA_BACKUP_COMMIT_VERIFIED_STAGED,   /* 复裁确认 STAGED 有效落盘（视为成功） */
    OTA_BACKUP_COMMIT_VERIFIED_CONFIRMED,/* 复裁确认活动块仍 CONFIRMED（可重试） */
    OTA_BACKUP_COMMIT_UNKNOWN            /* 复裁无法判定（双坏/仲裁失败/字段不符） */
} ota_backup_commit_state_t;

typedef struct ota_backup_info_t
{
    uint32_t candidate_len;
    uint32_t candidate_crc32;
    uint32_t candidate_vcode;
    uint8_t  candidate_sha8[8];
    uint32_t backup_len;
    uint32_t backup_crc32;
    uint32_t backup_vcode;
    uint8_t  backup_sha8[8];
    /* 副作用计数：erase_count = 本事务已执行的 4KB 扇区擦除数；
     * program_count = 本事务已执行的 flash 编程调用成功数。写成功但读回
     * 失败同样计入 program_count（实际已发生写入）。两者在函数返回时始终
     * 反映真实已发生副作用，即使 OTA_BACKUP_ERR_* 失败路径也已回填。 */
    uint32_t erase_count;
    uint32_t program_count;
    /* BCB 提交后的确定性分类；提交尚未发生时=OTA_BACKUP_COMMIT_NONE。 */
    ota_backup_commit_state_t commit_state;
} ota_backup_info_t;

/* 执行 backup 自拷 + candidate/backup 槽头(marker-last) + BCB=STAGED 原子提交。
 * io/bcb_hal 必须非空；out 可为空。
 * 前置阶段失败（BCB 仲裁/复核，尚未写 EEPROM）活动块仍 CONFIRMED；
 * 提交期失败见 ota_backup_commit_state_t 与 OTA_BACKUP_ERR_COMMIT_AMBIGUOUS。 */
ota_backup_result_t ota_backup_stage(const ota_backup_io_t *io,
                                     const bcb_hal_t *bcb_hal,
                                     ota_backup_info_t *out);

const char *ota_backup_result_name(ota_backup_result_t result);

#ifdef __cplusplus
}
#endif

#endif /* E_TRACK_OTA_BACKUP_H */
