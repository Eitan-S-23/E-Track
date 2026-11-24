/* Host-only I/O census of the real package, backup and Boot implementations. */
#include <setjmp.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "OTA/ota_backup.h"
#include "OTA/ota_confirm.h"
#include "OTA/ota_package.h"
#include "boot_state_machine.h"

#define BLOCK 4096u
#define EXTERNAL_SIZE (OTA_EXT_BACKUP + OTA_EXT_SLOT_LENGTH)

enum { CANDIDATE_PHASE, BACKUP_PHASE, BOOT_PHASE, RESUME_PHASE,
       CONFIRM_PHASE, PHASE_COUNT };
enum { PACKAGE, CANDIDATE, BACKUP, INTERNAL, EEPROM, RESOURCE_COUNT };
enum { READ_OP, ERASE_OP, PROGRAM_OP, OP_COUNT };
enum { NORMAL, BAD_PACKAGE, BAD_CANDIDATE, BAD_BACKUP_WRITE,
       NOT_CONFIRMED, CUT_BEFORE, CUT_AFTER, BAD_RESUME, BAD_STAGED };

typedef struct { uint32_t calls, bytes; } count_t;
typedef struct {
    count_t io[RESOURCE_COUNT][OP_COUNT];
    int ran, interrupted, result;
} phase_t;
typedef struct { const uint8_t *data; uint32_t len; } image_t;

static const char *phase_names[] = {
    "candidate", "backup", "boot", "boot_resume", "confirmation_commit"
};
static const char *resource_names[] = {
    "package", "candidate", "backup", "internal", "eeprom"
};
static const char *op_names[] = { "read", "erase", "program" };
static const char *mode_names[] = {
    "normal", "bad-package", "bad-candidate", "bad-backup-write",
    "not-confirmed", "cut-before", "cut-after", "bad-resume", "bad-staged"
};
static phase_t phases[PHASE_COUNT];
static int phase = -1, mode, checks, failures, injection_seen, cut_armed;
static uint32_t cut_block, package_len, current_len, target_len;
static uint8_t *package_bytes, *current_image, *target_image, *external, *internal;
static uint8_t eeprom[256];
static uint64_t workspace[OTA_PACKAGE_WORKSPACE_SIZE / sizeof(uint64_t)];
static int workspace_owned;
static jmp_buf power_loss;
static ota_backup_info_t backup_info;
static boot_state_outcome_t outcome;

static void check(const char *name, int ok)
{
    ++checks;
    if (!ok) {
        ++failures;
        fprintf(stderr, "FAIL: %s\n", name);
    }
}

static void count(int resource, int op, uint32_t len)
{
    if (phase >= 0) {
        count_t *item = &phases[phase].io[resource][op];
        ++item->calls;
        item->bytes += len;
    }
}

static int range_ok(uint32_t address, uint32_t len, uint32_t size)
{
    return address <= size && len <= size - address;
}

static int slot_range(uint32_t address, uint32_t len)
{
    uint32_t base = address < OTA_EXT_BACKUP ? OTA_EXT_CANDIDATE : OTA_EXT_BACKUP;
    return len != 0u && address >= base && address < base + OTA_EXT_SLOT_LENGTH &&
           range_ok(address - base, len, OTA_EXT_SLOT_LENGTH);
}

static int nor_program(uint8_t *dst, const uint8_t *src, uint32_t len)
{
    uint32_t i;
    for (i = 0; i < len; ++i) {
        if ((dst[i] & src[i]) != src[i]) return -1;
    }
    for (i = 0; i < len; ++i) dst[i] &= src[i];
    return 0;
}

static int external_read(void *ctx, uint32_t address, uint8_t *dst, uint32_t len)
{
    (void)ctx;
    if (!dst || !slot_range(address, len)) return -1;
    memcpy(dst, external + address, len);
    count(address < OTA_EXT_BACKUP ? CANDIDATE : BACKUP, READ_OP, len);
    return 0;
}

