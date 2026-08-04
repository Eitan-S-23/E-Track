/*
 * P2-5 backup 自拷与 STAGED 提交宿主测试。
 *
 * 覆盖（对应卡内宿主测试要求 1-6）：
 *   T1  正常链：CONFIRMED + 合法 candidate → OTA_BACKUP_OK，STAGED 读回一致，
 *       candidate/backup ETSL(marker) 落位且字段与 BCB 逐项一致。
 *   T2  candidate 无效：backup 擦除数==0、编程数==0、BCB 零写入。
 *   T3  backup 擦除失败 / payloa 写失败 / 读回失败 / 槽头字段失败 / marker 失败
 *       各自不提交 STAGED，活动 BCB 保持 CONFIRMED。
 *   T4  marker-last 实际调用序：每个槽头区最后两次 flash_program 为
 *       28B 字段 + 4B marker；半写 backup（marker 写失败）解析返回未提交。
 *   T5  仅 CONFIRMED 可启动：TEST_BOOT/STAGED/APPLYING/ROLLBACK/双坏/EEPROM
 *       读失败全部拒绝且零副作用。
 *   T6  BCB commit 写失败/读回失败 → fail-closed（ERR_COMMIT）；提交后读回
 *       失败 → ERR_VERIFY；均不产生可用的 STAGED。
 */
#include "OTA/ota_backup.h"
#include "OTA/ota_slot_header.h"
#include "OTA/ota_layout.h"
#include "EEPROM/eeprom_bcb.h"
#include "boot_crypto.h"
#include "boot_fw_header.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum
{
    IMAGE_BYTES = 4096,
    MAX_IMAGE = 8192 + 512,        /* 多块回归最大镜像 */
    FLASH_BYTES = 0x200000,        /* candidate + backup 两槽窗口 */
    EEPROM_BYTES = 256,
    PROGRAM_LOG_MAX = 128
};

static uint8_t g_flash[FLASH_BYTES];
static uint8_t g_eeprom[EEPROM_BYTES];
static uint8_t g_current[MAX_IMAGE];
static uint8_t g_candidate[MAX_IMAGE];
static uint32_t g_current_len;     /* 本次用例的当前镜像长度（默认 IMAGE_BYTES） */
static uint32_t g_candidate_len;

static uint32_t g_program_log[PROGRAM_LOG_MAX][2];
static int g_program_log_count;
static uint32_t g_erase_count;
static uint32_t g_program_count;
static uint32_t g_eeprom_read_count;
static uint32_t g_eeprom_write_count;

static int g_fail_erase_addr;
static int g_fail_program_addr;
static int g_fail_program_done;
static int g_fail_read_addr;
static int g_fail_read_done;
static int g_eeprom_read_budget;   /* -1 不限 */
static int g_eeprom_write_fail;

static int checks;
static int failures;

static void check(const char* name, int condition)
{
    checks++;
    if(!condition)
    {
        failures++;
        fprintf(stderr, "FAIL: %s\n", name);
    }
}

/* 构造 image_len 大小合法镜像：向量表 + 0x400 fw_header（SHA 双零法 + CRC32）。
 * image_len 必须 >= OTA_FW_HEADER_OFFSET + OTA_FW_HEADER_SIZE。 */
static void build_valid_image_ex(uint8_t* out, uint32_t image_len,
                                 uint32_t vcode, const char* name)
{
    uint8_t sha[32];
    boot_sha256_ctx_t sha_ctx;
    uint8_t* header;
    uint32_t crc;

    memset(out, 0, image_len);
    /* 向量表：MSP 落 RAM（< 0x20080000 排他上界），reset 落 app 区（thumb 位） */
    out[0] = 0x00; out[1] = 0xF0; out[2] = 0x07; out[3] = 0x20;   /* 0x2007F000 */
    out[4] = 0x01; out[5] = 0x00; out[6] = 0x01; out[7] = 0x08;   /* 0x08010001 */

    header = out + OTA_FW_HEADER_OFFSET;
    memset(header, 0xFF, 96);
    memcpy(header + 0,  "ETFW", 4);
    header[4] = 1u;                       /* header_ver LE = 1 */
    header[5] = 0u;
    header[6] = 0u;
    header[7] = 0u;
    /* version_code LE */
    header[8]  = (uint8_t)(vcode & 0xFF);
    header[9]  = (uint8_t)((vcode >> 8) & 0xFF);
    header[10] = (uint8_t)((vcode >> 16) & 0xFF);
    header[11] = (uint8_t)((vcode >> 24) & 0xFF);
    memset(header + 12, 0, 16);   /* version_name 固定 0x00 填充，随后写 ASCIIZ */
    {
        size_t n;
        for(n = 0; n < strlen(name) && n < 16; n++)
        {
            header[12 + n] = (uint8_t)name[n];
        }
    }
    header[28] = 1; header[29] = 0; header[30] = 0; header[31] = 0; /* build_ts */
    header[32] = 1; header[33] = 0; header[34] = 0; header[35] = 0; /* hw_rev=1 */
    header[36] = (uint8_t)(image_len & 0xFF);
    header[37] = (uint8_t)((image_len >> 8) & 0xFF);
    header[38] = (uint8_t)((image_len >> 16) & 0xFF);
    header[39] = (uint8_t)((image_len >> 24) & 0xFF);
    memset(header + 40, 0, 32);             /* image_sha256 占位零 */
    header[72] = 1;                         /* layout_id */
    header[73] = 1;                         /* min_boot_ver */
    memset(header + 74, 0xFF, 18);
    memset(header + 92, 0, 4);              /* header_crc32 占位零 */

    /* SHA 双零法：image_sha256(40..71) 与 header_crc32(92..95) 按零参与 */
    boot_sha256_init(&sha_ctx);
    boot_sha256_update(&sha_ctx, out, image_len);
    boot_sha256_final(&sha_ctx, sha);
    memcpy(header + 40, sha, 32);

    crc = boot_crc32(header, 92);   /* 头部前 92B，覆盖 0x400..0x45B */
    header[92] = (uint8_t)(crc & 0xFF);
    header[93] = (uint8_t)((crc >> 8) & 0xFF);
    header[94] = (uint8_t)((crc >> 16) & 0xFF);
    header[95] = (uint8_t)((crc >> 24) & 0xFF);
}

