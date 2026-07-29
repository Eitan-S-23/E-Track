#include "boot_p1_6_test.h"

#include "boot_crypto.h"
#include "boot_fw_header.h"
#include "boot_platform.h"
#include "boot_slot.h"
#include "EEPROM/eeprom_bcb.h"
#include "OTA/ota_layout.h"
#include "OTA/ota_p1_6_test.h"

#include <string.h>

#if !defined(P1_6_TEST_ENABLE) || !defined(OTA_TARGET_BOOT)
#error "P1-6 evidence source is only valid for the test-enabled Boot target"
#endif

enum
{
    P1_6_BLOCK_SIZE = 4096,
    P1_6_VERIFY_CHUNK = 256,
    P1_6_SLOT_COMMIT_MARKER = 0x434F4D54u
};

typedef struct
{
    uint32_t base;
    uint32_t length;
} p1_6_reader_context_t;

typedef struct
{
    boot_slot_header_t slot;
    boot_fw_header_t header;
    uint32_t slot_base;
} p1_6_validated_slot_t;

static uint8_t g_p1_6_block[P1_6_BLOCK_SIZE];
static uint8_t g_p1_6_verify[P1_6_VERIFY_CHUNK];

static int snapshot_app(void);

static void write_le32(uint8_t *dst, uint32_t value)
{
    dst[0] = (uint8_t)value;
    dst[1] = (uint8_t)(value >> 8);
    dst[2] = (uint8_t)(value >> 16);
    dst[3] = (uint8_t)(value >> 24);
}

static uint32_t read_le32(const uint8_t *src)
{
    return (uint32_t)src[0] |
           ((uint32_t)src[1] << 8) |
           ((uint32_t)src[2] << 16) |
           ((uint32_t)src[3] << 24);
}

static uint32_t control_crc(uint32_t offset, uint32_t length)
{
    boot_crc32_ctx_t crc;
    uint8_t chunk[32];

    boot_crc32_init(&crc);
    while (length != 0u)
    {
        uint32_t index;
        uint32_t take = length < sizeof(chunk) ? length : sizeof(chunk);

        for (index = 0u; index < take; ++index)
        {
            chunk[index] = ota_p1_6_control()[offset + index];
        }
        boot_crc32_update(&crc, chunk, take);
        offset += take;
        length -= take;
    }
    return boot_crc32_final(&crc);
}

static void control_copy_out(uint32_t offset, const uint8_t *src, size_t len)
{
    size_t index;

    for (index = 0u; index < len; ++index)
    {
        ota_p1_6_control()[offset + index] = src[index];
    }
}

static void result_reset(void)
{
    uint32_t offset;

    for (offset = OTA_P1_6_OFF_STATUS;
         offset <= OTA_P1_6_OFF_RESULT_CRC32;
         offset += sizeof(uint32_t))
    {
        ota_p1_6_write_u32(offset, 0u);
    }
    ota_p1_6_write_u32(OTA_P1_6_OFF_STATUS, OTA_P1_6_STATUS_RUNNING);
    ota_p1_6_write_u32(OTA_P1_6_OFF_ACTIVE, (uint32_t)BCB_ARBITER_ERROR);
    ota_p1_6_write_u32(OTA_P1_6_OFF_STATE, UINT32_MAX);
    ota_p1_6_write_u32(OTA_P1_6_OFF_BOOT_TRY, UINT32_MAX);
    ota_p1_6_write_u32(OTA_P1_6_OFF_COPY_PHASE, UINT32_MAX);
    ota_p1_6_write_u32(OTA_P1_6_OFF_RESUME_BLOCK, UINT32_MAX);
    ota_p1_6_write_u32(OTA_P1_6_OFF_SEQ, UINT32_MAX);
    ota_p1_6_write_u32(OTA_P1_6_OFF_CUR_VCODE, UINT32_MAX);
    ota_p1_6_write_u32(OTA_P1_6_OFF_CAND_VCODE, UINT32_MAX);
    ota_p1_6_write_u32(OTA_P1_6_OFF_BACKUP_VCODE, UINT32_MAX);
}

static int bcb_write(uint8_t address, const uint8_t *src, uint16_t len)
{
    return boot_platform_eeprom_write(address, src, len);
}

