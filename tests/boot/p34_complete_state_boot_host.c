/* HOST_ONLY original Boot branch model. No target transport or reset API. */
#include "confirm.h"
#include "boot_state_machine.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static uint8_t boot[65536], old[617588], image[619580], capture[619580];
static uint8_t flash[OTA_APP_LENGTH], nor[0x300000], ee[128], before[256];
static unsigned erases, programs, commits;
static uint32_t erase_end, program_end;

static int er(uint8_t address, uint8_t *data, uint16_t size)
{
    assert((address == 0 || address == 64) && size == 64);
    memcpy(data, ee+address, size); return 0;
}
static int ew(uint8_t address, const uint8_t *data, uint16_t size)
{
    assert((address == 0 || address == 64) && size == 64);
    memcpy(ee+address, data, size); ++commits; return 0;
}
static const bcb_hal_t hal = {ew, er};
static int ir(void *ctx, uint32_t address, uint8_t *data, size_t size)
{
    (void)ctx;
    assert(address >= OTA_APP_ORIGIN && address-OTA_APP_ORIGIN <= sizeof(flash));
    assert(size <= sizeof(flash)-(address-OTA_APP_ORIGIN));
    memcpy(data, flash+address-OTA_APP_ORIGIN, size); return 0;
}
static int nr(void *ctx, uint32_t address, uint8_t *data, size_t size)
{
    (void)ctx;
    assert(address <= sizeof(nor) && size <= sizeof(nor)-address);
    memcpy(data, nor+address, size); return 0;
}
static int ie(void *ctx, uint32_t address)
{
    (void)ctx;
    assert(!(address & 4095u) && address >= OTA_APP_ORIGIN);
    assert(address-OTA_APP_ORIGIN <= sizeof(flash)-4096);
    memset(flash+address-OTA_APP_ORIGIN, 0xff, 4096);
    if (address+4096 > erase_end) erase_end=address+4096;
    ++erases; return 0;
}
static int ip(void *ctx, uint32_t address, const uint8_t *data, size_t size)
{
    size_t i;
    (void)ctx;
    assert(address >= OTA_APP_ORIGIN && address-OTA_APP_ORIGIN <= sizeof(flash));
    assert(!(address & 3u) && !(size & 3u) && size <= sizeof(flash)-(address-OTA_APP_ORIGIN));
    for (i=0; i<size; ++i) {
        assert((flash[address-OTA_APP_ORIGIN+i] & data[i]) == data[i]);
        flash[address-OTA_APP_ORIGIN+i] &= data[i];
    }
    if (address+size > program_end) program_end=address+(uint32_t)size;
    ++programs; return 0;
}
static boot_state_outcome_t run(void)
{
    boot_state_outcome_t result;
    boot_state_io_t io = {&hal, NULL, nr, ir, ie, ip, NULL, 1};
    assert(boot_state_machine_run(&io, &result) == BOOT_STATE_STATUS_OK);
    assert(result.action == BOOT_STATE_ACTION_JUMP_APP);
    return result;
}
static void setup(void)
{
    memset(flash, 0x6b, sizeof(flash));
    memcpy(flash, capture, sizeof(capture));
    memcpy(ee, before, sizeof(ee)); erases=programs=commits=0;
    erase_end=program_end=0;
}
static void load(const char *path, uint8_t *data, size_t size)
{
    FILE *f = fopen(path, "rb"); assert(f);
    assert(fread(data, 1, size, f) == size && fgetc(f) == EOF); fclose(f);
}
int main(int argc, char **argv)
{
    unsigned i, unchanged=0, rollback=0;
    boot_state_outcome_t result;
    rc_plan plan;
    rc_request request;
    rc_result confirmed;
    bcb_t active;
    uint8_t saved;
    if (argc != 9) return 2;
    load(argv[1], boot, sizeof(boot)); load(argv[2], old, sizeof(old));
    load(argv[3], image, sizeof(image)); load(argv[4], before, sizeof(before));
    load(argv[5], nor, 0x200000); load(argv[6], nor+0x200000, 0x99000);
    load(argv[7], nor+0x299000, 0x67000); load(argv[8], capture, sizeof(capture));
    assert(!memcmp(old, capture, sizeof(old)) && !memcmp(before, before+128, 128));

    setup(); result=run();
    assert(result.app_header.version_code == 30275 && !erases && !programs && !commits);
    printf("BOOT_MODEL original=30275 recovery_not_forced=1\n");

    setup(); memcpy(flash, image, sizeof(image)); result=run();
    assert(result.app_header.version_code == 30276 && result.bcb.cur_vcode == 30275);
    assert(!erases && !programs && !commits);
    printf("BOOT_MODEL complete_image_before_confirmation=30276 bcb_current=30275\n");

    setup(); memcpy(flash, image, sizeof(image));
    memset(&plan, 0, sizeof(plan)); memcpy(plan.before, before, 128);
    memset(&request, 0, sizeof(request)); request.boot=boot; request.boot_length=sizeof(boot);
    request.image=image; request.image_length=sizeof(image);
    assert(rc_confirm(&plan, &request, &hal, &confirmed) == RC_CONFIRMED && commits == 1);
    assert(bcb_arbiter(&hal, &active) == confirmed.active);
    printf("BOOT_MODEL confirmation_slot=%u seq=%u\n", (unsigned)confirmed.active,
           (unsigned)active.seq);
    result=run();
    assert(result.app_header.version_code == 30276 && result.bcb.cur_vcode == 30276);
    assert(!erases && !programs && commits == 1);
    printf("BOOT_MODEL complete_state=30276 bcb_current=30276\n");

    for (i=0; i<303; ++i) {
        int same;
        setup(); memset(flash+i*2048u, 0xff, 2048);
        same = memcmp(flash, old, sizeof(old)) == 0;
        result=run();
        if (same) {
            assert(result.app_header.version_code == 30275 && !erases && !commits);
            ++unchanged;
        } else {
            assert(result.app_header.version_code == 30274 && result.bcb.cur_vcode == 30274);
            assert(erases && programs && commits); ++rollback;
        }
    }
    printf("BOOT_MODEL isolated_sector_erases=303 old_survives=%u backup30274=%u\n", unchanged, rollback);

    setup(); memset(flash, 0xff, 2048);
    saved=nor[0x100000]; nor[0x100000]^=1;
    result=run(); nor[0x100000]=saved;
    assert(result.app_header.version_code == 30276 && result.bcb.cur_vcode == 30276);
    assert(erases && programs && commits);
    assert(erase_end == 0x080A8000u && program_end == erase_end);
    for (i=sizeof(image); i<erase_end-OTA_APP_ORIGIN; ++i) assert(flash[i] == 0xff);
    printf("BOOT_MODEL invalid_internal_and_backup_recovery=30276\n");
    printf("BOOT_MODEL recovery_erase_end=0x%08lX program_end=0x%08lX extra_beyond_direct=2048\n",
           (unsigned long)erase_end, (unsigned long)program_end);
    printf("COMPLETE_STATE_BOOT_HOST_PASS hardware=0 reset_qualified=0\n");
    return 0;
}