/* 固定 4096B 变体（既有用例复用）。 */
static void build_valid_image(uint8_t* out, uint32_t vcode,
                              const char* name)
{
    build_valid_image_ex(out, IMAGE_BYTES, vcode, name);
}

/* ---- flash 仿真 ---- */
static int f_app_read(void* ctx, uint32_t off, uint8_t* dst, uint32_t len)
{
    (void)ctx;
    if(dst == 0 || len > g_current_len || off > g_current_len - len)
    {
        return -1;
    }
    memcpy(dst, g_current + off, len);
    return 0;
}

static int f_flash_read(void* ctx, uint32_t addr, uint8_t* dst, uint32_t len)
{
    (void)ctx;
    if(dst == 0 || addr > FLASH_BYTES || len > FLASH_BYTES - addr)
    {
        return -1;
    }
    if(g_fail_read_addr >= 0 && !g_fail_read_done &&
       addr == (uint32_t)g_fail_read_addr)
    {
        g_fail_read_done = 1;
        return -1;
    }
    memcpy(dst, g_flash + addr, len);
    return 0;
}

static int f_flash_erase(void* ctx, uint32_t addr)
{
    (void)ctx;
    if((addr & (OTA_SLOT_HEADER_SIZE - 1u)) != 0u ||
       addr > FLASH_BYTES || OTA_SLOT_HEADER_SIZE > FLASH_BYTES - addr)
    {
        return -1;
    }
    if(g_fail_erase_addr >= 0 && addr == (uint32_t)g_fail_erase_addr)
    {
        return -1;
    }
    memset(g_flash + addr, 0xFF, OTA_SLOT_HEADER_SIZE);
    g_erase_count++;
    return 0;
}

static int f_flash_program(void* ctx, uint32_t addr,
                           const uint8_t* src, uint32_t len)
{
    uint32_t i;

    (void)ctx;
    if(src == 0 || len == 0u || addr > FLASH_BYTES ||
       len > FLASH_BYTES - addr)
    {
        return -1;
    }
    if(g_fail_program_addr >= 0 && !g_fail_program_done &&
       addr == (uint32_t)g_fail_program_addr)
    {
        g_fail_program_done = 1;
        return -1;
    }
    for(i = 0u; i < len; i++)
    {
        g_flash[addr + i] &= src[i];
    }
    if(g_program_log_count < PROGRAM_LOG_MAX)
    {
        g_program_log[g_program_log_count][0] = addr;
        g_program_log[g_program_log_count][1] = len;
    }
    g_program_log_count++;
    g_program_count++;
    return 0;
}

/* ---- EEPROM 仿真 ---- */
static int e_write(uint8_t reg, const uint8_t* buf, uint16_t len)
{
    if(g_eeprom_write_fail)
    {
        return -1;
    }
    if((uint32_t)reg + len > EEPROM_BYTES)
    {
        return -1;
    }
    memcpy(g_eeprom + reg, buf, len);
    g_eeprom_write_count++;
    return 0;
}

static int e_read(uint8_t reg, uint8_t* buf, uint16_t len)
{
    if(g_eeprom_read_budget >= 0 &&
       g_eeprom_read_count >= (uint32_t)g_eeprom_read_budget)
    {
        return -1;
    }
    g_eeprom_read_count++;
    if((uint32_t)reg + len > EEPROM_BYTES)
    {
        return -1;
    }
    memcpy(buf, g_eeprom + reg, len);
    return 0;
}

static const bcb_hal_t g_bcb_hal = { e_write, e_read };
static const ota_backup_io_t g_flash_io = {
    NULL, f_app_read, f_flash_read, f_flash_erase, f_flash_program
};

