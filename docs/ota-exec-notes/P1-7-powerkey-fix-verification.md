# P1-7 开机键冲突修复验证证据

## 任务卡
PLAN-OTA-EXEC.md P1-7（状态：待回写）

## 问题原始描述
用户原文：
> 当前直接供电（即JLink绕过开机键）时可以上电数秒就开机，但需要按开机键，即usb供电时，按下开机键数十分钟也不会开机

## 根因定位（compaction 前已完成）

PA15 同时是编码器 push 键（设备**唯一**物理按键，即开机键）与 boot 恢复键（`boot/platform/at32/boot_platform_at32.c:configure_recovery_key()` 配置为上拉输入、低电平有效）。电源自锁（`configure_power_hold()` 拉低 PD2 1000ms 后拉高锁存）要求开机时按键必须持续按住 ≥1s。

`boot/src/boot_main.c` 原实现在 `boot_platform_init` 之后、状态机之前做**无条件**恢复键预检：

```c
if (boot_platform_recovery_key_held()) {
    receive_physical_recovery(&state_io, &outcome, 1);
} else {
    /* 正常引导路径 */
}
```

此时按键必然处于按下态（因电源自锁要求），于是直接进入 `receive_physical_recovery()` 的 `do{}while(g_boot_p1_recovery_result != 0)` YMODEM 等待循环（无超时、无出口），表现为 USB 供电按开机键数十分钟不开机；J-Link 直供绕过自锁、PA15 保持上拉高，反而能正常启动。

契约 `PLAN-OTA.md` §4/§5.3 明确物理恢复的"按住 ≥3s"是 App/backup/recovery 全部无效**之后**才要求的必要条件，不是开机首要检测项。

## 修复方案

移除 `boot_main.c:main()` 中状态机之前的无条件恢复键预检，恢复模式入口只由状态机判定。改动文件：

- `D:\github\my\E-Track-p2-5-20260801\boot\src\boot_main.c`（4 次 Edit，已自洽）
  - 移除 `main()` 中 `if (boot_platform_recovery_key_held()) { receive_physical_recovery(...,1) } else { 正常引导 }` 结构，直接走正常引导路径
  - 把 `receive_physical_recovery()` 签名从 3 参数改为 2 参数，删除恒为 0 的 `key_already_held`，循环简化为 `while (!boot_platform_recovery_key_held())`
  - 同步唯一调用点 `receive_physical_recovery(&state_io, &outcome, 0)` → `receive_physical_recovery(&state_io, &outcome)`
  - 注释描述根因链与契约依据（第 167-177 行）

修复保留了 P1-7 的其他未提交改动：
- `boot/platform/at32/boot_platform_at32.c:boot_platform_init()` 中 `system_clock_config()` 提频 288MHz + `configure_recovery_key()` 后 `boot_platform_delay_ms(2u)`（原为解决提频后 PA15 上拉稳定问题，缺陷 A）
- `MDK-ARM_F435/Platform/HAL/HAL_Power.cpp:Power_Init()` 中 `#if defined(OTA_TARGET_APP)` 分支保持 PD2 自锁逻辑（缺陷 B，本轮未再次验证）

## 编译证据

### 构建配置
- 构建目录：`D:\github\my\E-Track-p2-5-20260801\.cache\p1-7-unlock\gcc-release`
- CMake 配置：Release，arm-none-eabi-gcc 13.3.1，MinGW Makefiles
- 测试开关：`P1_6_TEST_ENABLE=OFF`、`BOOT_HANDOFF_TEST_CLEAR_BCB=OFF`、`BOOT_HANDOFF_TEST_INJECT_PENDING=OFF`

### 构建命令与输出
```bash
cmake --build "D:\github\my\E-Track-p2-5-20260801\.cache\p1-7-unlock\gcc-release" --target X_Track_Boot
```

