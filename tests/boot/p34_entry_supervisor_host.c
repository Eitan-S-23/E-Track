#include "supervisor.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static re_hw_snapshot hw;
static unsigned snapshots, writes, fail_snapshot, fail_write, change_after;
static int finish;
static uint8_t status_byte;
static uint32_t trace[4][2];
int re_platform_snapshot(re_hw_snapshot *h)
{
    ++snapshots;
    if (snapshots==fail_snapshot) return -1;
    hw.ticks+=10;
    *h=hw;
    if (change_after && snapshots>=change_after) h->clock[2]^=1u;
    return 0;
}
int re_platform_read32(uint32_t off, uint32_t *v)
{
    switch (off) {
    case 0x10: *v=3; return 0;
    case 0x18: *v=4u|((writes==4 && finish)?2u:0u); return 0;
    case 0x24: *v=(writes==4 && finish)?1u:0u; return 0;
    default: assert(0); return -1;
    }
}
int re_platform_write32(uint32_t off, uint32_t v)
{
    static const uint32_t expected[4]={0,0x01000000,1,0x05000000};
    assert(writes<4 && off==writes*4 && v==expected[writes]);
    trace[writes][0]=off; trace[writes][1]=v; ++writes;
    return writes==fail_write ? -1 : 0;
}
int re_platform_read8(uint32_t off, uint8_t *v)
{ assert(off==0x100); *v=status_byte; return 0; }
static re_profile reset(void)
{
    re_profile p;
    memset(&p,0,sizeof(p)); memset(&hw,0,sizeof(hw)); memset(trace,0,sizeof(trace));
    snapshots=writes=fail_snapshot=fail_write=change_after=0; finish=1; status_byte=0;
    hw.primask=1; hw.msp=0x20065e00; hw.vtor=0x20060000;
    hw.trace_enabled=hw.counter_enabled=1;
    p.epoch=3; p.hz=288000000; p.budget=100000;
    p.entry_qualified=p.media_qualified=p.clock_qualified=p.ownership_qualified=1;
    memset(p.operation,0x27,32);
    return p;
}
static unsigned cases;
static void expect(re_profile *p, re_observation desired, int zero_writes)
{
    re_session session={0}; uint8_t raw=0xa5;
    re_observation result=re_supervise_once(&session,p,p->operation,&raw);
    assert(result==desired && session.consumed==1);
    assert(result==RE_OBS_UNKNOWN ? raw==0xa5 : raw==status_byte);
    if (zero_writes) assert(writes==0);
    {
        unsigned before=writes, reads=snapshots;
        assert(re_supervise_once(&session,p,p->operation,&raw)==RE_OBS_UNKNOWN);
        assert(writes==before && snapshots==reads);
    }
    ++cases;
}
int main(void)
{
    re_profile p=reset(); unsigned i, reachable_snapshots;
    expect(&p,RE_OBS_IDLE_STATUS_ONLY,0);
    reachable_snapshots=snapshots;
    p=reset(); status_byte=1; expect(&p,RE_OBS_BUSY,0);
    for (i=0;i<5;++i) { p=reset(); hw.clock[i]=1; expect(&p,RE_OBS_UNKNOWN,1); }
    p=reset(); hw.ipsr=3; expect(&p,RE_OBS_UNKNOWN,1);
    p=reset(); hw.control=2; expect(&p,RE_OBS_UNKNOWN,1);
    p=reset(); hw.primask=0; expect(&p,RE_OBS_UNKNOWN,1);
    p=reset(); hw.msp=0x20064000; expect(&p,RE_OBS_UNKNOWN,1);
    p=reset(); hw.vtor=0x08010000; expect(&p,RE_OBS_UNKNOWN,1);
    p=reset(); hw.fpccr=1; expect(&p,RE_OBS_UNKNOWN,1);
    p=reset(); hw.dma_active=1; expect(&p,RE_OBS_UNKNOWN,1);
    p=reset(); hw.qspi_dma=1; expect(&p,RE_OBS_UNKNOWN,1);
    p=reset(); hw.trace_enabled=0; expect(&p,RE_OBS_UNKNOWN,1);
    p=reset(); hw.counter_enabled=0; expect(&p,RE_OBS_UNKNOWN,1);
    p=reset(); p.entry_qualified=0; expect(&p,RE_OBS_UNKNOWN,1);
    p=reset(); p.media_qualified=0; expect(&p,RE_OBS_UNKNOWN,1);
    p=reset(); p.clock_qualified=0; expect(&p,RE_OBS_UNKNOWN,1);
    p=reset(); p.ownership_qualified=0; expect(&p,RE_OBS_UNKNOWN,1);
    p=reset(); p.hz=1; expect(&p,RE_OBS_UNKNOWN,1);
    p=reset(); p.epoch=0; expect(&p,RE_OBS_UNKNOWN,1);
    p=reset(); memset(p.operation,0,32); expect(&p,RE_OBS_UNKNOWN,1);
    p=reset(); finish=0; expect(&p,RE_OBS_UNKNOWN,0);
    for (i=1;i<=4;++i) { p=reset(); fail_write=i; expect(&p,RE_OBS_UNKNOWN,0); assert(writes==i); }
    for (i=1;i<=reachable_snapshots;++i) { p=reset(); fail_snapshot=i; expect(&p,RE_OBS_UNKNOWN,0); }
    p=reset(); change_after=20; expect(&p,RE_OBS_UNKNOWN,0);
    p=reset(); {
        uint8_t wrong[32]={0}, raw=0xa5; re_session s={0};
        assert(re_supervise_once(&s,&p,wrong,&raw)==RE_OBS_UNKNOWN && writes==0);
        ++cases;
    }
    printf("ENTRY_SUPERVISOR_HOST_PASS scenarios=%u\n",cases);
    return 0;
}
