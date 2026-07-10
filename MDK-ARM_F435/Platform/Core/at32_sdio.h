/**
  **************************************************************************
  * @file     at32_sdio.h
  * @brief    header file for at32_sdio.c
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

#ifndef __AT32_SDIO_H
#define __AT32_SDIO_H

#ifdef __cplusplus
extern "C" {
#endif

#include "at32f435_437_conf.h"
#include <stddef.h>  /* For NULL definition */

/** @addtogroup AT32F435_periph_examples
  * @{
  */

/** @addtogroup 435_SDIO_sd_mmc_card
  * @{
  */

/**
  * @brief  sdio specific error defines
  */
typedef enum
{
  /**
    * @brief  sdio specific error defines
    */
  SD_CMD_CRC_ERROR                    = (1),  /*!< command response received (but crc check failed) */
  SD_DATA_CRC_ERROR                   = (2),  /*!< data bock sent/received (crc check failed) */
  SD_CMD_RSP_TIMEOUT                  = (3),  /*!< command response timeout */
  SD_DATA_TIMEOUT                     = (4),  /*!< data time out */
  SD_TX_UNDERRUN                      = (5),  /*!< transmit fifo under-run */
  SD_RX_OVERRUN                       = (6),  /*!< receive fifo over-run */
  SD_START_BIT_ERR                    = (7),  /*!< start bit not detected on all data signals in widE bus mode */
  SD_CMD_OUT_OF_RANGE                 = (8),  /*!< cmd's argument was out of range.*/
  SD_ADDR_MISALIGNED                  = (9),  /*!< misaligned address */
  SD_BLOCK_LEN_ERR                    = (10), /*!< transferred block length is not allowed for the card or the number of transferred bytes does not match the block length */
  SD_ERASE_SEQ_ERR                    = (11), /*!< an error in the sequence of erase command occurs.*/
  SD_BAD_ERASE_PARAM                  = (12), /*!< an invalid selection for erase groups */
  SD_WRITE_PROT_VIOLATION             = (13), /*!< attempt to program a write protect block */
  SD_LOCK_UNLOCK_ERROR                = (14), /*!< sequence or password error has been detected in unlock command or if there was an attempt to access a locked card */
  SD_COM_CRC_ERROR                    = (15), /*!< crc check of the previous command failed */
  SD_ILLEGAL_CMD                      = (16), /*!< command is not legal for the card state */
  SD_CARD_ECC_ERROR                   = (17), /*!< card internal ecc was applied but failed to correct the data */
  SD_CC_ERROR                         = (18), /*!< internal card controller error */
  SD_GENERAL_UNKNOWN_ERROR            = (19), /*!< general or unknown error */
  SD_STREAM_READ_UNDERRUN             = (20), /*!< the card could not sustain data transfer in stream read operation. */
  SD_STREAM_WRITE_OVERRUN             = (21), /*!< the card could not sustain data programming in stream mode */
  SD_CID_CSD_OVERWRITE                = (22), /*!< cid/csd overwrite error */
  SD_WP_ERASE_SKIP                    = (23), /*!< only partial address space was erased */
  SD_CARD_ECC_DISABLED                = (24), /*!< command has been executed without using internal ecc */
  SD_ERASE_RESET                      = (25), /*!< erase sequence was cleared before executing because an out of erase sequence command was received */
  SD_AKE_SEQ_ERROR                    = (26), /*!< error in sequence of authentication. */
  SD_INVALID_VOLTRANGE                = (27),
  SD_ADDR_OUT_OF_RANGE                = (28),
  SD_SWITCH_ERROR                     = (29),
  SD_SDIO_DISABLED                    = (30),
  SD_SDIO_FUNCTION_BUSY               = (31),
  SD_SDIO_FUNCTION_ERROR              = (32),
  SD_SDIO_UNKNOWN_FUNC                = (33),

  /**
    * @brief  standard error defines
    */
  SD_INTERNAL_ERROR, 
  SD_NOT_CONFIGURED,
  SD_REQ_PENDING,
  SD_REQ_NOT_APPLICABLE,
  SD_INVALID_PARAMETER,  
  SD_UNSUPPORTED_FEATURE,
  SD_UNSUPPORTED_HW,
  SD_ERROR,
  SD_CMD_FAIL,      /*!< Command failed */
  SD_DATA_FAIL,     /*!< Data transfer failed */
  SD_OK = 0
} sd_error_status_type;

/**
  * @brief  sdio transfer state
  */