输出：
```
[ 25%] Built target X_Track_Boot_linker_script
[ 50%] Building C object CMakeFiles/X_Track_Boot.dir/0f1999a4cfe5fe006b886cf298d78c9c/boot_main.c.obj
[ 50%] Linking C executable boot\X-Track-Boot.elf
Memory region         Used Size  Region Size  %age Used
           FLASH:       14724 B        64 KB     22.47%
             RAM:        9784 B       352 KB      2.71%
Generating isolated OTA Boot artifacts
   text	   data	    bss	    dec	    hex	filename
  14720	      4	   9780	  24504	   5fb8	D:/github/my/E-Track-p2-5-20260801/.cache/p1-7-unlock/gcc-release/boot/X-Track-Boot.elf
[100%] Built target X_Track_Boot
```

**0 错误 0 警告**，产物：
- `X-Track-Boot.bin` 14724 字节（原 14768 B，**-44 字节**符合移除预检分支的预期）
- `X-Track-Boot.elf` 36860 字节
- `X-Track-Boot.hex` 41485 字节
- `X-Track-Boot.map` 94509 字节
- 时间戳：2026-08-05 15:46:14

## 静态验证——反汇编

### 全映像恢复键调用点检查
```bash
arm-none-eabi-objdump -d --no-show-raw-insn X-Track-Boot.elf | grep -n "bl.*boot_platform_recovery_key_held"
```

输出：
```
2511: 80019e4:	bl	8001e20 <boot_platform_recovery_key_held>
```

**唯一调用点** `0x80019e4`，位于 `main()` 中 `cmp r3,#2 / bne 8001a60`（`outcome.action` != `BOOT_STATE_ACTION_PHYSICAL_RECOVERY` 即跳过恢复分支）之后。正常路径完整调用链（反汇编确认）：

```
main:
  800191c: <函数序言>
  ...
  800195a: bl 8001e98 <boot_platform_init>
  ...
  8001986: bl 800223c <boot_platform_qspi_init>
  ...
  80019a8: bl 80026f8 <bcb_arbiter>
  80019b4: bl 8000db0 <boot_state_machine_run>
  80019d4: subs r2, r3, #1          ; 比较 outcome.action
  80019da: cmp r3, #2
  80019de: bne.n 8001a60 <main+0x144>  ; !=PHYSICAL_RECOVERY 跳转到 App 切换分支
  80019e0: ldr.w r9, [pc, #224]
  80019e4: bl 8001e20 <boot_platform_recovery_key_held>  ; **唯一调用点，状态机之后**
```

正常引导路径（`bne 8001a60` 跳转目标）不含任何恢复键检测：

```
8001a60: ldrb.w r3, [sp, #32]
8001a64: cmp r3, #1
8001a66: beq.n 8001a32 <main+0x116>  ; action==JUMP_APP → handoff
```

## 真机验证

### 验证脚本
`D:\github\my\E-Track-p2-5-20260801\.cache\p1-7-unlock\verify-powerkey-fix.ps1`（95 行，ASCII，复用冻结 P1-6/P1 harness，不手写 J-Link flag）

关键步骤：
1. 烧录生产 boot（`loadfile X-Track-Boot.bin 0x08000000 → r → g → qc`）
2. 复位设备并等待 90 秒
3. 采集 RTT 日志（从 map 查 `_SEGGER_RTT` 地址 → 验证 `SEGGER RTT` 签名 → `JLinkRTTLogger` 30 秒超时）
4. 断言：
   - RTT 含 `OTA: HANDOFF vtor=0x08010000`（boot→app 切换）
   - RTT **不含** `BOOT: hold recovery key`（正常路径未进恢复等待）
   - RTT **不含** `BOOT: physical recovery condition accepted`

### 执行命令
```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& 'D:\github\my\E-Track-p2-5-20260801\.cache\p1-7-unlock\verify-powerkey-fix.ps1'"
```

