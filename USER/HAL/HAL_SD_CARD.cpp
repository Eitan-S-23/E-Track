#include "HAL.h"
#include "Config/Config.h"
#include "SdFat.h"
#include "at32_sdio.h"
#include "SEGGER_RTT.h"

/* SD 多块读自检实验开关：开机后、文件系统挂载前，依次验证
 *   A) 8x 单块 CMD17 基线
 *   C) CMD18 多块读 + 数据完成后同步 CMD12（修复后的 sd_mult_blocks_read）
 * 结果经 RTT 输出。判定修复生效的标准：C 行 ret=0 且 match=1，
 * 且 C-after 行 state=4（tran 态）、singleRead=0。
 * （CMD23 路线已被实测判死刑：本卡对 CMD23 无响应，SCR cmd_support=0。）
 * 自检结束后无条件重新初始化，SD.begin() 再完整初始化一次。
 * 判读完成后应将本开关置 0 并重新编译。 */
#ifndef CONFIG_SD_MULTIBLOCK_SELFTEST
#define CONFIG_SD_MULTIBLOCK_SELFTEST 0
#endif

// Use SDIO instead of SPI
// Note: Non-static to allow USB MSC access (declared as extern in msc_diskio.cpp)
SdFatSdioEX SD;

static bool SD_IsReady = false;
static uint32_t SD_CardSize = 0;

static HAL::SD_CallbackFunction_t SD_EventCallback = nullptr;

/*
 * User provided date time callback function.
 * See SdFile::dateTimeCallback() for usage.
 */
static void SD_GetDateTime(uint16_t* date, uint16_t* time)
{
    // User gets date and time from GPS or real-time
    // clock in real callback function
    HAL::Clock_Info_t clock;
    HAL::Clock_GetInfo(&clock);

    // return date using FAT_DATE macro to format fields
    *date = FAT_DATE(clock.year, clock.month, clock.day);

    // return time using FAT_TIME macro to format fields
    *time = FAT_TIME(clock.hour, clock.minute, clock.second);
}

static bool SD_CheckDir(const char* path)
{
    bool retval = true;
    if(!SD.exists(path))
    {
        CONFIG_DEBUG_SERIAL.printf("SD: Auto create path \"%s\"...", path);
        retval = SD.mkdir(path);
        CONFIG_DEBUG_SERIAL.println(retval ? "success" : "failed");
    }
    return retval;
}

#if CONFIG_SD_MULTIBLOCK_SELFTEST

/* DWT 周期计数器，与 lv_img_decoder.c 的 SD 记账使用同一套寄存器 */
#define SDST_DWT_DEMCR   (*(volatile uint32_t *)0xE000EDFCU)
#define SDST_DWT_CTRL    (*(volatile uint32_t *)0xE0001000U)
#define SDST_DWT_CYCCNT  (*(volatile uint32_t *)0xE0001004U)

static uint32_t SD_SelfTestChecksum(const uint8_t* buf, uint32_t len)
{
    uint32_t sum = 0;
    for(uint32_t i = 0; i < len; i++)
    {
        sum = sum * 31u + buf[i];
    }
    return sum;
}

/* 打印 CMD13 卡状态（bits 12:9 = current_state，4=tran 为正常静止态）
   与单块复读结果，回答"多块读之后卡是否仍然活着" */
static void SD_SelfTestProbe(const char* tag, uint8_t* buf)
{
    uint32_t cardStatus = 0;
    sd_error_status_type ret = sd_status_send(&cardStatus);
    sd_error_status_type retRd = sd_block_read(buf, 0, 512);
    SEGGER_RTT_printf(0, "SDST %s: cmd13 ret=%d state=%u singleRead=%d\r\n",
                      tag, (int)ret, (unsigned)((cardStatus >> 9) & 0xF), (int)retRd);
}

