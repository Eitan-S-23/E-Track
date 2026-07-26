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
#include "W25Q128/qspi_cmd_en25qh128a.h"

/** @addtogroup AT32F435_periph_examples
  * @{
  */

/** @addtogroup 435_QSPI_xip_port_read_flash
  * @{
  */
extern "C" {
#define FLASH_PAGE_PROGRAM_SIZE          256

/* EDMA configuration for QSPI */
#define QSPI_EDMA_STREAM                 EDMA_STREAM1
#define QSPI_EDMAMUX_CHANNEL             EDMAMUX_CHANNEL1
#define QSPI_DMA_BUFFER_SIZE             4096  // 4KB buffer size

static edma_init_type edma_init_struct;
static volatile uint8_t qspi_dma_transfer_done = 0;
static volatile uint8_t qspi_current_buffer = 0;  // 0 or 1

/* Debug: track interrupt trigger count */
static volatile uint32_t edma_irq_count = 0;
static volatile uint32_t edma_fdt_count = 0;
static volatile uint32_t edma_hdt_count = 0;
static volatile uint32_t edma_err_count = 0;

/* Double buffer for QSPI DMA */
ALIGNED_HEAD static uint8_t qspi_dma_buffer0[QSPI_DMA_BUFFER_SIZE] ALIGNED_TAIL;
ALIGNED_HEAD static uint8_t qspi_dma_buffer1[QSPI_DMA_BUFFER_SIZE] ALIGNED_TAIL;

/* Link list structure for chained transfers */
typedef struct
{
  uint32_t ctrl;
  uint32_t dtcnt;
  uint32_t paddr;
  uint32_t m0addr;
  uint32_t m1addr;
  uint32_t fctrl;
  uint32_t llp;
} edma_link_list_node_type;

#define MAX_LINK_NODES                   16
ALIGNED_HEAD static edma_link_list_node_type edma_link_nodes[MAX_LINK_NODES] ALIGNED_TAIL;

/* Transfer statistics for debugging */
static volatile uint32_t qspi_cpu_transfer_count = 0;
static volatile uint32_t qspi_double_buffer_transfer_count = 0;
static volatile uint32_t qspi_link_list_transfer_count = 0;

/* en25qh128a cmd write parameters, the address_code and data_counter need to be set in application */
static const qspi_cmd_type en25qh128a_write_para = {
FALSE,0,0x32,QSPI_CMD_INSLEN_1_BYTE,0,QSPI_CMD_ADRLEN_3_BYTE,0,0,QSPI_OPERATE_MODE_114,QSPI_RSTSC_HW_AUTO,FALSE,TRUE};

/* en25qh128a cmd sector erase parameters, the address_code need to be set in application */
static const qspi_cmd_type en25qh128a_erase_para = {
FALSE,0,0x20,QSPI_CMD_INSLEN_1_BYTE,0,QSPI_CMD_ADRLEN_3_BYTE,0,0,QSPI_OPERATE_MODE_111,QSPI_RSTSC_HW_AUTO,FALSE,TRUE};

/* en25qh128a cmd wren parameters */
static const qspi_cmd_type en25qh128a_wren_para = {
FALSE,0,0x06,QSPI_CMD_INSLEN_1_BYTE,0,QSPI_CMD_ADRLEN_0_BYTE,0,0,QSPI_OPERATE_MODE_111,QSPI_RSTSC_HW_AUTO,FALSE,TRUE};

/* en25qh128a cmd rdsr parameters (auto-polling mode for busy check) */
static const qspi_cmd_type en25qh128a_rdsr_para = {
FALSE,0,0x05,QSPI_CMD_INSLEN_1_BYTE,0,QSPI_CMD_ADRLEN_0_BYTE,0,0,QSPI_OPERATE_MODE_111,QSPI_RSTSC_HW_AUTO,TRUE,FALSE};

/* w25q128 cmd write status registers (SR1 and SR2) parameters */
static const qspi_cmd_type w25q128_wrsr_para = {
FALSE,0,0x01,QSPI_CMD_INSLEN_1_BYTE,0,QSPI_CMD_ADRLEN_0_BYTE,0,0,QSPI_OPERATE_MODE_111,QSPI_RSTSC_HW_AUTO,FALSE,TRUE};

/* en25qh128a cmd rsten parameters */
static const qspi_cmd_type en25qh128a_rsten_para = {
FALSE,0,0x66,QSPI_CMD_INSLEN_1_BYTE,0,QSPI_CMD_ADRLEN_0_BYTE,0,0,QSPI_OPERATE_MODE_111,QSPI_RSTSC_HW_AUTO,FALSE,TRUE};

/* en25qh128a cmd rst parameters */
static const qspi_cmd_type en25qh128a_rst_para = {
FALSE,0,0x99,QSPI_CMD_INSLEN_1_BYTE,0,QSPI_CMD_ADRLEN_0_BYTE,0,0,QSPI_OPERATE_MODE_111,QSPI_RSTSC_HW_AUTO,FALSE,TRUE};

/* en25qh128a/w25q RDID(0x9F) 命令口读 3 字节参数（命令口读：无地址、读状态关、写数据关，data_counter=3） */
static const qspi_cmd_type qspi_rdid_para = {
FALSE,0,0x9F,QSPI_CMD_INSLEN_1_BYTE,0,QSPI_CMD_ADRLEN_0_BYTE,3,0,QSPI_OPERATE_MODE_111,QSPI_RSTSC_HW_AUTO,FALSE,FALSE};

/* en25qh128a xip init parameters */
static const qspi_xip_type en25qh128a_xip_init_para = {
0x6B,QSPI_XIP_ADDRLEN_3_BYTE,QSPI_OPERATE_MODE_114,8,0x32,QSPI_XIP_ADDRLEN_3_BYTE,QSPI_OPERATE_MODE_114,0,QSPI_XIPW_SEL_MODED,0x7F,0x1F,QSPI_XIPR_SEL_MODET,0x7F,0x1F};

qspi_cmd_type en25qh128a_cmd_config;

/**
  * @brief  initialize EDMA for QSPI TX with double buffer and link list
  * @param  none
  * @retval none
  */
void qspi_edma_init(void)
{
  /* enable edma clock */
  crm_periph_clock_enable(CRM_EDMA_PERIPH_CLOCK, TRUE);

  /* enable edmamux */
  edmamux_enable(TRUE);

  /* edma configuration for qspi tx */
  edma_reset(QSPI_EDMA_STREAM);
  edma_default_para_init(&edma_init_struct);
  edma_init_struct.direction = EDMA_DIR_MEMORY_TO_PERIPHERAL;
  edma_init_struct.memory_inc_enable = TRUE;
  edma_init_struct.peripheral_inc_enable = FALSE;
  edma_init_struct.memory_data_width = EDMA_MEMORY_DATA_WIDTH_BYTE;
  edma_init_struct.peripheral_data_width = EDMA_PERIPHERAL_DATA_WIDTH_BYTE;
  edma_init_struct.loop_mode_enable = FALSE;
  edma_init_struct.priority = EDMA_PRIORITY_HIGH;
  edma_init_struct.fifo_mode_enable = TRUE;
  edma_init_struct.fifo_threshold = EDMA_FIFO_THRESHOLD_FULL;
  edma_init_struct.memory_burst_mode = EDMA_MEMORY_BURST_4;
  edma_init_struct.peripheral_burst_mode = EDMA_PERIPHERAL_BURST_4;
  edma_init_struct.peripheral_base_addr = (uint32_t)&(QSPI1->dt);
  edma_init_struct.buffer_size = 0;  // will be set dynamically
  edma_init_struct.memory0_base_addr = (uint32_t)qspi_dma_buffer0;
  edma_init(QSPI_EDMA_STREAM, &edma_init_struct);

  /* Note: Hardware double buffer mode is disabled for manual buffer management
   * Hardware auto-switching is suitable for continuous streaming but not for
   * our use case where each transfer is small (256 bytes per page) and independent.
   * We manually alternate between buffer0 and buffer1 to reduce cache conflicts. */
  edma_double_buffer_mode_enable(QSPI_EDMA_STREAM, FALSE);

  /* configure edmamux */
  edmamux_init(QSPI_EDMAMUX_CHANNEL, EDMAMUX_DMAREQ_ID_QSPI1);

  /* enable edma transfer complete and error interrupts (disable half transfer) */
  edma_interrupt_enable(QSPI_EDMA_STREAM, EDMA_FDT_INT, TRUE);
  edma_interrupt_enable(QSPI_EDMA_STREAM, EDMA_HDT_INT, FALSE);  // Disable half transfer interrupt
  edma_interrupt_enable(QSPI_EDMA_STREAM, EDMA_DTERR_INT, TRUE);

  /* enable edma stream1 nvic interrupt - priority 0 (HIGHEST - must preempt USB to avoid deadlock) */
  nvic_irq_enable(EDMA_Stream1_IRQn, 0, 0);
}

/**
  * @brief  edma stream1 interrupt handler for qspi with double buffer support
  * @param  none
  * @retval none
  */
extern "C" void EDMA_Stream1_IRQHandler(void)
{
  /* Debug: increment interrupt count */
  edma_irq_count++;

  /* half transfer complete - buffer 0 or buffer 1 is ready to be refilled */
  if(edma_flag_get(EDMA_HDT1_FLAG) != RESET)
  {
    edma_hdt_count++;
    edma_flag_clear(EDMA_HDT1_FLAG);

    /* toggle current buffer indicator */
    qspi_current_buffer = 1 - qspi_current_buffer;

    /* CPU can prepare next data in the idle buffer here */
  }

  /* full transfer complete */
  if(edma_flag_get(EDMA_FDT1_FLAG) != RESET)
  {
    edma_fdt_count++;
    /* clear transfer complete flag */
    edma_flag_clear(EDMA_FDT1_FLAG);

    /* set transfer done flag */
    qspi_dma_transfer_done = 1;

    /* check if link list is not enabled, then disable stream */
    if((EDMA->llctrl & 0x0001) == 0)
    {
      /* disable edma stream */
      edma_stream_enable(QSPI_EDMA_STREAM, FALSE);

      /* disable qspi dma */
      qspi_dma_enable(QSPI1, FALSE);
    }
  }

  /* transfer error */
  if(edma_flag_get(EDMA_DTERR1_FLAG) != RESET)
  {
    edma_err_count++;
    edma_flag_clear(EDMA_DTERR1_FLAG);

    /* disable edma stream */
    edma_stream_enable(QSPI_EDMA_STREAM, FALSE);
    qspi_dma_enable(QSPI1, FALSE);

    /* set transfer done flag to prevent infinite loop */
    qspi_dma_transfer_done = 1;
  }
}

/* 内部前置声明 */
qspi_status_t qspi_busy_check(void);
qspi_status_t qspi_write_enable(void);
qspi_status_t qspi_cmd_send(qspi_cmd_type* qspi_cmd_struct);
static qspi_status_t qspi_cmd_send_ex(qspi_cmd_type* qspi_cmd_struct, uint32_t timeout_ms);

/**
  * @brief  带超时地等待某个 QSPI 标志置位（fail-closed：超时返错，绝不死循环）
  * @param  flag: 待等待的标志位
  * @param  timeout_ms: 超时毫秒数（基于 millis()）
  * @retval QSPI_OK / QSPI_ERR_TIMEOUT
  */
static qspi_status_t qspi_wait_flag(uint32_t flag, uint32_t timeout_ms)
{
  uint32_t start = millis();
  while(qspi_flag_get(QSPI1, flag) == RESET)
  {
    if((millis() - start) >= timeout_ms)
      return QSPI_ERR_TIMEOUT;
  }
  return QSPI_OK;
}

/**
  * @brief  带超时地等待 DMA 传输完成（ISR 置 qspi_dma_transfer_done；fail-closed）
  * @param  timeout_ms: 超时毫秒数
  * @retval QSPI_OK / QSPI_ERR_TIMEOUT
  */
static qspi_status_t qspi_wait_dma_done(uint32_t timeout_ms)
{
  uint32_t start = millis();
  while(qspi_dma_transfer_done == 0)
  {
    if((millis() - start) >= timeout_ms)
    {
      /* 超时兜底：停流、关 DMA，避免残留 DMA 打断后续外设 */
      edma_stream_enable(QSPI_EDMA_STREAM, FALSE);
      qspi_dma_enable(QSPI1, FALSE);
      return QSPI_ERR_TIMEOUT;
    }
  }
  return QSPI_OK;
}

/**
  * @brief  带超时地等待 EDMA stream 完全停用（EN 位清零）
  * @retval QSPI_OK / QSPI_ERR_TIMEOUT
  */
static qspi_status_t qspi_wait_stream_disabled(uint32_t timeout_ms)
{
  uint32_t start = millis();
  while(QSPI_EDMA_STREAM->ctrl & 0x01)
  {
    if((millis() - start) >= timeout_ms)
      return QSPI_ERR_TIMEOUT;
  }
  return QSPI_OK;
}

/**
  * @brief  地址区间是否越界或触碰自检保留区（契约 §0.4/§0.5）
  * @retval true 合法；false 越界或触自检区
  */
static bool qspi_range_ok(uint32_t addr, uint32_t len)
{
  uint32_t end;
  if(len == 0)
    return false;
  /* 溢出与容量上界检查 */
  if(addr >= QSPI_FLASH_CAPACITY)
    return false;
  end = addr + len;
  if(end < addr || end > QSPI_FLASH_CAPACITY)
    return false;
  /* 自检保留区 0x7F0000..0x7FFFFF 永久避让：区间不得与之相交 */
  if(addr < (QSPI_SELFTEST_ADDR + QSPI_SELFTEST_SIZE) &&
     QSPI_SELFTEST_ADDR < end)
    return false;
  return true;
}

/**
  * @brief  自检区间检查：区间必须完整落在自检保留区 0x7F0000..0x7FFFFF 内
  * @retval true 合法（仅自检 API 使用）；false 越界
  */
static bool qspi_range_selftest_ok(uint32_t addr, uint32_t len)
{
  uint32_t end;
  if(len == 0)
    return false;
  if(addr < QSPI_SELFTEST_ADDR)
    return false;
  end = addr + len;
  if(end < addr || end > (QSPI_SELFTEST_ADDR + QSPI_SELFTEST_SIZE))
    return false;
  return true;
}

/**
  * @brief  setup link list nodes for chained DMA transfers
  * @param  buf: source data buffer
  * @param  total_len: total length to transfer
  * @param  node_count: pointer to store number of nodes created
  * @retval none
  */
static void qspi_setup_link_list(uint8_t* buf, uint32_t total_len, uint32_t* node_count)
{
  uint32_t remaining = total_len;
  uint32_t offset = 0;
  uint32_t count = 0;
  uint32_t chunk_size;

  while(remaining > 0 && count < MAX_LINK_NODES)
  {
    chunk_size = (remaining > QSPI_DMA_BUFFER_SIZE) ? QSPI_DMA_BUFFER_SIZE : remaining;

    /* setup link list node */
    edma_link_nodes[count].ctrl = QSPI_EDMA_STREAM->ctrl;
    edma_link_nodes[count].dtcnt = chunk_size;
    edma_link_nodes[count].paddr = (uint32_t)&(QSPI1->dt);
    edma_link_nodes[count].m0addr = (uint32_t)(buf + offset);
    edma_link_nodes[count].m1addr = (uint32_t)(buf + offset + chunk_size);
    edma_link_nodes[count].fctrl = QSPI_EDMA_STREAM->fctrl;

    /* set link to next node, or 0 for last node */
    if(remaining > chunk_size && count < (MAX_LINK_NODES - 1))
    {
      edma_link_nodes[count].llp = (uint32_t)&edma_link_nodes[count + 1];
    }
    else
    {
      edma_link_nodes[count].llp = 0;  // last node
    }

    remaining -= chunk_size;
    offset += chunk_size;
    count++;
  }

  *node_count = count;
}

/**
  * @brief  qspi 写核心（不含区间策略；调用方负责区间检查）
  * @param  addr/total_len/buf: 同 qspi_data_write
  * @retval QSPI_OK / QSPI_ERR_TIMEOUT
  */
static qspi_status_t qspi_data_write_core(uint32_t addr, uint32_t total_len, uint8_t* buf)
{
 uint32_t i, len;
 uint32_t node_count = 0;
 qspi_status_t st;

 do
 {
   st = qspi_write_enable();
   if(st != QSPI_OK)
     return st;
    /* send up to 256 bytes at one time, and only one page */
    len = (addr / FLASH_PAGE_PROGRAM_SIZE + 1) * FLASH_PAGE_PROGRAM_SIZE - addr;
    if(total_len < len)
      len = total_len;

   en25qh128a_cmd_config = en25qh128a_write_para;
   en25qh128a_cmd_config.address_code = addr;
   en25qh128a_cmd_config.data_counter = len;
   qspi_cmd_operation_kick(QSPI1, &en25qh128a_cmd_config);

   /* determine transfer mode based on data size */
   if(len < 32)
   {
     /* Mode 1: CPU transfer for small data (<32 bytes) */
     qspi_cpu_transfer_count++;
     for(i = 0; i < len; ++i)
     {
       st = qspi_wait_flag(QSPI_TXFIFORDY_FLAG, QSPI_FIFO_TIMEOUT_MS);
       if(st != QSPI_OK)
         return st;
       qspi_byte_write(QSPI1, *buf++);
     }
   }
   else if(len <= QSPI_DMA_BUFFER_SIZE * 2)
   {
     /* Mode 2: Double buffer DMA for medium data (32 bytes - 8KB) */
     qspi_double_buffer_transfer_count++;
     uint32_t transferred = 0;
     uint32_t buffer_index = 0;
     uint32_t chunk;
     uint8_t* current_buffer;

     while(transferred < len)
     {
       chunk = (len - transferred > QSPI_DMA_BUFFER_SIZE) ? QSPI_DMA_BUFFER_SIZE : (len - transferred);

       /* select buffer and copy data */
       current_buffer = (buffer_index == 0) ? qspi_dma_buffer0 : qspi_dma_buffer1;
       memcpy(current_buffer, buf + transferred, chunk);

       /* STEP 1: Disable EDMA stream before reconfiguration */
       edma_stream_enable(QSPI_EDMA_STREAM, FALSE);

       /* STEP 2: Wait for stream to be fully disabled (check EN bit) */
       st = qspi_wait_stream_disabled(QSPI_DMA_TIMEOUT_MS);
       if(st != QSPI_OK)
         return st;

       /* STEP 3: Configure DMA parameters while stream is disabled */
       edma_data_number_set(QSPI_EDMA_STREAM, chunk);
       edma_memory_addr_set(QSPI_EDMA_STREAM, (uint32_t)current_buffer, EDMA_MEMORY_0);

       /* STEP 4: Clear all EDMA flags before starting transfer */
       edma_flag_clear(EDMA_FDT1_FLAG);
       edma_flag_clear(EDMA_HDT1_FLAG);
       edma_flag_clear(EDMA_DTERR1_FLAG);

       /* STEP 5: Set QSPI DMA threshold */
       qspi_dma_tx_threshold_set(QSPI1, QSPI_DMA_FIFO_THOD_WORD08);

       /* STEP 6: Clear transfer done flag */
       qspi_dma_transfer_done = 0;

       /* STEP 7: Enable QSPI DMA */
       qspi_dma_enable(QSPI1, TRUE);

       /* STEP 8: Enable EDMA stream to start transfer */
       edma_stream_enable(QSPI_EDMA_STREAM, TRUE);

       /* wait for dma transfer complete */
       st = qspi_wait_dma_done(QSPI_DMA_TIMEOUT_MS);
       if(st != QSPI_OK)
         return st;

       transferred += chunk;
       buffer_index = 1 - buffer_index;  // toggle buffer to reduce cache conflicts
     }
   }
   else
   {
     /* Mode 3: Link list DMA for large data (>8KB) */
     qspi_link_list_transfer_count++;
     qspi_setup_link_list(buf, len, &node_count);

     if(node_count > 0)
     {
       /* initialize link list */
       edma_link_list_init(EDMA_STREAM1_LL, (uint32_t)&edma_link_nodes[0]);

       /* enable link list mode */
       edma_link_list_enable(EDMA_STREAM1_LL, TRUE);
       /* STEP 1: Disable EDMA stream before reconfiguration */
       edma_stream_enable(QSPI_EDMA_STREAM, FALSE);

       /* STEP 2: Wait for stream to be fully disabled (check EN bit) */
       st = qspi_wait_stream_disabled(QSPI_DMA_TIMEOUT_MS);
       if(st != QSPI_OK)
       {
         edma_link_list_enable(EDMA_STREAM1_LL, FALSE);
         return st;
       }

       /* STEP 3: Configure first transfer parameters while stream is disabled */
       edma_data_number_set(QSPI_EDMA_STREAM, edma_link_nodes[0].dtcnt);
       edma_memory_addr_set(QSPI_EDMA_STREAM, edma_link_nodes[0].m0addr, EDMA_MEMORY_0);

       /* STEP 4: Clear all EDMA flags before starting transfer */
       edma_flag_clear(EDMA_FDT1_FLAG);
       edma_flag_clear(EDMA_HDT1_FLAG);
       edma_flag_clear(EDMA_DTERR1_FLAG);

       /* STEP 5: Set QSPI DMA threshold */
       qspi_dma_tx_threshold_set(QSPI1, QSPI_DMA_FIFO_THOD_WORD08);

       /* STEP 6: Clear transfer done flag */
       qspi_dma_transfer_done = 0;

       /* STEP 7: Enable QSPI DMA */
       qspi_dma_enable(QSPI1, TRUE);

       /* STEP 8: Enable EDMA stream to start transfer */
       edma_stream_enable(QSPI_EDMA_STREAM, TRUE);

       /* wait for all linked transfers complete */
       st = qspi_wait_dma_done(QSPI_DMA_TIMEOUT_MS);

       /* disable link list mode */
       edma_link_list_enable(EDMA_STREAM1_LL, FALSE);

       if(st != QSPI_OK)
         return st;
     }
   }

   total_len -= len;
   addr += len;
   if(len >= 32)
     buf += len;  // buf already advanced in CPU mode

   /* wait command completed */
   st = qspi_wait_flag(QSPI_CMDSTS_FLAG, QSPI_CMD_TIMEOUT_MS);
   if(st != QSPI_OK)
     return st;
   qspi_flag_clear(QSPI1, QSPI_CMDSTS_FLAG);

   /* wait for page program completion（覆盖写周期，长超时） */
   st = qspi_busy_check();
   if(st != QSPI_OK)
     return st;

 }while(total_len);

 return QSPI_OK;
}

/**
  * @brief  qspi write data（生产路径，区间策略：拒绝越界/自检保留区）
  * @retval QSPI_OK / QSPI_ERR_PARAM / QSPI_ERR_REGION / QSPI_ERR_TIMEOUT
  */
qspi_status_t qspi_data_write(uint32_t addr, uint32_t total_len, uint8_t* buf)
{
  if(buf == NULL)
    return QSPI_ERR_PARAM;
  /* 越界或触碰自检保留区一律 fail-closed 拒绝 */
  if(!qspi_range_ok(addr, total_len))
    return QSPI_ERR_REGION;
  return qspi_data_write_core(addr, total_len, buf);
}

/**
  * @brief  qspi write data（自检专用，区间策略：仅允许落在自检保留区内）
  * @retval QSPI_OK / QSPI_ERR_PARAM / QSPI_ERR_REGION / QSPI_ERR_TIMEOUT
  */
qspi_status_t qspi_data_write_selftest(uint32_t addr, uint32_t total_len, uint8_t* buf)
{
  if(buf == NULL)
    return QSPI_ERR_PARAM;
  if(!qspi_range_selftest_ok(addr, total_len))
    return QSPI_ERR_REGION;
  return qspi_data_write_core(addr, total_len, buf);
}

/**
  * @brief  qspi 擦除核心（不含区间策略检查；4KB 扇区擦除）
  * @retval QSPI_OK / QSPI_ERR_TIMEOUT（fail-closed，绝不死循环）
  */
static qspi_status_t qspi_erase_core(uint32_t sec_addr)
{
  qspi_status_t st;

  st = qspi_write_enable();
  if(st != QSPI_OK)
    return st;

  en25qh128a_cmd_config = en25qh128a_erase_para;
  en25qh128a_cmd_config.address_code = sec_addr;
  st = qspi_cmd_send(&en25qh128a_cmd_config);
  if(st != QSPI_OK)
    return st;

  /* 擦除周期长，用 busy 长超时 */
  return qspi_busy_check();
}

/**
  * @brief  qspi erase data（生产路径，4KB 扇区擦除）
  * @param  sec_addr: the sector address for erase
  * @retval QSPI_OK 成功；QSPI_ERR_REGION 越界/触自检区；QSPI_ERR_TIMEOUT 忙等超时
  */
qspi_status_t qspi_erase(uint32_t sec_addr)
{
  /* 擦除粒度 4KB；越界或触碰自检保留区 fail-closed 拒绝 */
  if(!qspi_range_ok(sec_addr, QSPI_DMA_BUFFER_SIZE))
    return QSPI_ERR_REGION;
  return qspi_erase_core(sec_addr);
}

/**
  * @brief  qspi erase data（自检专用，仅允许自检保留区内）
  * @retval QSPI_OK / QSPI_ERR_REGION / QSPI_ERR_TIMEOUT
  */
qspi_status_t qspi_erase_selftest(uint32_t sec_addr)
{
  if(!qspi_range_selftest_ok(sec_addr, QSPI_DMA_BUFFER_SIZE))
    return QSPI_ERR_REGION;
  return qspi_erase_core(sec_addr);
}

/**
  * @brief  qspi check busy（RDSR 自动轮询，带超时）
  * @param  none
  * @retval QSPI_OK / QSPI_ERR_TIMEOUT
  */
qspi_status_t qspi_busy_check(void)
{
  /* RDSR 自动轮询覆盖擦写周期，用较长的 busy 超时 fail-closed */
  return qspi_cmd_send_ex((qspi_cmd_type*)&en25qh128a_rdsr_para, QSPI_BUSY_TIMEOUT_MS);
}

/**
  * @brief  qspi write enable（带超时）
  * @param  none
  * @retval QSPI_OK / QSPI_ERR_TIMEOUT
  */
qspi_status_t qspi_write_enable(void)
{
  return qspi_cmd_send((qspi_cmd_type*)&en25qh128a_wren_para);
}

/**
  * @brief  qspi cmd kick and wait completed（可指定超时；fail-closed）
  * @param  qspi_cmd_struct: the pointer for qspi_cmd_type parameter
  * @param  timeout_ms: 命令完成超时毫秒数
  * @retval QSPI_OK / QSPI_ERR_PARAM / QSPI_ERR_TIMEOUT
  */
static qspi_status_t qspi_cmd_send_ex(qspi_cmd_type* qspi_cmd_struct, uint32_t timeout_ms)
{
  qspi_status_t st;

  if(qspi_cmd_struct == NULL)
    return QSPI_ERR_PARAM;

  /* kick command */
  qspi_cmd_operation_kick(QSPI1, qspi_cmd_struct);

  /* wait command completed（带超时，绝不死循环） */
  st = qspi_wait_flag(QSPI_CMDSTS_FLAG, timeout_ms);
  if(st != QSPI_OK)
    return st;
  qspi_flag_clear(QSPI1, QSPI_CMDSTS_FLAG);
  return QSPI_OK;
}

/**
  * @brief  qspi cmd kick and wait completed（命令口短超时；fail-closed）
  * @param  qspi_cmd_struct: the pointer for qspi_cmd_type parameter
  * @retval QSPI_OK / QSPI_ERR_PARAM / QSPI_ERR_TIMEOUT
  */
qspi_status_t qspi_cmd_send(qspi_cmd_type* qspi_cmd_struct)
{
  return qspi_cmd_send_ex(qspi_cmd_struct, QSPI_CMD_TIMEOUT_MS);
}

/**
  * @brief  set QE bit in status register-2 for W25Q128
  * @param  none
  * @retval QSPI_OK / QSPI_ERR_TIMEOUT
  * @note   directly write SR1=0x00 (no protection) and SR2=0x02 (QE bit set)
  */
qspi_status_t qspi_set_qe_bit(void)
{
  qspi_cmd_type wrsr_cmd;
  qspi_status_t st;

  /* write enable */
  st = qspi_write_enable();
  if(st != QSPI_OK)
    return st;

  /* write both status registers: SR1=0x00, SR2=0x02 (QE bit set) */
  wrsr_cmd = w25q128_wrsr_para;
  wrsr_cmd.data_counter = 2;
  qspi_cmd_operation_kick(QSPI1, &wrsr_cmd);

  /* write SR1=0x00 (no write protection) */
  st = qspi_wait_flag(QSPI_TXFIFORDY_FLAG, QSPI_FIFO_TIMEOUT_MS);
  if(st != QSPI_OK)
    return st;
  qspi_byte_write(QSPI1, 0x00);

  /* write SR2=0x02 (QE bit set, bit 1 = 1) */
  st = qspi_wait_flag(QSPI_TXFIFORDY_FLAG, QSPI_FIFO_TIMEOUT_MS);
  if(st != QSPI_OK)
    return st;
  qspi_byte_write(QSPI1, 0x02);

  /* wait command completed */
  st = qspi_wait_flag(QSPI_CMDSTS_FLAG, QSPI_CMD_TIMEOUT_MS);
  if(st != QSPI_OK)
    return st;
  qspi_flag_clear(QSPI1, QSPI_CMDSTS_FLAG);

  /* wait for write completion（写状态寄存器周期，长超时） */
  return qspi_busy_check();
}

/**
  * @brief  复位外部 flash（RSTEN 0x66 + RST 0x99），退出上一轮遗留的
  *         连续读/XIP 模式，使命令口 1-1-1 指令（如 RDID 0x9F）可被识别。
  * @note   暖复位（J-Link NRST）后 QSPI 控制器寄存器复位，但 flash 芯片
  *         仍保持上次 en25qh128a_qspi_xip_init 设置的连续读模式；此时未复位
  *         直接发 RDID 会读到 0x000000。必须先在命令口态发复位序列。
  * @retval QSPI_OK / QSPI_ERR_TIMEOUT
  */
qspi_status_t qspi_flash_reset(void)
{
  qspi_status_t st;

  /* 确保控制器处于命令口模式 */
  qspi_xip_enable(QSPI1, FALSE);

  st = qspi_cmd_send((qspi_cmd_type*)&en25qh128a_rsten_para);
  if(st != QSPI_OK)
    return st;
  st = qspi_cmd_send((qspi_cmd_type*)&en25qh128a_rst_para);
  if(st != QSPI_OK)
    return st;

  /* flash tRST 恢复时间（数据手册 ~30us），给足余量 */
  delay_us(100);
  return QSPI_OK;
}

/**
  * @brief  读 JEDEC ID(RDID 0x9F)，命令口 3 字节读
  * @param  id: 出参，manuf<<16 | mem_type<<8 | capacity
  * @retval QSPI_OK / QSPI_ERR_PARAM / QSPI_ERR_TIMEOUT
  * @note   调用前必须已复位 flash 退出连续读模式（见 qspi_flash_reset），
  *         否则暖复位后读到 0x000000。
  */
qspi_status_t qspi_read_jedec_id(uint32_t* id)
{
  qspi_cmd_type cmd;
  qspi_status_t st;
  uint8_t b[3];
  int i;

  if(id == NULL)
    return QSPI_ERR_PARAM;

  cmd = qspi_rdid_para;
  qspi_cmd_operation_kick(QSPI1, &cmd);

  /* 小定长读的正确姿势：先等命令完成（CMDSTS），此时硬件已把全部 dcnt 字节
   * 时钟进 RXFIFO；再从数据寄存器逐字节 drain。
   * 不依赖 RXFIFORDY：该 ready 标志按 RX FIFO 阈值触发（复位默认阈值 = 最小
   * 档 WORD08 = 8 word = 32B），3 字节 RDID 永远达不到阈值，若逐字节等
   * RXFIFORDY 会在首字节就超时、id 归零（真机复验的 JEDEC=0 根因）。
   * TXFIFORDY 是“FIFO 有空位”一开始即真，故写路径逐字节轮询可行，读路径不对称。 */
  st = qspi_wait_flag(QSPI_CMDSTS_FLAG, QSPI_CMD_TIMEOUT_MS);
  if(st != QSPI_OK)
    return st;
  qspi_flag_clear(QSPI1, QSPI_CMDSTS_FLAG);

  /* 命令完成后 RXFIFO 内已有 3 字节，逐字节 drain 数据寄存器 */
  for(i = 0; i < 3; i++)
    b[i] = qspi_byte_read(QSPI1);

  *id = ((uint32_t)b[0] << 16) | ((uint32_t)b[1] << 8) | (uint32_t)b[2];
  return QSPI_OK;
}

/**
  * @brief  JEDEC ID 是否在 OTA 白名单内（契约 §0.7）
  * @param  id: qspi_read_jedec_id 读出的值
  * @retval true 在白名单；false 不识别（调用方应置 OTA 禁用旗标）
  */
bool qspi_jedec_is_whitelisted(uint32_t id)
{
  return (id == QSPI_JEDEC_W25Q128) ||
         (id == QSPI_JEDEC_EN25QH128A) ||
         (id == QSPI_JEDEC_EN25QH64A) ||
         (id == QSPI_JEDEC_W25Q64);
}

/**
  * @brief  超时路径注错自检：在不 kick 任何命令时等待 CMDSTS。
  *         正常固件里 CMDSTS 保持 RESET，故本调用必须在 timeout_ms 后
  *         返回 QSPI_ERR_TIMEOUT（证明 fail-closed 生效，绝不死循环）。
  * @param  timeout_ms: 注错等待时限
  * @retval 期望恒为 QSPI_ERR_TIMEOUT
  */
qspi_status_t qspi_probe_timeout(uint32_t timeout_ms)
{
  /* 先清一次 CMDSTS，确保等待期间标志为 RESET */
  qspi_flag_clear(QSPI1, QSPI_CMDSTS_FLAG);
  return qspi_wait_flag(QSPI_CMDSTS_FLAG, timeout_ms);
}

qspi_status_t en25qh128a_qspi_xip_init(void)
{
  qspi_status_t st;

  /* switch to command-port mode */
  qspi_xip_enable(QSPI1, FALSE);

  /* system reset */
  st = qspi_cmd_send((qspi_cmd_type*)&en25qh128a_rsten_para);
  if(st != QSPI_OK)
    return st;
  st = qspi_cmd_send((qspi_cmd_type*)&en25qh128a_rst_para);
  if(st != QSPI_OK)
    return st;

  /* set QE bit for W25Q128 to enable quad SPI */
  st = qspi_set_qe_bit();
  if(st != QSPI_OK)
    return st;

  /* initial xip */
  qspi_xip_init(QSPI1, (qspi_xip_type*)&en25qh128a_xip_init_para);
  qspi_xip_enable(QSPI1, TRUE);
  return QSPI_OK;
}

/**
  * @brief  get transfer mode statistics
  * @param  cpu_count: pointer to receive CPU transfer count
  * @param  double_buffer_count: pointer to receive double buffer transfer count
  * @param  link_list_count: pointer to receive link list transfer count
  * @retval none
  */
void qspi_get_transfer_stats(uint32_t* cpu_count, uint32_t* double_buffer_count, uint32_t* link_list_count)
{
  if(cpu_count)
    *cpu_count = qspi_cpu_transfer_count;
  if(double_buffer_count)
    *double_buffer_count = qspi_double_buffer_transfer_count;
  if(link_list_count)
    *link_list_count = qspi_link_list_transfer_count;
}

/**
  * @brief  reset transfer mode statistics
  * @param  none
  * @retval none
  */
void qspi_reset_transfer_stats(void)
{
  qspi_cpu_transfer_count = 0;
  qspi_double_buffer_transfer_count = 0;
  qspi_link_list_transfer_count = 0;
}

}

/**
  * @}
  */

/**
  * @}
  */
