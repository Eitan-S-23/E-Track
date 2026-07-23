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
extern char _Min_Stack_Size;

void *_sbrk(ptrdiff_t increment)
{
    static uintptr_t current = (uintptr_t)&end;
    const uintptr_t base = (uintptr_t)&end;
    const uintptr_t limit = (uintptr_t)&_estack - (uintptr_t)&_Min_Stack_Size;
    uintptr_t next;

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
    return previous;
}
