#include "tiny_AES_decrypt.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

// S盒替换表: 代表GF(2^8)上的乘法逆并进行线性变换
static const uint8_t sbox[256] = {
    // 0     1     2     3     4     5     6     7     8     9     A     B     C     D     E     F
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16};

// 轮常量表: 用于密钥扩展
static const uint8_t rcon[11] = {
    0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36};

/**
 * @brief 字节代换变换
 *
 * 使用S盒对状态矩阵的每个字节进行非线性变换
 *
 * @param state 需要变换的状态(16字节)
 */
static void sub_bytes(uint8_t *state)
{
    for (int i = 0; i < 16; i++)
    {
        state[i] = sbox[state[i]];
    }
}

/**
 * @brief 行移位变换
 *
 * 对状态矩阵的行进行循环左移:
 * - 第0行: 不移位
 * - 第1行: 左移1个字节
 * - 第2行: 左移2个字节
 * - 第3行: 左移3个字节
 *
 * @param state 需要变换的状态(16字节)
 */
static void shift_rows(uint8_t *state)
{
    uint8_t temp;

    // 第1行左移1个字节
    temp = state[1];
    state[1] = state[5];
    state[5] = state[9];
    state[9] = state[13];
    state[13] = temp;

    // 第2行左移2个字节
    temp = state[2];
    state[2] = state[10];
    state[10] = temp;
    temp = state[6];
    state[6] = state[14];
    state[14] = temp;

    // 第3行左移3个字节
    temp = state[15];
    state[15] = state[11];
    state[11] = state[7];
    state[7] = state[3];
    state[3] = temp;
}

/**
 * @brief 单列混合变换
 *
 * 对状态矩阵的一列进行GF(2^8)上的矩阵乘法,用于MixColumns步骤
 * 标准AES中的多项式乘法：
 * [2 3 1 1]   [a]
 * [1 2 3 1] × [b]
 * [1 1 2 3]   [c]
 * [3 1 1 2]   [d]
 *
 * @param x 需要混合变换的列(4字节)
 * @return 混合变换后的列
 */
static uint32_t mix_single_column(uint32_t x)
{
    // 提取列中的4个字节
    uint8_t a = (uint8_t)x;         // 第0行
    uint8_t b = (uint8_t)(x >> 8);  // 第1行
    uint8_t c = (uint8_t)(x >> 16); // 第2行
    uint8_t d = (uint8_t)(x >> 24); // 第3行

    // 用于存储临时值的变量
    uint8_t a2, b2, c2, d2; // ×2的结果
    uint8_t a3, b3, c3, d3; // ×3的结果

    // GF(2^8)上的乘2操作: 左移一位，如果最高位是1，异或0x1B
    a2 = (a << 1) ^ (((a >> 7) & 1) * 0x1b);
    b2 = (b << 1) ^ (((b >> 7) & 1) * 0x1b);
    c2 = (c << 1) ^ (((c >> 7) & 1) * 0x1b);
    d2 = (d << 1) ^ (((d >> 7) & 1) * 0x1b);

    // GF(2^8)上的乘3操作: 乘2再异或原值
    a3 = a2 ^ a;
    b3 = b2 ^ b;
    c3 = c2 ^ c;
    d3 = d2 ^ d;

    // 计算每一行的结果并重组为32位整数
    uint8_t r0 = a2 ^ b3 ^ c ^ d; // 第0行: (2*a)⊕(3*b)⊕c⊕d
    uint8_t r1 = a ^ b2 ^ c3 ^ d; // 第1行: a⊕(2*b)⊕(3*c)⊕d
    uint8_t r2 = a ^ b ^ c2 ^ d3; // 第2行: a⊕b⊕(2*c)⊕(3*d)
    uint8_t r3 = a3 ^ b ^ c ^ d2; // 第3行: (3*a)⊕b⊕c⊕(2*d)

    // 将结果重组为32位整数返回
    return r0 | (r1 << 8) | (r2 << 16) | (r3 << 24);
}

/**
 * @brief 列混合变换
 *
 * 对状态矩阵的每一列进行GF(2^8)上的矩阵乘法
 *
 * @param state 需要变换的状态(16字节)
 */
static void mix_columns(uint8_t *state)
{
    uint32_t *state_ptr = (uint32_t *)state;

    for (int i = 0; i < 4; i++)
    {
        state_ptr[i] = mix_single_column(state_ptr[i]);
    }
}

/**
 * @brief 轮密钥加变换
 *
 * 将状态矩阵的每个字节与对应的轮密钥字节进行异或操作
 *
 * @param state 需要变换的状态(16字节)
 * @param round_key 扩展后的轮密钥
 * @param round 当前轮次
 */
static void add_round_key(uint8_t *state, const uint8_t *round_key, uint8_t round)
{
    for (int i = 0; i < 16; i++)
    {
        state[i] ^= round_key[round * 16 + i];
    }
}

/**
 * @brief 密钥扩展
 *
 * 将128位原始密钥扩展为11个轮密钥(176字节)
 *
 * @param round_key 用于存储扩展后的轮密钥
 * @param key 原始密钥(16字节)
 */
