#define main original_main
#include "p34_confirm_supervisor_host.c"
#undef main

int main(int argc,char **argv)
{
    bcb_t b;
    unsigned checks=0;
    if(original_main(argc,argv)!=0) return 2;
    setup(0,7); prefix=17; write_error=0;
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_NOT_CONFIRMED && writes==1);
    assert(result.transaction_status!=0); ++checks;
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_REJECTED && writes==1); ++checks;
    setup(0,7); prefix=64; write_error=1;
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_CONFIRMED && writes==1);
    assert(result.transaction_status!=0); ++checks;
    setup(0,7); persistent_after_write=1;
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_UNKNOWN && writes==1);
    persistent_after_write=0;
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_ALREADY && writes==1); ++checks;
    setup(0,7); fail_read=12;
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_UNKNOWN && writes==1);
    fail_read=0;
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_ALREADY && writes==1); ++checks;
    setup(0,7); --request.boot_length;
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_REJECTED && writes==0); ++checks;
    setup(0,7); --request.image_length;
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_REJECTED && writes==0); ++checks;
    setup(0,7); bcb_deserialize(ee,&b); b.reserved=1;
    bcb_serialize(&b,ee); memcpy(plan.before,ee,128);
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_REJECTED && writes==0); ++checks;
    setup(0,7); bcb_deserialize(ee,&b); b.boot_try=99;
    bcb_serialize(&b,ee); memcpy(plan.before,ee,128);
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_REJECTED && writes==0); ++checks;
    printf("CONFIRM_FOLLOWUP_HOST_PASS additional_checks=%u\n",checks);
    return 0;
}