typedef enum
{
  SD_TRANSFER_OK  = 0,
  SD_TRANSFER_BUSY = 1,
  SD_TRANSFER_ERROR
} sd_transfer_status_type;

/**
  * @brief  sd card states
  */
typedef enum
{
  SD_CARD_READY                  = ((uint32_t)0x00000001),
  SD_CARD_IDENTIFICATION         = ((uint32_t)0x00000002),
  SD_CARD_STANDBY                = ((uint32_t)0x00000003),
  SD_CARD_TRANSFER               = ((uint32_t)0x00000004),
  SD_CARD_SENDING                = ((uint32_t)0x00000005),
  SD_CARD_RECEIVING              = ((uint32_t)0x00000006),
  SD_CARD_PROGRAMMING            = ((uint32_t)0x00000007),
  SD_CARD_DISCONNECTED           = ((uint32_t)0x00000008),
  SD_CARD_ERROR                  = ((uint32_t)0x000000FF)
} sd_card_state_type;

/**
  * @brief  card specific data: csd register
  */
typedef struct
{
  __IO uint8_t  csd_struct;            /*!< csd structure */
  __IO uint8_t  spec_version;          /*!< system specification version */
  __IO uint8_t  reserved1;             /*!< reserved */
  __IO uint8_t  taac;                  /*!< data read access-time 1 */
  __IO uint8_t  nsac;                  /*!< data read access-time 2 in clk cycles */
  __IO uint8_t  max_bus_clk_freq;      /*!< max. bus clock frequency */
  __IO uint16_t card_cmd_classes;      /*!< card command classes */
  __IO uint8_t  max_read_blk_length;   /*!< max. read data block length */
  __IO uint8_t  part_blk_read;         /*!< partial blocks for read allowed */
  __IO uint8_t  write_blk_misalign;    /*!< write block misalignment */
  __IO uint8_t  read_blk_misalign;     /*!< read block misalignment */
  __IO uint8_t  dsr_implemented;       /*!< dsr implemented */
  __IO uint8_t  reserved2;             /*!< reserved */
  __IO uint32_t device_size;           /*!< device size */
  __IO uint8_t  max_read_current_vdd_min;  /*!< max. read current @ vdd min */
  __IO uint8_t  max_read_current_vdd_max;  /*!< max. read current @ vdd max */
  __IO uint8_t  max_write_current_vdd_min; /*!< max. write current @ vdd min */
  __IO uint8_t  max_write_current_vdd_max; /*!< max. write current @ vdd max */
  __IO uint8_t  device_size_mult;      /*!< device size multiplier */
  __IO uint8_t  erase_group_size;      /*!< erase group size */
  __IO uint8_t  erase_group_size_mult; /*!< erase group size multiplier */
  __IO uint8_t  write_protect_group_size;  /*!< write protect group size */
  __IO uint8_t  write_protect_group_enable; /*!< write protect group enable */
  __IO uint8_t  manufacturer_default_ecc;   /*!< manufacturer default ecc */
  __IO uint8_t  write_speed_factor;    /*!< write speed factor */
  __IO uint8_t  max_write_blk_length;  /*!< max. write data block length */
  __IO uint8_t  part_blk_write;        /*!< partial blocks for write allowed */
  __IO uint8_t  reserved3;             /*!< reserbed */
  __IO uint8_t  content_protect_app;   /*!< content protection application */
  __IO uint8_t  file_format_group;     /*!< file format group */
  __IO uint8_t  copy_flag;             /*!< copy flag (otp) */
  __IO uint8_t  permanent_write_protect; /*!< permanent write protection */
  __IO uint8_t  temp_write_protect;    /*!< temporary write protection */
  __IO uint8_t  file_formart;          /*!< file format */
  __IO uint8_t  ecc_code;              /*!< ecc code */
  __IO uint8_t  csd_crc;               /*!< csd crc */
  __IO uint8_t  reserved4;             /*!< always 1*/
} sd_csd_reg_type;

/**
  * @brief  card identification data: cid register
  */
typedef struct
{
  __IO uint8_t  manufacturer_id;       /*!< manufacturer id */
  __IO uint16_t oem_app_id;            /*!< oem/application id */
  __IO uint32_t product_name1;         /*!< product name part1 */
  __IO uint8_t  product_name2;         /*!< product name part2*/
  __IO uint8_t  product_reversion;     /*!< product reversion */
  __IO uint32_t product_sn;            /*!< product serial number */
  __IO uint8_t  reserved1;             /*!< reserved1 */
  __IO uint16_t manufact_date;         /*!< manufacturing date */
  __IO uint8_t  cid_crc;               /*!< cid crc */
  __IO uint8_t  reserved2;             /*!< always 1 */
} sd_cid_reg_type;