static int bcb_read(uint8_t address, uint8_t *dst, uint16_t len)
{
    return boot_platform_eeprom_read(address, dst, len);
}

static const bcb_hal_t g_p1_6_bcb_hal = {bcb_write, bcb_read};

static int internal_reader(void *ctx, uint32_t offset,
                           uint8_t *dst, size_t len)
{
    (void)ctx;
    if (offset > OTA_APP_LENGTH || len > OTA_APP_LENGTH - offset)
    {
        return -1;
    }
    return boot_platform_flash_read(OTA_APP_ORIGIN + offset, dst, len);
}

static int slot_reader(void *ctx, uint32_t offset,
                       uint8_t *dst, size_t len)
{
    const p1_6_reader_context_t *reader =
        (const p1_6_reader_context_t *)ctx;

    if (reader == NULL || offset > reader->length ||
        len > reader->length - offset)
    {
        return -1;
    }
    return boot_platform_qspi_read(reader->base + offset, dst, len);
}

static boot_fw_result_t validate_internal_app(boot_fw_header_t *header)
{
    boot_image_reader_t reader;
    boot_fw_expectations_t expected;

    reader.read = internal_reader;
    reader.ctx = NULL;
    boot_fw_default_expectations(&expected);
    return boot_fw_header_validate(&reader, &expected, header);
}

static uint32_t slot_base(uint32_t type)
{
    if (type == OTA_P1_6_SLOT_CANDIDATE)
    {
        return OTA_EXT_CANDIDATE;
    }
    if (type == OTA_P1_6_SLOT_BACKUP)
    {
        return OTA_EXT_BACKUP;
    }
    return OTA_EXT_RECOVERY;
}

static int slot_type_valid(uint32_t type)
{
    return type == OTA_P1_6_SLOT_CANDIDATE ||
           type == OTA_P1_6_SLOT_BACKUP ||
           type == OTA_P1_6_SLOT_RECOVERY;
}

static int verify_external(uint32_t address,
                           const uint8_t *expected,
                           size_t len)
{
    size_t offset = 0u;

    while (offset < len)
    {
        size_t take = len - offset;

        if (take > sizeof(g_p1_6_verify))
        {
            take = sizeof(g_p1_6_verify);
        }
        if (boot_platform_qspi_read(address + (uint32_t)offset,
                                    g_p1_6_verify, take) != 0 ||
            memcmp(g_p1_6_verify, expected + offset, take) != 0)
        {
            return -1;
        }
        offset += take;
    }
    return 0;
}

static int verify_external_crc(uint32_t address,
                               uint32_t length,
                               uint32_t expected_crc)
{
    boot_crc32_ctx_t crc;
    uint32_t offset = 0u;

    boot_crc32_init(&crc);
    while (offset < length)
    {
        size_t take = length - offset;

        if (take > sizeof(g_p1_6_verify))
        {
            take = sizeof(g_p1_6_verify);
        }
        if (boot_platform_qspi_read(address + offset,
                                    g_p1_6_verify, take) != 0)
        {
            return -1;
        }
        boot_crc32_update(&crc, g_p1_6_verify, take);
        offset += (uint32_t)take;
    }
    return boot_crc32_final(&crc) == expected_crc ? 0 : -1;
}

static int validate_slot(uint32_t type, p1_6_validated_slot_t *validated)
{
    boot_image_reader_t reader;
    boot_fw_expectations_t expected;
    p1_6_reader_context_t context;
    uint8_t raw[BOOT_SLOT_HEADER_SIZE];

    if (!slot_type_valid(type) || validated == NULL)
    {
        return -1;
    }
    memset(validated, 0, sizeof(*validated));
    validated->slot_base = slot_base(type);
    if (boot_platform_qspi_read(validated->slot_base,
                                raw, sizeof(raw)) != 0 ||
        boot_slot_header_parse(raw, (boot_slot_type_t)type,
                               &validated->slot) != BOOT_SLOT_OK ||
        verify_external_crc(validated->slot_base + OTA_SLOT_HEADER_SIZE,
                            validated->slot.payload_len,
                            validated->slot.payload_crc32) != 0)
    {
        return -1;
    }

    context.base = validated->slot_base + OTA_SLOT_HEADER_SIZE;
    context.length = validated->slot.payload_len;
    reader.read = slot_reader;
    reader.ctx = &context;
    boot_fw_default_expectations(&expected);
    if (boot_fw_header_validate(&reader, &expected,
                                &validated->header) != BOOT_FW_OK ||
        validated->header.image_len != validated->slot.payload_len ||
        validated->header.version_code != validated->slot.version_code ||
        memcmp(validated->header.image_sha256, validated->slot.sha8,
               sizeof(validated->slot.sha8)) != 0)
    {
        return -1;
    }
    return 0;
}

