__asm__(
    ".syntax unified\n"
    ".thumb\n"
    ".weak __disable_irq\n"
    ".type __disable_irq, %function\n"
    ".thumb_func\n"
    "__disable_irq:\n"
    "cpsid i\n"
    "bx lr\n"
    ".size __disable_irq, .-__disable_irq\n"
    ".weak __enable_irq\n"
    ".type __enable_irq, %function\n"
    ".thumb_func\n"
    "__enable_irq:\n"
    "cpsie i\n"
    "bx lr\n"
    ".size __enable_irq, .-__enable_irq\n"
);

#include <errno.h>
#include <stddef.h>
#include <stdint.h>

extern char end;
extern char _estack;
extern char __StackGuardStart;

#if defined(P2_6_TEST_ENABLE)
static volatile uint32_t sbrk_call_count;
static volatile uintptr_t sbrk_peak;

uint32_t P2_6_sbrk_call_count(void)
{
    return sbrk_call_count;
}

uintptr_t P2_6_sbrk_peak(void)
{
    return sbrk_peak;
}
#endif

void *_sbrk(ptrdiff_t increment)
{
    static uintptr_t current = (uintptr_t)&end;
    const uintptr_t base = (uintptr_t)&end;
    const uintptr_t limit = (uintptr_t)&__StackGuardStart;
    uintptr_t next;

#if defined(P2_6_TEST_ENABLE)
    ++sbrk_call_count;
    if (current > sbrk_peak)
    {
        sbrk_peak = current;
    }
#endif

    if (increment >= 0)
    {
        if (current > limit || (uintptr_t)increment > limit - current)
        {
            errno = ENOMEM;
            return (void *)-1;
        }
        next = current + (uintptr_t)increment;
    }
    else
    {
        uintptr_t decrease = (uintptr_t)(-(increment + 1)) + 1U;
        if (current < base || decrease > current - base)
        {
            errno = ENOMEM;
            return (void *)-1;
        }
        next = current - decrease;
    }

    void *previous = (void *)current;
    current = next;
#if defined(P2_6_TEST_ENABLE)
    if (current > sbrk_peak)
    {
        sbrk_peak = current;
    }
#endif
    return previous;
}
