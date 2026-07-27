#include "boot_crypto.h"
#include "boot_slot.h"
#include "boot_state_machine.h"
#include "OTA/ota_confirm.h"
#include "OTA/ota_layout.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum
{
    TEST_EEPROM_SIZE = 256,
    TEST_IMAGE_LEN = 0x2800,
    TEST_BLOCK_SIZE = 0x1000,
    TEST_BLOCK_COUNT = 3,
    TEST_HISTORY_MAX = 64
};

typedef struct
{
    uint8_t state;
    uint8_t boot_try;
    uint8_t copy_phase;
    uint16_t resume_block;
    uint32_t cur_vcode;
} bcb_snapshot_t;

static uint8_t g_eeprom[TEST_EEPROM_SIZE];
static uint8_t *g_external;
static uint8_t *g_internal;
static uint8_t g_current_image[TEST_IMAGE_LEN];
static uint8_t g_candidate_image[TEST_IMAGE_LEN];
static uint8_t g_recovery_image[TEST_IMAGE_LEN];

static bcb_snapshot_t g_history[TEST_HISTORY_MAX];
static int g_history_count;
static int g_eeprom_write_calls;
static int g_fail_eeprom_write_call;
static int g_fail_eeprom_after_write;
static int g_erase_count[OTA_APP_LENGTH / TEST_BLOCK_SIZE];
static int g_total_erases;
static uint32_t g_first_erase_address;
static int g_fail_erase_block;
static int g_fail_program_block;
static int g_inject_readback_block;
static int g_readback_armed;

static int g_checks;
static int g_failures;

static void check(const char *name, int condition)
{
    ++g_checks;
    printf("  %-58s %s\n", name, condition ? "PASS" : "FAIL");
    if (!condition)
    {
        ++g_failures;
    }
}

static void put_le32(uint8_t *dst, uint32_t value)
{
    dst[0] = (uint8_t)value;
    dst[1] = (uint8_t)(value >> 8);
    dst[2] = (uint8_t)(value >> 16);
    dst[3] = (uint8_t)(value >> 24);
}

static void make_image(uint8_t image[TEST_IMAGE_LEN],
                       uint32_t version_code, uint8_t seed)
{
    boot_sha256_ctx_t sha;
    uint8_t digest[32];
    uint8_t *header;
    uint32_t i;

    for (i = 0u; i < TEST_IMAGE_LEN; ++i)
    {
        image[i] = (uint8_t)(seed + i * 13u);
    }
    put_le32(image, OTA_RAM_ORIGIN + 0x2000u);
    put_le32(image + 4u, OTA_APP_ORIGIN + 0x801u);

    header = image + OTA_FW_HEADER_OFFSET;
    memset(header, 0, OTA_FW_HEADER_SIZE);
    memcpy(header, "ETFW", 4u);
    put_le32(header + 4u, 1u);
    put_le32(header + 8u, version_code);
    memcpy(header + 12u, "2.8.0", 5u);
    put_le32(header + 28u, 1721000000u);
    put_le32(header + 32u, 1u);
    put_le32(header + 36u, TEST_IMAGE_LEN);
    header[72] = 1u;
    header[73] = 1u;
    memset(header + 74u, 0xFF, 18u);

    boot_sha256_init(&sha);
    boot_sha256_update(&sha, image, TEST_IMAGE_LEN);
    boot_sha256_final(&sha, digest);
    memcpy(header + 40u, digest, sizeof(digest));
    put_le32(header + 92u, boot_crc32(header, 92u));
}

static void install_slot(uint32_t base, uint8_t type,
                         const uint8_t image[TEST_IMAGE_LEN])
{
    uint8_t *header = g_external + base;

    memset(g_external + base, 0xFF, OTA_EXT_SLOT_LENGTH);
    memcpy(g_external + base + OTA_SLOT_HEADER_SIZE, image, TEST_IMAGE_LEN);
    memcpy(header, "ETSL", 4u);
    header[4] = type;
    header[5] = 0xFFu;
    header[6] = 0xFFu;
    header[7] = 0xFFu;
    put_le32(header + 8u, TEST_IMAGE_LEN);
    put_le32(header + 12u, boot_crc32(image, TEST_IMAGE_LEN));
    put_le32(header + 16u,
             (uint32_t)image[OTA_FW_HEADER_OFFSET + 8u] |
                 ((uint32_t)image[OTA_FW_HEADER_OFFSET + 9u] << 8) |
                 ((uint32_t)image[OTA_FW_HEADER_OFFSET + 10u] << 16) |
                 ((uint32_t)image[OTA_FW_HEADER_OFFSET + 11u] << 24));
    memcpy(header + 20u, image + OTA_FW_HEADER_OFFSET + 40u, 8u);
    put_le32(header + 28u, 0x434F4D54u);
}

static void record_bcb(const uint8_t *raw)
{
    bcb_t value;

    if (g_history_count >= TEST_HISTORY_MAX || !bcb_is_valid(raw))
    {
        return;
    }
    bcb_deserialize(raw, &value);
    g_history[g_history_count].state = value.state;
    g_history[g_history_count].boot_try = value.boot_try;
    g_history[g_history_count].copy_phase = value.copy_phase;
    g_history[g_history_count].resume_block = value.resume_block;
    g_history[g_history_count].cur_vcode = value.cur_vcode;
    ++g_history_count;
}

