#include "at32_qspi_port.h"
#include "at32f435_437.h"
#include <string.h>

typedef struct { uint32_t start, cycles, polls; } deadline;

static void begin(deadline *d, uint32_t milliseconds)
{
    d->start = DWT->CYCCNT;
    d->cycles = milliseconds*288000u;
    d->polls = 0;
}

static int alive(deadline *d)
{
    return ++d->polls < 2000000u && (uint32_t)(DWT->CYCCNT-d->start) < d->cycles;
}

static int wait_flag(deadline *d, uint32_t flag)
{
    while (alive(d))
        if (qspi_flag_get(QSPI1, flag) != RESET) return 0;
    return -1;
}

static int command(deadline *d, uint8_t opcode, uint32_t address, uint32_t count, int write)
{
    qspi_cmd_type cmd;
    int addressed = opcode == 0x03u || opcode == 0x20u || opcode == 0x02u;
    if (!alive(d)) return -1;
    if (opcode != 0x03u && opcode != 0x20u && opcode != 0x02u &&
        opcode != 0x05u && opcode != 0x06u && opcode != 0x9fu) return -1;
    /* Guard command emission as well as public wrappers, before any WREN. */
    if (addressed && (address < 0x200000u || address >= 0x300000u ||
        count > 0x300000u-address)) return -1;
    memset(&cmd, 0, sizeof(cmd));
    cmd.instruction_code = opcode;
    cmd.instruction_length = QSPI_CMD_INSLEN_1_BYTE;
    cmd.address_code = address;
    cmd.address_length = addressed ? QSPI_CMD_ADRLEN_3_BYTE : QSPI_CMD_ADRLEN_0_BYTE;
    cmd.data_counter = count;
    cmd.operation_mode = QSPI_OPERATE_MODE_111;
    cmd.read_status_config = QSPI_RSTSC_HW_AUTO;
    cmd.write_data_enable = write ? TRUE : FALSE;
    qspi_flag_clear(QSPI1, QSPI_CMDSTS_FLAG);
    qspi_cmd_operation_kick(QSPI1, &cmd);
    return 0;
}

static int read_command(deadline *d, uint8_t opcode, uint32_t address, uint8_t *dst, uint32_t length)
{
    uint32_t i;
    if (length == 0u || length > 32u || command(d,opcode,address,length,0) != 0 ||
        wait_flag(d,QSPI_CMDSTS_FLAG) != 0) return -1;
    for (i = 0; i < length; ++i) {
        if (!alive(d)) return -1;
        dst[i] = qspi_byte_read(QSPI1);
    }
    qspi_flag_clear(QSPI1, QSPI_CMDSTS_FLAG);
    return 0;
}

static int ready(deadline *d)
{
    uint8_t status;
    while (alive(d)) {
        if (read_command(d,0x05u,0,&status,1u) != 0) return -1;
        if (!(status & 1u)) return 0;
    }
    return -1;
}

static int enable_write(deadline *d)
{
    uint8_t status;
    if (ready(d) != 0 || command(d,0x06u,0,0,1) != 0 ||
        wait_flag(d,QSPI_CMDSTS_FLAG) != 0) return -1;
    qspi_flag_clear(QSPI1,QSPI_CMDSTS_FLAG);
    if (read_command(d,0x05u,0,&status,1u) != 0) return -1;
    return (status & 3u) == 2u ? 0 : -1;
}

static int fail(rr_qspi_state *s)
{
    if (s) s->failed = 1;
    return -1;
}

static int usable(rr_qspi_state *s)
{
    return s && s->initialized && !s->failed;
}