static int snapshot_bcb(void)
{
    uint8_t raw_a[BCB_SIZE];
    uint8_t raw_b[BCB_SIZE];
    bcb_t current;
    bcb_arbiter_result_t active;
    int read_a;
    int read_b;

    memset(raw_a, 0xFF, sizeof(raw_a));
    memset(raw_b, 0xFF, sizeof(raw_b));
    read_a = boot_platform_eeprom_read(BCB_A_ADDR, raw_a, sizeof(raw_a));
    read_b = boot_platform_eeprom_read(BCB_B_ADDR, raw_b, sizeof(raw_b));
    if (read_a == 0)
    {
        control_copy_out(OTA_P1_6_OFF_BCB_A_RAW, raw_a, sizeof(raw_a));
    }
    if (read_b == 0)
    {
        control_copy_out(OTA_P1_6_OFF_BCB_B_RAW, raw_b, sizeof(raw_b));
    }
    if (read_a != 0 || read_b != 0)
    {
        ota_p1_6_write_u32(OTA_P1_6_OFF_ACTIVE,
                           (uint32_t)BCB_ARBITER_ERROR);
        return -1;
    }

    active = bcb_arbiter(&g_p1_6_bcb_hal, &current);
    ota_p1_6_write_u32(OTA_P1_6_OFF_ACTIVE, (uint32_t)active);
    if (active == BCB_ARBITER_ERROR)
    {
        return -1;
    }
    if (active == BCB_ARBITER_NONE)
    {
        return 0;
    }
    ota_p1_6_write_u32(OTA_P1_6_OFF_STATE, current.state);
    ota_p1_6_write_u32(OTA_P1_6_OFF_BOOT_TRY, current.boot_try);
    ota_p1_6_write_u32(OTA_P1_6_OFF_COPY_PHASE, current.copy_phase);
    ota_p1_6_write_u32(OTA_P1_6_OFF_RESUME_BLOCK, current.resume_block);
    ota_p1_6_write_u32(OTA_P1_6_OFF_SEQ, current.seq);
    ota_p1_6_write_u32(OTA_P1_6_OFF_CUR_VCODE, current.cur_vcode);
    ota_p1_6_write_u32(OTA_P1_6_OFF_CAND_VCODE, current.cand_vcode);
    ota_p1_6_write_u32(OTA_P1_6_OFF_BACKUP_VCODE, current.backup_vcode);
    return 0;
}

void boot_p1_6_capture_checkpoint_state(void)
{
    (void)snapshot_bcb();
    (void)snapshot_app();
}

static int snapshot_app(void)
{
    boot_fw_header_t header;
    uint8_t raw_crc[4];

    if (validate_internal_app(&header) != BOOT_FW_OK)
    {
        ota_p1_6_write_u32(OTA_P1_6_OFF_APP_RESULT,
                           OTA_P1_6_APP_RESULT_INVALID);
        return -1;
    }
    ota_p1_6_write_u32(OTA_P1_6_OFF_APP_RESULT,
                       OTA_P1_6_APP_RESULT_VALID);
    ota_p1_6_write_u32(OTA_P1_6_OFF_APP_VCODE, header.version_code);
    ota_p1_6_write_u32(OTA_P1_6_OFF_APP_LEN, header.image_len);
    if (boot_platform_flash_read(OTA_APP_ORIGIN + OTA_FW_HEADER_OFFSET + 92u,
                                 raw_crc, sizeof(raw_crc)) == 0)
    {
        ota_p1_6_write_u32(OTA_P1_6_OFF_APP_HEADER_CRC32,
                           read_le32(raw_crc));
    }
    else
    {
        return -1;
    }
    control_copy_out(OTA_P1_6_OFF_APP_SHA256,
                     header.image_sha256, sizeof(header.image_sha256));
    return 0;
}