static void key_expansion(uint8_t *round_key, const uint8_t *key)
{
    uint8_t k = 0;
    uint8_t temp[4]; // 用于存储临时值

    // 密钥的前16个字节就是原始密钥
    for (int i = 0; i < 16; i++)
    {
        round_key[i] = key[i];
    }

    // 扩展密钥
    for (int i = 4; i < 44; i++) // 4 * 11 = 44 个字(176个字节)
    {
        // 临时存储上一个字
        for (int j = 0; j < 4; j++)
        {
            temp[j] = round_key[(i - 1) * 4 + j];
        }

        if (i % 4 == 0) // 每隔4个字进行特殊处理
        {
            // 循环左移一个字节
            uint8_t t = temp[0];
            temp[0] = temp[1];
            temp[1] = temp[2];
            temp[2] = temp[3];
            temp[3] = t;

            // S盒替换
            for (int j = 0; j < 4; j++)
            {
                temp[j] = sbox[temp[j]];
            }

            // 与轮常量异或
            temp[0] ^= rcon[i / 4];
        }

        // 生成新的字=前第4个字异或临时值
        for (int j = 0; j < 4; j++)
        {
            round_key[i * 4 + j] = round_key[(i - 4) * 4 + j] ^ temp[j];
        }
    }
}

/**
 * @brief AES上下文初始化
 *
 * 使用给定的密钥初始化AES上下文,执行密钥扩展
 *
 * @param ctx AES上下文
 * @param key 加密密钥(16字节)
 */
void AES_init_ctx(AES_ctx *ctx, const uint8_t key[16])
{
    key_expansion((uint8_t *)ctx->round_key, key);
}

/**
 * @brief AES单块加密
 *
 * 对单个128位块进行AES加密,包括初始轮、9个标准轮和一个最终轮
 * 在CTR模式中用于生成密钥流
 *
 * @param ctx AES上下文,包含扩展密钥
 * @param buffer 需要加密的数据块(16字节),操作完成后保存加密结果
 */
void AES_encrypt_block(AES_ctx *ctx, uint8_t *buffer)
{
    // 使用临时缓冲区避免潜在的字节序问题
    uint8_t state[16];
    memcpy(state, buffer, 16);

    // 初始轮密钥加
    add_round_key(state, (const uint8_t *)ctx->round_key, 0);

    // 9个主要轮
    for (int i = 1; i < 10; i++)
    {
        sub_bytes(state);                        // 字节代换
        shift_rows(state);                       // 行移位
        mix_columns(state);                      // 列混合
        add_round_key(state, (const uint8_t *)ctx->round_key, i); // 轮密钥加
    }

    // 最后一轮(无列混合)
    sub_bytes(state);
    shift_rows(state);
    add_round_key(state, (const uint8_t *)ctx->round_key, 10);

    // 将结果复制回原始buffer
    memcpy(buffer, state, 16);
}

/**
 * @brief 递增计数器
 *
 * 将16字节的计数器视为大端序整数递增
 *
 * @param counter 需要递增的计数器
 */
void increment_counter(uint8_t *counter)
{
    // 从最低有效字节开始增加
    for (int i = 15; i >= 0; i--)
    {
        if (++counter[i] != 0)
        {
            break; // 如果没有溢出,则结束循环
        }
    }
}

/**
 * @brief AES-CTR模式解密
 *
 * CTR模式下,解密操作与加密操作相同
 * 使用CTR模式对数据进行解密,实际上是生成密钥流并与密文异或
 *
 * @param ctx AES上下文,包含扩展密钥
 * @param buffer 需要解密的数据,操作完成后保存解密结果
 * @param length 数据长度(字节)
 * @param nonce_counter 随机数计数器(16字节),会被修改
 */
void AES_CTR_decrypt(AES_ctx *ctx, uint8_t *buffer, size_t length, uint8_t *nonce_counter)
{
    uint8_t counter_block[AES_BLOCK_SIZE]; // 用于加密的计数器块
    size_t i;

    // 保存原始计数器，用于重置或调试
    uint8_t original_counter[AES_BLOCK_SIZE];
    memcpy(original_counter, nonce_counter, AES_BLOCK_SIZE);

    // 逐块处理数据
    for (i = 0; i < length; i += AES_BLOCK_SIZE)
    {
        // 复制当前的nonce_counter到临时缓冲区进行加密
        memcpy(counter_block, nonce_counter, AES_BLOCK_SIZE);

        // 加密计数器块以生成密钥流块
        AES_encrypt_block(ctx, counter_block);

        // 将密钥流与密文异或得到明文，但只处理实际数据长度
        size_t block_size = ((i + AES_BLOCK_SIZE) <= length) ? AES_BLOCK_SIZE : (length - i);

        for (size_t j = 0; j < block_size; j++)
        {
            buffer[i + j] ^= counter_block[j];
        }

        // 增加计数器,为下一个块准备
        increment_counter(nonce_counter);
    }

    // 调试信息 - 这段注释掉的代码可以在需要时解除注释来观察计数器变化
    /*
    printf("初始计数器: ");
    for (i = 0; i < AES_BLOCK_SIZE; i++) printf("%02X ", original_counter[i]);
    printf("\n最终计数器: ");
    for (i = 0; i < AES_BLOCK_SIZE; i++) printf("%02X ", nonce_counter[i]);
    printf("\n");
    */
}

void Aes128_Ctr(uint8_t *buffer, size_t bytes_read)
{
    // 固定密钥(实际应用中应从安全源获取或通过密钥协商)
    uint8_t key[16] = {0x2b, 0x7e, 0x15, 0x16, 0x28, 0xae, 0xd2, 0xa6, 0xab, 0xf7, 0x15, 0x88, 0x09, 0xcf, 0x4f, 0x3c};

    // 从密文文件头读取 nonce_counter（前16字节）
    uint8_t nonce_counter[16];

    // 初始化AES上下文
    AES_ctx ctx;
    AES_init_ctx(&ctx, key);

    AES_CTR_decrypt(&ctx, buffer, bytes_read, nonce_counter);
}