static int external_erase(void *ctx, uint32_t address)
{
    (void)ctx;
    if (address % BLOCK || !slot_range(address, BLOCK)) return -1;
    memset(external + address, 0xff, BLOCK);
    count(address < OTA_EXT_BACKUP ? CANDIDATE : BACKUP, ERASE_OP, BLOCK);
    return 0;
}

static int external_program(void *ctx, uint32_t address,
                            const uint8_t *src, uint32_t len)
{
    (void)ctx;
    if (!src || !slot_range(address, len) ||
        nor_program(external + address, src, len)) return -1;
    count(address < OTA_EXT_BACKUP ? CANDIDATE : BACKUP, PROGRAM_OP, len);
    if (mode == BAD_BACKUP_WRITE && !injection_seen &&
        address == OTA_EXT_BACKUP + OTA_SLOT_HEADER_SIZE) {
        external[address] ^= 1u;
        injection_seen = 1;
    }
    return 0;
}

static int package_read(void *ctx, uint32_t offset, uint8_t *dst, uint32_t len)
{
    (void)ctx;
    if (!dst || !range_ok(offset, len, package_len)) return -1;
    memcpy(dst, package_bytes + offset, len);
    count(PACKAGE, READ_OP, len);
    return 0;
}

static int candidate_prepare(void *ctx, uint32_t len)
{
    uint32_t address, end;
    if (!len || len > OTA_APP_LENGTH) return -1;
    /* HAL candidate_prepare's sector policy, not measured physical erases. */
    end = OTA_SLOT_HEADER_SIZE + ((len + BLOCK - 1u) / BLOCK) * BLOCK;
    for (address = 0; address < end; address += BLOCK) {
        if (external_erase(ctx, address)) return -1;
    }
    return 0;
}

static int candidate_program(void *ctx, uint32_t offset,
                             const uint8_t *src, uint32_t len)
{
    if (!range_ok(offset, len, OTA_APP_LENGTH)) return -1;
    return external_program(ctx, OTA_SLOT_HEADER_SIZE + offset, src, len);
}

static int candidate_read(void *ctx, uint32_t offset, uint8_t *dst, uint32_t len)
{
    if (!range_ok(offset, len, OTA_APP_LENGTH)) return -1;
    return external_read(ctx, OTA_SLOT_HEADER_SIZE + offset, dst, len);
}

static int acquire(void *ctx, uint8_t **out, uint32_t *len)
{
    (void)ctx;
    if (workspace_owned) return -1;
    workspace_owned = 1;
    *out = (uint8_t *)workspace;
    *len = sizeof(workspace);
    return 0;
}

static void release(void *ctx, uint8_t *data, uint32_t len)
{
    uint32_t i;
    (void)ctx;
    check("workspace ownership and size", workspace_owned &&
          data == (uint8_t *)workspace && len == sizeof(workspace));
    for (i = 0; i < len; ++i) {
        if (data[i] != 0u) break;
    }
    check("workspace wiped by real decoder", i == len);
    workspace_owned = 0;
}

static int app_read(void *ctx, uint32_t offset, uint8_t *dst, uint32_t len)
{
    (void)ctx;
    if (!dst || !range_ok(offset, len, OTA_APP_LENGTH)) return -1;
    memcpy(dst, internal + offset, len);
    count(INTERNAL, READ_OP, len);
    return 0;
}

static int boot_internal_read(void *ctx, uint32_t address, uint8_t *dst, size_t len)
{
    if (address < OTA_APP_ORIGIN || len > OTA_APP_LENGTH) return -1;
    return app_read(ctx, address - OTA_APP_ORIGIN, dst, (uint32_t)len);
}

static int boot_external_read(void *ctx, uint32_t address, uint8_t *dst, size_t len)
{
    if (len > EXTERNAL_SIZE) return -1;
    return external_read(ctx, address, dst, (uint32_t)len);
}

