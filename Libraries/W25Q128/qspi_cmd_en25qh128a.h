/**
  **************************************************************************
  * @file     qspi_cmd_en25qh128a.c
  * @brief    qspi_cmd_en25qh128a program
  **************************************************************************
  *                       Copyright notice & Disclaimer
  *
  * The software Board Support Package (BSP) that is made available to
  * download from Artery official website is the copyrighted work of Artery.
  * Artery authorizes customers to use, copy, and distribute the BSP
  * software and its related documentation for the purpose of design and
  * development in conjunction with Artery microcontrollers. Use of the
  * software is governed by this copyright notice and the following disclaimer.
  *
  * THIS SOFTWARE IS PROVIDED ON "AS IS" BASIS WITHOUT WARRANTIES,
  * GUARANTEES OR REPRESENTATIONS OF ANY KIND. ARTERY EXPRESSLY DISCLAIMS,
  * TO THE FULLEST EXTENT PERMITTED BY LAW, ALL EXPRESS, IMPLIED OR
  * STATUTORY OR OTHER WARRANTIES, GUARANTEES OR REPRESENTATIONS,
  * INCLUDING BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY,
  * FITNESS FOR A PARTICULAR PURPOSE, OR NON-INFRINGEMENT.
  *
  **************************************************************************
  */




