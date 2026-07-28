#include "boot_bootstrap.h"

#include "boot_crypto.h"
#include "boot_fw_header.h"
#include "boot_slot.h"
#include "EEPROM/eeprom_bcb.h"
#include "OTA/ota_layout.h"

#include <string.h>

enum
{
    BOOT_BOOTSTRAP_BLOCK_SIZE = 4096,
    BOOT_BOOTSTRAP_VERIFY_CHUNK = 256,
    BOOT_SLOT_COMMIT_MARKER = 0x434F4D54u
};

#if defined(OTA_TARGET_BOOT)
#define BOOT_BOOTSTRAP_NOINIT \
    __attribute__((used, section(".boot_bootstrap_noinit")))
#else
#define BOOT_BOOTSTRAP_NOINIT
#endif

BOOT_BOOTSTRAP_NOINIT volatile boot_bootstrap_command_t
    g_boot_bootstrap_command;

typedef char boot_bootstrap_command_size_check[
    sizeof(boot_bootstrap_command_t) == BOOT_BOOTSTRAP_COMMAND_SIZE ? 1 : -1];

typedef struct
{
    const boot_bootstrap_io_t *io;
    uint32_t base;
    uint32_t length;
} slot_reader_context_t;

typedef struct
{
    boot_slot_header_t slot;
    boot_fw_header_t header;
    uint32_t slot_base;
} validated_slot_t;

static const boot_bootstrap_io_t *g_bcb_io;
static uint8_t g_bootstrap_block[BOOT_BOOTSTRAP_BLOCK_SIZE];
static uint8_t g_bootstrap_verify[BOOT_BOOTSTRAP_VERIFY_CHUNK];

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

static uint32_t command_read_u32(uint32_t offset)
{
    uint8_t raw[4];
    uint32_t index;

    for (index = 0u; index < sizeof(raw); ++index)
    {
        raw[index] = g_boot_bootstrap_command.bytes[offset + index];
    }
    return read_le32(raw);
}

static void command_write_u32(uint32_t offset, uint32_t value)
{
    g_boot_bootstrap_command.bytes[offset] = (uint8_t)value;
    g_boot_bootstrap_command.bytes[offset + 1u] = (uint8_t)(value >> 8);
    g_boot_bootstrap_command.bytes[offset + 2u] = (uint8_t)(value >> 16);
    g_boot_bootstrap_command.bytes[offset + 3u] = (uint8_t)(value >> 24);
}

static uint32_t command_crc(uint32_t offset, uint32_t length)
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
            chunk[index] = g_boot_bootstrap_command.bytes[offset + index];
        }
        boot_crc32_update(&crc, chunk, take);
        offset += take;
        length -= take;
    }
    return boot_crc32_final(&crc);
}

static int bcb_write(uint8_t address, const uint8_t *src, uint16_t len)
{
    return g_bcb_io->eeprom_write(g_bcb_io->ctx, address, src, len);
}

static int bcb_read(uint8_t address, uint8_t *dst, uint16_t len)
{
    return g_bcb_io->eeprom_read(g_bcb_io->ctx, address, dst, len);
}

static const bcb_hal_t g_bootstrap_bcb_hal = {bcb_write, bcb_read};

static void result_reset(void)
{
    uint32_t offset;

    for (offset = BOOT_BOOTSTRAP_OFF_STATUS;
         offset <= BOOT_BOOTSTRAP_OFF_RESULT_CRC32;
         offset += sizeof(uint32_t))
    {
        command_write_u32(offset, 0u);
    }
    command_write_u32(BOOT_BOOTSTRAP_OFF_STATUS,
                      BOOT_BOOTSTRAP_STATUS_RUNNING);
    command_write_u32(BOOT_BOOTSTRAP_OFF_ACTIVE,
                      (uint32_t)BCB_ARBITER_ERROR);
    command_write_u32(BOOT_BOOTSTRAP_OFF_STATE, UINT32_MAX);
    command_write_u32(BOOT_BOOTSTRAP_OFF_BOOT_TRY, UINT32_MAX);
    command_write_u32(BOOT_BOOTSTRAP_OFF_COPY_PHASE, UINT32_MAX);
    command_write_u32(BOOT_BOOTSTRAP_OFF_RESUME_BLOCK, UINT32_MAX);
    command_write_u32(BOOT_BOOTSTRAP_OFF_CUR_VCODE, UINT32_MAX);
    command_write_u32(BOOT_BOOTSTRAP_OFF_CAND_VCODE, UINT32_MAX);
    command_write_u32(BOOT_BOOTSTRAP_OFF_BACKUP_VCODE, UINT32_MAX);
}

