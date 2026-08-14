#include "boot_fw_header.h"
#include "boot_handoff.h"
#if defined(P1_6_TEST_ENABLE)
#include "boot_p1_6_test.h"
#endif
#include "boot_platform.h"
#include "boot_recovery.h"
#include "boot_state_machine.h"

#include "EEPROM/eeprom_bcb.h"

#include <stdint.h>
#include <string.h>

#if !defined(OTA_TARGET_BOOT) || defined(OTA_TARGET_APP)
#error "Boot sources must only be compiled by the OTA Boot target"
#endif

volatile int32_t g_boot_p1_bcb_result;
volatile int32_t g_boot_p1_qspi_result;
volatile int32_t g_boot_p1_app_result;
volatile int32_t g_boot_p1_recovery_result;
volatile int32_t g_boot_p1_state_status;
volatile uint32_t g_boot_p1_state_action;
volatile uint32_t g_boot_p1_state_value;
volatile uint32_t g_boot_p1_state_resume;

static int eeprom_read(uint8_t address, uint8_t *dst, uint16_t len)
{
    return boot_platform_eeprom_read(address, dst, len);
}

static int eeprom_write(uint8_t address, const uint8_t *src, uint16_t len)
{
    return boot_platform_eeprom_write(address, src, len);
}

#if defined(BOOT_HANDOFF_TEST_CLEAR_BCB)
static int clear_test_bcb(void)
{
    uint8_t blank[BCB_SIZE];

    memset(blank, 0xFF, sizeof(blank));
    if (eeprom_write(BCB_A_ADDR, blank, sizeof(blank)) != 0)
    {
        return -1;
    }
    return eeprom_write(BCB_B_ADDR, blank, sizeof(blank));
}
#endif

static int state_external_read(void *ctx, uint32_t address,
                               uint8_t *dst, size_t len)
{
    (void)ctx;
    return boot_platform_qspi_read(address, dst, len);
}

static int state_internal_read(void *ctx, uint32_t address,
                               uint8_t *dst, size_t len)
{
    (void)ctx;
    return boot_platform_flash_read(address, dst, len);
}

static int state_internal_erase(void *ctx, uint32_t address)
{
    (void)ctx;
    return boot_platform_flash_erase_4k(address);
}

static int state_internal_program(void *ctx, uint32_t address,
                                  const uint8_t *src, size_t len)
{
    (void)ctx;
    return boot_platform_flash_program(address, src, len);
}

static void state_log(void *ctx, const char *text)
{
    (void)ctx;
    boot_platform_log(text);
}

static void publish_outcome(const boot_state_outcome_t *outcome)
{
    if (outcome == NULL)
    {
        return;
    }
    g_boot_p1_state_status = outcome->status;
    g_boot_p1_state_action = (uint32_t)outcome->action;
    g_boot_p1_state_value = outcome->bcb.state;
    g_boot_p1_state_resume = outcome->bcb.resume_block;
    g_boot_p1_app_result = outcome->action == BOOT_STATE_ACTION_JUMP_APP
                               ? BOOT_FW_OK
                               : BOOT_FW_ERR_ARGUMENT;
}

static int receive_physical_recovery(const boot_state_io_t *io,
                                     boot_state_outcome_t *outcome)
{
    /* 进入此函数说明状态机已判定 App/backup/recovery 全部不可用。
     * 契约 PLAN-OTA.md §0.2：裸恢复必须有物理在场证明，故在此等待用户
     * 持续按住恢复键 >=3s（BOOT_RECOVERY_HOLD_MS）后才开始 YMODEM 接收。 */
    while (!boot_platform_recovery_key_held())
    {
        boot_platform_log("BOOT: hold recovery key for 3 seconds\r\n");
        boot_platform_delay_ms(100u);
    }

    boot_platform_log("BOOT: physical recovery condition accepted\r\n");
    do
    {
        g_boot_p1_recovery_result = boot_recovery_receive();
    } while (g_boot_p1_recovery_result != 0);

    g_boot_p1_state_status =
        boot_state_machine_accept_physical_recovery(io, outcome);
    publish_outcome(outcome);
    return outcome->action == BOOT_STATE_ACTION_JUMP_APP ? 0 : -1;
}

