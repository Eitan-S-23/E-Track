#include "at32_qspi_port.c"
#include <assert.h>
#include <stdio.h>

fake_dwt fake_clock;
fake_scb fake_core;
fake_qspi fake_controller;
static uint8_t nor[0x100000];
static qspi_cmd_type current;
static uint32_t index_, commands, wren, writes;
static int mode, wel;

int qspi_flag_get(fake_qspi *q, uint32_t flag)
{
    (void)q;
    if (mode != 4) fake_clock.CYCCNT += 144000u;
    if (mode == 1 || mode == 4) return RESET;
    if (mode == 2 && flag == QSPI_TXFIFORDY_FLAG) return RESET;
    return 1;
}
void qspi_flag_clear(fake_qspi *q, uint32_t flag) { (void)q; (void)flag; }
void qspi_clk_division_set(fake_qspi *q, int n) { (void)q; assert(n == 8); }
void qspi_sck_mode_set(fake_qspi *q, int n) { (void)q; assert(n == 0); }
void qspi_busy_config(fake_qspi *q, int n) { (void)q; assert(n == 0); }
void qspi_auto_ispc_enable(fake_qspi *q) { (void)q; }

void qspi_cmd_operation_kick(fake_qspi *q, qspi_cmd_type *c)
{
    (void)q;
    current = *c; index_ = 0; ++commands;
    switch (c->instruction_code) {
    case 0x06: ++wren; wel = mode != 3; break;
    case 0x05: case 0x9f: break;
    case 0x03: case 0x02: case 0x20:
        assert(c->address_code >= 0x200000u && c->address_code < 0x300000u);
        assert(c->data_counter <= 0x300000u-c->address_code);
        if (c->instruction_code == 0x20) {
            assert(wel && !(c->address_code & 4095u));
            memset(nor+c->address_code-0x200000u,0xff,4096u);
            ++writes; wel = 0;
        }
        break;
    default: assert(0);
    }
}

uint8_t qspi_byte_read(fake_qspi *q)
{
    static const uint8_t id[3] = {0xef,0x40,0x18};
    (void)q;
    if (current.instruction_code == 0x05) return (uint8_t)(wel ? 2 : 0);
    if (current.instruction_code == 0x9f) { assert(index_ < 3u); return id[index_++]; }
    assert(current.instruction_code == 0x03 && index_ < current.data_counter);
    return nor[current.address_code-0x200000u+index_++];
}

void qspi_byte_write(fake_qspi *q, uint8_t value)
{
    (void)q;
    assert(current.instruction_code == 0x02 && wel && index_ < current.data_counter);
    nor[current.address_code-0x200000u+index_++] &= value;
    ++writes;
    if (index_ == current.data_counter) wel = 0;
}

static void reset(rr_qspi_state *state)
{
    mode = wel = 0; commands = wren = writes = 0;
    memset(&fake_controller,0,sizeof(fake_controller));
    memset(nor,0xa5,sizeof(nor));
    fake_core.VTOR = 0x20058000u;
    fake_clock.CTRL = 1; fake_clock.CYCCNT = 0;
    assert(rr_qspi_prepare(state) == 0);
    assert(state->initialized && !state->failed && state->jedec == 0xef4018u);
}

int main(void)
{
    rr_qspi_state state;
    uint8_t data[256], result[256];
    unsigned i, cases = 0;
    const uint32_t bad[][2] = {{0x1fffffu,1},{0x300000u,1},{0x2fffffu,2},
                               {0x2000ffu,2},{0x200000u,257},{0x200000u,0},
                               {0x200000u,UINT32_MAX}};
    reset(&state);
    memset(data,0x3c,sizeof(data));
    assert(rr_qspi_erase(&state,0x200000u) == 0);
    assert(rr_qspi_program(&state,0x200000u,data,sizeof(data)) == 0);
    assert(rr_qspi_read(&state,0x200000u,result,sizeof(result)) == 0);
    assert(memcmp(result,data,sizeof(data)) == 0); ++cases;
    for (i = 0; i < sizeof(bad)/sizeof(bad[0]); ++i) {
        uint32_t before;
        reset(&state); before = commands;
        assert(rr_qspi_program(&state,bad[i][0],data,bad[i][1]) == -1);
        assert(commands == before && wren == 0 && writes == 0 && state.failed);
        assert(rr_qspi_erase(&state,0x200000u) == -1 && commands == before); ++cases;
    }
    for (i = 1; i <= 4u; ++i) {
        uint32_t before;
        reset(&state); mode = (int)i;
        assert(rr_qspi_program(&state,0x200000u,data,256) == -1 && state.failed);
        before = commands;
        assert(rr_qspi_read(&state,0x200000u,result,32) == -1 && commands == before);
        assert(writes == 0); ++cases;
    }
    reset(&state);
    assert(rr_qspi_erase(&state,0x200001u) == -1 && wren == 0); ++cases;
    reset(&state);
    assert(rr_qspi_erase(&state,0x300000u) == -1 && wren == 0); ++cases;
    printf("QSPI_PORT_HOST_PASS cases=%u\n",cases);
    return 0;
}
