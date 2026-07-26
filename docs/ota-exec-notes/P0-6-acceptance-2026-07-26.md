# P0-6 独立验收记录

- 验收人: Codex（非实现会话）
- 日期: 2026-07-26
- 结论: 通过

## 1. 工具链复验

### AC5

命令:

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& '.\MDK-ARM_F435\build_f435.ps1' -AutoStale"

结果: armlink/fromelf exit code 0; Program Size: Code=263556 RO-data=288308 RW-data=1244 ZI-data=453392。

### GCC Release

CMake/Ninja 入口出现本机已知的零 CPU 等待，未将该状态当作结果；按记录的可靠回退方式直接复用 CMakeFiles\X_Track.rsp 执行同一链接参数，再运行 run_artifacts.bat。

结果:

- link exit 0，artifact exit 0。
- linker memory report: FLASH 560344 B/1 MB, RAM 286232 B/352 KB, RW_IRAM2 160 KB/160 KB。
- 输出含既有 newlib syscall、wchar/格式和 RWX segment warnings；错误为 0，未将 warnings 伪报为无警告。

## 2. 独立 map/源码核对

- AC5 RW_IRAM1: Size=0x4c8b8, Max=0x58000，即 313528/360448B，余 46920B。
- AC5 RW_IRAM2: 0x20058000, 0x28000/0x28000; snapshotBuf 位于该区且大小 163840B。
- GCC RAM: 0x20000000, 0x58000; ._user_heap_stack 末端 0x20045e18，已用 286232B，余 74216B。
- GCC RW_IRAM2/.sram_ext: 0x20058000..0x20080000, 163840/163840B，输入对象为 LiveMap.cpp。
- generated_linker.ld 定义 RAM=0x58000、RW_IRAM2=0x28000，LiveMap.cpp 定义 snapshotBuf[256*320] 的 .sram_ext 段。

## 3. ABI、分配与预算复算

- GCC/AC5 ABI 探针: sizeof(CLzmaDec)=100B, sizeof(CLzmaProb)=2B, numProbs=5056, 概率表 10112B。
- 分配探针复现: 字典 8192B 和 16384B 分别原值分配，无隐式放大。
- 工作集算术: 100+10112+16384+1024+1024+4096+192+512+2048=35492B；加保护量 5468B 得池上限 40960B。
- 不采用 overlay: AC5 16KiB 余量 46920-(35492+5468+8192)=-2232B；改 8KiB 仅余 5960B。
- 采纳 overlay: 固定物理区 [0x20058000,0x20080000)，池余 163840-40960=122880B，保留 16KiB 字典；主 RAM 栈保留后 AC5/GCC 分别余 38728B/66024B。

## 4. 卡内标准判定

1. GCC/AC5 map 摘录已留存于 P0-6 实测记录，本次独立从产物重新解析，数值一致。
2. 预算表每项均标注 ABI 实测、源码/契约尺寸或设计上限，算术闭环通过。
3. overlay 裁决明确为“采纳 A”：OTA 独占 .sram_ext，与 LiveMap 互斥；不采用时 AC5 16KiB 工作集短缺 2232B，故不降为 8KiB。

## 5. 产物指纹

AC5 map/AXF/HEX/BIN SHA-256 与实现记录一致；GCC 重新链接后的 ELF/MAP/BIN/HEX SHA-256 分别为:

FFEA77E3B7563C39D34E185F420B90008DC15EC3C4B16DA6FA85599C07587637
1304F02C6E7EFDE222A358C0A30A8A52BAB74145264DC94CD63F92636EC03406
88A39AD84CE2E3CB4916FC3D6F3FA15ACD50C44EAE80D92F782A906D060D1D41
C8181333F768CAAEACE07E95DDF7B84304BDF92910A7D0238C3D17BFBD419E31
