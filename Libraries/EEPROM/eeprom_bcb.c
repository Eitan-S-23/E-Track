/*
 * eeprom_bcb.c —— OTA Boot Control Block (BCB) 双块安全写事务 + seq 仲裁
 *
 * 契约唯一依据: docs/ota-binary-contracts.md v1.0 §3 / §0.2 / §0.4。
 * 设计见 docs/ota-exec-notes/P0-4-eeprom-bcb.md。
 *
 * 红线: 不写 byte 255 (0xFF 处 0x55 初始化魔数);不直接调 Wire;
 *      通过 bcb_hal_t 注入端口,以便 boot/App 共用本源。
 */
#include "eeprom_bcb.h"
#include <string.h>

/* ============================================================
 * CRC32-IEEE (契约 §0.2)
 * 多项式反射 0xEDB88320, 初值 0xFFFFFFFF, 输入输出反射, 异或出 0xFFFFFFFF。
 * 与 zlib.crc32 / vendor bsdiff/lib/crc32.c / binascii.crc32 同参数。
 * 表生成与运行时一致,P0-3 acceptance 已用 RAW_CONTRACT_AUDIT 验证算法一致。
 * ============================================================ */

static uint32_t crc32_table[256];
static int crc32_table_ready = 0;

static void crc32_init_table(void)
{
    for (uint32_t i = 0; i < 256u; i++)
    {
        uint32_t c = i;
        for (uint32_t k = 0; k < 8u; k++)
        {
            c = (c & 1u) ? (0xEDB88320u ^ (c >> 1)) : (c >> 1);
        }
        crc32_table[i] = c;
    }
    crc32_table_ready = 1;
}

uint32_t bcb_crc32(const uint8_t* data, uint16_t len)
{
    if (!crc32_table_ready)
    {
        crc32_init_table();
    }
    uint32_t crc = 0xFFFFFFFFu;
    for (uint16_t i = 0; i < len; i++)
    {
        crc = crc32_table[(crc ^ data[i]) & 0xFFu] ^ (crc >> 8);
    }
    return crc ^ 0xFFFFFFFFu;
}

/* ============================================================
 * 序列化 / 反序列化 (契约 §3.1, 小端, 禁 struct memcpy)
 * ============================================================ */

static void put_u16le(uint8_t* p, uint16_t v)
{
    p[0] = (uint8_t)(v & 0xFFu);
    p[1] = (uint8_t)((v >> 8) & 0xFFu);
}

static void put_u32le(uint8_t* p, uint32_t v)
{
    p[0] = (uint8_t)(v & 0xFFu);
    p[1] = (uint8_t)((v >> 8) & 0xFFu);
    p[2] = (uint8_t)((v >> 16) & 0xFFu);
    p[3] = (uint8_t)((v >> 24) & 0xFFu);
}