static void result_snapshot_bcb(void)
{
    bcb_t bcb;
    bcb_arbiter_result_t active = bcb_arbiter(&g_bootstrap_bcb_hal, &bcb);

    command_write_u32(BOOT_BOOTSTRAP_OFF_ACTIVE, (uint32_t)active);
    if (active != BCB_ARBITER_A && active != BCB_ARBITER_B)
    {
        return;
    }
    command_write_u32(BOOT_BOOTSTRAP_OFF_STATE, bcb.state);
    command_write_u32(BOOT_BOOTSTRAP_OFF_BOOT_TRY, bcb.boot_try);
    command_write_u32(BOOT_BOOTSTRAP_OFF_COPY_PHASE, bcb.copy_phase);
    command_write_u32(BOOT_BOOTSTRAP_OFF_RESUME_BLOCK, bcb.resume_block);
    command_write_u32(BOOT_BOOTSTRAP_OFF_CUR_VCODE, bcb.cur_vcode);
    command_write_u32(BOOT_BOOTSTRAP_OFF_CAND_VCODE, bcb.cand_vcode);
    command_write_u32(BOOT_BOOTSTRAP_OFF_BACKUP_VCODE, bcb.backup_vcode);
}

static void result_finish(uint32_t status, uint32_t detail)
{
    result_snapshot_bcb();
    command_write_u32(BOOT_BOOTSTRAP_OFF_DETAIL, detail);
    command_write_u32(BOOT_BOOTSTRAP_OFF_STATUS, status);
    command_write_u32(
        BOOT_BOOTSTRAP_OFF_RESULT_CRC32,
        command_crc(BOOT_BOOTSTRAP_RESULT_CRC_OFFSET,
                    BOOT_BOOTSTRAP_RESULT_CRC_LENGTH));
    command_write_u32(BOOT_BOOTSTRAP_OFF_MAGIC,
                      BOOT_BOOTSTRAP_DONE_MAGIC);
}

static int internal_reader(void *ctx, uint32_t offset,
                           uint8_t *dst, size_t len)
{
    const boot_bootstrap_io_t *io = (const boot_bootstrap_io_t *)ctx;

    if (offset > OTA_APP_LENGTH || len > OTA_APP_LENGTH - offset)
    {
        return -1;
    }
    return io->internal_read(io->ctx, OTA_APP_ORIGIN + offset, dst, len);
}

static int slot_reader(void *ctx, uint32_t offset,
                       uint8_t *dst, size_t len)
{
    const slot_reader_context_t *reader =
        (const slot_reader_context_t *)ctx;

    if (reader == NULL || offset > reader->length ||
        len > reader->length - offset)
    {
        return -1;
    }
    return reader->io->external_read(
        reader->io->ctx, reader->base + offset, dst, len);
}

static boot_fw_result_t validate_internal_app(const boot_bootstrap_io_t *io,
                                              boot_fw_header_t *header)
{
    boot_image_reader_t reader;
    boot_fw_expectations_t expected;

    reader.read = internal_reader;
    reader.ctx = (void *)io;
    boot_fw_default_expectations(&expected);
    return boot_fw_header_validate(&reader, &expected, header);
}

