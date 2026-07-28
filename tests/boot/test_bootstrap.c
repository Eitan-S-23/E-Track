#include "boot_bootstrap.h"
#include "boot_crypto.h"
#include "boot_slot.h"
#include "EEPROM/eeprom_bcb.h"
#include "OTA/ota_layout.h"

#include <stdio.h>
#include <string.h>

enum
{
    TEST_IMAGE_SIZE = 12288,
    TEST_EXTERNAL_SIZE = 0x300000,
    TEST_SECTOR_SIZE = 4096
};

typedef struct
{
    uint8_t eeprom[256];
    uint8_t internal[TEST_IMAGE_SIZE];
    uint8_t external[TEST_EXTERNAL_SIZE];
    uint32_t program_order;
    uint32_t header_order;
    uint32_t payload_last_order;
    uint32_t marker_order;
    uint32_t eeprom_read_calls;
    uint32_t eeprom_write_calls;
    uint32_t fail_eeprom_read_call;
    uint32_t fail_program_order;
    uint32_t corrupt_read_address;
    int corrupt_read_once;
    int external_init_fail;
} test_model_t;

static test_model_t g_model;
static unsigned g_checks;
static unsigned g_failures;

#define CHECK(condition, message)                                      \
    do                                                                 \
    {                                                                  \
        ++g_checks;                                                     \
        if (!(condition))                                              \
        {                                                              \
            ++g_failures;                                              \
            printf("FAIL: %s\n", message);                             \
        }                                                              \
    } while (0)

static uint32_t read_le32(const uint8_t *src)
{
    return (uint32_t)src[0] |
           ((uint32_t)src[1] << 8) |
           ((uint32_t)src[2] << 16) |
           ((uint32_t)src[3] << 24);
}

static void write_le32(uint8_t *dst, uint32_t value)
{
    dst[0] = (uint8_t)value;
    dst[1] = (uint8_t)(value >> 8);
    dst[2] = (uint8_t)(value >> 16);
    dst[3] = (uint8_t)(value >> 24);
}

static int all_value(const uint8_t *src, size_t len, uint8_t value)
{
    size_t index;

    for (index = 0u; index < len; ++index)
    {
        if (src[index] != value)
        {
            return 0;
        }
    }
    return 1;
}

static int eeprom_write(void *ctx, uint8_t address,
                        const uint8_t *src, uint16_t len)
{
    test_model_t *model = (test_model_t *)ctx;

    if (src == NULL || (uint16_t)address + len > sizeof(model->eeprom))
    {
        return -1;
    }
    ++model->eeprom_write_calls;
    memcpy(model->eeprom + address, src, len);
    return 0;
}

static int eeprom_read(void *ctx, uint8_t address,
                       uint8_t *dst, uint16_t len)
{
    test_model_t *model = (test_model_t *)ctx;

    if (dst == NULL || (uint16_t)address + len > sizeof(model->eeprom))
    {
        return -1;
    }
    ++model->eeprom_read_calls;
    if (model->eeprom_read_calls == model->fail_eeprom_read_call)
    {
        return -1;
    }
    memcpy(dst, model->eeprom + address, len);
    return 0;
}

static int bcb_write_adapter(uint8_t address,
                             const uint8_t *src, uint16_t len)
{
    return eeprom_write(&g_model, address, src, len);
}

static int bcb_read_adapter(uint8_t address, uint8_t *dst, uint16_t len)
{
    return eeprom_read(&g_model, address, dst, len);
}

static const bcb_hal_t g_bcb_hal = {
    bcb_write_adapter,
    bcb_read_adapter
};

static int internal_read(void *ctx, uint32_t address,
                         uint8_t *dst, size_t len)
{
    test_model_t *model = (test_model_t *)ctx;
    uint32_t offset;

    if (dst == NULL || address < OTA_APP_ORIGIN)
    {
        return -1;
    }
    offset = address - OTA_APP_ORIGIN;
    if (offset > sizeof(model->internal) ||
        len > sizeof(model->internal) - offset)
    {
        return -1;
    }
    memcpy(dst, model->internal + offset, len);
    return 0;
}

static int external_init(void *ctx)
{
    test_model_t *model = (test_model_t *)ctx;

    return model->external_init_fail ? -1 : 0;
}

