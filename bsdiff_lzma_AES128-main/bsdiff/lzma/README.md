# LZMA 压缩算法代码库

本文件夹包含了完整的 LZMA 和 LZMA2 压缩算法实现，这是一种高效的压缩算法，适用于嵌入式系统如 STM32。

## 主要模块

### 核心压缩/解压模块

- **LzmaEnc.c/h**: LZMA 压缩算法的核心编码实现
- **LzmaDec.c/h**: LZMA 解压算法的核心实现
- **Lzma2Enc.c/h**: LZMA2 压缩算法的实现（LZMA 的改进版本）
- **Lzma2Dec.c/h**: LZMA2 解压算法的实现
- **LzmaLib.c/h**: LZMA 库的简易接口，提供了简单的压缩/解压函数

### 支持模块

- **LzFind.c/h**: LZ（Lempel-Ziv）匹配查找器实现
- **LzFindMt.c/h**: 多线程版本的 LZ 匹配查找器
- **LzHash.h**: LZ 算法的哈希表实现
- **MtCoder.c/h**: 多线程编码器支持
- **MtDec.c/h**: 多线程解码器支持

### 工具和实用程序

- **Util/Lzma/LzmaUtil.c**: LZMA 算法的命令行工具示例实现

### 基础支持库

- **Alloc.c/h**: 内存分配函数
- **7zTypes.h**: 基本数据类型定义
- **7zBuf.c/h**: 缓冲区处理
- **CpuArch.c/h**: CPU 架构特定的优化

## 主要 API

### LZMA 压缩

```c
// 压缩函数
Z7_STDAPI LzmaCompress(
  unsigned char *dest,       // 输出缓冲区
  size_t *destLen,           // 输出缓冲区大小（输入）/压缩后大小（输出）
  const unsigned char *src,  // 输入数据
  size_t srcLen,             // 输入数据大小
  unsigned char *outProps,   // LZMA属性（输出）
  size_t *outPropsSize,      // 属性大小（输入/输出，必须为5）
  int level,                 // 压缩级别（0-9，默认为5）
  unsigned dictSize,         // 字典大小（默认16MB）
  int lc, int lp, int pb,    // LZMA参数
  int fb,                    // 快速字节数
  int numThreads             // 线程数（1或2）
);
```

### LZMA 解压

```c
// 解压函数
Z7_STDAPI LzmaUncompress(
  unsigned char *dest,       // 输出缓冲区
  size_t *destLen,           // 输出缓冲区大小（输入）/解压后大小（输出）
  const unsigned char *src,  // 输入数据
  SizeT *srcLen,             // 输入数据大小（输入）/使用的输入大小（输出）
  const unsigned char *props, // LZMA属性（从压缩时获得的）
  size_t propsSize           // 属性大小（通常为5）
);
```

## 压缩参数说明

LZMA 压缩算法可以通过以下参数进行调整：

- **level**: 压缩级别(0-9)，较高的值提供更好的压缩率但速度较慢
- **dictSize**: 字典大小，影响压缩率和内存使用
- **lc**: 文字上下文位数(0-8)，默认为 3
- **lp**: 文字位置位数(0-4)，默认为 0
- **pb**: 位置位数(0-4)，默认为 2
- **fb**: 快速字节数(5-273)，默认为 32
- **numThreads**: 使用的线程数，1 或 2

## 在 STM32 上使用

在 STM32 等嵌入式系统上使用 LZMA 算法时，需要注意内存限制，建议：

1. 使用较小的字典大小（如 64KB 或 128KB）
2. 设置适当的压缩级别（建议 0-3 用于快速压缩）
3. 如果内存受限，可以使用流式压缩/解压