static int eeprom_write(uint8_t reg, const uint8_t *src, uint16_t len)
{
    int call;

    if ((uint16_t)reg + len > TEST_EEPROM_SIZE)
    {
        return -1;
    }
    call = ++g_eeprom_write_calls;
    if (call == g_fail_eeprom_write_call && !g_fail_eeprom_after_write)
    {
        return -1;
    }
    memcpy(g_eeprom + reg, src, len);
    if (len == BCB_SIZE)
    {
        record_bcb(src);
    }
    if (call == g_fail_eeprom_write_call && g_fail_eeprom_after_write)
    {
        return -1;
    }
    return 0;
}

static int eeprom_read(uint8_t reg, uint8_t *dst, uint16_t len)
{
    if ((uint16_t)reg + len > TEST_EEPROM_SIZE)
    {
        return -1;
    }
    memcpy(dst, g_eeprom + reg, len);
    return 0;
}

static const bcb_hal_t g_bcb_hal = { eeprom_write, eeprom_read };

static int external_read(void *ctx, uint32_t address, uint8_t *dst, size_t len)
{
    (void)ctx;
    if (dst == NULL || address > OTA_EXT_WINDOW_LENGTH ||
        len > OTA_EXT_WINDOW_LENGTH - address)
    {
        return -1;
    }
    memcpy(dst, g_external + address, len);
    return 0;
}

static int internal_read(void *ctx, uint32_t address, uint8_t *dst, size_t len)
{
    uint32_t offset;
    int block;

    (void)ctx;
    if (dst == NULL || address < OTA_APP_ORIGIN ||
        address > OTA_APP_ORIGIN + OTA_APP_LENGTH ||
        len > OTA_APP_ORIGIN + OTA_APP_LENGTH - address)
    {
        return -1;
    }
    offset = address - OTA_APP_ORIGIN;
    memcpy(dst, g_internal + offset, len);
    block = (int)(offset / TEST_BLOCK_SIZE);
    if (g_readback_armed && block == g_inject_readback_block &&
        (offset & (TEST_BLOCK_SIZE - 1u)) == 0u)
    {
        dst[0] ^= 0x01u;
        g_readback_armed = 0;
    }
    return 0;
}

static int internal_erase(void *ctx, uint32_t address)
{
    uint32_t offset;
    int block;

    (void)ctx;
    if (address < OTA_APP_ORIGIN ||
        address > OTA_APP_ORIGIN + OTA_APP_LENGTH - TEST_BLOCK_SIZE ||
        (address & (TEST_BLOCK_SIZE - 1u)) != 0u)
    {
        return -1;
    }
    offset = address - OTA_APP_ORIGIN;
    block = (int)(offset / TEST_BLOCK_SIZE);
    if (g_total_erases == 0)
    {
        g_first_erase_address = address;
    }
    ++g_total_erases;
    ++g_erase_count[block];
    if (block == g_fail_erase_block)
    {
        return -1;
    }
    memset(g_internal + offset, 0xFF, TEST_BLOCK_SIZE);
    return 0;
}

static int internal_program(void *ctx, uint32_t address,
                            const uint8_t *src, size_t len)
{
    uint32_t offset;
    int block;

    (void)ctx;
    if (src == NULL || len != TEST_BLOCK_SIZE || address < OTA_APP_ORIGIN ||
        len > OTA_APP_ORIGIN + OTA_APP_LENGTH - address)
    {
        return -1;
    }
    offset = address - OTA_APP_ORIGIN;
    block = (int)(offset / TEST_BLOCK_SIZE);
    if (block == g_fail_program_block)
    {
        return -1;
    }
    memcpy(g_internal + offset, src, len);
    if (block == g_inject_readback_block)
    {
        g_readback_armed = 1;
    }
    return 0;
}

static void clear_runtime_counters(void)
{
    memset(g_history, 0, sizeof(g_history));
    memset(g_erase_count, 0, sizeof(g_erase_count));
    g_history_count = 0;
    g_eeprom_write_calls = 0;
    g_fail_eeprom_write_call = 0;
    g_fail_eeprom_after_write = 0;
    g_total_erases = 0;
    g_first_erase_address = 0u;
    g_fail_erase_block = -1;
    g_fail_program_block = -1;
    g_inject_readback_block = -1;
    g_readback_armed = 0;
}

static void reset_model(void)
{
    memset(g_eeprom, 0xFF, sizeof(g_eeprom));
    memset(g_external, 0xFF, OTA_EXT_WINDOW_LENGTH);
    memset(g_internal, 0xFF, OTA_APP_LENGTH);
    clear_runtime_counters();
}

static void place_bcb(const bcb_t *bcb)
{
    uint8_t raw[BCB_SIZE];

    bcb_serialize(bcb, raw);
    memcpy(g_eeprom + BCB_A_ADDR, raw, sizeof(raw));
    memset(g_eeprom + BCB_B_ADDR, 0xFF, BCB_SIZE);
}

static void fill_upgrade_bcb(bcb_t *bcb, uint8_t state,
                             uint8_t boot_try, uint16_t resume_block)
{
    bcb_make_idle(bcb, 20700u);
    bcb->state = state;
    bcb->boot_try = boot_try;
    bcb->copy_phase = state == BCB_STATE_APPLYING
                          ? BCB_COPY_APPLY
                          : (state == BCB_STATE_ROLLBACK
                                 ? BCB_COPY_ROLLBACK
                                 : BCB_COPY_NONE);
    bcb->resume_block = resume_block;
    bcb->cand_addr = OTA_EXT_CANDIDATE + OTA_SLOT_HEADER_SIZE;
    bcb->cand_len = TEST_IMAGE_LEN;
    bcb->cand_crc32 = boot_crc32(g_candidate_image, TEST_IMAGE_LEN);
    bcb->cand_vcode = 20800u;
    bcb->backup_len = TEST_IMAGE_LEN;
    bcb->backup_crc32 = boot_crc32(g_current_image, TEST_IMAGE_LEN);
    bcb->backup_vcode = 20700u;
}

