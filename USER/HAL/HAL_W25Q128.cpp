#include "HAL/HAL.h"
#include "W25Q128/qspi_cmd_en25qh128a.h"

/**
  * @brief  qspi config
  * @param  none
  * @retval none
  */
void qspi_config(void)
{
	gpio_init_type gpio_init_struct;

  /* enable the qspi clock */
  crm_periph_clock_enable(CRM_QSPI1_PERIPH_CLOCK, TRUE);

  /* enable the pin clock */
  crm_periph_clock_enable(CRM_GPIOB_PERIPH_CLOCK, TRUE);
  crm_periph_clock_enable(CRM_GPIOC_PERIPH_CLOCK, TRUE);

  /* set default parameter */
  gpio_default_para_init(&gpio_init_struct);

  /* configure the io0 gpio */
  gpio_init_struct.gpio_drive_strength = GPIO_DRIVE_STRENGTH_STRONGER;
  gpio_init_struct.gpio_out_type  = GPIO_OUTPUT_PUSH_PULL;
  gpio_init_struct.gpio_mode = GPIO_MODE_MUX;
  gpio_init_struct.gpio_pins = GPIO_PINS_9;
  gpio_init_struct.gpio_pull = GPIO_PULL_NONE;
  gpio_init(GPIOC, &gpio_init_struct);
  gpio_pin_mux_config(GPIOC, GPIO_PINS_SOURCE9, GPIO_MUX_9);

  /* configure the io1 gpio */
  gpio_init_struct.gpio_pins = GPIO_PINS_10;
  gpio_init(GPIOC, &gpio_init_struct);
  gpio_pin_mux_config(GPIOC, GPIO_PINS_SOURCE10, GPIO_MUX_9);

  /* configure the io2 gpio */
  gpio_init_struct.gpio_pins = GPIO_PINS_8;
  gpio_init(GPIOC, &gpio_init_struct);
  gpio_pin_mux_config(GPIOC, GPIO_PINS_SOURCE8, GPIO_MUX_9);

  /* configure the io3 gpio */
  gpio_init_struct.gpio_pins = GPIO_PINS_3;
  gpio_init(GPIOB, &gpio_init_struct);
  gpio_pin_mux_config(GPIOB, GPIO_PINS_SOURCE3, GPIO_MUX_10);

  /* configure the sck gpio */
  gpio_init_struct.gpio_pins = GPIO_PINS_1;
  gpio_init(GPIOB, &gpio_init_struct);
  gpio_pin_mux_config(GPIOB, GPIO_PINS_SOURCE1, GPIO_MUX_9);

  /* configure the cs gpio */
  gpio_init_struct.gpio_pins = GPIO_PINS_11;
  gpio_init(GPIOC, &gpio_init_struct);
  gpio_pin_mux_config(GPIOC, GPIO_PINS_SOURCE11, GPIO_MUX_9);
}

/* OTA 禁用旗标与开机读到的 JEDEC ID（契约 §0.7）。
 * JEDEC 不在白名单时 g_qspi_ota_disabled=true；仅 OTA 链路据此拒绝，
 * XIP 读/文件系统等既有功能不受影响。 */
static bool g_qspi_ota_disabled = true;   /* 未成功识别前一律视为禁用（fail-closed） */
static uint32_t g_qspi_jedec_id = 0;

bool HAL::Qspi_IsOtaDisabled(void)
{
    return g_qspi_ota_disabled;
}

uint32_t HAL::Qspi_GetJedecId(void)
{
    return g_qspi_jedec_id;
}

#if CONFIG_QSPI_SELFTEST_ENABLE
/* 自检区（契约 §0.4 EXT_SELFTEST=0x7F0000 64KB 永久避让）。
 * 只在自检开关开启时编译；写/擦一律走 *_selftest 区间受限 API，
 * 不触碰文件系统与 OTA 分区，输出经 SEGGER_RTT 供 J-Link 取证。 */
#define QSPI_SELFTEST_BASE               0x7F0000u
#define QSPI_SELFTEST_SECTORS            16      /* 16 × 4KB = 64KB 自检区全覆盖 */
#define QSPI_SELFTEST_SECTOR_SIZE        4096
#define QSPI_SELFTEST_ITERS              1000    /* 卡验收：读/写/擦 ≥1000 次零错 */
ALIGNED_HEAD static uint8_t qspi_selftest_wbuf[QSPI_SELFTEST_SECTOR_SIZE] ALIGNED_TAIL;
ALIGNED_HEAD static uint8_t qspi_selftest_rbuf[QSPI_SELFTEST_SECTOR_SIZE] ALIGNED_TAIL;

/* 每个自检扇区填不同图案（含 iter 低字节使每轮数据不同，防命中残留旧数据） */
static void qspi_selftest_fill(uint8_t* buf, uint32_t sector, uint32_t iter)
{
    for(int i = 0; i < QSPI_SELFTEST_SECTOR_SIZE; i++)
        buf[i] = (uint8_t)(i + sector + iter);
}

/* 一轮 = 擦→写(命令口)→XIP 读回 memcmp。返回 QSPI_OK 或首个错误码。
 * 每轮内部完成 XIP 进出，保证读回走内存映射、下一轮回到命令口可擦写。 */