static int external_erase(void *ctx, uint32_t address)
{
    test_model_t *model = (test_model_t *)ctx;

    if ((address & (TEST_SECTOR_SIZE - 1u)) != 0u ||
        address > sizeof(model->external) - TEST_SECTOR_SIZE)
    {
        return -1;
    }
    memset(model->external + address, 0xFF, TEST_SECTOR_SIZE);
    return 0;
}

static int external_program(void *ctx, uint32_t address,
                            const uint8_t *src, size_t len)
{
    test_model_t *model = (test_model_t *)ctx;
    size_t index;

    if (src == NULL || address > sizeof(model->external) ||
        len > sizeof(model->external) - address)
    {
        return -1;
    }
    ++model->program_order;
    if (model->program_order == model->fail_program_order)
    {
        return -1;
    }
    if ((address == OTA_EXT_CANDIDATE || address == OTA_EXT_BACKUP ||
         address == OTA_EXT_RECOVERY) && len == 28u)
    {
        model->header_order = model->program_order;
    }
    else if ((address == OTA_EXT_CANDIDATE + 28u ||
              address == OTA_EXT_BACKUP + 28u ||
              address == OTA_EXT_RECOVERY + 28u) && len == 4u)
    {
        model->marker_order = model->program_order;
    }
    else
    {
        model->payload_last_order = model->program_order;
    }
    for (index = 0u; index < len; ++index)
    {
        if ((model->external[address + index] & src[index]) != src[index])
        {
            return -1;
        }
        model->external[address + index] &= src[index];
    }
    return 0;
}

static int external_read(void *ctx, uint32_t address,
                         uint8_t *dst, size_t len)
{
    test_model_t *model = (test_model_t *)ctx;

    if (dst == NULL || address > sizeof(model->external) ||
        len > sizeof(model->external) - address)
    {
        return -1;
    }
    memcpy(dst, model->external + address, len);
    if (model->corrupt_read_once &&
        model->corrupt_read_address >= address &&
        model->corrupt_read_address - address < len)
    {
        dst[model->corrupt_read_address - address] ^= 0x01u;
        model->corrupt_read_once = 0;
    }
    return 0;
}

static const boot_bootstrap_io_t g_io = {
    eeprom_write,
    eeprom_read,
    internal_read,
    external_init,
    external_erase,
    external_program,
    external_read,
    &g_model
};

static void build_image(uint32_t version_code, const char *version_name)
{
    boot_sha256_ctx_t sha;
    uint8_t digest[32];
    uint8_t *header = g_model.internal + OTA_FW_HEADER_OFFSET;
    size_t name_len = strlen(version_name);
    uint32_t index;

    for (index = 0u; index < sizeof(g_model.internal); ++index)
    {
        g_model.internal[index] = (uint8_t)(index * 13u + version_code);
    }
    write_le32(g_model.internal, OTA_RAM_ORIGIN + 0x1000u);
    write_le32(g_model.internal + 4u, OTA_APP_ORIGIN + 0x101u);

    memset(header, 0xFF, OTA_FW_HEADER_SIZE);
    memcpy(header, "ETFW", 4u);
    write_le32(header + 4u, 1u);
    write_le32(header + 8u, version_code);
    memset(header + 12u, 0, 16u);
    if (name_len > 15u)
    {
        name_len = 15u;
    }
    memcpy(header + 12u, version_name, name_len);
    write_le32(header + 28u, 1785196800u);
    write_le32(header + 32u, 1u);
    write_le32(header + 36u, sizeof(g_model.internal));
    memset(header + 40u, 0, 32u);
    header[72] = 1u;
    header[73] = 1u;
    memset(header + 74u, 0xFF, 18u);
    memset(header + 92u, 0, 4u);

    boot_sha256_init(&sha);
    boot_sha256_update(&sha, g_model.internal, sizeof(g_model.internal));
    boot_sha256_final(&sha, digest);
    memcpy(header + 40u, digest, sizeof(digest));
    write_le32(header + 92u, boot_crc32(header, 92u));
}

static void command_write(uint32_t offset, uint32_t value)
{
    volatile uint8_t *bytes = g_boot_bootstrap_command.bytes;

    bytes[offset] = (uint8_t)value;
    bytes[offset + 1u] = (uint8_t)(value >> 8);
    bytes[offset + 2u] = (uint8_t)(value >> 16);
    bytes[offset + 3u] = (uint8_t)(value >> 24);
}

