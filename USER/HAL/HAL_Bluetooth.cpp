#include "HAL.h"
#include "Bluetooth/Bluetooth.h"
#include "HAL/HAL_OTA_Backup.h"
#include "HAL/HAL_OTA_Package.h"
#include "HAL/HAL_OTA_Staging.h"
#include "OTA/ota_ble_session.h"
#include "OTA/ota_device_info.h"
#include "OTA/ota_layout.h"
#include "boot_fw_header.h"
#include "EEPROM/eeprom_bcb.h"
#include <stdio.h>
#include <stdarg.h>
#include <stddef.h>
#include <string.h>
#include "p34_ack_gap.h"
#if defined(P34_OTA_PIPELINE_ACK_BIND) && P34_OTA_PIPELINE_ACK_BIND
#include "../../Tools/ota/p34_timed_ack_batch.h"
#else
#include "p34_timed_ack_batch.h"
#endif

#define BT_SERIAL             CONFIG_BT_SERIAL
#define DEBUG_SERIAL          CONFIG_DEBUG_SERIAL
#define BT_USE_TRANSPARENT    CONFIG_BT_USE_TRANSPARENT

#ifndef CONFIG_BT_FIXED_BAUD
#define CONFIG_BT_FIXED_BAUD 115200u
#endif

#if CONFIG_BT_BAUD_EXPERIMENT
/* 实验构型一致性门槛（fail-closed，两组互斥都必须编译期拒绝）：
 * 1) RTT down channel 0 只允许一个读取者。本文件的实验控制台与 App.cpp 的
 *    RttDebugCmd_Poll（CONFIG_RTT_DEBUG_CMD_ENABLE）读同一路下行环，同时
 *    开启会按字节切开命令行。
 * 2) 透明串口桥（CONFIG_BT_USE_TRANSPARENT）会把 DEBUG_SERIAL 的字节无条件
 *    写进 BT UART，实验中无法隔离"非预期 UART TX"，也不符合单变量纪律。 */
#include "Config/Config.h"
#if CONFIG_RTT_DEBUG_CMD_ENABLE
#error "CONFIG_BT_BAUD_EXPERIMENT 与 CONFIG_RTT_DEBUG_CMD_ENABLE 不得同时为 1"
#endif
#if BT_USE_TRANSPARENT
#error "CONFIG_BT_BAUD_EXPERIMENT 不得与透明串口桥 CONFIG_BT_USE_TRANSPARENT 同时启用"
#endif
#endif

static TinyBTPlus bt;
static uint32_t lastRxTick = 0;

/* ACK batches belong to a real session generation, with or without profiling. */
static volatile uint32_t s_ble_epoch = 0;
static uint32_t s_p34_clock_ok;

static uint32_t p34_clock(void)
{
    return DWT->CYCCNT;
}

/* ================= P3-1 BLE OTA 传输接线 =================
 * 职责分工（合同 OTA-XC-BLE-LIFECYCLE）：HAL_Bluetooth 拥有 UART demux
 * 与调度入口；ota_ble_session 拥有帧/会话状态机；ota_staging 继续拥有
 * durable staging 事实。本文件只做注入接线，不复制任何协议状态。 */
static ota_ble_session_t s_ble_session;
static ota_staging_io_t s_ble_staging_io;
#if defined(P34_OTA_PIPELINE_SYNC) && P34_OTA_PIPELINE_SYNC
#include "OTA/ota_pipeline_sync.h"
static ota_pipeline_io_t s_ble_pipeline_io;
#endif

/* P3-2 设备身份链（OTA-XC-INFO-MAPPING）：快照与校验归 ota_device_info，
 * 此处只注入内部 Flash 镜像读与 App 侧 BCB hal。get_device 与 INFO
 * provider 同源——单份快照供 BLE BEGIN 的 .etu 头校验与 GET_INFO 回包；
 * 运行期镜像不变故快照缓存复用，重启清零重建（派工书快照失效语义）。 */
static ota_device_identity_t s_ble_identity;

#if CONFIG_OTA_BLE_PROFILE
#if !CONFIG_BT_BAUD_EXPERIMENT
#error "P3-4 profile requires the bounded baud controller"
#endif
#include "HAL/BtBaudExperiment/p34_link_profile.h"
static uint32_t bt_bx_actual_baud(usart_type *u);
static p34_profile_t s_p34_profile;
static ota_staging_io_t s_p34_staging_io;
static uint32_t s_p34_bad_frames_start;
static uint32_t s_p34_last_pump;
static uint32_t s_p34_last_pump_ms;
static uint32_t s_p34_pump_start;
static uint32_t s_p34_pump_start_ms;
static int s_p34_pump_running;
extern "C" {
volatile p34_profile_t g_p34_ble_profile;
volatile uint32_t g_p34_boot_baud;
volatile uint32_t g_p34_retained_word;
volatile uint32_t g_p34_retention_error;
}

static void p34_record(unsigned phase, uint32_t start, uint32_t start_ms,
                        uint32_t bytes, int result)
{
    p34_profile_add(&s_p34_profile, phase, p34_clock() - start,
                    millis() - start_ms, bytes, result);
}

static int p34_staging_read(void *ctx, uint32_t address, uint8_t *dst, uint32_t len)
{
    uint32_t start = p34_clock(), start_ms = millis();
    int result = s_p34_staging_io.read(ctx, address, dst, len);
    p34_record(address < OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET ?
               P34_JOURNAL_READ : P34_PAYLOAD_READ, start, start_ms, len, result);
    return result;
}