static void load_internal_image(const uint8_t image[TEST_IMAGE_LEN])
{
    memset(g_internal, 0xFF, OTA_APP_LENGTH);
    memcpy(g_internal, image, TEST_IMAGE_LEN);
}

static void prefill_blocks(const uint8_t image[TEST_IMAGE_LEN],
                           uint16_t block_count)
{
    uint16_t block;

    for (block = 0u; block < block_count; ++block)
    {
        uint32_t offset = (uint32_t)block * TEST_BLOCK_SIZE;
        size_t take = TEST_IMAGE_LEN - offset;
        if (take > TEST_BLOCK_SIZE)
        {
            take = TEST_BLOCK_SIZE;
        }
        memset(g_internal + offset, 0xFF, TEST_BLOCK_SIZE);
        memcpy(g_internal + offset, image + offset, take);
    }
}

static void prepare_upgrade(uint8_t state, uint8_t boot_try,
                            uint16_t resume_block)
{
    bcb_t bcb;

    reset_model();
    make_image(g_current_image, 20700u, 0x11u);
    make_image(g_candidate_image, 20800u, 0x22u);
    make_image(g_recovery_image, 20600u, 0x33u);
    install_slot(OTA_EXT_CANDIDATE, BOOT_SLOT_CANDIDATE, g_candidate_image);
    install_slot(OTA_EXT_BACKUP, BOOT_SLOT_BACKUP, g_current_image);
    install_slot(OTA_EXT_RECOVERY, BOOT_SLOT_RECOVERY, g_recovery_image);

    if (state == BCB_STATE_TEST_BOOT || state == BCB_STATE_ROLLBACK)
    {
        load_internal_image(g_candidate_image);
    }
    else
    {
        load_internal_image(g_current_image);
    }
    if (state == BCB_STATE_APPLYING)
    {
        prefill_blocks(g_candidate_image, resume_block);
    }
    if (state == BCB_STATE_ROLLBACK)
    {
        prefill_blocks(g_current_image, resume_block);
    }

    fill_upgrade_bcb(&bcb, state, boot_try, resume_block);
    place_bcb(&bcb);
    clear_runtime_counters();
}

static bcb_t active_bcb(void)
{
    bcb_t active;
    bcb_arbiter_result_t selected = bcb_arbiter(&g_bcb_hal, &active);
    if (selected != BCB_ARBITER_A && selected != BCB_ARBITER_B)
    {
        memset(&active, 0, sizeof(active));
        active.state = 0xFFu;
    }
    return active;
}

static boot_state_outcome_t run_state_machine(int external_available)
{
    boot_state_io_t io;
    boot_state_outcome_t outcome;

    memset(&io, 0, sizeof(io));
    io.bcb_hal = &g_bcb_hal;
    io.external_read = external_read;
    io.internal_read = internal_read;
    io.internal_erase_4k = internal_erase;
    io.internal_program = internal_program;
    io.external_available = external_available;
    (void)boot_state_machine_run(&io, &outcome);
    return outcome;
}

static uint32_t backup_slot_crc(void)
{
    return boot_crc32(g_external + OTA_EXT_BACKUP, OTA_EXT_SLOT_LENGTH);
}

static void test_blank_bootstrap(void)
{
    boot_state_outcome_t outcome;
    bcb_t active;

    printf("\n[blank BCB bootstrap]\n");
    reset_model();
    make_image(g_current_image, 20700u, 0x11u);
    load_internal_image(g_current_image);
    outcome = run_state_machine(0);
    active = active_bcb();
    check("blank BCB jumps only after internal fw_header validation",
          outcome.action == BOOT_STATE_ACTION_JUMP_APP);
    check("blank BCB is initialized as CONFIRMED",
          active.state == BCB_STATE_CONFIRMED);
    check("bootstrap cur_vcode comes from the validated fw_header",
          active.cur_vcode == 20700u);
    check("bootstrap performs no App erase", g_total_erases == 0);
}

static void test_idle_and_confirmed(void)
{
    bcb_t bcb;
    boot_state_outcome_t outcome;

    printf("\n[stable states]\n");
    reset_model();
    make_image(g_current_image, 20700u, 0x11u);
    load_internal_image(g_current_image);
    bcb_make_idle(&bcb, 20700u);
    place_bcb(&bcb);
    clear_runtime_counters();
    outcome = run_state_machine(0);
    check("legacy IDLE normalizes to CONFIRMED and jumps",
          outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
              active_bcb().state == BCB_STATE_CONFIRMED);

    clear_runtime_counters();
    outcome = run_state_machine(0);
    check("CONFIRMED validates and jumps without another BCB write",
          outcome.action == BOOT_STATE_ACTION_JUMP_APP && g_history_count == 0);
}