static int boot_erase(void *ctx, uint32_t address)
{
    (void)ctx;
    if (address < OTA_APP_ORIGIN || address % BLOCK ||
        !range_ok(address - OTA_APP_ORIGIN, BLOCK, OTA_APP_LENGTH)) return -1;
    memset(internal + address - OTA_APP_ORIGIN, 0xff, BLOCK);
    count(INTERNAL, ERASE_OP, BLOCK);
    return 0;
}

static int boot_program(void *ctx, uint32_t address, const uint8_t *src, size_t len)
{
    (void)ctx;
    if (!src || address < OTA_APP_ORIGIN || len > OTA_APP_LENGTH ||
        !range_ok(address - OTA_APP_ORIGIN, (uint32_t)len, OTA_APP_LENGTH) ||
        nor_program(internal + address - OTA_APP_ORIGIN, src, (uint32_t)len)) return -1;
    count(INTERNAL, PROGRAM_OP, (uint32_t)len);
    return 0;
}

static int eeprom_read(uint8_t address, uint8_t *dst, uint16_t len)
{
    if (!dst || !range_ok(address, len, 2u * BCB_SIZE)) return -1;
    memcpy(dst, eeprom + address, len);
    count(EEPROM, READ_OP, len);
    return 0;
}

static int eeprom_write(uint8_t address, const uint8_t *src, uint16_t len)
{
    bcb_t next;
    int cut;
    if (!src || len != BCB_SIZE || (address != BCB_A_ADDR && address != BCB_B_ADDR))
        return -1;
    bcb_deserialize(src, &next);
    cut = cut_armed && phase == BOOT_PHASE && next.state == BCB_STATE_APPLYING &&
          next.resume_block == cut_block;
    if (cut && mode == CUT_BEFORE) {
        injection_seen = 1;
        cut_armed = 0;
        longjmp(power_loss, 1);
    }
    memcpy(eeprom + address, src, len);
    count(EEPROM, PROGRAM_OP, len);
    if (cut) {
        injection_seen = 1;
        cut_armed = 0;
        longjmp(power_loss, 1);
    }
    return 0;
}

static const bcb_hal_t bcb_hal = { eeprom_write, eeprom_read };

static bcb_t active_bcb(void)
{
    bcb_t result;
    bcb_arbiter_result_t selected;
    int saved = phase;
    phase = -1;
    memset(&result, 0, sizeof(result));
    selected = bcb_arbiter(&bcb_hal, &result);
    check("BCB arbitration", selected == BCB_ARBITER_A || selected == BCB_ARBITER_B);
    phase = saved;
    return result;
}

static uint8_t *load_file(const char *path, uint32_t limit, uint32_t *len)
{
    FILE *file = fopen(path, "rb");
    long size;
    uint8_t *bytes;
    if (!file) return NULL;
    if (fseek(file, 0, SEEK_END) || (size = ftell(file)) <= 0 ||
        (unsigned long)size > limit || fseek(file, 0, SEEK_SET)) {
        fclose(file);
        return NULL;
    }
    bytes = (uint8_t *)malloc((size_t)size);
    if (!bytes || fread(bytes, 1, (size_t)size, file) != (size_t)size) {
        free(bytes);
        fclose(file);
        return NULL;
    }
    fclose(file);
    *len = (uint32_t)size;
    return bytes;
}

static int image_read(void *ctx, uint32_t offset, uint8_t *dst, size_t len)
{
    const image_t *image = (const image_t *)ctx;
    if (len > image->len || !range_ok(offset, (uint32_t)len, image->len)) return -1;
    memcpy(dst, image->data + offset, len);
    return 0;
}

static int validate_image(const uint8_t *data, uint32_t len, boot_fw_header_t *header)
{
    image_t image = { data, len };
    boot_image_reader_t reader = { image_read, &image };
    boot_fw_expectations_t expectations;
    boot_fw_default_expectations(&expectations);
    return boot_fw_header_validate(&reader, &expectations, header) == BOOT_FW_OK &&
           header->image_len == len;
}