#include "HAL/HAL.h"
#ifdef __cplusplus
extern "C" {
#endif
/** @addtogroup AT32F435_periph_examples
  * @{
  */

/** @addtogroup 435_QSPI_xip_port_read_flash
  * @{
  */

/* QSPI 安全化返回码（P0-5，OTA 契约 §0.5/§0.7）。
 * 所有裸命令/擦/写原语一律带超时并返回状态：忙等超时 fail-closed 返错，
 * 绝不死循环；越界或触碰自检保留区返 QSPI_ERR_REGION。 */
typedef enum
{
  QSPI_OK          = 0,  /* 成功 */
  QSPI_ERR_TIMEOUT = 1,  /* 忙等超时（命令/FIFO/DMA/busy 未在时限内完成） */
  QSPI_ERR_PARAM   = 2,  /* 入参非法（空指针等） */
  QSPI_ERR_REGION  = 3,  /* 越界或触碰自检保留区 0x7F0000..0x7FFFFF */
  QSPI_ERR_VERIFY  = 4   /* 读回比对失败 */
} qspi_status_t;

/* 超时口径（毫秒，基于 millis()）。命令口/ FIFO 走短超时；
 * busy 覆盖扇区擦除最坏耗时（W25Q128 sector erase ≤400ms，取 2s 余量）。 */
#define QSPI_CMD_TIMEOUT_MS              100u
#define QSPI_FIFO_TIMEOUT_MS             100u
#define QSPI_DMA_TIMEOUT_MS              1000u
#define QSPI_BUSY_TIMEOUT_MS             2000u

/* 容量与自检保留区（契约 §0.4：EXT_SELFTEST=0x7F0000 64KB 永久避让）。 */
#define QSPI_FLASH_CAPACITY              (8u * 1024u * 1024u)  /* contracted 8MB window */
#define QSPI_SELFTEST_ADDR               0x7F0000u
#define QSPI_SELFTEST_SIZE               0x10000u              /* 64KB */

/* JEDEC ID 白名单（契约 §0.7）。RDID(0x9F) 返回 manuf<<16 | mem_type<<8 | capacity。 */
#define QSPI_JEDEC_W25Q128               0xEF4018u  /* W25Q128 16MiB */
#define QSPI_JEDEC_EN25QH128A            0x1C4018u  /* EN25QH128A 16MiB */
#define QSPI_JEDEC_EN25QH64A             0x1C4017u  /* EN25QH64A 8MiB */
#define QSPI_JEDEC_W25Q64                0xEF4017u  /* W25Q64 8MiB */

/**
  * @brief  qspi write data
  * @param  addr: the address for write
  * @param  total_len: the length for write
  * @param  buf: the pointer for write data
  * @retval QSPI_OK 成功；越界/触自检区 QSPI_ERR_REGION；忙等超时 QSPI_ERR_TIMEOUT
  */
qspi_status_t qspi_data_write(uint32_t addr, uint32_t total_len, uint8_t* buf);

/**
  * @brief  qspi write data（自检专用，仅允许落在自检保留区 0x7F0000..0x7FFFFF 内）
  * @retval QSPI_OK / QSPI_ERR_PARAM / QSPI_ERR_REGION / QSPI_ERR_TIMEOUT
  */
qspi_status_t qspi_data_write_selftest(uint32_t addr, uint32_t total_len, uint8_t* buf);

/**
  * @brief  initialize EDMA for QSPI
  * @param  none
  * @retval none
  */
void qspi_edma_init(void);

/**
  * @brief  qspi erase data
  * @param  sec_addr: the sector address for erase
  * @retval QSPI_OK 成功；越界/触自检区 QSPI_ERR_REGION；忙等超时 QSPI_ERR_TIMEOUT
  */
qspi_status_t qspi_erase(uint32_t sec_addr);

/**
  * @brief  qspi erase data（自检专用，仅允许落在自检保留区 0x7F0000..0x7FFFFF 内）
  * @retval QSPI_OK / QSPI_ERR_REGION / QSPI_ERR_TIMEOUT
  */
qspi_status_t qspi_erase_selftest(uint32_t sec_addr);

/**
  * @brief  qspi check busy（RDSR 自动轮询，带超时）
  * @param  none
  * @retval QSPI_OK / QSPI_ERR_TIMEOUT
  */
qspi_status_t qspi_busy_check(void);

/**
  * @brief  qspi write enable
  * @param  none
  * @retval QSPI_OK / QSPI_ERR_TIMEOUT
  */
qspi_status_t qspi_write_enable(void);

/**
  * @brief  qspi cmd kick and wait completed（带超时）
  * @param  qspi_cmd_struct: the pointer for qspi_cmd_type parameter
  * @retval QSPI_OK / QSPI_ERR_PARAM / QSPI_ERR_TIMEOUT
  */
qspi_status_t qspi_cmd_send(qspi_cmd_type* qspi_cmd_struct);

/**
  * @brief  set QE bit in status register-2 for W25Q128
  * @param  none
  * @retval QSPI_OK / QSPI_ERR_TIMEOUT
  */
qspi_status_t qspi_set_qe_bit(void);

/**
  * @brief  复位外部 flash（RSTEN 0x66 + RST 0x99），退出遗留连续读/XIP 模式
  * @retval QSPI_OK / QSPI_ERR_TIMEOUT
  */
qspi_status_t qspi_flash_reset(void);

/**
  * @brief  读 JEDEC ID(RDID 0x9F)，命令口 3 字节读
  * @param  id: 出参，manuf<<16 | mem_type<<8 | capacity
  * @retval QSPI_OK / QSPI_ERR_PARAM / QSPI_ERR_TIMEOUT
  * @note   调用前必须先 qspi_flash_reset 退出连续读模式，否则暖复位读到 0
  */
qspi_status_t qspi_read_jedec_id(uint32_t* id);

/**
  * @brief  JEDEC ID 是否在 OTA 白名单内（契约 §0.7）
  * @param  id: qspi_read_jedec_id 读出的值
  * @retval true 在白名单；false 不识别（调用方应置 OTA 禁用旗标）
  */
bool qspi_jedec_is_whitelisted(uint32_t id);

/**
  * @brief  超时路径注错自检（不 kick 命令等 CMDSTS，必须超时返错，验证 fail-closed）
  * @param  timeout_ms: 注错等待时限
  * @retval 期望恒为 QSPI_ERR_TIMEOUT
  */
qspi_status_t qspi_probe_timeout(uint32_t timeout_ms);

qspi_status_t en25qh128a_qspi_xip_init(void);

/**
  * @brief  get transfer mode statistics
  * @param  cpu_count: pointer to receive CPU transfer count
  * @param  double_buffer_count: pointer to receive double buffer transfer count
  * @param  link_list_count: pointer to receive link list transfer count
  * @retval none
  */
void qspi_get_transfer_stats(uint32_t* cpu_count, uint32_t* double_buffer_count, uint32_t* link_list_count);

/**
  * @brief  reset transfer mode statistics
  * @param  none
  * @retval none
  */
void qspi_reset_transfer_stats(void);
#ifdef __cplusplus
}
#endif

/**
  * @}
  */

/**
  * @}
  */
