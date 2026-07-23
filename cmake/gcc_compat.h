#pragma once
#ifdef __cplusplus
#include <algorithm>
#include <cmath>
#endif
#ifndef __forceinline
#define __forceinline inline __attribute__((always_inline))
#endif
#ifndef __align
#define __align(n) __attribute__((aligned(n)))
#endif
#ifndef __weak
#define __weak __attribute__((weak))
#endif
#ifndef __wfi
#define __wfi() __asm volatile ("wfi")
#endif
