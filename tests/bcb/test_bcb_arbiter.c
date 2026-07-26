/*
 * test_bcb_arbiter.c —— BCB seq 仲裁五场景单测 (契约 §3.2)
 *
 * 编译运行 (本机 gcc, 不依赖真机):
 *   gcc -std=c99 -Wall -Wextra -I ../../Libraries/EEPROM \
 *       ../../Libraries/EEPROM/eeprom_bcb.c test_bcb_arbiter.c -o test_bcb_arbiter
 *   ./test_bcb_arbiter
 *
 * 覆盖 §3.2 全部场景:
 *   1. A_newer      (A.seq=5, B.seq=3)        → A
 *   2. B_wrap_newer (A.seq=5, B.seq=65530)    → B   ((int16)(5-65530)=-11<0)
 *   3. equal_both_valid (A.seq=7, B.seq=7)    → A
 *   4. only_B_valid (A 损坏)                  → B
 *   5. only_A_valid (B 损坏)                  → A
 *   6. both_invalid                           → NONE (recovery)
 *   7. crc_corrupted (magic/schema 对但 crc 坏) → 视为损坏
 *   8. commit 单次事务: 非活动块写入+读回比对,seq 递增后活动性转移
 *
 * 输出: 每场景 PASS/FAIL, 末尾汇总。
 */
#include <stdio.h>
#include <string.h>
#include "eeprom_bcb.h"

/* ---- 并发式内存 EEPROM 模型 (256B),供 HAL 注入端口读写 ---- */
static uint8_t mem_eeprom[256];

static int mem_write(uint8_t reg, const uint8_t* buf, uint16_t len)
{
    if ((uint16_t)reg + len > 256u) return -1;
    memcpy(mem_eeprom + reg, buf, len);
    return 0;
}

static int mem_read(uint8_t reg, uint8_t* buf, uint16_t len)
{
    if ((uint16_t)reg + len > 256u) return -1;
    memcpy(buf, mem_eeprom + reg, len);
    return 0;
}

static const bcb_hal_t hal = { mem_write, mem_read };

static int failures = 0;

static void check(const char* name, int cond)
{
    printf("  %-32s %s\n", name, cond ? "PASS" : "FAIL");
    if (!cond) failures++;
}

/* 在 mem_eeprom 中构造一份合法 BCB 块 (指定 seq/state/cur_vcode),写指定地址。 */
static void place_valid_bcb(uint8_t addr, uint16_t seq, uint8_t state, uint32_t cur_vcode)
{
    bcb_t b;
    bcb_make_idle(&b, cur_vcode);
    b.seq = seq;
    b.state = state;
    uint8_t raw[BCB_SIZE];
    bcb_serialize(&b, raw);
    memcpy(mem_eeprom + addr, raw, BCB_SIZE);
}

static void corrupt_block(uint8_t addr)
{
    /* 写全 0xFF 模拟擦除态/损坏。 */
    memset(mem_eeprom + addr, 0xFF, BCB_SIZE);
}

