/*
 * ota_backup.c —— P2-5 backup 自拷 + candidate/backup 槽头 + BCB=STAGED 事务。
 *
 * 顺序严格执行冻结契约：candidate 全镜像复核（CRC+fw_header 全项+元数据）
 * → backup 槽头扇区先擦（marker 保持 0xFF）→ 分块自拷（4KB，禁整镜像 malloc）
 * → backup ETSL 头字段写读回 → backup commit_marker 最后单独写 →
 * candidate 槽头扇区重擦（marker→0xFF，禁止复用旧 marker）→ candidate ETSL
 * 头字段/与 marker 同理 → 双槽复核（与 boot 消费端等价）→
 * `bcb_commit(STAGED)` 原子提交并读回。提交前失败不写 EEPROM；提交期读回
 * 故障按 ota_backup_commit_state_t 分类（verified STAGED/verified CONFIRMED/
 * unknown），unknown 返回 OTA_BACKUP_ERR_COMMIT_AMBIGUOUS 禁止上层覆盖。
 */
#include "OTA/ota_backup.h"

#include "OTA/ota_layout.h"
#include "OTA/ota_slot_header.h"
#include "boot_crypto.h"
#include "boot_fw_header.h"

#include <string.h>

#define OTA_BACKUP_BLOCK_SIZE 4096u
#define OTA_BACKUP_MIN_IMAGE  (OTA_FW_HEADER_OFFSET + OTA_FW_HEADER_SIZE)
#define OTA_BACKUP_BYTE_FF    0xFFu

/* 自拷块缓冲：固定 4KB 静态区，禁止整镜像 malloc（契约 §0.4 / §10）。 */
static uint8_t g_backup_block[OTA_BACKUP_BLOCK_SIZE];

typedef struct ota_backup_reader_t
{
    const ota_backup_io_t *io;
    uint32_t flash_base;  /* 0 = 内部 App（走 app_read），否则外部绝对地址 */
    int external;
} ota_backup_reader_t;

static uint32_t align_up_4k(uint32_t value)
{
    return (value + OTA_BACKUP_BLOCK_SIZE - 1u) &
           ~(OTA_BACKUP_BLOCK_SIZE - 1u);
}

static int image_read_bridge(void *ctx, uint32_t offset,
                             uint8_t *dst, size_t len)
{
    ota_backup_reader_t *reader = (ota_backup_reader_t *)ctx;

    if (reader == 0 || reader->io == 0 || dst == 0 ||
        len > OTA_APP_LENGTH || offset > OTA_APP_LENGTH - (uint32_t)len)
    {
        return -1;
    }
    if (reader->external)
    {
        return reader->io->flash_read(reader->io->ctx,
                                      reader->flash_base + offset,
                                      dst, (uint32_t)len);
    }
    return reader->io->app_read(reader->io->ctx, offset, dst,
                                (uint32_t)len);
}

static int validate_image(const ota_backup_io_t *io,
                          int external,
                          uint32_t flash_base,
                          boot_fw_header_t *out_header)
{
    ota_backup_reader_t reader_ctx;
    boot_image_reader_t reader;
    boot_fw_expectations_t expectations;

    reader_ctx.io = io;
    reader_ctx.flash_base = flash_base;
    reader_ctx.external = external;
    reader.read = image_read_bridge;
    reader.ctx = &reader_ctx;
    boot_fw_default_expectations(&expectations);
    return boot_fw_header_validate(&reader, &expectations, out_header);
}

/* 读 candidate/backup 槽的 ETSL 头并做完整 getattr（magic/marker/type/界）。 */
static int read_slot_header(const ota_backup_io_t *io,
                            uint32_t slot_base,
                            uint8_t expected_type,
                            ota_slot_header_t *out)
{
    uint8_t raw[OTA_SLOT_HEADER_BYTES];

    if (io->flash_read(io->ctx, slot_base, raw, sizeof(raw)) != 0)
    {
        return 0;
    }
    return ota_slot_header_parse(raw, expected_type, out) == 0 ? 1 : 0;
}

