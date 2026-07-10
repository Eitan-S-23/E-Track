#include "interface.h"
#include "bs_type.h"
#include "AES128_CTR/tiny_AES_decrypt.h"
// Convert byte array to 64-bit integer
int64_t offtin(uint8_t *buf)
{
    int64_t y;

    y = buf[7] & 0x7F;
    y = y * 256;
    y += buf[6];
    y = y * 256;
    y += buf[5];
    y = y * 256;
    y += buf[4];
    y = y * 256;
    y += buf[3];
    y = y * 256;
    y += buf[2];
    y = y * 256;
    y += buf[1];
    y = y * 256;
    y += buf[0];

    if (buf[7] & 0x80)
        y = -y;

    return y;
}

// Variables for step-by-step decompression
static uint8_t *diff_data_buff;
static int diff_data_len, diff_data_fp;

// Read patch data from the decompression buffer
static int patch_data_read(const struct bspatch_stream *stream, void *buffer, int length)
{
    uint8_t *dp = (uint8_t *)buffer;
    vFile *pf = (vFile *)stream->opaque_r;

    for (int i = 0; i < length; i++)
    {
        if (diff_data_len == 0)
        {
            // Need to read more decompressed data
            diff_data_len = lzma_decompress_read(pf, diff_data_buff, DCOMPRESS_BUFFER_SIZE);

            if (diff_data_len > 0)
            {
                diff_data_fp = 0;
            }
            else
            {
#if bspatch_debug
                bs_printf("Error reading decompressed data at position %d\n", i);
#endif
                return -1;
            }
        }

        if (diff_data_len > 0)
        {
            *(dp++) = diff_data_buff[diff_data_fp++];
            diff_data_len--;
        }
    }

    return 0;
}

// Custom bspatch implementation that processes the patch in chunks
static int chunked_bspatch(uint8_t *old_data, int64_t old_size,
                           uint8_t *new_data, int64_t new_size, uint32_t newfile_addr,
                           struct bspatch_stream *stream)
{
    uint8_t buf[8];
    int64_t oldpos, newpos;
    int64_t ctrl[3];
    int64_t i;
    // 确保缓冲区大小是4的倍数，以优化Flash写入
    uint32_t buffer_size = (DCOMPRESS_BUFFER_SIZE / 4) * 4;
    if (buffer_size == 0)
        buffer_size = 4; // 确保至少有4字节的缓冲区

    uint8_t *new_buffer = (uint8_t *)bs_user_func.bs_malloc(buffer_size);
    if (new_buffer == NULL)
    {
#if bspatch_debug
        bs_printf("Failed to allocate new_buffer memory\n");
#endif
        return -1;
    }