static uint32_t slot_base(uint32_t type)
{
    if (type == BOOT_BOOTSTRAP_SLOT_CANDIDATE)
    {
        return OTA_EXT_CANDIDATE;
    }
    if (type == BOOT_BOOTSTRAP_SLOT_BACKUP)
    {
        return OTA_EXT_BACKUP;
    }
    return OTA_EXT_RECOVERY;
}

static int verify_external(const boot_bootstrap_io_t *io,
                           uint32_t address, const uint8_t *expected,
                           size_t len)
{
    size_t offset = 0u;

    while (offset < len)
    {
        size_t take = len - offset;

        if (take > sizeof(g_bootstrap_verify))
        {
            take = sizeof(g_bootstrap_verify);
        }
        if (io->external_read(io->ctx, address + (uint32_t)offset,
                              g_bootstrap_verify, take) != 0 ||
            memcmp(g_bootstrap_verify, expected + offset, take) != 0)
        {
            return -1;
        }
        offset += take;
    }
    return 0;
}

static int verify_external_crc(const boot_bootstrap_io_t *io,
                               uint32_t address, uint32_t length,
                               uint32_t expected_crc)
{
    boot_crc32_ctx_t crc;
    uint32_t offset = 0u;

    boot_crc32_init(&crc);
    while (offset < length)
    {
        size_t take = length - offset;

        if (take > sizeof(g_bootstrap_verify))
        {
            take = sizeof(g_bootstrap_verify);
        }
        if (io->external_read(io->ctx, address + offset,
                              g_bootstrap_verify, take) != 0)
        {
            return -1;
        }
        boot_crc32_update(&crc, g_bootstrap_verify, take);
        offset += (uint32_t)take;
    }
    return boot_crc32_final(&crc) == expected_crc ? 0 : -1;
}

static int slot_write_allowed(uint32_t type)
{
    bcb_t bcb;
    bcb_arbiter_result_t active;

    if (type == BOOT_BOOTSTRAP_SLOT_RECOVERY)
    {
        return 1;
    }
    active = bcb_arbiter(&g_bootstrap_bcb_hal, &bcb);
    if (active != BCB_ARBITER_A && active != BCB_ARBITER_B)
    {
        return 0;
    }
    return bcb.state == BCB_STATE_IDLE || bcb.state == BCB_STATE_CONFIRMED;
}