static int p34_staging_program(void *ctx, uint32_t address, const uint8_t *src, uint32_t len)
{
    uint32_t start = p34_clock(), start_ms = millis();
    int result = s_p34_staging_io.program(ctx, address, src, len);
    p34_record(address < OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET ?
               P34_JOURNAL_PROGRAM : P34_PAYLOAD_PROGRAM, start, start_ms, len, result);
    return result;
}

static ota_staging_result_t p34_staging_verify(void *ctx, uint32_t address,
                                             const uint8_t *expected, uint32_t len)
{
    uint32_t start = p34_clock(), start_ms = millis();
    ota_staging_result_t result = s_p34_staging_io.verify(ctx, address, expected, len);
    p34_record(address < OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET ?
               P34_JOURNAL_VERIFY : P34_PAYLOAD_VERIFY, start, start_ms, len, (int)result);
    return result;
}

static int p34_staging_erase(void *ctx, uint32_t address)
{
    uint32_t start = p34_clock(), start_ms = millis();
    int result = s_p34_staging_io.erase_4k(ctx, address);
    p34_record(address < OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET ?
               P34_JOURNAL_ERASE : P34_PAYLOAD_ERASE, start, start_ms, 4096u, result);
    return result;
}

static void p34_begin(void)
{
    uint32_t primask = __get_PRIMASK();
    uint32_t run = s_p34_profile.run + 1u;
    __disable_irq();
    BT_SERIAL.resetRxDiagnostics();
    p34_profile_reset(&s_p34_profile, run, SystemCoreClock, s_p34_clock_ok,
                       bt_bx_actual_baud(BT_SERIAL.getUSART()),
                       p34_baud_from_word(ertc_bpr_data_read(ERTC_DT20)));
    g_p34_ble_profile.ready = 0u;
    s_p34_bad_frames_start = s_ble_session.demux.parser.bad_frames;
    s_p34_last_pump = p34_clock();
    s_p34_last_pump_ms = millis();
    __set_PRIMASK(primask);
}

static void p34_finish(uint32_t total_len, uint32_t terminal)
{
    uint32_t primask;
    if (!s_p34_profile.active)
    {
        return;
    }
    if (s_p34_pump_running)
    {
        p34_record(P34_PUMP_WORK, s_p34_pump_start, s_p34_pump_start_ms, 0u, 0);
    }
    primask = __get_PRIMASK();
    __disable_irq();
    s_p34_profile.hw_buffer_dropped = BT_SERIAL.rxBufferDropped();
    s_p34_profile.uart_error_events = BT_SERIAL.rxErrorEvents();
    s_p34_profile.uart_error_flags = BT_SERIAL.rxErrorFlags();
    s_p34_profile.parser_bad_frames = s_ble_session.demux.parser.bad_frames - s_p34_bad_frames_start;
    p34_profile_freeze(&s_p34_profile, (p34_profile_t *)&g_p34_ble_profile, total_len, terminal);
    __DMB();
    g_p34_ble_profile.ready = 1u;
    __set_PRIMASK(primask);
    SEGGER_RTT_printf(0, "P34PERF: ready run=%lu bytes=%lu terminal=%lu size=%lu\r\n",
                      (unsigned long)s_p34_profile.run, (unsigned long)total_len,
                      (unsigned long)terminal, (unsigned long)sizeof(p34_profile_t));
}
#endif

static int ble_current_image_read(void *ctx, uint32_t offset,
                                  uint8_t *dst, size_t len)
{
    (void)ctx;
    if (dst == NULL || offset > OTA_APP_LENGTH ||
        len > (size_t)(OTA_APP_LENGTH - offset))
    {
        return -1;
    }
    memcpy(dst, (const void *)(uintptr_t)(OTA_APP_ORIGIN + offset), len);
    return 0;
}

static boot_image_reader_t s_ble_image_reader = { ble_current_image_read, NULL };

/* ---- ota_ble_env_t 注入实现 ---- */

static uint32_t ble_env_now_ms(void)
{
    return millis();
}

static P34TimedAckBatch s_p34_ack_batch;
static uint32_t s_p34_ack_durable;

#if defined(P34_OTA_PIPELINE_WAIT_RX) && P34_OTA_PIPELINE_WAIT_RX
#if !defined(P34_OTA_PIPELINE_SYNC) || !P34_OTA_PIPELINE_SYNC
#error P34_OTA_PIPELINE_WAIT_RX_requires_the_owned_synchronous_payload_port
#endif
#if !defined(P34_OTA_PIPELINE_ACK_BIND) || !P34_OTA_PIPELINE_ACK_BIND
#error P34_OTA_PIPELINE_WAIT_RX_requires_v2_ACK_deadline_polling
#endif
static int ble_uart_send(const uint8_t *frame, uint16_t len);
extern "C" void HAL_OTA_QspiWaitRx(void)
{
    if (s_ble_session.pipeline == NULL || !s_ble_session.pipeline->in_start) return;
    ota_ble_session_receive_pending(&s_ble_session);
    (void)s_p34_ack_batch.poll(millis(), ota_ble_session_active(&s_ble_session) != 0,
                              ble_uart_send);
}
#endif

static int ble_uart_send(const uint8_t *frame, uint16_t len)
{
    uint16_t i;
    int result = 0;
#if CONFIG_OTA_BLE_PROFILE
    uint32_t start = p34_clock(), start_ms = millis();
#endif

    for (i = 0u; i < len; ++i)
    {
        BT_SERIAL.write(frame[i]);
    }
    /* Drain the last stop bit, then preserve the measured 1 ms ACK gap. */
    if (!s_p34_clock_ok || SystemCoreClock != 288000000u ||
        !p34_ack_gap(p34_clock,
            []() { return usart_flag_get(BT_SERIAL.getUSART(), USART_TDC_FLAG) != RESET; },
            288000u, 576000u))
    {
        result = -1;
    }
#if CONFIG_OTA_BLE_PROFILE
    p34_record(P34_ACK_TX_CALL, start, start_ms, len, result);
#endif
    return result;
}