static void test_apply_and_confirm(void)
{
    boot_state_outcome_t outcome;
    bcb_t active;
    uint32_t backup_crc;
    int confirm_result;

    printf("\n[STAGED -> APPLYING -> TEST_BOOT -> CONFIRMED]\n");
    prepare_upgrade(BCB_STATE_STAGED, 0u, 0u);
    backup_crc = backup_slot_crc();
    outcome = run_state_machine(1);
    active = active_bcb();
    check("first persistent transition is atomic APPLYING/phase1/resume0",
          g_history_count >= 1 &&
              g_history[0].state == BCB_STATE_APPLYING &&
              g_history[0].copy_phase == BCB_COPY_APPLY &&
              g_history[0].resume_block == 0u);
    check("each verified apply block persists resume 1,2,3",
          g_history_count >= 4 &&
              g_history[1].resume_block == 1u &&
              g_history[2].resume_block == 2u &&
              g_history[3].resume_block == 3u);
    check("copy completion persists TEST_BOOT try=3 before consumption",
          g_history_count >= 5 &&
              g_history[4].state == BCB_STATE_TEST_BOOT &&
              g_history[4].boot_try == 3u);
    check("first test jump persists boot_try 3->2",
          outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
              active.state == BCB_STATE_TEST_BOOT && active.boot_try == 2u &&
              g_history_count >= 6 && g_history[5].boot_try == 2u);
    check("apply erased exactly three logical 4 KiB blocks",
          g_total_erases == TEST_BLOCK_COUNT &&
              g_erase_count[0] == 1 && g_erase_count[1] == 1 &&
              g_erase_count[2] == 1);
    check("internal image equals candidate after apply",
          memcmp(g_internal, g_candidate_image, TEST_IMAGE_LEN) == 0);
    check("backup slot stays byte-for-byte locked during apply",
          backup_slot_crc() == backup_crc);

    confirm_result = ota_confirm_test_boot(&g_bcb_hal, &active);
    check("App confirmation uses the shared TEST_BOOT helper",
          confirm_result == OTA_CONFIRM_COMMITTED);
    check("App confirmation persists CONFIRMED/candidate vcode",
          active.state == BCB_STATE_CONFIRMED &&
              active.cur_vcode == active.cand_vcode &&
              active.cur_vcode == 20800u);
    check("backup remains locked through App confirmation",
          backup_slot_crc() == backup_crc);
}

static void test_apply_resume_points(void)
{
    uint16_t resume;

    printf("\n[apply resume points]\n");
    for (resume = 0u; resume < TEST_BLOCK_COUNT; ++resume)
    {
        boot_state_outcome_t outcome;
        char name[96];

        prepare_upgrade(BCB_STATE_APPLYING, 0u, resume);
        outcome = run_state_machine(1);
        snprintf(name, sizeof(name),
                 "APPLYING resume=%u starts at its next unverified block",
                 (unsigned)resume);
        check(name, g_first_erase_address ==
                        OTA_APP_ORIGIN + (uint32_t)resume * TEST_BLOCK_SIZE);
        snprintf(name, sizeof(name),
                 "APPLYING resume=%u completes and consumes first try",
                 (unsigned)resume);
        check(name, outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
                        active_bcb().state == BCB_STATE_TEST_BOOT &&
                        active_bcb().boot_try == 2u);
    }
}

static void test_commit_boundaries(void)
{
    boot_state_outcome_t outcome;
    bcb_t active;

    printf("\n[persistent commit boundaries]\n");
    prepare_upgrade(BCB_STATE_STAGED, 0u, 0u);
    g_fail_eeprom_write_call = 1;
    outcome = run_state_machine(1);
    active = active_bcb();
    check("failed STAGED->APPLYING commit leaves STAGED active",
          outcome.action == BOOT_STATE_ACTION_HOLD &&
              active.state == BCB_STATE_STAGED);
    check("no App erase occurs before APPLYING is durable", g_total_erases == 0);
    g_fail_eeprom_write_call = 0;
    g_eeprom_write_calls = 0;
    outcome = run_state_machine(1);
    check("reset after failed first transition can complete",
          outcome.action == BOOT_STATE_ACTION_JUMP_APP);

    prepare_upgrade(BCB_STATE_APPLYING, 0u, 0u);
    g_fail_eeprom_write_call = 1;
    outcome = run_state_machine(1);
    active = active_bcb();
    check("readback-verified block without progress commit leaves resume=0",
          outcome.action == BOOT_STATE_ACTION_HOLD &&
              active.resume_block == 0u && g_erase_count[0] == 1);
    g_fail_eeprom_write_call = 0;
    g_eeprom_write_calls = 0;
    outcome = run_state_machine(1);
    check("reset repeats only the uncommitted block, not the whole App",
          outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
              g_erase_count[0] == 2 && g_erase_count[1] == 1 &&
              g_erase_count[2] == 1);

    prepare_upgrade(BCB_STATE_APPLYING, 0u, 0u);
    g_fail_eeprom_write_call = 1;
    g_fail_eeprom_after_write = 1;
    outcome = run_state_machine(1);
    active = active_bcb();
    check("commit-return failure after a valid write still advances arbitration",
          outcome.action == BOOT_STATE_ACTION_HOLD &&
              active.resume_block == 1u);
    g_fail_eeprom_write_call = 0;
    g_fail_eeprom_after_write = 0;
    g_eeprom_write_calls = 0;
    outcome = run_state_machine(1);
    check("reset honors the durable progress even when prior call returned error",
          outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
              g_erase_count[0] == 1 && g_erase_count[1] == 1);
}

