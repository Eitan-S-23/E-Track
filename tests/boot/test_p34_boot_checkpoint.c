/* Real state machine and BCB serialization; only the storage/CPU are simulated. */
#include <setjmp.h>
#define main original_fixture_main
#include "fixture.c"
#undef main
#include "p34_boot_checkpoint.h"

static jmp_buf power_cut;
static int cut_at, event_count, fired;
static unsigned verified, max_rework, scenarios, cuts;
static int apply_commits, rollback_commits;
static uint8_t template_internal[OTA_APP_LENGTH], template_eeprom[256];
static unsigned page_events, flash_events;

#define REQUIRE(x) do { if (!(x)) { fprintf(stderr, "MODEL_FAIL line=%d group=%d event=%d cut=%d\n", __LINE__, P34_BOOT_APPLY_CHECKPOINT_BLOCKS, event_count, cut_at); exit(9); } } while (0)

static void prefix_oracle(void)
{
    bcb_t active = active_bcb();
    if (active.state == BCB_STATE_APPLYING)
    {
        size_t bytes = (size_t)active.resume_block * TEST_BLOCK_SIZE;
        REQUIRE(active.resume_block <= verified);
        if (bytes > TEST_IMAGE_LEN) bytes = TEST_IMAGE_LEN;
        REQUIRE(memcmp(g_internal, g_candidate_image, bytes) == 0);
    }
}

static void event(int page)
{
    ++event_count;
    if (page) ++page_events; else ++flash_events;
    if (cut_at && event_count == cut_at)
    {
        bcb_t active;
        unsigned rework;
        prefix_oracle();
        active = active_bcb();
        if (active.state == BCB_STATE_APPLYING)
        {
            rework = verified - active.resume_block;
            REQUIRE(rework <= P34_BOOT_APPLY_CHECKPOINT_BLOCKS);
            if (rework > max_rework) max_rework = rework;
        }
        fired = 1;
        longjmp(power_cut, 1);
    }
}

void p34_model_checkpoint(uint32_t point, uint32_t phase, uint32_t block)
{
    if (point == OTA_P1_6_CP_COPY_AFTER_READBACK)
    {
        uint32_t offset = block * TEST_BLOCK_SIZE;
        size_t take = TEST_IMAGE_LEN - offset;
        const uint8_t *expected = phase == BCB_COPY_APPLY ? g_candidate_image : g_current_image;
        if (take > TEST_BLOCK_SIZE) take = TEST_BLOCK_SIZE;
        REQUIRE(memcmp(g_internal + offset, expected + offset, take) == 0);
        for (size_t i = take; i < TEST_BLOCK_SIZE; ++i) REQUIRE(g_internal[offset+i] == 0xff);
        verified = block + 1;
    }
    event(0);
}

static int paged_write(uint8_t reg, const uint8_t *src, uint16_t len)
{
    bcb_t next;
    int call = ++g_eeprom_write_calls;
    REQUIRE(len == BCB_SIZE && (reg == BCB_A_ADDR || reg == BCB_B_ADDR));
    bcb_deserialize(src, &next);
    if (next.state == BCB_STATE_APPLYING) REQUIRE(next.resume_block <= verified);
    if (call == g_fail_eeprom_write_call && !g_fail_eeprom_after_write) return -1;
    for (unsigned offset = 0; offset < len; offset += 8)
    {
        event(1); /* Before the page, and with a torn half-page. */
        memcpy(g_eeprom + reg + offset, src + offset, 4);
        event(1);
        memcpy(g_eeprom + reg + offset + 4, src + offset + 4, 4);
        event(1);
    }
    record_bcb(src);
    if (next.state == BCB_STATE_APPLYING && next.resume_block) ++apply_commits;
    if (next.state == BCB_STATE_ROLLBACK && next.resume_block) ++rollback_commits;
    if (call == g_fail_eeprom_write_call && g_fail_eeprom_after_write) return -1;
    return 0;
}

static const bcb_hal_t model_hal = {paged_write, eeprom_read};

static int model_erase(void *ctx, uint32_t address)
{
    uint8_t remaining[TEST_BLOCK_SIZE/2];
    size_t offset=address-OTA_APP_ORIGIN;
    REQUIRE(offset+TEST_BLOCK_SIZE<=OTA_APP_LENGTH);
    memcpy(remaining,g_internal+offset+sizeof(remaining),sizeof(remaining));
    if (internal_erase(ctx,address)!=0) return -1;
    memcpy(g_internal+offset+sizeof(remaining),remaining,sizeof(remaining));
    event(0);
    memset(g_internal+offset+sizeof(remaining),0xff,sizeof(remaining));
    return 0;
}