static uint32_t ble_ack_u32(const uint8_t *bytes)
{
    return (uint32_t)bytes[0] | ((uint32_t)bytes[1] << 8) |
           ((uint32_t)bytes[2] << 16) | ((uint32_t)bytes[3] << 24);
}

static int ble_env_send(const uint8_t *frame, uint16_t len)
{
    const bool data_ok = len == 19u && frame[2] == OTA_BLE_CMD_ACK_DATA &&
                         frame[8] == OTA_BLE_STATUS_OK;
#if OTA_BLE_PIPELINE_ENABLED
    const bool data2_ok = len == 27u && frame[2] == OTA_BLE_CMD_ACK_DATA2 &&
                         frame[8] == OTA_BLE_STATUS_OK;
    const uint32_t durable = data2_ok ? ble_ack_u32(frame + 13) :
        data_ok ? ble_ack_u32(frame + 9) : s_p34_ack_durable;
#else
    const uint32_t durable = data_ok ? ble_ack_u32(frame + 9) : s_p34_ack_durable;
#endif
    /* Commit advancement and control/error responses flush immediately. All
     * other ACK frames keep their original bytes and FIFO order. */
    const int result = s_p34_ack_batch.send(frame, len,
        (data_ok
#if OTA_BLE_PIPELINE_ENABLED
         || data2_ok
#endif
        ) && durable == s_p34_ack_durable, millis(), ble_uart_send);
    if (result == 0)
    {
        if (data_ok) s_p34_ack_durable = durable;
        else if (len == 20u && frame[2] == OTA_BLE_CMD_ACK_BEGIN)
            s_p34_ack_durable = ble_ack_u32(frame + 10);
#if OTA_BLE_PIPELINE_ENABLED
        else if (data2_ok) s_p34_ack_durable = durable;
        else if (len == 28u && frame[2] == OTA_BLE_CMD_ACK_BEGIN2 && frame[8] == 0u)
            s_p34_ack_durable = ble_ack_u32(frame + 14);
#endif
    }
    return result;
}

static int ble_env_bcb_confirmed(void)
{
    return HAL::OTA_GetBcbState() == BCB_STATE_CONFIRMED ? 1 : 0;
}

static int ble_env_ota_disabled(void)
{
    return HAL::Qspi_IsOtaDisabled() ? 1 : 0;
}

static int ble_env_overlay_acquire(void)
{
    int ok = HAL::OTA_OverlayAcquireBle() ? 1 : 0;

    if (ok)
    {
        /* 真实会话获取边界：代次递增使所有旧 epoch 下行命令与在飞探针失效 */
        s_ble_epoch++;
        (void)s_p34_ack_batch.rebind(s_ble_epoch);
#if CONFIG_OTA_BLE_PROFILE
        p34_begin();
#endif
    }
    return ok;
}

static void ble_env_overlay_release(void)
{
    (void)s_p34_ack_batch.drain(ble_uart_send);
    HAL::OTA_OverlayReleaseBle();
    /* 真实会话释放边界：释放后进入的观测属于下一代 */
    s_ble_epoch++;
}

static uint8_t *ble_env_overlay_workspace(uint32_t *out_size)
{
    return HAL::OTA_OverlayGetWorkspace(out_size);
}

static int ble_env_get_device(ota_sd_device_t *out_device)
{
    ota_device_info_t info;

    if (out_device == NULL ||
        ota_device_identity_get(&s_ble_identity, &info,
                                &s_ble_image_reader,
                                HAL::OTA_GetBcbHal()) != OTA_DEVICE_OK)
    {
        return 0;
    }
    memset(out_device, 0, sizeof(*out_device));
    out_device->current_vcode = info.cur_vcode;
    out_device->hardware_rev = info.hw_rev;
    out_device->layout_id = info.layout_id;
    out_device->boot_version = info.boot_ver;
    /* .etu base_sha8 比较域 = 设备 raw SHA-256 前 8B
     * （OTA-XC-IMAGE-IDENTITY 摘要域矩阵） */
    memcpy(out_device->base_image_sha8, info.image_sha256,
           sizeof(out_device->base_image_sha8));
    return 1;
}

static int ble_env_info_provider(ota_ble_info_t *out_info)
{
    ota_device_info_t info;

    if (out_info == NULL ||
        ota_device_identity_get(&s_ble_identity, &info,
                                &s_ble_image_reader,
                                HAL::OTA_GetBcbHal()) != OTA_DEVICE_OK)
    {
        return 0;
    }
    memset(out_info, 0, sizeof(*out_info));
    memcpy(out_info->model, info.model, sizeof(out_info->model));
    out_info->hw_rev = info.hw_rev;
    out_info->layout_id = info.layout_id;
    out_info->boot_ver = info.boot_ver;
    out_info->cur_vcode = info.cur_vcode;
    memcpy(out_info->image_sha256, info.image_sha256,
           sizeof(out_info->image_sha256));
    return 1;
}

/* P3-3 修复：END 激活链（对齐 SD 卡路径 OtaUpdate::Apply/Stage 既有
 * 语义，共用 ota_package/ota_backup/BCB 底层，不复制协议状态）：
 * CONFIRMED 再核 → staging→candidate 搬运+ETU 解包校验（full/patch 按
 * BEGIN inspect 的 kind 分派）→ backup 自拷+BCB STAGED 原子提交 →
 * 身份三元核对。任何环节失败不提交，活动 BCB 保持 CONFIRMED，设备
 * 继续运行旧版。同步长跑（Apply/Backup 内部喂狗，同 SD 路径先例）。 */
