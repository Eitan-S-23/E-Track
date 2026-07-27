#include "boot_state_machine.h"

#include "boot_crypto.h"
#include "boot_slot.h"
#include "OTA/ota_layout.h"

#include <string.h>

enum
{
    BOOT_COPY_BLOCK_SIZE = 4096,
    BOOT_VERIFY_CHUNK_SIZE = 256,
    BOOT_STATE_MAX_TRANSITIONS = 16
};

typedef enum
{
    SOURCE_CANDIDATE,
    SOURCE_BACKUP,
    SOURCE_RECOVERY
} source_kind_t;

typedef enum
{
    SOURCE_OK = 0,
    SOURCE_INVALID,
    SOURCE_IO_ERROR
} source_result_t;

typedef struct
{
    const boot_state_io_t *io;
    uint32_t base;
    uint32_t length;
    int external;
} image_reader_context_t;

typedef struct
{
    source_kind_t kind;
    uint32_t payload_address;
    uint32_t payload_len;
    uint32_t payload_crc32;
    uint32_t version_code;
    boot_fw_header_t header;
} image_source_t;

static uint8_t g_copy_block[BOOT_COPY_BLOCK_SIZE];

static void state_log(const boot_state_io_t *io, const char *text)
{
    if (io != NULL && io->log != NULL)
    {
        io->log(io->ctx, text);
    }
}

static void outcome_reset(boot_state_outcome_t *outcome)
{
    if (outcome != NULL)
    {
        memset(outcome, 0, sizeof(*outcome));
        outcome->action = BOOT_STATE_ACTION_HOLD;
        outcome->status = BOOT_STATE_STATUS_OK;
    }
}

static int image_read_bridge(void *opaque, uint32_t offset,
                             uint8_t *dst, size_t len)
{
    image_reader_context_t *ctx = (image_reader_context_t *)opaque;
    boot_state_read_fn read_fn;

    if (ctx == NULL || ctx->io == NULL || dst == NULL ||
        offset > ctx->length || len > ctx->length - offset)
    {
        return -1;
    }

    read_fn = ctx->external ? ctx->io->external_read : ctx->io->internal_read;
    if (read_fn == NULL)
    {
        return -1;
    }
    return read_fn(ctx->io->ctx, ctx->base + offset, dst, len);
}

static boot_fw_result_t validate_internal_app(const boot_state_io_t *io,
                                              boot_fw_header_t *header)
{
    image_reader_context_t context;
    boot_image_reader_t reader;
    boot_fw_expectations_t expected;

    context.io = io;
    context.base = OTA_APP_ORIGIN;
    context.length = OTA_APP_LENGTH;
    context.external = 0;
    reader.read = image_read_bridge;
    reader.ctx = &context;
    boot_fw_default_expectations(&expected);
    return boot_fw_header_validate(&reader, &expected, header);
}

static uint32_t source_slot_base(source_kind_t kind)
{
    if (kind == SOURCE_CANDIDATE)
    {
        return OTA_EXT_CANDIDATE;
    }
    if (kind == SOURCE_BACKUP)
    {
        return OTA_EXT_BACKUP;
    }
    return OTA_EXT_RECOVERY;
}

static boot_slot_type_t source_slot_type(source_kind_t kind)
{
    if (kind == SOURCE_CANDIDATE)
    {
        return BOOT_SLOT_CANDIDATE;
    }
    if (kind == SOURCE_BACKUP)
    {
        return BOOT_SLOT_BACKUP;
    }
    return BOOT_SLOT_RECOVERY;
}

