#ifndef TINY_AES_DECRYPT_H
#define TINY_AES_DECRYPT_H

#include <stdint.h>
#include <stddef.h>

/**
 * AES 解密算法的参数定义
 */
#define AES_BLOCK_SIZE 16 // AES块大小: 128位 = 16字节
#define AES_KEY_SIZE 16   // AES密钥大小: 128位 = 16字节 (也可以是16, 24, 或32字节)

/**
 * @brief AES密钥扩展结构体
 *
 * 存储AES算法的轮密钥,用于解密过程中的各个轮
 */
typedef struct
{
    uint32_t round_key[44]; // 128位密钥需要10轮(每轮4个字,加上初始轮)
} AES_ctx;

/**
 * @brief 初始化AES上下文
 *
 * @param ctx 待初始化的AES上下文
 * @param key 用于初始化的密钥(16字节)
 */
void AES_init_ctx(AES_ctx *ctx, const uint8_t *key);

/**
 * @brief AES-CTR模式解密函数
 *
 * 在CTR模式中,解密操作与加密操作相同
 *
 * @param ctx AES上下文,包含扩展密钥
 * @param buffer 需要解密的数据缓冲区,操作完成后将保存解密结果
 * @param length 数据长度(字节)
 * @param nonce_counter 随机数计数器(16字节),会被修改
 */
void AES_CTR_decrypt(AES_ctx *ctx, uint8_t *buffer, size_t length, uint8_t *nonce_counter);

/**
 * @brief AES单块加密函数
 *
 * 对单个128位(16字节)块进行AES加密,在CTR模式中用于生成密钥流
 *
 * @param ctx AES上下文,包含扩展密钥
 * @param buffer 需要加密的数据块,操作完成后将保存加密结果
 */
void AES_encrypt_block(AES_ctx *ctx, uint8_t *buffer);

void Aes128_Ctr(uint8_t *buffer, size_t bytes_read);

#endif // TINY_AES_DECRYPT_H