/* 对槽 [payload_base, payload_base+payload_len) 单遍算 CRC32。 */
static int slot_payload_crc(const ota_backup_io_t *io,
                            uint32_t payload_base,
                            uint32_t payload_len,
                            uint32_t *out_crc)
{
    uint8_t chunk[256];
    boot_crc32_ctx_t crc;
    uint32_t offset = 0u;

    boot_crc32_init(&crc);
    while (offset < payload_len)
    {
        uint32_t take = payload_len - offset;

        if (take > sizeof(chunk))
        {
            take = (uint32_t)sizeof(chunk);
        }
        if (io->flash_read(io->ctx, payload_base + offset,
                           chunk, take) != 0)
        {
            return 0;
        }
        boot_crc32_update(&crc, chunk, take);
        offset += take;
    }
    *out_crc = boot_crc32_final(&crc);
    return 1;
}

/* 程序化写入 len 字节并读回逐字节比对。flash 写成功即计入 program_count
 * （读回失败也反映“实际已发生写入”，阻断 8；失败返回 0 但计数已 +1）。 */
static int program_verify(const ota_backup_io_t *io,
                          uint32_t address,
                          const uint8_t *src,
                          uint32_t len,
                          uint32_t *program_count)
{
    uint8_t readback[256];
    uint32_t offset;

    if (io->flash_program(io->ctx, address, src, len) != 0)
    {
        return 0;
    }
    if (program_count != 0)
    {
        (*program_count)++;
    }
    for (offset = 0u; offset < len;)
    {
        uint32_t take = len - offset;

        if (take > sizeof(readback))
        {
            take = (uint32_t)sizeof(readback);
        }
        if (io->flash_read(io->ctx, address + offset,
                           readback, take) != 0 ||
            memcmp(readback, src + offset, take) != 0)
        {
            return 0;
        }
        offset += take;
    }
    return 1;
}

/* 一次性把 32B ETSL 头写入槽起（slot_base=EXT_*）并读回校验；
 * marker 分成两个 flash_program：最后单独写 commit_marker。 */
static int commit_slot_header(const ota_backup_io_t *io,
                              uint32_t slot_base,
                              const ota_slot_header_t *slot,
                              uint32_t *program_count)
{
    uint8_t fields[OTA_SLOT_HEADER_BYTES];
    uint8_t marker_bytes[4];
    uint32_t marker_value;
    unsigned byte;

    marker_value = OTA_SLOT_MARKER_COMMIT;
    for (byte = 0u; byte < 4u; ++byte)
    {
        marker_bytes[byte] = (uint8_t)(marker_value >> (byte * 8u));
    }

    /* 契约 §4.3 第 5 步：commit_marker 最后单独写（禁止与其他头字段一次同时
     * 提交）。故分两次独立 flash_program：先写除 marker 外的 28B 并读回，
     * 再单独写 marker 4B 并读回。 */
    ota_slot_header_serialize_partial(slot, fields);
    if (!program_verify(io, slot_base, fields,
                        OTA_SLOT_HEADER_BYTES - 4u, program_count))
    {
        return 0;
    }
    return program_verify(io, slot_base + OTA_SLOT_HEADER_BYTES - 4u,
                          marker_bytes, sizeof(marker_bytes), program_count);
}

/* 复核槽内 payload 的 fw_header（与 boot validate_external_source 等价）：
 *   - 全项校验（magic/header_crc/SHA 双零/hw_rev/layout/min_boot/向量表）
 *   - header.image_len == slot.payload_len
 *   - header.version_code == slot.version_code
 *   - header.image_sha256[:8] == slot.sha8
 * 返回 0 成功，非 0 失败。 */
static int slot_fw_header_matches(const ota_backup_io_t *io,
                                  uint32_t slot_base,
                                  const ota_slot_header_t *slot)
{
    boot_fw_header_t header;

    if (validate_image(io, 1, slot_base + OTA_SLOT_HEADER_SIZE,
                       &header) != BOOT_FW_OK)
    {
        return 0;
    }
    return header.image_len == slot->payload_len &&
           header.version_code == slot->version_code &&
           memcmp(header.image_sha256, slot->sha8, sizeof(slot->sha8)) == 0;
}