static void reset_faults(void)
{
    g_fail_erase_addr = -1;
    g_fail_program_addr = -1;
    g_fail_program_done = 0;
    g_fail_read_addr = -1;
    g_fail_read_done = 0;
    g_eeprom_read_budget = -1;
    g_eeprom_write_fail = 0;
}

static void reset_counters(void)
{
    g_erase_count = 0u;
    g_program_count = 0u;
    g_program_log_count = 0;
    g_eeprom_read_count = 0u;
    g_eeprom_write_count = 0u;
}

static void setup_flash_with_candidate(void)
{
    memset(g_flash, 0xFF, FLASH_BYTES);
    /* 模拟 P2-4 Apply 后状态：candidate 槽头扇区擦净、payload 已写 */
    memcpy(g_flash + OTA_EXT_CANDIDATE + OTA_SLOT_HEADER_SIZE,
           g_candidate, g_candidate_len);
}

static void setup_eeprom_confirmed(uint32_t vcode)
{
    bcb_t bcb;
    uint8_t raw[BCB_SIZE];

    memset(&bcb, 0, sizeof(bcb));
    bcb.magic = BCB_MAGIC;
    bcb.schema_ver = BCB_SCHEMA_VER;
    bcb.state = BCB_STATE_CONFIRMED;
    bcb.boot_try = 0u;
    bcb.copy_phase = BCB_COPY_NONE;
    bcb.seq = 5u;
    bcb.resume_block = 0u;
    bcb.cur_vcode = vcode;
    bcb.reserved = 0u;
    bcb_serialize(&bcb, raw);
    memcpy(g_eeprom + BCB_A_ADDR, raw, BCB_SIZE);
    memcpy(g_eeprom + BCB_B_ADDR, raw, BCB_SIZE);
}

static int eeprom_active_state(void)
{
    bcb_t active;
    bcb_arbiter_result_t r = bcb_arbiter(&g_bcb_hal, &active);

    if(r != BCB_ARBITER_A && r != BCB_ARBITER_B)
    {
        return -1;
    }
    return (int)active.state;
}

static void reset_all(void)
{
    memset(g_eeprom, 0xFF, EEPROM_BYTES);
    memset(g_current, 0, sizeof(g_current));
    memset(g_candidate, 0, sizeof(g_candidate));
    g_current_len = IMAGE_BYTES;
    g_candidate_len = IMAGE_BYTES;
    build_valid_image(g_current, 20700u, "2.7.0");
    build_valid_image(g_candidate, 20800u, "2.8.0");
    reset_faults();
    reset_counters();
    /* default: unlimited eeprom reads, all flash ok */
    g_eeprom_read_budget = -1;
    g_eeprom_write_fail = 0;
}

/* T1 正常链 */
static void t1_normal(void)
{
    ota_backup_info_t info;
    ota_backup_result_t result;
    ota_slot_header_t cand;
    ota_slot_header_t backup;
    uint8_t raw[32];
    bcb_t staged;
    bcb_arbiter_result_t r;

    reset_all();
    setup_flash_with_candidate();
    setup_eeprom_confirmed(20700u);

    memset(&info, 0, sizeof(info));
    result = ota_backup_stage(&g_flash_io, &g_bcb_hal, &info);

    check("T1 result ok", result == OTA_BACKUP_OK);
    check("T1 info candidate_len", info.candidate_len == IMAGE_BYTES);
    check("T1 info backup_len", info.backup_len == IMAGE_BYTES);
    check("T1 info backup_vcode", info.backup_vcode == 20700u);
    check("T1 info candidate_vcode", info.candidate_vcode == 20800u);
    check("T1 commit_state == verified staged",
          info.commit_state == OTA_BACKUP_COMMIT_VERIFIED_STAGED);
    check("T1 erase count == 3 (backup 槽头+payload, candidate 槽头重擦)",
          g_erase_count == 3u);
    check("T1 program count == 5 (payload1+backup头2+cand头2)",
          g_program_count == 5u);

    /* ETSL 双槽 committed */
    check("T1 candidate slot committed",
          f_flash_read(0, OTA_EXT_CANDIDATE, raw, 32) == 0 &&
          ota_slot_header_parse(raw, OTA_SLOT_TYPE_CANDIDATE, &cand) == 0 &&
          cand.committed && cand.payload_len == IMAGE_BYTES &&
          cand.version_code == 20800u);
    check("T1 backup slot committed",
          f_flash_read(0, OTA_EXT_BACKUP, raw, 32) == 0 &&
          ota_slot_header_parse(raw, OTA_SLOT_TYPE_BACKUP, &backup) == 0 &&
          backup.committed && backup.payload_len == IMAGE_BYTES &&
          backup.version_code == 20700u);

    /* backup payload == 当前 App；candidate payload 未被改写 */
    check("T1 backup payload == current",
          memcmp(g_flash + OTA_EXT_BACKUP + OTA_SLOT_HEADER_SIZE,
                 g_current, IMAGE_BYTES) == 0);
    check("T1 candidate payload untouched",
          memcmp(g_flash + OTA_EXT_CANDIDATE + OTA_SLOT_HEADER_SIZE,
                 g_candidate, IMAGE_BYTES) == 0);

    /* BCB=STAGED 且字段一致 */
    r = bcb_arbiter(&g_bcb_hal, &staged);
    check("T1 bcb staged", r != BCB_ARBITER_NONE &&
          r != BCB_ARBITER_ERROR && staged.state == BCB_STATE_STAGED);
    if(r != BCB_ARBITER_NONE && r != BCB_ARBITER_ERROR)
    {
        check("T1 bcb cand_addr", staged.cand_addr ==
              OTA_EXT_CANDIDATE + OTA_SLOT_HEADER_SIZE);
        check("T1 bcb cand_len", staged.cand_len == IMAGE_BYTES);
        check("T1 bcb cand_crc32 == info", staged.cand_crc32 ==
              info.candidate_crc32);
        check("T1 bcb cand_vcode", staged.cand_vcode == 20800u);
        check("T1 bcb cur_vcode", staged.cur_vcode == 20700u);
        check("T1 bcb backup_len", staged.backup_len == IMAGE_BYTES);
        check("T1 bcb backup_crc32 == info", staged.backup_crc32 ==
              info.backup_crc32);
        check("T1 bcb backup_vcode", staged.backup_vcode == 20700u);
        check("T1 bcb boot_try == 3", staged.boot_try == BCB_INIT_BOOT_TRY);
        check("T1 bcb copy_phase == none", staged.copy_phase == BCB_COPY_NONE);
        check("T1 bcb resume == 0", staged.resume_block == 0u);
    }
}

