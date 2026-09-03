/*
 * P3-2 设备身份链宿主测试。
 *
 * 覆盖（派工书「必须新增或调整的测试」→ docs/ota-exec-notes/
 * P3-2-identity-research.md §8 映射）：
 *   T1  golden 正例：toy-old.bin 装配合法向量 + 合法 BCB，全字段断言
 *       （model="E-Track\0" / hw=1 / layout=1 / boot=BOOT_VERSION /
 *        vcode=20700 / image_sha256 == 独立重算 raw SHA）。
 *   T2  fw_header 负例：magic / header_crc / image_sha（字段位翻转 +
 *       payload 篡改两种形态）/ image_len 超上界 / image_len 过小 /
 *       向量 MSP / 向量 reset → fail closed + fw_header_result 诊断码。
 *   T3  读 IO 负例：header 读失败、payload 读失败（validate 阶段）、
 *       raw SHA 阶段读失败（读预算注入）→ fail closed。
 *   T4  BCB 仲裁：A 新 / B 回绕新 / 仅 B 合法 / 双块无效（NONE 照常
 *       放行）/ cur_vcode 与 fw_header 不一致以 fw_header 为准 /
 *       每次调用重仲裁（bcb_result 刷新）。
 *   T5  BCB IO 失败（EEPROM 读失败）→ OTA_DEVICE_ERR_BCB_IO fail closed。
 *   T6  参数负例：state/out/reader/read/bcb_hal 任一为 NULL → ERR_ARGUMENT。
 *   T7  摘要域分离：设备输出 raw SHA ≠ fixture fw_header 双零摘要，
 *       前 8B 对应 .etu base_sha8 域；expected.json 两域互异锚定。
 *   T8  快照语义：第二次调用缓存复用（镜像读不增加、输出一致）、
 *       全程零写副作用、快照重置（模拟重启）+ 换镜像 → 新值。
 *
 * golden fixture 约定：tests/ota-vectors/toy-old.bin 是 .etu/ETSL 打包
 * 向量文件，向量表为占位填充字节，不能过 boot_fw_header_validate 的
 * 向量检查。测试先锚定原始字节（raw SHA == expected.json file_sha256、
 * 头内双零 sha == expected.json fw_header.image_sha256，证明与 CI/Tools
 * 同 fixture），再装配合法向量表（MSP 落 RAM / reset 落 App 区）并按
 * 双零法 refit 头部，期望 raw SHA 对装配后镜像独立重算 —— 设备身份链
 * 的输出因此同时满足「同 fixture 锚定」与「逐字节独立计算」。
 *
 * 不单测 OTA_DEVICE_ERR_HW_RANGE：boot_fw_header_validate 先行拒绝
 * hw_rev != BOOT_FW_HARDWARE_REV，该分支仅防御 BOOT_FW_HARDWARE_REV
 * 常量漂移超出 u16 wire 范围，生产保留 fail closed。proto_ver /
 * max_window_segs 由 session 层冻结常量填充（P3-1 已测），本组件
 * 值对象不含这两个字段。
 */
#include "OTA/ota_device_info.h"
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
    MAX_IMAGE = 8192 + 512,
    EEPROM_BYTES = 256
};