static void SD_MultiBlockSelfTest(void)
{
    /* SDIO DMA 按 32 位字访问，缓冲必须 4 字节对齐 */
    static uint32_t bufWords[4096 / 4];
    uint8_t* buf = (uint8_t*)bufWords;
    uint32_t t0, cycles;
    uint32_t sumA = 0, sum = 0;
    sd_error_status_type ret;
    const uint32_t usDiv = system_core_clock / 1000000u;

    SDST_DWT_DEMCR |= (1UL << 24);
    SDST_DWT_CTRL |= 1UL;

    SEGGER_RTT_printf(0, "SDST: begin\r\n");

    ret = sd_init();
    SEGGER_RTT_printf(0, "SDST init: ret=%d type=%u cmdSupport=0x%x (bit1=CMD23)\r\n",
                      (int)ret, (unsigned)sd_card_info.card_type,
                      (unsigned)sd_card_info.sd_scr_reg.cmd_support);
    if(ret != SD_OK)
    {
        SEGGER_RTT_printf(0, "SDST: init failed, abort\r\n");
        return;
    }

    /* A) 基线：8x 单块 CMD17 读 LBA0..7（已验证路径） */
    t0 = SDST_DWT_CYCCNT;
    for(uint32_t i = 0; i < 8; i++)
    {
        ret = sd_block_read(buf + i * 512, (long long)i * 512, 512);
        if(ret != SD_OK)
        {
            break;
        }
    }
    cycles = SDST_DWT_CYCCNT - t0;
    sumA = SD_SelfTestChecksum(buf, 4096);
    SEGGER_RTT_printf(0, "SDST A(8x CMD17): ret=%d t=%uus sum=0x%08x\r\n",
                      (int)ret, (unsigned)(cycles / usDiv), (unsigned)sumA);

    /* C) CMD18 多块读 + 同步 CMD12（修复验证：期望 ret=0 match=1，
       之后 state=4、singleRead=0） */
    for(uint32_t i = 0; i < 4096 / 4; i++) bufWords[i] = 0;
    t0 = SDST_DWT_CYCCNT;
    ret = sd_mult_blocks_read(buf, 0, 512, 8);
    cycles = SDST_DWT_CYCCNT - t0;
    sum = SD_SelfTestChecksum(buf, 4096);
    SEGGER_RTT_printf(0, "SDST C(CMD18+syncCMD12): ret=%d t=%uus sum=0x%08x match=%d lastCmd=%u lastErr=%d\r\n",
                      (int)ret, (unsigned)(cycles / usDiv), (unsigned)sum,
                      (int)(sum == sumA), (unsigned)sd_last_cmd_get(), (int)sd_last_error_get());
    SD_SelfTestProbe("C-after", buf);

    /* 无条件重新初始化：即使修复失效也不把坏状态留给 SD.begin() */
    ret = sd_init();
    SEGGER_RTT_printf(0, "SDST: final reinit=%d, done\r\n", (int)ret);
}

#endif /* CONFIG_SD_MULTIBLOCK_SELFTEST */

