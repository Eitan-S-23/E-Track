#include "HAL.h"
#include "EEPROM/EEPROM.h"
#include "EEPROM/eeprom_bcb.h"

static EEPROM at24c;

bool HAL::EEPROM_Init()
{
    CONFIG_DEBUG_SERIAL.print("EEPROM: init...");

    bool success = at24c.Init();
    if(success && EEPROM_Check() != 0)
    {
        success = false;
    }

    CONFIG_DEBUG_SERIAL.println(success ? "success" : "failed");

    return success;
}

void HAL::EEPROM_Read(uint8_t reg, uint8_t* buf, uint16_t len)
{
    at24c.ReadBytes(reg, buf, len);
}

void HAL::EEPROM_WritePage(uint8_t reg, uint8_t* buf, uint16_t len)
{
    // Preserve the legacy void API, but preflight the entire range so a write
    // crossing 0xFF cannot wrap around and modify byte 0x00.
    (void)at24c.WriteBuffer(reg, buf, len);
}

void HAL::EEPROM_Write(uint8_t reg, uint8_t buf)
{
    at24c.WriteByte(reg, buf);
}

bool HAL::EEPROM_WriteBufferSafe(uint8_t reg, const uint8_t* buf, uint16_t len)
{
    // P0-4: OTA BCB 安全写路径 = 驱动层 WriteBuffer（逐 8B 页 + ACK polling
    // ≤10ms + 全块读回比对，契约 §3.3）。HAL 旧 WriteByte/WritePage 仍保留
    // void 签名供既有探活用，OTA 链路改用本安全 API。
    return at24c.WriteBuffer(reg, buf, len);
}

bool HAL::EEPROM_ReadBufferSafe(uint8_t reg, uint8_t* buf, uint16_t len)
{
    return at24c.ReadBytes(reg, buf, len);
}

uint8_t HAL::EEPROM_Check(void)
{
    // General writes reject byte 0xFF. Only this initialization path may
    // create the reserved 0x55 marker, with ACK polling and readback verify.
    return at24c.EnsureInitMagic() ? 0 : 1;
}

#if CONFIG_EEPROM_BCB_STRESS
// P0-4: OTA BCB 真机压测（契约 §3.2/§3.3/§3.4）。
// CONFIG_EEPROM_BCB_STRESS=1 时由 HAL_Init 末尾调用；用 BCB-A/B 两块区
// （0x00/0x40，各 64B）做安全写(逐 8B 页 + ACK polling + 读回比对)+仲裁
// +commit 往返，1000 次零错为验收，输出经 SEGGER_RTT_printf(通道0)供 J-Link RTT 取证
// （CONFIG_DEBUG_SERIAL=Serial5 UART，RTT logger 抓不到，故统一用 RTT，与 App.cpp
//  RTTCMD、LiveMap stat 行的项目惯例一致）。
// 内嵌于本文件（而非独立编译单元）以复用 HAL_EEPROM 已在 Keil 工程内的
// --cpp11 编译配置，避免新增页面组的 --cpp11 坑与 build_f435 -NewSources 同名 .o 冲突。
extern "C" {
    static int bcb_app_write(uint8_t reg, const uint8_t* buf, uint16_t len)
    {
        return HAL::EEPROM_WriteBufferSafe(reg, buf, len) ? 0 : -1;
    }
    static int bcb_app_read(uint8_t reg, uint8_t* buf, uint16_t len)
    {
        return HAL::EEPROM_ReadBufferSafe(reg, buf, len) ? 0 : -1;
    }
}