static void test_all_apply_commit_boundaries(void)
{
    static const uint8_t expected_state[] = {
        BCB_STATE_STAGED,
        BCB_STATE_APPLYING,
        BCB_STATE_APPLYING,
        BCB_STATE_APPLYING,
        BCB_STATE_APPLYING,
        BCB_STATE_TEST_BOOT
    };
    static const uint8_t expected_try[] = { 0u, 0u, 0u, 0u, 0u, 3u };
    static const uint16_t expected_resume[] = { 0u, 0u, 1u, 2u, 3u, 0u };
    int boundary;

    printf("\n[all apply persistence boundaries]\n");
    for (boundary = 1; boundary <= 6; ++boundary)
    {
        boot_state_outcome_t outcome;
        bcb_t active;
        char name[96];

        prepare_upgrade(BCB_STATE_STAGED, 0u, 0u);
        g_fail_eeprom_write_call = boundary;
        outcome = run_state_machine(1);
        active = active_bcb();
        snprintf(name, sizeof(name),
                 "apply commit boundary %d fails without advancing state",
                 boundary);
        check(name, outcome.action == BOOT_STATE_ACTION_HOLD &&
                        outcome.status == BOOT_STATE_STATUS_COMMIT &&
                        active.state == expected_state[boundary - 1] &&
                        active.boot_try == expected_try[boundary - 1] &&
                        active.resume_block == expected_resume[boundary - 1]);

        g_fail_eeprom_write_call = 0;
        g_eeprom_write_calls = 0;
        outcome = run_state_machine(1);
        snprintf(name, sizeof(name),
                 "apply commit boundary %d resumes to first TEST_BOOT jump",
                 boundary);
        check(name, outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
                        active_bcb().state == BCB_STATE_TEST_BOOT &&
                        active_bcb().boot_try == 2u);
    }
}

static void test_all_rollback_commit_boundaries(void)
{
    static const uint8_t expected_state[] = {
        BCB_STATE_TEST_BOOT,
        BCB_STATE_ROLLBACK,
        BCB_STATE_ROLLBACK,
        BCB_STATE_ROLLBACK,
        BCB_STATE_ROLLBACK
    };
    static const uint16_t expected_resume[] = { 0u, 0u, 1u, 2u, 3u };
    int boundary;

    printf("\n[all rollback persistence boundaries]\n");
    for (boundary = 1; boundary <= 5; ++boundary)
    {
        boot_state_outcome_t outcome;
        bcb_t active;
        char name[104];

        prepare_upgrade(BCB_STATE_TEST_BOOT, 0u, 0u);
        g_fail_eeprom_write_call = boundary;
        outcome = run_state_machine(1);
        active = active_bcb();
        snprintf(name, sizeof(name),
                 "rollback commit boundary %d fails without skipping progress",
                 boundary);
        check(name, outcome.action == BOOT_STATE_ACTION_HOLD &&
                        outcome.status == BOOT_STATE_STATUS_COMMIT &&
                        active.state == expected_state[boundary - 1] &&
                        active.resume_block == expected_resume[boundary - 1] &&
                        (active.state != BCB_STATE_ROLLBACK ||
                         active.copy_phase == BCB_COPY_ROLLBACK));

        g_fail_eeprom_write_call = 0;
        g_eeprom_write_calls = 0;
        outcome = run_state_machine(1);
        snprintf(name, sizeof(name),
                 "rollback commit boundary %d resumes to CONFIRMED backup",
                 boundary);
        check(name, outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
                        active_bcb().state == BCB_STATE_CONFIRMED &&
                        active_bcb().cur_vcode == 20700u);
    }
}

static void test_transition_commit_failures(void)
{
    boot_state_outcome_t outcome;
    bcb_t bcb;
    bcb_t confirmed;
    int confirm_result;

    printf("\n[transition commit failures]\n");
    reset_model();
    make_image(g_current_image, 20700u, 0x11u);
    load_internal_image(g_current_image);
    g_fail_eeprom_write_call = 1;
    outcome = run_state_machine(0);
    check("blank-BCB bootstrap commit failure keeps both BCB blocks invalid",
          outcome.action == BOOT_STATE_ACTION_HOLD &&
              bcb_arbiter(&g_bcb_hal, NULL) == BCB_ARBITER_NONE);
    g_fail_eeprom_write_call = 0;
    g_eeprom_write_calls = 0;
    outcome = run_state_machine(0);
    check("blank-BCB bootstrap retries to validated CONFIRMED App",
          outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
              active_bcb().state == BCB_STATE_CONFIRMED);

    reset_model();
    make_image(g_current_image, 20700u, 0x11u);
    load_internal_image(g_current_image);
    bcb_make_idle(&bcb, 20700u);
    place_bcb(&bcb);
    clear_runtime_counters();
    g_fail_eeprom_write_call = 1;
    outcome = run_state_machine(0);
    check("IDLE->CONFIRMED commit failure leaves IDLE active",
          outcome.action == BOOT_STATE_ACTION_HOLD &&
              active_bcb().state == BCB_STATE_IDLE);
    g_fail_eeprom_write_call = 0;
    g_eeprom_write_calls = 0;
    outcome = run_state_machine(0);
    check("IDLE->CONFIRMED retry succeeds",
          outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
              active_bcb().state == BCB_STATE_CONFIRMED);

    prepare_upgrade(BCB_STATE_TEST_BOOT, 2u, 0u);
    g_fail_eeprom_write_call = 1;
    outcome = run_state_machine(1);
    check("TEST_BOOT decrement commit failure prevents the jump",
          outcome.action == BOOT_STATE_ACTION_HOLD &&
              active_bcb().state == BCB_STATE_TEST_BOOT &&
              active_bcb().boot_try == 2u);
    g_fail_eeprom_write_call = 0;
    g_eeprom_write_calls = 0;
    outcome = run_state_machine(1);
    check("TEST_BOOT decrement retry persists 2->1 before jump",
          outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
              active_bcb().boot_try == 1u);

    prepare_upgrade(BCB_STATE_TEST_BOOT, 2u, 0u);
    g_fail_eeprom_write_call = 1;
    confirm_result = ota_confirm_test_boot(&g_bcb_hal, &confirmed);
    check("App confirmation commit failure leaves TEST_BOOT active",
          confirm_result == OTA_CONFIRM_ERR_COMMIT &&
              active_bcb().state == BCB_STATE_TEST_BOOT);
    g_fail_eeprom_write_call = 0;
    g_eeprom_write_calls = 0;
    confirm_result = ota_confirm_test_boot(&g_bcb_hal, &confirmed);
    check("App confirmation retry commits candidate vcode",
          confirm_result == OTA_CONFIRM_COMMITTED &&
              confirmed.state == BCB_STATE_CONFIRMED &&
              confirmed.cur_vcode == 20800u);
}