static int model_program(void *ctx, uint32_t address, const uint8_t *src, size_t len)
{
    size_t offset = address - OTA_APP_ORIGIN;
    REQUIRE(len == TEST_BLOCK_SIZE && offset + len <= OTA_APP_LENGTH);
    if ((int)(offset/TEST_BLOCK_SIZE) == g_fail_program_block) return -1;
    /* Enforce NOR 1->0 programming and expose a partially programmed page. */
    for (size_t i = 0; i < len; ++i) REQUIRE((g_internal[offset+i] & src[i]) == src[i]);
    memcpy(g_internal + offset, src, len/2);
    event(0);
    REQUIRE(internal_program(ctx, address, src, len) == 0);
    event(0);
    return 0;
}

static boot_state_outcome_t run_model(int cut)
{
    boot_state_io_t io;
    boot_state_outcome_t outcome;
    bcb_t active = active_bcb();
    verified = active.resume_block;
    memset(&io, 0, sizeof(io));
    memset(&outcome, 0, sizeof(outcome));
    io.bcb_hal=&model_hal; io.external_read=external_read; io.internal_read=internal_read;
    io.internal_erase_4k=model_erase; io.internal_program=model_program; io.external_available=1;
    cut_at=cut;event_count=0;fired=0;
    if (setjmp(power_cut) == 0) (void)boot_state_machine_run(&io,&outcome);
    else memset(&outcome,0,sizeof(outcome));
    return outcome;
}

static void rehash(uint8_t *image)
{
    boot_sha256_ctx_t sha;
    uint8_t digest[32], *header=image+OTA_FW_HEADER_OFFSET;
    memset(header+40,0,32);memset(header+92,0,4);
    boot_sha256_init(&sha);boot_sha256_update(&sha,image,TEST_IMAGE_LEN);boot_sha256_final(&sha,digest);
    memcpy(header+40,digest,32);put_le32(header+92,boot_crc32(header,92));
}

static void setup(unsigned changed, uint16_t sequence)
{
    bcb_t bcb;
    reset_model();
    make_image(g_current_image,20700,0x11);
    make_image(g_candidate_image,20800,0x11);
    make_image(g_recovery_image,20600,0x33);
    for (unsigned block=1;block<changed;++block)
    {
        unsigned end=(block+1)*TEST_BLOCK_SIZE;
        if (end>TEST_IMAGE_LEN) end=TEST_IMAGE_LEN;
        for (unsigned i=block*TEST_BLOCK_SIZE;i<end;++i) g_candidate_image[i]^=0x40;
    }
    rehash(g_candidate_image);
    install_slot(OTA_EXT_CANDIDATE,BOOT_SLOT_CANDIDATE,g_candidate_image);
    install_slot(OTA_EXT_BACKUP,BOOT_SLOT_BACKUP,g_current_image);
    install_slot(OTA_EXT_RECOVERY,BOOT_SLOT_RECOVERY,g_recovery_image);
    load_internal_image(g_current_image);
    fill_upgrade_bcb(&bcb,BCB_STATE_STAGED,0,0);bcb.seq=sequence;place_bcb(&bcb);
    memcpy(template_internal,g_internal,OTA_APP_LENGTH);memcpy(template_eeprom,g_eeprom,256);
}

static void restore(void)
{
    memcpy(g_internal,template_internal,OTA_APP_LENGTH);memcpy(g_eeprom,template_eeprom,256);
    clear_runtime_counters();apply_commits=0;rollback_commits=0;
}

static void success(boot_state_outcome_t outcome, int rollback)
{
    const uint8_t *image=rollback?g_current_image:g_candidate_image;
    bcb_t active=active_bcb();
    REQUIRE(outcome.action==BOOT_STATE_ACTION_JUMP_APP);
    REQUIRE(memcmp(g_internal,image,TEST_IMAGE_LEN)==0);
    REQUIRE(memcmp(g_external+OTA_EXT_BACKUP+OTA_SLOT_HEADER_SIZE,g_current_image,TEST_IMAGE_LEN)==0);
    if (rollback) REQUIRE(active.state==BCB_STATE_CONFIRMED && active.cur_vcode==20700);
    else REQUIRE(active.state==BCB_STATE_TEST_BOOT && active.boot_try<=2 && active.cand_vcode==20800);
    ++scenarios;
}