/**
  * @brief sd card status
  */
typedef struct
{
  __IO uint8_t dat_bus_width;
  __IO uint8_t secured_mode;
  __IO uint16_t sd_card_type;
  __IO uint32_t size_of_protected_area;
  __IO uint8_t speed_class;
  __IO uint8_t performance_move;
  __IO uint8_t au_size;
  __IO uint16_t erase_size;
  __IO uint8_t erase_timeout;
  __IO uint8_t erase_offset;
} sd_card_status_type;

/**
  * @brief  sd card configuration register
  */
typedef struct
{
  __IO uint8_t  sd_spec;
  __IO uint8_t  sd_spec3;
  __IO uint8_t  sd_bus_width;
  __IO uint8_t  sd_security;
  __IO uint8_t  data_stat_after_erase;
  __IO uint8_t  sd_spec4;
  __IO uint8_t  sd_ex_security;
  __IO uint8_t  cmd_support;
} sd_scr_reg_type;

/**
  * @brief sd card information
  */
typedef struct
{
  sd_csd_reg_type sd_csd_reg;
  sd_cid_reg_type sd_cid_reg;
  sd_scr_reg_type sd_scr_reg;  /*!< SD card configuration register */
  uint64_t card_capacity;  /*!< card capacity */
  uint32_t card_blk_size;  /*!< card block size */
  uint16_t rca;
  uint8_t card_type;
} sd_card_info_struct_type;

/**
  * @brief  card type
  */
typedef enum
{
  SDIO_STD_CAPACITY_SD_CARD_V1_1     = 0,
  SDIO_STD_CAPACITY_SD_CARD_V2_0     = 1,
  SDIO_HIGH_CAPACITY_SD_CARD         = 2,
  SDIO_MULTIMEDIA_CARD                = 3,
  SDIO_SECURE_DIGITAL_IO_CARD        = 4,
  SDIO_HIGH_SPEED_MULTIMEDIA_CARD    = 5,
  SDIO_SECURE_DIGITAL_IO_COMBO_CARD  = 6,
  SDIO_HIGH_CAPACITY_MMC_CARD        = 7
} sd_memory_card_type;

/**
  * @brief  data bus mode
  */
typedef enum
{
  SD_TRANSFER_POLLING_MODE = 0,
  SD_TRANSFER_DMA_MODE = 1
} sd_data_transfer_mode_type;

/* define macro */
#define SDIOx                           SDIO2
#define DMAMUX_SDIOx                    DMAMUX_DMAREQ_ID_SDIO2

#define SD_DETECT_PIN                   GPIO_PINS_ALL
#define SD_DETECT_GPIO_PORT             GPIOA
#define SD_DETECT_GPIO_CLOCK            CRM_GPIOA_PERIPH_CLOCK

#define NULL_CARD                       0
#define SDIO_STATIC_FLAGS               ((uint32_t)0x000005FF)
#define SDIO_CMD0TIMEOUT                ((uint32_t)0x00010000)
#define SDIO_DATATIMEOUT                ((uint32_t)0xFFFFFFFF)
#define SD_ALLZERO                      0x00000000

#define SD_VOLTAGE_WINDOW_SD            0x80100000
#define SD_VOLTAGE_WINDOW_MMC           0x80FF8000
#define SD_HIGH_CAPACITY                0x40000000
#define SD_STD_CAPACITY                 0x00000000
#define SD_CHECK_PATTERN                0x000001AA
#define SD_MAX_VOLT_TRIAL               ((uint32_t)0x0000FFFF)

#define SD_INTR_STS_READ_MASK           ((uint32_t)(SDIO_DTFAIL_FLAG | SDIO_DTTIMEOUT_FLAG | \
                                                    SDIO_DTCMPL_FLAG | SDIO_RXERRO_FLAG | SDIO_SBITERR_FLAG))
#define SDIO_INTR_STS_READ_MASK         SD_INTR_STS_READ_MASK  /* Alias for compatibility */

#define SD_INTR_STS_WRITE_MASK          ((uint32_t)(SDIO_DTFAIL_FLAG | SDIO_DTTIMEOUT_FLAG | \
                                                    SDIO_DTCMPL_FLAG | SDIO_RXERRO_FLAG | SDIO_TXERRU_FLAG | \
                                                    SDIO_SBITERR_FLAG))