/* T2 candidate 无效 → 零擦除/零写/BCB 零写入 */
static void t2_candidate_invalid(void)
{
    ota_backup_result_t result;

    reset_all();
    setup_flash_with_candidate();
    setup_eeprom_confirmed(20700u);
    g_flash[OTA_EXT_CANDIDATE + OTA_SLOT_HEADER_SIZE + 2000] ^= 0xFF;
    /* 破坏 candidate 全镜像，令其在任何擦除/写之前被拒 */

    result = ota_backup_stage(&g_flash_io, &g_bcb_hal, 0);
    check("T2 candidate invalid rejected(非 OK)",
          result != OTA_BACKUP_OK);
    check("T2 zero flash erase", g_erase_count == 0u);
    check("T2 zero flash program", g_program_count == 0u);
    check("T2 zero eeprom write", g_eeprom_write_count == 0u);
    check("T2 bcb still confirmed", eeprom_active_state() == BCB_STATE_CONFIRMED);
}

/* T3/T4 各步骤失败均不提交 STAGED */
typedef enum
{
    FAIL_ERASE_HDR,
    FAIL_ERASE_PAY,
    FAIL_PAYLOAD_PROG,
    FAIL_PAYLOAD_READ,
    FAIL_SLOT_FIELDS,
    FAIL_MARKER_BACKUP,
    FAIL_MARKER_CANDIDATE
} fail_kind_t;

static void t3s_fail_closed(fail_kind_t kind)
{
    ota_backup_result_t result;

    reset_all();
    setup_flash_with_candidate();
    setup_eeprom_confirmed(20700u);
    switch(kind)
    {
    case FAIL_ERASE_HDR:      g_fail_erase_addr = (int)OTA_EXT_BACKUP; break;
    case FAIL_ERASE_PAY:      g_fail_erase_addr =
        (int)(OTA_EXT_BACKUP + OTA_SLOT_HEADER_SIZE); break;
    case FAIL_PAYLOAD_PROG:   g_fail_program_addr =
        (int)(OTA_EXT_BACKUP + OTA_SLOT_HEADER_SIZE); break;
    case FAIL_PAYLOAD_READ:   g_fail_read_addr =
        (int)(OTA_EXT_BACKUP + OTA_SLOT_HEADER_SIZE); break;
    case FAIL_SLOT_FIELDS:    g_fail_program_addr = (int)OTA_EXT_BACKUP; break;
    case FAIL_MARKER_BACKUP:  g_fail_program_addr =
        (int)(OTA_EXT_BACKUP + OTA_SLOT_HEADER_BYTES - 4u); break;
    case FAIL_MARKER_CANDIDATE: g_fail_program_addr =
        (int)(OTA_EXT_CANDIDATE + OTA_SLOT_HEADER_BYTES - 4u); break;
    default: break;
    }
    result = ota_backup_stage(&g_flash_io, &g_bcb_hal, 0);

    check("T3 fail-closed result<0", result < 0);
    check("T3 no STAGED committed", eeprom_active_state() == BCB_STATE_CONFIRMED);
}