static void campaign(unsigned changed)
{
    int events, transactions;
    setup(changed,65534);restore();
    success(run_model(0),0);events=event_count;transactions=g_eeprom_write_calls;
    REQUIRE(apply_commits==(TEST_BLOCK_COUNT+P34_BOOT_APPLY_CHECKPOINT_BLOCKS-1)/P34_BOOT_APPLY_CHECKPOINT_BLOCKS);
    REQUIRE(g_total_erases==(int)changed);
    REQUIRE(active_bcb().seq==(uint16_t)(65534+transactions));
    printf("NORMAL group=%d changed=%u commits=%d events=%d\n",P34_BOOT_APPLY_CHECKPOINT_BLOCKS,changed,apply_commits,events);
    /* Default is byte-identical and keeps its original fault regression suite.
     * Full event sweeps target changed policies on header-only and dense input. */
    for (int at=1;P34_BOOT_APPLY_CHECKPOINT_BLOCKS>1 && changed!=73 && at<=events;++at)
    {
        restore();(void)run_model(at);REQUIRE(fired);++cuts;
        success(run_model(0),0);
    }
    for (int call=1;call<=transactions;++call)
    for (int after=0;after<2;++after)
    {
        boot_state_outcome_t failed;
        if (P34_BOOT_APPLY_CHECKPOINT_BLOCKS==1 && call!=1 && call!=transactions) continue;
        restore();g_fail_eeprom_write_call=call;g_fail_eeprom_after_write=after;
        failed=run_model(0);REQUIRE(failed.action!=BOOT_STATE_ACTION_JUMP_APP);
        g_fail_eeprom_write_call=0;success(run_model(0),0);
    }
}

static void failures(void)
{
    static const int blocks[]={0,15,16,145,150};
    setup(151,0);
    for (unsigned i=0;i<sizeof(blocks)/sizeof(blocks[0]);++i)
    for (int kind=0;kind<3;++kind)
    {
        boot_state_outcome_t failed;
        restore();
        if (kind==0) g_fail_erase_block=blocks[i];
        if (kind==1) g_fail_program_block=blocks[i];
        if (kind==2) g_inject_readback_block=blocks[i];
        failed=run_model(0);REQUIRE(failed.action!=BOOT_STATE_ACTION_JUMP_APP);
        g_fail_erase_block=g_fail_program_block=g_inject_readback_block=-1;g_readback_armed=0;
        success(run_model(0),0);
    }
    restore();g_fail_internal_read_block=0;
    REQUIRE(run_model(0).action!=BOOT_STATE_ACTION_JUMP_APP);
    REQUIRE(g_total_erases==0);g_fail_internal_read_block=-1;success(run_model(0),0);

    /* Corruption and a valid replacement must not reuse the original BCB binding. */
    for (int replacement=0;replacement<2;++replacement)
    {
        restore();(void)run_model(40);REQUIRE(fired);
        if (replacement) install_slot(OTA_EXT_CANDIDATE,BOOT_SLOT_CANDIDATE,g_recovery_image);
        else g_external[OTA_EXT_CANDIDATE+OTA_SLOT_HEADER_SIZE+0x700]^=1;
        success(run_model(0),1);
        install_slot(OTA_EXT_CANDIDATE,BOOT_SLOT_CANDIDATE,g_candidate_image);
    }
    restore();success(run_model(0),0);
    REQUIRE(run_model(0).bcb.boot_try==1);REQUIRE(run_model(0).bcb.boot_try==0);
    rollback_commits=0;success(run_model(0),1);REQUIRE(rollback_commits==TEST_BLOCK_COUNT);

    /* A persisted checkpoint deliberately starting off the group grid remains valid. */
    restore();
    {
        bcb_t bcb;fill_upgrade_bcb(&bcb,BCB_STATE_APPLYING,0,3);place_bcb(&bcb);
        prefill_blocks(g_candidate_image,3);success(run_model(0),0);
    }
}

int main(void)
{
    (void)original_fixture_main;
    setvbuf(stdout,NULL,_IONBF,0);
    g_external=malloc(OTA_EXT_WINDOW_LENGTH);g_internal=malloc(OTA_APP_LENGTH);
    REQUIRE(g_external && g_internal);
    REQUIRE(p34_boot_checkpoint_due(0,1,151));REQUIRE(p34_boot_checkpoint_due(1,151,151));
    campaign(1);campaign(73);campaign(146);failures();
    printf("BOOT_CHECKPOINT_MODEL_PASS group=%d scenarios=%u cuts=%u max_rework=%u page_events=%u flash_events=%u\n",
           P34_BOOT_APPLY_CHECKPOINT_BLOCKS,scenarios,cuts,max_rework,page_events,flash_events);
    free(g_external);free(g_internal);return 0;
}