static uint16_t get_u16le(const uint8_t* p)
{
    return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

static uint32_t get_u32le(const uint8_t* p)
{
    return (uint32_t)p[0]
         | ((uint32_t)p[1] << 8)
         | ((uint32_t)p[2] << 16)
         | ((uint32_t)p[3] << 24);
}

void bcb_serialize(const bcb_t* bcb, uint8_t out[BCB_SIZE])
{
    /* off 0..3 magic */
    put_u32le(out + 0, bcb->magic);
    /* off 4 schema, off 5 state, off 6 boot_try, off 7 copy_phase */
    out[4] = bcb->schema_ver;
    out[5] = bcb->state;
    out[6] = bcb->boot_try;
    out[7] = bcb->copy_phase;
    /* off 8 seq, off 10 resume_block */
    put_u16le(out + 8, bcb->seq);
    put_u16le(out + 10, bcb->resume_block);
    /* off 12..43 各 u32 字段 */
    put_u32le(out + 12, bcb->cand_addr);
    put_u32le(out + 16, bcb->cand_len);
    put_u32le(out + 20, bcb->cand_crc32);
    put_u32le(out + 24, bcb->cand_vcode);
    put_u32le(out + 28, bcb->cur_vcode);
    put_u32le(out + 32, bcb->backup_len);
    put_u32le(out + 36, bcb->backup_crc32);
    put_u32le(out + 40, bcb->backup_vcode);
    /* off 44..55 pad = 0xFF */
    memset(out + 44, 0xFF, 12);
    /* off 56..59 reserved = 0 */
    put_u32le(out + 56, bcb->reserved);
    /* off 60..63 crc32 覆盖 off 0..59 */
    uint32_t crc = bcb_crc32(out, BCB_CRC_REGION_LEN);
    put_u32le(out + 60, crc);
}

void bcb_deserialize(const uint8_t in[BCB_SIZE], bcb_t* out)
{
    out->magic        = get_u32le(in + 0);
    out->schema_ver   = in[4];
    out->state        = in[5];
    out->boot_try     = in[6];
    out->copy_phase   = in[7];
    out->seq          = get_u16le(in + 8);
    out->resume_block = get_u16le(in + 10);
    out->cand_addr    = get_u32le(in + 12);
    out->cand_len     = get_u32le(in + 16);
    out->cand_crc32   = get_u32le(in + 20);
    out->cand_vcode   = get_u32le(in + 24);
    out->cur_vcode    = get_u32le(in + 28);
    out->backup_len   = get_u32le(in + 32);
    out->backup_crc32 = get_u32le(in + 36);
    out->backup_vcode = get_u32le(in + 40);
    /* pad/reserved 不参与逻辑,略 */
    out->reserved     = get_u32le(in + 56);
    out->crc32        = get_u32le(in + 60);
}

int bcb_is_valid(const uint8_t raw[BCB_SIZE])
{
    bcb_t b;
    bcb_deserialize(raw, &b);
    if (b.magic != BCB_MAGIC)
    {
        return 0;
    }
    if (b.schema_ver != BCB_SCHEMA_VER)
    {
        return 0;
    }
    uint32_t crc = bcb_crc32(raw, BCB_CRC_REGION_LEN);
    return (crc == b.crc32) ? 1 : 0;
}

/* ============================================================
 * 仲裁 (契约 §3.2)
 * ============================================================ */

static int read_block(const bcb_hal_t* hal, uint8_t addr, uint8_t raw[BCB_SIZE])
{
    if (!hal || !hal->read_buffer)
    {
        return -1;
    }
    return hal->read_buffer(addr, raw, BCB_SIZE);
}

bcb_arbiter_result_t bcb_arbiter(const bcb_hal_t* hal, bcb_t* out_active)
{
    uint8_t rawA[BCB_SIZE];
    uint8_t rawB[BCB_SIZE];
    bcb_t a, b;

    if (read_block(hal, BCB_A_ADDR, rawA) != 0)
    {
        return BCB_ARBITER_ERROR;
    }
    if (read_block(hal, BCB_B_ADDR, rawB) != 0)
    {
        return BCB_ARBITER_ERROR;
    }

    int a_ok = bcb_is_valid(rawA);
    int b_ok = bcb_is_valid(rawB);

    bcb_arbiter_result_t chosen = BCB_ARBITER_NONE;
    const uint8_t* chosen_raw = NULL;

    if (a_ok && b_ok)
    {
        bcb_deserialize(rawA, &a);
        bcb_deserialize(rawB, &b);
        /* 契约 §3.2: (int16)(a.seq - b.seq) > 0 → A 新;相等取 A。
         * 差按 16bit 回绕后再解释为有符号 (uint16_t 减法自然回绕)。
         * 注意: a.seq - b.seq 在 C 中会提升为 int, 须显式截回 uint16_t
         * 再转 int16_t, 否则 5-65530=-65525 不会被解释为回绕后的 +11。 */
        uint16_t diff16 = (uint16_t)(a.seq - b.seq);
        int16_t diff = (int16_t)diff16;
        if (diff >= 0)
        {
            chosen = BCB_ARBITER_A;
            chosen_raw = rawA;
        }
        else
        {
            chosen = BCB_ARBITER_B;
            chosen_raw = rawB;
        }
    }
    else if (a_ok)
    {
        chosen = BCB_ARBITER_A;
        chosen_raw = rawA;
    }
    else if (b_ok)
    {
        chosen = BCB_ARBITER_B;
        chosen_raw = rawB;
    }
    else
    {
        /* 双坏 → recovery */
        chosen = BCB_ARBITER_NONE;
        chosen_raw = NULL;
    }

    if (out_active && chosen_raw)
    {
        bcb_deserialize(chosen_raw, out_active);
    }
    return chosen;
}

/* ============================================================
 * 单次安全写事务 (契约 §3.2 写序 + §3.4 R4-1 原子写)
 * ============================================================ */

int bcb_commit(const bcb_hal_t* hal,
               bcb_arbiter_result_t active_now,
               const bcb_t* new_bcb)
{
    if (!hal || !hal->write_buffer || !hal->read_buffer || !new_bcb)
    {
        return BCB_COMMIT_ERR_PARAM;
    }
    if (new_bcb->magic != BCB_MAGIC || new_bcb->schema_ver != BCB_SCHEMA_VER)
    {
        return BCB_COMMIT_ERR_PARAM;
    }
    if (active_now != BCB_ARBITER_NONE &&
        active_now != BCB_ARBITER_A &&
        active_now != BCB_ARBITER_B)
    {
        return BCB_COMMIT_ERR_PARAM;
    }

    bcb_t active;
    bcb_arbiter_result_t observed = bcb_arbiter(hal, &active);
    if (observed == BCB_ARBITER_ERROR)
    {
        return BCB_COMMIT_ERR_ARBITER;
    }
    uint8_t target_addr;
    bcb_t transaction = *new_bcb;

    if (active_now == BCB_ARBITER_NONE)
    {
        if (observed != BCB_ARBITER_NONE)
        {
            return BCB_COMMIT_ERR_ACTIVE;
        }
        target_addr = BCB_A_ADDR;
        transaction.seq = 0;
    }
    else
    {
        if (observed != active_now)
        {
            return BCB_COMMIT_ERR_ACTIVE;
        }
        target_addr = (active_now == BCB_ARBITER_A) ? BCB_B_ADDR : BCB_A_ADDR;
        transaction.seq = (uint16_t)(active.seq + 1u);
    }
    /* The core owns seq advancement; callers only provide the next state. */
    uint8_t buf[BCB_SIZE];
    bcb_serialize(&transaction, buf);

    /* 写非活动块整 64B (HAL 内部逐页 + ACK polling + 写后读回比对)。 */
    if (hal->write_buffer(target_addr, buf, BCB_SIZE) != 0)
    {
        return BCB_COMMIT_ERR_WRITE;
    }

    /* 独立读回 64B 逐字节比对 (契约 §3.3, 不依赖 write_buffer 内部读回)。 */
    uint8_t readback[BCB_SIZE];
    if (hal->read_buffer(target_addr, readback, BCB_SIZE) != 0)
    {
        return BCB_COMMIT_ERR_READBACK;
    }
    if (memcmp(readback, buf, BCB_SIZE) != 0)
    {
        return BCB_COMMIT_ERR_VERIFY;
    }

    return BCB_COMMIT_OK;
}

void bcb_make_idle(bcb_t* out, uint32_t cur_vcode)
{
    if (!out)
    {
        return;
    }
    memset(out, 0, sizeof(*out));
    out->magic      = BCB_MAGIC;
    out->schema_ver = BCB_SCHEMA_VER;
    out->state      = BCB_STATE_IDLE;
    out->boot_try   = BCB_INIT_BOOT_TRY;
    out->copy_phase = BCB_COPY_NONE;
    out->seq        = 0;
    out->resume_block = 0;
    out->cur_vcode  = cur_vcode;
    out->reserved   = 0;
    /* crc32 由 bcb_serialize 在序列化时计算并回填,此处内存视图先置 0。 */
    out->crc32      = 0;
    /* pad 视图保持 0 (序列化时填 0xFF)。 */
}