static int ble_env_activate_staged(uint32_t target_vcode, uint32_t total_len,
                                   ota_sd_kind_t kind)
{
#if CONFIG_OTA_BLE_PROFILE
    p34_finish(total_len, 0u);
#endif
#if defined(_WIN32)
    /* 模拟器不驱动真实 QSPI/EEPROM（同 OtaUpdate::Apply/Stage 的
     * _WIN32 语义）：返回成功供会话流程走通。 */
    (void)target_vcode;
    (void)total_len;
    (void)kind;
    return 0;
#else
    ota_sd_device_t device;
    ota_backup_info_t stage_info;
    ota_backup_result_t stage_result;
    uint32_t cand_vcode;
    uint32_t cand_len;
    uint8_t cand_sha8[8];
    uint32_t t_apply0;
    uint32_t t_apply1;

    /* 身份快照与 GET_INFO/BEGIN 同源（运行期镜像不变，缓存复用）。 */
    if (!ble_env_get_device(&device))
    {
        return -1;
    }
    /* P2-5 阻断 3 对齐：candidate prepare/write 前再次确认 CONFIRMED。 */
    if (HAL::OTA_GetBcbState() != BCB_STATE_CONFIRMED)
    {
        return -2;
    }

    t_apply0 = millis();
    if (kind == OTA_SD_KIND_PATCH)
    {
        /* 差分基线 = 当前运行镜像 fw_header（SD 路径 Begin 同源读法）。 */
        boot_fw_header_t fw;
        boot_fw_expectations_t expect;
        ota_patch_info_t info;
        ota_patch_result_t result;

        boot_fw_default_expectations(&expect);
        if (boot_fw_header_validate(&s_ble_image_reader, &expect,
                                    &fw) != BOOT_FW_OK)
        {
            return -3;
        }
        memset(&info, 0, sizeof(info));
        result = HAL::OTA_PatchApplyStaging(total_len, device.current_vcode,
                                            fw.image_len,
                                            device.base_image_sha8, &info);
        if (result != OTA_PATCH_OK)
        {
            SEGGER_RTT_printf(0, "BLEACT: patch apply %s\r\n",
                              ota_patch_result_name(result));
            return -4;
        }
        cand_vcode = info.target_vcode;
        cand_len = info.image_len;
        memcpy(cand_sha8, info.image_sha256, sizeof(cand_sha8));
    }
    else
    {
        ota_package_info_t info;
        ota_package_result_t result;

        memset(&info, 0, sizeof(info));
        result = HAL::OTA_PackageApplyStaging(total_len,
                                              device.current_vcode, &info);
        if (result != OTA_PACKAGE_OK)
        {
            SEGGER_RTT_printf(0, "BLEACT: full apply %s\r\n",
                              ota_package_result_name(result));
            return -4;
        }
        cand_vcode = info.target_vcode;
        cand_len = info.image_len;
        memcpy(cand_sha8, info.image_sha256, sizeof(cand_sha8));
    }
    /* Apply 输出版本必须等于 BEGIN inspect 的 target_vcode（SD 路径
     * Apply 同款核对）。 */
    if (cand_vcode != target_vcode)
    {
        return -5;
    }
    t_apply1 = millis();

    memset(&stage_info, 0, sizeof(stage_info));
    stage_result = HAL::OTA_BackupStage(&stage_info);
    if (stage_result == OTA_BACKUP_ERR_COMMIT_AMBIGUOUS)
    {
        /* 与 SD 路径同分类（commit_unknown）：提交后状态未知，不复位、
         * 不覆盖槽区；BCB 由 boot 下次启动仲裁（STAGED 则走 TEST_BOOT
         * 带看门狗与回滚保护，CONFIRMED 则维持旧版）。App 重试时 BEGIN
         * 的 bcb_confirmed 门槛自然拒绝，不会重传覆盖。 */
        SEGGER_RTT_printf(0, "BLEACT: stage commit_unknown\r\n");
        return -6;
    }
    if (stage_result != OTA_BACKUP_OK)
    {
        SEGGER_RTT_printf(0, "BLEACT: stage %s\r\n",
                          ota_backup_result_name(stage_result));
        return -6;
    }
    /* 核对 STAGED 提交的正是本次 Apply 的 candidate（身份三元，与 SD
     * 路径 Stage() 相同；sha8 = image_sha256 raw 前 8B）。 */
    if (stage_info.candidate_vcode != cand_vcode ||
        stage_info.candidate_len != cand_len ||
        memcmp(stage_info.candidate_sha8, cand_sha8,
               sizeof(cand_sha8)) != 0)
    {
        return -7;
    }
    /* 激活耗时打点：实测数据决定 App 侧 60s 重启复核窗口是否需要放宽。 */
    SEGGER_RTT_printf(0, "BLEACT: ok apply=%lums stage=%lums vcode=%lu\r\n",
                      (unsigned long)(t_apply1 - t_apply0),
                      (unsigned long)(millis() - t_apply1),
                      (unsigned long)target_vcode);
    return 0;
#endif
}

/* 激活成功后的系统复位（合同 §4.5：成功路径随后重启进入 boot STAGED
 * 流程；复位函数沿用固件内既有先例 HAL_FaultHandle.cpp 的 CMSIS
 * NVIC_SystemReset）。 */
