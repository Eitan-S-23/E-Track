/**
  **************************************************************************
  * @file     msc_diskio.c
  * @brief    usb mass storage disk function
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
#include "msc_diskio.h"
#include "msc_class/msc_bot_scsi.h"
#include <string.h>

#ifdef MSC_USE_SD_CARD
/* SD Card backend */
#include "SdFat.h"

extern SdFatSdioEX SD;  // Defined in HAL_SD_CARD.cpp

#elif defined(MSC_USE_QSPI_FLASH)
/* QSPI Flash backend；签名以 W25Q128 契约安全化头为准（P0-5：带超时/错误返回）。 */
#include "W25Q128/qspi_cmd_en25qh128a.h"
#else
#error "No storage backend selected! Define either MSC_USE_SD_CARD or MSC_USE_QSPI_FLASH in msc_diskio.h"
#endif

/** @addtogroup AT32F435_periph_examples
  * @{
  */

/** @addtogroup 435_USB_device_msc
  * @{
  */
uint32_t sector_size = 512;  // USB standard 512 bytes per block
uint32_t msc_flash_size = 0; // Will be set dynamically

#ifdef MSC_USE_QSPI_FLASH
typedef char qspi_msc_capacity_match[
  (QSPI_FLASH_TOTAL_SIZE == QSPI_FLASH_CAPACITY) ? 1 : -1];
typedef char qspi_msc_selftest_start_match[
  (QSPI_FLASH_USABLE_SIZE == QSPI_SELFTEST_ADDR) ? 1 : -1];
typedef char qspi_msc_selftest_size_match[
  (QSPI_FLASH_RESERVED_SIZE == QSPI_SELFTEST_SIZE) ? 1 : -1];

static bool qspi_msc_xip_ready = false;

static bool qspi_msc_range_valid(uint64_t addr, uint32_t len)
{
  if(addr > (uint64_t)QSPI_FLASH_USABLE_SIZE)
    return false;
  return (uint64_t)len <= ((uint64_t)QSPI_FLASH_USABLE_SIZE - addr);
}

static bool qspi_msc_enter_xip(void)
{
  qspi_msc_xip_ready = (en25qh128a_qspi_xip_init() == QSPI_OK);
  return qspi_msc_xip_ready;
}

static void qspi_msc_leave_xip(void)
{
  qspi_xip_enable(QSPI1, FALSE);
  qspi_msc_xip_ready = false;
}
#endif

uint8_t scsi_inquiry[MSC_SUPPORT_MAX_LUN][SCSI_INQUIRY_DATA_LENGTH] =
{
#ifdef MSC_USE_SD_CARD
  /* lun = 0: SD Card */
  {
    0x00,         /* peripheral device type (direct-access device) */
    0x80,         /* removable media bit */
    0x00,         /* ansi version, ecma version, iso version */
    0x01,         /* respond data format */
    SCSI_INQUIRY_DATA_LENGTH - 5, /* additional length */
    0x00, 0x00, 0x00, /* reserved */
    'A', 'T', '3', '2', ' ', ' ', ' ', ' ', /* vendor information "AT32" */
    'S', 'D', ' ', 'C', 'a', 'r', 'd', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', /* Product identification "SD Card" */
    '1', '.', '0', '0'  /* product revision level */
  }
#elif defined(MSC_USE_QSPI_FLASH)
  /* lun = 0: SPI Flash (W25Q128) */
  {
    0x00,         /* peripheral device type (direct-access device) */
    0x80,         /* removable media bit */
    0x00,         /* ansi version, ecma version, iso version */
    0x01,         /* respond data format */
    SCSI_INQUIRY_DATA_LENGTH - 5, /* additional length */
    0x00, 0x00, 0x00, /* reserved */
    'A', 'T', '3', '2', ' ', ' ', ' ', ' ', /* vendor information "AT32" */
    'Q', 'S', 'P', 'I', ' ', 'F', 'l', 'a', 's', 'h', ' ', ' ', ' ', ' ', ' ', ' ', /* Product identification "QSPI Flash" */
    '2', '.', '0', '0'  /* product revision level */
  }
#endif
};

/**
  * @brief  get disk inquiry
  * @param  lun: logical units number
  * @retval inquiry string
  */
uint8_t *get_inquiry(uint8_t lun)
{
  if(lun < MSC_SUPPORT_MAX_LUN)
    return (uint8_t *)scsi_inquiry[lun];
  else
    return NULL;
}

/**
  * @brief  disk capacity
  * @param  lun: logical units number
  * @param  blk_nbr: pointer to number of block
  * @param  blk_size: pointer to block size
  * @retval status of usb_sts_type
  */
usb_sts_type msc_disk_capacity(uint8_t lun, uint32_t *blk_nbr, uint32_t *blk_size)
{
  if(blk_nbr == NULL || blk_size == NULL)
    return USB_FAIL;

  /* LUN 0 maps to selected storage backend */
  if(lun == 0)
  {
#ifdef MSC_USE_SD_CARD
    /* SD Card: Get capacity dynamically from card */
    if(SD.card() && SD.card()->cardSize() > 0)
    {
      *blk_nbr = SD.card()->cardSize();  // cardSize() returns number of 512-byte blocks
      *blk_size = SD_CARD_BLOCK_SIZE;
      return USB_OK;
    }
    else
    {
      return USB_FAIL;  // SD card not ready or not inserted
    }
#elif defined(MSC_USE_QSPI_FLASH)
    /* Exclude the permanent 64KB self-test reservation from the LUN. */
    msc_flash_size = QSPI_FLASH_USABLE_SIZE;
    *blk_nbr = QSPI_FLASH_USABLE_SIZE / QSPI_FLASH_BLOCK_SIZE;
    *blk_size = QSPI_FLASH_BLOCK_SIZE;
    return USB_OK;
#endif
  }

  return USB_FAIL;  // Other LUNs not supported
}

