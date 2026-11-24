#include "boot_state_machine.h"
#include "OTA/ota_backup.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static uint8_t image[0xf0000], eeprom[128];
static uint32_t image_length;
static unsigned eeprom_writes, external_reads, flash_writes;

static int er(uint8_t address, uint8_t *data, uint16_t length)
{
    assert(address <= sizeof(eeprom) && length <= sizeof(eeprom)-address);
    memcpy(data,eeprom+address,length); return 0;
}
static int ew(uint8_t address, const uint8_t *data, uint16_t length)
{
    assert(address <= sizeof(eeprom) && length <= sizeof(eeprom)-address);
    ++eeprom_writes; memcpy(eeprom+address,data,length); return 0;
}
static int ar(void *ctx, uint32_t offset, uint8_t *data, uint32_t length)
{
    (void)ctx;
    if (offset > image_length || length > image_length-offset) return -1;
    memcpy(data,image+offset,length); return 0;
}
static int ir(void *ctx, uint32_t address, uint8_t *data, size_t length)
{
    if (address < OTA_APP_ORIGIN || length > image_length) return -1;
    return ar(ctx,address-OTA_APP_ORIGIN,data,(uint32_t)length);
}
static int fr(void *ctx, uint32_t address, uint8_t *data, uint32_t length)
{
    (void)ctx; (void)address; (void)data; (void)length;
    ++external_reads; return -1;
}
static int fe(void *ctx, uint32_t address)
{
    (void)ctx; (void)address; ++flash_writes; return -1;
}
static int fp(void *ctx, uint32_t address, const uint8_t *data, uint32_t length)
{
    (void)ctx; (void)address; (void)data; (void)length; ++flash_writes; return -1;
}
static int ip(void *ctx, uint32_t address, const uint8_t *data, size_t length)
{
    assert(length <= UINT32_MAX);
    return fp(ctx,address,data,(uint32_t)length);
}

int main(int argc, char **argv)
{
    FILE *file;
    bcb_t current;
    bcb_hal_t hal = {ew,er};
    boot_state_io_t boot;
    boot_state_outcome_t outcome;
    ota_backup_io_t backup = {NULL,ar,fr,fe,fp};
    if (argc != 2 || (file=fopen(argv[1],"rb")) == NULL) return 2;
    image_length = (uint32_t)fread(image,1,sizeof(image),file);
    assert(!ferror(file) && fgetc(file) == EOF); fclose(file);
    memset(eeprom,0xff,sizeof(eeprom));
    bcb_make_idle(&current,30275u); current.state = BCB_STATE_CONFIRMED;
    bcb_serialize(&current,eeprom);
    memset(&boot,0,sizeof(boot)); boot.bcb_hal=&hal; boot.internal_read=ir;
    boot.internal_erase_4k=fe; boot.internal_program=ip;
    assert(boot_state_machine_run(&boot,&outcome) == BOOT_STATE_STATUS_OK);
    assert(outcome.action == BOOT_STATE_ACTION_JUMP_APP && outcome.app_header.version_code == 30276u);
    assert(outcome.bcb.cur_vcode == 30275u && eeprom_writes == 0u);
    assert(ota_backup_stage(&backup,&hal,NULL) == OTA_BACKUP_ERR_APP_HEADER);
    assert(external_reads == 0u && eeprom_writes == 0u && flash_writes == 0u);
    puts("DIRECT_R2_RESTORE_STARTS_BUT_NEXT_OTA_REJECTED");
    /* Host-only exploration of existing transaction, NOT a device entry plan. */
    assert(boot_state_machine_accept_physical_recovery(&boot,&outcome) == BOOT_STATE_STATUS_OK);
    assert(outcome.action == BOOT_STATE_ACTION_JUMP_APP && outcome.bcb.cur_vcode == 30276u);
    assert(outcome.bcb.state == BCB_STATE_CONFIRMED && eeprom_writes > 0u);
    assert(ota_backup_stage(&backup,&hal,NULL) == OTA_BACKUP_ERR_CANDIDATE_HEADER);
    assert(external_reads == 1u && flash_writes == 0u);
    puts("ORIGINAL_RECOVERY_CONFIRMATION_CONVERGES_VERSION_IN_HOST_FIXTURE");
    return 0;
}
