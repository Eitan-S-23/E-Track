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




extern "C" {
#include "HAL/HAL.h"
/** @addtogroup AT32F435_periph_examples
  * @{
  */

/** @addtogroup 435_QSPI_xip_port_read_flash
  * @{
  */	
	
/**
  * @brief  qspi write data
  * @param  addr: the address for write
  * @param  total_len: the length for write
  * @param  buf: the pointer for write data
  * @retval none
  */
void qspi_data_write(uint32_t addr, uint32_t total_len, uint8_t* buf);

/**
  * @brief  initialize EDMA for QSPI
  * @param  none
  * @retval none
  */
void qspi_edma_init(void);

/**
  * @brief  qspi erase data
  * @param  sec_addr: the sector address for erase
  * @retval none
  */
void qspi_erase(uint32_t sec_addr);

/**
  * @brief  qspi check busy
  * @param  none
  * @retval none
  */
void qspi_busy_check(void);

/**
  * @brief  qspi write enable
  * @param  none
  * @retval none
  */
void qspi_write_enable(void);

/**
  * @brief  qspi cmd kick and wait completed
  * @param  qspi_cmd_struct: the pointer for qspi_cmd_type parameter
  * @retval none
  */
void qspi_cmd_send(qspi_cmd_type* qspi_cmd_struct);

/**
  * @brief  set QE bit in status register-2 for W25Q128
  * @param  none
  * @retval none
  */
void qspi_set_qe_bit(void);

void en25qh128a_qspi_xip_init(void);

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
}

/**
  * @}
  */

/**
  * @}
  */
