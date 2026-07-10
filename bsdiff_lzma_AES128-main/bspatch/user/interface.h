#ifndef __USER_INTERFACE_H_
#define __USER_INTERFACE_H_

#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>
#include "bs_type.h"
#include "bspatch.h"
#include "crc32.h"
#include "vFile.h"
#include "LzmaDec.h"

// 确保缓冲区大小是4的倍数，以优化Flash写入
#define DCOMPRESS_BUFFER_SIZE 1024

#ifndef bspatch_debug
#define bspatch_debug 0
#endif

#define __DEBUG

#ifdef __DEBUG
#define bs_printf(...) printf("\r\n" __VA_ARGS__)
#else
#define bs_printf(...)
#endif

typedef struct patch_header
{
    uint32_t ph_hcrc;  /* patch Header CRC Checksum 差分包包头校验 大端 */
    uint32_t ph_psize; /* patch Data Size 差分包的大小 大端 */
    uint32_t ph_osize; /* Data Load Address 上一版本旧文件的大小 小端*/
    uint32_t ph_nsize; /* Entry Point Address 要升级的新文件的大小 小端*/
    uint32_t ph_ocrc;  /* Old patch Data CRC Checksum 上一版本旧文件的CRC 大端*/
    uint32_t ph_ncrc;  /* patch Data CRC Checksum 新文件的CRC 大端 */
    /* LZMA header fields (13 bytes) */
    uint8_t ph_lzma_props[5];  /* LZMA properties (5 bytes) */
    uint64_t ph_original_size; /* Uncompressed size (8 bytes) */
} patch_header_t;

/**
 * @brief 用户需注册的flash写入功能函数，bs会调用该函数写入用户的flash，特别注意在写入之前
 * 用户需要擦除，也就是该函数需自带擦除功能
 * @param addr bs将要写入的flash地址
 * @param p bs传入要写入的内容
 * @param len bs传入要写的长度
 * @return int 0代表成功，其他为错误码
 */
typedef int (*bs_flash_write_func)(uint32_t addr, const unsigned char *p, uint32_t len);

/**
 * @brief 用户需注册的内存申请函数，bs会调用该函数申请内存，请注意，最大可能会申请20k左右堆空间
 * @param size 要申请的内存大小
 * @return void* 返回非NULL代表成功
 */
typedef void *(*bs_malloc_func)(uint32_t size);

/**
 * @brief 用户需注册的内存释放函数，bs会调用该函数释放内存
 * @param ptr 要释放的内存地址
 */
typedef void (*bs_free_func)(void *ptr);

typedef struct
{
    bs_flash_write_func bs_flash_write;
    bs_malloc_func bs_malloc;
    bs_free_func bs_free;
} interface;
extern interface bs_user_func;

// LZMA related forward declarations
extern int lzma_decompress_read(vFile *pf, uint8_t *buffer, int size);
extern void lzma_decompress_finish(void);
extern int EraseAndWriteFlash(uint32_t address, const unsigned char *data, uint32_t length);

// Convert byte array to 64-bit integer
int64_t offtin(uint8_t *buf);


/******************************************************************************/
/************************************ 用户提供 *********************************/
/**
 * @brief 用户需要注册的函数
 *
 * @param user_func 用户创建一个结构体然后将功能依次注册
 * @return 0成功 1失败
 */
int bs_user_func_register(interface *user_func);

extern int bspatch_patch(patch_header_t header, uint8_t *old_data, uint32_t old_size, uint8_t *patch_data,
                     uint32_t patch_size, uint32_t newfile_addr, uint8_t *new_data, int64_t new_size);

/* bs所使用到的crc32校验函数，用户可酌情使用 */
extern unsigned int crc32(const unsigned char *buf, unsigned int size);

#endif // !__USER_INTERFACE_H_
