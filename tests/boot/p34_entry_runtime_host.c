#include "runtime.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

typedef struct {
    uint32_t ticks, step, epoch, hz, ctrl, fifo, done;
    unsigned writes, reads, samples, lose_epoch, fail_write;
    int owned, finish;
    uint8_t status;
    uint32_t offsets[4], values[4];
} mock;
static int sample(void *p, re_sample *s)
{
    mock *m=p;
    ++m->samples;
    s->epoch=m->epoch + (m->lose_epoch && m->samples >= m->lose_epoch);
    s->hz=m->hz; s->ticks=m->ticks; m->ticks+=m->step;
    return 0;
}
static int owned(void *p) { return ((mock *)p)->owned; }
static int read32(void *p, uint32_t off, uint32_t *v)
{
    mock *m=p; ++m->reads;
    if (off==0x10) *v=m->ctrl;
    else if (off==0x18) *v=m->fifo | ((m->writes==4 && m->finish) ? 2u : 0u);
    else if (off==0x24) *v=m->done | ((m->writes==4 && m->finish) ? 1u : 0u);
    else { assert(0); return -1; }
    return 0;
}
static int write32(void *p, uint32_t off, uint32_t v)
{
    mock *m=p;
    assert(m->writes<4 && off==m->writes*4);
    m->offsets[m->writes]=off; m->values[m->writes++]=v;
    return m->fail_write==m->writes ? -1 : 0;
}
static int read8(void *p, uint32_t off, uint8_t *v)
{ assert(off==0x100); *v=((mock *)p)->status; return 0; }
static mock initial(void)
{
    mock m; memset(&m,0,sizeof(m));
    m.step=1; m.epoch=7; m.hz=288000000; m.ctrl=3; m.fifo=4;
    m.owned=1; m.finish=1; return m;
}
static re_observation run(mock *m)
{
    re_clock c={m,sample}; re_status_io io={m,owned,read32,write32,read8};
    /* Writer state is deliberately not passed into either interface. */
    struct { int initialized, failed; uint32_t jedec; } writer={1,1,0xef4018}, before=writer;
    uint8_t raw=0xa5;
    re_observation r=re_observe(&io,&c,7,288000000,100,&raw);
    assert(memcmp(&writer,&before,sizeof(writer))==0);
    assert(r==RE_OBS_UNKNOWN ? raw==0xa5 : raw==m->status);
    if (m->writes==4) {
        assert(m->values[0]==0 && m->values[1]==0x01000000 && m->values[2]==1);
        assert(m->values[3]==0x05000000);
    }
    return r;
}
int main(void)
{
    mock m=initial(); re_clock c={&m,sample}; re_deadline d;
    assert(run(&m)==RE_OBS_IDLE_STATUS_ONLY && m.writes==4);
    m=initial(); m.status=1; assert(run(&m)==RE_OBS_BUSY);
    m=initial(); m.owned=0; assert(run(&m)==RE_OBS_UNKNOWN && !m.writes);
    m=initial(); m.ctrl|=1u<<20; assert(run(&m)==RE_OBS_UNKNOWN && !m.writes);
    m=initial(); m.fifo|=2; assert(run(&m)==RE_OBS_UNKNOWN && !m.writes);
    m=initial(); m.done=1; assert(run(&m)==RE_OBS_UNKNOWN && !m.writes);
    m=initial(); m.finish=0; assert(run(&m)==RE_OBS_UNKNOWN && m.writes==4);
    m=initial(); m.step=0; m.finish=0; assert(run(&m)==RE_OBS_UNKNOWN && m.samples<4100);
    m=initial(); m.lose_epoch=4; assert(run(&m)==RE_OBS_UNKNOWN && m.writes<4);
    m=initial(); m.hz=1; assert(run(&m)==RE_OBS_UNKNOWN && !m.writes);
    m=initial(); m.fail_write=4; assert(run(&m)==RE_OBS_UNKNOWN && m.writes==4);
    m=initial(); m.ticks=0xfffffffdu; assert(run(&m)==RE_OBS_IDLE_STATUS_ONLY);
    m=initial(); assert(re_begin(&c,7,m.hz,100,&d)==0); m.hz=1; assert(!re_alive(&c,&d));
    m=initial(); assert(re_begin(&c,7,m.hz,100,&d)==0); m.ticks=0xffffffffu; assert(!re_alive(&c,&d));
    m=initial(); assert(re_begin(&c,7,m.hz,0x80000000u,&d)!=0);
    puts("ENTRY_RUNTIME_HOST_PASS scenarios=15"); return 0;
}
