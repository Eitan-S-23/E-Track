/**
 * Copyright (c) 2011-2018 Bill Greiman
 * This file is part of the SdFat library for SD memory cards.
 *
 * MIT License
 *
 * Permission is hereby granted, free of charge, to any person obtaining a
 * copy of this software and associated documentation files (the "Software"),
 * to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense,
 * and/or sell copies of the Software, and to permit persons to whom the
 * Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included
 * in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
 * OR IMPLIED, INCLUDING BUT NOT LIMITED TO, WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 * FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
 * DEALINGS IN THE SOFTWARE.
 */
 
#if defined(__AT32F435_437__)

#include "SdioCard.h"

extern "C" {
  #include "at32_sdio.h"
}

//------------------------------------------------------------------------------
bool SdioCard::begin() {
  sd_error_status_type status = sd_init();
  if (status != SD_OK) {
    transfer_error = status;
    return false;
  }

  transfer_error = SD_OK;
  return true;
}
//------------------------------------------------------------------------------
uint32_t SdioCard::cardCapacity() {
  return (uint32_t)(sd_card_info.card_capacity / 512);
}
//------------------------------------------------------------------------------
bool SdioCard::erase(uint32_t firstBlock, uint32_t lastBlock) {
  sd_error_status_type status = sd_blocks_erase((long long)firstBlock * 512, lastBlock - firstBlock + 1);
  if (status != SD_OK) {
    transfer_error = status;
    return false;
  }
  transfer_error = SD_OK;
  return true;
}
//------------------------------------------------------------------------------
uint8_t SdioCard::errorCode() {
  return (uint8_t)transfer_error;
}
//------------------------------------------------------------------------------
uint32_t SdioCard::errorData() {
  return 0;
}
//------------------------------------------------------------------------------
uint32_t SdioCard::errorLine() {
  return 0;
}
//------------------------------------------------------------------------------
bool SdioCard::isBusy() {
  uint32_t cardStatus;
  sd_error_status_type status = sd_status_send(&cardStatus);
  if (status != SD_OK) {
    return false;
  }
  return (cardStatus & 0x00000100) == 0;
}
//------------------------------------------------------------------------------
uint32_t SdioCard::kHzSdClk() {
  // Return approximate SDIO clock frequency in kHz
  return 25000;  // 25 MHz
}
//------------------------------------------------------------------------------
bool SdioCard::readBlock(uint32_t lba, uint8_t* dst) {
  sd_error_status_type status = sd_block_read(dst, (long long)lba * 512, 512);
  if (status != SD_OK) {
    transfer_error = status;
    return false;
  }
  transfer_error = SD_OK;
  return true;
}
//------------------------------------------------------------------------------
bool SdioCard::readBlocks(uint32_t lba, uint8_t* dst, size_t nb) {
  sd_error_status_type status = sd_mult_blocks_read(dst, (long long)lba * 512, 512, nb);
  if (status != SD_OK) {
    transfer_error = status;
    return false;
  }
  transfer_error = SD_OK;
  return true;
}
//------------------------------------------------------------------------------
bool SdioCard::readCID(void* cid) {
  memcpy(cid, &sd_card_info.sd_cid_reg, sizeof(sd_cid_reg_type));
  return true;
}
//------------------------------------------------------------------------------
bool SdioCard::readCSD(void* csd) {
  memcpy(csd, &sd_card_info.sd_csd_reg, sizeof(sd_csd_reg_type));
  return true;
}
//------------------------------------------------------------------------------
bool SdioCard::readData(uint8_t *dst) {
  // Not implemented for basic SDIO mode
  return false;
}
//------------------------------------------------------------------------------
bool SdioCard::readOCR(uint32_t* ocr) {
  *ocr = 0x80FF8000;  // Standard voltage range
  return true;
}
//------------------------------------------------------------------------------
bool SdioCard::readStart(uint32_t lba) {
  // Not implemented for basic SDIO mode
  return false;
}
//------------------------------------------------------------------------------
bool SdioCard::readStart(uint32_t lba, uint32_t count) {
  // Not implemented for basic SDIO mode
  return false;
}
//------------------------------------------------------------------------------
bool SdioCard::readStop() {
  // Not implemented for basic SDIO mode
  return false;
}
//------------------------------------------------------------------------------
bool SdioCard::syncBlocks() {
  return !isBusy();
}
//------------------------------------------------------------------------------
uint8_t SdioCard::type() {
  return sd_card_info.card_type;
}
//------------------------------------------------------------------------------
bool SdioCard::writeBlock(uint32_t lba, const uint8_t* src) {
  sd_error_status_type status = sd_block_write(src, (long long)lba * 512, 512);
  if (status != SD_OK) {
    transfer_error = status;
    return false;
  }
  transfer_error = SD_OK;
  return true;
}
//------------------------------------------------------------------------------
bool SdioCard::writeBlocks(uint32_t lba, const uint8_t* src, size_t nb) {
  sd_error_status_type status = sd_mult_blocks_write(src, (long long)lba * 512, 512, nb);
  if (status != SD_OK) {
    transfer_error = status;
    return false;
  }
  transfer_error = SD_OK;
  return true;
}
//------------------------------------------------------------------------------
bool SdioCard::writeData(const uint8_t* src) {
  // Not implemented for basic SDIO mode
  return false;
}
//------------------------------------------------------------------------------
bool SdioCard::writeStart(uint32_t lba) {
  // Not implemented for basic SDIO mode
  return false;
}
//------------------------------------------------------------------------------
bool SdioCard::writeStart(uint32_t lba, uint32_t count) {
  // Not implemented for basic SDIO mode
  return false;
}
//------------------------------------------------------------------------------
bool SdioCard::writeStop() {
  // Not implemented for basic SDIO mode
  return false;
}
//==============================================================================
bool SdioCardEX::readBlock(uint32_t lba, uint8_t* dst) {
  if (m_curState != READ_STATE || lba != m_curLba) {
    if (!syncBlocks()) {
      return false;
    }
    m_curLba = lba;
    m_curState = READ_STATE;
  }
  bool status = SdioCard::readBlock(lba, dst);
  m_curLba++;
  return status;
}
//------------------------------------------------------------------------------
bool SdioCardEX::readBlocks(uint32_t lba, uint8_t* dst, size_t nb) {
  /* 多块 CMD18 一次事务只付一次卡内寻址延迟（NAC），4KB 读实测 ~0.35ms，
     比逐块 CMD17（~1.5ms）快 4 倍以上；sd_mult_blocks_read 在数据完成后
     同步发 CMD12 停卡（本工程 SDIO 中断未使能，不能依赖 sd_irq_service）。
     多块路径绕过 EX 状态机，置 IDLE 让后续单块读重新同步。 */
  m_curState = IDLE_STATE;
  if (SdioCard::readBlocks(lba, dst, nb)) {
    return true;
  }
  /* 多块失败：先完整重新初始化把卡拉回 tran 态，再逐块降级重试 */
  if (!SdioCard::begin()) {
    return false;
  }
  for (size_t i = 0; i < nb; i++) {
    if (!SdioCard::readBlock(lba + i, dst + (i * 512))) {
      return false;
    }
  }
  return true;
}
//------------------------------------------------------------------------------
bool SdioCardEX::syncBlocks() {
  if (m_curState != IDLE_STATE) {
    m_curState = IDLE_STATE;
  }
  return SdioCard::syncBlocks();
}
//------------------------------------------------------------------------------
bool SdioCardEX::writeBlock(uint32_t lba, const uint8_t* src) {
  if (m_curState != WRITE_STATE || lba != m_curLba) {
    if (!syncBlocks()) {
      return false;
    }
    m_curLba = lba;
    m_curState = WRITE_STATE;
  }
  bool status = SdioCard::writeBlock(lba, src);
  m_curLba++;
  return status;
}
//------------------------------------------------------------------------------
bool SdioCardEX::writeBlocks(uint32_t lba, const uint8_t* src, size_t nb) {
  if (m_curState != WRITE_STATE || lba != m_curLba) {
    if (!syncBlocks()) {
      return false;
    }
    m_curLba = lba;
    m_curState = WRITE_STATE;
  }
  for (size_t i = 0; i < nb; i++) {
    if (!SdioCard::writeBlock(lba + i, src + (i * 512))) {
      return false;
    }
  }
  m_curLba += nb;
  return true;
}

#endif  // __AT32F435_437__