/* golden 期望值（tests/ota-vectors/expected.json，生成于冻结契约向量） */
static const uint8_t RAW_SHA_OLD[32] = {
    0x30, 0x81, 0xfa, 0x0a, 0xfc, 0x5b, 0xb2, 0xf3,
    0xa7, 0xd4, 0x56, 0xa2, 0x49, 0xcd, 0x8f, 0x07,
    0xd9, 0x51, 0x7d, 0x25, 0x7e, 0x58, 0x1e, 0x95,
    0x62, 0xbf, 0x3e, 0xb1, 0x02, 0xea, 0xdb, 0x1b
};
static const uint8_t HDR_SHA_OLD[32] = {
    0xe0, 0x25, 0xe0, 0x68, 0x3e, 0xa0, 0x0f, 0x5c,
    0xd0, 0x01, 0x61, 0xb7, 0xfe, 0xde, 0x22, 0x51,
    0xff, 0xb4, 0x0b, 0x9c, 0xac, 0xba, 0x6b, 0xba,
    0xfb, 0x6b, 0x39, 0xe2, 0x70, 0x2a, 0xa9, 0x44
};
static const uint8_t RAW_SHA_NEW[32] = {
    0xf6, 0x8f, 0x35, 0x7c, 0x70, 0x8c, 0x2d, 0x65,
    0xe6, 0xb1, 0x54, 0x76, 0x48, 0xe9, 0x55, 0xea,
    0x47, 0x94, 0x9d, 0x81, 0xbd, 0x52, 0xf2, 0xcd,
    0xed, 0x68, 0x4a, 0x8f, 0x64, 0x0e, 0x21, 0xc3
};
static const uint8_t HDR_SHA_NEW[32] = {
    0x5b, 0x50, 0x8e, 0xea, 0x3c, 0x36, 0x04, 0xef,
    0x42, 0xb5, 0x89, 0x5d, 0x44, 0xb1, 0xdf, 0x54,
    0x0a, 0x21, 0xe9, 0x10, 0xbd, 0x00, 0xb1, 0x84,
    0xff, 0x31, 0xab, 0x80, 0xf0, 0xc8, 0x24, 0xdf
};
/* .etu base_sha8 比较域期望（expected.json toy-patch.etu base_sha8，
 * 即 raw 域前 8B 截断）。 */
static const uint8_t BASE_SHA8_OLD[8] = {
    0x30, 0x81, 0xfa, 0x0a, 0xfc, 0x5b, 0xb2, 0xf3
};
/* OTA-XC-DEVICE-MODEL 冻结线端值：7 ASCII + NUL 恰 8 字节。 */
static const char MODEL_EXPECTED[8] = {
    'E', '-', 'T', 'r', 'a', 'c', 'k', '\0'
};

static uint8_t g_image[MAX_IMAGE];
static uint32_t g_image_len; /* 当前镜像长度（golden 4096） */
static uint8_t g_expected_raw[32]; /* 装配后镜像的独立 raw SHA 期望 */

static uint8_t g_eeprom[EEPROM_BYTES];

static uint32_t g_read_count;      /* 镜像读计数 */
static int g_read_budget;          /* -1 不限；N = 前 N 次成功 */
static int g_fail_read_off;        /* >= 0 时该 offset 首次读失败 */
static int g_fail_read_done;
static uint32_t g_eeprom_read_count;
static uint32_t g_eeprom_write_count;
static int g_eeprom_read_budget;   /* -1 不限 */

static int checks;
static int failures;

static void check(const char *name, int condition)
{
    checks++;
    if (!condition)
    {
        failures++;
        fprintf(stderr, "FAIL: %s\n", name);
    }
}

/* ---- 镜像 reader 仿真 ---- */
static int f_image_read(void *ctx, uint32_t off, uint8_t *dst, size_t len)
{
    (void)ctx;
    if (dst == NULL || len > g_image_len || off > g_image_len - len)
    {
        return -1;
    }
    if (g_read_budget >= 0 && g_read_count >= (uint32_t)g_read_budget)
    {
        return -1;
    }
    if (g_fail_read_off >= 0 && !g_fail_read_done &&
        off == (uint32_t)g_fail_read_off)
    {
        g_fail_read_done = 1;
        return -1;
    }
    g_read_count++;
    memcpy(dst, g_image + off, len);
    return 0;
}

static const boot_image_reader_t g_reader = { f_image_read, NULL };

/* ---- EEPROM 仿真（组件契约：只读，写计数必须恒 0） ---- */
static int e_write(uint8_t reg, const uint8_t *buf, uint16_t len)
{
    (void)reg;
    (void)buf;
    (void)len;
    g_eeprom_write_count++;
    return -1; /* 身份链绝不允许写 EEPROM；任何写调用即测试失败 */
}

static int e_read(uint8_t reg, uint8_t *buf, uint16_t len)
{
    if (g_eeprom_read_budget >= 0 &&
        g_eeprom_read_count >= (uint32_t)g_eeprom_read_budget)
    {
        return -1;
    }
    g_eeprom_read_count++;
    if ((uint32_t)reg + len > EEPROM_BYTES)
    {
        return -1;
    }
    memcpy(buf, g_eeprom + reg, len);
    return 0;
}

static const bcb_hal_t g_bcb_hal = { e_write, e_read };