static int install_slot(const boot_bootstrap_io_t *io, uint32_t type,
                        uint32_t *detail)
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

    if (type != BOOT_BOOTSTRAP_SLOT_CANDIDATE &&
        type != BOOT_BOOTSTRAP_SLOT_BACKUP &&
        type != BOOT_BOOTSTRAP_SLOT_RECOVERY)
    {
        *detail = BOOT_BOOTSTRAP_DETAIL_SLOT_ARGUMENT;
        return -1;
    }
    if (!slot_write_allowed(type))
    {
        *detail = BOOT_BOOTSTRAP_DETAIL_BCB_LOCKED;
        return -1;
    }
    if (validate_internal_app(io, &app_header) != BOOT_FW_OK)
    {
        *detail = BOOT_BOOTSTRAP_DETAIL_APP_INVALID;
        return -1;
    }

    base = slot_base(type);
    block_count = (app_header.image_len + BOOT_BOOTSTRAP_BLOCK_SIZE - 1u) /
                  BOOT_BOOTSTRAP_BLOCK_SIZE;
    command_write_u32(BOOT_BOOTSTRAP_OFF_TOTAL, block_count);
    command_write_u32(BOOT_BOOTSTRAP_OFF_IMAGE_VCODE,
                      app_header.version_code);
    command_write_u32(BOOT_BOOTSTRAP_OFF_IMAGE_LEN, app_header.image_len);

    if (io->external_erase_4k(io->ctx, base) != 0)
    {
        *detail = BOOT_BOOTSTRAP_DETAIL_SLOT_ERASE;
        return -1;
    }

    boot_crc32_init(&crc);
    for (block = 0u; block < block_count; ++block)
    {
        uint32_t offset = block * BOOT_BOOTSTRAP_BLOCK_SIZE;
        size_t take = app_header.image_len - offset;
        uint32_t external_address = base + OTA_SLOT_HEADER_SIZE + offset;

        if (take > sizeof(g_bootstrap_block))
        {
            take = sizeof(g_bootstrap_block);
        }
        if (io->internal_read(io->ctx, OTA_APP_ORIGIN + offset,
                              g_bootstrap_block, take) != 0 ||
            io->external_erase_4k(io->ctx, external_address) != 0)
        {
            *detail = BOOT_BOOTSTRAP_DETAIL_SLOT_ERASE;
            return -1;
        }
        if (io->external_program(io->ctx, external_address,
                                 g_bootstrap_block, take) != 0)
        {
            *detail = BOOT_BOOTSTRAP_DETAIL_SLOT_PROGRAM;
            return -1;
        }
        if (verify_external(io, external_address,
                            g_bootstrap_block, take) != 0)
        {
            *detail = BOOT_BOOTSTRAP_DETAIL_SLOT_VERIFY;
            return -1;
        }
        boot_crc32_update(&crc, g_bootstrap_block, take);
        command_write_u32(BOOT_BOOTSTRAP_OFF_PROGRESS, block + 1u);
    }
    image_crc = boot_crc32_final(&crc);
    command_write_u32(BOOT_BOOTSTRAP_OFF_IMAGE_CRC32, image_crc);
    if (verify_external_crc(io, base + OTA_SLOT_HEADER_SIZE,
                            app_header.image_len, image_crc) != 0)
    {
        *detail = BOOT_BOOTSTRAP_DETAIL_SLOT_VERIFY;
        return -1;
    }

    memset(raw_header, 0xFF, sizeof(raw_header));
    memcpy(raw_header, "ETSL", 4u);
    raw_header[4] = (uint8_t)type;
    write_le32(raw_header + 8u, app_header.image_len);
    write_le32(raw_header + 12u, image_crc);
    write_le32(raw_header + 16u, app_header.version_code);
    memcpy(raw_header + 20u, app_header.image_sha256, 8u);

    if (io->external_program(io->ctx, base, raw_header, 28u) != 0 ||
        io->external_read(io->ctx, base, readback, sizeof(readback)) != 0 ||
        memcmp(readback, raw_header, 28u) != 0 ||
        readback[28] != 0xFFu || readback[29] != 0xFFu ||
        readback[30] != 0xFFu || readback[31] != 0xFFu)
    {
        *detail = BOOT_BOOTSTRAP_DETAIL_SLOT_HEADER;
        return -1;
    }

    write_le32(raw_header + 28u, BOOT_SLOT_COMMIT_MARKER);
    if (io->external_program(io->ctx, base + 28u,
                             raw_header + 28u, 4u) != 0 ||
        io->external_read(io->ctx, base, readback, sizeof(readback)) != 0 ||
        memcmp(readback, raw_header, sizeof(readback)) != 0 ||
        boot_slot_header_parse(readback, (boot_slot_type_t)type, &parsed) !=
            BOOT_SLOT_OK ||
        parsed.payload_len != app_header.image_len ||
        parsed.payload_crc32 != image_crc ||
        parsed.version_code != app_header.version_code ||
        memcmp(parsed.sha8, app_header.image_sha256,
               sizeof(parsed.sha8)) != 0)
    {
        *detail = BOOT_BOOTSTRAP_DETAIL_SLOT_HEADER;
        return -1;
    }
    return 0;
}

