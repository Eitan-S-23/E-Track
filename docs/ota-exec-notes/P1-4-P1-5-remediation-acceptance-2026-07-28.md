# P1-4 / P1-5 整改联合独立复验记录

- 验收人: Codex（非实现会话，联合 P1-4/P1-5 独立审查分工）
- 日期: 2026-07-28
- 待验收 HEAD: `035d96e6f0a3d180c411fe4adf0d5cf0521b0ed2`
- 结论: P1-4 通过；P1-5 通过
- 看板结果: P1-4/P1-5 置 `完成`，P1 总进度由 `3/6` 更新为 `5/6`

## 1. 基线与验收纪律

验收使用独立 fresh checkout：

```text
C:\Users\SU\AppData\Local\Temp\E-Track-p14-reaccept-035d96e-worktree
```

未使用 `D:\github\my\E-Track` 根工作树。开始验收及写证据前均确认：

```text
HEAD=035d96e6f0a3d180c411fe4adf0d5cf0521b0ed2
origin/main=035d96e6f0a3d180c411fe4adf0d5cf0521b0ed2
GitHub live main=035d96e6f0a3d180c411fe4adf0d5cf0521b0ed2
git status clean
```

已阅读 `PLAN-OTA-EXEC.md`、P1-4/P1-5 implementation evidence、上一轮
`P1-3-P1-5-acceptance-2026-07-28.md`，并逐项复核上一轮阻断。本会话未修改
任何实现、`PLAN-OTA.md` 或 `docs/ota-binary-contracts.md`，没有通过放宽冻结
契约迁就实现。

P1-3 已完成且未重开。P1-6 的 20 点断电矩阵、mid-Flash 注错和人工物理断电
不在本次范围，本会话未执行、未宣称通过。

## 2. 宿主测试与 fresh GCC Release

从当前 HEAD 独立重跑：

| 测试 | 结果 |
|---|---|
| fw_header 向量/负例 | `P1_1_FW_HEADER_VECTORS=PASS cases=16` |
| Ymodem/ETSL | `P1_1_BOOT_PROTOCOLS=PASS checks=19 failures=0` |
| BCB | `P0_4_BCB=PASS checks=27 failures=0` |
| P1-3 状态机回归 | `P1_3_STATE_MACHINE=PASS checks=96 failures=0` |
| P1-5 bootstrap/utility | `P1_5_PREPARE_TOOL=PASS checks=42 powershell_checks=8` |

fw_header 与协议 runner 使用进程内 `TemporaryDirectory` 映射到预创建目录，规避
本机已知的 MinGW 临时目录 ACL 问题；测试源码和待测实现均未修改。P1-5 的
`powershell_checks=8` 是实际 `powershell.exe` 执行，不是 Python mock。

fresh GCC Release 构建目录为：

```text
C:\Users\SU\AppData\Local\Temp\E-Track-p1-45-reaccept-gcc-035d96e6
```

`X_Track_App_GCC` 与 `X_Track_Boot` 均构建成功。App 保留仓库既有编译 warning、
short-wchar linker warning 和 App RWX LOAD warning；Boot 构建成功且满足本卡
约束。独立四件套为：

```text
X-Track-Boot.bin 14208
  sha256=411f3e1d703f07bd107d0f1f4f9687a54bd69981c63cc70d3f421ad15494ac3c
X-Track-Boot.elf 36148
  sha256=4a0961b5a5ac10e93da26204ef8001195081016fb30e44ea43f711288efde767
X-Track-Boot.hex 40037
  sha256=89b6938bf014b1b5a45434414054184099fc13ebf13c8bead5efc6ec883cd6e2
X-Track-Boot.map 90578
  sha256=8c33137e2d815e57ac88e6f66f47b93806ac3b9e32bbcec2d6c18bf8cf0f20d6

X-Track-App-GCC.bin 563108
  sha256=9a87df22d37af98f212efcc434d8cec1ff3b165a25c8e9ee48aeefdf9757a1a3
X-Track-App-GCC.elf 810688
  sha256=7a82dace521b56dbb5d5496faa9b20f11856181b5c5c41c528f37bfe06896d95
X-Track-App-GCC.hex 1582561
  sha256=508028e29f45fd9985f5cc49b97136771726c8d54117f97558d0cfeed5c3583c
X-Track-App-GCC.map 2133533
  sha256=272aaeaf0e88ae47ebecac46c3a02c50b678a778edfdc67ac7060048fc82d466
```

Boot 为 `14208B < 64KiB`，LOAD 仅 `R E` 与 `RW`，没有 RWX LOAD；map/ELF
中无 LZMA、bspatch、BLE/Bluetooth 或 AES 依赖。独立 validator 输出：