static void test_readback_failure(void)
{
    boot_state_outcome_t outcome;
    bcb_t active;

    printf("\n[write-after-readback failure]\n");
    prepare_upgrade(BCB_STATE_APPLYING, 0u, 0u);
    g_inject_readback_block = 1;
    outcome = run_state_machine(1);
    active = active_bcb();
    check("full-block readback mismatch fails closed",
          outcome.action == BOOT_STATE_ACTION_HOLD &&
              outcome.status == BOOT_STATE_STATUS_COPY);
    check("readback failure never persists resume for the bad block",
          active.resume_block == 1u);
    g_inject_readback_block = -1;
    g_readback_armed = 0;
    outcome = run_state_machine(1);
    check("reset rewrites only the block whose readback failed",
          outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
              g_erase_count[0] == 1 && g_erase_count[1] == 2 &&
              g_erase_count[2] == 1);
}

static void test_flash_operation_failures(void)
{
    boot_state_outcome_t outcome;
    bcb_t active;

    printf("\n[erase/program failure re-entry]\n");
    prepare_upgrade(BCB_STATE_APPLYING, 0u, 1u);
    g_fail_erase_block = 1;
    outcome = run_state_machine(1);
    active = active_bcb();
    check("erase failure preserves the last verified resume block",
          outcome.action == BOOT_STATE_ACTION_HOLD &&
              outcome.status == BOOT_STATE_STATUS_COPY &&
              active.resume_block == 1u);
    g_fail_erase_block = -1;
    outcome = run_state_machine(1);
    check("reset retries the failed erase block without touching block zero",
          outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
              g_erase_count[0] == 0 && g_erase_count[1] == 2 &&
              g_erase_count[2] == 1);

    prepare_upgrade(BCB_STATE_APPLYING, 0u, 1u);
    g_fail_program_block = 1;
    outcome = run_state_machine(1);
    active = active_bcb();
    check("program failure preserves the last verified resume block",
          outcome.action == BOOT_STATE_ACTION_HOLD &&
              outcome.status == BOOT_STATE_STATUS_COPY &&
              active.resume_block == 1u);
    g_fail_program_block = -1;
    outcome = run_state_machine(1);
    check("reset erases and rewrites only the failed program block onward",
          outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
              g_erase_count[0] == 0 && g_erase_count[1] == 2 &&
              g_erase_count[2] == 1);
}

static void test_bad_candidate(void)
{
    boot_state_outcome_t outcome;
    bcb_t active;

    printf("\n[bad candidate]\n");
    prepare_upgrade(BCB_STATE_STAGED, 0u, 0u);
    g_external[OTA_EXT_CANDIDATE + OTA_SLOT_HEADER_SIZE + 0x700u] ^= 0x01u;
    outcome = run_state_machine(1);
    active = active_bcb();
    check("bad STAGED candidate enters atomic rollback before any apply",
          g_history_count >= 1 &&
              g_history[0].state == BCB_STATE_ROLLBACK &&
              g_history[0].copy_phase == BCB_COPY_ROLLBACK &&
              g_history[0].resume_block == 0u);
    check("bad candidate restores the validated backup and confirms it",
          outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
              active.state == BCB_STATE_CONFIRMED &&
              active.cur_vcode == 20700u &&
              memcmp(g_internal, g_current_image, TEST_IMAGE_LEN) == 0);
}

static void test_rollback_resume_points(void)
{
    uint16_t resume;

    printf("\n[rollback resume points]\n");
    for (resume = 0u; resume < TEST_BLOCK_COUNT; ++resume)
    {
        boot_state_outcome_t outcome;
        char name[96];

        prepare_upgrade(BCB_STATE_ROLLBACK, 0u, resume);
        outcome = run_state_machine(1);
        snprintf(name, sizeof(name),
                 "ROLLBACK resume=%u starts at its next unverified block",
                 (unsigned)resume);
        check(name, g_first_erase_address ==
                        OTA_APP_ORIGIN + (uint32_t)resume * TEST_BLOCK_SIZE);
        snprintf(name, sizeof(name),
                 "ROLLBACK resume=%u validates and confirms backup",
                 (unsigned)resume);
        check(name, outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
                        active_bcb().state == BCB_STATE_CONFIRMED &&
                        active_bcb().cur_vcode == 20700u);
    }
}