static source_result_t validate_external_source(const boot_state_io_t *io,
                                                const bcb_t *bcb,
                                                source_kind_t kind,
                                                image_source_t *source)
{
    uint8_t raw[BOOT_SLOT_HEADER_SIZE];
    uint8_t chunk[BOOT_VERIFY_CHUNK_SIZE];
    boot_slot_header_t slot;
    boot_slot_result_t slot_result;
    image_reader_context_t context;
    boot_image_reader_t reader;
    boot_fw_expectations_t expected;
    boot_crc32_ctx_t crc;
    uint32_t slot_base;
    uint32_t offset;

    if (io == NULL || source == NULL || !io->external_available ||
        io->external_read == NULL)
    {
        return SOURCE_IO_ERROR;
    }

    slot_base = source_slot_base(kind);
    if (io->external_read(io->ctx, slot_base, raw, sizeof(raw)) != 0)
    {
        return SOURCE_IO_ERROR;
    }
    slot_result = boot_slot_header_parse(raw, source_slot_type(kind), &slot);
    if (slot_result != BOOT_SLOT_OK)
    {
        return SOURCE_INVALID;
    }

    boot_crc32_init(&crc);
    offset = 0u;
    while (offset < slot.payload_len)
    {
        size_t take = slot.payload_len - offset;
        if (take > sizeof(chunk))
        {
            take = sizeof(chunk);
        }
        if (io->external_read(io->ctx,
                              slot_base + OTA_SLOT_HEADER_SIZE + offset,
                              chunk, take) != 0)
        {
            return SOURCE_IO_ERROR;
        }
        boot_crc32_update(&crc, chunk, take);
        offset += (uint32_t)take;
    }
    if (boot_crc32_final(&crc) != slot.payload_crc32)
    {
        return SOURCE_INVALID;
    }

    context.io = io;
    context.base = slot_base + OTA_SLOT_HEADER_SIZE;
    context.length = slot.payload_len;
    context.external = 1;
    reader.read = image_read_bridge;
    reader.ctx = &context;
    boot_fw_default_expectations(&expected);
    if (boot_fw_header_validate(&reader, &expected, &source->header) != BOOT_FW_OK)
    {
        return SOURCE_INVALID;
    }
    if (source->header.image_len != slot.payload_len ||
        source->header.version_code != slot.version_code ||
        memcmp(source->header.image_sha256, slot.sha8, sizeof(slot.sha8)) != 0)
    {
        return SOURCE_INVALID;
    }

    if (kind == SOURCE_CANDIDATE)
    {
        if (bcb == NULL ||
            bcb->cand_addr != slot_base + OTA_SLOT_HEADER_SIZE ||
            bcb->cand_len != slot.payload_len ||
            bcb->cand_crc32 != slot.payload_crc32 ||
            bcb->cand_vcode != slot.version_code)
        {
            return SOURCE_INVALID;
        }
    }
    else if (kind == SOURCE_BACKUP)
    {
        if (bcb == NULL || bcb->backup_len == 0u ||
            bcb->backup_len != slot.payload_len ||
            bcb->backup_crc32 != slot.payload_crc32 ||
            bcb->backup_vcode != slot.version_code)
        {
            return SOURCE_INVALID;
        }
    }

    source->kind = kind;
    source->payload_address = slot_base + OTA_SLOT_HEADER_SIZE;
    source->payload_len = slot.payload_len;
    source->payload_crc32 = slot.payload_crc32;
    source->version_code = slot.version_code;
    return SOURCE_OK;
}

static int commit_record(const boot_state_io_t *io,
                         bcb_arbiter_result_t *active,
                         bcb_t *current,
                         const bcb_t *next)
{
    bcb_arbiter_result_t observed;

    if (bcb_commit(io->bcb_hal, *active, next) != BCB_COMMIT_OK)
    {
        return -1;
    }
    observed = bcb_arbiter(io->bcb_hal, current);
    if (observed != BCB_ARBITER_A && observed != BCB_ARBITER_B)
    {
        return -1;
    }
    *active = observed;
    return 0;
}

static int begin_rollback(const boot_state_io_t *io,
                          bcb_arbiter_result_t *active,
                          bcb_t *current)
{
    bcb_t next = *current;

    next.state = BCB_STATE_ROLLBACK;
    next.boot_try = 0u;
    next.copy_phase = BCB_COPY_ROLLBACK;
    next.resume_block = 0u;
    return commit_record(io, active, current, &next);
}

static int initialize_recovery_rollback(const boot_state_io_t *io,
                                        bcb_arbiter_result_t *active,
                                        bcb_t *current)
{
    bcb_t next;

    if (*active == BCB_ARBITER_NONE)
    {
        bcb_make_idle(&next, 0u);
    }
    else
    {
        next = *current;
    }
    next.state = BCB_STATE_ROLLBACK;
    next.boot_try = 0u;
    next.copy_phase = BCB_COPY_ROLLBACK;
    next.resume_block = 0u;
    return commit_record(io, active, current, &next);
}