static int snapshot_slot(uint32_t type)
{
    p1_6_validated_slot_t validated;
    uint8_t raw[BOOT_SLOT_HEADER_SIZE];

    if (!slot_type_valid(type) ||
        boot_platform_qspi_read(slot_base(type), raw, sizeof(raw)) != 0)
    {
        return -1;
    }
    ota_p1_6_write_u32(OTA_P1_6_OFF_SLOT_TYPE, type);
    control_copy_out(OTA_P1_6_OFF_SLOT_HEADER_RAW, raw, sizeof(raw));
    if (validate_slot(type, &validated) != 0)
    {
        return -1;
    }
    ota_p1_6_write_u32(OTA_P1_6_OFF_SLOT_VCODE,
                       validated.slot.version_code);
    ota_p1_6_write_u32(OTA_P1_6_OFF_SLOT_LEN,
                       validated.slot.payload_len);
    ota_p1_6_write_u32(OTA_P1_6_OFF_SLOT_CRC32,
                       validated.slot.payload_crc32);
    control_copy_out(OTA_P1_6_OFF_SLOT_SHA8,
                     validated.slot.sha8, sizeof(validated.slot.sha8));
    return 0;
}

static void result_finish(uint32_t status, uint32_t detail, int bcb_only)
{
    int bcb_result = snapshot_bcb();
    int app_result = snapshot_app();

    if ((bcb_result != 0 || (app_result != 0 && !bcb_only)) &&
        status == OTA_P1_6_STATUS_PASS)
    {
        status = OTA_P1_6_STATUS_FAIL;
        detail = OTA_P1_6_DETAIL_SNAPSHOT;
    }
    ota_p1_6_write_u32(OTA_P1_6_OFF_DETAIL, detail);
    ota_p1_6_write_u32(OTA_P1_6_OFF_STATUS, status);
    ota_p1_6_write_u32(
        OTA_P1_6_OFF_RESULT_CRC32,
        control_crc(OTA_P1_6_RESULT_CRC_OFFSET,
                    OTA_P1_6_RESULT_CRC_LENGTH));
    ota_p1_6_write_u32(OTA_P1_6_OFF_MAGIC, OTA_P1_6_DONE_MAGIC);
}

static int slot_write_allowed(uint32_t type)
{
    bcb_t bcb;
    bcb_arbiter_result_t active;

    if (type == OTA_P1_6_SLOT_RECOVERY)
    {
        return 1;
    }
    active = bcb_arbiter(&g_p1_6_bcb_hal, &bcb);
    if (active != BCB_ARBITER_A && active != BCB_ARBITER_B)
    {
        return 0;
    }
    return bcb.state == BCB_STATE_IDLE || bcb.state == BCB_STATE_CONFIRMED;
}

