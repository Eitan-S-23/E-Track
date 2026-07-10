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

void qspi_busy_check(void);
void qspi_write_enable(void);
void qspi_cmd_send(qspi_cmd_type* qspi_cmd_struct);

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
  * @brief  qspi write data with double buffer and link list support
  * @param  addr: the address for write
  * @param  total_len: the length for write
  * @param  buf: the pointer for write data
  * @retval none
  */
void qspi_data_write(uint32_t addr, uint32_t total_len, uint8_t* buf)
{
 uint32_t i, len;
 uint32_t node_count = 0;

 do
 {
   qspi_write_enable();
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
       while(qspi_flag_get(QSPI1, QSPI_TXFIFORDY_FLAG) == RESET);
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
       while(QSPI_EDMA_STREAM->ctrl & 0x01);

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
       while(qspi_dma_transfer_done == 0);

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
       while(QSPI_EDMA_STREAM->ctrl & 0x01);

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
       while(qspi_dma_transfer_done == 0);

       /* disable link list mode */
       edma_link_list_enable(EDMA_STREAM1_LL, FALSE);
     }
   }

   total_len -= len;
   addr += len;
   if(len >= 32)
     buf += len;  // buf already advanced in CPU mode

   /* wait command completed */
   while(qspi_flag_get(QSPI1, QSPI_CMDSTS_FLAG) == RESET);
   qspi_flag_clear(QSPI1, QSPI_CMDSTS_FLAG);

   qspi_busy_check();

 }while(total_len);
}

/**
  * @brief  qspi erase data
  * @param  sec_addr: the sector address for erase
  * @retval none
  */
void qspi_erase(uint32_t sec_addr)
{
  qspi_write_enable();

  en25qh128a_cmd_config = en25qh128a_erase_para;
  en25qh128a_cmd_config.address_code = sec_addr; 
  qspi_cmd_send(&en25qh128a_cmd_config);

  qspi_busy_check();
}

/**
  * @brief  qspi check busy
  * @param  none
  * @retval none
  */
void qspi_busy_check(void)
{
  qspi_cmd_send((qspi_cmd_type*)&en25qh128a_rdsr_para);
}

/**
  * @brief  qspi write enable
  * @param  none
  * @retval none
  */
void qspi_write_enable(void)
{
  qspi_cmd_send((qspi_cmd_type*)&en25qh128a_wren_para);
}

/**
  * @brief  qspi cmd kick and wait completed
  * @param  qspi_cmd_struct: the pointer for qspi_cmd_type parameter
  * @retval none
  */
void qspi_cmd_send(qspi_cmd_type* qspi_cmd_struct)
{
  /* kick command */
  qspi_cmd_operation_kick(QSPI1, qspi_cmd_struct);

  /* wait command completed */
  while(qspi_flag_get(QSPI1, QSPI_CMDSTS_FLAG) == RESET);
  qspi_flag_clear(QSPI1, QSPI_CMDSTS_FLAG);
}

/**
  * @brief  set QE bit in status register-2 for W25Q128
  * @param  none
  * @retval none
  * @note   directly write SR1=0x00 (no protection) and SR2=0x02 (QE bit set)
  */
void qspi_set_qe_bit(void)
{
  qspi_cmd_type wrsr_cmd;

  /* write enable */
  qspi_write_enable();

  /* write both status registers: SR1=0x00, SR2=0x02 (QE bit set) */
  wrsr_cmd = w25q128_wrsr_para;
  wrsr_cmd.data_counter = 2;
  qspi_cmd_operation_kick(QSPI1, &wrsr_cmd);

  /* write SR1=0x00 (no write protection) */
  while(qspi_flag_get(QSPI1, QSPI_TXFIFORDY_FLAG) == RESET);
  qspi_byte_write(QSPI1, 0x00);

  /* write SR2=0x02 (QE bit set, bit 1 = 1) */
  while(qspi_flag_get(QSPI1, QSPI_TXFIFORDY_FLAG) == RESET);
  qspi_byte_write(QSPI1, 0x02);

  /* wait command completed */
  while(qspi_flag_get(QSPI1, QSPI_CMDSTS_FLAG) == RESET);
  qspi_flag_clear(QSPI1, QSPI_CMDSTS_FLAG);

  /* wait for write completion */
  qspi_busy_check();
}

void en25qh128a_qspi_xip_init(void)
{
  /* switch to command-port mode */
  qspi_xip_enable(QSPI1, FALSE);

  /* system reset */
  qspi_cmd_send((qspi_cmd_type*)&en25qh128a_rsten_para);
  qspi_cmd_send((qspi_cmd_type*)&en25qh128a_rst_para);

  /* set QE bit for W25Q128 to enable quad SPI */
  qspi_set_qe_bit();

  /* initial xip */
  qspi_xip_init(QSPI1, (qspi_xip_type*)&en25qh128a_xip_init_para);
  qspi_xip_enable(QSPI1, TRUE);
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