static void guard_tests(void)
{
    uint8_t byte = 0xff;
    uint8_t zero = 0;
    uint8_t before = internal[0];
    check("no cross-slot program", external_program(NULL, OTA_EXT_BACKUP - 1u, &byte, 2u) != 0);
    check("no recovery erase", external_erase(NULL, OTA_EXT_RECOVERY) != 0);
    check("no unaligned erase", external_erase(NULL, 1u) != 0);
    check("no Boot overwrite", boot_program(NULL, OTA_BOOT_ORIGIN, &zero, 1u) != 0);
    check("no EEPROM settings write", eeprom_write(0xff, &zero, 1u) != 0);
    check("internal guard unchanged", internal[0] == before);
    check("NOR rejects zero-to-one", nor_program(&zero, &byte, 1u) != 0 && zero == 0u);
}

static void start_phase(int next)
{
    phase = next;
    phases[next].ran = 1;
}

static void run_workload(const boot_fw_header_t *old_header,
                         const boot_fw_header_t *new_header)
{
    ota_package_io_t package_io = {
        NULL, package_read, candidate_prepare, candidate_program,
        candidate_read, acquire, release
    };
    ota_package_device_t device = { old_header->version_code, 1u, 1u, 1u };
    ota_package_info_t package_info;
    ota_backup_io_t backup_io = { NULL, app_read, external_read, external_erase, external_program };
    boot_state_io_t boot_io = {
        &bcb_hal, NULL, boot_external_read, boot_internal_read, boot_erase,
        boot_program, NULL, 1
    };
    bcb_t current;

    if (mode == BAD_PACKAGE) {
        package_bytes[package_len - 1u] ^= 1u;
        injection_seen = 1;
    }
    start_phase(CANDIDATE_PHASE);
    phases[phase].result = ota_package_apply_full(&package_io, &device, package_len, &package_info);
    check("workspace released", !workspace_owned);
    if (mode == BAD_PACKAGE) {
        check("payload CRC rejected before candidate erase", phases[phase].result == OTA_PACKAGE_ERR_PAYLOAD_CRC &&
              phases[phase].io[CANDIDATE][ERASE_OP].calls == 0 &&
              phases[phase].io[CANDIDATE][PROGRAM_OP].calls == 0);
        return;
    }
    check("full package accepted", phases[phase].result == OTA_PACKAGE_OK);
    if (phases[phase].result != OTA_PACKAGE_OK) return;
    check("candidate exact target bytes", package_info.image_len == target_len &&
          package_info.target_vcode == new_header->version_code &&
          memcmp(external + OTA_SLOT_HEADER_SIZE, target_image, target_len) == 0);
    if (failures) return;
    if (mode == BAD_CANDIDATE) {
        external[OTA_SLOT_HEADER_SIZE + target_len - 1u] ^= 1u;
        injection_seen = 1;
    }
    if (mode == NOT_CONFIRMED) {
        /* Simulate a state change between candidate creation and staging. */
        current = active_bcb();
        current.state = BCB_STATE_TEST_BOOT;
        bcb_serialize(&current, eeprom + BCB_A_ADDR);
        bcb_serialize(&current, eeprom + BCB_B_ADDR);
    }
    start_phase(BACKUP_PHASE);
    phases[phase].result = ota_backup_stage(&backup_io, &bcb_hal, &backup_info);
    current = active_bcb();
    if (mode == BAD_CANDIDATE || mode == BAD_BACKUP_WRITE || mode == NOT_CONFIRMED) {
        int expected = mode == BAD_CANDIDATE ? OTA_BACKUP_ERR_CANDIDATE_HEADER :
                       mode == BAD_BACKUP_WRITE ? OTA_BACKUP_ERR_READBACK : OTA_BACKUP_ERR_STATE;
        check("backup failure classified", phases[phase].result == expected);
        check("no BCB write on backup failure", phases[phase].io[EEPROM][PROGRAM_OP].calls == 0);
        check("backup failure preserves state", current.state ==
              (mode == NOT_CONFIRMED ? BCB_STATE_TEST_BOOT : BCB_STATE_CONFIRMED));
        if (mode != BAD_BACKUP_WRITE)
            check("preflight rejection has no erase", phases[phase].io[BACKUP][ERASE_OP].calls == 0);
        return;
    }
    check("backup stage committed", phases[phase].result == OTA_BACKUP_OK &&
          current.state == BCB_STATE_STAGED && backup_info.commit_state == OTA_BACKUP_COMMIT_VERIFIED_STAGED);
    check("backup exact retained bytes", backup_info.backup_len == current_len &&
          memcmp(external + OTA_EXT_BACKUP + OTA_SLOT_HEADER_SIZE, current_image, current_len) == 0);
    check("reported erase count matches I/O", backup_info.erase_count ==
          phases[phase].io[CANDIDATE][ERASE_OP].calls + phases[phase].io[BACKUP][ERASE_OP].calls);
    check("reported program count matches I/O", backup_info.program_count ==
          phases[phase].io[CANDIDATE][PROGRAM_OP].calls + phases[phase].io[BACKUP][PROGRAM_OP].calls);
    if (failures) return;
    if (mode == BAD_STAGED) {
        external[OTA_SLOT_HEADER_SIZE + target_len - 1u] ^= 1u;
        injection_seen = 1;
    }
    start_phase(BOOT_PHASE);
    cut_armed = mode == CUT_BEFORE || mode == CUT_AFTER || mode == BAD_RESUME;
    /* Only persistent memory survives the simulated loss of control flow. */
    if (setjmp(power_loss) == 0) {
        phases[BOOT_PHASE].result = boot_state_machine_run(&boot_io, &outcome);
    } else {
        phases[BOOT_PHASE].interrupted = 1;
        current = active_bcb();
        check("cut leaves valid APPLYING checkpoint", current.state == BCB_STATE_APPLYING &&
              current.resume_block == cut_block - (mode == CUT_BEFORE ? 1u : 0u));
        if (mode == BAD_RESUME) internal[0] ^= 1u;
        start_phase(RESUME_PHASE);
        phases[RESUME_PHASE].result = boot_state_machine_run(&boot_io, &outcome);
    }
    check("Boot returns valid image", phases[phase].result == BOOT_STATE_STATUS_OK &&
          outcome.action == BOOT_STATE_ACTION_JUMP_APP);
    if (mode == BAD_STAGED || mode == BAD_RESUME) {
        check("corruption rolls back to retained image", outcome.bcb.state == BCB_STATE_CONFIRMED &&
              outcome.app_header.version_code == old_header->version_code &&
              memcmp(internal, current_image, current_len) == 0);
        return;
    }
    check("Boot target verified, still TEST_BOOT", outcome.bcb.state == BCB_STATE_TEST_BOOT &&
          outcome.app_header.version_code == new_header->version_code &&
          memcmp(internal, target_image, target_len) == 0);
    if (failures) return;
    /* This tests the commit helper only, not actual App startup/health. */
    start_phase(CONFIRM_PHASE);
    phases[phase].result = ota_confirm_test_boot(&bcb_hal, &current);
    check("host confirmation commit", phases[phase].result == OTA_CONFIRM_COMMITTED &&
          current.state == BCB_STATE_CONFIRMED && current.cur_vcode == new_header->version_code);
}