static uint32_t command_read(uint32_t offset)
{
    uint8_t raw[4];
    uint32_t index;

    for (index = 0u; index < sizeof(raw); ++index)
    {
        raw[index] = g_boot_bootstrap_command.bytes[offset + index];
    }
    return read_le32(raw);
}

static uint32_t command_crc(uint32_t offset, uint32_t len)
{
    uint8_t raw[BOOT_BOOTSTRAP_COMMAND_SIZE];
    uint32_t index;

    for (index = 0u; index < sizeof(raw); ++index)
    {
        raw[index] = g_boot_bootstrap_command.bytes[index];
    }
    return boot_crc32(raw + offset, len);
}

static void arm_command(uint32_t opcode, uint32_t arg0)
{
    memset((void *)g_boot_bootstrap_command.bytes, 0,
           sizeof(g_boot_bootstrap_command.bytes));
    command_write(BOOT_BOOTSTRAP_OFF_MAGIC,
                  BOOT_BOOTSTRAP_COMMAND_MAGIC);
    command_write(BOOT_BOOTSTRAP_OFF_VERSION,
                  BOOT_BOOTSTRAP_COMMAND_VERSION);
    command_write(BOOT_BOOTSTRAP_OFF_OPCODE, opcode);
    command_write(BOOT_BOOTSTRAP_OFF_OPCODE_INVERSE, ~opcode);
    command_write(BOOT_BOOTSTRAP_OFF_COOKIE,
                  BOOT_BOOTSTRAP_COMMAND_COOKIE);
    command_write(BOOT_BOOTSTRAP_OFF_COOKIE_INVERSE,
                  ~BOOT_BOOTSTRAP_COMMAND_COOKIE);
    command_write(BOOT_BOOTSTRAP_OFF_ARG0, arg0);
    command_write(BOOT_BOOTSTRAP_OFF_COMMAND_CRC32,
                  command_crc(0u, BOOT_BOOTSTRAP_COMMAND_CRC_LENGTH));
}

static void check_result(uint32_t status, uint32_t detail,
                         const char *label)
{
    CHECK(command_read(BOOT_BOOTSTRAP_OFF_MAGIC) ==
              BOOT_BOOTSTRAP_DONE_MAGIC,
          label);
    CHECK(command_read(BOOT_BOOTSTRAP_OFF_STATUS) == status, label);
    CHECK(command_read(BOOT_BOOTSTRAP_OFF_DETAIL) == detail, label);
    CHECK(command_read(BOOT_BOOTSTRAP_OFF_RESULT_CRC32) ==
              command_crc(BOOT_BOOTSTRAP_RESULT_CRC_OFFSET,
                          BOOT_BOOTSTRAP_RESULT_CRC_LENGTH),
          label);
}

static void reset_program_order(void)
{
    g_model.program_order = 0u;
    g_model.header_order = 0u;
    g_model.payload_last_order = 0u;
    g_model.marker_order = 0u;
    g_model.fail_program_order = 0u;
    g_model.corrupt_read_address = 0u;
    g_model.corrupt_read_once = 0;
}

static void reset_eeprom_faults(void)
{
    g_model.eeprom_read_calls = 0u;
    g_model.eeprom_write_calls = 0u;
    g_model.fail_eeprom_read_call = 0u;
}

static void initialize_confirmed(uint32_t version_code)
{
    bcb_t bcb;

    bcb_make_idle(&bcb, version_code);
    bcb.state = BCB_STATE_CONFIRMED;
    CHECK(bcb_commit(&g_bcb_hal, BCB_ARBITER_NONE, &bcb) == BCB_COMMIT_OK,
          "initialize confirmed BCB");
}

static void check_marker_last(const char *label)
{
    CHECK(g_model.header_order > g_model.payload_last_order, label);
    CHECK(g_model.marker_order > g_model.header_order, label);
}