```text
P1_1_BOOT_ASSERTIONS=PASS bin=14208 vector=0x08000000/0x20c
  msp=0x20058000 reset=0x08002885
P1_4_BOOT_HANDOFF_ASSERTIONS=PASS nvic_banks=8 primask=0 basepri=0
  faultmask=0 control=0 vtor=0x08010000 branch=MSP/DSB/ISB/BX
```

## 3. P1-4 整改复验

### 3.1 App 首调用

当前源码为：

```text
USER/main.cpp:143  int main(void)
USER/main.cpp:146      ota_vtor_check();
USER/main.cpp:147      ota_handoff_capture();
USER/main.cpp:149      Core_Init();
```

fresh App ELF 的 `main()` 前三次调用与源码一致：

```text
08042c00 <main>:
  08042c02  bl 08042e3c <ota_vtor_check>
  08042c06  bl 08042d3c <ota_handoff_capture>
  08042c0a  bl 08017a18 <Core_Init>
```

因此 `ota_vtor_check()` 已恢复为 App `main()` 首调用；VTOR 不匹配会在 handoff
采集及正常 App 初始化前 fail-closed。新增顺序回归断言也在本轮 validator 中通过。

### 3.2 完整 handoff 与真机普通 reset

源码、反汇编和 validator 一致证明：8 组 ICER、8 组 ICPR、SysTick 停止、
PendST/PendSV 清理、PRIMASK/BASEPRI/FAULTMASK/CONTROL 归零、VTOR 写入后
DSB+ISB、MSP 重载后 DSB+ISB、最终 BX 向量[1]；没有 `cpsid` 或以
PRIMASK=1 跳转。跳转前仍使用统一 fw_header/vector 完整校验器。

上一轮已经通过的 pending SysTick/外设 IRQ 注错证据及三次生产普通 reset 证据
已复核；整改提交只恢复 App 调用顺序并增加 validator，不改 Boot handoff 实现。
本轮另对当前 `035d96e6` 产物独立执行一次普通 reset，按当前 map 重查
`_SEGGER_RTT=0x20044E04`，mem8 签名为 `SEGGER RTT`，结果：

```text
PC=0x08095B5E
VTOR=0x08010000
CFSR=0x00000000
OTA: HANDOFF vtor=0x08010000 primask=0 basepri=0 faultmask=0 control=0
  systick=0x00000000 icsr=0x00000000 iser=0x00000000 ispr=0x00000000
```

检查后执行 `g` 恢复运行，且无残留 `JLinkRTTLogger` 或 `JLinkRTTViewer`。

### 3.3 P1-4 结论

上一轮唯一阻断“VTOR 自检不是首调用”已关闭，P1-4 验收通过，可置 `完成`。
低风险残余仍是 ICER 动态注错覆盖弱于 ICPR；8 组 ICER 的源码、反汇编和
validator 证据完整，该缺口不阻断本卡，后续可在 P1-6 注错矩阵中扩展。

## 4. P1-5 五项阻断复验

### 4.1 Legacy 同名资产隔离

显式选择的 `LegacyHex` 在设备改动前保存为
`selected-legacy-<sha256>-<basename>`；仓库默认审计件使用不同的
`repo-default-*` role，catch 回退只引用 selected 副本。`42/42` 中的真实
PowerShell 同 basename、不同内容用例确认两份资产均保持原字节且不会互相覆盖。
本轮 recovery 真机工具保存的实际回退件为：

```text
selected-legacy-6ec05ecba8f36d83591dcaeb5400cba582e0e858d7293d3414a7dbbdf5400084-X-Track.hex
```

### 4.2 最终 PC/VTOR/CFSR 判定

部署与 recovery 工具均取 J-Link 输出的最终样本，PASS 强制要求最终 PC 位于
App 分区、`VTOR=0x08010000`、`CFSR=0x00000000`、当前 map RTT 签名、
HANDOFF 行及匹配 fw_header 的 CONFIRMED vcode。真实 PowerShell 回归覆盖
“先 Boot PC 后 App PC”、最终 PC 越界和非零 CFSR 拒绝，上一轮假阳性阻断已关闭。

### 4.3 Recovery 原地破坏拒绝

host utility 在打开输出前拒绝 input/App-output/recovery-output 任意路径碰撞。
真机 recovery 脚本只写独立 `recovery-stripped-app.bin`，并在操作前后复核源
长度和 SHA-256。本轮独立真机结果：

```text
P1_5_RECOVERY_TRAILER_STRIPPED=PASS
  container_len=563116 app_len=563108 bytes_removed=8
  app_sha256=f3e2e85052188f9f2e0d2df7db4c2fea6208c5cb7cb85e0ad8cd8d5ef7b3f92e
  source_sha256=858bba65196b280abf91f24bc3299d0092c09ad86460b25449e9c03f158cfd60
  source_preserved=1
```

操作结束后源容器仍为 `563116B` 且 SHA-256 不变。

