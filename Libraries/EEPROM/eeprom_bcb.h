/*
 * eeprom_bcb.h —— OTA Boot Control Block (BCB) 双块安全写事务 + seq 仲裁
 *
 * 契约唯一依据: docs/ota-binary-contracts.md v1.0 §3 (BCB 64B 字段表 / seq 仲裁 /
 * 安全写事务) 与 §0.2 (CRC32-IEEE) / §0.4 (EEPROM_BCB_A=0x00, EEPROM_BCB_B=0x40)。
 *
 * 设计要点 (契约 §3.3): boot/App 共用本源文件;不直接调 Wire/HAL,
 * 通过 bcb_hal_t 注入 { write_buffer, read_buffer } 二端口,以便 P1 boot 工程
 * (无 ArduinoAPI) 与 App (有 Wire,经 HAL_EEPROM.cpp 适配) 共用同一状态机。
 *
 * 红线: byte 255 (0xFF) 处的 0x55 初始化魔数保持不动,本文件任何路径不写该字节。
 */
#ifndef __EEPROM_BCB_H
#define __EEPROM_BCB_H

#include <stdint.h>

/* AC5 在 --c99 模式下对部分匿名 typedef 写法解析不稳;显式定义 struct tag
 * 后再 typedef, 保证 boot(App) / App(GCC) / 本机 gcc 单测三方一致编译。 */