#define SDIO_INTR_STS_WRITE_MASK        SD_INTR_STS_WRITE_MASK  /* Alias for compatibility */

#define SD_MAX_DATA_LENGTH              ((uint32_t)0x01FFFFFF)

#define SD_HALFFIFO                     ((uint32_t)0x00000008)
#define SD_HALFFIFOBYTES                ((uint32_t)0x00000020)

/**
  * @brief  mask for errors card status r1 (ocr register)
  */
#define SD_OCR_ADDR_OUT_OF_RANGE        ((uint32_t)0x80000000)
#define SD_OCR_ADDR_MISALIGNED          ((uint32_t)0x40000000)
#define SD_OCR_BLOCK_LEN_ERR            ((uint32_t)0x20000000)
#define SD_OCR_ERASE_SEQ_ERR            ((uint32_t)0x10000000)
#define SD_OCR_BAD_ERASE_PARAM          ((uint32_t)0x08000000)
#define SD_OCR_WRITE_PROT_VIOLATION     ((uint32_t)0x04000000)
#define SD_OCR_LOCK_UNLOCK_ERROR        ((uint32_t)0x01000000)
#define SD_OCR_COM_CRC_ERROR            ((uint32_t)0x00800000)
#define SD_OCR_ILLEGAL_CMD              ((uint32_t)0x00400000)
#define SD_OCR_CARD_ECC_ERROR           ((uint32_t)0x00200000)
#define SD_OCR_CC_ERROR                 ((uint32_t)0x00100000)
#define SD_OCR_GENERAL_UNKNOWN_ERROR    ((uint32_t)0x00080000)
#define SD_OCR_STREAM_READ_UNDERRUN     ((uint32_t)0x00040000)
#define SD_OCR_STREAM_WRITE_OVERRUN     ((uint32_t)0x00020000)
#define SD_OCR_CID_CSD_OVERWRIETE       ((uint32_t)0x00010000)
#define SD_OCR_WP_ERASE_SKIP            ((uint32_t)0x00008000)
#define SD_OCR_CARD_ECC_DISABLED        ((uint32_t)0x00004000)
#define SD_OCR_ERASE_RESET              ((uint32_t)0x00002000)
#define SD_OCR_AKE_SEQ_ERROR            ((uint32_t)0x00000008)
#define SD_OCR_ERRORBITS                ((uint32_t)0xFDFFE008)

/**
  * @brief  masks for r6 response
  */
#define SD_R6_GENERAL_UNKNOWN_ERROR     ((uint32_t)0x00002000)
#define SD_R6_ILLEGAL_CMD               ((uint32_t)0x00004000)
#define SD_R6_CMD_CRC_ERROR             ((uint32_t)0x00008000)

#define SD_VOLTAGE_WINDOW_SD            0x80100000
#define SD_VOLTAGE_WINDOW_MMC           0x80FF8000
#define SD_HIGH_CAPACITY                0x40000000
#define SD_STD_CAPACITY                 0x00000000
#define SD_CHECK_PATTERN                0x000001AA

#define SD_MAX_VOLT_TRIAL               ((uint32_t)0x0000FFFF)
#define SD_ALLZERO                      0x00000000

#define SD_WIDE_BUS_SUPPORT             ((uint32_t)0x00040000)
#define SD_SINGLE_BUS_SUPPORT           ((uint32_t)0x00010000)
#define SD_CARD_LOCKED                  ((uint32_t)0x02000000)
#define SD_CARD_PROGRAMMING             0x07
#define SD_CARD_RECEIVING               0x06

#define SD_DATATIMEOUT                  ((uint32_t)0xFFFFFFFF)
#define SD_0TO7BITS                     ((uint32_t)0x000000FF)
#define SD_8TO15BITS                    ((uint32_t)0x0000FF00)
#define SD_16TO23BITS                   ((uint32_t)0x00FF0000)
#define SD_24TO31BITS                   ((uint32_t)0xFF000000)
#define SD_MAX_DATA_LENGTH              ((uint32_t)0x01FFFFFF)

#define SD_HALFFIFO                     ((uint32_t)0x00000008)
#define SD_HALFFIFOBYTES                ((uint32_t)0x00000020)

/**
  * @brief  command class supported
  */
#define SD_CCCC_ERASE                   ((uint32_t)0x00000020)

