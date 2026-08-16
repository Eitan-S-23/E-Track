/* --wrap 最小验证：模拟 LVGL 的两层结构。
 *
 * 关键点：lv_mem_alloc 与 lv_tlsf_malloc 在真实 LVGL 里位于不同翻译单元
 * （lv_mem.c 调 lv_tlsf.c），而 lv_mem.c 内部对自身函数的调用是同翻译单元。
 * 本文件复刻这个结构，用来实测 --wrap 各自能拦到什么。
 */

#include <stddef.h>

/* 下层池入口（对应 lv_tlsf.c）。 */
extern void *lv_tlsf_malloc(void *tlsf, size_t size);
extern void *lv_tlsf_realloc(void *tlsf, void *ptr, size_t size);
extern void lv_tlsf_free(void *tlsf, void *ptr);

static char pool[512];
static void *tlsf_handle = (void *)pool;

/* 记录真实池活动，供正/负例交叉核对。
 * real_pool_seq 是到达真实实现的调用序列指纹，用于比对两种构型行为一致。 */
volatile unsigned int real_pool_alloc_calls;
volatile unsigned int real_pool_seq;
volatile size_t real_pool_last_size;

/* 对应 lv_mem_alloc：跨翻译单元调下层。 */
void *lv_mem_alloc(size_t size)
{
    return lv_tlsf_malloc(tlsf_handle, size);
}

void *lv_mem_realloc(void *ptr, size_t size)
{
    return lv_tlsf_realloc(tlsf_handle, ptr, size);
}

void lv_mem_free(void *ptr)
{
    lv_tlsf_free(tlsf_handle, ptr);
}

/* 对应 lv_mem_buf_get：lv_mem.c 内部调用 lv_mem_alloc（同翻译单元）。
 * --wrap=lv_mem_alloc 拦不到这条路径，这正是裁定阻断 4 指出的盲区。 */
void *lv_mem_buf_get(size_t size)
{
    return lv_mem_alloc(size);
}

void lv_mem_pool_reset(void)
{
    real_pool_alloc_calls = 0;
    real_pool_seq = 0;
    real_pool_last_size = 0;
}
