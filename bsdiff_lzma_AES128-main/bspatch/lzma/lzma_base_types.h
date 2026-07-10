#ifndef LZMA_BASE_TYPES_H
#define LZMA_BASE_TYPES_H

#include <stdint.h>

/* 基本类型定义 */
typedef uint8_t Byte;
typedef uint16_t UInt16;
typedef uint32_t UInt32;
typedef uint64_t UInt64;
typedef int16_t Int16;
typedef int32_t Int32;
typedef int64_t Int64;
typedef size_t SizeT;
typedef ptrdiff_t SSizeT;

/* 基本函数宏定义 */
#define MY_FAST_CALL

/* STM32优化相关定义 */
#ifdef __GNUC__
#define Z7_NO_INLINE __attribute__((noinline))
#else
#define Z7_FORCE_INLINE static inline
#define Z7_NO_INLINE
#endif

#endif /* LZMA_BASE_TYPES_H */