/* ---- fixture 构造 ---- */

/* 重算 header_crc32（92..95）：header 前 92B 任一字段被改后调用。 */
static void refit_crc(void)
{
    uint8_t *header = g_image + OTA_FW_HEADER_OFFSET;
    uint32_t crc = boot_crc32(header, 92);

    header[92] = (uint8_t)(crc & 0xFF);
    header[93] = (uint8_t)((crc >> 8) & 0xFF);
    header[94] = (uint8_t)((crc >> 16) & 0xFF);
    header[95] = (uint8_t)((crc >> 24) & 0xFF);
}

/* 双零法重装订：镜像任意字节被篡改后，重算 fw_header 的
 * image_sha256（40..71）与 header_crc32（92..95），使 validate 的
 * header 完整性检查全部通过、缺陷暴露在目标检查项。 */
static void refit_header(void)
{
    uint8_t sha[32];
    boot_sha256_ctx_t ctx;
    uint8_t *header = g_image + OTA_FW_HEADER_OFFSET;

    memset(header + 40, 0, 32);
    memset(header + 92, 0, 4);
    boot_sha256_init(&ctx);
    boot_sha256_update(&ctx, g_image, g_image_len);
    boot_sha256_final(&ctx, sha);
    memcpy(header + 40, sha, 32);
    refit_crc();
}

static void compute_expected_raw(void)
{
    boot_sha256_ctx_t ctx;

    boot_sha256_init(&ctx);
    boot_sha256_update(&ctx, g_image, g_image_len);
    boot_sha256_final(&ctx, g_expected_raw);
}

static int load_golden(const char *path)
{
    FILE *f = fopen(path, "rb");
    if (f == NULL)
    {
        return -1;
    }
    if (fread(g_image, 1u, MAX_IMAGE, f) != IMAGE_BYTES)
    {
        fclose(f);
        return -1;
    }
    fclose(f);
    g_image_len = IMAGE_BYTES;
    return 0;
}

/* 锚定 golden 原始字节与 expected.json 一致（与 CI/Tools 同 fixture
 * 的逐字节证明）；两域期望互异 + raw 前 8B 即 .etu base_sha8 域。 */
static void anchor_golden(const char *tag, const uint8_t *file_sha,
                          const uint8_t *hdr_sha)
{
    uint8_t raw[32];
    boot_sha256_ctx_t ctx;

    boot_sha256_init(&ctx);
    boot_sha256_update(&ctx, g_image, g_image_len);
    boot_sha256_final(&ctx, raw);
    {
        char label[80];
        snprintf(label, sizeof(label), "ANCHOR %s file_sha256 == expected.json",
                 tag);
        check(label, memcmp(raw, file_sha, 32) == 0);
        snprintf(label, sizeof(label), "ANCHOR %s fw header sha == expected.json",
                 tag);
        check(label,
              memcmp(g_image + OTA_FW_HEADER_OFFSET + 40, hdr_sha, 32) == 0);
    }
}

/* 装配合法向量表（MSP 落 RAM、reset 落 App 区 thumb 位）并 refit 头部。 */
static void install_valid_vectors(void)
{
    g_image[0] = 0x00; g_image[1] = 0xF0; g_image[2] = 0x07; g_image[3] = 0x20;
    g_image[4] = 0x01; g_image[5] = 0x00; g_image[6] = 0x01; g_image[7] = 0x08;
    refit_header();
    compute_expected_raw();
}

/* 写合法 BCB 到指定块（slot 位掩码：1=A，2=B）；其余块保持 0xFF。 */
static void setup_bcb(int slots, uint16_t seq, uint32_t cur_vcode)
{
    bcb_t bcb;
    uint8_t raw[BCB_SIZE];

    memset(&bcb, 0, sizeof(bcb));
    bcb.magic = BCB_MAGIC;
    bcb.schema_ver = BCB_SCHEMA_VER;
    bcb.state = BCB_STATE_CONFIRMED;
    bcb.boot_try = 0u;
    bcb.copy_phase = BCB_COPY_NONE;
    bcb.seq = seq;
    bcb.resume_block = 0u;
    bcb.cur_vcode = cur_vcode;
    bcb.reserved = 0u;
    bcb_serialize(&bcb, raw);
    if ((slots & 1) != 0)
    {
        memcpy(g_eeprom + BCB_A_ADDR, raw, BCB_SIZE);
    }
    if ((slots & 2) != 0)
    {
        memcpy(g_eeprom + BCB_B_ADDR, raw, BCB_SIZE);
    }
}