/* T4 marker-last 顺序 + 半写 backup 无效 */
static void t4_marker_last(void)
{
    int i;
    static const uint32_t slots[2] = { OTA_EXT_CANDIDATE, OTA_EXT_BACKUP };
    int slot_idx;
    uint8_t raw[32];
    ota_slot_header_t h;

    reset_all();
    setup_flash_with_candidate();
    setup_eeprom_confirmed(20700u);
    check("T4 normal ok",
          ota_backup_stage(&g_flash_io, &g_bcb_hal, 0) == OTA_BACKUP_OK);

    for(slot_idx = 0; slot_idx < 2; slot_idx++)
    {
        uint32_t slot = slots[slot_idx];
        int fields_seen = 0;
        int marker_seen = 0;
        int after_marker = 0;
        for(i = 0; i < g_program_log_count; i++)
        {
            uint32_t addr = g_program_log[i][0];
            uint32_t len = g_program_log[i][1];
            /* ETSL 头区 = 28B 字段(除 marker) + 4B marker，不是槽页 0x1000 */
            const uint32_t kFieldLen = OTA_SLOT_HEADER_BYTES - 4u;
            if(addr >= slot && addr < slot + OTA_SLOT_HEADER_SIZE)
            {
                if(after_marker)
                {
                    /* 头区内 marker 之后不得再有写 */
                    check("T4 no write after marker", 0);
                    continue;
                }
                if(len == kFieldLen && !fields_seen && !marker_seen)
                {
                    fields_seen = 1;
                    check("T4 fields at slot", addr == slot);
                }
                else if(len == 4u && fields_seen && !marker_seen &&
                        addr == slot + OTA_SLOT_HEADER_BYTES - 4u)
                {
                    marker_seen = 1;
                    after_marker = 1;
                }
                else
                {
                    check("T4 unexpected header region program", 0);
                }
            }
        }
        check("T4 marker last for slot", marker_seen == 1);
    }

    /* 半写 backup：marker 写失败后 flash 内 marker 仍擦除态 → parse 未提交 */
    reset_all();
    setup_flash_with_candidate();
    setup_eeprom_confirmed(20700u);
    g_fail_program_addr = (int)(OTA_EXT_BACKUP + OTA_SLOT_HEADER_BYTES - 4u);
    check("T4 half backup rejected",
          ota_backup_stage(&g_flash_io, &g_bcb_hal, 0) != OTA_BACKUP_OK);
    f_flash_read(0, OTA_EXT_BACKUP, raw, sizeof(raw));
    check("T4 half backup marker erased",
          ota_slot_header_parse(raw, OTA_SLOT_TYPE_BACKUP, &h) == 0 &&
          h.committed == 0);
    f_flash_read(0, OTA_EXT_CANDIDATE, raw, sizeof(raw));
    check("T4 half backup => candidate header untouched",
          ota_slot_header_parse(raw, OTA_SLOT_TYPE_CANDIDATE, &h) != 0 ||
          h.committed == 0);
}

/* T5 仅 CONFIRMED 可启动 */
static void t5_state_gate(void)
{
    int s;
    static const uint8_t bad_states[] = {
        BCB_STATE_IDLE, BCB_STATE_STAGED, BCB_STATE_APPLYING,
        BCB_STATE_TEST_BOOT, BCB_STATE_ROLLBACK
    };
    for(s = 0; s < (int)(sizeof(bad_states) / sizeof(bad_states[0])); s++)
    {
        bcb_t bcb;
        uint8_t raw[BCB_SIZE];

        reset_all();
        setup_flash_with_candidate();
        memset(&bcb, 0, sizeof(bcb));
        bcb.magic = BCB_MAGIC;
        bcb.schema_ver = BCB_SCHEMA_VER;
        bcb.state = bad_states[s];
        bcb.boot_try = 0u;
        bcb.seq = 5u;
        bcb.cur_vcode = 20700u;
        bcb_serialize(&bcb, raw);
        memcpy(g_eeprom + BCB_A_ADDR, raw, BCB_SIZE);
        memcpy(g_eeprom + BCB_B_ADDR, raw, BCB_SIZE);

        check("T5 non-CONFIRMED rejected",
              ota_backup_stage(&g_flash_io, &g_bcb_hal, 0) ==
              OTA_BACKUP_ERR_STATE);
        check("T5 zero flash erase", g_erase_count == 0u);
        check("T5 zero flash program", g_program_count == 0u);
        check("T5 zero eeprom write", g_eeprom_write_count == 0u);
    }

    /* 双坏 → ERR_EEPROM */
    reset_all();
    setup_flash_with_candidate();
    memset(g_eeprom, 0xFF, EEPROM_BYTES);
    check("T5 double-bad -> eeprom err",
          ota_backup_stage(&g_flash_io, &g_bcb_hal, 0) ==
          OTA_BACKUP_ERR_EEPROM);
    check("T5 zero flash erase dbl", g_erase_count == 0u);
    check("T5 zero flash program dbl", g_program_count == 0u);

    /* EEPROM 读失败 → ERR_EEPROM */
    reset_all();
    setup_flash_with_candidate();
    setup_eeprom_confirmed(20700u);
    g_fail_program_addr = -1;
    g_eeprom_read_budget = 0;
    check("T5 eeprom i/o -> eeprom err",
          ota_backup_stage(&g_flash_io, &g_bcb_hal, 0) ==
          OTA_BACKUP_ERR_EEPROM);
    check("T5 zero flash erase io", g_erase_count == 0u);
    check("T5 zero flash program io", g_program_count == 0u);
}