#define SD_SDIO_SEND_IF_COND            ((uint32_t)SD_CMD_HS_SEND_EXT_CSD)

#define MMC_SWITCH_ERROR                ((uint32_t)0x00000080)

/**
  * @brief  masks for r5 response
  */
#define SD_R5_OUT_OF_RANGE              ((uint32_t)0x00000100)
#define SD_R5_FUNCTION_NUMBER           ((uint32_t)0x00000200)
#define SD_R5_ERROR                     ((uint32_t)0x00000800)

/* sd command index */
#define SD_CMD_GO_IDLE_STATE                       ((uint8_t)0)
#define SD_CMD_SEND_OP_COND                        ((uint8_t)1)
#define SD_CMD_ALL_SEND_CID                        ((uint8_t)2)
#define SD_CMD_SET_REL_ADDR                        ((uint8_t)3)
#define SD_CMD_SET_DSR                             ((uint8_t)4)
#define SD_CMD_SDIO_SEN_OP_COND                    ((uint8_t)5)
#define SD_CMD_HS_SWITCH                           ((uint8_t)6)
#define SD_CMD_SEL_DESEL_CARD                      ((uint8_t)7)
#define SD_CMD_HS_SEND_EXT_CSD                     ((uint8_t)8)
#define SD_CMD_SEND_CSD                            ((uint8_t)9)
#define SD_CMD_SEND_CID                            ((uint8_t)10)
#define SD_CMD_READ_DAT_UNTIL_STOP                 ((uint8_t)11)
#define SD_CMD_STOP_TRANSMISSION                   ((uint8_t)12)
#define SD_CMD_SEND_STATUS                         ((uint8_t)13)
#define SD_CMD_HS_BUSTEST_READ                     ((uint8_t)14)
#define SD_CMD_GO_INACTIVE_STATE                   ((uint8_t)15)
#define SD_CMD_SET_BLOCKLEN                        ((uint8_t)16)
#define SD_CMD_READ_SINGLE_BLOCK                   ((uint8_t)17)
#define SD_CMD_READ_MULT_BLOCK                     ((uint8_t)18)
#define SD_CMD_HS_BUSTEST_WRITE                    ((uint8_t)19)
#define SD_CMD_WRITE_DAT_UNTIL_STOP                ((uint8_t)20)
#define SD_CMD_SET_BLOCK_COUNT                     ((uint8_t)23)
#define SD_CMD_WRITE_SINGLE_BLOCK                  ((uint8_t)24)
#define SD_CMD_WRITE_MULT_BLOCK                    ((uint8_t)25)
#define SD_CMD_PROG_CID                            ((uint8_t)26)
#define SD_CMD_PROG_CSD                            ((uint8_t)27)
#define SD_CMD_SET_WRITE_PROT                      ((uint8_t)28)
#define SD_CMD_CLR_WRITE_PROT                      ((uint8_t)29)
#define SD_CMD_SEND_WRITE_PROT                     ((uint8_t)30)
#define SD_CMD_SD_ERASE_GRP_START                  ((uint8_t)32)
#define SD_CMD_SD_ERASE_GRP_END                    ((uint8_t)33)
#define SD_CMD_ERASE_GRP_START                     ((uint8_t)35)
#define SD_CMD_ERASE_GRP_END                       ((uint8_t)36)
#define SD_CMD_ERASE                               ((uint8_t)38)
#define SD_CMD_FAST_IO                             ((uint8_t)39)
#define SD_CMD_GO_IRQ_STATE                        ((uint8_t)40)
#define SD_CMD_LOCK_UNLOCK                         ((uint8_t)42)
#define SD_CMD_APP_CMD                             ((uint8_t)55)
#define SD_CMD_GEN_CMD                             ((uint8_t)56)
#define SD_CMD_NO_CMD                              ((uint8_t)64)

/* following commands are sd card specific commands. */
/* sdio_app_cmd should be sent before sending these commands. */
#define SD_CMD_APP_SD_SET_BUSWIDTH                 ((uint8_t)6)
#define SD_CMD_SD_APP_STAUS                        ((uint8_t)13)
#define SD_CMD_SD_APP_SEND_NUM_WRITE_BLOCKS        ((uint8_t)22)
#define SD_CMD_SD_APP_OP_COND                      ((uint8_t)41)
#define SD_CMD_SD_APP_SET_CLR_CARD_DETECT          ((uint8_t)42)
#define SD_CMD_SD_APP_SEND_SCR                     ((uint8_t)51)
#define SD_CMD_SDIO_RW_DIRECT                      ((uint8_t)52)
#define SD_CMD_SDIO_RW_EXTENDED                    ((uint8_t)53)

