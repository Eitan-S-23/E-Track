#include "confirm.h"
#include "boot_crypto.h"
#include "OTA/ota_backup.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static uint8_t boot_bytes[65536], app[619580], candidate[619580];
static uint8_t ee[128], nor[0x300000];
static unsigned reads, writes, nor_writes, fail_read, drift_read;
static int prefix, write_error, persistent_after_write, persistent_read;
static rc_plan plan;
static rc_request request;
static rc_result result;

static int er(uint8_t address, uint8_t *data, uint16_t length)
{
    ++reads;
    assert(address <= sizeof(ee) && length <= sizeof(ee)-address);
    if (reads == drift_read) {
        bcb_t changed;
        bcb_deserialize(ee,&changed); changed.state = BCB_STATE_STAGED;
        bcb_serialize(&changed,ee);
    }
    if (reads == fail_read || persistent_read || (persistent_after_write && writes)) return -1;
    memcpy(data,ee+address,length); return 0;
}
static int ew(uint8_t address, const uint8_t *data, uint16_t length)
{
    unsigned take = prefix < 0 ? length : (unsigned)prefix;
    assert((address == 0 || address == 64) && length == 64 && take <= length);
    ++writes; memcpy(ee+address,data,take);
    return write_error ? -1 : 0;
}
static const bcb_hal_t hal = {ew,er};

static void setup(unsigned active, uint16_t seq)
{
    bcb_t b;
    unsigned i;
    reads=writes=nor_writes=fail_read=drift_read=0;
    prefix=-1; write_error=persistent_after_write=persistent_read=0;
    bcb_make_idle(&b,30275u); b.state=BCB_STATE_CONFIRMED; b.boot_try=2;
    b.seq=seq; b.cand_addr=0x1000; b.cand_len=0x50000;
    b.cand_crc32=0x11223344; b.cand_vcode=30274;
    b.backup_len=0x50000; b.backup_crc32=0x55667788; b.backup_vcode=30273;
    bcb_serialize(&b,ee+active*64u);
    b.seq=(uint16_t)(seq-1u); b.cur_vcode=30274;
    bcb_serialize(&b,ee+(1u-active)*64u);
    memcpy(plan.before,ee,sizeof(ee));
    for(i=0;i<16;++i) plan.operation[i]=(uint8_t)(i+1u);
    memset(&request,0,sizeof(request)); memcpy(request.operation,plan.operation,16);
    request.boot=boot_bytes; request.boot_length=sizeof(boot_bytes);
    request.image=app; request.image_length=sizeof(app);
}

static void target(unsigned active, uint8_t expected[128])
{
    bcb_t b;
    memcpy(expected,plan.before,128);
    bcb_deserialize(plan.before[active],&b);
    b.seq=(uint16_t)(b.seq+1u); b.boot_try=0; b.cur_vcode=30276;
    b.copy_phase=0; b.resume_block=0; b.state=BCB_STATE_CONFIRMED;
    bcb_serialize(&b,expected+(1u-active)*64u);
}

static void change_pre(unsigned state, unsigned phase, unsigned resume, unsigned version)
{
    bcb_t b;
    bcb_deserialize(ee,&b); b.state=(uint8_t)state; b.copy_phase=(uint8_t)phase;
    b.resume_block=(uint16_t)resume; b.cur_vcode=version;
    bcb_serialize(&b,ee); memcpy(plan.before,ee,128);
}

static int ar(void *ctx,uint32_t offset,uint8_t *data,uint32_t length)
{
    (void)ctx;
    assert(offset <= sizeof(app) && length <= sizeof(app)-offset);
    memcpy(data,app+offset,length); return 0;
}
static int nr(void *ctx,uint32_t offset,uint8_t *data,uint32_t length)
{
    (void)ctx;
    assert(offset <= sizeof(nor) && length <= sizeof(nor)-offset);
    memcpy(data,nor+offset,length); return 0;
}
static int ne(void *ctx,uint32_t offset)
{
    (void)ctx;
    assert(offset < 0x200000u && !(offset & 4095u));
    memset(nor+offset,0xff,4096); ++nor_writes; return 0;
}
static int np(void *ctx,uint32_t offset,const uint8_t *data,uint32_t length)
{
    uint32_t i;
    (void)ctx;
    assert(offset < 0x200000u && length <= 0x200000u-offset);
    for(i=0;i<length;++i) nor[offset+i] &= data[i];
    ++nor_writes; return 0;
}

static void load(const char *name,uint8_t *dst,size_t length)
{
    FILE *f=fopen(name,"rb"); assert(f);
    assert(fread(dst,1,length,f)==length && fgetc(f)==EOF); fclose(f);
}