/* T6 BCB 提交三元语义（阻断 6）：
 *   - 写失败（未写）→ 复裁仍 CONFIRMED → ERR_COMMIT / commit_state=VERIFIED_CONFIRMED
 *   - 写成功但独立读回失败 → 有效 STAGED 已落盘：复裁观测失败 → AMBIGUOUS / UNKNOWN；
 *     解除读故障后必须读到 STAGED（不能宣称仍 CONFIRMED）
 *   - 提交读回成功后复核仲裁失败 → AMBIGUOUS / UNKNOWN */
static void t6_bcb_commit_tristate(void)
{
    ota_backup_result_t result;
    ota_backup_info_t info;
    bcb_arbiter_result_t r;
    bcb_t active;

    /* 写失败（HAL write 直接拒，未发生写入）：复裁得到 CONFIRMED → 可重试 */
    reset_all();
    setup_flash_with_candidate();
    setup_eeprom_confirmed(20700u);
    g_eeprom_write_fail = 1;
    memset(&info, 0, sizeof(info));
    result = ota_backup_stage(&g_flash_io, &g_bcb_hal, &info);
    check("T6 write fail (verified confirmed)",
          result == OTA_BACKUP_ERR_COMMIT &&
          info.commit_state == OTA_BACKUP_COMMIT_VERIFIED_CONFIRMED);
    check("T6 bcb still confirmed after write fail",
          eeprom_active_state() == BCB_STATE_CONFIRMED);
    {
        ota_slot_header_t sh;
        uint8_t raw[32];
        int parse = f_flash_read(0, OTA_EXT_CANDIDATE, raw, sizeof(raw)) == 0
                        ? ota_slot_header_parse(raw, OTA_SLOT_TYPE_CANDIDATE,
                                                &sh)
                        : -1;
        check("T6 candidate slot committed even after commit fail",
              parse == 0 && sh.committed);
    }

    /* 写成功 + 独立读回失败（budget=4，第 5 次读失败）：
     * 实际已写非活动块 STAGED(seq+1)；复裁读失败 → AMBIGUOUS/UNKNOWN。
     * 随后解除读故障，必须仲裁到 STAGED —— 不能宣称仍 CONFIRMED。 */
    reset_all();
    setup_flash_with_candidate();
    setup_eeprom_confirmed(20700u);
    g_eeprom_read_budget = 4;
    memset(&info, 0, sizeof(info));
    result = ota_backup_stage(&g_flash_io, &g_bcb_hal, &info);
    check("T6 readback fail -> ambiguous(unknown)",
          result == OTA_BACKUP_ERR_COMMIT_AMBIGUOUS &&
          info.commit_state == OTA_BACKUP_COMMIT_UNKNOWN);
    /* 解除读故障后重新仲裁：写已生效，读到 STAGED，活动块已非 CONFIRMED */
    reset_faults();
    r = bcb_arbiter(&g_bcb_hal, &active);
    check("T6 post-failure re-arbiter shows STAGED",
          r == BCB_ARBITER_A || r == BCB_ARBITER_B);
    if(r == BCB_ARBITER_A || r == BCB_ARBITER_B)
    {
        check("T6 stagged actually committed", active.state == BCB_STATE_STAGED);
    }

    /* 提交读回 OK 后模块复核仲裁失败（budget=5：前 5 次 OK，第 6 次失败）：
     * 复裁观测失败 → AMBIGUOUS/UNKNOWN（禁止按普通失败覆盖） */
    reset_all();
    setup_flash_with_candidate();
    setup_eeprom_confirmed(20700u);
    g_eeprom_read_budget = 5;
    memset(&info, 0, sizeof(info));
    result = ota_backup_stage(&g_flash_io, &g_bcb_hal, &info);
    check("T6 post-commit verify fail -> ambiguous(unknown)",
          result == OTA_BACKUP_ERR_COMMIT_AMBIGUOUS &&
          info.commit_state == OTA_BACKUP_COMMIT_UNKNOWN);
    reset_faults();
    r = bcb_arbiter(&g_bcb_hal, &active);
    check("T6 post-commit re-arbiter OK", r == BCB_ARBITER_A ||
          r == BCB_ARBITER_B);
    if(r == BCB_ARBITER_A || r == BCB_ARBITER_B)
    {
        check("T6 post-commit effective STAGED", active.state == BCB_STATE_STAGED);
    }

    /* 正常路径返回 VERIFIED_STAGED（T1 已覆盖），此处补 commit_state 断言关联 */
    reset_all();
    setup_flash_with_candidate();
    setup_eeprom_confirmed(20700u);
    memset(&info, 0, sizeof(info));
    result = ota_backup_stage(&g_flash_io, &g_bcb_hal, &info);
    check("T6 normal ok staged", result == OTA_BACKUP_OK &&
          info.commit_state == OTA_BACKUP_COMMIT_VERIFIED_STAGED);
}