static void ble_env_system_reset(void)
{
#if defined(_WIN32)
    /* 模拟器不复位进程，仅留痕。 */
    CONFIG_DEBUG_SERIAL.println("BLEACT: reset (sim)");
#else
    SEGGER_RTT_printf(0, "BLEACT: reset\r\n");
    NVIC_SystemReset();
#endif
}

/* UART ISR 回调（HardwareSerial 每字节入 HW 环后调用）：
 * 会话活跃期把 HW 环即时搬空进 overlay RX 环（HW 环 tail 仅 ISR 动），
 * 使 512B HW 环在任何波特率下都不积压；空闲期立刻返回，字节留给
 * 文本协议路径。 */
static void ble_isr_hook(HardwareSerial *serial)
{
#if CONFIG_OTA_BLE_PROFILE
    if (s_p34_profile.active)
    {
        uint32_t queued = (uint32_t)serial->available();
        if (queued > s_p34_profile.hw_queue_peak)
        {
            s_p34_profile.hw_queue_peak = queued;
        }
    }
#endif
    if (!ota_ble_session_isr_active(&s_ble_session))
    {
        return;
    }
    while (serial->available() > 0)
    {
        ota_ble_session_isr_feed(&s_ble_session,
                                 (uint8_t)serial->read());
#if CONFIG_OTA_BLE_PROFILE
        if (s_p34_profile.active)
        {
            uint32_t queued = ota_ble_ring_count(&s_ble_session.rx_ring);
            ++s_p34_profile.rx_session_bytes;
            s_p34_profile.overlay_dropped = s_ble_session.rx_ring.dropped;
            if (queued > s_p34_profile.rx_ring_peak)
            {
                s_p34_profile.rx_ring_peak = queued;
            }
        }
#endif
    }
}

/* 文本协议出口：demux 判定的非帧字节喂 TinyBTPlus（会话活跃期
 * session 层不会调用本 sink，合同 §5.1 活跃期文本零调用）。
 * 实验构型：不把模块文本送进 TinyBTPlus——它的成帧恰好与模块 AT 应答
 * （`+UART: 5\r\n`、`+READY\r\n`）同形，会把应答当文本包回写到 BT UART，
 * 既污染单变量实验又可能触发手册未定义的行为。此处只丢弃，不改共享库，
 * 原始 RX 观测与 OTA demux 仍由 bt_rx_service 完整保留。 */
static void bt_text_sink(void *ctx, uint8_t byte)
{
    (void)ctx;
#if CONFIG_BT_BAUD_EXPERIMENT
    (void)byte;
#else
    bt.encode((char)byte);
#endif
}

#if CONFIG_BT_BAUD_EXPERIMENT
/* ================= P3-4 波特率实验控制（仅实验构型） =================
 * 全部观测/命令/切速/状态机决策都在平台无关模块
 * USER/HAL/BtBaudExperiment/bt_baud_experiment.h 内实现；本段只注入真实
 * 平台操作（时间、RTT、UART、TX 完成标志、会话代次）。host 自测编译同一个
 * 头文件并只替换这些 op，因此测试跑的是实际决策代码。 */
#define BT_BX_RTT_CAP BUFFER_SIZE_UP
#include "HAL/BtBaudExperiment/bt_baud_experiment.h"

#define BT_BT_BAUD_INITIAL 115200u

static bt_bx_ops_t s_bt_bx_ops;
static bt_bx_t     s_bt_bx;
static int         s_bt_bx_ready = 0;

static uint32_t bt_bx_op_now_ms(void *io)
{
    (void)io;
    return millis();
}

/* 忙 = OTA 会话活跃或会话 ISR 活跃。两者任一成立都不允许观测输出与下行执行。 */
static int bt_bx_op_busy(void *io)
{
    (void)io;
    return (ota_ble_session_active(&s_ble_session) ||
            ota_ble_session_isr_active(&s_ble_session)) ? 1 : 0;
}

static uint32_t bt_bx_op_epoch(void *io)
{
    (void)io;
    return s_ble_epoch;
}

static unsigned bt_bx_op_rtt_read(void *io, char *dst, unsigned cap)
{
    (void)io;
    return (unsigned)SEGGER_RTT_Read(0, dst, cap);
}

static unsigned bt_bx_op_rtt_write(void *io, const char *src, unsigned len)
{
    (void)io;
    /* 上行环是 NO_BLOCK_SKIP：放不下时返回 0 而不是截断。
     * 只有返回值等于 len 才算写成功（由模块判定）。 */
    return (unsigned)SEGGER_RTT_Write(0, src, len);
}

/* 按手册行尾 \r\n 写一行 AT。返回写入字节数。 */
static unsigned bt_bx_op_at_write(void *io, const char *text, unsigned len)
{
    unsigned i;

    (void)io;
    for (i = 0u; i < len; ++i)
    {
        BT_SERIAL.write((uint8_t)text[i]);
    }
    BT_SERIAL.write((uint8_t)'\r');
    BT_SERIAL.write((uint8_t)'\n');
    return len + 2u;
}

/* 回读 PERIPH 实际分频后的线路速率（不是请求值）。 */
static uint32_t bt_bx_actual_baud(usart_type *u)
{
    crm_clocks_freq_type cf;
    uint32_t div;

    if (u == NULL)
    {
        return 0u;
    }
    div = (uint32_t)u->baudr_bit.div;
    if (div == 0u)
    {
        return 0u;
    }
    crm_clocks_freq_get(&cf);
    if (u == USART1 || u == USART6)
    {
        return cf.apb2_freq / div;
    }
    return cf.apb1_freq / div;
}

/* 本地 MCU UART 切速。不发送任何模块 AT、不复位模块、不重新烧录。
 * 返回 0 成功；-1 TX 完成等待超时；-2 非法/不支持；-3 重配或回读失败。 */