static void test_rollback_source_identity(void)
{
    boot_state_outcome_t outcome;

    printf("\n[rollback source identity]\n");
    prepare_upgrade(BCB_STATE_ROLLBACK, 0u, 1u);
    prefill_blocks(g_recovery_image, 1u);
    g_external[OTA_EXT_BACKUP + OTA_SLOT_HEADER_SIZE + 0x800u] ^= 0x01u;
    clear_runtime_counters();
    outcome = run_state_machine(1);
    check("recovery rollback resumes when persisted prefix matches recovery",
          outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
              g_first_erase_address == OTA_APP_ORIGIN + TEST_BLOCK_SIZE &&
              active_bcb().cur_vcode == 20600u &&
              memcmp(g_internal, g_recovery_image, TEST_IMAGE_LEN) == 0);

    prepare_upgrade(BCB_STATE_ROLLBACK, 0u, 1u);
    g_external[OTA_EXT_BACKUP + OTA_SLOT_HEADER_SIZE + 0x800u] ^= 0x01u;
    clear_runtime_counters();
    outcome = run_state_machine(1);
    check("backup-to-recovery switch atomically resets resume before copying",
          g_history_count >= 1 &&
              g_history[0].state == BCB_STATE_ROLLBACK &&
              g_history[0].copy_phase == BCB_COPY_ROLLBACK &&
              g_history[0].resume_block == 0u);
    check("source switch restarts at block zero and cannot create a mixed App",
          outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
              g_first_erase_address == OTA_APP_ORIGIN &&
              active_bcb().cur_vcode == 20600u &&
              memcmp(g_internal, g_recovery_image, TEST_IMAGE_LEN) == 0);

    prepare_upgrade(BCB_STATE_ROLLBACK, 0u, 1u);
    prefill_blocks(g_recovery_image, 1u);
    clear_runtime_counters();
    outcome = run_state_machine(1);
    check("a valid backup cannot steal an in-progress recovery prefix",
          outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
              g_first_erase_address == OTA_APP_ORIGIN + TEST_BLOCK_SIZE &&
              active_bcb().cur_vcode == 20600u &&
              memcmp(g_internal, g_recovery_image, TEST_IMAGE_LEN) == 0);
}

static void test_failure_driven_transitions(void)
{
    boot_state_outcome_t outcome;
    bcb_t bcb;

    printf("\n[failure-driven state transitions]\n");
    prepare_upgrade(BCB_STATE_CONFIRMED, 0u, 0u);
    g_internal[0x700u] ^= 0x01u;
    outcome = run_state_machine(1);
    check("invalid CONFIRMED App enters atomic rollback and restores backup",
          g_history_count >= 1 &&
              g_history[0].state == BCB_STATE_ROLLBACK &&
              g_history[0].copy_phase == BCB_COPY_ROLLBACK &&
              g_history[0].resume_block == 0u &&
              outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
              active_bcb().cur_vcode == 20700u);

    prepare_upgrade(BCB_STATE_TEST_BOOT, 2u, 0u);
    g_internal[0x700u] ^= 0x01u;
    outcome = run_state_machine(1);
    check("invalid TEST_BOOT App enters rollback without another test jump",
          g_history_count >= 1 &&
              g_history[0].state == BCB_STATE_ROLLBACK &&
              g_history[0].copy_phase == BCB_COPY_ROLLBACK &&
              outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
              active_bcb().cur_vcode == 20700u);

    prepare_upgrade(BCB_STATE_APPLYING, 0u, 1u);
    g_external[OTA_EXT_CANDIDATE + OTA_SLOT_HEADER_SIZE + 0x700u] ^= 0x01u;
    outcome = run_state_machine(1);
    check("invalid APPLYING candidate resets progress in atomic rollback",
          g_history_count >= 1 &&
              g_history[0].state == BCB_STATE_ROLLBACK &&
              g_history[0].copy_phase == BCB_COPY_ROLLBACK &&
              g_history[0].resume_block == 0u &&
              outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
              active_bcb().cur_vcode == 20700u);

    reset_model();
    make_image(g_current_image, 20700u, 0x11u);
    load_internal_image(g_current_image);
    bcb_make_idle(&bcb, 20700u);
    bcb.state = BCB_STATE_APPLYING;
    bcb.copy_phase = BCB_COPY_NONE;
    place_bcb(&bcb);
    clear_runtime_counters();
    outcome = run_state_machine(0);
    check("APPLYING with an invalid copy_phase fails closed through rollback",
          g_history_count >= 1 &&
              g_history[0].state == BCB_STATE_ROLLBACK &&
              g_history[0].copy_phase == BCB_COPY_ROLLBACK &&
              outcome.action == BOOT_STATE_ACTION_PHYSICAL_RECOVERY);
}

static void test_boot_try_exhaustion(void)
{
    boot_state_outcome_t outcome;
    bcb_t active;
    int expected;

    printf("\n[boot_try exhaustion]\n");
    prepare_upgrade(BCB_STATE_TEST_BOOT, 3u, 0u);
    for (expected = 2; expected >= 0; --expected)
    {
        outcome = run_state_machine(1);
        active = active_bcb();
        check(expected == 2 ? "first TEST_BOOT jump persists 3->2" :
              expected == 1 ? "second TEST_BOOT jump persists 2->1" :
                              "third TEST_BOOT jump persists 1->0",
              outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
                  active.state == BCB_STATE_TEST_BOOT &&
                  active.boot_try == (uint8_t)expected);
    }
    outcome = run_state_machine(1);
    active = active_bcb();
    check("fourth reset starts rollback with atomic phase2/resume0",
          g_history_count >= 4 &&
              g_history[3].state == BCB_STATE_ROLLBACK &&
              g_history[3].copy_phase == BCB_COPY_ROLLBACK &&
              g_history[3].resume_block == 0u);
    check("exhausted test boots restore and confirm backup",
          outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
              active.state == BCB_STATE_CONFIRMED &&
              active.cur_vcode == 20700u);
}

