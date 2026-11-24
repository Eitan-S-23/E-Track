/* Behavioral SDK mock only; does not model the real register bit layout. */
#ifndef RR_QSPI_MOCK_H
#define RR_QSPI_MOCK_H
#include <stdint.h>
#define TRUE 1
#define FALSE 0
#define RESET 0
#define QSPI_CMDSTS_FLAG 1u
#define QSPI_TXFIFORDY_FLAG 2u
#define QSPI_CMD_INSLEN_1_BYTE 1
#define QSPI_CMD_ADRLEN_3_BYTE 3
#define QSPI_CMD_ADRLEN_0_BYTE 0
#define QSPI_OPERATE_MODE_111 0
#define QSPI_RSTSC_HW_AUTO 0
#define QSPI_CLK_DIV_8 8
#define QSPI_SCK_MODE_0 0
#define QSPI_BUSY_OFFSET_0 0
#define DWT_CTRL_CYCCNTENA_Msk 1u
typedef struct { uint32_t CYCCNT, CTRL; } fake_dwt;
typedef struct { uint32_t VTOR; } fake_scb;
typedef struct { uint32_t ctrl; struct { int xipsel, xiprcmdf, abort; } ctrl_bit; } fake_qspi;
extern fake_dwt fake_clock;
extern fake_scb fake_core;
extern fake_qspi fake_controller;
#define DWT (&fake_clock)
#define SCB (&fake_core)
#define QSPI1 (&fake_controller)
#define __NOP() ((void)0)
static inline unsigned __get_IPSR(void) { return 0; }
static inline unsigned __get_PRIMASK(void) { return 1; }
typedef struct {
    uint32_t instruction_code, instruction_length, address_code, address_length;
    uint32_t data_counter, operation_mode, read_status_config, write_data_enable;
} qspi_cmd_type;
int qspi_flag_get(fake_qspi *, uint32_t);
void qspi_flag_clear(fake_qspi *, uint32_t);
void qspi_cmd_operation_kick(fake_qspi *, qspi_cmd_type *);
uint8_t qspi_byte_read(fake_qspi *);
void qspi_byte_write(fake_qspi *, uint8_t);
void qspi_clk_division_set(fake_qspi *, int);
void qspi_sck_mode_set(fake_qspi *, int);
void qspi_busy_config(fake_qspi *, int);
void qspi_auto_ispc_enable(fake_qspi *);
#endif
