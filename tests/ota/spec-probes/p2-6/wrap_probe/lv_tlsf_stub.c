/* 下层池实现（对应 lv_tlsf.c，独立翻译单元）。
 *
 * real_pool_seq 记录到达真实实现的调用序列编码（malloc=1 realloc=2 free=3）。
 * 生产构型与插桩构型必须得到完全相同的序列值，这就是「wrapper 未改变
 * 参数以外的调用顺序」的可验证证据。
 */

#include <stddef.h>

extern volatile unsigned int real_pool_alloc_calls;
extern volatile unsigned int real_pool_seq;
extern volatile size_t real_pool_last_size;

static char tlsf_pool[1024];
static size_t tlsf_used;

static void *pool_take(size_t size)
{
    if (tlsf_used + size > sizeof(tlsf_pool)) {
        return NULL;
    }
    void *p = &tlsf_pool[tlsf_used];
    tlsf_used += (size + 7u) & ~(size_t)7u;
    return p;
}

void *lv_tlsf_malloc(void *tlsf, size_t size)
{
    (void)tlsf;
    real_pool_alloc_calls++;
    real_pool_seq = real_pool_seq * 5u + 1u;
    real_pool_last_size = size;
    return pool_take(size);
}

/* 独立实现，不内部转调 lv_tlsf_malloc，保持序列编码清晰。 */
void *lv_tlsf_realloc(void *tlsf, void *ptr, size_t size)
{
    (void)tlsf;
    (void)ptr;
    real_pool_seq = real_pool_seq * 5u + 2u;
    real_pool_last_size = size;
    return pool_take(size);
}

void lv_tlsf_free(void *tlsf, void *ptr)
{
    (void)tlsf;
    (void)ptr;
    real_pool_seq = real_pool_seq * 5u + 3u;
}