static void print_result(void)
{
    bcb_t current = active_bcb();
    int p, r, o;
    printf("{\"schema\":1,\"kind\":\"HOST_INSTALL_WORKLOAD\",\"hardware\":false,"
           "\"hardware_timing\":false,\"scenario\":\"%s\",\"cut_block\":%lu,"
           "\"injection_seen\":%s,\"passed\":%s,\"checks\":%d,\"failures\":%d,"
           "\"package_bytes\":%lu,\"current_bytes\":%lu,\"target_bytes\":%lu,"
           "\"final_bcb_state\":%u,\"final_vcode\":%lu,\"phases\":{",
           mode_names[mode], (unsigned long)cut_block, injection_seen ? "true" : "false",
           failures ? "false" : "true", checks, failures, (unsigned long)package_len,
           (unsigned long)current_len, (unsigned long)target_len, current.state,
           (unsigned long)current.cur_vcode);
    for (p = 0; p < PHASE_COUNT; ++p) {
        printf("%s\"%s\":{\"ran\":%s,\"interrupted\":%s,\"result_code\":",
               p ? "," : "", phase_names[p], phases[p].ran ? "true" : "false",
               phases[p].interrupted ? "true" : "false");
        if (!phases[p].ran || phases[p].interrupted) printf("null");
        else printf("%d", phases[p].result);
        printf(",\"io\":{");
        for (r = 0; r < RESOURCE_COUNT; ++r) {
            printf("%s\"%s\":{", r ? "," : "", resource_names[r]);
            for (o = 0; o < OP_COUNT; ++o) {
                count_t *c = &phases[p].io[r][o];
                printf("%s\"%s\":{\"calls\":%lu,\"bytes\":%lu}",
                       o ? "," : "", op_names[o], (unsigned long)c->calls, (unsigned long)c->bytes);
            }
            printf("}");
        }
        printf("}}");
    }
    printf("}}\n");
}

