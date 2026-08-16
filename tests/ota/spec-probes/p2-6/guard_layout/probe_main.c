/* 外置 guard 布局最小链接验证的引用侧。
 *
 * 两个职责：
 *   1. 让四个栈符号与两个 `$$` 别名在最终 ELF 里被真实引用，
 *      避免 --gc-sections 把引用连同 .text 一起丢掉而造成假通过。
 *   2. 用与 `Libraries/StackInfo/StackInfo.c:25-34` 完全一致的两层间接宏引用
 *      `$$` 别名，从而在链接期验证该写法确实解析到 `STACK$$Base`/`STACK$$Limit`。
 *
 * 定义 P2_6_ONE_LAYER_MACRO 时退化成一层宏写法，用于负例：`##` 抑制形参展开，
 * 得到字面量符号 `CSTACK_BLOCK_NAME$$Base`，链接期必须报未定义引用。
 * 该错误在编译期不报错，是"简化两层宏"会静默拿到错误栈边界的根因。
 */

extern const int __StackTop;
extern const int __StackLimit;
extern const int __StackGuardStart;
extern const int __StackGuardEnd;

#define CSTACK_BLOCK_NAME            STACK
#define SECTION_START(_name_)        _name_##$$Base
#define SECTION_END(_name_)          _name_##$$Limit

#if defined(P2_6_ONE_LAYER_MACRO)
/* 负例：少一层间接，形参不展开 */
#define CSTACK_BLOCK_START(_name_)   SECTION_START(CSTACK_BLOCK_NAME)
#define CSTACK_BLOCK_END(_name_)     SECTION_END(CSTACK_BLOCK_NAME)
#else
#define CSTACK_BLOCK_START(_name_)   SECTION_START(_name_)
#define CSTACK_BLOCK_END(_name_)     SECTION_END(_name_)
#endif

extern const int CSTACK_BLOCK_START(CSTACK_BLOCK_NAME);
extern const int CSTACK_BLOCK_END(CSTACK_BLOCK_NAME);

volatile unsigned int probe_sink;

void _start(void)
{
    probe_sink = (unsigned int)&__StackTop;
    probe_sink += (unsigned int)&__StackLimit;
    probe_sink += (unsigned int)&__StackGuardStart;
    probe_sink += (unsigned int)&__StackGuardEnd;
    /* 两层宏路径：等价于 &STACK$$Limit - &STACK$$Base，应恰为 OTA_STACK_RESERVE */
    probe_sink += (unsigned int)&CSTACK_BLOCK_END(CSTACK_BLOCK_NAME)
                - (unsigned int)&CSTACK_BLOCK_START(CSTACK_BLOCK_NAME);
    for (;;) {
    }
}
