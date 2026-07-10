/**
  **************************************************************************
  * @file     msc_diskio.h
  * @brief    usb mass storage disk interface header file
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
/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __MSC_DISKIO_H
#define __MSC_DISKIO_H

#ifdef __cplusplus
extern "C" {
#endif


#include "usb_conf.h"
#include "middlewares\usb_drivers\inc\usb_std.h"

/** @addtogroup AT32F435_periph_examples
  * @{
  */

/** @addtogroup 435_USB_device_msc
  * @{
  */

/**
  * @brief USB MSC Storage Media Selection
  * Uncomment one of the following to select the storage backend:
  * - MSC_USE_QSPI_FLASH: Use external W25Q128 QSPI Flash (16MB)
  * - MSC_USE_SD_CARD:    Use SD Card via SDIO
  */
#define MSC_USE_SD_CARD           /* Use SD Card as USB MSC storage */
//#define MSC_USE_QSPI_FLASH     /* Use QSPI Flash as USB MSC storage */

#define INTERNAL_FLASH_LUN               0
#define SPI_FLASH_LUN                    1
#define SD_LUN                           2

#define USB_FLASH_ADDR_OFFSET            0x08060000

#define SECTOR_SIZE_1K                   1024
#define SECTOR_SIZE_2K                   2048
#define SECTOR_SIZE_4K                   4096

/* QSPI Flash (W25Q128) configuration */
#ifndef QSPI1_MEM_BASE
#define QSPI1_MEM_BASE                   0x90000000  /* QSPI1 memory mapped base address */
#endif
#define QSPI_FLASH_TOTAL_SIZE            (8 * 1024 * 1024)  /* 16MB (128Mbit) */
#define QSPI_FLASH_SECTOR_SIZE           4096        /* 4KB per sector */
#define QSPI_FLASH_BLOCK_SIZE            512         /* 512 bytes per block (USB standard) */

/* SD Card configuration */
#define SD_CARD_BLOCK_SIZE               512         /* 512 bytes per block (standard) */

uint8_t *get_inquiry(uint8_t lun);
usb_sts_type msc_disk_read(uint8_t lun, uint64_t addr, uint8_t *read_buf, uint32_t len);
usb_sts_type msc_disk_write(uint8_t lun, uint64_t addr, uint8_t *buf, uint32_t len);
usb_sts_type msc_disk_capacity(uint8_t lun, uint32_t *blk_nbr, uint32_t *blk_size);

/**
  * @}
  */

/**
  * @}
  */

#ifdef __cplusplus
}
#endif

#endif


