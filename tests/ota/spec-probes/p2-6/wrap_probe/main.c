/* --wrap 验证主程序。
 *
 * 五个场景：
 *   A 正例（OTA 窗口）：不发生任何分配，所有计数增量必须为 0。
 *   B 负例（外部调用者）：调 lv_mem_alloc，lv_mem 层与 tlsf 层都应 +1。
 *   C 负例（LVGL 内部入口）：调 lv_mem_buf_get，它内部调 lv_mem_alloc。
 *     --wrap=lv_mem_alloc 拦不到（同翻译单元），--wrap=lv_tlsf_malloc 能拦到。
 *     这一格是本次验证的核心结论。
 *   D 负例：lv_mem_realloc
 *   E 负例：lv_mem_free
 *
 * 最后打印 real_pool_seq —— 到达真实实现的调用序列指纹。生产构型与插桩构型
 * 必须得到同一个值，否则 wrapper 改变了调用顺序。
 */

#include <stddef.h>

/* 宿主构型用 printf 打印观测值；ARM 裸机构型（-nostdlib）没有 stdio，
 * 改为把观测值累加进 volatile sink，既能链接又能防止 --gc-sections
 * 把 wrapper 与计数器当成未引用符号删掉（假通过）。 */
#if defined(P2_6_FREESTANDING)
volatile unsigned int probe_sink;
#define P2_6_OBSERVE(v)  do { probe_sink += (unsigned int)(v); } while (0)
#define P2_6_PRINT(...)  do { } while (0)
#else
#include <stdio.h>
#define P2_6_OBSERVE(v)  do { } while (0)
#define P2_6_PRINT(...)  printf(__VA_ARGS__)
#endif

extern void *lv_mem_alloc(size_t size);
extern void *lv_mem_realloc(void *ptr, size_t size);
extern void lv_mem_free(void *ptr);
extern void *lv_mem_buf_get(size_t size);
extern void lv_mem_pool_reset(void);
extern volatile unsigned int real_pool_alloc_calls;
extern volatile unsigned int real_pool_seq;
extern volatile size_t real_pool_last_size;

#if defined(P2_6_WRAP_MEM)
extern volatile unsigned int P2_6_lv_mem_alloc_calls;
extern volatile unsigned int P2_6_lv_mem_realloc_calls;
extern volatile unsigned int P2_6_lv_mem_free_calls;
#define MEM_A   P2_6_lv_mem_alloc_calls
#define MEM_R   P2_6_lv_mem_realloc_calls
#define MEM_F   P2_6_lv_mem_free_calls
#else
#define MEM_A   0u
#define MEM_R   0u
#define MEM_F   0u
#endif

#if defined(P2_6_WRAP_TLSF)
extern volatile unsigned int P2_6_lv_tlsf_malloc_calls;
extern volatile unsigned int P2_6_lv_tlsf_realloc_calls;
extern volatile unsigned int P2_6_lv_tlsf_free_calls;
extern volatile size_t P2_6_last_tlsf_size;
extern volatile void *P2_6_last_tlsf_ret;
#define TLSF_A  P2_6_lv_tlsf_malloc_calls
#define TLSF_R  P2_6_lv_tlsf_realloc_calls
#define TLSF_F  P2_6_lv_tlsf_free_calls
#else
#define TLSF_A  0u
#define TLSF_R  0u
#define TLSF_F  0u
#endif

/* 四字段净状态快照（对应裁定提到的降级方案），用于与 wrapper 计数交叉核对。 */
struct snap {
    unsigned mem_a, mem_r, mem_f;
    unsigned tlsf_a, tlsf_r, tlsf_f;
    unsigned real_a;
};

static void take(struct snap *s)
{
    s->mem_a = MEM_A;   s->mem_r = MEM_R;   s->mem_f = MEM_F;
    s->tlsf_a = TLSF_A; s->tlsf_r = TLSF_R; s->tlsf_f = TLSF_F;
    s->real_a = real_pool_alloc_calls;
}

static void report(const char *tag, const struct snap *s)
{
    P2_6_OBSERVE(MEM_A + MEM_R + MEM_F + TLSF_A + TLSF_R + TLSF_F
                 + real_pool_alloc_calls + real_pool_seq
                 + (unsigned)real_pool_last_size);
    P2_6_PRINT("%-26s mem[a=%u r=%u f=%u]  tlsf[a=%u r=%u f=%u]  real_a=%u\n",
               tag,
               MEM_A - s->mem_a, MEM_R - s->mem_r, MEM_F - s->mem_f,
               TLSF_A - s->tlsf_a, TLSF_R - s->tlsf_r, TLSF_F - s->tlsf_f,
               real_pool_alloc_calls - s->real_a);
}

int main(void)
{
    struct snap s;
    void *p;

    lv_mem_pool_reset();

    /* 场景 A：正例，OTA 窗口内无分配 */
    take(&s);
    report("A_no_alloc", &s);

    /* 场景 B：负例，外部调用者走 lv_mem_alloc（跨翻译单元） */
    take(&s);
    p = lv_mem_alloc(64);
    report("B_external_lv_mem_alloc", &s);

    /* 场景 C：负例，LVGL 内部入口 lv_mem_buf_get -> lv_mem_alloc（同翻译单元） */
    take(&s);
    p = lv_mem_buf_get(48);
    report("C_internal_lv_mem_buf_get", &s);

    /* 场景 D：负例，realloc 路径 */
    take(&s);
    p = lv_mem_realloc(p, 96);
    report("D_lv_mem_realloc", &s);

    /* 场景 E：负例，free 路径 */
    take(&s);
    lv_mem_free(p);
    report("E_lv_mem_free", &s);

    /* 调用序列指纹 + 最后一次到达真实实现的请求大小 */
    P2_6_PRINT("real_pool_seq=%u  real_pool_last_size=%u\n",
               real_pool_seq, (unsigned)real_pool_last_size);

#if defined(P2_6_WRAP_TLSF)
    /* 转发保真：场景 C 的 48 字节请求应原样到达 tlsf 层，
     * 返回值应原样传回给调用方（此处比对 realloc 之前的那次分配）。 */
    P2_6_OBSERVE((unsigned)P2_6_last_tlsf_size + (P2_6_last_tlsf_ret != NULL));
    P2_6_PRINT("forward_fidelity  last_tlsf_size=%u  ret_nonnull=%d\n",
               (unsigned)P2_6_last_tlsf_size,
               (int)(P2_6_last_tlsf_ret != NULL));
#endif
    return 0;
}