### 4.4 实施范围收缩

相对已验收 P1-4 基线 `3fe2e006...` 的独立路径审计确认：生产
`.github/workflows/firmware-build.yml`、`MDK-ARM_F435/cmake-generated/CMakeLists.txt`、
Boot linker 和 `boot/**` 均无差异。最终 P1-5 功能保持在 `Tools/jlink/**`、
bootstrap 文档和 host tests；唯一非工具前置是 §9 已登记的
`proj.uvprojx` 排除 OTA-App-only 源及受控 `X-Track-Legacy-AC5.sct`。
它只恢复 frozen legacy AC5 构建，不改变 Boot、分区或二进制契约，本次复验接受
该最小前置并关闭 §9 待复验项。

### 4.5 Fresh legacy AC5

另一个 fresh checkout 从同一 HEAD 完整构建 legacy AC5 target `X-Track`：

```text
Program Size: Code=263496 RO-data=288312 RW-data=1244 ZI-data=453392
".\Objects\X-Track.axf" - 0 Error(s), 0 Warning(s).
Build Time Elapsed: 00:02:47
```

`X-Track.lnp` 使用：

```text
--strict --scatter ".\scatter\X-Track-Legacy-AC5.sct"
```

构建日志、LNP 和 Objects 中 `ota_vtor_check`/`fw_header_placeholder` 编译或链接
命中均为 0。四件套为：

```text
X-Track.axf 6918664
  sha256=d3fb006cbc5135044ef2a9bfa68300d29050745969d365e032cc3f0a1dc52ee4
X-Track.hex 1552994
  sha256=6ec05ecba8f36d83591dcaeb5400cba582e0e858d7293d3414a7dbbdf5400084
Track.bin 552108
  sha256=bbc352785223006cbc13dddd7d3bdc0eb1a6ccad1e4a7f57f84e2c4927598dcf
X-Track.map 3698075
  sha256=3295af72dd0e1181f46d62413567fba0e621c6f01cf9e848e092b525a4266178
```

uVision 仅使两个生成的 RTE header 出现行尾/空白变化，
`git diff --ignore-space-at-eol` 为 0；该辅助构建 checkout 未用于验收提交。

### 4.6 Recovery 真机闭环与 P1-5 结论

使用 fresh finalized App v2.8.2 与上述 AC5 legacy HEX 独立执行
`flash-recovery-container.ps1`。J-Link 使用 `AT32F435RGT7`、SWD 1000 kHz；
烧录、VerifyBin、普通 reset、map RTT 地址重查、mem8 签名和单 logger 超时控制
均按 `AGENTS.md` 执行。最终结果：

```text
P1_5_RECOVERY_FLASH=PASS
PC=0x08042CE4
VTOR=0x08010000
CFSR=0x00000000
RTT=0x20044E04, signature="SEGGER RTT"
source_preserved=1
OTA: HANDOFF vtor=0x08010000 primask=0 basepri=0 faultmask=0 control=0
  systick=0x00000000 icsr=0x00000000 iser=0x00000000 ispr=0x00000000
```

检查后 MCU 已恢复运行，logger/viewer 无残留。上一轮五项阻断全部关闭，P1-5
验收通过，可置 `完成`。

## 5. CI 独立核对

GitHub Actions run `30370629275` 实时复核结果：

```text
workflow=MCU Firmware Build
event=push
headSha=035d96e6f0a3d180c411fe4adf0d5cf0521b0ed2
status=completed
conclusion=success
```

下载并展开两组 artifact：

```text
boot-2.7-nightly.48/
  X-Track-Boot.bin
  X-Track-Boot.elf
  X-Track-Boot.hex
  X-Track-Boot.map

firmware-2.7-nightly.48/
  X-Track-App-GCC.bin
  X-Track-App-GCC.elf
  X-Track-App-GCC.hex
  X-Track-App-GCC.map
```

共 8 个文件，Boot/App 各恰四件且名称、角色、目录隔离正确；artifact API 显示
两组均未过期。工作流内 fw_header、协议、状态机、P1-5 utility、Boot/App 布局
及 handoff 断言均通过。

## 6. 最终判定与残余风险

| 卡 | 结论 | 看板状态 | 依据 |
|---|---|---|---|
| P1-4 | 通过 | 完成 | source/ELF 首调用恢复，完整 handoff validator、Boot 布局和当前普通 reset 真机闭环均通过 |
| P1-5 | 通过 | 完成 | 五项阻断关闭，42/42+真实 PowerShell 8/8、fresh AC5、CI 双四件套和 recovery 真机闭环均通过 |

P1 总进度更新为 `5/6`。残余风险仅包括 App 既有 GCC/short-wchar/RWX warnings
以及 P1-4 ICER 动态注错深度不足；两者不是本轮整改引入，也不改变两卡结论。