int main(void)
{
    bcb_t bcb;
    bcb_arbiter_result_t active;
    boot_slot_header_t slot;
    uint8_t raw_header[BOOT_SLOT_HEADER_SIZE];
    uint8_t backup_before[64];

    memset(&g_model, 0xFF, sizeof(g_model));
    memset((void *)&g_boot_bootstrap_command, 0,
           sizeof(g_boot_bootstrap_command));
    build_image(20700u, "2.7.0");

    CHECK(boot_bootstrap_process(&g_io) == BOOT_BOOTSTRAP_NO_REQUEST,
          "blank command is ignored");
    CHECK(command_read(BOOT_BOOTSTRAP_OFF_MAGIC) == 0u,
          "blank command remains untouched");

    arm_command(BOOT_BOOTSTRAP_OPCODE_CLEAR_BCB, 0u);
    command_write(BOOT_BOOTSTRAP_OFF_OPCODE_INVERSE,
                  ~BOOT_BOOTSTRAP_OPCODE_CLEAR_BCB ^ 1u);
    command_write(BOOT_BOOTSTRAP_OFF_COMMAND_CRC32,
                  command_crc(0u, BOOT_BOOTSTRAP_COMMAND_CRC_LENGTH));
    CHECK(boot_bootstrap_process(&g_io) == BOOT_BOOTSTRAP_HOLD,
          "bad opcode inverse is consumed");
    check_result(BOOT_BOOTSTRAP_STATUS_FAIL,
                 BOOT_BOOTSTRAP_DETAIL_COMMAND,
                 "bad opcode inverse rejected");

    arm_command(BOOT_BOOTSTRAP_OPCODE_CLEAR_BCB, 0u);
    command_write(BOOT_BOOTSTRAP_OFF_COMMAND_CRC32, 0u);
    CHECK(boot_bootstrap_process(&g_io) == BOOT_BOOTSTRAP_HOLD,
          "bad command is consumed");
    check_result(BOOT_BOOTSTRAP_STATUS_FAIL,
                 BOOT_BOOTSTRAP_DETAIL_COMMAND,
                 "bad command CRC rejected");

    memset(g_model.eeprom + BCB_A_ADDR, 0xA5, BCB_SIZE);
    memset(g_model.eeprom + BCB_B_ADDR, 0x5A, BCB_SIZE);
    g_model.internal[OTA_FW_HEADER_OFFSET] ^= 0x01u;
    arm_command(BOOT_BOOTSTRAP_OPCODE_CLEAR_BCB, 0u);
    CHECK(boot_bootstrap_process(&g_io) == BOOT_BOOTSTRAP_HOLD,
          "invalid App clear command holds");
    check_result(BOOT_BOOTSTRAP_STATUS_FAIL,
                 BOOT_BOOTSTRAP_DETAIL_APP_INVALID,
                 "invalid App blocks BCB clear");
    CHECK(g_model.eeprom[BCB_A_ADDR] == 0xA5u &&
              g_model.eeprom[BCB_B_ADDR] == 0x5Au,
          "invalid App leaves both BCB records untouched");
    build_image(20700u, "2.7.0");

    reset_eeprom_faults();
    g_model.fail_eeprom_read_call = 1u;
    arm_command(BOOT_BOOTSTRAP_OPCODE_CLEAR_BCB, 0u);
    CHECK(boot_bootstrap_process(&g_io) == BOOT_BOOTSTRAP_HOLD,
          "BCB readback failure command holds");
    check_result(BOOT_BOOTSTRAP_STATUS_FAIL,
                 BOOT_BOOTSTRAP_DETAIL_EEPROM,
                 "BCB readback failure is reported");
    CHECK(!all_value(g_model.eeprom + BCB_B_ADDR, BCB_SIZE, 0xFFu),
          "BCB clear stops before the second record after readback failure");

    reset_eeprom_faults();
    arm_command(BOOT_BOOTSTRAP_OPCODE_CLEAR_BCB, 0u);
    CHECK(boot_bootstrap_process(&g_io) == BOOT_BOOTSTRAP_HOLD,
          "clear BCB command holds");
    check_result(BOOT_BOOTSTRAP_STATUS_PASS,
                 BOOT_BOOTSTRAP_DETAIL_NONE,
                 "clear BCB result");
    CHECK(bcb_arbiter(&g_bcb_hal, NULL) == BCB_ARBITER_NONE,
          "both BCB records are blank");
    CHECK(all_value(g_model.eeprom + BCB_A_ADDR, BCB_SIZE, 0xFFu) &&
              all_value(g_model.eeprom + BCB_B_ADDR, BCB_SIZE, 0xFFu),
          "clear command erases both complete BCB records");
    CHECK(g_model.eeprom_write_calls == 2u &&
              g_model.eeprom_read_calls >= 4u,
          "clear command writes and reads back both BCB records");

    initialize_confirmed(20700u);

    g_model.external_init_fail = 1;
    arm_command(BOOT_BOOTSTRAP_OPCODE_INSTALL_SLOT,
                BOOT_BOOTSTRAP_SLOT_RECOVERY);
    CHECK(boot_bootstrap_process(&g_io) == BOOT_BOOTSTRAP_HOLD,
          "QSPI init failure command holds");
    check_result(BOOT_BOOTSTRAP_STATUS_FAIL,
                 BOOT_BOOTSTRAP_DETAIL_QSPI_INIT,
                 "QSPI init failure is reported");
    g_model.external_init_fail = 0;

    reset_program_order();
    g_model.fail_program_order = 1u;
    arm_command(BOOT_BOOTSTRAP_OPCODE_INSTALL_SLOT,
                BOOT_BOOTSTRAP_SLOT_RECOVERY);
    CHECK(boot_bootstrap_process(&g_io) == BOOT_BOOTSTRAP_HOLD,
          "payload program failure command holds");
    check_result(BOOT_BOOTSTRAP_STATUS_FAIL,
                 BOOT_BOOTSTRAP_DETAIL_SLOT_PROGRAM,
                 "payload program failure is reported");
    CHECK(all_value(g_model.external + OTA_EXT_RECOVERY + 28u, 4u, 0xFFu),
          "payload program failure leaves recovery marker erased");

    reset_program_order();
    g_model.corrupt_read_address = OTA_EXT_RECOVERY + OTA_SLOT_HEADER_SIZE;
    g_model.corrupt_read_once = 1;
    arm_command(BOOT_BOOTSTRAP_OPCODE_INSTALL_SLOT,
                BOOT_BOOTSTRAP_SLOT_RECOVERY);
    CHECK(boot_bootstrap_process(&g_io) == BOOT_BOOTSTRAP_HOLD,
          "payload readback failure command holds");
    check_result(BOOT_BOOTSTRAP_STATUS_FAIL,
                 BOOT_BOOTSTRAP_DETAIL_SLOT_VERIFY,
                 "payload readback failure is reported");
    CHECK(all_value(g_model.external + OTA_EXT_RECOVERY + 28u, 4u, 0xFFu),
          "payload readback failure leaves recovery marker erased");

    reset_program_order();
    g_model.fail_program_order = 5u;
    arm_command(BOOT_BOOTSTRAP_OPCODE_INSTALL_SLOT,
                BOOT_BOOTSTRAP_SLOT_RECOVERY);
    CHECK(boot_bootstrap_process(&g_io) == BOOT_BOOTSTRAP_HOLD,
          "marker program failure command holds");
    check_result(BOOT_BOOTSTRAP_STATUS_FAIL,
                 BOOT_BOOTSTRAP_DETAIL_SLOT_HEADER,
                 "marker program failure is reported");
    CHECK(all_value(g_model.external + OTA_EXT_RECOVERY + 28u, 4u, 0xFFu),
          "marker program failure leaves recovery marker erased");

    reset_program_order();
    arm_command(BOOT_BOOTSTRAP_OPCODE_INSTALL_SLOT,
                BOOT_BOOTSTRAP_SLOT_RECOVERY);
    CHECK(boot_bootstrap_process(&g_io) == BOOT_BOOTSTRAP_HOLD,
          "install recovery holds");
    check_result(BOOT_BOOTSTRAP_STATUS_PASS,
                 BOOT_BOOTSTRAP_DETAIL_NONE,
                 "install recovery result");
    check_marker_last("recovery marker last");
    CHECK(memcmp(g_model.external + OTA_EXT_RECOVERY + OTA_SLOT_HEADER_SIZE,
                 g_model.internal, sizeof(g_model.internal)) == 0,
          "recovery payload matches the validated internal App");
    memcpy(raw_header, g_model.external + OTA_EXT_RECOVERY,
           sizeof(raw_header));
    CHECK(boot_slot_header_parse(raw_header, BOOT_SLOT_RECOVERY, &slot) ==
              BOOT_SLOT_OK,
          "recovery ETSL header parses after marker-last commit");
    CHECK(slot.payload_len == sizeof(g_model.internal) &&
              slot.payload_crc32 == boot_crc32(g_model.internal,
                                               sizeof(g_model.internal)) &&
              slot.version_code == 20700u,
          "recovery ETSL metadata matches the App");
    CHECK(all_value(g_model.external + OTA_EXT_RECOVERY +
                        BOOT_SLOT_HEADER_SIZE,
                    OTA_SLOT_HEADER_SIZE - BOOT_SLOT_HEADER_SIZE, 0xFFu),
          "recovery header sector gap remains erased");

    reset_program_order();
    arm_command(BOOT_BOOTSTRAP_OPCODE_INSTALL_SLOT,
                BOOT_BOOTSTRAP_SLOT_BACKUP);
    CHECK(boot_bootstrap_process(&g_io) == BOOT_BOOTSTRAP_HOLD,
          "install backup holds");
    check_result(BOOT_BOOTSTRAP_STATUS_PASS,
                 BOOT_BOOTSTRAP_DETAIL_NONE,
                 "install backup result");
    check_marker_last("backup marker last");

    build_image(20701u, "2.7.1");
    reset_program_order();
    arm_command(BOOT_BOOTSTRAP_OPCODE_INSTALL_SLOT,
                BOOT_BOOTSTRAP_SLOT_CANDIDATE);
    CHECK(boot_bootstrap_process(&g_io) == BOOT_BOOTSTRAP_HOLD,
          "install candidate holds");
    check_result(BOOT_BOOTSTRAP_STATUS_PASS,
                 BOOT_BOOTSTRAP_DETAIL_NONE,
                 "install candidate result");
    check_marker_last("candidate marker last");

    build_image(20700u, "2.7.0");
    arm_command(BOOT_BOOTSTRAP_OPCODE_STAGE_SLOTS, 0u);
    CHECK(boot_bootstrap_process(&g_io) == BOOT_BOOTSTRAP_HOLD,
          "stage slots holds");
    check_result(BOOT_BOOTSTRAP_STATUS_PASS,
                 BOOT_BOOTSTRAP_DETAIL_NONE,
                 "stage slots result");
    active = bcb_arbiter(&g_bcb_hal, &bcb);
    CHECK(active == BCB_ARBITER_A || active == BCB_ARBITER_B,
          "staged BCB remains valid");
    CHECK(bcb.state == BCB_STATE_STAGED &&
              bcb.copy_phase == BCB_COPY_NONE && bcb.resume_block == 0u,
          "staged transition is atomic");
    CHECK(bcb.cur_vcode == 20700u && bcb.cand_vcode == 20701u &&
              bcb.backup_vcode == 20700u,
          "staged metadata matches slots");

    memcpy(backup_before, g_model.external + OTA_EXT_BACKUP,
           sizeof(backup_before));
    arm_command(BOOT_BOOTSTRAP_OPCODE_INSTALL_SLOT,
                BOOT_BOOTSTRAP_SLOT_BACKUP);
    CHECK(boot_bootstrap_process(&g_io) == BOOT_BOOTSTRAP_HOLD,
          "locked backup command holds");
    check_result(BOOT_BOOTSTRAP_STATUS_FAIL,
                 BOOT_BOOTSTRAP_DETAIL_BCB_LOCKED,
                 "backup rewrite locked while staged");
    CHECK(memcmp(backup_before, g_model.external + OTA_EXT_BACKUP,
                 sizeof(backup_before)) == 0,
          "locked backup remains byte-for-byte unchanged");

    arm_command(BOOT_BOOTSTRAP_OPCODE_SNAPSHOT_BCB, 0u);
    CHECK(boot_bootstrap_process(&g_io) == BOOT_BOOTSTRAP_HOLD,
          "snapshot command holds");
    check_result(BOOT_BOOTSTRAP_STATUS_PASS,
                 BOOT_BOOTSTRAP_DETAIL_NONE,
                 "snapshot result");
    CHECK(command_read(BOOT_BOOTSTRAP_OFF_STATE) == BCB_STATE_STAGED &&
              command_read(BOOT_BOOTSTRAP_OFF_CUR_VCODE) == 20700u &&
              command_read(BOOT_BOOTSTRAP_OFF_CAND_VCODE) == 20701u,
          "snapshot publishes active BCB");

    printf("P1_5_BOOTSTRAP=PASS checks=%u failures=%u\n",
           g_checks, g_failures);
    return g_failures == 0u ? 0 : 1;
}
