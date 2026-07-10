/*
 * main.c - Entry point for bspatch program with LZMA decompression
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <errno.h>
#include "interface.h"
#include "AES128_CTR/tiny_AES_decrypt.h"

// Define user interface functions
interface bs_user_func = {
    .bs_malloc = (bs_malloc_func)malloc,
    .bs_free = free,
    .bs_flash_write = NULL};

// Read the entire file into memory
static uint8_t *read_entire_file(const char *filename, int64_t file_size)
{
    FILE *file = fopen(filename, "rb");
    if (file == NULL)
    {
        fprintf(stderr, "Error opening %s: %s\n", filename, strerror(errno));
        return NULL;
    }

    // Allocate memory for the entire file
    uint8_t *data = (uint8_t *)bs_user_func.bs_malloc(file_size);
    if (data == NULL)
    {
        fprintf(stderr, "Out of memory\n");
        fclose(file);
        return NULL;
    }

    // Read the entire file into memory
    if (fread(data, 1, file_size, file) != file_size)
    {
        fprintf(stderr, "Error reading from %s: %s\n", filename, strerror(errno));
        bs_user_func.bs_free(data);
        fclose(file);
        return NULL;
    }

    fclose(file);
    return data;
}

// Initialize memory for the new file
static uint8_t *init_new_file_memory(int64_t size)
{
    uint8_t *data = (uint8_t *)bs_user_func.bs_malloc(size);
    if (data == NULL)
    {
        fprintf(stderr, "Out of memory\n");
        return NULL;
    }

    return data;
}

// Write memory to file
static int write_memory_to_file(uint8_t *data, int64_t size, const char *filename)
{
    FILE *file = fopen(filename, "wb");
    if (file == NULL)
    {
        fprintf(stderr, "Error opening %s for writing: %s\n", filename, strerror(errno));
        return -1;
    }

    if (fwrite(data, 1, size, file) != size)
    {
        fprintf(stderr, "Error writing to %s: %s\n", filename, strerror(errno));
        fclose(file);
        return -1;
    }

    fclose(file);
    return 0;
}

int main(int argc, char *argv[])
{
    uint8_t *old_data, *new_data;
    int64_t old_size, new_size;
    patch_header_t header;
    FILE *patch_file;
    uint32_t calc_crc;
    uint8_t *patch_data = NULL;

    // AES解密相关变量
    int is_encrypted = 0;
    uint8_t *decrypted_data = NULL;
    size_t decrypted_size = 0;
    const char *temp_file = "decrypted_patch.tmp";
    int temp_file_created = 0;

    // AES密钥（必须与bsdiff端一致）
    const uint8_t key[16] = {
        0x2b, 0x7e, 0x15, 0x16, 0x28, 0xae, 0xd2, 0xa6,
        0xab, 0xf7, 0x15, 0x88, 0x09, 0xcf, 0x4f, 0x3c
    };

    if (argc != 4)
    {
        fprintf(stderr, "usage: %s oldfile newfile patchfile\n", argv[0]);
        return 1;
    }

    // Open patch file
    if ((patch_file = fopen(argv[3], "rb")) == NULL)
    {
        fprintf(stderr, "Error opening %s: %s\n", argv[3], strerror(errno));
        return 1;
    }

    // 检测文件名是否包含 "_encrypt" 来判断是否为加密文件
    is_encrypted = (strstr(argv[3], "_encrypt") != NULL);

    if (is_encrypted)
    {
        printf("Detected encrypted patch file, decrypting with AES-128-CTR...\n");

        // 获取加密文件大小
        fseek(patch_file, 0, SEEK_END);
        long encrypted_file_size = ftell(patch_file);
        fseek(patch_file, 0, SEEK_SET);

        if (encrypted_file_size < 16)
        {
            fprintf(stderr, "Encrypted file too small\n");
            fclose(patch_file);
            return 1;
        }

        // 读取加密文件到内存
        uint8_t *encrypted_data = (uint8_t *)bs_user_func.bs_malloc(encrypted_file_size);
        if (encrypted_data == NULL)
        {
            fprintf(stderr, "Failed to allocate memory for encrypted data\n");
            fclose(patch_file);
            return 1;
        }

        if (fread(encrypted_data, 1, encrypted_file_size, patch_file) != encrypted_file_size)
        {
            fprintf(stderr, "Failed to read encrypted file\n");
            bs_user_func.bs_free(encrypted_data);
            fclose(patch_file);
            return 1;
        }

        fclose(patch_file);

        // 前16字节是nonce_counter
        uint8_t nonce_counter[16];
        memcpy(nonce_counter, encrypted_data, 16);

        // 剩余部分是加密数据
        decrypted_size = encrypted_file_size - 16;
        decrypted_data = (uint8_t *)bs_user_func.bs_malloc(decrypted_size);
        if (decrypted_data == NULL)
        {
            fprintf(stderr, "Failed to allocate memory for decrypted data\n");
            bs_user_func.bs_free(encrypted_data);
            return 1;
        }

        memcpy(decrypted_data, encrypted_data + 16, decrypted_size);

        // 初始化AES上下文并解密
        AES_ctx ctx;
        AES_init_ctx(&ctx, key);
        AES_CTR_decrypt(&ctx, decrypted_data, decrypted_size, nonce_counter);

        bs_user_func.bs_free(encrypted_data);

        printf("Decryption completed, decrypted size: %zu bytes\n", decrypted_size);

        // Windows不支持fmemopen，使用临时文件
        FILE *temp_fp = fopen(temp_file, "wb");
        if (temp_fp == NULL)
        {
            fprintf(stderr, "Failed to create temporary file\n");
            bs_user_func.bs_free(decrypted_data);
            return 1;
        }

        if (fwrite(decrypted_data, 1, decrypted_size, temp_fp) != decrypted_size)
        {
            fprintf(stderr, "Failed to write to temporary file\n");
            fclose(temp_fp);
            bs_user_func.bs_free(decrypted_data);
            remove(temp_file);
            return 1;
        }

        fclose(temp_fp);
        temp_file_created = 1;

        // 重新打开临时文件作为patch_file
        patch_file = fopen(temp_file, "rb");
        if (patch_file == NULL)
        {
            fprintf(stderr, "Failed to open temporary file for reading\n");
            bs_user_func.bs_free(decrypted_data);
            remove(temp_file);
            return 1;
        }
    }

    // Read header
    if (fread(&header, sizeof(patch_header_t), 1, patch_file) != 1)
    {
        if (feof(patch_file))
            fprintf(stderr, "Corrupt patch file (header too short)\n");
        else
            fprintf(stderr, "Error reading from %s: %s\n", argv[3], strerror(errno));
        fclose(patch_file);
        return 1;
    }

    // Verify header CRC
    uint32_t original_hcrc = header.ph_hcrc;
    header.ph_hcrc = 0;
    calc_crc = crc32((const unsigned char *)&header, sizeof(patch_header_t));
    if (BigtoLittle32(original_hcrc) != calc_crc)
    {
        fprintf(stderr, "Corrupt patch file (invalid header CRC)\n");
        fprintf(stderr, "Calculated CRC: %u, Header CRC: %u\n", calc_crc, BigtoLittle32(original_hcrc));
        fclose(patch_file);
        return 1;
    }

    // Restore original header
    header.ph_hcrc = original_hcrc;

    // Get file sizes from header
    old_size = header.ph_osize; // 小端，直接使用
    new_size = header.ph_nsize; // 小端，直接使用

    printf("Old file size from header: %lld, New file size from header: %lld\n",
           (int64_t)old_size, (int64_t)new_size);
    printf("Compressed patch size: %u bytes\n", BigtoLittle32(header.ph_psize));
    printf("Original uncompressed size: %llu bytes\n", header.ph_original_size);

    // Read old file
    old_data = read_entire_file(argv[1], old_size);
    if (old_data == NULL)
    {
        fclose(patch_file);
        return 1;
    }

    // Verify old file CRC
    calc_crc = crc32(old_data, old_size);
    if (BigtoLittle32(header.ph_ocrc) != calc_crc)
    {
        fprintf(stderr, "Old file CRC mismatch (file may be corrupted or not match the patch)\n");
        fprintf(stderr, "Calculated CRC: %u, Header CRC: %u\n", calc_crc, BigtoLittle32(header.ph_ocrc));
        bs_user_func.bs_free(old_data);
        fclose(patch_file);
        return 1;
    }

    // Initialize memory for new file
    new_data = init_new_file_memory(new_size);
    if (new_data == NULL)
    {
        bs_user_func.bs_free(old_data);
        fclose(patch_file);
        return 1;
    }

    // Get the patch file size (excluding header)
    long patch_start_pos = ftell(patch_file);
    uint32_t patch_size = BigtoLittle32(header.ph_psize);

    // Read the entire compressed patch data into memory
    patch_data = (uint8_t *)bs_user_func.bs_malloc(patch_size);
    if (patch_data == NULL)
    {
        fprintf(stderr, "Failed to allocate memory for patch data\n");
        bs_user_func.bs_free(old_data);
        bs_user_func.bs_free(new_data);
        fclose(patch_file);
        return 1;
    }

    if (fread(patch_data, 1, patch_size, patch_file) != patch_size)
    {
        fprintf(stderr, "Failed to read patch data\n");
        bs_user_func.bs_free(patch_data);
        bs_user_func.bs_free(old_data);
        bs_user_func.bs_free(new_data);
        fclose(patch_file);
        return 1;
    }

    // Close the patch file, we have everything in memory now
    fclose(patch_file);

    bspatch_patch(header, old_data, old_size, patch_data, patch_size, 0x80000000, new_data, new_size);

    // Verify new file CRC
    calc_crc = crc32(new_data, new_size);
    if (BigtoLittle32(header.ph_ncrc) != calc_crc)
    {
        fprintf(stderr, "New file CRC mismatch (patch process failed)\n");
        fprintf(stderr, "Calculated CRC: %u, Header CRC: %u\n", calc_crc, BigtoLittle32(header.ph_ncrc));
        bs_user_func.bs_free(patch_data);
        bs_user_func.bs_free(old_data);
        bs_user_func.bs_free(new_data);
        if (decrypted_data != NULL)
        {
            bs_user_func.bs_free(decrypted_data);
        }
        if (temp_file_created)
        {
            remove(temp_file);
        }
        return 1;
    }

    // Write new file to disk
    if (write_memory_to_file(new_data, new_size, argv[2]) != 0)
    {
        bs_user_func.bs_free(patch_data);
        bs_user_func.bs_free(old_data);
        bs_user_func.bs_free(new_data);
        if (decrypted_data != NULL)
        {
            bs_user_func.bs_free(decrypted_data);
        }
        if (temp_file_created)
        {
            remove(temp_file);
        }
        return 1;
    }

    // Free all resources
    bs_user_func.bs_free(patch_data);
    bs_user_func.bs_free(old_data);
    bs_user_func.bs_free(new_data);

    // 清理AES解密资源
    if (decrypted_data != NULL)
    {
        bs_user_func.bs_free(decrypted_data);
    }
    if (temp_file_created)
    {
        remove(temp_file);
    }

    printf("Successfully applied patch: %s created\n", argv[2]);
    return 0;
}