int main(int argc,char **argv)
{
    unsigned active,i,j,checks=0,normal_reads;
    const uint16_t sequences[]={7,65535};
    const unsigned invalid[]={BCB_STATE_IDLE,BCB_STATE_STAGED,BCB_STATE_APPLYING,
                              BCB_STATE_TEST_BOOT,BCB_STATE_ROLLBACK,255};
    uint8_t expected[128];
    rc_status rc;
    bcb_t observed;
    if(argc!=4) return 2;
    load(argv[1],boot_bytes,sizeof(boot_bytes)); load(argv[2],app,sizeof(app));
    load(argv[3],candidate,sizeof(candidate));
    for(active=0;active<2;++active) for(j=0;j<2;++j) {
        setup(active,sequences[j]); target(active,expected);
        assert(rc_confirm(&plan,&request,&hal,&result)==RC_CONFIRMED);
        assert(writes==1 && !memcmp(ee,expected,128));
        normal_reads=reads;
        assert(rc_confirm(&plan,&request,&hal,&result)==RC_ALREADY && writes==1);
        assert(!memcmp(ee,expected,128)); checks+=2;
    }
    for(i=0;i<sizeof(invalid)/sizeof(invalid[0]);++i) {
        setup(0,7); change_pre(invalid[i],0,0,30275);
        assert(rc_confirm(&plan,&request,&hal,&result)==RC_REJECTED && writes==0); ++checks;
    }
    for(i=0;i<3;++i) {
        setup(0,7); change_pre(BCB_STATE_CONFIRMED,i==0, i==1, i==2 ? 40000 : 30275);
        assert(rc_confirm(&plan,&request,&hal,&result)==RC_REJECTED && writes==0); ++checks;
    }
    setup(0,7); memset(ee,0xff,128); memcpy(plan.before,ee,128);
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_REJECTED && writes==0); ++checks;
    setup(0,7); ee[100]^=1;
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_REJECTED && writes==0); ++checks;
    setup(0,7); request.operation[0]^=1;
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_REJECTED && writes==0); ++checks;
    setup(0,7); boot_bytes[65535]^=1;
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_REJECTED && writes==0); boot_bytes[65535]^=1; ++checks;
    setup(0,7); request.image=candidate;
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_REJECTED && writes==0); ++checks;
    setup(0,7); app[0x500]^=1;
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_REJECTED && writes==0); app[0x500]^=1; ++checks;
    setup(0,7); change_pre(BCB_STATE_CONFIRMED,0,0,30276);
    bcb_deserialize(ee,&observed); observed.boot_try=0; bcb_serialize(&observed,ee); memcpy(plan.before,ee,128);
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_ALREADY && writes==0); ++checks;

    for(active=0;active<2;++active) for(i=0;i<=64;++i) {
        setup(active,65535); target(active,expected); prefix=(int)i; write_error=1;
        rc=rc_confirm(&plan,&request,&hal,&result);
        assert(writes==1 && result.write_attempts==1);
        assert(!memcmp(ee+active*64u,plan.before[active],64));
        assert(rc==(!memcmp(ee,expected,128) ? RC_CONFIRMED : RC_NOT_CONFIRMED)); ++checks;
    }
    for(i=1;i<=normal_reads;++i) {
        setup(0,7); target(0,expected); fail_read=i;
        rc=rc_confirm(&plan,&request,&hal,&result);
        assert(writes<=1);
        if(i<=8) assert(writes==0);
        if(rc==RC_CONFIRMED) assert(!memcmp(ee,expected,128));
        if(i>=12) assert(rc==RC_UNKNOWN);
        ++checks;
    }
    setup(0,7); persistent_read=1;
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_UNKNOWN && writes==0); ++checks;
    setup(0,7); persistent_after_write=1;
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_UNKNOWN && writes==1); ++checks;
    setup(0,7); drift_read=3;
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_REJECTED && writes==0); ++checks;

    /* Separate ordinary OTA action, not a NOR side effect of confirmation. */
    setup(0,65535); memset(nor,0xff,sizeof(nor)); memset(nor+0x200000,0x6d,0x100000);
    memcpy(nor+0x1000,candidate,sizeof(candidate));
    assert(rc_confirm(&plan,&request,&hal,&result)==RC_CONFIRMED && nor_writes==0);
    {
        ota_backup_io_t io={NULL,ar,nr,ne,np};
        ota_backup_info_t info;
        assert(ota_backup_stage(&io,&hal,&info)==OTA_BACKUP_OK);
        assert(bcb_arbiter(&hal,&observed)>0 && observed.state==BCB_STATE_STAGED);
        assert(observed.cur_vcode==30276 && observed.cand_vcode==30277 && observed.backup_vcode==30276);
        assert(nor_writes>0 && writes==2);
        for(i=0x200000;i<sizeof(nor);++i) assert(nor[i]==0x6d);
        printf("NORMAL_STAGING_PASS nor_calls=%u eeprom_writes=%u\n",nor_writes,writes);
    }
    ++checks;
    printf("CONFIRM_SUPERVISOR_HOST_PASS checks=%u normal_reads=%u\n",checks,normal_reads);
    return 0;
}
