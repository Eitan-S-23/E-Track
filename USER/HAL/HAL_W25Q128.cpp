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

#define FLASH_TOTAL_SIZE                 (8 * 1024 * 1024)  // 16MB total
#define TEST_TIMES                       16    // 测试16个扇区 = 64KB
#define TEST_SIZE                        4096  // 每个扇区4KB
#define TEST_START_ADDR                  (FLASH_TOTAL_SIZE - TEST_TIMES * TEST_SIZE)  // Test at end of flash to preserve filesystem
ALIGNED_HEAD uint8_t wbuf[TEST_SIZE] ALIGNED_TAIL;
ALIGNED_HEAD uint8_t rbuf[TEST_SIZE] ALIGNED_TAIL;


void HAL::Qspi_Init(void)
{
	int pass_count = 0;
	int fail_count = 0;

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

	CONFIG_DEBUG_SERIAL.printf("\r\n========== W25Q128 Flash Test Start ==========\r\n");
	CONFIG_DEBUG_SERIAL.printf("Testing %d sectors (%d KB total) at END of flash\r\n", TEST_TIMES, TEST_TIMES * 4);
	CONFIG_DEBUG_SERIAL.printf("Test area: 0x%08X - 0x%08X (to preserve filesystem)\r\n",
	                           TEST_START_ADDR, FLASH_TOTAL_SIZE - 1);
	CONFIG_DEBUG_SERIAL.printf("Memory usage: %d KB (%.1f%% of test area)\r\n",
	                           (TEST_SIZE * 2) / 1024,
	                           (float)(TEST_SIZE * 2) * 100 / (TEST_SIZE * TEST_TIMES));
	CONFIG_DEBUG_SERIAL.printf("EDMA Features: Manual Dual-Buffer + Link List Transfer\r\n");
	CONFIG_DEBUG_SERIAL.printf("  - CPU mode: < 32 bytes\r\n");
	CONFIG_DEBUG_SERIAL.printf("  - Dual-Buffer DMA: 32 bytes - 8 KB (Software managed)\r\n");
	CONFIG_DEBUG_SERIAL.printf("  - Link List DMA: > 8 KB (Hardware chaining)\r\n\r\n");

	/* Step 1: Erase all test sectors */
	CONFIG_DEBUG_SERIAL.printf("[1/4] Erasing %d sectors...\r\n", TEST_TIMES);
	for(int j = 0; j < TEST_TIMES; j++)
	{
		qspi_erase(TEST_START_ADDR + TEST_SIZE * j);
		if((j + 1) % 4 == 0 || j == TEST_TIMES - 1)
		{
			CONFIG_DEBUG_SERIAL.printf("  Progress: %d/%d sectors erased\r\n", j + 1, TEST_TIMES);
		}
	}

	/* Step 2: Write test data to all sectors */
	CONFIG_DEBUG_SERIAL.printf("\r\n[2/4] Writing test data to %d sectors...\r\n", TEST_TIMES);
	for(int j = 0; j < TEST_TIMES; j++)
	{
		/* Generate unique test pattern for each sector */
		for(int i = 0; i < TEST_SIZE; i++)
		{
			wbuf[i] = (uint8_t)(i + j);  // Each sector has different data
		}

		/* Program the sector */
		qspi_data_write(TEST_START_ADDR + TEST_SIZE * j, TEST_SIZE, wbuf);

		if((j + 1) % 4 == 0 || j == TEST_TIMES - 1)
		{
			CONFIG_DEBUG_SERIAL.printf("  Progress: %d/%d sectors written\r\n", j + 1, TEST_TIMES);
		}
	}

	/* Step 3: Configure XIP mode for reading */
	CONFIG_DEBUG_SERIAL.printf("\r\n[3/4] Configuring XIP mode...\r\n");
	en25qh128a_qspi_xip_init();
	CONFIG_DEBUG_SERIAL.printf("  XIP mode enabled\r\n");

	/* Step 4: Read and verify all sectors */
	CONFIG_DEBUG_SERIAL.printf("\r\n[4/4] Verifying %d sectors...\r\n", TEST_TIMES);
	for(int j = 0; j < TEST_TIMES; j++)
	{
		/* Regenerate expected data pattern */
		for(int i = 0; i < TEST_SIZE; i++)
		{
			wbuf[i] = (uint8_t)(i + j);
		}

		/* Read from flash via XIP */
		memcpy(rbuf, (uint8_t*)QSPI1_MEM_BASE + TEST_START_ADDR + TEST_SIZE * j, TEST_SIZE);

		/* Verify data */
		if(memcmp(wbuf, rbuf, TEST_SIZE) == 0)
		{
			CONFIG_DEBUG_SERIAL.printf("  Sector %2d [0x%06X - 0x%06X]: PASS\r\n",
			                           j, TEST_START_ADDR + TEST_SIZE * j, TEST_START_ADDR + TEST_SIZE * (j + 1) - 1);
			pass_count++;
		}
		else
		{
			CONFIG_DEBUG_SERIAL.printf("  Sector %2d [0x%06X - 0x%06X]: FAIL\r\n",
			                           j, TEST_START_ADDR + TEST_SIZE * j, TEST_START_ADDR + TEST_SIZE * (j + 1) - 1);
			fail_count++;

			/* Print first error location for debugging */
			for(int i = 0; i < TEST_SIZE; i++)
			{
				if(wbuf[i] != rbuf[i])
				{
					CONFIG_DEBUG_SERIAL.printf("    First error at offset %d: expected 0x%02X, got 0x%02X\r\n",
					                           i, wbuf[i], rbuf[i]);
					break;
				}
			}
		}
	}

	/* Print test summary */
	CONFIG_DEBUG_SERIAL.printf("\r\n========== W25Q128 Flash Test Result ==========\r\n");
	CONFIG_DEBUG_SERIAL.printf("Total sectors tested: %d\r\n", TEST_TIMES);
	CONFIG_DEBUG_SERIAL.printf("Passed:               %d sectors\r\n", pass_count);
	CONFIG_DEBUG_SERIAL.printf("Failed:               %d sectors\r\n", fail_count);
	CONFIG_DEBUG_SERIAL.printf("Success rate:         %.1f%%\r\n", (float)pass_count * 100 / TEST_TIMES);

	/* Get and display transfer statistics */
	uint32_t cpu_count = 0, double_buf_count = 0, link_list_count = 0;
	qspi_get_transfer_stats(&cpu_count, &double_buf_count, &link_list_count);
	CONFIG_DEBUG_SERIAL.printf("\r\n--- EDMA Transfer Statistics ---\r\n");
	CONFIG_DEBUG_SERIAL.printf("CPU transfers:          %u\r\n", cpu_count);
	CONFIG_DEBUG_SERIAL.printf("Double Buffer DMA:      %u\r\n", double_buf_count);
	CONFIG_DEBUG_SERIAL.printf("Link List DMA:          %u\r\n", link_list_count);
	CONFIG_DEBUG_SERIAL.printf("Total DMA transfers:    %u\r\n", double_buf_count + link_list_count);

	if(fail_count == 0)
	{
		CONFIG_DEBUG_SERIAL.printf("\r\n>>> TEST PASSED <<<\r\n");
	}
	else
	{
		CONFIG_DEBUG_SERIAL.printf("\r\n>>> TEST FAILED <<<\r\n");
	}
	CONFIG_DEBUG_SERIAL.printf("===============================================\r\n\r\n");
}

