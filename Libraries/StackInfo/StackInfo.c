/*
 * MIT License
 * Copyright (c) 2021 _VIFEXTech
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */
#include "StackInfo.h"

#if !defined(__GNUC__) && !defined(__CC_ARM)
#error "StackInfo requires GNU Arm GCC or ARM Compiler 5"
#endif

#define CSTACK_BLOCK_NAME                    STACK

#define SECTION_START(_name_)                _name_##$$Base
#define SECTION_END(_name_)                  _name_##$$Limit

#define CSTACK_BLOCK_START(_name_)           SECTION_START(_name_)
#define CSTACK_BLOCK_END(_name_)             SECTION_END(_name_)

extern const int CSTACK_BLOCK_START(CSTACK_BLOCK_NAME);
extern const int CSTACK_BLOCK_END(CSTACK_BLOCK_NAME);

uint32_t StackInfo_GetTotalSize(void)
{
    uintptr_t stackBaseAddr = (uintptr_t)&CSTACK_BLOCK_START(CSTACK_BLOCK_NAME);
    uintptr_t stackLimitAddr = (uintptr_t)&CSTACK_BLOCK_END(CSTACK_BLOCK_NAME);
    uint32_t stackSize = (uint32_t)(stackLimitAddr - stackBaseAddr);
    return stackSize;
}

uint32_t StackInfo_GetMaxUsageSize(void)
{
    static uint32_t stackMaxUsage = 0;
    uintptr_t stackBaseAddr = (uintptr_t)&CSTACK_BLOCK_START(CSTACK_BLOCK_NAME);
    uint32_t stackSize = StackInfo_GetTotalSize();

    volatile uint32_t* stackBase = (uint32_t*)stackBaseAddr;

    uint32_t usageSize = 0;
    uint32_t size = stackSize / sizeof(uint32_t);

    for(uint32_t i = 0; i < size; i++)
    {
        if(stackBase[i] != STACK_INFO_BLANK)
        {
            usageSize = size - i;
            break;
        }
    }

    if(usageSize > stackMaxUsage)
    {
        stackMaxUsage = usageSize;
    }

    return stackMaxUsage * sizeof(uint32_t);
}

uint32_t StackInfo_GetMinFreeSize(void)
{
    return StackInfo_GetTotalSize() - StackInfo_GetMaxUsageSize();
}

float StackInfo_GetMaxUtilization(void)
{
    return (float)StackInfo_GetMaxUsageSize() / StackInfo_GetTotalSize();
}

uint32_t StackInfo_IsGuardIntact(void)
{
#if defined(__GNUC__) && !defined(__CC_ARM)
    extern const uint32_t __StackGuardStart;
    extern const uint32_t __StackGuardEnd;
    uintptr_t start = (uintptr_t)&__StackGuardStart;
    uintptr_t end = (uintptr_t)&__StackGuardEnd;
    volatile const uint32_t *guard = (volatile const uint32_t *)start;

    if (end < start || end - start != 32u)
    {
        return 0u;
    }
    while (start < end)
    {
        if (*guard++ != STACK_INFO_GUARD)
        {
            return 0u;
        }
        start += sizeof(uint32_t);
    }
    return 1u;
#else
    return 0u;
#endif
}