static void reset_all(void)
{
    memset(g_eeprom, 0xFF, EEPROM_BYTES);
    g_read_count = 0u;
    g_read_budget = -1;
    g_fail_read_off = -1;
    g_fail_read_done = 0;
    g_eeprom_read_count = 0u;
    g_eeprom_write_count = 0u;
    g_eeprom_read_budget = -1;
    if (load_golden("tests/ota-vectors/toy-old.bin") != 0)
    {
        fprintf(stderr, "FAIL: golden fixture missing\n");
        failures++;
        return;
    }
    anchor_golden("toy-old", RAW_SHA_OLD, HDR_SHA_OLD);
    install_valid_vectors();
}

/* T1 golden 正例 + T7 摘要域分离 */
static void t1_golden_and_domains(void)
{
    ota_device_identity_t state;
    ota_device_info_t info;
    const uint8_t *header_sha;
    ota_device_result_t r;

    reset_all();
    /* expected.json 域分离自洽：两域完整值互异；raw 前 8B 即
     * toy-patch.etu base_sha8 域。 */
    check("T7 expected domains differ",
          memcmp(RAW_SHA_OLD, HDR_SHA_OLD, 32) != 0);
    check("T7 raw first 8B == .etu base_sha8 domain",
          memcmp(RAW_SHA_OLD, BASE_SHA8_OLD, 8) == 0);

    setup_bcb(3, 5u, 20700u); /* A/B 均合法，A 新 */
    memset(&state, 0, sizeof(state));
    memset(&info, 0xAA, sizeof(info));

    r = ota_device_identity_get(&state, &info, &g_reader, &g_bcb_hal);
    check("T1 result ok", r == OTA_DEVICE_OK);
    check("T1 bcb result A", state.bcb_result == BCB_ARBITER_A);
    check("T1 fw result ok", state.fw_header_result == BOOT_FW_OK);
    check("T1 model exact 8B", memcmp(info.model, MODEL_EXPECTED,
                                      sizeof(MODEL_EXPECTED)) == 0);
    check("T1 hw_rev", info.hw_rev == 1u);
    check("T1 layout_id", info.layout_id == 1u);
    check("T1 boot_ver", info.boot_ver == BOOT_VERSION);
    check("T1 cur_vcode", info.cur_vcode == 20700u);
    check("T1 image_sha256 == independent raw sha",
          memcmp(info.image_sha256, g_expected_raw, 32) == 0);

    /* T7：设备输出 raw 域 ≠ fixture 头内双零域；两域前 8B 互异
     * （.etu base_sha8 域 vs ETSL sha8 域不可互换）。 */
    header_sha = g_image + OTA_FW_HEADER_OFFSET + 40;
    check("T7 device raw != fixture header double-zero domain",
          memcmp(info.image_sha256, header_sha, 32) != 0);
    check("T7 two 8B domains differ",
          memcmp(info.image_sha256, header_sha, 8) != 0);
    check("T7 device raw first 8B == expected raw first 8B",
          memcmp(info.image_sha256, g_expected_raw, 8) == 0);
}

/* T2 fw_header 负例：逐项注入缺陷，断言 fail closed + 诊断码，
 * 且失败时 *out 不被写入（0xAA 污染保持）。 */