### 验证输出
```
P1_7_VERIFY_BOOT_BIN=D:\github\my\E-Track-p2-5-20260801\.cache\p1-7-unlock\gcc-release\boot\X-Track-Boot.bin
P1_7_VERIFY_BOOT_SIZE=14724
P1_7_VERIFY_BOOT_MTIME=2026-08-05 15:46:14
P1_7_VERIFY_FLASH=PASS
P1_7_VERIFY_RTT_ADDRESS=0x20045E34
P1_7_VERIFY_RESET=PASS pc=134492606 vtor=134283264 cfsr=0
P1_7_VERIFY_NO_RECOVERY_WAIT=PASS
P1_7_VERIFY=PASS run_directory=D:\github\my\E-Track-p2-5-20260801\.cache\p1-7-unlock\verify-20260805-155501
```

**证据解读**：
- 烧录成功（FLASH=PASS），耗时约 33 秒
- 复位后 PC=0x0804173E（十进制 134492606），VTOR=0x08010000（十进制 134283264，App 基址），CFSR=0（无硬件故障）
- RTT 地址 0x20045E34 从 `X-Track-App-GCC.map` 查询并验证签名通过
- RTT 日志含 `OTA: HANDOFF vtor=0x08010000`（**boot 正常切换到 app**）
- RTT 日志**不含** `BOOT: hold recovery key` 与 `BOOT: physical recovery condition accepted`（**正常路径未进恢复等待循环**）

### 完整 RTT 日志位置
`D:\github\my\E-Track-p2-5-20260801\.cache\p1-7-unlock\verify-20260805-155501\verify-reset-rtt.log`

## 开放决策点（须告知用户）

移除无条件预检后，"App 有效但用户想主动进恢复模式"的入口将不可达。按契约 `PLAN-OTA.md` §4/§5.3，物理恢复本就只在状态机兜底失败（App/backup/recovery 全部无效）时才需要，故符合契约本意。

若用户希望保留主动入口，需另行设计不与开机自锁冲突的触发方式（例如：开机前长按 >5 秒、或独立恢复按键、或上位机 BLE 命令触发）。**该需求属契约变更，须按 OTA 规约在看板 `PLAN-OTA-EXEC.md` §9 登记，禁止就地改契约**。

## 相关系统性债务（背景，本卡未处理）

外部恢复槽 NOT_INSTALLED（`PLAN-OTA.md` §5.3），导致"CONFIRMED + App 坏"会死等。是否立卡由用户决定。

## 验收状态

- [x] 源码修复完成（`boot_main.c` 已自洽，无编译障碍）
- [x] GCC 构建通过（0 错误 0 警告）
- [x] 反汇编静态验证通过（恢复键检测唯一调用点在状态机分支内）
- [x] 真机烧录 + 复位验证通过（RTT 含 HANDOFF、不含 hold recovery key）
- [x] 回写看板 `PLAN-OTA-EXEC.md` P1-7 卡（状态行 + 缺陷 C + 目标 C + 范围补充）与 §10 会话日志
- [ ] P1-7 验收 1-5（启动 ≤1.5s、PD2 无回落、恢复键 3 秒、288MHz、电池独立开机）由非实现会话执行，其中第 5 项需用户物理配合
- [ ] git commit/push 由主会话在用户确认后小步收口（OTA 规约 §5，本会话不自行提交）

### 契约变更登记判定

本次修复**未入 §9 变更登记表**：改动只移除了状态机之前的无条件恢复键预检（"契约之外的实现追加"）并删除恒零形参，`fw_header`/SHA/BCB 仲裁/状态机分支等校验逻辑全未触碰，方向是让实现**回归**契约 `PLAN-OTA.md` §4/§5.3，不构成契约变更。若后续要新增"App 有效时主动进恢复模式"的入口，则属契约变更，须先在 §9 登记。

## 会话信息

- 工作目录：`D:\github\my\E-Track-p2-5-20260801`（worktree，branch `p2-5-20260801`）
- 完成时间：2026-08-05 15:55（验证脚本执行完成）
- 证据归档：`docs/ota-exec-notes/P1-7-powerkey-fix-verification.md`
- 验证运行目录：`.cache/p1-7-unlock/verify-20260805-155501`