static int verify_programmed_block(const boot_state_io_t *io,
                                   uint32_t address,
                                   const uint8_t expected[BOOT_COPY_BLOCK_SIZE])
{
    uint8_t readback[BOOT_VERIFY_CHUNK_SIZE];
    uint32_t offset;

    for (offset = 0u; offset < BOOT_COPY_BLOCK_SIZE;
         offset += (uint32_t)sizeof(readback))
    {
        if (io->internal_read(io->ctx, address + offset,
                              readback, sizeof(readback)) != 0 ||
            memcmp(readback, expected + offset, sizeof(readback)) != 0)
        {
            return -1;
        }
    }
    return 0;
}

static int verified_prefix_matches_source(const boot_state_io_t *io,
                                          const image_source_t *source,
                                          uint16_t resume_block)
{
    uint8_t readback[BOOT_VERIFY_CHUNK_SIZE];
    uint32_t block_count;
    uint32_t block;

    block_count = (source->payload_len + BOOT_COPY_BLOCK_SIZE - 1u) /
                  BOOT_COPY_BLOCK_SIZE;
    if (resume_block > block_count)
    {
        return 0;
    }

    for (block = 0u; block < resume_block; ++block)
    {
        uint32_t source_offset = block * BOOT_COPY_BLOCK_SIZE;
        uint32_t chunk_offset;
        size_t take = source->payload_len - source_offset;

        if (take > BOOT_COPY_BLOCK_SIZE)
        {
            take = BOOT_COPY_BLOCK_SIZE;
        }
        memset(g_copy_block, 0xFF, sizeof(g_copy_block));
        if (io->external_read(io->ctx, source->payload_address + source_offset,
                              g_copy_block, take) != 0)
        {
            return 0;
        }
        for (chunk_offset = 0u; chunk_offset < BOOT_COPY_BLOCK_SIZE;
             chunk_offset += (uint32_t)sizeof(readback))
        {
            if (io->internal_read(io->ctx,
                                  OTA_APP_ORIGIN + source_offset + chunk_offset,
                                  readback, sizeof(readback)) != 0 ||
                memcmp(readback, g_copy_block + chunk_offset,
                       sizeof(readback)) != 0)
            {
                return 0;
            }
        }
    }
    return 1;
}

static boot_state_status_t copy_source(const boot_state_io_t *io,
                                       const image_source_t *source,
                                       bcb_arbiter_result_t *active,
                                       bcb_t *current)
{
    uint32_t block_count;
    uint32_t block;

    block_count = (source->payload_len + BOOT_COPY_BLOCK_SIZE - 1u) /
                  BOOT_COPY_BLOCK_SIZE;
    if (current->resume_block > block_count)
    {
        return BOOT_STATE_STATUS_COPY;
    }

    for (block = current->resume_block; block < block_count; ++block)
    {
        uint32_t source_offset = block * BOOT_COPY_BLOCK_SIZE;
        uint32_t target_address = OTA_APP_ORIGIN + source_offset;
        size_t take = source->payload_len - source_offset;
        bcb_t next;

        if (take > BOOT_COPY_BLOCK_SIZE)
        {
            take = BOOT_COPY_BLOCK_SIZE;
        }
        memset(g_copy_block, 0xFF, sizeof(g_copy_block));
        if (io->external_read(io->ctx, source->payload_address + source_offset,
                              g_copy_block, take) != 0)
        {
            return BOOT_STATE_STATUS_COPY;
        }
        if (io->internal_erase_4k(io->ctx, target_address) != 0 ||
            io->internal_program(io->ctx, target_address,
                                 g_copy_block, sizeof(g_copy_block)) != 0 ||
            verify_programmed_block(io, target_address, g_copy_block) != 0)
        {
            return BOOT_STATE_STATUS_COPY;
        }

        next = *current;
        next.resume_block = (uint16_t)(block + 1u);
        if (commit_record(io, active, current, &next) != 0)
        {
            return BOOT_STATE_STATUS_COMMIT;
        }
    }
    return BOOT_STATE_STATUS_OK;
}

static int internal_matches_source(const boot_fw_header_t *app,
                                   const image_source_t *source)
{
    return app->image_len == source->header.image_len &&
           app->version_code == source->header.version_code &&
           memcmp(app->image_sha256, source->header.image_sha256,
                  sizeof(app->image_sha256)) == 0;
}