static int install_slot(uint32_t type, uint32_t *detail)
{
    boot_fw_header_t app_header;
    boot_slot_header_t parsed;
    boot_crc32_ctx_t crc;
    uint8_t raw_header[BOOT_SLOT_HEADER_SIZE];
    uint8_t readback[BOOT_SLOT_HEADER_SIZE];
    uint32_t base;
    uint32_t block_count;
    uint32_t block;
    uint32_t image_crc;

    if (!slot_type_valid(type))
    {
        *detail = OTA_P1_6_DETAIL_SLOT_ARGUMENT;
        return -1;
    }
    if (!slot_write_allowed(type))
    {
        *detail = OTA_P1_6_DETAIL_BCB_LOCKED;
        return -1;
    }
    if (validate_internal_app(&app_header) != BOOT_FW_OK)
    {
        *detail = OTA_P1_6_DETAIL_APP_INVALID;
        return -1;
    }

    base = slot_base(type);
    block_count = (app_header.image_len + P1_6_BLOCK_SIZE - 1u) /
                  P1_6_BLOCK_SIZE;
    ota_p1_6_write_u32(OTA_P1_6_OFF_TOTAL, block_count);

    if (boot_platform_qspi_erase_4k(base) != 0)
    {
        *detail = OTA_P1_6_DETAIL_SLOT_ERASE;
        return -1;
    }

    boot_crc32_init(&crc);
    for (block = 0u; block < block_count; ++block)
    {
        uint32_t offset = block * P1_6_BLOCK_SIZE;
        size_t take = app_header.image_len - offset;
        uint32_t external_address = base + OTA_SLOT_HEADER_SIZE + offset;

        if (take > sizeof(g_p1_6_block))
        {
            take = sizeof(g_p1_6_block);
        }
        if (boot_platform_flash_read(OTA_APP_ORIGIN + offset,
                                     g_p1_6_block, take) != 0 ||
            boot_platform_qspi_erase_4k(external_address) != 0)
        {
            *detail = OTA_P1_6_DETAIL_SLOT_ERASE;
            return -1;
        }
        if (boot_platform_qspi_program(external_address,
                                       g_p1_6_block, take) != 0)
        {
            *detail = OTA_P1_6_DETAIL_SLOT_PROGRAM;
            return -1;
        }
        if (verify_external(external_address, g_p1_6_block, take) != 0)
        {
            *detail = OTA_P1_6_DETAIL_SLOT_VERIFY;
            return -1;
        }
        boot_crc32_update(&crc, g_p1_6_block, take);
        ota_p1_6_write_u32(OTA_P1_6_OFF_PROGRESS, block + 1u);
    }
    image_crc = boot_crc32_final(&crc);
    if (verify_external_crc(base + OTA_SLOT_HEADER_SIZE,
                            app_header.image_len, image_crc) != 0)
    {
        *detail = OTA_P1_6_DETAIL_SLOT_VERIFY;
        return -1;
    }

    memset(raw_header, 0xFF, sizeof(raw_header));
    memcpy(raw_header, "ETSL", 4u);
    raw_header[4] = (uint8_t)type;
    write_le32(raw_header + 8u, app_header.image_len);
    write_le32(raw_header + 12u, image_crc);
    write_le32(raw_header + 16u, app_header.version_code);
    memcpy(raw_header + 20u, app_header.image_sha256, 8u);

    if (boot_platform_qspi_program(base, raw_header, 28u) != 0 ||
        boot_platform_qspi_read(base, readback, sizeof(readback)) != 0 ||
        memcmp(readback, raw_header, 28u) != 0 ||
        readback[28] != 0xFFu || readback[29] != 0xFFu ||
        readback[30] != 0xFFu || readback[31] != 0xFFu)
    {
        *detail = OTA_P1_6_DETAIL_SLOT_HEADER;
        return -1;
    }

    write_le32(raw_header + 28u, P1_6_SLOT_COMMIT_MARKER);
    if (boot_platform_qspi_program(base + 28u,
                                   raw_header + 28u, 4u) != 0 ||
        boot_platform_qspi_read(base, readback, sizeof(readback)) != 0 ||
        memcmp(readback, raw_header, sizeof(readback)) != 0 ||
        boot_slot_header_parse(readback, (boot_slot_type_t)type,
                               &parsed) != BOOT_SLOT_OK ||
        parsed.payload_len != app_header.image_len ||
        parsed.payload_crc32 != image_crc ||
        parsed.version_code != app_header.version_code ||
        memcmp(parsed.sha8, app_header.image_sha256,
               sizeof(parsed.sha8)) != 0)
    {
        *detail = OTA_P1_6_DETAIL_SLOT_HEADER;
        return -1;
    }
    return 0;
}

static int clear_bcb(void)
{
    uint8_t blank[BCB_SIZE];
    uint8_t readback[BCB_SIZE];

    memset(blank, 0xFF, sizeof(blank));
    if (boot_platform_eeprom_write(BCB_A_ADDR, blank, sizeof(blank)) != 0 ||
        boot_platform_eeprom_read(BCB_A_ADDR,
                                  readback, sizeof(readback)) != 0 ||
        memcmp(readback, blank, sizeof(blank)) != 0 ||
        boot_platform_eeprom_write(BCB_B_ADDR, blank, sizeof(blank)) != 0 ||
        boot_platform_eeprom_read(BCB_B_ADDR,
                                  readback, sizeof(readback)) != 0 ||
        memcmp(readback, blank, sizeof(blank)) != 0)
    {
        return -1;
    }
    return 0;
}