static void t2_header_negative(void)
{
    struct
    {
        const char *name;
        int expect_fw;
    } cases[] = {
        { "magic", BOOT_FW_ERR_MAGIC },
        { "header_crc", BOOT_FW_ERR_HEADER_CRC },
        { "image_sha_field", BOOT_FW_ERR_IMAGE_SHA },
        { "payload_tamper", BOOT_FW_ERR_IMAGE_SHA },
        { "image_len_over", BOOT_FW_ERR_IMAGE_LENGTH },
        { "image_len_under", BOOT_FW_ERR_IMAGE_LENGTH },
        { "vector_msp", BOOT_FW_ERR_VECTOR_MSP },
        { "vector_reset", BOOT_FW_ERR_VECTOR_RESET }
    };
    size_t i;

    for (i = 0; i < sizeof(cases) / sizeof(cases[0]); i++)
    {
        ota_device_identity_t state;
        ota_device_info_t info;
        ota_device_result_t r;
        uint8_t *header;

        reset_all();
        setup_bcb(3, 5u, 20700u);
        header = g_image + OTA_FW_HEADER_OFFSET;
        switch (i)
        {
        case 0: /* magic 首字节翻转（magic 检查先于 crc，无需 refit） */
            header[0] ^= 0xFFu;
            break;
        case 1: /* crc 字节翻转（crc 覆盖前 92B，不含自身） */
            header[93] ^= 0xFFu;
            break;
        case 2: /* sha 字段翻转 + 重装订 crc：sha 域完整性靠双零法暴露 */
            header[45] ^= 0xFFu;
            refit_crc();
            break;
        case 3: /* payload 篡改：header_crc 只覆盖头 92B，sha 全镜像失配 */
            g_image[0x500] ^= 0xFFu;
            break;
        case 4: /* image_len = OTA_APP_LENGTH+1（在 sha 读取前被拒） */
            header[36] = 0x01; header[37] = 0x00;
            header[38] = 0x0F; header[39] = 0x00;
            refit_crc();
            break;
        case 5: /* image_len < 头部下界（0x300 < 0x400+96） */
            header[36] = 0x00; header[37] = 0x03;
            header[38] = 0x00; header[39] = 0x00;
            refit_crc();
            break;
        case 6: /* MSP 落 RAM 区间外（RAM 为 [0x20000000,0x20080000]） */
            g_image[0] = 0xF1; g_image[1] = 0xFF;
            g_image[2] = 0xFF; g_image[3] = 0xFF;
            refit_header();
            break;
        case 7: /* reset 落 app 区间外（app 为 [0x08010000,0x08010000+F0000)） */
            g_image[4] = 0x01; g_image[5] = 0x00;
            g_image[6] = 0x00; g_image[7] = 0x08;
            refit_header();
            break;
        default:
            break;
        }

        memset(&state, 0, sizeof(state));
        memset(&info, 0xAA, sizeof(info));
        r = ota_device_identity_get(&state, &info, &g_reader, &g_bcb_hal);
        {
            char label[64];
            snprintf(label, sizeof(label), "T2 %s fail closed",
                     cases[i].name);
            check(label, r == OTA_DEVICE_ERR_FW_HEADER);
            snprintf(label, sizeof(label), "T2 %s diag code", cases[i].name);
            check(label, state.fw_header_result == cases[i].expect_fw);
            snprintf(label, sizeof(label), "T2 %s out untouched",
                     cases[i].name);
            check(label, ((uint8_t *)&info)[0] == 0xAAu);
        }
    }
}

/* T3 读 IO 负例。
 * raw SHA 阶段注入依赖 validate 读次数 = 1 header + 16 sha 块 + 1
 * vectors = 18（boot_fw_header.c FW_HASH_CHUNK_SIZE=256，4096B 镜像）；
 * 预算 18 恰好放行 validate，拦截 ota_device_info 的首次镜像读。 */
static void t3_read_io_negative(void)
{
    ota_device_identity_t state;
    ota_device_info_t info;
    ota_device_result_t r;

    /* header 读失败（validate 第一跳） */
    reset_all();
    setup_bcb(3, 5u, 20700u);
    g_fail_read_off = (int)OTA_FW_HEADER_OFFSET;
    memset(&state, 0, sizeof(state));
    r = ota_device_identity_get(&state, &info, &g_reader, &g_bcb_hal);
    check("T3 header read fail", r == OTA_DEVICE_ERR_FW_HEADER &&
          state.fw_header_result == BOOT_FW_ERR_READ);

    /* payload 读失败（validate 的 sha 循环阶段） */
    reset_all();
    setup_bcb(3, 5u, 20700u);
    g_fail_read_off = 0x500;
    memset(&state, 0, sizeof(state));
    r = ota_device_identity_get(&state, &info, &g_reader, &g_bcb_hal);
    check("T3 payload read fail (validate stage)",
          r == OTA_DEVICE_ERR_FW_HEADER &&
          state.fw_header_result == BOOT_FW_ERR_READ);

    /* raw SHA 阶段读失败：validate 完成（18 次读）后预算耗尽 */
    reset_all();
    setup_bcb(3, 5u, 20700u);
    g_read_budget = 18;
    memset(&state, 0, sizeof(state));
    r = ota_device_identity_get(&state, &info, &g_reader, &g_bcb_hal);
    check("T3 raw sha read fail", r == OTA_DEVICE_ERR_IMAGE_READ);
    check("T3 raw sha read consumed validate reads", g_read_count == 18u);
}