void HAL::EEPROM_BCBStress_Run(uint32_t iterations)
{
    static const bcb_hal_t hal = { bcb_app_write, bcb_app_read };

    SEGGER_RTT_printf(0, "BCBSTRESS: start %lu iters\r\n", (unsigned long)iterations);

    // 先仲裁出当前活动块（首次通常双坏→NONE，则写初始 IDLE bootstrap）。
    bcb_arbiter_result_t active = bcb_arbiter(&hal, NULL);
    bcb_t cur;
    if(active == BCB_ARBITER_A || active == BCB_ARBITER_B)
    {
        bcb_arbiter_result_t confirmed = bcb_arbiter(&hal, &cur);
        if(confirmed != active)
        {
            SEGGER_RTT_printf(0, "BCBSTRESS: initial arbiter read FAIL%c%c", 13, 10);
            return;
        }
    }
    else
    {
        bcb_make_idle(&cur, 20700u);
        if(bcb_commit(&hal, BCB_ARBITER_NONE, &cur) != BCB_COMMIT_OK)
        {
            SEGGER_RTT_printf(0, "BCBSTRESS: bootstrap commit FAIL\r\n");
            return;
        }
        active = bcb_arbiter(&hal, &cur);
        if(active != BCB_ARBITER_A && active != BCB_ARBITER_B)
        {
            SEGGER_RTT_printf(0, "BCBSTRESS: bootstrap arbiter NONE\r\n");
            return;
        }
    }

    // Preserve the logical BCB contents so the stress mode never leaves the
    // device in APPLYING/STAGED after the measurement completes.
    bcb_t baseline = cur;
    uint32_t ok = 0, fail = 0;
    for(uint32_t i = 0; i < iterations; i++)
    {
        uint16_t expected_seq = (uint16_t)(cur.seq + 1u);
        // Caller supplies state only. A stale seq proves the core owns seq+1.
        bcb_t next = cur;
        next.seq = cur.seq;
        next.state = (i & 1) ? BCB_STATE_APPLYING : BCB_STATE_STAGED;
        next.copy_phase = (i & 1) ? BCB_COPY_APPLY : BCB_COPY_NONE;
        next.resume_block = (uint16_t)(i & 0x1F);

        int rc = bcb_commit(&hal, active, &next);
        if(rc != BCB_COMMIT_OK)
        {
            fail++;
            SEGGER_RTT_printf(0, "BCBSTRESS: i=%lu commit rc=%d\r\n",
                              (unsigned long)i, rc);
            active = bcb_arbiter(&hal, &cur);
            if(active != BCB_ARBITER_A && active != BCB_ARBITER_B)
            {
                SEGGER_RTT_printf(0, "BCBSTRESS: arbiter lost, abort\r\n");
                break;
            }
            continue;
        }

        active = bcb_arbiter(&hal, &cur);
        if(active != BCB_ARBITER_A && active != BCB_ARBITER_B)
        {
            fail++;
            SEGGER_RTT_printf(0, "BCBSTRESS: i=%lu arbiter NONE after commit\r\n",
                              (unsigned long)i);
            break;
        }
        if(cur.seq != expected_seq)
        {
            fail++;
            SEGGER_RTT_printf(0, "BCBSTRESS: i=%lu seq mismatch got=%u want=%u\r\n",
                              (unsigned long)i, cur.seq, expected_seq);
        }
        ok++;
    }

    if(active == BCB_ARBITER_A || active == BCB_ARBITER_B)
    {
        int restore_rc = bcb_commit(&hal, active, &baseline);
        if(restore_rc != BCB_COMMIT_OK)
        {
            fail++;
            SEGGER_RTT_printf(0, "BCBSTRESS: restore rc=%d\r\n", restore_rc);
        }
        else
        {
            bcb_arbiter_result_t restored = bcb_arbiter(&hal, &cur);
            if((restored != BCB_ARBITER_A && restored != BCB_ARBITER_B) ||
               cur.state != baseline.state ||
               cur.copy_phase != baseline.copy_phase ||
               cur.resume_block != baseline.resume_block ||
               cur.cur_vcode != baseline.cur_vcode)
            {
                fail++;
                SEGGER_RTT_printf(0, "BCBSTRESS: restore verification FAIL\r\n");
            }
        }
    }

    SEGGER_RTT_printf(0, "BCBSTRESS: done ok=%lu fail=%lu / %lu\r\n",
                      (unsigned long)ok, (unsigned long)fail,
                      (unsigned long)iterations);
}
#endif /* CONFIG_EEPROM_BCB_STRESS */
