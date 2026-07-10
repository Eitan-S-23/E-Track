/*
 * main.c - Entry point for bsdiff program with LZMA compression
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <errno.h>

#include "bsdiff/bsdiff.h"
#include "file/vFile.h"
#include "user/bs_user_interface.h"
#include "user/bs_type.h"
#include "lib/crc32.h"
#include "AES128_CTR/tiny_AES_encrypt.h"

// LZMA includes
#include "CpuArch.h"
#include "Alloc.h"
#include "7zFile.h"
#include "7zVersion.h"
#include "LzFind.h"
#include "LzmaDec.h"
#include "LzmaEnc.h"

#ifdef _WIN32
#include <windows.h>
#include <wincrypt.h>
#endif

// Define user bs_user_interface functions
bs_user_interface bs_user_func = {
    .bs_malloc = (bs_malloc_func)malloc,
    .bs_free = free,
    .bs_flash_write = NULL};

// Temporary file for storing uncompressed diff data
#define TEMP_DIFF_FILE "temp_diff.data"

// LZMA 参数的默认值
#define DEFAULT_LC 2
#define DEFAULT_LP 0
#define DEFAULT_PB 0
#define DEFAULT_FB 64
#define DEFAULT_DICT_SIZE (1 << 12) // 4KB
#define DEFAULT_ALGO 1
#define DEFAULT_WRITE_END_MARK 1

// 显示帮助信息
void print_usage(const char *program_name)
{
    printf("Usage: %s oldfile newfile patchfile [options]\n", program_name);
    printf("\nLZMA Compression Options:\n");
    printf("  -lc NUM        Literal Context bits (0-8, default: %d)\n", DEFAULT_LC);
    printf("  -lp NUM        Literal Position bits (0-4, default: %d)\n", DEFAULT_LP);
    printf("  -pb NUM        Position Bits (0-4, default: %d)\n", DEFAULT_PB);
    printf("  -fb NUM        Fast Bytes (5-273, default: %d)\n", DEFAULT_FB);
    printf("  -dict NUM      Dictionary Size in KB (default: %d)\n", DEFAULT_DICT_SIZE >> 10);
    printf("  -a NUM         Algorithm (0-fast, 1-normal, default: %d)\n", DEFAULT_ALGO);
    printf("  -eos NUM       Write End Of Stream marker (0-no, 1-yes, default: %d)\n", DEFAULT_WRITE_END_MARK);
    printf("\nAES Encryption Options:\n");
    printf("  -aes NUM       Enable AES-128-CTR encryption (0-no, 1-yes, default: 1)\n");
    printf("  -h             Show this help message\n");
    printf("\nExample:\n");
    printf("  %s oldfile newfile patchfile -lc 3 -dict 8 -aes 1\n", program_name);
}

// 检查参数是否在有效范围内
int validate_params(int lc, int lp, int pb, int fb, int dict_size_kb, int algo, int write_end_mark)
{
    if (lc < 0 || lc > 8)
    {
        fprintf(stderr, "Error: lc must be between 0 and 8\n");
        return 0;
    }
    if (lp < 0 || lp > 4)
    {
        fprintf(stderr, "Error: lp must be between 0 and 4\n");
        return 0;
    }
    if (pb < 0 || pb > 4)
    {
        fprintf(stderr, "Error: pb must be between 0 and 4\n");
        return 0;
    }
    if (fb < 5 || fb > 273)
    {
        fprintf(stderr, "Error: fb must be between 5 and 273\n");
        return 0;
    }
    if (dict_size_kb < 1)
    {
        fprintf(stderr, "Error: dictSize must be at least 1 KB\n");
        return 0;
    }
    if (algo < 0 || algo > 1)
    {
        fprintf(stderr, "Error: algo must be 0 or 1\n");
        return 0;
    }
    if (write_end_mark < 0 || write_end_mark > 1)
    {
        fprintf(stderr, "Error: eos must be 0 or 1\n");
        return 0;
    }
    // 检查 lc+lp 不超过总限制
    if (lc + lp > 4)
    {
        fprintf(stderr, "Warning: The sum of lc and lp should not exceed 4 for low memory systems\n");
        // 这里只是警告，不返回错误
    }
    return 1;
}

// Convert 64-bit integer to byte array
static void offtout(int64_t x, uint8_t *buf)
{
    int64_t y;

    if (x < 0)
        y = -x;
    else
        y = x;

    buf[0] = y % 256;
    y -= buf[0];
    y = y / 256;
    buf[1] = y % 256;
    y -= buf[1];
    y = y / 256;
    buf[2] = y % 256;
    y -= buf[2];
    y = y / 256;
    buf[3] = y % 256;
    y -= buf[3];
    y = y / 256;
    buf[4] = y % 256;
    y -= buf[4];
    y = y / 256;
    buf[5] = y % 256;
    y -= buf[5];
    y = y / 256;
    buf[6] = y % 256;
    y -= buf[6];
    y = y / 256;
    buf[7] = y % 256;

    if (x < 0)
        buf[7] |= 0x80;
}

// Read file to memory using standard file operations
static uint8_t *read_file_to_memory(const char *filename, int64_t *size)
{
    FILE *file;
    uint8_t *data;
    int64_t file_size;

    file = fopen(filename, "rb");
    if (file == NULL)
    {
        fprintf(stderr, "Error opening %s: %s\n", filename, strerror(errno));
        return NULL;
    }

    // Get file size
    fseek(file, 0, SEEK_END);
    file_size = ftell(file);
    fseek(file, 0, SEEK_SET);

    // Allocate memory
    data = (uint8_t *)bs_user_func.bs_malloc(file_size + 1);
    if (data == NULL)
    {
        fprintf(stderr, "Out of memory\n");
        fclose(file);
        return NULL;
    }

    // Read file content
    if (fread(data, 1, file_size, file) != file_size)
    {
        fprintf(stderr, "Error reading from %s: %s\n", filename, strerror(errno));
        bs_user_func.bs_free(data);
        fclose(file);
        return NULL;
    }

    fclose(file);
    *size = file_size;
    return data;
}

// Write callback function for bsdiff
static int file_write(struct bsdiff_stream *stream, const void *buffer, int size)
{
    FILE *file = (FILE *)stream->opaque;

    if (fwrite(buffer, 1, size, file) != size)
    {
        return -1;
    }

    return 0;
}

// LZMA streaming memory read bs_user_interface
typedef struct
{
    const uint8_t *data;
    size_t size;
    size_t pos;
} MemReadState;

static SRes MemReadCallback(void *p, void *buf, size_t *size)
{
    MemReadState *state = (MemReadState *)p;
    size_t remainingSize = state->size - state->pos;
    size_t readSize = *size;

    if (readSize > remainingSize)
        readSize = remainingSize;

    if (readSize > 0)
    {
        memcpy(buf, state->data + state->pos, readSize);
        state->pos += readSize;
    }

    *size = readSize;
    return SZ_OK;
}

// LZMA streaming file write bs_user_interface
typedef struct
{
    FILE *file;
} FileWriteState;

static size_t FileWriteCallback(void *p, const void *buf, size_t size)
{
    FileWriteState *state = (FileWriteState *)p;
    printf("FileWriteCallback called with size: %zu\n", size);
    size_t written = fwrite(buf, 1, size, state->file);
    printf("Written bytes: %zu\n", written);
    return written;
}

void Aes128_Ctr(char *patch, char *encrypt)
{
    // 固定密钥(实际应用中应从安全源获取或通过密钥协商)
    uint8_t key[16] = {0x2b, 0x7e, 0x15, 0x16, 0x28, 0xae, 0xd2, 0xa6, 0xab, 0xf7, 0x15, 0x88, 0x09, 0xcf, 0x4f, 0x3c};

    // 生成随机的 12 字节 nonce，并将后 4 字节置为 0 作为 counter 初始值（形成 16 字节 nonce||counter）
    uint8_t nonce_counter[16];
    // 生成安全随机字节
#ifdef _WIN32
    {
        HCRYPTPROV hProv = 0;
        uint8_t tmp[12];
        if (!CryptAcquireContext(&hProv, NULL, NULL, PROV_RSA_FULL, CRYPT_VERIFYCONTEXT))
        {
            fprintf(stderr, "警告: CryptAcquireContext 失败，使用弱随机回退\n");
            for (int i = 0; i < 12; i++)
                tmp[i] = (uint8_t)rand();
        }
        else
        {
            if (!CryptGenRandom(hProv, 12, tmp))
            {
                fprintf(stderr, "警告: CryptGenRandom 失败，使用弱随机回退\n");
                for (int i = 0; i < 12; i++)
                    tmp[i] = (uint8_t)rand();
            }
            CryptReleaseContext(hProv, 0);
        }
        // 前12字节为随机 nonce，后4字节为0作为计数器初始值
        memcpy(nonce_counter, tmp, 12);
        nonce_counter[12] = 0;
        nonce_counter[13] = 0;
        nonce_counter[14] = 0;
        nonce_counter[15] = 0;
    }
#else
    // 非 Windows 平台：尝试从 /dev/urandom 读取 12 字节
    FILE *ur = fopen("/dev/urandom", "rb");
    if (ur)
    {
        if (fread(nonce_counter, 1, 12, ur) != 12)
        {
            fprintf(stderr, "警告: 读取 /dev/urandom 失败，使用弱随机回退\n");
            for (int i = 0; i < 12; i++)
                nonce_counter[i] = (uint8_t)rand();
        }
        fclose(ur);
    }
    else
    {
        fprintf(stderr, "警告: 无法打开 /dev/urandom，使用弱随机回退\n");
        for (int i = 0; i < 12; i++)
            nonce_counter[i] = (uint8_t)rand();
    }
    // 后4字节为0
    nonce_counter[12] = 0;
    nonce_counter[13] = 0;
    nonce_counter[14] = 0;
    nonce_counter[15] = 0;
#endif

    // 初始化AES上下文
    AES_ctx ctx;
    AES_init_ctx(&ctx, key);

    // 打开输入文件
    FILE *infile = fopen(patch, "rb");
    if (infile == NULL)
    {
        printf("无法打开输入文件: %s\n", patch);
        return;
    }

    // 打开输出文件
    FILE *outfile = fopen(encrypt, "wb");
    if (outfile == NULL)
    {
        printf("无法打开输出文件: %s\n", encrypt);
        fclose(infile);
        return;
    }

    // 缓冲区用于读取和处理数据
    uint8_t buffer[AES_BLOCK_SIZE * 16]; // 一次处理16个块
    size_t bytes_read;

    // 先将 nonce_counter 写入输出文件头（前16字节）
    if (fwrite(nonce_counter, 1, 16, outfile) != 16)
    {
        fprintf(stderr, "写入输出文件头 nonce 失败\n");
        fclose(infile);
        fclose(outfile);
        return;
    }

    // 读取、加密并写入数据
    while ((bytes_read = fread(buffer, 1, sizeof(buffer), infile)) > 0)
    {
        // 使用CTR模式加密数据
        AES_CTR_encrypt(&ctx, buffer, bytes_read, nonce_counter);

        // 写入加密后的数据到输出文件
        fwrite(buffer, 1, bytes_read, outfile);
    }

    // 关闭文件
    fclose(infile);
    fclose(outfile);

    printf("加密完成: %s -> %s\n", patch, encrypt);
}

// 截取字符串中".bin"前面的部分
char *get_part_before_bin(const char *str)
{
    if (str == NULL)
    {
        return NULL;
    }

    // 为了不修改原字符串，先复制一份
    char *copy = strdup(str);
    if (copy == NULL)
    {
        return NULL;
    }

    // 查找".bin"的位置
    char *bin_pos = strstr(copy, ".bin");

    // 如果找到，则截断字符串
    if (bin_pos != NULL)
    {
        *bin_pos = '\0'; // 在".bin"开始处添加字符串结束符
    }

    return copy;
}

// Create diff and then compress it with LZMA
int main(int argc, char *argv[])
{
    uint8_t *old_data, *new_data;
    int64_t old_size, new_size;
    patch_header_t header;
    FILE *temp_diff_file, *final_patch_file;
    struct bsdiff_stream stream;
    int result = 0;

    // LZMA参数
    int lc = DEFAULT_LC;
    int lp = DEFAULT_LP;
    int pb = DEFAULT_PB;
    int fb = DEFAULT_FB;
    int dict_size_kb = DEFAULT_DICT_SIZE >> 10; // 将字节转换为KB
    int algo = DEFAULT_ALGO;
    int write_end_mark = DEFAULT_WRITE_END_MARK;

    // AES加密参数（默认启用）
    int enable_aes = 1;

    // 解析基本参数
    if (argc < 4)
    {
        print_usage(argv[0]);
        return 1;
    }

    // 解析选项参数
    int i;
    for (i = 4; i < argc; i++)
    {
        if (strcmp(argv[i], "-lc") == 0 && i + 1 < argc)
        {
            lc = atoi(argv[++i]);
        }
        else if (strcmp(argv[i], "-lp") == 0 && i + 1 < argc)
        {
            lp = atoi(argv[++i]);
        }
        else if (strcmp(argv[i], "-pb") == 0 && i + 1 < argc)
        {
            pb = atoi(argv[++i]);
        }
        else if (strcmp(argv[i], "-fb") == 0 && i + 1 < argc)
        {
            fb = atoi(argv[++i]);
        }
        else if (strcmp(argv[i], "-dict") == 0 && i + 1 < argc)
        {
            dict_size_kb = atoi(argv[++i]);
        }
        else if (strcmp(argv[i], "-a") == 0 && i + 1 < argc)
        {
            algo = atoi(argv[++i]);
        }
        else if (strcmp(argv[i], "-eos") == 0 && i + 1 < argc)
        {
            write_end_mark = atoi(argv[++i]);
        }
        else if (strcmp(argv[i], "-aes") == 0 && i + 1 < argc)
        {
            enable_aes = atoi(argv[++i]);
        }
        else if (strcmp(argv[i], "-h") == 0)
        {
            print_usage(argv[0]);
            return 0;
        }
        else
        {
            fprintf(stderr, "Unknown option: %s\n", argv[i]);
            print_usage(argv[0]);
            return 1;
        }
    }

    // 验证参数有效性
    if (!validate_params(lc, lp, pb, fb, dict_size_kb, algo, write_end_mark))
    {
        print_usage(argv[0]);
        return 1;
    }

    // Read old file
    old_data = read_file_to_memory(argv[1], &old_size);
    if (old_data == NULL)
    {
        return 1;
    }

    // Read new file
    new_data = read_file_to_memory(argv[2], &new_size);
    if (new_data == NULL)
    {
        bs_user_func.bs_free(old_data);
        return 1;
    }

    // Create temporary diff file (uncompressed)
    if ((temp_diff_file = fopen(TEMP_DIFF_FILE, "wb")) == NULL)
    {
        fprintf(stderr, "Error creating temporary file: %s\n", strerror(errno));
        bs_user_func.bs_free(old_data);
        bs_user_func.bs_free(new_data);
        return 1;
    }

    // Initialize bsdiff stream
    stream.malloc = (void *(*)(size_t))bs_user_func.bs_malloc;
    stream.free = bs_user_func.bs_free;
    stream.write = file_write;
    stream.opaque = temp_diff_file;

    // Run diff algorithm
    printf("Running bsdiff algorithm...\n");
    if (bsdiff(old_data, old_size, new_data, new_size, &stream))
    {
        fprintf(stderr, "bsdiff failed\n");
        bs_user_func.bs_free(old_data);
        bs_user_func.bs_free(new_data);
        fclose(temp_diff_file);
        remove(TEMP_DIFF_FILE);
        return 1;
    }

    // Close the temporary diff file
    fclose(temp_diff_file);

    // Get size of uncompressed diff data
    struct stat temp_diff_stat;
    if (stat(TEMP_DIFF_FILE, &temp_diff_stat) != 0)
    {
        fprintf(stderr, "Error getting temp file size: %s\n", strerror(errno));
        bs_user_func.bs_free(old_data);
        bs_user_func.bs_free(new_data);
        remove(TEMP_DIFF_FILE);
        return 1;
    }
    int64_t diff_size = temp_diff_stat.st_size;
    printf("Uncompressed diff size: %lld bytes\n", diff_size);

    // Open files for compression
    temp_diff_file = fopen(TEMP_DIFF_FILE, "rb");
    if (temp_diff_file == NULL)
    {
        fprintf(stderr, "Error opening temp file for reading: %s\n", strerror(errno));
        bs_user_func.bs_free(old_data);
        bs_user_func.bs_free(new_data);
        remove(TEMP_DIFF_FILE);
        return 1;
    }

    // Make sure we're at the beginning of the temporary file
    fseek(temp_diff_file, 0, SEEK_SET);

    // Load the entire temporary file into memory for compression
    uint8_t *temp_buffer = (uint8_t *)bs_user_func.bs_malloc(diff_size);
    if (temp_buffer == NULL)
    {
        fprintf(stderr, "Error allocating memory for temp buffer\n");
        bs_user_func.bs_free(old_data);
        bs_user_func.bs_free(new_data);
        fclose(temp_diff_file);
        remove(TEMP_DIFF_FILE);
        return 1;
    }

    if (fread(temp_buffer, 1, diff_size, temp_diff_file) != diff_size)
    {
        fprintf(stderr, "Error reading temporary file\n");
        bs_user_func.bs_free(temp_buffer);
        bs_user_func.bs_free(old_data);
        bs_user_func.bs_free(new_data);
        fclose(temp_diff_file);
        remove(TEMP_DIFF_FILE);
        return 1;
    }

    // Close the temporary file as we now have its contents in memory
    fclose(temp_diff_file);

    final_patch_file = fopen(argv[3], "wb");
    if (final_patch_file == NULL)
    {
        fprintf(stderr, "Error opening patch file for writing: %s\n", strerror(errno));
        bs_user_func.bs_free(temp_buffer);
        bs_user_func.bs_free(old_data);
        bs_user_func.bs_free(new_data);
        remove(TEMP_DIFF_FILE);
        return 1;
    }

    // Initialize patch header
    memset(&header, 0, sizeof(patch_header_t));
    // Set sizes in header
    header.ph_osize = (uint32_t)old_size; // 小端
    header.ph_nsize = (uint32_t)new_size; // 小端

    // Calculate CRC values for old and new files
    header.ph_ocrc = BigtoLittle32(crc32(old_data, old_size)); // 大端
    header.ph_ncrc = BigtoLittle32(crc32(new_data, new_size)); // 大端

    // We will need to set ph_psize later after compression

    // Store uncompressed size in the header
    header.ph_original_size = diff_size;

    // Allocate memory for the compressed data
    // We'll allocate a buffer that's big enough to hold the compressed data
    // LZMA usually compresses data to a smaller size, but we'll allocate the
    // same amount of memory as the uncompressed data to be safe
    size_t compressedSize = diff_size;
    uint8_t *compressedBuffer = (uint8_t *)bs_user_func.bs_malloc(compressedSize);
    if (compressedBuffer == NULL)
    {
        fprintf(stderr, "Error allocating memory for compressed buffer\n");
        bs_user_func.bs_free(temp_buffer);
        bs_user_func.bs_free(old_data);
        bs_user_func.bs_free(new_data);
        fclose(final_patch_file);
        remove(TEMP_DIFF_FILE);
        remove(argv[3]);
        return 1;
    }

    // Compress the data using LzmaCompress
    // This is a simpler bs_user_interface compared to LzmaEnc_Encode
    size_t propsSize = LZMA_PROPS_SIZE;
    printf("Compressing diff data with LZMA...\n");
    printf("Input buffer size: %lld bytes\n", diff_size);

    // 显示LZMA压缩参数
    printf("LZMA Parameters:\n");
    printf("  - lc: %d\n", lc);
    printf("  - lp: %d\n", lp);
    printf("  - pb: %d\n", pb);
    printf("  - fb: %d\n", fb);
    printf("  - dictSize: %d KB\n", dict_size_kb);
    printf("  - algo: %d\n", algo);
    printf("  - writeEndMark: %d\n", write_end_mark);

    // Setup LZMA properties
    CLzmaEncProps props;
    LzmaEncProps_Init(&props);
    props.level = 9;                      // Maximum compression level
    props.dictSize = dict_size_kb * 1024; // 转换为字节
    props.lc = lc;
    props.lp = lp;
    props.pb = pb;
    props.fb = fb;
    props.algo = algo;
    props.numThreads = 1; // Single-threaded mode
    props.writeEndMark = write_end_mark;

    // Compress the data
    SRes lzma_res = LzmaEncode(
        compressedBuffer, &compressedSize,
        temp_buffer, diff_size,
        &props, header.ph_lzma_props, &propsSize,
        props.writeEndMark, // 使用writeEndMark结束标记，增强解压可靠性
        NULL,               // No progress callback
        &g_Alloc, &g_Alloc);

    printf("LZMA compression result: %d\n", lzma_res);
    printf("Compressed size: %zu bytes\n", compressedSize);
    printf("Properties size: %zu bytes\n", propsSize);

    if (lzma_res != SZ_OK)
    {
        fprintf(stderr, "Error: LZMA compression failed: %d\n", lzma_res);
        bs_user_func.bs_free(compressedBuffer);
        bs_user_func.bs_free(temp_buffer);
        bs_user_func.bs_free(old_data);
        bs_user_func.bs_free(new_data);
        fclose(final_patch_file);
        remove(TEMP_DIFF_FILE);
        remove(argv[3]);
        return 1;
    }

    // Set the compressed size in the header
    header.ph_psize = BigtoLittle32((uint32_t)compressedSize);

    // Calculate header CRC
    header.ph_hcrc = 0; // Temporarily set to 0 for calculation
    header.ph_hcrc = BigtoLittle32(crc32((const unsigned char *)&header, sizeof(patch_header_t)));

    // Write the header to the patch file
    fseek(final_patch_file, 0, SEEK_SET);
    if (fwrite(&header, sizeof(patch_header_t), 1, final_patch_file) != 1)
    {
        fprintf(stderr, "Error writing header to patch file\n");
        bs_user_func.bs_free(compressedBuffer);
        bs_user_func.bs_free(temp_buffer);
        bs_user_func.bs_free(old_data);
        bs_user_func.bs_free(new_data);
        fclose(final_patch_file);
        remove(TEMP_DIFF_FILE);
        remove(argv[3]);
        return 1;
    }

    // Write the compressed data to the patch file
    if (fwrite(compressedBuffer, 1, compressedSize, final_patch_file) != compressedSize)
    {
        fprintf(stderr, "Error writing compressed data to patch file\n");
        bs_user_func.bs_free(compressedBuffer);
        bs_user_func.bs_free(temp_buffer);
        bs_user_func.bs_free(old_data);
        bs_user_func.bs_free(new_data);
        fclose(final_patch_file);
        remove(TEMP_DIFF_FILE);
        remove(argv[3]);
        return 1;
    }

    // Clean up
    bs_user_func.bs_free(compressedBuffer);
    bs_user_func.bs_free(temp_buffer);
    bs_user_func.bs_free(old_data);
    bs_user_func.bs_free(new_data);
    fclose(final_patch_file);
    remove(TEMP_DIFF_FILE); // Remove the temporary file

    // Get final patch file size for reporting
    struct stat final_patch_stat;
    if (stat(argv[3], &final_patch_stat) != 0)
    {
        fprintf(stderr, "Error getting final patch file size: %s\n", strerror(errno));
        return 1;
    }

    printf("Successfully created compressed patch: %s\n", argv[3]);
    printf("  - Original file size: %lld bytes\n", old_size);
    printf("  - New file size: %lld bytes\n", new_size);
    printf("  - Uncompressed diff size: %lld bytes\n", diff_size);
    printf("  - Compressed patch size: %lld bytes\n", (int64_t)final_patch_stat.st_size);

    // 根据enable_aes参数决定是否加密
    if (enable_aes)
    {
        char encrypt[1024];
        sprintf(encrypt, "%s_encrypt.bin", get_part_before_bin(argv[3]));
        printf("\nEncrypting patch with AES-128-CTR...\n");
        Aes128_Ctr(argv[3], encrypt);
        printf("Encrypted patch saved as: %s\n", encrypt);
    }
    else
    {
        printf("\nAES encryption is disabled, patch file is not encrypted.\n");
    }

    return 0;
}