static int bt_bx_op_mcu_set_baud(void *io, uint32_t baud)
{
    usart_type *u;
    uint32_t t0;
    uint32_t actual;
    uint32_t tol;

    (void)io;
    if (!bt_bx_rate_known(baud))
    {
        return -2;
    }
    u = BT_SERIAL.getUSART();
    if (u == NULL)
    {
        /* 前置检查失败：尚未调用 begin()，硬件未被改动，调用方可安全保留原速率。
         * 与 (5) 的回读失败区分开——后者已经重配过寄存器，实际状态不确定。 */
        return -4;
    }

    /* (1) 有界等待最后一位真正发完。HardwareSerial::write() 只等到发送数据
     *     寄存器空（USART_TDBE_FLAG），flush() 清的是 RX 缓冲——两者都不能
     *     用来等待 TX 完成。USART_TDC_FLAG 才是移位器送完。超时不切换。 */
    t0 = millis();
    while (usart_flag_get(u, USART_TDC_FLAG) == RESET)
    {
        if ((uint32_t)(millis() - t0) >= BT_BX_TX_DRAIN_MS)
        {
            return -1;
        }
    }

    /* (2) 短临界区：停接收中断，清掉旧 RX 残留，避免旧字节混入新速率的观测 */
    usart_interrupt_enable(u, USART_RDBF_INT, FALSE);
    BT_SERIAL.flush();

    /* (3) 重配（begin 内部重新使能 RDBF 中断与 NVIC） */
    BT_SERIAL.begin(baud);

    /* (4) 恢复 ISR hook。begin() 不清回调，这里显式重申所有权，使
     *     "切速后中断通路仍归 OTA 会话"成为可复核事实而非隐含假设。 */
    BT_SERIAL.attachInterrupt(ble_isr_hook);

    /* (5) 回读实际速率：分频器必须真的落到目标档，否则视为未切换。
     *     注意这里返回的是 **-3（重配后实际状态不确定）**，不是「切换失败且
     *     硬件未变」：寄存器可能已按新速率工作，只是回读/校验不通过。调用方
     *     必须按不确定处理，不得继续依赖旧速率。 */
    actual = bt_bx_actual_baud(u);
    if (actual == 0u)
    {
        return -3;
    }
    tol = baud / 33u; /* 允许约 3% 整数分频量化 */
    if (actual < baud - tol || actual > baud + tol)
    {
        return -3;
    }
    return 0;
}

/* 仅在确认 OTA 空闲后清 demux 残留：不重建 session、不动 durable staging。
 * HAL_Bluetooth 本就是 UART demux 与调度入口的所有者（见文件顶部职责分工）。 */
static void bt_bx_op_reset_demux(void *io)
{
    (void)io;
    ota_ble_demux_init(&s_ble_session.demux);
}

static void bt_bx_platform_init(uint32_t baud)
{
    s_bt_bx_ops.io = NULL;
    s_bt_bx_ops.now_ms = bt_bx_op_now_ms;
    s_bt_bx_ops.busy = bt_bx_op_busy;
    s_bt_bx_ops.epoch = bt_bx_op_epoch;
    s_bt_bx_ops.rtt_read = bt_bx_op_rtt_read;
    s_bt_bx_ops.rtt_write = bt_bx_op_rtt_write;
    s_bt_bx_ops.at_write = bt_bx_op_at_write;
    s_bt_bx_ops.mcu_set_baud = bt_bx_op_mcu_set_baud;
    s_bt_bx_ops.reset_demux = bt_bx_op_reset_demux;
    bt_bx_init(&s_bt_bx, &s_bt_bx_ops, baud);
    s_bt_bx_ready = 1;
}

/* 空闲期 RX 观测入口：逐字节进采集缓冲，静默窗口到期后封存成记录。 */
static void bt_bx_platform_capture(uint8_t byte)
{
    if (!s_bt_bx_ready || bt_bx_op_busy(NULL))
    {
        return;
    }
    bt_bx_capture(&s_bt_bx, byte);
}

static void bt_bx_platform_poll(void)
{
    if (s_bt_bx_ready)
    {
        bt_bx_poll(&s_bt_bx);
#if CONFIG_OTA_BLE_PROFILE
        if (!bt_bx_op_busy(NULL) && s_bt_bx.rate_state == BT_BX_STATE_KNOWN &&
            s_bt_bx.ev_valid && s_bt_bx.ev_epoch == s_ble_epoch &&
            s_bt_bx.known_baud == s_bt_bx.mcu_baud && !g_p34_retention_error)
        {
            uint32_t word = p34_baud_word(s_bt_bx.known_baud);
            uint32_t previous = ertc_bpr_data_read(ERTC_DT20);
            if (previous != 0u && p34_baud_from_word(previous) == 0u)
            {
                g_p34_retention_error = 1u;
            }
            else if (word != 0u && previous != word)
            {
                /* DT1 belongs to RTC initialization. Only the unused DT20
                 * stores a checked development baud hint; never reset RTC. */
                ertc_bpr_data_write(ERTC_DT20, word);
                g_p34_retained_word = ertc_bpr_data_read(ERTC_DT20);
                g_p34_retention_error = g_p34_retained_word == word ? 0u : 2u;
                SEGGER_RTT_printf(0, "P34BAUD: retained=%lu error=%lu\r\n",
                    (unsigned long)p34_baud_from_word(g_p34_retained_word),
                    (unsigned long)g_p34_retention_error);
            }
        }
#endif
    }
}
#endif /* CONFIG_BT_BAUD_EXPERIMENT */