    oldpos = 0;
    newpos = 0;
    while (newpos < new_size)
    {
        /* Read control data */
        for (i = 0; i <= 2; i++)
        {
            if (stream->read(stream, buf, 8))
            {
#if bspatch_debug
                bs_printf("Error reading control data %lld\n", i);
#endif
                bs_user_func.bs_free(new_buffer);
                return -1;
            }
            ctrl[i] = offtin(buf);
        };
#if bspatch_debug
        bs_printf("Control: diff=%lld, extra=%lld, seek=%lld\n", ctrl[0], ctrl[1], ctrl[2]);
#endif

        /* Sanity-check */
        if (ctrl[0] < 0 || ctrl[0] > INT_MAX ||
            ctrl[1] < 0 || ctrl[1] > INT_MAX ||
            newpos + ctrl[0] > new_size)
        {
#if bspatch_debug
            bs_printf("Corrupt patch file (control sanity check failed)\n");
            bs_printf("ctrl[0]=%lld, ctrl[1]=%lld, newpos=%lld, new_size=%lld\n",
                      ctrl[0], ctrl[1], newpos, new_size);
#endif
            bs_user_func.bs_free(new_buffer);
            return -1;
        }

        /* Process diff string in chunks */
        int64_t diff_bytes_left = ctrl[0];
        int64_t current_oldpos = oldpos;
        int64_t current_newpos = newpos;

        while (diff_bytes_left > 0)
        {
            int64_t bytes_to_process = (diff_bytes_left > buffer_size) ? buffer_size : diff_bytes_left;

            // Read diff data from patch
            if (stream->read(stream, new_buffer, bytes_to_process))
            {
#if bspatch_debug
                bs_printf("Error reading diff data\n");
#endif
                bs_user_func.bs_free(new_buffer);
                return -1;
            }

            // Process chunk from the old file data
            if (current_oldpos < old_size && current_oldpos >= 0)
            {
                // Copy chunk from in-memory old file
                for (i = 0; i < bytes_to_process; i++)
                {
                    if ((current_oldpos + i >= 0) && (current_oldpos + i < old_size))
                    {
                        // Add old data to diff string
                        new_buffer[i] += old_data[current_oldpos + i];
                    }
                }
            }
#if bspatch_debug
            // Write this chunk to the in-memory new file
            memcpy(new_data + current_newpos, new_buffer, bytes_to_process);
#else
            // 调用我们改进后的EraseAndWriteFlash函数，它现在可以处理未对齐的地址和大小
            if (EraseAndWriteFlash(newfile_addr + current_newpos, new_buffer, bytes_to_process) != 0)
            {
#if bspatch_debug
                bs_printf("Failed to write flash at address 0x%x with size %lld\n",
                          newfile_addr + current_newpos, bytes_to_process);
#endif
                bs_user_func.bs_free(new_buffer);
                return -1;
            }
#endif

            current_oldpos += bytes_to_process;
            current_newpos += bytes_to_process;
            diff_bytes_left -= bytes_to_process;
        }

        /* Adjust pointers */
        newpos += ctrl[0];
        oldpos += ctrl[0];

        /* Sanity-check */
        if (newpos + ctrl[1] > new_size)
        {
#if bspatch_debug
            bs_printf("Corrupt patch file (data sanity check failed)\n");
            bs_printf("newpos=%lld, ctrl[1]=%lld, new_size=%lld\n",
                      newpos, ctrl[1], new_size);
#endif
            bs_user_func.bs_free(new_buffer);
            return -1;
        }

        /* Process extra string in chunks */
        int64_t extra_bytes_left = ctrl[1];
        current_newpos = newpos;

        while (extra_bytes_left > 0)
        {
            int64_t bytes_to_process = (extra_bytes_left > buffer_size) ? buffer_size : extra_bytes_left;

            // Read extra data from patch
            if (stream->read(stream, new_buffer, bytes_to_process))
            {
#if bspatch_debug
                bs_printf("Error reading extra data\n");
#endif
                bs_user_func.bs_free(new_buffer);
                return -1;
            }
#if bspatch_debug
            // Write this chunk to the in-memory new file
            memcpy(new_data + current_newpos, new_buffer, bytes_to_process);
#else
            // 调用我们改进后的EraseAndWriteFlash函数，它现在可以处理未对齐的地址和大小
            if (EraseAndWriteFlash(newfile_addr + current_newpos, new_buffer, bytes_to_process) != 0)
            {
#if bspatch_debug
                bs_printf("Failed to write flash at address 0x%x with size %lld\n",
                          newfile_addr + current_newpos, bytes_to_process);
#endif
                bs_user_func.bs_free(new_buffer);
                return -1;
            }
#endif

            current_newpos += bytes_to_process;
            extra_bytes_left -= bytes_to_process;
        }

        /* Adjust pointers */
        newpos += ctrl[1];
        oldpos += ctrl[2];
    };

    bs_user_func.bs_free(new_buffer);
    return 0;
}

/**
 * @brief 用户需要注册的函数
 *
 * @param user_func 用户创建一个结构体然后将功能依次注册
 * @return 0成功 1失败
 */
