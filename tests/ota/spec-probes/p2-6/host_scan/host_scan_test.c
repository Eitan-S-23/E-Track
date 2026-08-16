/* 宿主模式验证 StackInfo 扫描算法与「栈底 guard」的相互作用。
 *
 * 输出为机器可读键值行（纯 ASCII），判定一律由 run.py 按期望值执行 ——
 * 原始版本靠人工看 ✓/✗，不构成 fail-closed 证据。
 *
 * 五个场景：
 *   S1 非零哨兵 + 无 guard              基准，扫描应准确
 *   S2 非零哨兵 + 栈底 guard + skip=0   guard 落在 i=0，扫描恒返回满栈（失效）
 *   S3 同上但 skip_words=1              仅证明 S2 的成因确是 guard 落在 i=0
 *                                       （该修法已被裁定作废，不是推荐方案）
 *   S4 BLANK 未同步为哨兵常量           i=0 即命中，扫描恒返回满栈（失效）
 *   S5 guard 被完全踩破                 guard 字被覆盖，溢出可检出
 */
#include <stdio.h>
#include <stdint.h>

#define STACK_WORDS   2048u              /* 8192B / 4 */
#define FILL_PATTERN  0xA5A5A5A5u        /* 非零哨兵 */
#define GUARD_PATTERN 0x5AA55AA5u        /* 栈底 guard */

static uint32_t stack_area[STACK_WORDS];

/* 原始算法：照抄 StackInfo.c:43-69，BLANK 与起扫下标参数化 */
static uint32_t scan_original(uint32_t blank, uint32_t skip_words)
{
    uint32_t size = STACK_WORDS;
    uint32_t usage = 0;
    for (uint32_t i = skip_words; i < size; i++) {
        if (stack_area[i] != blank) { usage = size - i; break; }
    }
    return usage * sizeof(uint32_t);
}

static void reset_stack(int with_guard)
{
    for (uint32_t i = 0; i < STACK_WORDS; i++) stack_area[i] = FILL_PATTERN;
    if (with_guard) stack_area[0] = GUARD_PATTERN;
}

/* 模拟从栈顶向下用掉 used_bytes */
static void simulate_usage(uint32_t used_bytes)
{
    uint32_t words = used_bytes / 4;
    for (uint32_t i = 0; i < words; i++) {
        stack_area[STACK_WORDS - 1 - i] = 0xDEADBEEFu;
    }
}

int main(void)
{
    printf("STACK_BYTES=%u\n", STACK_WORDS * 4u);

    reset_stack(0); simulate_usage(1024);
    printf("S1_scan=%u\n", scan_original(FILL_PATTERN, 0));

    reset_stack(1); simulate_usage(1024);
    printf("S2_scan=%u\n", scan_original(FILL_PATTERN, 0));

    reset_stack(1); simulate_usage(1024);
    printf("S3_scan=%u\n", scan_original(FILL_PATTERN, 1));

    reset_stack(0); simulate_usage(1024);
    printf("S4_scan=%u\n", scan_original(0x00000000u, 0));

    reset_stack(1); simulate_usage(STACK_WORDS * 4u);
    printf("S5_guard_word=0x%08X\n", stack_area[0]);
    printf("S5_guard_intact=%d\n", stack_area[0] == GUARD_PATTERN ? 1 : 0);
    return 0;
}