static boot_state_status_t commit_confirmed(const boot_state_io_t *io,
                                            bcb_arbiter_result_t *active,
                                            bcb_t *current,
                                            uint32_t version_code)
{
    bcb_t next;

    if (*active == BCB_ARBITER_NONE)
    {
        bcb_make_idle(&next, version_code);
    }
    else
    {
        next = *current;
    }
    next.state = BCB_STATE_CONFIRMED;
    next.boot_try = 0u;
    next.copy_phase = BCB_COPY_NONE;
    next.resume_block = 0u;
    next.cur_vcode = version_code;
    return commit_record(io, active, current, &next) == 0
               ? BOOT_STATE_STATUS_OK
               : BOOT_STATE_STATUS_COMMIT;
}

static boot_state_status_t return_jump(const bcb_t *current,
                                       const boot_fw_header_t *header,
                                       boot_state_outcome_t *outcome)
{
    if (outcome != NULL)
    {
        outcome->action = BOOT_STATE_ACTION_JUMP_APP;
        outcome->status = BOOT_STATE_STATUS_OK;
        outcome->bcb = *current;
        outcome->app_header = *header;
    }
    return BOOT_STATE_STATUS_OK;
}

static boot_state_status_t return_recovery(boot_state_status_t status,
                                           const bcb_t *current,
                                           boot_state_outcome_t *outcome)
{
    if (outcome != NULL)
    {
        outcome->action = BOOT_STATE_ACTION_PHYSICAL_RECOVERY;
        outcome->status = status;
        if (current != NULL)
        {
            outcome->bcb = *current;
        }
    }
    return status;
}

static boot_state_status_t return_hold(boot_state_status_t status,
                                       const bcb_t *current,
                                       boot_state_outcome_t *outcome)
{
    if (outcome != NULL)
    {
        outcome->action = BOOT_STATE_ACTION_HOLD;
        outcome->status = status;
        if (current != NULL)
        {
            outcome->bcb = *current;
        }
    }
    return status;
}