/* 提交 STAGED 前的双槽复核，与 boot 消费端（boot_state_machine.c
 * validate_external_source）等价：
 *   - ETSL magic/marker/type 已由 read_slot_header 校验
 *   - payload_len 界与期望一致
 *   - payload 全镜像 CRC 与期望一致（本函数与 slot_header 双计算）
 *   - 槽内 fw_header 全项 + image_len/vcode/sha8 与 ETSL 一致
 *   - 若 require_newer_than != 0：slot vcode 必须 > require_newer_than
 *     （拒绝过期/降级 candidate）
 * 全部满足返回 0。 */
static int verify_slot_final(const ota_backup_io_t *io,
                             uint32_t slot_base,
                             uint8_t slot_type,
                             uint32_t expected_len,
                             uint32_t expected_crc,
                             uint32_t expected_vcode,
                             const uint8_t expected_sha8[8],
                             uint32_t require_newer_than)
{
    ota_slot_header_t slot;
    uint32_t crc;

    if (!read_slot_header(io, slot_base, slot_type, &slot) || !slot.committed)
    {
        return 0;
    }
    if (slot.payload_len != expected_len ||
        slot.payload_crc32 != expected_crc ||
        slot.version_code != expected_vcode ||
        memcmp(slot.sha8, expected_sha8, sizeof(slot.sha8)) != 0)
    {
        return 0;
    }
    if (require_newer_than != 0u && slot.version_code <= require_newer_than)
    {
        return 0;
    }
    if (!slot_payload_crc(io, slot_base + OTA_SLOT_HEADER_SIZE,
                          slot.payload_len, &crc) ||
        crc != expected_crc)
    {
        return 0;
    }
    return slot_fw_header_matches(io, slot_base, &slot);
}

/* BCB 提交后分类（阻断 6）。写一旦发生，读回失败不代表“未提交”；必须再次
 * 仲裁后归类。返回的成功/失败码与 info->commit_state 同步。 */
static int bcb_fields_match(const bcb_t *a, const bcb_t *b)
{
    return a->magic == b->magic &&
           a->schema_ver == b->schema_ver &&
           a->state == b->state &&
           a->boot_try == b->boot_try &&
           a->copy_phase == b->copy_phase &&
           a->resume_block == b->resume_block &&
           a->cand_addr == b->cand_addr &&
           a->cand_len == b->cand_len &&
           a->cand_crc32 == b->cand_crc32 &&
           a->cand_vcode == b->cand_vcode &&
           a->cur_vcode == b->cur_vcode &&
           a->backup_len == b->backup_len &&
           a->backup_crc32 == b->backup_crc32 &&
           a->backup_vcode == b->backup_vcode;
}

static ota_backup_result_t classify_commit(const bcb_hal_t *bcb_hal,
                                           const bcb_t *next,
                                           ota_backup_info_t *info,
                                           ota_backup_info_t *out)
{
    bcb_t checked;
    bcb_arbiter_result_t observed;

    observed = bcb_arbiter(bcb_hal, &checked);
    if (observed == BCB_ARBITER_ERROR || observed == BCB_ARBITER_NONE)
    {
        info->commit_state = OTA_BACKUP_COMMIT_UNKNOWN;
        if (out != 0)
        {
            *out = *info;
        }
        return OTA_BACKUP_ERR_COMMIT_AMBIGUOUS;
    }
    if (checked.state == BCB_STATE_STAGED &&
        bcb_fields_match(&checked, next))
    {
        info->commit_state = OTA_BACKUP_COMMIT_VERIFIED_STAGED;
        if (out != 0)
        {
            *out = *info;
        }
        return OTA_BACKUP_OK;
    }
    if (checked.state == BCB_STATE_CONFIRMED &&
        checked.cur_vcode == next->cur_vcode)
    {
        /* 复裁确认活动块仍是 CONFIRMED：本次提交未生效，可安全重试。 */
        info->commit_state = OTA_BACKUP_COMMIT_VERIFIED_CONFIRMED;
        if (out != 0)
        {
            *out = *info;
        }
        return OTA_BACKUP_ERR_COMMIT;
    }
    /* 其他状态（APPLYING/TEST_BOOT/ROLLBACK）或字段不符 → unknown。 */
    info->commit_state = OTA_BACKUP_COMMIT_UNKNOWN;
    if (out != 0)
    {
        *out = *info;
    }
    return OTA_BACKUP_ERR_COMMIT_AMBIGUOUS;
}