#ifdef __cplusplus
extern "C" {
#endif

/* ---- 常量 (契约 §0.4 / §3.1, 四方唯一引用本头) ---- */
#define BCB_SIZE            64u     /* 单块字节数 */
#define BCB_A_ADDR          0x00u   /* EEPROM 内 BCB-A 地址 */
#define BCB_B_ADDR          0x40u   /* EEPROM 内 BCB-B 地址 */
#define BCB_CRC_REGION_LEN  60u     /* crc32 覆盖 off 0..59 */
#define BCB_MAGIC           0x43425445u  /* "ETBC" 小端存储 = 45 54 42 43 */
#define BCB_SCHEMA_VER      1u
#define BCB_INIT_BOOT_TRY   3u

/* BCB.state 取值 (契约 §3.1) */
typedef enum {
    BCB_STATE_IDLE      = 0,
    BCB_STATE_STAGED    = 1,
    BCB_STATE_APPLYING  = 2,
    BCB_STATE_TEST_BOOT = 3,
    BCB_STATE_CONFIRMED = 4,
    BCB_STATE_ROLLBACK  = 5,
} bcb_state_t;

/* BCB.copy_phase 取值 (契约 §3.1) */
typedef enum {
    BCB_COPY_NONE     = 0,
    BCB_COPY_APPLY    = 1,  /* APPLYING 搬运中 */
    BCB_COPY_ROLLBACK = 2,  /* ROLLBACK 搬运中 */
} bcb_copy_phase_t;

/* 64B BCB 字段视图 (契约 §3.1, 小端)。仅用作内存中解析/构造,不直接 memcpy 到总线。 */
#pragma pack(push, 1)
typedef struct bcb_t {
    uint32_t magic;          /* off 0  "ETBC" */
    uint8_t  schema_ver;     /* off 4  恒 1 */
    uint8_t  state;          /* off 5  bcb_state_t */
    uint8_t  boot_try;       /* off 6  初始 3 */
    uint8_t  copy_phase;     /* off 7  bcb_copy_phase_t */
    uint16_t seq;            /* off 8  仲裁序号 */
    uint16_t resume_block;   /* off 10 已读回验证的 4KB 块数 */
    uint32_t cand_addr;      /* off 12 候选镜像外部 flash 绝对地址 */
    uint32_t cand_len;       /* off 16 */
    uint32_t cand_crc32;     /* off 20 */
    uint32_t cand_vcode;     /* off 24 */
    uint32_t cur_vcode;      /* off 28 */
    uint32_t backup_len;     /* off 32 */
    uint32_t backup_crc32;   /* off 36 */
    uint32_t backup_vcode;   /* off 40 */
    uint8_t  pad[12];        /* off 44 0xFF */
    uint32_t reserved;       /* off 56 0 */
    uint32_t crc32;          /* off 60 覆盖 off 0..59 */
} bcb_t;
#pragma pack(pop)

/* 编译期尺寸校验 (契约 §3.1: bcb_t 必须 64B)。
 * AC5 --c99 不支持 C11 _Static_assert 关键字,改用手写断言宏:取负数组下标
 * 在 sizeof(bcb_t)!=64 时编译报错,gcc/AC5 双向兼容。 */
typedef char bcb_size_check[(sizeof(struct bcb_t) == BCB_SIZE) ? 1 : -1];

/* ---- HAL 注入端口 (boot/App 各自实现) ---- */
typedef struct bcb_hal_t {
    /* 安全多字节写: 逐页 + ACK polling + 读回比对 (契约 §3.3)。返回 0 成功。 */
    int  (*write_buffer)(uint8_t reg, const uint8_t* buf, uint16_t len);
    /* 多字节读。返回 0 成功且读齐 len。 */
    int  (*read_buffer) (uint8_t reg, uint8_t* buf, uint16_t len);
} bcb_hal_t;

/* 仲裁结果 (契约 §3.2) */
typedef enum bcb_arbiter_result_t {
    BCB_ARBITER_A      =  1,  /* A 活动块 */
    BCB_ARBITER_B      =  2,  /* B 活动块 */
    BCB_ARBITER_NONE   =  0,  /* 双块均坏 → recovery */
    BCB_ARBITER_ERROR  = -1,  /* HAL 读写失败 */
} bcb_arbiter_result_t;

/* bcb_commit return values. All failures require the caller to re-run
 * arbitration before deciding the next action. */
#define BCB_COMMIT_OK             0
#define BCB_COMMIT_ERR_PARAM     -1
#define BCB_COMMIT_ERR_ACTIVE    -2
#define BCB_COMMIT_ERR_WRITE     -3
#define BCB_COMMIT_ERR_READBACK  -4
#define BCB_COMMIT_ERR_VERIFY    -5
#define BCB_COMMIT_ERR_ARBITER   -6

/* ---- 公共 API ---- */

/* CRC32-IEEE (契约 §0.2, 与 zlib.crc32 / vendor crc32.c 同参数)。 */
uint32_t bcb_crc32(const uint8_t* data, uint16_t len);

/* 构造一份合法 BCB 内存视图的 64B 序列化字节流 (禁 struct memcpy,逐字段小端手填)。
 * 计算 crc32 覆盖 off 0..59 后回填 off 60..63。 */
void bcb_serialize(const bcb_t* bcb, uint8_t out[BCB_SIZE]);

/* 反序列化: 从 64B 字节流逐字段解析到 bcb_t。仅做字段抽取,不做合法性判定。 */
void bcb_deserialize(const uint8_t in[BCB_SIZE], bcb_t* out);

/* 合法性判定 (契约 §3.1): magic==ETBC 且 schema_ver==1 且 crc32 重算通过。 */
int bcb_is_valid(const uint8_t raw[BCB_SIZE]);

/* 整块读 A 与 B (经 HAL),做合法性判定,按 §3.2 仲裁选活动块。
 *   - 双合法 相等 seq 取 A; (int16)(a.seq-b.seq)>0 取新者。
 *   - 单合法 取合法者。
 *   - 双坏 → BCB_ARBITER_NONE (调用方走 recovery)。
 *   - HAL 失败 → BCB_ARBITER_ERROR。
 * 活动块内容经 *out_active 返回 (若非 NULL)。 */
bcb_arbiter_result_t bcb_arbiter(const bcb_hal_t* hal,
                                 bcb_t* out_active);

/* 单次安全写事务 (契约 §3.2 写序 + §3.4 R4-1 原子写):
 *   1. 重新仲裁当前活动块，并由核心强制设置 seq=active.seq+1;
 *   2. 在内存中把 new_bcb 整 64B 序列化 (含 crc32);
 *   3. 经 HAL 写【非活动块】整 64B (逐页 + ACK polling);
 *   4. 经 HAL 读回 64B 逐字节比对，通过即生效。
 * 不允许分字段多次写 (R4-1 ROLLBACK 首转必须原子)。
 * active_now: 当前活动块 (BCB_ARBITER_A/B)。双块均坏的首次初始化必须传
 * BCB_ARBITER_NONE，此时核心强制 seq=0 并写 A。其他值拒绝。
 * new_bcb->seq 由核心覆盖，调用方不得依赖其输入值。
 * 返回 BCB_COMMIT_OK 或 BCB_COMMIT_ERR_*。 */
int bcb_commit(const bcb_hal_t* hal,
               bcb_arbiter_result_t active_now,
               const bcb_t* new_bcb);

/* 便捷构造: 初始化一份全新 IDLE BCB (首次烧录 bootstrap 用)。
 * seq=0, state=IDLE, boot_try=3, copy_phase=NONE；CRC 在序列化时生成。 */
void bcb_make_idle(bcb_t* out, uint32_t cur_vcode);

#ifdef __cplusplus
}
#endif

#endif /* __EEPROM_BCB_H */