static qspi_status_t qspi_selftest_cycle(uint32_t sector, uint32_t iter)
{
    uint32_t addr = QSPI_SELFTEST_BASE + (uint32_t)QSPI_SELFTEST_SECTOR_SIZE * sector;
    qspi_status_t st;

    st = qspi_erase_selftest(addr);
    if(st != QSPI_OK)
        return st;

    qspi_selftest_fill(qspi_selftest_wbuf, sector, iter);
    st = qspi_data_write_selftest(addr, QSPI_SELFTEST_SECTOR_SIZE, qspi_selftest_wbuf);
    if(st != QSPI_OK)
        return st;

    /* 读回验证需 XIP 内存映射，比对后回命令口供下一轮擦写 */
    en25qh128a_qspi_xip_init();
    memcpy(qspi_selftest_rbuf, (uint8_t*)QSPI1_MEM_BASE + addr, QSPI_SELFTEST_SECTOR_SIZE);
    qspi_xip_enable(QSPI1, FALSE);

    if(memcmp(qspi_selftest_wbuf, qspi_selftest_rbuf, QSPI_SELFTEST_SECTOR_SIZE) != 0)
        return QSPI_ERR_VERIFY;
    return QSPI_OK;
}

static void Qspi_SelfTest(void)
{
    uint32_t ok = 0, fail = 0;

    /* 注错子测：未 kick 命令时等 CMDSTS，必须超时返错而非死循环（fail-closed 证明） */
    qspi_status_t inj = qspi_probe_timeout(10u);
    SEGGER_RTT_printf(0, "QSPISELF: inject timeout rc=%d (%s)\r\n",
                      (int)inj, (inj == QSPI_ERR_TIMEOUT) ? "PASS" : "FAIL");

    SEGGER_RTT_printf(0, "QSPISELF: start %d iters @0x%06X (reserved)\r\n",
                      QSPI_SELFTEST_ITERS, (unsigned)QSPI_SELFTEST_BASE);

    for(uint32_t n = 0; n < QSPI_SELFTEST_ITERS; n++)
    {
        uint32_t sector = n % QSPI_SELFTEST_SECTORS;  /* 轮转 16 个自检扇区 */
        qspi_status_t st = qspi_selftest_cycle(sector, n);
        if(st == QSPI_OK)
        {
            ok++;
        }
        else
        {
            fail++;
            SEGGER_RTT_printf(0, "QSPISELF: iter=%lu sec=%lu rc=%d\r\n",
                              (unsigned long)n, (unsigned long)sector, (int)st);
        }
    }

    SEGGER_RTT_printf(0, "QSPISELF: done ok=%lu fail=%lu / %d\r\n",
                      (unsigned long)ok, (unsigned long)fail, QSPI_SELFTEST_ITERS);
}
#endif /* CONFIG_QSPI_SELFTEST_ENABLE */

void HAL::Qspi_Init(void)
{
	/* qspi config */
	qspi_config();

	/* initialize EDMA for QSPI */
	qspi_edma_init();

	/* switch to cmd port */
	qspi_xip_enable(QSPI1, FALSE);

	/* set sclk */
	qspi_clk_division_set(QSPI1, QSPI_CLK_DIV_2);

	/* set sck idle mode 0 */
	qspi_sck_mode_set(QSPI1, QSPI_SCK_MODE_0);

	/* set wip in bit 0 */
	qspi_busy_config(QSPI1, QSPI_BUSY_OFFSET_0);

	/* enable auto ispc */
	qspi_auto_ispc_enable(QSPI1);

	/* JEDEC ID 白名单判定（契约 §0.7）：命令口读 RDID。
	 * 先复位 flash 退出上一轮遗留的连续读/XIP 模式——暖复位（J-Link NRST）
	 * 后 QSPI 控制器寄存器复位但 flash 芯片仍处连续读模式，直接发 RDID
	 * 会读到 0x000000。复位后 1-1-1 RDID 才能被识别。
	 * 判定/告警输出走 SEGGER_RTT（Serial5 UART 的 RTT logger 抓不到，
	 * 与 App.cpp RTTCMD、LiveMap stat、P0-4 BCBSTRESS 惯例一致，AGENTS.md
	 * “验收判定依赖输出必须走 RTT API”红线）。 */
	g_qspi_jedec_id = 0;
	g_qspi_ota_disabled = true;
	qspi_flash_reset();
	qspi_status_t jedec_rc = qspi_read_jedec_id(&g_qspi_jedec_id);
	if(jedec_rc == QSPI_OK && qspi_jedec_is_whitelisted(g_qspi_jedec_id))
	{
		g_qspi_ota_disabled = false;
		SEGGER_RTT_printf(0, "QSPI: JEDEC=0x%06X whitelisted, OTA enabled\r\n",
		                  (unsigned)g_qspi_jedec_id);
	}
	else
	{
		/* rc 用于区分“读超时”(rc=1)与“读到全零”(rc=0 但 id=0)，
		 * 便于真机诊断 RDID 命令口链路失败模式。 */
		SEGGER_RTT_printf(0, "QSPI: JEDEC=0x%06X rc=%d NOT whitelisted, OTA disabled\r\n",
		                  (unsigned)g_qspi_jedec_id, (int)jedec_rc);
	}

#if CONFIG_QSPI_SELFTEST_ENABLE
	/* 自检默认 0；开启时仅动自检保留区 0x7F0000-0x7FFFFF，不碰文件系统/OTA 分区 */
	Qspi_SelfTest();
#endif

	/* 进入 XIP 内存映射模式，供 USB/文件系统直读（既有功能） */
	en25qh128a_qspi_xip_init();
}