/**
  * @brief  disk read
  * @param  lun: logical units number
  * @param  addr: logical address
  * @param  read_buf: pointer to read buffer
  * @param  len: read length
  * @retval status of usb_sts_type
  */
usb_sts_type msc_disk_read(uint8_t lun, uint64_t addr, uint8_t *read_buf, uint32_t len)
{
  /* LUN 0 maps to selected storage backend */
  if(lun == 0)
  {
#ifdef MSC_USE_SD_CARD
    /* SD Card: Direct block read via SDIO */
    uint32_t block_addr = (uint32_t)addr / SD_CARD_BLOCK_SIZE;
    uint32_t block_count = len / SD_CARD_BLOCK_SIZE;

    if(len % SD_CARD_BLOCK_SIZE != 0)
    {
      return USB_FAIL;  // Length must be multiple of block size
    }

    if(SD.card() && SD.card()->readBlocks(block_addr, read_buf, block_count))
    {
      return USB_OK;
    }
    else
    {
      return USB_FAIL;  // SD card read error
    }

#elif defined(MSC_USE_QSPI_FLASH)
    /* QSPI Flash: Read from XIP (memory mapped mode) */
    if((len > 0 && read_buf == NULL) || (len % QSPI_FLASH_BLOCK_SIZE) != 0 ||
       !qspi_msc_range_valid(addr, len))
    {
      return USB_FAIL;
    }
    if(len == 0)
    {
      return USB_OK;
    }
    if(!qspi_msc_xip_ready && !qspi_msc_enter_xip())
    {
      return USB_FAIL;
    }
    memcpy(read_buf, (uint8_t *)(QSPI1_MEM_BASE + (uint32_t)addr), len);
    return USB_OK;
#endif
  }

  return USB_FAIL;  // Other LUNs not supported
}

/**
  * @brief  disk write
  * @param  lun: logical units number
  * @param  addr: logical address
  * @param  buf: pointer to write buffer
  * @param  len: write length
  * @retval status of usb_sts_type
  */
usb_sts_type msc_disk_write(uint8_t lun, uint64_t addr, uint8_t *buf, uint32_t len)
{
  /* LUN 0 maps to selected storage backend */
  if(lun == 0)
  {
#ifdef MSC_USE_SD_CARD
    /* SD Card: Direct block write via SDIO */
    uint32_t block_addr = (uint32_t)addr / SD_CARD_BLOCK_SIZE;
    uint32_t block_count = len / SD_CARD_BLOCK_SIZE;

    if(len % SD_CARD_BLOCK_SIZE != 0)
    {
      return USB_FAIL;  // Length must be multiple of block size
    }

    if(SD.card() && SD.card()->writeBlocks(block_addr, buf, block_count))
    {
      return USB_OK;
    }
    else
    {
      return USB_FAIL;  // SD card write error
    }

#elif defined(MSC_USE_QSPI_FLASH)
    /* QSPI Flash: Read-modify-write for flash sectors */
    static uint8_t sector_buffer[QSPI_FLASH_SECTOR_SIZE];  // 4KB缓冲区
		uint32_t sector_addr;
		uint32_t offset_in_sector;
		uint32_t bytes_to_write;
    uint32_t total_written = 0;
    qspi_status_t st;

    if((len % QSPI_FLASH_BLOCK_SIZE) != 0 ||
       !qspi_msc_range_valid(addr, len) || (len > 0 && buf == NULL))
    {
      return USB_FAIL;
    }
    if(len == 0)
    {
      return USB_OK;
    }

    qspi_msc_leave_xip();

    /* 按扇区处理，使用读-改-写策略 */
    while(total_written < len)
    {
      /* 计算当前扇区地址和偏移 */
      sector_addr = ((uint32_t)addr + total_written) & ~(QSPI_FLASH_SECTOR_SIZE - 1);
      offset_in_sector = ((uint32_t)addr + total_written) % QSPI_FLASH_SECTOR_SIZE;
      bytes_to_write = QSPI_FLASH_SECTOR_SIZE - offset_in_sector;

      if(bytes_to_write > (len - total_written))
        bytes_to_write = len - total_written;

      /* Step 1: 通过XIP读取整个扇区 */
      if(!qspi_msc_enter_xip())
      {
        (void)qspi_msc_enter_xip();
        return USB_FAIL;
      }
      memcpy(sector_buffer, (uint8_t *)(QSPI1_MEM_BASE + sector_addr), QSPI_FLASH_SECTOR_SIZE);
      qspi_msc_leave_xip();

      /* Step 2: 在缓冲区中修改需要更新的部分 */
      memcpy(sector_buffer + offset_in_sector, buf + total_written, bytes_to_write);

      /* Step 3: 擦除扇区 */
      st = qspi_erase(sector_addr);
      if(st != QSPI_OK)
      {
        (void)qspi_msc_enter_xip();
        return USB_FAIL;
      }

      /* Step 4: 写回整个修改后的扇区 */
      st = qspi_data_write(sector_addr, QSPI_FLASH_SECTOR_SIZE, sector_buffer);
      if(st != QSPI_OK)
      {
        (void)qspi_msc_enter_xip();
        return USB_FAIL;
      }

      total_written += bytes_to_write;
    }

    if(!qspi_msc_enter_xip())
    {
      return USB_FAIL;
    }

    return USB_OK;
#endif
  }

  return USB_FAIL;  // Other LUNs not supported
}

/**
  * @}
  */

/**
  * @}
  */