int main(int argc, char **argv)
{
    boot_fw_header_t old_header, new_header;
    bcb_t initial;
    char *end;
    unsigned long requested;
    if (argc != 6) {
        fprintf(stderr, "usage: install_workload PACKAGE CURRENT TARGET SCENARIO CUT_BLOCK\n");
        return 2;
    }
    for (mode = 0; mode < (int)(sizeof(mode_names) / sizeof(mode_names[0])); ++mode)
        if (!strcmp(argv[4], mode_names[mode])) break;
    if (mode == (int)(sizeof(mode_names) / sizeof(mode_names[0]))) return 2;
    requested = strtoul(argv[5], &end, 10);
    if (!argv[5][0] || *end || requested > OTA_APP_LENGTH / BLOCK) return 2;
    cut_block = (uint32_t)requested;
    package_bytes = load_file(argv[1], OTA_ETU_MAX_LENGTH, &package_len);
    current_image = load_file(argv[2], OTA_APP_LENGTH, &current_len);
    target_image = load_file(argv[3], OTA_APP_LENGTH, &target_len);
    if (!package_bytes || !current_image || !target_image ||
        !validate_image(current_image, current_len, &old_header) ||
        !validate_image(target_image, target_len, &new_header) ||
        ((mode == CUT_BEFORE || mode == CUT_AFTER || mode == BAD_RESUME) &&
         (!cut_block || cut_block > (target_len + BLOCK - 1u) / BLOCK))) {
        fprintf(stderr, "invalid input image or cut position\n");
        return 2;
    }
    external = (uint8_t *)malloc(EXTERNAL_SIZE);
    internal = (uint8_t *)malloc(OTA_APP_LENGTH);
    if (!external || !internal) return 2;
    memset(external, 0xff, EXTERNAL_SIZE);
    memset(internal, 0xff, OTA_APP_LENGTH);
    memcpy(internal, current_image, current_len);
    memset(eeprom, 0xff, sizeof(eeprom));
    eeprom[255] = 0x55;
    bcb_make_idle(&initial, old_header.version_code);
    initial.state = BCB_STATE_CONFIRMED;
    initial.boot_try = 0;
    bcb_serialize(&initial, eeprom + BCB_A_ADDR);
    bcb_serialize(&initial, eeprom + BCB_B_ADDR);
    guard_tests();
    run_workload(&old_header, &new_header);
    phase = -1;
    check("EEPROM settings preserved", eeprom[255] == 0x55);
    check("declared fault actually injected", mode == NORMAL || mode == NOT_CONFIRMED || injection_seen);
    check("pre-Boot failure never changes current App", phases[BOOT_PHASE].ran ||
          memcmp(internal, current_image, current_len) == 0);
    print_result();
    free(package_bytes);
    free(current_image);
    free(target_image);
    free(external);
    free(internal);
    return failures ? 1 : 0;
}