ota_backup_result_t ota_backup_stage(const ota_backup_io_t *io,
                                     const bcb_hal_t *bcb_hal,
                                     ota_backup_info_t *out)
{
    bcb_arbiter_result_t active;
    bcb_t current;
    boot_fw_header_t app_header;
    boot_fw_header_t cand_header;
    ota_backup_info_t info;
    ota_backup_result_t result;
    boot_crc32_ctx_t backup_crc;
    uint32_t backup_cursor;
    uint32_t candidate_len;
    uint32_t candidate_crc = 0u;
    uint32_t backup_crc32;
    uint32_t payload_end;
    ota_slot_header_t cand_slot;
    ota_slot_header_t backup_slot;
    bcb_t next;
    uint32_t erase_address;

    memset(&info, 0, sizeof(info));
    info.commit_state = OTA_BACKUP_COMMIT_NONE;
    if (io == 0 || bcb_hal == 0 ||
        io->app_read == 0 || io->flash_read == 0 ||
        io->flash_erase_4k == 0 || io->flash_program == 0)
    {
        return OTA_BACKUP_ERR_ARGUMENT;
    }

    /* 1) fail-closed 重新仲裁：只有 CONFIRMED 才允许发起新 OTA / 覆盖 backup */
    active = bcb_arbiter(bcb_hal, &current);
    if (active == BCB_ARBITER_ERROR || active == BCB_ARBITER_NONE)
    {
        result = OTA_BACKUP_ERR_EEPROM;
        if (out != 0) *out = info;
        return result;
    }
    if (current.state != BCB_STATE_CONFIRMED)
    {
        result = OTA_BACKUP_ERR_STATE;
        if (out != 0) *out = info;
        return result;
    }

    /* 2) 读取并验证当前内部 App fw_header（真实 image_len/版本/SHA） */
    result = OTA_BACKUP_ERR_APP_HEADER;
    if (validate_image(io, 0, 0u, &app_header) != BOOT_FW_OK ||
        app_header.image_len < OTA_BACKUP_MIN_IMAGE)
    {
        if (out != 0) *out = info;
        return result;
    }
    /* 2b) 当前 CONFIRMED BCB cur_vcode 必须等于当前 App fw_header 的 vcode。
     * 不一致说明 BCB 已过期/错位，禁止据此自拷备份或提交 STAGED。 */
    if (current.cur_vcode != app_header.version_code)
    {
        result = OTA_BACKUP_ERR_APP_HEADER;
        if (out != 0) *out = info;
        return result;
    }

    /* 3) 复核候选镜像（ETSL 未写，直接按 payload 域 + fw_header 全项）。
     * candidate 版本必须严格高于当前版（拒绝降级/过期 candidate）。 */
    result = OTA_BACKUP_ERR_CANDIDATE_READ;
    if (validate_image(io, 1, OTA_EXT_CANDIDATE + OTA_SLOT_HEADER_SIZE,
                       &cand_header) != BOOT_FW_OK)
    {
        result = OTA_BACKUP_ERR_CANDIDATE_HEADER;
        if (out != 0) *out = info;
        return result;
    }
    candidate_len = cand_header.image_len;
    if (candidate_len < OTA_BACKUP_MIN_IMAGE ||
        !slot_payload_crc(io, OTA_EXT_CANDIDATE + OTA_SLOT_HEADER_SIZE,
                          candidate_len, &candidate_crc))
    {
        if (out != 0) *out = info;
        return result;
    }
    if (cand_header.version_code <= app_header.version_code)
    {
        result = OTA_BACKUP_ERR_CANDIDATE_CRC;
        if (out != 0) *out = info;
        return result;
    }

    info.candidate_len = candidate_len;
    info.candidate_crc32 = candidate_crc;
    info.candidate_vcode = cand_header.version_code;
    memcpy(info.candidate_sha8, cand_header.image_sha256,
           sizeof(info.candidate_sha8));
    info.backup_len = app_header.image_len;
    info.backup_vcode = app_header.version_code;
    memcpy(info.backup_sha8, app_header.image_sha256,
           sizeof(info.backup_sha8));

    /* 4) backup 槽头扇区先擦（marker 保持擦除态 0xFF） */
    result = OTA_BACKUP_ERR_ERASE;
    if (io->flash_erase_4k(io->ctx, OTA_EXT_BACKUP) != 0)
    {
        if (out != 0) *out = info;
        return result;
    }
    info.erase_count++;
    payload_end = align_up_4k(info.backup_len);
    for (erase_address = OTA_EXT_BACKUP + OTA_SLOT_HEADER_SIZE;
         erase_address < OTA_EXT_BACKUP + OTA_SLOT_HEADER_SIZE + payload_end;
         erase_address += OTA_SLOT_HEADER_SIZE)
    {
        if (io->flash_erase_4k(io->ctx, erase_address) != 0)
        {
            if (out != 0) *out = info;
            return result;
        }
        info.erase_count++;
    }

    /* 5) 分块自拷：4KB 块读当前 App → 更新 CRC → 写 backup → 读回比对。
     * 禁止整镜像 malloc；源读失败单块即停。 */
    result = OTA_BACKUP_ERR_WRITE;
    boot_crc32_init(&backup_crc);
    for (backup_cursor = 0u; backup_cursor < info.backup_len;)
    {
        uint32_t take = info.backup_len - backup_cursor;

        if (take > OTA_BACKUP_BLOCK_SIZE)
        {
            take = OTA_BACKUP_BLOCK_SIZE;
        }
        memset(g_backup_block, OTA_BACKUP_BYTE_FF, sizeof(g_backup_block));
        if (io->app_read(io->ctx, backup_cursor, g_backup_block, take) != 0)
        {
            result = OTA_BACKUP_ERR_APP_HEADER;
            if (out != 0) *out = info;
            return result;
        }
        boot_crc32_update(&backup_crc, g_backup_block, take);
        if (io->flash_program(io->ctx,
                              OTA_EXT_BACKUP + OTA_SLOT_HEADER_SIZE +
                                  backup_cursor,
                              g_backup_block, take) != 0)
        {
            if (out != 0) *out = info;
            return OTA_BACKUP_ERR_WRITE;
        }
        info.program_count++;
        result = OTA_BACKUP_ERR_READBACK;
        {
            /* 块粒度过大时分段读回比对，避免一次性大缓冲入栈 */
            uint8_t verify_chunk[512];
            uint32_t chunk_offset;

            for (chunk_offset = 0u; chunk_offset < take;)
            {
                uint32_t vtake = take - chunk_offset;

                if (vtake > sizeof(verify_chunk))
                {
                    vtake = (uint32_t)sizeof(verify_chunk);
                }
                if (io->flash_read(io->ctx,
                                   OTA_EXT_BACKUP + OTA_SLOT_HEADER_SIZE +
                                       backup_cursor + chunk_offset,
                                   verify_chunk, vtake) != 0 ||
                    memcmp(verify_chunk, g_backup_block + chunk_offset,
                           vtake) != 0)
                {
                    if (out != 0) *out = info;
                    return result;
                }
                chunk_offset += vtake;
            }
        }
        backup_cursor += take;
    }
    backup_crc32 = boot_crc32_final(&backup_crc);
    info.backup_crc32 = backup_crc32;

    /* 6) backup ETSL 头字段 + marker 单独最后写 */
    result = OTA_BACKUP_ERR_SLOT_HEADER;
    memset(&backup_slot, 0, sizeof(backup_slot));
    backup_slot.slot_type = OTA_SLOT_TYPE_BACKUP;
    backup_slot.payload_len = info.backup_len;
    backup_slot.payload_crc32 = backup_crc32;
    backup_slot.version_code = info.backup_vcode;
    memcpy(backup_slot.sha8, info.backup_sha8, sizeof(backup_slot.sha8));
    backup_slot.committed = 1;
    if (!commit_slot_header(io, OTA_EXT_BACKUP, &backup_slot,
                            &info.program_count))
    {
        if (out != 0) *out = info;
        return result;
    }

    /* 7) candidate ETSL 头字段 + marker 最后单独写。
     * 每次提交前必须重擦 candidate 槽头扇区（marker→0xFF）；不能依赖上一次
     * candidate_prepare 的擦除，也不能在 BCB 提交失败后复用旧 marker（§4.3）。 */
    if (io->flash_erase_4k(io->ctx, OTA_EXT_CANDIDATE) != 0)
    {
        result = OTA_BACKUP_ERR_ERASE;
        if (out != 0) *out = info;
        return result;
    }
    info.erase_count++;
    memset(&cand_slot, 0, sizeof(cand_slot));
    cand_slot.slot_type = OTA_SLOT_TYPE_CANDIDATE;
    cand_slot.payload_len = info.candidate_len;
    cand_slot.payload_crc32 = info.candidate_crc32;
    cand_slot.version_code = info.candidate_vcode;
    memcpy(cand_slot.sha8, info.candidate_sha8, sizeof(cand_slot.sha8));
    cand_slot.committed = 1;
    if (!commit_slot_header(io, OTA_EXT_CANDIDATE, &cand_slot,
                            &info.program_count))
    {
        result = OTA_BACKUP_ERR_SLOT_HEADER;
        if (out != 0) *out = info;
        return result;
    }

    /* 8) 提交前双槽复核（ETSL + CRC + fw_header 元数据一致 + 拒绝降级） */
    result = OTA_BACKUP_ERR_SLOT_VERIFY;
    if (!verify_slot_final(io, OTA_EXT_CANDIDATE, OTA_SLOT_TYPE_CANDIDATE,
                           info.candidate_len, info.candidate_crc32,
                           info.candidate_vcode, info.candidate_sha8,
                           app_header.version_code) ||
        !verify_slot_final(io, OTA_EXT_BACKUP, OTA_SLOT_TYPE_BACKUP,
                           info.backup_len, info.backup_crc32,
                           info.backup_vcode, info.backup_sha8, 0u))
    {
        if (out != 0) *out = info;
        return result;
    }

    /* 9) 原子提交 BCB=STAGED（bcb_commit 核心强制 seq+1，写非活动块） */
    next = current;
    next.state = BCB_STATE_STAGED;
    next.boot_try = BCB_INIT_BOOT_TRY;   /* 契约 §3.1 初 3；copy_phase=0 */
    next.copy_phase = BCB_COPY_NONE;
    next.resume_block = 0u;
    next.cand_addr = OTA_EXT_CANDIDATE + OTA_SLOT_HEADER_SIZE;
    next.cand_len = info.candidate_len;
    next.cand_crc32 = info.candidate_crc32;
    next.cand_vcode = info.candidate_vcode;
    next.cur_vcode = info.backup_vcode;  /* 升级完成前仍是当前版 */
    next.backup_len = info.backup_len;
    next.backup_crc32 = info.backup_crc32;
    next.backup_vcode = info.backup_vcode;

    /* 10) 提交后分类：bcb_commit 触发 EEPROM 写后，读回故障必须再仲裁归类，
     * 不得直接判定“仍 CONFIRMED”。（阻断 6） */
    (void)bcb_commit(bcb_hal, active, &next);
    return classify_commit(bcb_hal, &next, &info, out);
}

