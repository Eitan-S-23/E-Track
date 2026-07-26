#include "HAL.h"
#include "EEPROM/EEPROM.h"
#include "EEPROM/eeprom_bcb.h"

static EEPROM at24c;

bool HAL::EEPROM_Init()
{
    CONFIG_DEBUG_SERIAL.print("EEPROM: init...");

    bool success = at24c.Init();

    CONFIG_DEBUG_SERIAL.println(success ? "success" : "failed");

    if(EEPROM_Check())
        CONFIG_DEBUG_SERIAL.print("EEPROM: read failed...");

    return success;
}

void HAL::EEPROM_Read(uint8_t reg, uint8_t* buf, uint16_t len)
{
    at24c.ReadBytes(reg, buf, len);
}

void HAL::EEPROM_WritePage(uint8_t reg, uint8_t* buf, uint16_t len)
{
    for(int i = 0; i < len; i++)
    {
       at24c.WriteByte(reg++, buf[i]);
    }
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
    // byte 255 (0xFF) = 0x55 初始化魔数（契约 §0.4/§3.3 保持不动）。
    // 首次上电若非 0x55 则写 0x55 + 读回确认，作为 EEPROM 探活。
    u8 buf;
    EEPROM_Read(255, &buf, 1);
    if((buf) == 0X55)
    {
        return 0;
    }
    else
    {
        EEPROM_Write(255, 0X55);
        delay_ms(5);
        EEPROM_Read(255, &buf, 1);
        if((buf) == 0X55)
            return 0;
        else
            return 1;
    }
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
        bcb_arbiter(&hal, &cur);
    }
    else
    {
        bcb_make_idle(&cur, 20700u);
        // 写入 B（非活动，双坏时任选一块），使 A 成为“另一块”待续。
        if(bcb_commit(&hal, BCB_ARBITER_A, &cur) != 0)
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

    uint32_t ok = 0, fail = 0;
    for(uint32_t i = 0; i < iterations; i++)
    {
        // 模拟 STAGED/APPLYING 原子事务：seq+1 + state/copy_phase 切换 + resume_block。
        bcb_t next = cur;
        next.seq = (uint16_t)(cur.seq + 1u);
        next.state = (i & 1) ? BCB_STATE_APPLYING : BCB_STATE_STAGED;
        next.copy_phase = (i & 1) ? BCB_COPY_APPLY : BCB_COPY_NONE;
        next.resume_block = (uint16_t)(i & 0x1F);

        int rc = bcb_commit(&hal, active, &next);
        if(rc != 0)
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
        if(cur.seq != next.seq)
        {
            fail++;
            SEGGER_RTT_printf(0, "BCBSTRESS: i=%lu seq mismatch got=%u want=%u\r\n",
                              (unsigned long)i, cur.seq, next.seq);
        }
        ok++;
    }

    SEGGER_RTT_printf(0, "BCBSTRESS: done ok=%lu fail=%lu / %lu\r\n",
                      (unsigned long)ok, (unsigned long)fail,
                      (unsigned long)iterations);
}
#endif /* CONFIG_EEPROM_BCB_STRESS */
