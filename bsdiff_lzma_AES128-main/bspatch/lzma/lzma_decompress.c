// #include <ustdio.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include "interface.h"
#include "LzmaDec.h"
#include "7zFile.h"
#include "vFile.h"

// #define LZMA_RAM_USE_DEBUG
#define LZMA_DEBUG 0

#ifdef LZMA_RAM_USE_DEBUG
static int ram_used_size = 0;
static int ram_used_max = 0;
#endif

static int lzma_initialized = 0; // 标记是否已初始化
static int header_read = 0;      // 标记是否已读取头部数据

void *lzma_alloc(ISzAllocPtr p, size_t size)
{
    void *mp;

    if (size == 0)
    {
        return NULL;
    }

    mp = vmalloc(size);

#ifdef LZMA_RAM_USE_DEBUG
    ram_used_size += _msize(mp);
    if (ram_used_max < ram_used_size)
        ram_used_max = ram_used_size;
    printk("ram used: now / max = %d / %d\n", ram_used_size, ram_used_max);
#endif

    return mp;
}

void lzma_free(ISzAllocPtr p, void *address)
{
    if (address != NULL)
    {
#ifdef LZMA_RAM_USE_DEBUG
        ram_used_size -= _msize(address);
        printk("ram used: now / max = %d / %d\n", ram_used_size, ram_used_max);
#endif
        vfree(address);
    }
}

ISzAlloc allocator = {lzma_alloc, lzma_free};
static CLzmaDec *lz_state = NULL;

// 读取并处理LZMA头部
static int lzma_read_header(vFile *pf)
{
    if (header_read)
        return 0;

    uint8_t header[LZMA_PROPS_SIZE + 8];
    size_t headerSize = sizeof(header);

    // 保存当前位置
    uint32_t current_pos;
    vfgetpos(pf, &current_pos);

    // 重置到文件开始
    vfsetpos(pf, 0);

    // 读取头部
    int readSize = vfread(pf, header, headerSize);
    if (readSize != headerSize)
    {
#ifdef LZMA_DEBUG
        printf("Failed to read LZMA header, read %d bytes\n", readSize);
#endif
        vfsetpos(pf, current_pos);
        return -1;
    }

    // 解析原始大小
    UInt64 unpack_size = 0;
    for (int i = 0; i < 8; i++)
    {
        unpack_size |= ((uint64_t)header[LZMA_PROPS_SIZE + i]) << (i * 8);
    }

#ifdef LZMA_DEBUG
    printf("Header read: LZMA properties + unpack size: %llu bytes\n", unpack_size);
#endif

    // 恢复文件位置
    vfsetpos(pf, current_pos);

    header_read = 1;
    return 0;
}

static int lzma_decompress_init(vFile *pf)
{
    // 如果已经初始化，则直接返回
    if (lzma_initialized)
        return 0;

    // 读取头部数据
    if (lzma_read_header(pf) != 0)
    {
        return -1;
    }

    // 保存当前位置
    uint32_t current_pos;
    vfgetpos(pf, &current_pos);

    // 重置到文件开始读取属性部分
    vfsetpos(pf, 0);

    uint8_t props[LZMA_PROPS_SIZE];
    int readSize = vfread(pf, props, LZMA_PROPS_SIZE);
    if (readSize != LZMA_PROPS_SIZE)
    {
#ifdef LZMA_DEBUG
        printf("Failed to read LZMA properties, read %d bytes\n", readSize);
#endif
        vfsetpos(pf, current_pos);
        return -1;
    }

    // 分配解码内存
    if (lz_state == NULL)
    {
        lz_state = (CLzmaDec *)lzma_alloc(NULL, sizeof(CLzmaDec));
        if (lz_state == NULL)
        {
#ifdef LZMA_DEBUG
            printf("Failed to allocate memory for LZMA state\n");
#endif
            vfsetpos(pf, current_pos);
            return -1;
        }
    }

    // 初始化解码器
    LzmaDec_Construct(lz_state);
    SRes res = LzmaDec_Allocate(lz_state, props, LZMA_PROPS_SIZE, &allocator);
    if (res != SZ_OK)
    {
#ifdef LZMA_DEBUG
        printf("LzmaDec_Allocate failed: %d\n", res);
#endif
        lzma_free(NULL, lz_state);
        lz_state = NULL;
        vfsetpos(pf, current_pos);
        return -1;
    }

    LzmaDec_Init(lz_state);
    lzma_initialized = 1;

    // 恢复文件位置
    vfsetpos(pf, current_pos);

#ifdef LZMA_DEBUG
    printf("LZMA decompressor initialized successfully\n");
#endif

    return 0;
}

int lzma_decompress_read(vFile *pf, uint8_t *buffer, int size)
{
    /* 如果缓冲区大小为0，仅初始化解压器 */
    if (size == 0 || buffer == NULL)
    {
        int res = lzma_decompress_init(pf);
        return (res == 0) ? 0 : -1;
    }

    /* 确保解压器已初始化 */
    if (!lzma_initialized)
    {
        int res = lzma_decompress_init(pf);
        if (res != 0)
        {
#ifdef LZMA_DEBUG
            printf("Failed to initialize decompressor: %d\n", res);
#endif
            return -1;
        }
    }

    /* 开始解压缩数据 */
    uint32_t position, file_size;
    size_t dcmprs_size = 0;
    uint8_t *inBuf;
    SizeT inProcessed;
    SizeT outProcessed = size;
    ELzmaFinishMode finishMode = LZMA_FINISH_ANY;
    ELzmaStatus status;
    SRes res;

    // 获取当前文件读指针和数据
    inBuf = vfgetpos(pf, &position);
    // 获取文件大小
    file_size = vfgetlen(pf);

#ifdef LZMA_DEBUG
    printf("Current position: %d, file size: %d\n", position, file_size);
#endif

    // 确定输入数据大小
    if (position >= file_size)
    {
#ifdef LZMA_DEBUG
        printf("End of input data reached\n");
#endif
        return 0; // 没有更多数据可解压
    }

    if ((position + size) > file_size)
    {
        inProcessed = file_size - position;
    }
    else
    {
        inProcessed = size;
    }

#ifdef LZMA_DEBUG
    printf("Input bytes to process: %d\n", inProcessed);
#endif

    // 解压数据
    res = LzmaDec_DecodeToBuf(lz_state, buffer, &outProcessed, inBuf, &inProcessed, finishMode, &status);

#ifdef LZMA_DEBUG
    printf("LzmaDec_DecodeToBuf result: %d, status: %d\n", res, status);
    printf("Processed input: %d bytes\n", inProcessed);
    printf("Generated output: %d bytes\n", outProcessed);
#endif

    if (res != SZ_OK)
    {
#ifdef LZMA_DEBUG
        printf("Decompression error: %d\n", res);
#endif
        return -1;
    }

    dcmprs_size = outProcessed;

    // 更新文件读指针
    position += inProcessed;
    vfsetpos(pf, position);

#ifdef LZMA_DEBUG
    printf("New file position: %d\n", position);
    printf("Decompressed size: %d\n", dcmprs_size);
#endif

    return dcmprs_size;
}

void lzma_decompress_finish(void)
{
    if (lz_state != NULL)
    {
        LzmaDec_Free(lz_state, &allocator);
        lzma_free(NULL, lz_state);
        lz_state = NULL;
        lzma_initialized = 0;
        header_read = 0;

#ifdef LZMA_DEBUG
        printf("Decompressor finalized\n");
#endif
    }
}
