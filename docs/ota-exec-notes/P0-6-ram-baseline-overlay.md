# P0-6 RAM 基线实测与 overlay 裁决

- 日期: 2026-07-26
- 实现会话: Codex
- 状态: 实测与裁决已落盘,待非实现会话独立验收

## 1. 任务边界与权威输入

本卡只做 RAM 基线、升级态预算和内存分配契约，不实现 P2 升级状态机。
权威输入如下:

- `PLAN-OTA-EXEC.md` P0-6: 当前 GCC/AC5 map、16KB/8KB 字典裁决、
  `.sram_ext` overlay 是/否裁决。
- `PLAN-OTA.md` §9: PRE-2 为本卡预留的合法回填位置。
- `docs/ota-binary-contracts.md`: P0-6 允许补充 MCU 端内存契约。
- `MDK-ARM_F435/cmake-generated/cmake/generated_linker.ld`: GCC 内存区定义。
- `MDK-ARM_F435/Listings/X-Track.map`: AC5 当前链接 map。
- `USER/App/Pages/LiveMap/LiveMap.cpp`: `snapshotBuf` 的段与生命周期事实。
- `bsdiff_lzma_AES128-main/bspatch/**`: LZMA/bspatch 实际分配路径。

## 2. 编码前检索结论

### 2.1 物理区与常态占用口径

- 片上 RAM 总量为 512KB，链接划分为主 `RAM/RW_IRAM1` 352KB
  (`0x20000000..0x20057fff`)和 `RW_IRAM2/.sram_ext` 160KB
  (`0x20058000..0x2007ffff`)。
- `snapshotBuf[256 * 320]` 是 RGB565，恰为 163840B，静态占满
  `.sram_ext`；页面卸载只改变对象状态，不释放该静态数组。
- 主 RAM 余量必须按 map 的执行区高水位计算，不能只用
  `RW Data + ZI Data` 相减。AC5 把 RAMCODE 也放在 RW_IRAM1，区域跨度
  大于数据项合计；GCC 则以 `._user_heap_stack` 末地址作为静态保留高水位。
- 当前证据使用本工作树重建/重链接后的产物: GCC Release 产物时间为
  `2026-07-26 01:46:10`,AC5 产物时间为 `2026-07-26 00:19:30/00:19:36`;
  旧 map 不再作为本卡数字来源。

### 2.2 OTA 工作集的源码口径

- P2 已冻结为流式集成: old 直接读内部 flash XIP，patch 从 QSPI 流式读，
  new 以 1KB 分块回调写 candidate；禁止分配 old/new/完整 patch 镜像。
- `DCOMPRESS_BUFFER_SIZE` 当前为 1024B。
- 7-Zip 解码器的动态对象不是只有字典:
  `CLzmaDec` 本体 + `numProbs * sizeof(CLzmaProb)` + 向 4KB 对齐的字典。
  当前制包参数 `lc=2, lp=0, pb=0`;GCC/AC5 ABI 探针均得到
  `CLzmaDec=100B`,`CLzmaProb=2B`,`numProbs=5056`,概率表 `10112B`。
- BLE/staging 活跃窗口按契约为 4KB；不得另算一份完整包缓冲。
- 本卡预算是 P2 的设计上限，P2-6 仍须用 StackInfo、堆水位和（若采用）
  overlay 池水位做真机峰值复核。

## 3. 实测方法

1. GCC: 复用 CI 的 Release `compile_commands.json` 重编当前工作树的 50 个
   脏对象,再从 `build.ninja` 对象清单解析链接输入;新 Ninja 树在本机沙箱会
   留下零 CPU 孤儿进程,所以没有等待它作为验收依据。保留 `X-Track.map` 摘录、
   `arm-none-eabi-size -A`、链接/转换返回码和文件时间戳。
2. AC5: 运行 `MDK-ARM_F435/build_f435.ps1 -AutoStale`，记录
   `Program Size`、RW_IRAM1/RW_IRAM2 execution region 和输出时间戳。
3. 对两条工具链分别计算主 RAM 高水位、主 RAM 空闲、`.sram_ext` 占用，
   并以较差工具链作为不采用 overlay 时的硬上限。
4. 用 ARM GCC 与 AC5 编译期 ABI 探针取得 `sizeof(CLzmaDec)`/概率表；另用
   同一 `LzmaDec_Allocate` 源码的分配回调探针确认 8KB/16KB 字典请求不会
   隐式放大。其余工作集只使用冻结协议/源码中的明确缓冲尺寸。