/* 排空 BT 串口 HW 环（空闲路径）。会话 ISR 活跃期间由 ISR 独占消费
 * HW 环（tail 竞争防护），本函数自退；处理 BEGIN 置位 ISR 标志后
 * 循环条件立即失效，剩余字节由 ISR 搬运。 */
static void bt_rx_service(void)
{
    while (!ota_ble_session_isr_active(&s_ble_session) &&
           BT_SERIAL.available() > 0)
    {
        char c = (char)BT_SERIAL.read();
        lastRxTick = millis();
#if BT_USE_TRANSPARENT
        DEBUG_SERIAL.write(c);
#endif
        /* 会话活跃（ISR 标志尚未置位的过渡窗口）时文本字节丢弃 */
        ota_ble_session_feed_idle(
            &s_ble_session,
            ota_ble_session_active(&s_ble_session) ? NULL : bt_text_sink,
            NULL, (uint8_t)c);
#if CONFIG_BT_BAUD_EXPERIMENT
        /* 实验构型旁路镜像：只观测空闲期文本字节，不改变上面的 demux
         * 语义（喂 session 的调用保持逐字节不变）。busy（会话活跃或 ISR
         * 活跃）时 bt_bx_platform_capture 自行拒绝，不会把 OTA 帧混入观测。 */
        bt_bx_platform_capture((uint8_t)c);
#endif
    }
}

/* ================= HAL 接口 ================= */

void HAL::BT_Init()
{
    ota_ble_env_t env;
    uint32_t start;
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    start = p34_clock();
    __NOP(); __NOP(); __NOP(); __NOP();
    s_p34_clock_ok = p34_clock() != start ? 1u : 0u;
#if CONFIG_OTA_BLE_PROFILE
    uint32_t selected_baud;
    crm_periph_clock_enable(CRM_PWC_PERIPH_CLOCK, TRUE);
    pwc_battery_powered_domain_access(TRUE);
    g_p34_retained_word = ertc_bpr_data_read(ERTC_DT20);
    selected_baud = p34_baud_from_word(g_p34_retained_word);
    g_p34_retention_error = g_p34_retained_word != 0u && selected_baud == 0u ? 1u : 0u;
    g_p34_boot_baud = selected_baud != 0u ? selected_baud : CONFIG_BT_BAUD_EXPERIMENT_RATE;
#endif

#if CONFIG_BT_BAUD_EXPERIMENT
    /* P3-4 实验构型：上电起始速率（默认 115200，即生产基线）。这是**起始**
     * 速率而非固定档位——四档切换全部在运行期经 RTT 控制通道完成，因此只需
     * 一份实验镜像，不需要为每个速率单独烧录。 */
#if CONFIG_OTA_BLE_PROFILE
    BT_SERIAL.begin(g_p34_boot_baud);
#else
    BT_SERIAL.begin(CONFIG_BT_BAUD_EXPERIMENT_RATE);
#endif
#else
    BT_SERIAL.begin(CONFIG_BT_FIXED_BAUD);
#endif
    //pinMode(CONFIG_BT_EN_PIN, OUTPUT);
#ifdef CONFIG_BT_STATE_PIN
    pinMode(CONFIG_BT_STATE_PIN, INPUT);
#endif
    BT_NormalMode();
		delay_ms(50);
		BT_SetName();
		delay_ms(50);
    CONFIG_DEBUG_SERIAL.print("Bluetooth library v. ");
    CONFIG_DEBUG_SERIAL.print(TinyBTPlus::libraryVersion());
    CONFIG_DEBUG_SERIAL.println(" by Eitan Su");

    memset(&env, 0, sizeof(env));
    env.now_ms = ble_env_now_ms;
    env.send = ble_env_send;
    env.bcb_confirmed = ble_env_bcb_confirmed;
    env.ota_disabled = ble_env_ota_disabled;
    env.overlay_acquire = ble_env_overlay_acquire;
    env.overlay_release = ble_env_overlay_release;
    env.overlay_workspace = ble_env_overlay_workspace;
    env.get_device = ble_env_get_device;
    env.info_provider = ble_env_info_provider;
    env.activate_staged = ble_env_activate_staged;
    env.system_reset = ble_env_system_reset;
    HAL::OTA_StagingGetIo(&s_ble_staging_io);
#if CONFIG_OTA_BLE_PROFILE
    s_p34_staging_io = s_ble_staging_io;
    s_ble_staging_io.read = p34_staging_read;
    s_ble_staging_io.program = p34_staging_program;
    s_ble_staging_io.erase_4k = p34_staging_erase;
    if (s_p34_staging_io.verify != NULL)
    {
        s_ble_staging_io.verify = p34_staging_verify;
    }
#endif
    env.staging_io = &s_ble_staging_io;
#if defined(P34_OTA_PIPELINE_SYNC) && P34_OTA_PIPELINE_SYNC
    if (ota_pipeline_sync_init(&s_ble_pipeline_io, &s_ble_staging_io) == OTA_PIPELINE_OK)
        env.pipeline_io = &s_ble_pipeline_io;
#endif
    ota_ble_session_init(&s_ble_session, &env);
    BT_SERIAL.attachInterrupt(ble_isr_hook);
#if CONFIG_BT_BAUD_EXPERIMENT
    /* 会话与 ISR 通路就绪后，再挂实验控制面（初始状态 UNKNOWN：未取得
     * 任何查询证据前禁止盲目设置模块速率）。 */
#if CONFIG_OTA_BLE_PROFILE
    bt_bx_platform_init(g_p34_boot_baud);
    SEGGER_RTT_printf(0, "P34BOOT: requested=%lu actual=%lu retained=%lu error=%lu clock=%lu\r\n",
        (unsigned long)g_p34_boot_baud, (unsigned long)bt_bx_actual_baud(BT_SERIAL.getUSART()),
        (unsigned long)p34_baud_from_word(g_p34_retained_word),
        (unsigned long)g_p34_retention_error, (unsigned long)s_p34_clock_ok);
#else
    bt_bx_platform_init(CONFIG_BT_BAUD_EXPERIMENT_RATE);
#endif
#endif
}