bool HAL::SD_Init()
{
    bool retval = true;

    pinMode(CONFIG_SD_CD_PIN, INPUT_PULLUP);
    if(digitalRead(CONFIG_SD_CD_PIN))
    {
        CONFIG_DEBUG_SERIAL.printf("SD: CARD was not inserted %d",digitalRead(CONFIG_SD_CD_PIN));
        retval = false;
    }

    CONFIG_DEBUG_SERIAL.printf("SD: init...%d",digitalRead(CONFIG_SD_CD_PIN));
    
    // Add delay for card power stabilization
    delay(100);  // Wait 100ms for card to stabilize

#if CONFIG_SD_MULTIBLOCK_SELFTEST
    /* 多块读自检：独立 sd_init 后测 A/B/C 三条读路径并 RTT 报告；
       随后 SD.begin() 内部会重新完整初始化，卡状态与自检结果无关。 */
    SD_MultiBlockSelfTest();
#endif

    // Initialize SDIO card and file system
    retval = SD.begin();

    if(retval)
    {
        SD_CardSize = SD.card()->cardSize();
        SdFile::dateTimeCallback(SD_GetDateTime);
        SD_CheckDir(CONFIG_TRACK_RECORD_FILE_DIR_NAME);
        CONFIG_DEBUG_SERIAL.printf(
            "success, Type: %s, Size: %0.2f GB\r\n",
            SD_GetTypeName(),
            SD_GetCardSizeMB() / 1024.0f
        );

        /* 诊断：打印 SDIO 硬件实际位宽与时钟，确认是否跑在 4 位并行 */
        {
            uint32_t clkdiv = ((uint32_t)SDIOx->clkctrl_bit.clkdiv_h << 8)
                              | (uint32_t)SDIOx->clkctrl_bit.clkdiv_l;
            uint32_t sdioMHz = (system_core_clock / (clkdiv + 2)) / 1000000;
            CONFIG_DEBUG_SERIAL.printf(
                "SDIO HW: busws=%u (0=1bit,1=4bit,2=8bit), clkdiv=%u, sdio_ck=%u MHz, scr_buswidth=0x%x\r\n",
                (unsigned)SDIOx->clkctrl_bit.busws,
                (unsigned)clkdiv,
                (unsigned)sdioMHz,
                (unsigned)sd_scr_bus_width_get()
            );
        }
    }
    else
    {
        CONFIG_DEBUG_SERIAL.printf("failed: 0x%x\r\n", SD.cardErrorCode());
        CONFIG_DEBUG_SERIAL.printf("SDIO last cmd: 0x%x, last error: 0x%x, last response: 0x%08lx\r\n",
                                   sd_last_cmd_get(),
                                   sd_last_error_get(),
                                   sd_last_response_get());
        CONFIG_DEBUG_SERIAL.printf("SCR spec: %u, bus width: 0x%x, SCR raw[0]: 0x%08lx, SCR raw[1]: 0x%08lx\r\n",
                                   sd_scr_spec_get(),
                                   sd_scr_bus_width_get(),
                                   sd_scr_raw_get(0),
                                   sd_scr_raw_get(1));
    }

    SD_IsReady = retval;

    return retval;
}

bool HAL::SD_GetReady()
{
    return SD_IsReady;
}

float HAL::SD_GetCardSizeMB()
{
#   define CONV_MB(size) (size*0.000512f)
    return CONV_MB(SD_CardSize);
}

const char* HAL::SD_GetTypeName()
{
    const char* type = "Unknown";

    if(!SD_CardSize)
    {
        return type;
    }

    uint8_t cardType = SD.card()->type();
    switch (cardType)
    {
    case 0:  // SDIO_STD_CAPACITY_SD_CARD_V1_1
        type = "SD1";
        break;

    case 1:  // SDIO_STD_CAPACITY_SD_CARD_V2_0
        type = "SD2";
        break;

    case 2:  // SDIO_HIGH_CAPACITY_SD_CARD
        type = (SD_CardSize < 70000000) ? "SDHC" : "SDXC";
        break;

    case 3:  // SDIO_MULTIMEDIA_CARD
    case 5:  // SDIO_HIGH_SPEED_MULTIMEDIA_CARD
    case 7:  // SDIO_HIGH_CAPACITY_MMC_CARD
        type = "MMC";
        break;

    default:
        break;
    }

    return type;
}

static void SD_Check(bool isInsert)
{
    if(isInsert)
    {
        bool ret = HAL::SD_Init();

        if(ret && SD_EventCallback)
        {
            SD_EventCallback(true);
        }

        HAL::Audio_PlayMusic(ret ? "DeviceInsert" : "Error");
    }
    else
    {
        SD_IsReady = false;

        if(SD_EventCallback)
        {
            SD_EventCallback(false);
            SD_CardSize = 0;
        }

        HAL::Audio_PlayMusic("DevicePullout");
    }
}

void HAL::SD_SetEventCallback(SD_CallbackFunction_t callback)
{
    SD_EventCallback = callback;
}

void HAL::SD_Update()
{
    bool isInsert = (digitalRead(CONFIG_SD_CD_PIN) == LOW);

    CM_VALUE_MONITOR(isInsert, SD_Check(isInsert));
}