boot_state_status_t boot_state_machine_run(const boot_state_io_t *io,
                                           boot_state_outcome_t *outcome)
{
    bcb_arbiter_result_t active;
    bcb_t current;
    unsigned transition;

    outcome_reset(outcome);
    if (io == NULL || io->bcb_hal == NULL || io->internal_read == NULL ||
        io->internal_erase_4k == NULL || io->internal_program == NULL)
    {
        return return_hold(BOOT_STATE_STATUS_ARGUMENT, NULL, outcome);
    }

    memset(&current, 0, sizeof(current));
    active = bcb_arbiter(io->bcb_hal, &current);
    if (active == BCB_ARBITER_ERROR)
    {
        state_log(io, "BOOT: BCB I/O failure\r\n");
        return return_recovery(BOOT_STATE_STATUS_BCB, NULL, outcome);
    }

    for (transition = 0u; transition < BOOT_STATE_MAX_TRANSITIONS; ++transition)
    {
        boot_fw_header_t app_header;
        boot_fw_result_t app_result;
        image_source_t source;
        source_result_t source_result;
        boot_state_status_t copy_result;

        if (active == BCB_ARBITER_NONE)
        {
            app_result = validate_internal_app(io, &app_header);
            if (app_result == BOOT_FW_OK)
            {
                if (commit_confirmed(io, &active, &current,
                                     app_header.version_code) != BOOT_STATE_STATUS_OK)
                {
                    return return_hold(BOOT_STATE_STATUS_COMMIT, NULL, outcome);
                }
                continue;
            }
            source_result = validate_external_source(io, NULL, SOURCE_RECOVERY,
                                                      &source);
            if (source_result != SOURCE_OK)
            {
                return return_recovery(BOOT_STATE_STATUS_APP, NULL, outcome);
            }
            if (initialize_recovery_rollback(io, &active, &current) != 0)
            {
                return return_hold(BOOT_STATE_STATUS_COMMIT, NULL, outcome);
            }
            continue;
        }

        switch ((bcb_state_t)current.state)
        {
        case BCB_STATE_IDLE:
            app_result = validate_internal_app(io, &app_header);
            if (app_result != BOOT_FW_OK)
            {
                if (initialize_recovery_rollback(io, &active, &current) != 0)
                {
                    return return_hold(BOOT_STATE_STATUS_COMMIT, &current, outcome);
                }
                continue;
            }
            if (commit_confirmed(io, &active, &current,
                                 app_header.version_code) != BOOT_STATE_STATUS_OK)
            {
                return return_hold(BOOT_STATE_STATUS_COMMIT, &current, outcome);
            }
            continue;

        case BCB_STATE_CONFIRMED:
            app_result = validate_internal_app(io, &app_header);
            if (app_result == BOOT_FW_OK)
            {
                return return_jump(&current, &app_header, outcome);
            }
            if (begin_rollback(io, &active, &current) != 0)
            {
                return return_hold(BOOT_STATE_STATUS_COMMIT, &current, outcome);
            }
            continue;

        case BCB_STATE_STAGED:
            source_result = validate_external_source(io, &current,
                                                      SOURCE_CANDIDATE, &source);
            if (source_result == SOURCE_IO_ERROR)
            {
                app_result = validate_internal_app(io, &app_header);
                if (app_result == BOOT_FW_OK)
                {
                    return return_jump(&current, &app_header, outcome);
                }
                return return_recovery(BOOT_STATE_STATUS_SLOT, &current, outcome);
            }
            if (source_result != SOURCE_OK)
            {
                if (begin_rollback(io, &active, &current) != 0)
                {
                    return return_hold(BOOT_STATE_STATUS_COMMIT, &current, outcome);
                }
                continue;
            }
            {
                bcb_t next = current;
                next.state = BCB_STATE_APPLYING;
                next.boot_try = 0u;
                next.copy_phase = BCB_COPY_APPLY;
                next.resume_block = 0u;
                if (commit_record(io, &active, &current, &next) != 0)
                {
                    return return_hold(BOOT_STATE_STATUS_COMMIT, &current, outcome);
                }
            }
            continue;

        case BCB_STATE_APPLYING:
            if (current.copy_phase != BCB_COPY_APPLY)
            {
                if (begin_rollback(io, &active, &current) != 0)
                {
                    return return_hold(BOOT_STATE_STATUS_COMMIT, &current, outcome);
                }
                continue;
            }
            source_result = validate_external_source(io, &current,
                                                      SOURCE_CANDIDATE, &source);
            if (source_result != SOURCE_OK)
            {
                if (source_result == SOURCE_IO_ERROR)
                {
                    return return_recovery(BOOT_STATE_STATUS_SLOT, &current, outcome);
                }
                if (begin_rollback(io, &active, &current) != 0)
                {
                    return return_hold(BOOT_STATE_STATUS_COMMIT, &current, outcome);
                }
                continue;
            }
            copy_result = copy_source(io, &source, &active, &current);
            if (copy_result != BOOT_STATE_STATUS_OK)
            {
                return return_hold(copy_result, &current, outcome);
            }
            app_result = validate_internal_app(io, &app_header);
            if (app_result != BOOT_FW_OK ||
                !internal_matches_source(&app_header, &source))
            {
                if (begin_rollback(io, &active, &current) != 0)
                {
                    return return_hold(BOOT_STATE_STATUS_COMMIT, &current, outcome);
                }
                continue;
            }
            {
                bcb_t next = current;
                next.state = BCB_STATE_TEST_BOOT;
                next.boot_try = BCB_INIT_BOOT_TRY;
                next.copy_phase = BCB_COPY_NONE;
                next.resume_block = 0u;
                if (commit_record(io, &active, &current, &next) != 0)
                {
                    return return_hold(BOOT_STATE_STATUS_COMMIT, &current, outcome);
                }
            }
            continue;

        case BCB_STATE_TEST_BOOT:
            app_result = validate_internal_app(io, &app_header);
            if (app_result != BOOT_FW_OK ||
                app_header.version_code != current.cand_vcode)
            {
                if (begin_rollback(io, &active, &current) != 0)
                {
                    return return_hold(BOOT_STATE_STATUS_COMMIT, &current, outcome);
                }
                continue;
            }
            if (current.boot_try == 0u)
            {
                if (begin_rollback(io, &active, &current) != 0)
                {
                    return return_hold(BOOT_STATE_STATUS_COMMIT, &current, outcome);
                }
                continue;
            }
            {
                bcb_t next = current;
                next.boot_try = (uint8_t)(current.boot_try - 1u);
                if (commit_record(io, &active, &current, &next) != 0)
                {
                    return return_hold(BOOT_STATE_STATUS_COMMIT, &current, outcome);
                }
            }
            return return_jump(&current, &app_header, outcome);

        case BCB_STATE_ROLLBACK:
        {
            image_source_t backup_source;
            image_source_t recovery_source;
            source_result_t backup_result;
            source_result_t recovery_result;
            int source_selected = 0;

            if (current.copy_phase != BCB_COPY_ROLLBACK)
            {
                return return_recovery(BOOT_STATE_STATUS_BCB, &current, outcome);
            }

            backup_result = validate_external_source(io, &current,
                                                       SOURCE_BACKUP,
                                                       &backup_source);
            recovery_result = SOURCE_INVALID;
            if (current.resume_block == 0u && backup_result == SOURCE_OK)
            {
                source = backup_source;
                source_selected = 1;
            }
            else if (current.resume_block != 0u && backup_result == SOURCE_OK &&
                     verified_prefix_matches_source(io, &backup_source,
                                                    current.resume_block))
            {
                source = backup_source;
                source_selected = 1;
            }

            if (!source_selected)
            {
                recovery_result = validate_external_source(io, &current,
                                                            SOURCE_RECOVERY,
                                                            &recovery_source);
                if (current.resume_block == 0u && recovery_result == SOURCE_OK)
                {
                    source = recovery_source;
                    source_selected = 1;
                }
                else if (current.resume_block != 0u &&
                         recovery_result == SOURCE_OK &&
                         verified_prefix_matches_source(io, &recovery_source,
                                                        current.resume_block))
                {
                    source = recovery_source;
                    source_selected = 1;
                }
            }

            if (!source_selected)
            {
                bcb_t next;

                if (backup_result != SOURCE_OK && recovery_result != SOURCE_OK)
                {
                    return return_recovery(BOOT_STATE_STATUS_SLOT,
                                           &current, outcome);
                }
                source = backup_result == SOURCE_OK
                             ? backup_source
                             : recovery_source;
                next = current;
                next.resume_block = 0u;
                if (commit_record(io, &active, &current, &next) != 0)
                {
                    return return_hold(BOOT_STATE_STATUS_COMMIT,
                                       &current, outcome);
                }
            }

            copy_result = copy_source(io, &source, &active, &current);
            if (copy_result != BOOT_STATE_STATUS_OK)
            {
                return return_hold(copy_result, &current, outcome);
            }
            app_result = validate_internal_app(io, &app_header);
            if (app_result != BOOT_FW_OK ||
                !internal_matches_source(&app_header, &source))
            {
                return return_recovery(BOOT_STATE_STATUS_APP, &current, outcome);
            }
            if (commit_confirmed(io, &active, &current,
                                 app_header.version_code) != BOOT_STATE_STATUS_OK)
            {
                return return_hold(BOOT_STATE_STATUS_COMMIT, &current, outcome);
            }
            continue;
        }

        default:
            return return_recovery(BOOT_STATE_STATUS_BCB, &current, outcome);
        }
    }

    return return_hold(BOOT_STATE_STATUS_LOOP, &current, outcome);
}

boot_state_status_t boot_state_machine_accept_physical_recovery(
    const boot_state_io_t *io,
    boot_state_outcome_t *outcome)
{
    bcb_arbiter_result_t active;
    bcb_t current;
    boot_fw_header_t header;

    outcome_reset(outcome);
    if (io == NULL || io->bcb_hal == NULL || io->internal_read == NULL)
    {
        return return_hold(BOOT_STATE_STATUS_ARGUMENT, NULL, outcome);
    }
    if (validate_internal_app(io, &header) != BOOT_FW_OK)
    {
        return return_recovery(BOOT_STATE_STATUS_APP, NULL, outcome);
    }

    memset(&current, 0, sizeof(current));
    active = bcb_arbiter(io->bcb_hal, &current);
    if (active == BCB_ARBITER_ERROR)
    {
        return return_recovery(BOOT_STATE_STATUS_BCB, NULL, outcome);
    }
    if (commit_confirmed(io, &active, &current,
                         header.version_code) != BOOT_STATE_STATUS_OK)
    {
        return return_hold(BOOT_STATE_STATUS_COMMIT, &current, outcome);
    }
    return return_jump(&current, &header, outcome);
}
