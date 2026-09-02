#include "HAL.h"
#include "Bluetooth/Bluetooth.h"
#include "HAL/HAL_OTA_Backup.h"
#include "HAL/HAL_OTA_Package.h"
#include "HAL/HAL_OTA_Staging.h"
#include "OTA/ota_ble_session.h"
#include "OTA/ota_layout.h"
#include "boot_fw_header.h"
#include "EEPROM/eeprom_bcb.h"
#include <stdio.h>
#include <stdarg.h>
#include <stddef.h>
#include <string.h>

#define BT_SERIAL             CONFIG_BT_SERIAL
#define DEBUG_SERIAL          CONFIG_DEBUG_SERIAL
#define BT_USE_TRANSPARENT    CONFIG_BT_USE_TRANSPARENT

static TinyBTPlus bt;
static uint32_t lastRxTick = 0;

/* ================= P3-1 BLE OTA 传输接线 =================
 * 职责分工（合同 OTA-XC-BLE-LIFECYCLE）：HAL_Bluetooth 拥有 UART demux
 * 与调度入口；ota_ble_session 拥有帧/会话状态机；ota_staging 继续拥有
 * durable staging 事实。本文件只做注入接线，不复制任何协议状态。 */
static ota_ble_session_t s_ble_session;
static ota_staging_io_t s_ble_staging_io;

/* 设备身份缓存：首次使用时校验当前镜像 fw_header 并计算整镜像
 * SHA-256（约百毫秒量级），运行期身份不变故缓存复用；
 * get_device 与 INFO provider 同源（单份身份链，P3-2 增强时替换此处）。 */
static bool s_ble_device_ready = false;
static ota_sd_device_t s_ble_device;
static uint8_t s_ble_image_sha256[32];

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

static bool ble_device_init(void)
{
    boot_image_reader_t reader;
    boot_fw_expectations_t expectations;
    boot_fw_header_t header;
    boot_sha256_ctx_t sha;
    uint32_t offset = 0u;
    uint8_t block[256];

    if (s_ble_device_ready)
    {
        return true;
    }

    memset(&s_ble_device, 0, sizeof(s_ble_device));
    s_ble_device.hardware_rev = 1u;
    s_ble_device.layout_id = 1u;
    s_ble_device.boot_version = 1u;

    reader.read = ble_current_image_read;
    reader.ctx = NULL;
    boot_fw_default_expectations(&expectations);
    if (boot_fw_header_validate(&reader, &expectations, &header) != BOOT_FW_OK)
    {
        return false;
    }
    s_ble_device.current_vcode = header.version_code;

    boot_sha256_init(&sha);
    while (offset < header.image_len)
    {
        uint32_t take = header.image_len - offset;
        if (take > sizeof(block))
        {
            take = sizeof(block);
        }
        if (ble_current_image_read(NULL, offset, block, take) != 0)
        {
            return false;
        }
        boot_sha256_update(&sha, block, take);
        offset += take;
    }
    boot_sha256_final(&sha, s_ble_image_sha256);
    memcpy(s_ble_device.base_image_sha8, s_ble_image_sha256,
           sizeof(s_ble_device.base_image_sha8));

    s_ble_device_ready = true;
    return true;
}

/* ---- ota_ble_env_t 注入实现 ---- */

static uint32_t ble_env_now_ms(void)
{
    return millis();
}

static int ble_env_send(const uint8_t *frame, uint16_t len)
{
    uint16_t i;

    for (i = 0u; i < len; ++i)
    {
        BT_SERIAL.write(frame[i]);
    }
    return 0;
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
    return HAL::OTA_OverlayAcquireBle() ? 1 : 0;
}

static void ble_env_overlay_release(void)
{
    HAL::OTA_OverlayReleaseBle();
}

static uint8_t *ble_env_overlay_workspace(uint32_t *out_size)
{
    return HAL::OTA_OverlayGetWorkspace(out_size);
}

static int ble_env_get_device(ota_sd_device_t *out_device)
{
    if (out_device == NULL || !ble_device_init())
    {
        return 0;
    }
    *out_device = s_ble_device;
    return 1;
}

static int ble_env_info_provider(ota_ble_info_t *out_info)
{
    if (out_info == NULL || !ble_device_init())
    {
        return 0;
    }
    memset(out_info, 0, sizeof(*out_info));
    memcpy(out_info->model, "X-Track", sizeof("X-Track"));
    out_info->hw_rev = s_ble_device.hardware_rev;
    out_info->layout_id = s_ble_device.layout_id;
    out_info->boot_ver = s_ble_device.boot_version;
    out_info->cur_vcode = s_ble_device.current_vcode;
    memcpy(out_info->image_sha256, s_ble_image_sha256,
           sizeof(out_info->image_sha256));
    return 1;
}

/* UART ISR 回调（HardwareSerial 每字节入 HW 环后调用）：
 * 会话活跃期把 HW 环即时搬空进 overlay RX 环（HW 环 tail 仅 ISR 动），
 * 使 512B HW 环在任何波特率下都不积压；空闲期立刻返回，字节留给
 * 文本协议路径。 */
static void ble_isr_hook(HardwareSerial *serial)
{
    if (!ota_ble_session_isr_active(&s_ble_session))
    {
        return;
    }
    while (serial->available() > 0)
    {
        ota_ble_session_isr_feed(&s_ble_session,
                                 (uint8_t)serial->read());
    }
}

/* 文本协议出口：demux 判定的非帧字节喂 TinyBTPlus（会话活跃期
 * session 层不会调用本 sink，合同 §5.1 活跃期文本零调用） */
static void bt_text_sink(void *ctx, uint8_t byte)
{
    (void)ctx;
    bt.encode((char)byte);
}

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
    }
}

/* ================= HAL 接口 ================= */

void HAL::BT_Init()
{
    ota_ble_env_t env;

    BT_SERIAL.begin(115200);
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
    HAL::OTA_StagingGetIo(&s_ble_staging_io);
    env.staging_io = &s_ble_staging_io;
    ota_ble_session_init(&s_ble_session, &env);
    BT_SERIAL.attachInterrupt(ble_isr_hook);
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
    BT_SERIAL.printf("AT+NAME=XTrace\r\n");
}

void HAL::BT_printf(char *format, ...)
{
    char String[100];
    va_list arg;
    va_start(arg, format);
    vsprintf(String, format, arg);
    va_end(arg);
    BT_SERIAL.print(String);
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
     * 活跃期上行只允许 ACK/事件帧） */
    if (!ota_ble_session_active(&s_ble_session))
    {
        BT_SERIAL.printf("X-Trace\r\n");
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
    bt_rx_service();
    ota_ble_session_pump(&s_ble_session);
}

bool HAL::BT_IsConnected()
{
#ifdef CONFIG_BT_STATE_PIN
    return digitalRead(CONFIG_BT_STATE_PIN) == HIGH;
#else
    return (lastRxTick != 0) && ((uint32_t)(millis() - lastRxTick) < 5000);
#endif
}