/* T7 多块 payload + 非 4KB 整数长度（阻断 10）：
 *   候选/当前镜像 len = 8192+333（跨 3 个 4KB 扇区），程序逐块写，
 *   收尾块只写剩余字节；ETSL payload_len 取真实 len 而非对齐值。 */
static void t7_multi_block_non_4k(void)
{
    enum { BIG = 8192 + 333 };
    uint8_t current_x[MAX_IMAGE];
    uint8_t candidate_x[MAX_IMAGE];
    ota_backup_info_t info;
    ota_backup_result_t result;
    bcb_t staged;
    bcb_arbiter_result_t r;
    ota_slot_header_t backup;
    uint8_t raw[32];

    memset(current_x, 0, sizeof(current_x));
    memset(candidate_x, 0, sizeof(candidate_x));
    build_valid_image_ex(current_x, (uint32_t)BIG, 20700u, "2.7.0");
    build_valid_image_ex(candidate_x, (uint32_t)BIG, 20800u, "2.8.0");

    /* 载入多块镜像并走完整事务 */
    reset_all();
    g_current_len = (uint32_t)BIG;
    g_candidate_len = (uint32_t)BIG;
    memcpy(g_current, current_x, (uint32_t)BIG);
    memcpy(g_candidate, candidate_x, (uint32_t)BIG);
    setup_flash_with_candidate();
    setup_eeprom_confirmed(20700u);

    memset(&info, 0, sizeof(info));
    result = ota_backup_stage(&g_flash_io, &g_bcb_hal, &info);
    check("T7 multi-block ok", result == OTA_BACKUP_OK);
    check("T7 candidate_len real",
          info.candidate_len == (uint32_t)BIG);
    check("T7 backup_len real", info.backup_len == (uint32_t)BIG);
    /* 3 块 payload 自拷 + 双侧槽头各 28B/4B 两段 = 3 + 4 = 7 */
    check("T7 program count", g_program_count == 7u);
    /* backup 槽头 + 3 payload 扇区 + candidate 槽头 = 5 */
    check("T7 erase count", g_erase_count == 5u);
    check("T7 payload tail coherent",
          memcmp(g_flash + OTA_EXT_BACKUP + OTA_SLOT_HEADER_SIZE,
                 current_x, (uint32_t)BIG) == 0);
    r = bcb_arbiter(&g_bcb_hal, &staged);
    check("T7 staged len", r != BCB_ARBITER_NONE &&
          staged.state == BCB_STATE_STAGED &&
          staged.backup_len == (uint32_t)BIG);
    check("T7 backup slot header len",
          f_flash_read(0, OTA_EXT_BACKUP, raw, sizeof(raw)) == 0 &&
          ota_slot_header_parse(raw, OTA_SLOT_TYPE_BACKUP,
                                &backup) == 0 &&
          backup.payload_len == (uint32_t)BIG);
}

/* T8 候选槽头旧 marker 重试（阻断 5）：候选槽头已残留已提交 marker
 * （上次失败遗留），重跑必须整扇区重擦后重新 28B+4B 写入。 */
static void t8_candidate_old_marker(void)
{
    ota_backup_result_t result;
    ota_slot_header_t cand;
    uint8_t raw[32];
    int fields_seen;
    int marker_seen;
    int i;

    reset_all();
    setup_flash_with_candidate();
    setup_eeprom_confirmed(20700u);
    /* 预置候选槽头为“已提交”残留：旧 marker 已写 */
    f_flash_program(0, OTA_EXT_CANDIDATE + OTA_SLOT_HEADER_BYTES - 4u,
                    (const uint8_t*)"\x54\x4D\x4F\x43", 4u);
    reset_counters();
    result = ota_backup_stage(&g_flash_io, &g_bcb_hal, 0);
    check("T8 old-marker retry ok", result == OTA_BACKUP_OK);
    /* candidate 槽头重擦发生在写入前，marker 必须是新写（程序日志验证
     * 顺序：槽头区没有只写 marker，28B+4B 均在重擦之后） */
    fields_seen = 0;
    marker_seen = 0;
    for(i = 0; i < g_program_log_count; i++)
    {
        uint32_t addr = g_program_log[i][0];
        uint32_t len = g_program_log[i][1];
        if(addr < OTA_EXT_CANDIDATE + OTA_SLOT_HEADER_SIZE)
        {
            if(len == OTA_SLOT_HEADER_BYTES - 4u && !fields_seen)
            {
                fields_seen = 1;
            }
            else if(len == 4u && fields_seen)
            {
                marker_seen = 1;
            }
        }
    }
    check("T8 candidate header rewritten fields+marker",
          fields_seen && marker_seen);
    f_flash_read(0, OTA_EXT_CANDIDATE, raw, sizeof(raw));
    check("T8 candidate committed",
          ota_slot_header_parse(raw, OTA_SLOT_TYPE_CANDIDATE, &cand) == 0 &&
          cand.committed);
    /* candidate payload 未被旧 marker 场景破坏 */
    check("T8 candidate payload intact",
          memcmp(g_flash + OTA_EXT_CANDIDATE + OTA_SLOT_HEADER_SIZE,
                 g_candidate, IMAGE_BYTES) == 0);
}

