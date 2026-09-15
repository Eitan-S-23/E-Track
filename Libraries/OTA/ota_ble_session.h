#ifndef E_TRACK_OTA_BLE_SESSION_H
#define E_TRACK_OTA_BLE_SESSION_H

#include <stdint.h>

#include "OTA/ota_ble_frame.h"
#include "OTA/ota_ble_ring.h"
#include "OTA/ota_sd.h"
#include "OTA/ota_staging.h"
#include "boot_crypto.h"

#ifdef __cplusplus
extern "C" {
#endif

/* P3-1 BLE 会话层：在帧层（ota_ble_frame）之上实现合同 §5 的
 * BEGIN/DATA/END/ABORT 会话状态机，并把有效段写入 ota_staging
 * （唯一 durable staging 通道，本组件不复制其任何状态）。
 *
 * 平台依赖全部经 ota_ble_env_t 注入：host 单元测试注入内存 IO 与
 * 模拟时钟即可全路径验证，生产构型不含任何测试符号。
 *
 * 内存布局（P2-6 v3 冻结口径下的落位）：
 * - 会话控制块 + demux/parser + 增量 SHA ctx 常驻主 RAM（<1KB）；
 * - RX 环（>=4KB，合同 §5.1）与 ota_staging_receiver_t（含 4KB 块缓冲）
 *   子分配自 OTA overlay workspace，BEGIN 时获取（BLE owner）、
 *   END/ABORT/超时释放。LiveMap 在屏期间 BEGIN 返回 ERR_BUSY。 */

/* 实验基线（P3-4 标定，禁止冻结为契约） */
#ifndef CONFIG_OTA_BLE_RX_RING_SIZE
#define CONFIG_OTA_BLE_RX_RING_SIZE 4096u
#endif
#ifndef CONFIG_OTA_BLE_LIVENESS_MS
#define CONFIG_OTA_BLE_LIVENESS_MS 500u
#endif
#ifndef CONFIG_OTA_BLE_SESSION_TIMEOUT_MS
#define CONFIG_OTA_BLE_SESSION_TIMEOUT_MS 30000u
#endif

/* INFO payload 内容提供者（合同 §5.2.1，内容由 P3-2 实现；
 * P3-1 只负责协议封装与发送）。返回 0 表示暂无应答。 */
typedef struct ota_ble_info_t
{
    char model[8]; /* ASCIIZ */
    uint16_t hw_rev;
    uint8_t layout_id;
    uint8_t boot_ver;
    uint32_t cur_vcode;
    uint8_t image_sha256[32];
} ota_ble_info_t;

typedef struct ota_ble_env_t
{
    uint32_t (*now_ms)(void);
    /* 上行帧出口（阻塞写 UART）。返回 0 成功。 */
    int (*send)(const uint8_t *frame, uint16_t len);
    /* 以下返回 1/0 */
    int (*bcb_confirmed)(void);  /* 活动 BCB == CONFIRMED（staging 前置门槛） */
    int (*ota_disabled)(void);   /* JEDEC 白名单外（合同 §0.7） */
    int (*overlay_acquire)(void); /* 获取 OTA overlay workspace（BLE owner） */
    void (*overlay_release)(void);
    /* acquire 成功后取 workspace 基址与容量（40960B） */
    uint8_t *(*overlay_workspace)(uint32_t *out_size);
    /* 设备身份（etu_header 校验输入；P3-2 INFO 与此处同源）。
     * 返回 0 表示身份未就绪（BEGIN 回 ERR_STATE）。 */
    int (*get_device)(ota_sd_device_t *out_device);
    /* INFO 内容提供者；NULL = GET_INFO 不应答 */
    int (*info_provider)(ota_ble_info_t *out_info);
    const ota_staging_io_t *staging_io; /* QSPI staging IO（绝对地址语义） */
    /* P3-3 修复：END 激活钩子（staging finalize 成功后调用）。
     * 平台实现串「staging→candidate 搬运+ETU 解包校验 +
     * backup 自拷 + BCB STAGED 提交」（对齐 SD 卡路径
     * OtaUpdate::Apply/Stage 的既有语义；kind 决定全量/差分 Apply
     * 分支）。返回 0 成功；非 0 = 任一环节失败（活动 BCB 保持
     * CONFIRMED，设备继续运行旧版）。target_vcode/total_len/kind
     * 均来自 BEGIN 时 ota_sd_inspect_header 的校验结果，供平台核对
     * Apply 输出版本与长度一致性。会话层 fail-closed：NULL 视为
     * 配置残缺，END 回 ERR_FLASH。 */
    int (*activate_staged)(uint32_t target_vcode, uint32_t total_len,
                           ota_sd_kind_t kind);
    /* 激活成功且 ACK END OK 已发出后调用（生产 = 系统复位进入 boot
     * STAGED 流程；host 测试注入打点后正常返回）。 */
    void (*system_reset)(void);
} ota_ble_env_t;

typedef enum ota_ble_session_state_t
{
    OTA_BLE_SESSION_IDLE = 0,
    OTA_BLE_SESSION_ACTIVE = 1
} ota_ble_session_state_t;

typedef struct ota_ble_session_t
{
    ota_ble_env_t env;
    ota_ble_demux_t demux;

    uint8_t state;
    uint8_t session_id;
    uint8_t next_session_id;
    uint16_t expected_seq;

    uint32_t total_len;
    uint8_t package_sha256[32];
    /* 整包 CRC32 增量（ETSL@12 冻结语义 = whole-package CRC，与 SD 路径
     * 的 verified_package_crc32 同源；END 时收尾传 ota_staging_finalize） */
    boot_crc32_ctx_t pkg_crc;
    uint32_t target_vcode;
    uint8_t pkg_kind; /* ota_sd_kind_t（BEGIN inspect 结果，END 激活分派） */

    ota_staging_progress_t progress;
    boot_sha256_ctx_t sha; /* 块提交时增量；resume 时从 staging 回填前缀 */

    uint32_t last_frame_ms;   /* 最近有效帧（会话超时基准，噪声不重置） */
    uint32_t last_data_ms;    /* 最近有效 DATA（liveness 基准） */
    uint32_t last_liveness_ms;
    uint8_t last_ack_cmd;     /* liveness 重发的 ACK 模板 */
    uint16_t last_ack_seq;

    /* overlay 子分配（仅 ACTIVE 期间有效） */
    ota_ble_ring_t rx_ring;
    ota_staging_receiver_t *receiver;
    /* ISR 与泵共享：ISR 读、泵写；为 1 时 ISR 把 UART 字节压入 rx_ring */
    volatile uint8_t isr_active;

    uint8_t tx_frame[OTA_BLE_MAX_FRAME];
} ota_ble_session_t;

void ota_ble_session_init(ota_ble_session_t *session,
                          const ota_ble_env_t *env);

/* 会话是否活跃（HAL 层据此门控 X-Trace 上行与文本回显） */
int ota_ble_session_active(const ota_ble_session_t *session);

/* ---- ISR 上下文（attachInterrupt 回调内调用） ---- */

/* 活跃标志查询（hook 先查再搬 HW 环，降低非活跃期 ISR 开销） */
int ota_ble_session_isr_active(const ota_ble_session_t *session);

/* 活跃期间压入一字节；非活跃期直接返回（字节留在 HardwareSerial 环） */
void ota_ble_session_isr_feed(ota_ble_session_t *session, uint8_t byte);

/* ---- 泵上下文（主循环，CONFIG_OTA_BLE_PUMP_PERIOD_MS 周期） ---- */

/* 空闲路径：非活跃期由 HAL 层从 HardwareSerial 环排出的字节喂入。
 * text_sink 在会话活跃期由调用方传 NULL（非帧字节丢弃，合同 §5.1）。 */
void ota_ble_session_feed_idle(ota_ble_session_t *session,
                               ota_ble_text_sink_t text_sink,
                               void *text_ctx,
                               uint8_t byte);

/* 泵节拍：排空 overlay RX 环 -> 帧处理（活跃期间文本字节丢弃）；
 * 处理会话超时与 liveness 重发。 */
void ota_ble_session_pump(ota_ble_session_t *session);

#ifdef __cplusplus
}
#endif

#endif
