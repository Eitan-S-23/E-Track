#define main original_main
#include "p34_confirm_supervisor_host.c"
#undef main
#include "observe.h"

int main(int argc,char **argv)
{
    bcb_hal_t readonly_hal={0,er};
    rc_observation observation;
    uint8_t expected[128];
    if(original_main(argc,argv)!=0) return 2;
    setup(0,7); persistent_read=1;
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_UNKNOWN && writes==0);
    assert(rc_readback(&readonly_hal,&observation)==-1 && !observation.stable && writes==0);
    persistent_read=0;
    assert(rc_readback(&readonly_hal,&observation)==0 && observation.value.cur_vcode==30275 && writes==0);
    setup(0,7); target(0,expected); persistent_after_write=1;
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_UNKNOWN && writes==1);
    persistent_after_write=0;
    assert(rc_readback(&readonly_hal,&observation)==0 && !memcmp(observation.pair,expected,128));
    assert(writes==1);
    setup(0,7); prefix=17; write_error=1;
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_NOT_CONFIRMED && writes==1);
    assert(rc_readback(&readonly_hal,&observation)==0 && observation.value.cur_vcode==30275 && writes==1);
    setup(0,7); change_pre(BCB_STATE_STAGED,0,0,30275);
    assert(rc_readback(&readonly_hal,&observation)==0 && observation.value.state==BCB_STATE_STAGED && writes==0);
    setup(0,7); drift_read=3;
    assert(rc_readback(&readonly_hal,&observation)==-1 && !observation.stable && writes==0);
    puts("CONFIRM_READONLY_OBSERVER_PASS scenarios=6");
    return 0;
}