## 4. 裁决门槛

- 16KB 字典只有在完整工作集加保留余量后可由选定内存池容纳时才保留；
  否则降为 8KB，并同步制包端默认/CI 参数。
- overlay 若采纳，必须同时冻结进入条件、LiveMap 互斥、退出/失败恢复、
  linker 段边界和分配失败行为；任何一项无法定义则不采纳。
- overlay 若不采纳，所有 OTA 动态工作集必须能装入两条工具链中较小的主 RAM
  余量，且仍保留明确的栈/运行时安全余量。

## 5. 实测结果

### 5.1 AC5 map

命令:

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& 'MDK-ARM_F435/build_f435.ps1' -AutoStale"
```

关键输出:

```text
Program Size: Code=263556 RO-data=288308 RW-data=1244 ZI-data=453392
[OK] build complete (armlink/fromelf exit code 0)
```

map 摘录:

```text
Execution Region RW_IRAM1: Exec base=0x20000000 Size=0x0004c8b8 Max=0x00058000
Execution Region RW_IRAM2: Exec base=0x20058000 Size=0x00028000 Max=0x00028000
snapshotBuf 0x20058000 Data 163840
```

计算: `0x4c8b8=313528B`,`0x58000-0x4c8b8=46920B`(45.82KiB),主区占用
86.98%;`RW_IRAM2` 为 `163840/163840B`。产物:

| 文件 | 大小 | 时间 | SHA-256(完整) |
|---|---:|---|---|
| `MDK-ARM_F435/Objects/X-Track.axf` | 6754188 | 2026-07-26 00:19:30 | `3C270252E412B5EDB858E712A085B6C367F704AF5A8942F9F1744D9BABED5260` |
| `MDK-ARM_F435/Objects/X-Track.hex` | 1553158 | 2026-07-26 00:19:36 | `DD2E1D2FC27A196F37466E2C51DDC8470637E5B5D9039D3488ABFD1F0819DEDE` |
| `MDK-ARM_F435/Track.bin` | 552164 | 2026-07-26 00:19:36 | `5702F5EC88759025658DFB8757CB957577D5BCF06700277057F162DB2E12912D` |
| `MDK-ARM_F435/Listings/X-Track.map` | 3694618 | 2026-07-26 00:19:30 | `C35B56399233563FAF9C9570DE61484AAAEA52399E65412486EB3FE80CB6AB74` |

### 5.2 GCC Release map

链接命令来源:`.cache/p0-6-gcc-link-command.txt`;链接、bin、hex 返回码均为
0。`arm-none-eabi-size -A` 关键段:

```text
.data                 848
.bss               280776
.sram_ext          163840
._user_heap_stack    4608
```

map 摘录:

```text
RAM 0x20000000 0x00058000
RW_IRAM2 0x20058000 0x00028000
.bss 0x20000350 0x448c8 -> 0x20044c18
._user_heap_stack 0x20044c18 0x1200 -> 0x20045e18
.sram_ext 0x20058000 0x28000 -> 0x20080000
```

计算:主区高水位 `0x20045e18-0x20000000=286232B`(79.41%),余
`0x58000-0x45e18=74216B`(72.48KiB);`.sram_ext` 为
`163840/163840B`。链接存在既有 GCC 警告(newlib syscall、wchar/格式及
RWX segment 等),错误为 0,不能将本次结果描述为“无警告”。产物:

| 文件 | 大小 | 时间 | SHA-256(完整) |
|---|---:|---|---|
| `MDK-ARM_F435/cmake-generated/build-gcc-release/X-Track.elf` | 804260 | 2026-07-26 01:46:10 | `FFEA77E3B7563C39D34E185F420B90008DC15EC3C4B16DA6FA85599C07587637` |
| `MDK-ARM_F435/cmake-generated/build-gcc-release/X-Track.map` | 2035113 | 2026-07-26 01:46:10 | `1304F02C6E7EFDE222A358C0A30A8A52BAB74145264DC94CD63F92636EC03406` |
| `MDK-ARM_F435/cmake-generated/build-gcc-release/X-Track.bin` | 560344 | 2026-07-26 01:46:10 | `88A39AD84CE2E3CB4916FC3D6F3FA15ACD50C44EAE80D92F782A906D060D1D41` |
| `MDK-ARM_F435/cmake-generated/build-gcc-release/X-Track.hex` | 1576179 | 2026-07-26 01:46:10 | `C8181333F768CAAEACE07E95DDF7B84304BDF92910A7D0238C3D17BFBD419E31` |

### 5.3 ABI 与分配探针

GCC ARM 探针命令:

```text
arm-none-eabi-gcc -mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16 -ffreestanding -Os -S .cache/p06_abi_probe.c -o .cache/p06_abi_probe.s
```

AC5 同一探针命令:

```text
armcc --cpu Cortex-M4 --thumb --c99 -Ospace -S .cache/p06_abi_probe.c -o .cache/p06_abi_probe_ac5.s
```

两份汇编均将以下常量直接折叠进调用参数:

```text
sizeof(CLzmaProb)=2
sizeof(CLzmaProps)=8
sizeof(CLzmaDec)=100
numProbs=5056
probsBytes=10112
dict16=16384
dict8=8192
```

同一 `LzmaDec_Allocate` 源码的分配回调探针输出:

```text
dict=8192  alloc=10112  alloc=8192  dicBufSize=8192 numProbs=5056
dict=16384 alloc=10112  alloc=16384 dicBufSize=16384 numProbs=5056
```

### 5.4 升级态预算与裁决

| 项 | 字节 | 依据 |
|---|---:|---|
| `CLzmaDec` | 100 | ABI 探针 |
| 概率表 | 10112 | `1984+(0x300<<(2+0))=5056`,每项 2B |
| 字典(已选) | 16384 | 16KiB 分配探针 |
| LZMA 输出缓冲 | 1024 | `DCOMPRESS_BUFFER_SIZE` |
| bspatch 写缓冲 | 1024 | 参考实现同时保留另一块 1KiB 缓冲 |
| 单个 staging/BLE 活跃窗口 | 4096 | 契约 4KiB,密文/明文不双算 |
| AES context+counter | 192 | `AES_ctx` 176B+16B |
| parser/vFile/控制元数据 | 512 | 源码字段与对齐余量 |
| hash/CRC/allocator 预算 | 2048 | P2 固定池设计上限(非 P0-6 运行时实测) |
| **已知小计** | **35492** | — |
| 对齐/保护量 | 5468 | 取整并保留哨兵 |
| **OTA overlay 池上限** | **40960 (40KiB)** | 160KiB 区内固定池 |
| OTA 调用栈保留(主 RAM) | 8192 | P2-6 水位复核上限 |

不采用 overlay 时,按同一 `5468B` 对齐/保护量计算,AC5 余量为
`46920-(35492+5468+8192)=-2232B`;即使降 8KiB 字典也只有 `5960B`余量。故裁决 **采纳显式 OTA 独占 overlay + 保留 16KiB
字典**:池占 `40960/163840B`,剩 `122880B`;主 RAM 扣 8KiB 栈后 AC5/GCC
分别剩 `38728B/66024B`。LiveMap 与 OTA 池必须是同一物理区的 linker/union
互斥所有者,不能靠页面卸载或普通 malloc 假装释放 `snapshotBuf`。

### 5.5 Overlay 契约与后续验收

- 进入 FirmwareUpdate/`APPLY_PREPARE` 且前置检查通过后 acquire;停止 LVGL
  refresh/timer、关闭地图文件、卸载 LiveMap、置 `snapshot_valid=false` 后才
  启动 LZMA/bspatch。
- owner=OTA 时禁止 `snapshotBuf` 访问和主堆 spill;owner=LiveMap 时 acquire
  失败。GCC/AC5 段边界固定为 `0x20058000..0x20080000`、`NOLOAD`、最大
  `0x28000`,linker 必须断言不越界。
- 失败/取消/超时先清零密钥、字典、压缩状态和 I/O,再释放 owner 并重新初始化
  LiveMap/生成新快照;成功路径清理后重启。acquire/固定池切分失败在写
  candidate/BCB 前终止,不得覆盖快照或退回无界堆。
- P2-6 验收命令:运行真实升级路径并同时采 `StackInfo`、固定池高水位、异常
  退出后的 LiveMap 重建;任一项超过 `40960B` 才能按 `PLAN-OTA-EXEC.md` §9
  变更登记降为 8KiB并同步制包端。

## 6. 实现会话结论

P0-6 的实测、预算和 overlay 契约已写入 `PLAN-OTA.md` §9 与
`docs/ota-binary-contracts.md` §10;本会话不实现 P2 状态机、不修改 linker 或
生产 OTA 路径。卡状态保持“进行中”,等待非实现会话按 `PLAN-OTA-EXEC.md` §0.3
独立验收后再决定是否置“完成”。