/* T9 降级/过期 candidate 拒绝（阻断 7）：candidate vcode <= 当前 → 零副作用。 */
static void t9_downgrade_reject(void)
{
    ota_backup_result_t result;

    reset_all();
    build_valid_image(g_candidate, 20700u, "2.7.0"); /* 与当前同版本 */
    setup_flash_with_candidate();
    setup_eeprom_confirmed(20700u);

    result = ota_backup_stage(&g_flash_io, &g_bcb_hal, 0);
    check("T9 downgrade rejected", result == OTA_BACKUP_ERR_CANDIDATE_CRC);
    check("T9 zero flash erase", g_erase_count == 0u);
    check("T9 zero flash program", g_program_count == 0u);
    check("T9 zero eeprom write", g_eeprom_write_count == 0u);
    check("T9 bcb still confirmed", eeprom_active_state() == BCB_STATE_CONFIRMED);

    /* 过期（更低）同样拒绝 */
    reset_all();
    build_valid_image(g_candidate, 20600u, "2.6.0");
    setup_flash_with_candidate();
    setup_eeprom_confirmed(20700u);
    result = ota_backup_stage(&g_flash_io, &g_bcb_hal, 0);
    check("T9 stale rejected", result == OTA_BACKUP_ERR_CANDIDATE_CRC);
    check("T9 stale zero side effects", g_erase_count == 0u &&
          g_program_count == 0u && g_eeprom_write_count == 0u);
}

/* T10 自拷中途故障（阻断 10）：payload 第二块写失败 → 不提交 STAGED。 */
static void t10_copy_mid_failure(void)
{
    ota_backup_result_t result;

    reset_all();
    /* 构造 2 块镜像：第一块成功，第二块程序失败 */
    {
        enum { TWO_BLOCK = 2 * 4096 };
        static uint8_t two_current[MAX_IMAGE];
        static uint8_t two_cand[MAX_IMAGE];

        build_valid_image_ex(two_current, (uint32_t)TWO_BLOCK, 20700u,
                             "2.7.0");
        build_valid_image_ex(two_cand, (uint32_t)TWO_BLOCK, 20800u,
                             "2.8.0");
        g_current_len = (uint32_t)TWO_BLOCK;
        g_candidate_len = (uint32_t)TWO_BLOCK;
        memcpy(g_current, two_current, (uint32_t)TWO_BLOCK);
        memset(g_flash, 0xFF, FLASH_BYTES);
        memcpy(g_flash + OTA_EXT_CANDIDATE + OTA_SLOT_HEADER_SIZE,
               two_cand, (uint32_t)TWO_BLOCK);
    }
    setup_eeprom_confirmed(20700u);
    g_fail_program_addr = (int)(OTA_EXT_BACKUP + OTA_SLOT_HEADER_SIZE +
                                4096u);   /* 第二块 */
    result = ota_backup_stage(&g_flash_io, &g_bcb_hal, 0);
    check("T10 mid-copy fail-closed", result == OTA_BACKUP_ERR_WRITE);
    check("T10 no STAGED", eeprom_active_state() == BCB_STATE_CONFIRMED);
}

int main(int argc, char** argv)
{
    (void)argc;
    (void)argv;
    checks = 0;
    failures = 0;

    t1_normal();
    t2_candidate_invalid();
    t3s_fail_closed(FAIL_ERASE_HDR);
    t3s_fail_closed(FAIL_ERASE_PAY);
    t3s_fail_closed(FAIL_PAYLOAD_PROG);
    t3s_fail_closed(FAIL_PAYLOAD_READ);
    t3s_fail_closed(FAIL_SLOT_FIELDS);
    t3s_fail_closed(FAIL_MARKER_BACKUP);
    t3s_fail_closed(FAIL_MARKER_CANDIDATE);
    t4_marker_last();
    t5_state_gate();
    t6_bcb_commit_tristate();
    t7_multi_block_non_4k();
    t8_candidate_old_marker();
    t9_downgrade_reject();
    t10_copy_mid_failure();

    printf("P2_5_OTA_BACKUP checks=%d failures=%d\n", checks, failures);
    return failures == 0 ? 0 : 1;
}