/* following commands are sd card specific security commands. */
/* sdio_app_cmd should be sent before sending these commands. */
#define SD_CMD_SD_APP_GET_MKB                      ((uint8_t)43)
#define SD_CMD_SD_APP_GET_MID                      ((uint8_t)44)
#define SD_CMD_SD_APP_SET_CER_RN1                  ((uint8_t)45)
#define SD_CMD_SD_APP_GET_CER_RN2                  ((uint8_t)46)
#define SD_CMD_SD_APP_SET_CER_RES2                 ((uint8_t)47)
#define SD_CMD_SD_APP_GET_CER_RES1                 ((uint8_t)48)
#define SD_CMD_SD_APP_SECURE_READ_MULT_BLOCK       ((uint8_t)18)
#define SD_CMD_SD_APP_SECURE_WRITE_MULT_BLOCK      ((uint8_t)25)
#define SD_CMD_SD_APP_SECURE_ERASE                 ((uint8_t)38)
#define SD_CMD_SD_APP_CHANGE_SECURE_AREA           ((uint8_t)49)
#define SD_CMD_SD_APP_SECURE_WRITE_MKB             ((uint8_t)48)

/* ext_csd fields */
#define EXT_CSD_BUS_WIDTH                          183
#define EXT_CSD_HS_TIMING                          185
#define EXT_CSD_CARD_TYPE                          196

/* ext_csd field definitions */
#define EXT_CSD_CMD_SET_NORMAL                     (1 << 0)
#define EXT_CSD_CMD_SET_SECURE                     (1 << 1)
#define EXT_CSD_CMD_SET_CPSECURE                   (1 << 2)

#define EXT_CSD_Write_byte                         0x03

/* supported commands */
#define SDIO_SEND_IF_COND                          ((uint32_t)SD_CMD_HS_SEND_EXT_CSD)

extern sd_card_info_struct_type sd_card_info;
extern volatile sd_error_status_type transfer_error;
extern volatile uint8_t transfer_end;

/* functions declaration */
sd_error_status_type sd_init(void);
sd_error_status_type sd_power_on(void);
sd_error_status_type sd_power_off(void);
sd_error_status_type sd_card_init(void);
sd_error_status_type sd_card_info_get(sd_card_info_struct_type *card_info);
sd_error_status_type sd_last_error_get(void);
uint8_t sd_last_cmd_get(void);
uint32_t sd_last_response_get(void);
uint8_t sd_scr_bus_width_get(void);
uint8_t sd_scr_spec_get(void);
uint32_t sd_scr_raw_get(uint8_t index);
sd_error_status_type sd_wide_bus_operation_config(sdio_bus_width_type mode);
sd_error_status_type sd_device_mode_set(uint32_t mode);
sd_error_status_type sd_deselect_select(uint32_t addr);
sd_error_status_type sd_blocks_erase(long long addr, uint32_t nblks);
sd_error_status_type sd_block_read(uint8_t *buf, long long addr, uint16_t blk_size);
sd_error_status_type sd_mult_blocks_read(uint8_t *buf, long long addr, uint16_t blk_size, uint32_t nblks);
sd_error_status_type sd_block_write(const uint8_t *buf, long long addr, uint16_t blk_size);
sd_error_status_type sd_mult_blocks_write(const uint8_t *buf, long long addr, uint16_t blk_size, uint32_t nblks);
sd_error_status_type mmc_stream_read(uint8_t *buf, long long addr, uint32_t len);
sd_error_status_type mmc_stream_write(uint8_t *buf, long long addr, uint32_t len);
sd_error_status_type sd_irq_service(void);
sd_error_status_type sd_status_send(uint32_t *p_card_status);
sd_card_state_type sd_state_get(void);
sd_error_status_type sdio_command_data_send(sdio_command_struct_type *sdio_cmd_init_t, sdio_data_struct_type* sdio_data_init_t, uint32_t *buf);
void sdio_clock_set(uint32_t clk_div);
void sd_dma_config(uint32_t *mbuf, uint32_t buf_size, dma_dir_type dir);

/**
  * @}
  */

/**
  * @}
  */

#ifdef __cplusplus
}
#endif

#endif /* __AT32_SDIO_H */