const char *ota_backup_result_name(ota_backup_result_t result)
{
    switch (result)
    {
    case OTA_BACKUP_OK: return "ok";
    case OTA_BACKUP_ERR_ARGUMENT: return "argument";
    case OTA_BACKUP_ERR_STATE: return "state";
    case OTA_BACKUP_ERR_EEPROM: return "eeprom";
    case OTA_BACKUP_ERR_APP_HEADER: return "app_header";
    case OTA_BACKUP_ERR_CANDIDATE_READ: return "candidate_read";
    case OTA_BACKUP_ERR_CANDIDATE_HEADER: return "candidate_header";
    case OTA_BACKUP_ERR_CANDIDATE_CRC: return "candidate_crc";
    case OTA_BACKUP_ERR_ERASE: return "erase";
    case OTA_BACKUP_ERR_WRITE: return "write";
    case OTA_BACKUP_ERR_READBACK: return "readback";
    case OTA_BACKUP_ERR_SLOT_HEADER: return "slot_header";
    case OTA_BACKUP_ERR_SLOT_VERIFY: return "slot_verify";
    case OTA_BACKUP_ERR_COMMIT: return "commit";
    case OTA_BACKUP_ERR_VERIFY: return "verify";
    case OTA_BACKUP_ERR_DISABLED: return "disabled";
    case OTA_BACKUP_ERR_COMMIT_AMBIGUOUS: return "commit_ambiguous";
    default: return "unknown";
    }
}