int main(void)
{
    printf("=== BCB arbiter tests (contract §3.2) ===\n");

    /* 场景 1: A_newer */
    memset(mem_eeprom, 0xFF, sizeof(mem_eeprom));
    place_valid_bcb(BCB_A_ADDR, 5, BCB_STATE_CONFIRMED, 20700);
    place_valid_bcb(BCB_B_ADDR, 3, BCB_STATE_CONFIRMED, 20700);
    check("1. A_newer (5 vs 3) -> A", bcb_arbiter(&hal, NULL) == BCB_ARBITER_A);

    /* 场景 2: B_wrap_newer (a=65530, b=5 → (int16)(65530-5)=-11<0 → B 新)
     *   对齐 P0-3 expected.json: "B_wrap_newer" a_seq=65530 b_seq=5 expect=B */
    memset(mem_eeprom, 0xFF, sizeof(mem_eeprom));
    place_valid_bcb(BCB_A_ADDR, 65530, BCB_STATE_CONFIRMED, 20700);
    place_valid_bcb(BCB_B_ADDR, 5,     BCB_STATE_CONFIRMED, 20700);
    check("2. B_wrap_newer (65530 vs 5) -> B", bcb_arbiter(&hal, NULL) == BCB_ARBITER_B);

    /* 场景 3: equal_both_valid → A */
    memset(mem_eeprom, 0xFF, sizeof(mem_eeprom));
    place_valid_bcb(BCB_A_ADDR, 7, BCB_STATE_CONFIRMED, 20700);
    place_valid_bcb(BCB_B_ADDR, 7, BCB_STATE_CONFIRMED, 20700);
    check("3. equal_both_valid (7 vs 7) -> A", bcb_arbiter(&hal, NULL) == BCB_ARBITER_A);

    /* 场景 4: only_B_valid */
    memset(mem_eeprom, 0xFF, sizeof(mem_eeprom));
    corrupt_block(BCB_A_ADDR);
    place_valid_bcb(BCB_B_ADDR, 9, BCB_STATE_CONFIRMED, 20700);
    check("4. only_B_valid -> B", bcb_arbiter(&hal, NULL) == BCB_ARBITER_B);

    /* 场景 5: only_A_valid */
    memset(mem_eeprom, 0xFF, sizeof(mem_eeprom));
    place_valid_bcb(BCB_A_ADDR, 9, BCB_STATE_CONFIRMED, 20700);
    corrupt_block(BCB_B_ADDR);
    check("5. only_A_valid -> A", bcb_arbiter(&hal, NULL) == BCB_ARBITER_A);

    /* 场景 6: both_invalid → NONE */
    memset(mem_eeprom, 0xFF, sizeof(mem_eeprom));
    corrupt_block(BCB_A_ADDR);
    corrupt_block(BCB_B_ADDR);
    check("6. both_invalid -> NONE", bcb_arbiter(&hal, NULL) == BCB_ARBITER_NONE);

    /* 场景 7: crc_corrupted (magic/schema 对但 crc 字节被改) */
    memset(mem_eeprom, 0xFF, sizeof(mem_eeprom));
    place_valid_bcb(BCB_A_ADDR, 5, BCB_STATE_CONFIRMED, 20700);
    /* 翻转 crc32 的一个字节 (off 60) */
    mem_eeprom[BCB_A_ADDR + 60] ^= 0xFF;
    place_valid_bcb(BCB_B_ADDR, 3, BCB_STATE_CONFIRMED, 20700);
    /* A 的 crc 坏 → 只 B 合法 → B */
    check("7. crc_corrupted A -> B", bcb_arbiter(&hal, NULL) == BCB_ARBITER_B);

    /* 场景 8: 单次事务 commit —— 当前 A 活动块,写非活动块 B,seq+1,读回比对 */
    memset(mem_eeprom, 0xFF, sizeof(mem_eeprom));
    place_valid_bcb(BCB_A_ADDR, 5, BCB_STATE_STAGED, 20700);
    corrupt_block(BCB_B_ADDR);

    bcb_t active;
    bcb_arbiter_result_t r = bcb_arbiter(&hal, &active);
    check("8a. initial active is A", r == BCB_ARBITER_A && active.seq == 5);

    /* 构造 STAGED→APPLYING 原子事务 (§3.4 R4-1): state/APPLYING, copy_phase/APPLY, resume_block=0, seq+1 */
    bcb_t next = active;
    next.state = BCB_STATE_APPLYING;
    next.copy_phase = BCB_COPY_APPLY;
    next.resume_block = 0;
    next.seq = (uint16_t)(active.seq + 1u);
    int rc = bcb_commit(&hal, BCB_ARBITER_A, &next);
    check("8b. commit returns 0", rc == 0);

    /* commit 后非活动块 B 应为合法且 seq=6/APPLYING/copy_phase=APPLY/resume_block=0 */
    bcb_t after;
    bcb_arbiter_result_t r2 = bcb_arbiter(&hal, &after);
    check("8c. after commit active is B (seq newer)", r2 == BCB_ARBITER_B && after.seq == 6);
    check("8d. state APPLIED atomically",
          after.state == BCB_STATE_APPLYING && after.copy_phase == BCB_COPY_APPLY && after.resume_block == 0);

    /* 场景 9: 读回失配检测 —— 模拟 write 成功但 read 回错 (注入: write 后人为破坏目标块) */
    memset(mem_eeprom, 0xFF, sizeof(mem_eeprom));
    place_valid_bcb(BCB_A_ADDR, 5, BCB_STATE_CONFIRMED, 20700);
    corrupt_block(BCB_B_ADDR);
    bcb_t active9;
    bcb_arbiter(&hal, &active9);
    bcb_t next9 = active9;
    next9.seq = (uint16_t)(active9.seq + 1u);
    /* 先把目标块 B 弄成"写成功后失配": 用一个包装 write 立即翻转一字节 */
    /* 这里直接验证 bcb_is_valid 对 crc 坏块判 0 已覆盖;此场景用 mem_write 注入对应字节再读 */
    /* 简化:人为在 commit 后翻转 B 一字节,确认下次仲裁不会误选 */
    bcb_commit(&hal, BCB_ARBITER_A, &next9);
    mem_eeprom[BCB_B_ADDR + 5] ^= 0x01; /* 翻 state 字节但不动 crc → crc 校验失败 */
    bcb_arbiter_result_t r9 = bcb_arbiter(&hal, NULL);
    check("9. tampered B invalid -> falls back to A", r9 == BCB_ARBITER_A);

    /* 场景 10: 序列化/反序列化 64B 严格契约 §3.1 字段 offset 对号 */
    {
        bcb_t b;
        bcb_make_idle(&b, 20800);
        b.state = BCB_STATE_STAGED;
        b.seq = 1;
        b.cand_addr = 0x1000;
        b.cand_len = 0x96000;
        b.cand_crc32 = 0x11223344;
        b.cand_vcode = 20800;
        b.cur_vcode = 20700;
        uint8_t raw[BCB_SIZE];
        bcb_serialize(&b, raw);
        /* magic ETBC at off 0..3 = 45 54 42 43 */
        check("10a. magic ETBC bytes 45 54 42 43",
              raw[0]==0x45 && raw[1]==0x54 && raw[2]==0x42 && raw[3]==0x43);
        /* schema at off 4 = 1 */
        check("10b. schema_ver at off 4 = 1", raw[4] == 1);
        /* state STAGED=1 at off 5 */
        check("10c. state STAGED at off 5 = 1", raw[5] == BCB_STATE_STAGED);
        /* seq=1 LE at off 8..9 = 01 00 */
        check("10d. seq LE at off 8 = 01 00", raw[8]==0x01 && raw[9]==0x00);
        /* cand_addr=0x1000 LE at off 12..15 = 00 10 00 00 */
        check("10e. cand_addr LE at off 12", raw[12]==0x00 && raw[13]==0x10 && raw[14]==0x00 && raw[15]==0x00);
        /* pad 0xFF at off 44..55 */
        int pad_ok = 1;
        for (int i = 44; i < 56; i++) if (raw[i] != 0xFF) pad_ok = 0;
        check("10f. pad 0xFF at off 44..55", pad_ok);
        /* crc32 at off 60..63 = bcb_crc32(raw,60) LE */
        uint32_t crc = bcb_crc32(raw, 60);
        check("10g. crc32 off 60 matches region 0..59",
              raw[60]==(uint8_t)(crc&0xFF) && raw[61]==(uint8_t)(crc>>8&0xFF) &&
              raw[62]==(uint8_t)(crc>>16&0xFF) && raw[63]==(uint8_t)(crc>>24&0xFF));
        /* round-trip deserialize */
        bcb_t d;
        bcb_deserialize(raw, &d);
        check("10h. deserialize roundtrip seq/state/cur_vcode",
              d.seq==1 && d.state==BCB_STATE_STAGED && d.cur_vcode==20700 && d.cand_vcode==20800);
    }

    printf("\n=== summary: %d failure(s) ===\n", failures);
    return failures == 0 ? 0 : 1;
}