int rr_qspi_prepare(rr_qspi_state *s)
{
    deadline d;
    uint8_t id[3];
    unsigned delay;
    if (!s) return -1;
    memset(s,0,sizeof(*s));
    if (__get_IPSR() || __get_PRIMASK() != 1u || SCB->VTOR < 0x20058000u ||
        SCB->VTOR >= 0x20080000u || !(DWT->CTRL & DWT_CTRL_CYCCNTENA_Msk)) return fail(s);
    begin(&d,100u);
    if (QSPI1->ctrl & (7u << 16)) return fail(s);
    if (QSPI1->ctrl_bit.xipsel) {
        if (wait_flag(&d,QSPI_TXFIFORDY_FLAG) != 0) return fail(s);
        for (delay = 0; delay < 64u; ++delay) __NOP();
        QSPI1->ctrl_bit.xiprcmdf = 1;
        while (QSPI1->ctrl_bit.abort) if (!alive(&d)) return fail(s);
        for (delay = 0; delay < 64u; ++delay) __NOP();
        QSPI1->ctrl_bit.xipsel = 0;
        while (QSPI1->ctrl_bit.abort) if (!alive(&d)) return fail(s);
    }
    qspi_clk_division_set(QSPI1,QSPI_CLK_DIV_8);
    qspi_sck_mode_set(QSPI1,QSPI_SCK_MODE_0);
    qspi_busy_config(QSPI1,QSPI_BUSY_OFFSET_0);
    qspi_auto_ispc_enable(QSPI1);
    if (ready(&d) != 0 || read_command(&d,0x9fu,0,id,3u) != 0) return fail(s);
    s->jedec = ((uint32_t)id[0] << 16) | ((uint32_t)id[1] << 8) | id[2];
    if (s->jedec != 0xef4018u && s->jedec != 0x1c4018u &&
        s->jedec != 0x1c4017u && s->jedec != 0xef4017u) return fail(s);
    s->initialized = 1;
    return 0;
}

int rr_qspi_read(void *ctx, uint32_t address, uint8_t *dst, uint32_t length)
{
    rr_qspi_state *s = ctx;
    deadline d;
    uint32_t offset, take;
    if (!usable(s) || !dst || !length || length > 4096u || address < 0x200000u ||
        address >= 0x300000u || length > 0x300000u-address) return fail(s);
    begin(&d,100u);
    if (ready(&d) != 0) return fail(s);
    for (offset = 0; offset < length; offset += take) {
        take = length-offset;
        if (take > 32u) take = 32u;
        if (read_command(&d,0x03u,address+offset,dst+offset,take) != 0) return fail(s);
    }
    return 0;
}

int rr_qspi_erase(void *ctx, uint32_t address)
{
    rr_qspi_state *s = ctx;
    deadline d;
    if (!usable(s) || address < 0x200000u || address > 0x2ff000u ||
        (address & 4095u)) return fail(s);
    begin(&d,2000u);
    if (enable_write(&d) != 0 || command(&d,0x20u,address,0,1) != 0 ||
        wait_flag(&d,QSPI_CMDSTS_FLAG) != 0) return fail(s);
    qspi_flag_clear(QSPI1,QSPI_CMDSTS_FLAG);
    return ready(&d) == 0 ? 0 : fail(s);
}

int rr_qspi_program(void *ctx, uint32_t address, const uint8_t *src, uint32_t length)
{
    rr_qspi_state *s = ctx;
    deadline d;
    uint32_t i;
    if (!usable(s) || !src || !length || length > 256u || address < 0x200000u ||
        address >= 0x300000u || length > 0x300000u-address ||
        length > 256u-(address & 255u)) return fail(s);
    begin(&d,2000u);
    if (enable_write(&d) != 0 || command(&d,0x02u,address,length,1) != 0) return fail(s);
    for (i = 0; i < length; ++i) {
        if (wait_flag(&d,QSPI_TXFIFORDY_FLAG) != 0) return fail(s);
        qspi_byte_write(QSPI1,src[i]);
    }
    if (wait_flag(&d,QSPI_CMDSTS_FLAG) != 0) return fail(s);
    qspi_flag_clear(QSPI1,QSPI_CMDSTS_FLAG);
    return ready(&d) == 0 ? 0 : fail(s);
}