static int stage_slots(uint32_t *detail)
{
    p1_6_validated_slot_t candidate;
    p1_6_validated_slot_t backup;
    boot_fw_header_t internal;
    bcb_t current;
    bcb_t staged;
    bcb_arbiter_result_t active =
        bcb_arbiter(&g_p1_6_bcb_hal, &current);

    if ((active != BCB_ARBITER_A && active != BCB_ARBITER_B) ||
        (current.state != BCB_STATE_IDLE &&
         current.state != BCB_STATE_CONFIRMED) ||
        validate_internal_app(&internal) != BOOT_FW_OK ||
        internal.version_code != current.cur_vcode ||
        validate_slot(OTA_P1_6_SLOT_CANDIDATE, &candidate) != 0 ||
        validate_slot(OTA_P1_6_SLOT_BACKUP, &backup) != 0 ||
        backup.header.version_code != internal.version_code ||
        candidate.header.version_code <= internal.version_code)
    {
        *detail = OTA_P1_6_DETAIL_STAGE_VALIDATE;
        return -1;
    }

    staged = current;
    staged.state = BCB_STATE_STAGED;
    staged.boot_try = BCB_INIT_BOOT_TRY;
    staged.copy_phase = BCB_COPY_NONE;
    staged.resume_block = 0u;
    staged.cand_addr = candidate.slot_base + OTA_SLOT_HEADER_SIZE;
    staged.cand_len = candidate.slot.payload_len;
    staged.cand_crc32 = candidate.slot.payload_crc32;
    staged.cand_vcode = candidate.slot.version_code;
    staged.backup_len = backup.slot.payload_len;
    staged.backup_crc32 = backup.slot.payload_crc32;
    staged.backup_vcode = backup.slot.version_code;
    if (bcb_commit(&g_p1_6_bcb_hal, active, &staged) != BCB_COMMIT_OK)
    {
        *detail = OTA_P1_6_DETAIL_STAGE_COMMIT;
        return -1;
    }
    return 0;
}

static int corrupt_slot(uint32_t type,
                        uint32_t requested_offset,
                        uint32_t *detail)
{
    uint8_t raw[BOOT_SLOT_HEADER_SIZE];
    uint8_t value;
    uint8_t changed;
    boot_slot_header_t slot;
    uint32_t offset;
    uint32_t base;

    if (!slot_type_valid(type))
    {
        *detail = OTA_P1_6_DETAIL_SLOT_ARGUMENT;
        return -1;
    }
    base = slot_base(type);
    if (boot_platform_qspi_read(base, raw, sizeof(raw)) != 0 ||
        boot_slot_header_parse(raw, (boot_slot_type_t)type,
                               &slot) != BOOT_SLOT_OK ||
        requested_offset >= slot.payload_len)
    {
        *detail = OTA_P1_6_DETAIL_CORRUPT;
        return -1;
    }

    for (offset = requested_offset; offset < slot.payload_len; ++offset)
    {
        if (boot_platform_qspi_read(base + OTA_SLOT_HEADER_SIZE + offset,
                                    &value, sizeof(value)) != 0)
        {
            *detail = OTA_P1_6_DETAIL_CORRUPT;
            return -1;
        }
        if (value == 0u)
        {
            continue;
        }
        changed = (uint8_t)(value & (uint8_t)(value - 1u));
        if (boot_platform_qspi_program(base + OTA_SLOT_HEADER_SIZE + offset,
                                       &changed, sizeof(changed)) != 0 ||
            boot_platform_qspi_read(base + OTA_SLOT_HEADER_SIZE + offset,
                                    g_p1_6_verify, 1u) != 0 ||
            g_p1_6_verify[0] != changed)
        {
            *detail = OTA_P1_6_DETAIL_CORRUPT;
            return -1;
        }
        ota_p1_6_write_u32(OTA_P1_6_OFF_CORRUPT_OFFSET, offset);
        ota_p1_6_write_u32(OTA_P1_6_OFF_CORRUPT_OLD_NEW,
                           (uint32_t)value | ((uint32_t)changed << 8));
        return 0;
    }

    *detail = OTA_P1_6_DETAIL_CORRUPT;
    return -1;
}