void HAL::BT_SleepMode()
{
	//digitalWrite(CONFIG_BT_EN_PIN, HIGH);
	CONFIG_DEBUG_SERIAL.println("Bt: OFF\r\n");
}

void HAL::BT_NormalMode()
{
	//digitalWrite(CONFIG_BT_EN_PIN, LOW);
	CONFIG_DEBUG_SERIAL.println("Bt: ON\r\n");
}

void HAL::BT_SetName()
{
#if CONFIG_BT_BAUD_EXPERIMENT || defined(P34_OTA_FIXED_CONFIG)
    /* 实验构型：抑制自动改名。AT+NAME=XTrace 是实验期间的非预期 UART TX，
     * 且会改变模块配置，违反单变量纪律。抑制点放在本函数内以覆盖全部调用者
     * （当前仅 BT_Init）。生产构型行为不变。 */
    return;
#else
    BT_SERIAL.printf("AT+NAME=XTrace\r\n");
#endif
}

void HAL::BT_printf(char *format, ...)
{
#if CONFIG_BT_BAUD_EXPERIMENT || defined(P34_OTA_FIXED_CONFIG)
    /* 实验构型：抑制遗留文本出口，覆盖 HAL::Init 的 EEPROM 值上报
     * （HAL.cpp 的三处 BT_printf 调用）以及后续任何调用者。
     * 生产构型行为不变。 */
    (void)format;
    return;
#else
    char String[100];
    va_list arg;
    va_start(arg, format);
    vsprintf(String, format, arg);
    va_end(arg);
    BT_SERIAL.print(String);
#endif
}

void HAL::BT_Update()
{
#if CONFIG_BT_BUF_OVERLOAD_CHK && !BT_USE_TRANSPARENT
    int available = BT_SERIAL.available();
    DEBUG_SERIAL.printf("BT: Buffer available = %d", available);
    if(available >= SERIAL_RX_BUFFER_SIZE / 2)
    {
        DEBUG_SERIAL.print(", maybe overload!");
    }
    DEBUG_SERIAL.println();
#endif
    /* OTA 会话活跃期关闭 200ms X-Trace 周期上行（合同 §5.1：
     * 活跃期上行只允许 ACK/事件帧）。实验构型整体关闭：该文本心跳不是
     * AT 命令，会污染模块应答观测，且实验期间不跑 OTA 文本协议。 */
    if (!ota_ble_session_active(&s_ble_session))
    {
#if !CONFIG_BT_BAUD_EXPERIMENT && !defined(P34_OTA_FIXED_CONFIG)
        BT_SERIAL.printf("X-Trace\r\n");
#endif
    }
    bt_rx_service();

#if BT_USE_TRANSPARENT
    while (DEBUG_SERIAL.available() > 0)
    {
        BT_SERIAL.write(DEBUG_SERIAL.read());
    }
#endif
}

/* P3-1 BLE OTA 泵（HAL.cpp 以 CONFIG_OTA_BLE_PUMP_PERIOD_MS 注册） */
void HAL::BT_OtaPump()
{
    (void)s_p34_ack_batch.begin(s_ble_epoch);
#if CONFIG_OTA_BLE_PROFILE
    s_p34_pump_start = p34_clock();
    s_p34_pump_start_ms = millis();
    s_p34_pump_running = 1;
    if (s_p34_profile.active)
    {
        uint32_t gap = s_p34_pump_start - s_p34_last_pump;
        if (SystemCoreClock < 1000u || s_p34_pump_start_ms - s_p34_last_pump_ms >=
            UINT32_MAX / (SystemCoreClock / 1000u))
        {
            s_p34_profile.clock_ok = 0u;
        }
        ++s_p34_profile.pump_entries;
        p34_add_cycles(&s_p34_profile.pump_gap_cycles_lo, &s_p34_profile.pump_gap_cycles_hi, gap);
        if (gap > s_p34_profile.pump_gap_max_cycles)
        {
            s_p34_profile.pump_gap_max_cycles = gap;
        }
        s_p34_last_pump = s_p34_pump_start;
        s_p34_last_pump_ms = s_p34_pump_start_ms;
    }
#endif
    bt_rx_service();
    ota_ble_session_pump(&s_ble_session);
    (void)s_p34_ack_batch.end(millis(), ota_ble_session_active(&s_ble_session) != 0, ble_uart_send);
#if CONFIG_OTA_BLE_PROFILE
    if (s_p34_profile.active && !ota_ble_session_active(&s_ble_session))
    {
        p34_finish(s_ble_session.total_len, 1u);
    }
    else
    {
        p34_record(P34_PUMP_WORK, s_p34_pump_start, s_p34_pump_start_ms, 0u, 0);
    }
    s_p34_pump_running = 0;
#endif
#if CONFIG_BT_BAUD_EXPERIMENT
    bt_bx_platform_poll();
#endif
}

bool HAL::BT_IsConnected()
{
#ifdef CONFIG_BT_STATE_PIN
    return digitalRead(CONFIG_BT_STATE_PIN) == HIGH;
#else
    return (lastRxTick != 0) && ((uint32_t)(millis() - lastRxTick) < 5000);
#endif
}