/* T4 BCB 仲裁语义（A/B/NONE 放行；身份权威在 fw_header） */
static void t4_bcb_arbitration(void)
{
    ota_device_identity_t state;
    ota_device_info_t info;
    ota_device_result_t r;

    /* 仅 A 合法 */
    reset_all();
    setup_bcb(1, 5u, 20700u);
    memset(&state, 0, sizeof(state));
    r = ota_device_identity_get(&state, &info, &g_reader, &g_bcb_hal);
    check("T4 only A ok", r == OTA_DEVICE_OK &&
          state.bcb_result == BCB_ARBITER_A);

    /* B 回绕更新（A=65530, B=5 → B 新） */
    reset_all();
    setup_bcb(1, 65530u, 20700u);
    setup_bcb(2, 5u, 20700u); /* 追加 B 块，A 保留 65530 */
    memset(&state, 0, sizeof(state));
    r = ota_device_identity_get(&state, &info, &g_reader, &g_bcb_hal);
    check("T4 wrap newer B ok", r == OTA_DEVICE_OK &&
          state.bcb_result == BCB_ARBITER_B);

    /* 仅 B 合法（A 块坏） */
    reset_all();
    setup_bcb(2, 8u, 20700u);
    memset(&state, 0, sizeof(state));
    r = ota_device_identity_get(&state, &info, &g_reader, &g_bcb_hal);
    check("T4 only B ok", r == OTA_DEVICE_OK &&
          state.bcb_result == BCB_ARBITER_B);

    /* 双块无效 → NONE：§3.2 fw_header 有效即可直接引导，照常返回身份 */
    reset_all();
    memset(&state, 0, sizeof(state));
    r = ota_device_identity_get(&state, &info, &g_reader, &g_bcb_hal);
    check("T4 double-bad NONE still ok", r == OTA_DEVICE_OK &&
          state.bcb_result == BCB_ARBITER_NONE);
    check("T4 NONE vcode from fw_header", info.cur_vcode == 20700u);
    check("T4 NONE sha from fw_header",
          memcmp(info.image_sha256, g_expected_raw, 32) == 0);

    /* BCB cur_vcode 与 fw_header 不一致 → 以 fw_header 为准
     * （J-Link 直刷后 BCB 必然 stale 的生产场景） */
    reset_all();
    setup_bcb(3, 5u, 20600u);
    memset(&state, 0, sizeof(state));
    r = ota_device_identity_get(&state, &info, &g_reader, &g_bcb_hal);
    check("T4 stale bcb vcode ignored", r == OTA_DEVICE_OK &&
          info.cur_vcode == 20700u);

    /* 每次调用重仲裁：首次 A，EEPROM 双块改坏后次轮刷新为 NONE */
    reset_all();
    setup_bcb(1, 5u, 20700u);
    memset(&state, 0, sizeof(state));
    r = ota_device_identity_get(&state, &info, &g_reader, &g_bcb_hal);
    check("T4 first call A", r == OTA_DEVICE_OK &&
          state.bcb_result == BCB_ARBITER_A);
    memset(g_eeprom, 0xFF, EEPROM_BYTES);
    r = ota_device_identity_get(&state, &info, &g_reader, &g_bcb_hal);
    check("T4 second call re-arbitrated NONE", r == OTA_DEVICE_OK &&
          state.bcb_result == BCB_ARBITER_NONE);
}