static void test_bad_backup_and_recovery(void)
{
    boot_state_outcome_t outcome;
    bcb_t active;

    printf("\n[backup/recovery fallback]\n");
    prepare_upgrade(BCB_STATE_TEST_BOOT, 0u, 0u);
    g_external[OTA_EXT_BACKUP + OTA_SLOT_HEADER_SIZE + 0x800u] ^= 0x01u;
    outcome = run_state_machine(1);
    active = active_bcb();
    check("invalid backup falls back to the validated recovery slot",
          outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
              active.state == BCB_STATE_CONFIRMED &&
              active.cur_vcode == 20600u &&
              memcmp(g_internal, g_recovery_image, TEST_IMAGE_LEN) == 0);

    prepare_upgrade(BCB_STATE_TEST_BOOT, 0u, 0u);
    g_external[OTA_EXT_BACKUP + OTA_SLOT_HEADER_SIZE + 0x800u] ^= 0x01u;
    g_external[OTA_EXT_RECOVERY + OTA_SLOT_HEADER_SIZE + 0x900u] ^= 0x01u;
    outcome = run_state_machine(1);
    check("invalid backup and recovery enter physical recovery mode",
          outcome.action == BOOT_STATE_ACTION_PHYSICAL_RECOVERY &&
              g_history_count >= 1 &&
              g_history[0].state == BCB_STATE_ROLLBACK &&
              g_history[0].copy_phase == BCB_COPY_ROLLBACK);
}

static void test_external_unavailable(void)
{
    boot_state_outcome_t outcome;
    bcb_t active;

    printf("\n[external Flash unavailable]\n");
    prepare_upgrade(BCB_STATE_STAGED, 0u, 0u);
    outcome = run_state_machine(0);
    active = active_bcb();
    check("STAGED with unavailable QSPI keeps the valid current App bootable",
          outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
              active.state == BCB_STATE_STAGED);
    check("unavailable QSPI does not erase internal Flash", g_total_erases == 0);
}

static void test_blank_bcb_recovery_slot(void)
{
    boot_state_outcome_t outcome;
    bcb_t active;

    printf("\n[blank BCB with damaged App]\n");
    reset_model();
    make_image(g_recovery_image, 20600u, 0x33u);
    install_slot(OTA_EXT_RECOVERY, BOOT_SLOT_RECOVERY, g_recovery_image);
    outcome = run_state_machine(1);
    active = active_bcb();
    check("blank BCB plus invalid App can enter resumable recovery copy",
          g_history_count >= 1 &&
              g_history[0].state == BCB_STATE_ROLLBACK &&
              g_history[0].copy_phase == BCB_COPY_ROLLBACK);
    check("recovery slot completion establishes CONFIRMED",
          outcome.action == BOOT_STATE_ACTION_JUMP_APP &&
              active.state == BCB_STATE_CONFIRMED &&
              active.cur_vcode == 20600u);
}

static void test_physical_recovery_acceptance(void)
{
    boot_state_io_t io;
    boot_state_outcome_t outcome;
    bcb_t active;

    printf("\n[physical recovery acceptance]\n");
    reset_model();
    make_image(g_recovery_image, 20600u, 0x33u);
    load_internal_image(g_recovery_image);
    memset(&io, 0, sizeof(io));
    io.bcb_hal = &g_bcb_hal;
    io.internal_read = internal_read;
    (void)boot_state_machine_accept_physical_recovery(&io, &outcome);
    active = active_bcb();
    check("validated physical recovery image creates a jump action",
          outcome.action == BOOT_STATE_ACTION_JUMP_APP);
    check("physical recovery resets BCB to CONFIRMED recovery vcode",
          active.state == BCB_STATE_CONFIRMED && active.cur_vcode == 20600u);
}

static void test_invalid_state(void)
{
    bcb_t bcb;
    boot_state_outcome_t outcome;

    printf("\n[invalid state]\n");
    reset_model();
    make_image(g_current_image, 20700u, 0x11u);
    load_internal_image(g_current_image);
    bcb_make_idle(&bcb, 20700u);
    bcb.state = 99u;
    place_bcb(&bcb);
    clear_runtime_counters();
    outcome = run_state_machine(0);
    check("unknown BCB state fails closed to physical recovery",
          outcome.action == BOOT_STATE_ACTION_PHYSICAL_RECOVERY);
}

int main(void)
{
    g_external = (uint8_t *)malloc(OTA_EXT_WINDOW_LENGTH);
    g_internal = (uint8_t *)malloc(OTA_APP_LENGTH);
    if (g_external == NULL || g_internal == NULL)
    {
        fprintf(stderr, "allocation failed\n");
        free(g_external);
        free(g_internal);
        return 2;
    }

    printf("=== P1-3 Boot state machine host simulation ===\n");
    test_blank_bootstrap();
    test_idle_and_confirmed();
    test_apply_and_confirm();
    test_apply_resume_points();
    test_commit_boundaries();
    test_all_apply_commit_boundaries();
    test_all_rollback_commit_boundaries();
    test_transition_commit_failures();
    test_readback_failure();
    test_flash_operation_failures();
    test_bad_candidate();
    test_rollback_resume_points();
    test_rollback_source_identity();
    test_failure_driven_transitions();
    test_boot_try_exhaustion();
    test_bad_backup_and_recovery();
    test_external_unavailable();
    test_blank_bcb_recovery_slot();
    test_physical_recovery_acceptance();
    test_invalid_state();

    printf("\nP1_3_STATE_MACHINE=%s checks=%d failures=%d\n",
           g_failures == 0 ? "PASS" : "FAIL", g_checks, g_failures);
    free(g_external);
    free(g_internal);
    return g_failures == 0 ? 0 : 1;
}