static int command_valid(uint32_t *opcode,
                         uint32_t *arg0,
                         uint32_t *arg1)
{
    uint32_t observed_opcode =
        ota_p1_6_read_u32(OTA_P1_6_OFF_OPCODE);
    uint32_t observed_cookie =
        ota_p1_6_read_u32(OTA_P1_6_OFF_COOKIE);

    if (ota_p1_6_read_u32(OTA_P1_6_OFF_VERSION) != OTA_P1_6_VERSION ||
        (observed_opcode ^
         ota_p1_6_read_u32(OTA_P1_6_OFF_OPCODE_INVERSE)) != UINT32_MAX ||
        observed_cookie != OTA_P1_6_COOKIE ||
        (observed_cookie ^
         ota_p1_6_read_u32(OTA_P1_6_OFF_COOKIE_INVERSE)) != UINT32_MAX ||
        control_crc(0u, OTA_P1_6_COMMAND_CRC_LENGTH) !=
            ota_p1_6_read_u32(OTA_P1_6_OFF_COMMAND_CRC32))
    {
        return 0;
    }
    *opcode = observed_opcode;
    *arg0 = ota_p1_6_read_u32(OTA_P1_6_OFF_ARG0);
    *arg1 = ota_p1_6_read_u32(OTA_P1_6_OFF_ARG1);
    return 1;
}

boot_p1_6_result_t boot_p1_6_process_command(void)
{
    boot_fw_header_t app_header;
    uint32_t opcode;
    uint32_t arg0;
    uint32_t arg1;
    uint32_t detail = OTA_P1_6_DETAIL_NONE;
    int operation_result = -1;

    if (ota_p1_6_read_u32(OTA_P1_6_OFF_MAGIC) != OTA_P1_6_COMMAND_MAGIC)
    {
        return BOOT_P1_6_NO_REQUEST;
    }

    result_reset();
    if (!command_valid(&opcode, &arg0, &arg1))
    {
        result_finish(OTA_P1_6_STATUS_FAIL, OTA_P1_6_DETAIL_COMMAND, 0);
        return BOOT_P1_6_HOLD;
    }

    if (opcode == OTA_P1_6_OPCODE_CLEAR_BCB)
    {
        if (validate_internal_app(&app_header) != BOOT_FW_OK)
        {
            detail = OTA_P1_6_DETAIL_APP_INVALID;
        }
        else
        {
            operation_result = clear_bcb();
            detail = operation_result == 0 ? OTA_P1_6_DETAIL_NONE
                                           : OTA_P1_6_DETAIL_EEPROM;
        }
    }
    else if (opcode == OTA_P1_6_OPCODE_SNAPSHOT)
    {
        operation_result = 0;
        if (arg0 != 0u)
        {
            if (boot_platform_qspi_init() != 0)
            {
                operation_result = -1;
                detail = OTA_P1_6_DETAIL_QSPI_INIT;
            }
            else if (snapshot_slot(arg0) != 0)
            {
                operation_result = -1;
                detail = OTA_P1_6_DETAIL_SNAPSHOT;
            }
        }
        if (operation_result == 0 && arg1 != OTA_P1_6_SNAPSHOT_BCB_ONLY)
        {
            operation_result = snapshot_app();
            if (operation_result != 0)
            {
                detail = OTA_P1_6_DETAIL_SNAPSHOT;
            }
        }
    }
    else if (opcode == OTA_P1_6_OPCODE_INSTALL_SLOT ||
             opcode == OTA_P1_6_OPCODE_STAGE_SLOTS ||
             opcode == OTA_P1_6_OPCODE_CORRUPT_SLOT)
    {
        if (boot_platform_qspi_init() != 0)
        {
            detail = OTA_P1_6_DETAIL_QSPI_INIT;
        }
        else if (opcode == OTA_P1_6_OPCODE_INSTALL_SLOT)
        {
            operation_result = install_slot(arg0, &detail);
        }
        else if (opcode == OTA_P1_6_OPCODE_STAGE_SLOTS)
        {
            operation_result = stage_slots(&detail);
        }
        else
        {
            operation_result = corrupt_slot(arg0, arg1, &detail);
        }
    }
    else
    {
        detail = OTA_P1_6_DETAIL_COMMAND;
    }

    result_finish(operation_result == 0 ? OTA_P1_6_STATUS_PASS
                                         : OTA_P1_6_STATUS_FAIL,
                  detail, opcode == OTA_P1_6_OPCODE_SNAPSHOT &&
                              arg1 == OTA_P1_6_SNAPSHOT_BCB_ONLY);
    return BOOT_P1_6_HOLD;
}