/* T5 BCB IO 失败 → fail closed */
static void t5_bcb_io_fail(void)
{
    ota_device_identity_t state;
    ota_device_info_t info;
    ota_device_result_t r;

    reset_all();
    setup_bcb(3, 5u, 20700u);
    g_eeprom_read_budget = 0;
    memset(&state, 0, sizeof(state));
    memset(&info, 0xAA, sizeof(info));
    r = ota_device_identity_get(&state, &info, &g_reader, &g_bcb_hal);
    check("T5 bcb io fail closed", r == OTA_DEVICE_ERR_BCB_IO);
    check("T5 bcb result error", state.bcb_result == BCB_ARBITER_ERROR);
    check("T5 out untouched", ((uint8_t *)&info)[0] == 0xAAu);
}

/* T6 参数负例 */
static void t6_arguments(void)
{
    ota_device_identity_t state;
    ota_device_info_t info;
    boot_image_reader_t bad_reader;

    reset_all();
    memset(&state, 0, sizeof(state));
    memset(&info, 0, sizeof(info));
    check("T6 null state",
          ota_device_identity_get(NULL, &info, &g_reader, &g_bcb_hal) ==
          OTA_DEVICE_ERR_ARGUMENT);
    check("T6 null out",
          ota_device_identity_get(&state, NULL, &g_reader, &g_bcb_hal) ==
          OTA_DEVICE_ERR_ARGUMENT);
    check("T6 null reader",
          ota_device_identity_get(&state, &info, NULL, &g_bcb_hal) ==
          OTA_DEVICE_ERR_ARGUMENT);
    check("T6 null bcb hal",
          ota_device_identity_get(&state, &info, &g_reader, NULL) ==
          OTA_DEVICE_ERR_ARGUMENT);
    bad_reader.read = NULL;
    bad_reader.ctx = NULL;
    check("T6 null read fn",
          ota_device_identity_get(&state, &info, &bad_reader, &g_bcb_hal) ==
          OTA_DEVICE_ERR_ARGUMENT);
}

/* T8 快照语义：缓存复用、零写副作用、重置后随镜像刷新 */
static void t8_snapshot(void)
{
    ota_device_identity_t state;
    ota_device_info_t first;
    ota_device_info_t second;
    uint32_t reads_after_first;
    ota_device_result_t r;

    reset_all();
    setup_bcb(3, 5u, 20700u);
    memset(&state, 0, sizeof(state));
    r = ota_device_identity_get(&state, &first, &g_reader, &g_bcb_hal);
    check("T8 first ok", r == OTA_DEVICE_OK);
    /* validate(1+16+1) + raw sha(16) = 34 次镜像读 */
    reads_after_first = g_read_count;
    check("T8 first read count 34", reads_after_first == 34u);

    r = ota_device_identity_get(&state, &second, &g_reader, &g_bcb_hal);
    check("T8 second ok", r == OTA_DEVICE_OK);
    check("T8 second cached (no extra image reads)",
          g_read_count == reads_after_first);
    check("T8 outputs identical", memcmp(&first, &second, sizeof(first)) == 0);
    check("T8 zero eeprom writes", g_eeprom_write_count == 0u);

    /* 快照重置（模拟重启 RAM 清零）+ 换镜像 toy-new.bin → 新身份 */
    memset(&state, 0, sizeof(state));
    if (load_golden("tests/ota-vectors/toy-new.bin") != 0)
    {
        check("T8 toy-new fixture loaded", 0);
        return;
    }
    anchor_golden("toy-new", RAW_SHA_NEW, HDR_SHA_NEW);
    install_valid_vectors();
    r = ota_device_identity_get(&state, &second, &g_reader, &g_bcb_hal);
    check("T8 rebuild after reset ok", r == OTA_DEVICE_OK);
    check("T8 rebuild read again", g_read_count > reads_after_first);
    check("T8 new vcode", second.cur_vcode == 20800u);
    check("T8 new raw sha",
          memcmp(second.image_sha256, g_expected_raw, 32) == 0);
    check("T8 new differs from old",
          memcmp(second.image_sha256, first.image_sha256, 32) != 0);
}

int main(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    checks = 0;
    failures = 0;

    t1_golden_and_domains();
    t2_header_negative();
    t3_read_io_negative();
    t4_bcb_arbitration();
    t5_bcb_io_fail();
    t6_arguments();
    t8_snapshot();

    printf("P3_2_OTA_DEVICE_INFO checks=%d failures=%d\n", checks, failures);
    return failures == 0 ? 0 : 1;
}