int main(void)
{
    static const bcb_hal_t bcb_hal = {eeprom_write, eeprom_read};
    boot_state_io_t state_io;
    boot_state_outcome_t outcome;

    g_boot_p1_bcb_result = BCB_ARBITER_ERROR;
    g_boot_p1_qspi_result = -1;
    g_boot_p1_app_result = BOOT_FW_ERR_ARGUMENT;
    g_boot_p1_recovery_result = -1;
    g_boot_p1_state_status = BOOT_STATE_STATUS_ARGUMENT;
    g_boot_p1_state_action = BOOT_STATE_ACTION_HOLD;
    g_boot_p1_state_value = 0xFFFFFFFFu;
    g_boot_p1_state_resume = 0u;

    if (boot_platform_init() != 0)
    {
        boot_platform_hold();
    }

#if defined(P1_6_TEST_ENABLE)
    if (boot_p1_6_process_command() == BOOT_P1_6_HOLD)
    {
        boot_platform_hold();
    }
#endif

#if defined(BOOT_HANDOFF_TEST_CLEAR_BCB)
    if (clear_test_bcb() != 0)
    {
        boot_platform_log("BOOT: test BCB clear failed\r\n");
        boot_platform_hold();
    }
#endif

    memset(&state_io, 0, sizeof(state_io));
    state_io.bcb_hal = &bcb_hal;
    state_io.external_read = state_external_read;
    state_io.internal_read = state_internal_read;
    state_io.internal_erase_4k = state_internal_erase;
    state_io.internal_program = state_internal_program;
    state_io.log = state_log;

    /* P1-7 开机键冲突修复：恢复模式入口只由状态机判定，开机不再无条件预检恢复键。
     * PA15 同时是编码器 push 键（整机唯一物理开机键）与 boot 恢复键，而电源自锁
     * （configure_power_hold 拉低 PD2 1000ms 后拉高）要求开机时按键必须持续按住
     * >=1s。原先在状态机之前调用 boot_platform_recovery_key_held() 做无条件预检，
     * 该时刻按键必然处于按下态，于是直接进入 receive_physical_recovery() 的
     * YMODEM 等待循环（无超时无出口），表现为 USB 供电按开机键数十分钟不开机；
     * 而 J-Link 直供绕过自锁、PA15 保持上拉高，反而能正常启动。
     * 契约 PLAN-OTA.md §4/§5.3：物理恢复的"按住 >=3s"是 App/backup/recovery 全部
     * 无效之后才要求的必要条件，不是开机首要检测项。故此处只走正常引导路径，
     * 仅当 outcome.action 判定为 PHYSICAL_RECOVERY 时才等待按键（见下方分支），
     * 此时设备已完成电源自锁，用户可松开按键再按 3 秒确认物理在场。 */
    g_boot_p1_qspi_result = boot_platform_qspi_init();
    state_io.external_available = g_boot_p1_qspi_result == 0;
    if (!state_io.external_available)
    {
        boot_platform_log("BOOT: QSPI unavailable, external slot branch skipped\r\n");
    }

    g_boot_p1_bcb_result = bcb_arbiter(&bcb_hal, NULL);
    g_boot_p1_state_status = boot_state_machine_run(&state_io, &outcome);
    publish_outcome(&outcome);
    if (outcome.action == BOOT_STATE_ACTION_PHYSICAL_RECOVERY)
    {
#if defined(P1_6_TEST_ENABLE)
        boot_p1_6_checkpoint(OTA_P1_6_CP_PHYSICAL_RECOVERY,
                             (uint32_t)outcome.status,
                             outcome.bcb.state);
#endif
        if (receive_physical_recovery(&state_io, &outcome) != 0)
        {
            boot_platform_hold();
        }
    }

    if (outcome.action == BOOT_STATE_ACTION_JUMP_APP)
    {
        if (outcome.bcb.state == BCB_STATE_TEST_BOOT &&
            boot_platform_watchdog_start() != 0)
        {
            boot_platform_log("BOOT: TEST_BOOT watchdog start failed\r\n");
            boot_platform_hold();
        }
#if defined(BOOT_HANDOFF_TEST_INJECT_PENDING)
        boot_handoff_test_inject_pending();
#endif
        boot_handoff_to_app();
    }

    boot_platform_log("BOOT: no valid App handoff action\r\n");
    boot_platform_hold();
    return 0;
}