int bs_user_func_register(interface *user_func)
{
    if (user_func == NULL || user_func->bs_flash_write == NULL || user_func->bs_malloc == NULL || user_func->bs_free == NULL)
    {
        return 1;
    }
    bs_user_func.bs_flash_write = user_func->bs_flash_write;
    bs_user_func.bs_malloc = user_func->bs_malloc;
    bs_user_func.bs_free = user_func->bs_free;
    return 0;
}

int bspatch_patch(patch_header_t header, uint8_t *old_data, uint32_t old_size, uint8_t *patch_data,
                  uint32_t patch_size, uint32_t newfile_addr, uint8_t *new_data, int64_t new_size)
{
    struct bspatch_stream stream;
    vFile *vf = NULL;
    // Allocate buffer for decompressed data chunks
    diff_data_buff = (uint8_t *)bs_user_func.bs_malloc(DCOMPRESS_BUFFER_SIZE);

    if (diff_data_buff == NULL)
    {
#if bspatch_debug
        bs_printf("Failed to allocate memory for decompression buffer\n");
        bs_user_func.bs_free(old_data);
        bs_user_func.bs_free(new_data);
#endif
        return 1;
    }

    // Create a virtual file for decompression
    vf = vfopen(patch_data, patch_size);
    if (!vf)
    {
#if bspatch_debug
        bs_printf("Failed to create virtual file\n");
        bs_user_func.bs_free(patch_data);
        bs_user_func.bs_free(diff_data_buff);
        bs_user_func.bs_free(old_data);
        bs_user_func.bs_free(new_data);
#endif
        return 1;
    }

    // Initialize decompressor with the LZMA properties from header
    uint8_t header_with_props[LZMA_PROPS_SIZE + 8];
    memcpy(header_with_props, header.ph_lzma_props, LZMA_PROPS_SIZE);

    // Copy the uncompressed size (8 bytes)
    for (int i = 0; i < 8; i++)
    {
        header_with_props[LZMA_PROPS_SIZE + i] = (header.ph_original_size >> (i * 8)) & 0xFF;
    }

    // Create a virtual file for decompression header
    vFile *header_vf = vfopen(header_with_props, sizeof(header_with_props));
    if (!header_vf)
    {
#if bspatch_debug
        bs_printf("Failed to create virtual file for header\n");
        bs_user_func.bs_free(patch_data);
        bs_user_func.bs_free(diff_data_buff);
        bs_user_func.bs_free(old_data);
        bs_user_func.bs_free(new_data);
#endif
        vfclose(vf);
        return 1;
    }

    // Initialize the decompressor
    int init_result = lzma_decompress_read(header_vf, NULL, 0);
    vfclose(header_vf);

    if (init_result < 0)
    {
#if bspatch_debug
        bs_printf("Failed to initialize LZMA decompressor\n");
        bs_user_func.bs_free(patch_data);
        bs_user_func.bs_free(diff_data_buff);
        bs_user_func.bs_free(old_data);
        bs_user_func.bs_free(new_data);
#endif
        vfclose(vf);
        return 1;
    }

    // Initialize diff_data buffers
    diff_data_len = 0;
    diff_data_fp = 0;

    // Initialize bspatch stream with our step-by-step decompression
    stream.read = patch_data_read;
    stream.opaque_r = vf;

#if bspatch_debug
    bs_printf("Starting decompression and patching...\n");
#endif
    // Apply patch using chunked approach
    if (chunked_bspatch(old_data, old_size, new_data, new_size, newfile_addr, &stream))
    {
#if bspatch_debug
        bs_printf("bspatch failed\n");
        bs_user_func.bs_free(patch_data);
        bs_user_func.bs_free(diff_data_buff);
        bs_user_func.bs_free(old_data);
        bs_user_func.bs_free(new_data);
#endif
        lzma_decompress_finish();
        vfclose(vf);
        return 1;
    }

    // Clean up LZMA resources
    lzma_decompress_finish();
    vfclose(vf);
    return new_size;
}