static int validate_slot(const boot_bootstrap_io_t *io, uint32_t type,
                         validated_slot_t *validated)
{
    boot_image_reader_t reader;
    boot_fw_expectations_t expected;
    slot_reader_context_t context;
    uint8_t raw[BOOT_SLOT_HEADER_SIZE];

    memset(validated, 0, sizeof(*validated));
    validated->slot_base = slot_base(type);
    if (io->external_read(io->ctx, validated->slot_base,
                          raw, sizeof(raw)) != 0 ||
        boot_slot_header_parse(raw, (boot_slot_type_t)type,
                               &validated->slot) != BOOT_SLOT_OK ||
        verify_external_crc(io,
                            validated->slot_base + OTA_SLOT_HEADER_SIZE,
                            validated->slot.payload_len,
                            validated->slot.payload_crc32) != 0)
    {
        return -1;
    }

    context.io = io;
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

static int clear_bcb(const boot_bootstrap_io_t *io)
{
    uint8_t blank[BCB_SIZE];
    uint8_t readback[BCB_SIZE];

    memset(blank, 0xFF, sizeof(blank));
    if (io->eeprom_write(io->ctx, BCB_A_ADDR, blank, sizeof(blank)) != 0 ||
        io->eeprom_read(io->ctx, BCB_A_ADDR,
                        readback, sizeof(readback)) != 0 ||
        memcmp(readback, blank, sizeof(blank)) != 0 ||
        io->eeprom_write(io->ctx, BCB_B_ADDR, blank, sizeof(blank)) != 0 ||
        io->eeprom_read(io->ctx, BCB_B_ADDR,
                        readback, sizeof(readback)) != 0 ||
        memcmp(readback, blank, sizeof(blank)) != 0)
    {
        return -1;
    }
    return 0;
}

static int stage_slots(const boot_bootstrap_io_t *io, uint32_t *detail)
{
    validated_slot_t candidate;
    validated_slot_t backup;
    boot_fw_header_t internal;
    bcb_t current;
    bcb_t staged;
    bcb_arbiter_result_t active =
        bcb_arbiter(&g_bootstrap_bcb_hal, &current);

    if ((active != BCB_ARBITER_A && active != BCB_ARBITER_B) ||
        (current.state != BCB_STATE_IDLE &&
         current.state != BCB_STATE_CONFIRMED) ||
        validate_internal_app(io, &internal) != BOOT_FW_OK ||
        internal.version_code != current.cur_vcode ||
        validate_slot(io, BOOT_BOOTSTRAP_SLOT_CANDIDATE,
                      &candidate) != 0 ||
        validate_slot(io, BOOT_BOOTSTRAP_SLOT_BACKUP, &backup) != 0 ||
        backup.header.version_code != internal.version_code ||
        candidate.header.version_code <= internal.version_code)
    {
        *detail = BOOT_BOOTSTRAP_DETAIL_STAGE_VALIDATE;
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
    if (bcb_commit(&g_bootstrap_bcb_hal, active, &staged) != BCB_COMMIT_OK)
    {
        *detail = BOOT_BOOTSTRAP_DETAIL_STAGE_COMMIT;
        return -1;
    }
    return 0;
}

static int command_valid(uint32_t *opcode, uint32_t *arg0)
{
    uint32_t observed_opcode =
        command_read_u32(BOOT_BOOTSTRAP_OFF_OPCODE);
    uint32_t observed_cookie =
        command_read_u32(BOOT_BOOTSTRAP_OFF_COOKIE);

    if (command_read_u32(BOOT_BOOTSTRAP_OFF_VERSION) !=
            BOOT_BOOTSTRAP_COMMAND_VERSION ||
        (observed_opcode ^
         command_read_u32(BOOT_BOOTSTRAP_OFF_OPCODE_INVERSE)) != UINT32_MAX ||
        observed_cookie != BOOT_BOOTSTRAP_COMMAND_COOKIE ||
        (observed_cookie ^
         command_read_u32(BOOT_BOOTSTRAP_OFF_COOKIE_INVERSE)) != UINT32_MAX ||
        command_crc(0u, BOOT_BOOTSTRAP_COMMAND_CRC_LENGTH) !=
            command_read_u32(BOOT_BOOTSTRAP_OFF_COMMAND_CRC32))
    {
        return 0;
    }
    *opcode = observed_opcode;
    *arg0 = command_read_u32(BOOT_BOOTSTRAP_OFF_ARG0);
    return 1;
}

static int io_valid(const boot_bootstrap_io_t *io)
{
    return io != NULL && io->eeprom_write != NULL &&
           io->eeprom_read != NULL && io->internal_read != NULL &&
           io->external_init != NULL && io->external_erase_4k != NULL &&
           io->external_program != NULL && io->external_read != NULL;
}

boot_bootstrap_result_t boot_bootstrap_process(const boot_bootstrap_io_t *io)
{
    boot_fw_header_t app_header;
    uint32_t opcode;
    uint32_t arg0;
    uint32_t detail = BOOT_BOOTSTRAP_DETAIL_NONE;
    int operation_result = -1;

    if (command_read_u32(BOOT_BOOTSTRAP_OFF_MAGIC) !=
        BOOT_BOOTSTRAP_COMMAND_MAGIC)
    {
        return BOOT_BOOTSTRAP_NO_REQUEST;
    }

    result_reset();
    if (!io_valid(io))
    {
        command_write_u32(BOOT_BOOTSTRAP_OFF_STATUS,
                          BOOT_BOOTSTRAP_STATUS_FAIL);
        command_write_u32(BOOT_BOOTSTRAP_OFF_DETAIL,
                          BOOT_BOOTSTRAP_DETAIL_COMMAND);
        command_write_u32(BOOT_BOOTSTRAP_OFF_MAGIC,
                          BOOT_BOOTSTRAP_DONE_MAGIC);
        return BOOT_BOOTSTRAP_HOLD;
    }
    g_bcb_io = io;
    if (!command_valid(&opcode, &arg0))
    {
        result_finish(BOOT_BOOTSTRAP_STATUS_FAIL,
                      BOOT_BOOTSTRAP_DETAIL_COMMAND);
        return BOOT_BOOTSTRAP_HOLD;
    }

    if (opcode == BOOT_BOOTSTRAP_OPCODE_CLEAR_BCB)
    {
        if (validate_internal_app(io, &app_header) != BOOT_FW_OK)
        {
            detail = BOOT_BOOTSTRAP_DETAIL_APP_INVALID;
        }
        else
        {
            command_write_u32(BOOT_BOOTSTRAP_OFF_IMAGE_VCODE,
                              app_header.version_code);
            command_write_u32(BOOT_BOOTSTRAP_OFF_IMAGE_LEN,
                              app_header.image_len);
            operation_result = clear_bcb(io);
            detail = operation_result == 0 ? BOOT_BOOTSTRAP_DETAIL_NONE
                                           : BOOT_BOOTSTRAP_DETAIL_EEPROM;
        }
    }
    else if (opcode == BOOT_BOOTSTRAP_OPCODE_SNAPSHOT_BCB)
    {
        operation_result = 0;
    }
    else if (opcode == BOOT_BOOTSTRAP_OPCODE_INSTALL_SLOT ||
             opcode == BOOT_BOOTSTRAP_OPCODE_STAGE_SLOTS)
    {
        if (io->external_init(io->ctx) != 0)
        {
            detail = BOOT_BOOTSTRAP_DETAIL_QSPI_INIT;
        }
        else if (opcode == BOOT_BOOTSTRAP_OPCODE_INSTALL_SLOT)
        {
            operation_result = install_slot(io, arg0, &detail);
        }
        else
        {
            operation_result = stage_slots(io, &detail);
        }
    }
    else
    {
        detail = BOOT_BOOTSTRAP_DETAIL_COMMAND;
    }

    result_finish(operation_result == 0 ? BOOT_BOOTSTRAP_STATUS_PASS
                                        : BOOT_BOOTSTRAP_STATUS_FAIL,
                  detail);
    return BOOT_BOOTSTRAP_HOLD;
}

#undef BOOT_BOOTSTRAP_NOINIT
