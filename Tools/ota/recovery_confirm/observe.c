#include "observe.h"
#include <string.h>

/* Original HAL lacks context; this observer is intentionally non-reentrant. */
static const rc_observation *observed;
static int read_saved(uint8_t address,uint8_t *data,uint16_t length)
{
    if(length!=BCB_SIZE || (address!=0 && address!=64)) return -1;
    memcpy(data,observed->pair[address==64],length); return 0;
}

int rc_readback(const bcb_hal_t *hal,rc_observation *out)
{
    uint8_t second[2][BCB_SIZE];
    bcb_hal_t memory_hal={0,read_saved};
    unsigned i;
    if(!hal || !hal->read_buffer || !out) return -1;
    memset(out,0,sizeof(*out)); out->active=BCB_ARBITER_ERROR;
    for(i=0;i<2;++i) {
        if(hal->read_buffer((uint8_t)(i*64u),out->pair[i],BCB_SIZE)!=0) return -1;
        ++out->completed;
    }
    for(i=0;i<2;++i) {
        if(hal->read_buffer((uint8_t)(i*64u),second[i],BCB_SIZE)!=0) return -1;
        ++out->completed;
    }
    if(memcmp(out->pair,second,sizeof(second))!=0) return -1;
    observed=out;
    out->active=bcb_arbiter(&memory_hal,&out->value);
    observed=0;
    out->stable=1;
    return 0;
}
