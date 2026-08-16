/* test-only 插桩翻译单元：__wrap_* 计数后原样转发 __real_*。
 * 只在 P2_6_TEST_ENABLE 构型编入；生产构型整个文件不参与链接。
 *
 * 实测约束（本探针第一轮链接失败得到）：
 *   __real_X 这个符号只有在链接命令行出现 --wrap=X 时才由 ld 提供。
 *   若本文件定义了 __wrap_X 却没传 --wrap=X，__real_X 会变成未定义引用，
 *   链接直接失败（fail-closed，不会静默降级）。
 *   因此 wrapper 定义集合必须与 --wrap= 集合严格一一对应；
 *   下面用 P2_6_WRAP_MEM / P2_6_WRAP_TLSF 分别门控两层，便于单独启用。
 */

#include <stddef.h>

#if defined(P2_6_TEST_ENABLE)

/* ---- lv_mem 层 ---- */
#if defined(P2_6_WRAP_MEM)
extern void *__real_lv_mem_alloc(size_t size);
extern void *__real_lv_mem_realloc(void *ptr, size_t size);
extern void __real_lv_mem_free(void *ptr);

volatile unsigned int P2_6_lv_mem_alloc_calls;
volatile unsigned int P2_6_lv_mem_realloc_calls;
volatile unsigned int P2_6_lv_mem_free_calls;

void *__wrap_lv_mem_alloc(size_t size)
{
    P2_6_lv_mem_alloc_calls++;
    return __real_lv_mem_alloc(size);
}

void *__wrap_lv_mem_realloc(void *ptr, size_t size)
{
    P2_6_lv_mem_realloc_calls++;
    return __real_lv_mem_realloc(ptr, size);
}

void __wrap_lv_mem_free(void *ptr)
{
    P2_6_lv_mem_free_calls++;
    __real_lv_mem_free(ptr);
}
#endif /* P2_6_WRAP_MEM */

/* ---- lv_tlsf 层（真实池入口） ---- */
#if defined(P2_6_WRAP_TLSF)
extern void *__real_lv_tlsf_malloc(void *tlsf, size_t size);
extern void *__real_lv_tlsf_realloc(void *tlsf, void *ptr, size_t size);
extern void __real_lv_tlsf_free(void *tlsf, void *ptr);

volatile unsigned int P2_6_lv_tlsf_malloc_calls;
volatile unsigned int P2_6_lv_tlsf_realloc_calls;
volatile unsigned int P2_6_lv_tlsf_free_calls;

/* 转发保真自检：记录最后一次的入参与返回值，供比对。 */
volatile size_t P2_6_last_tlsf_size;
volatile void *P2_6_last_tlsf_ret;

void *__wrap_lv_tlsf_malloc(void *tlsf, size_t size)
{
    P2_6_lv_tlsf_malloc_calls++;
    P2_6_last_tlsf_size = size;
    void *ret = __real_lv_tlsf_malloc(tlsf, size);
    P2_6_last_tlsf_ret = ret;
    return ret;
}

void *__wrap_lv_tlsf_realloc(void *tlsf, void *ptr, size_t size)
{
    P2_6_lv_tlsf_realloc_calls++;
    return __real_lv_tlsf_realloc(tlsf, ptr, size);
}

void __wrap_lv_tlsf_free(void *tlsf, void *ptr)
{
    P2_6_lv_tlsf_free_calls++;
    __real_lv_tlsf_free(tlsf, ptr);
}
#endif /* P2_6_WRAP_TLSF */

#endif /* P2_6_TEST_ENABLE */
