# P3-3 T1a 目标板 J-Link 只读识别 —— 2026-09-12

> 依据：用户 2026-09-12 对「有界只读 J-Link 识别」的授权（原话「1授权」）。
> 关联：`docs/ota-exec-notes/P3-3-t1a-step1-device-observation-2026-09-12.md`、
> `docs/ota-exec-notes/P3-3-batch9-device-observation-sheet.md` §2.2/§4。
> **未烧录、未擦除、未写任何寄存器、未执行 RTT 下行命令、未清数据。**
> 正式验收继续 `NOT_RUN`；A1 配额 1 授权 / **0 消耗**。

## 0. 结论速览

| 项 | 观测值 |
| --- | --- |
| 目标板是否在运行 | **是**，应用全速运行（§3） |
| J-Link 是否把 MCU 顶在停机态 | **否**（这条假设被证伪，见 §3.4） |
| 板上 Boot 镜像 | = 磁盘 `X-Track-Boot.bin`（逐字节一致） |
| 板上 App 镜像 | = 磁盘 `X-Track-App-GCC.bin`（双零法全镜像 SHA 一致） |
| 固件版本 | fw_header：`3.2.0`（version_code 30200） |
| 复位原因 | `NRST POR`（含本次 J-Link 接入触发的一次 NRESET，见 §4） |
| 外部 QSPI | `JEDEC=0xEF4018`（Winbond 128Mbit）已白名单、OTA enabled |
| BCB 已确认版本 | `vcode=20801`（2.8.1）——与镜像头 3.2.0 不一致，见 §6 |
| App 是否输出 RTT | 启动 4 行后**静默**（20 s 内 0 字节） |
| 目标板 MAC | **仍未取得**（本轮不产生 BLE 观测） |

## 1. 实际执行的命令（4 个会话，全部只读）

```text
JLink.exe -Device AT32F435RGT7 -If SWD -Speed 1000 -AutoConnect 1 \
          -CommandFile <脚本>
```

| 会话 | 脚本 | 命令 | 原始输出 |
| --- | --- | --- | --- |
| 1 | `id.txt` | `h` / 读 DBGMCU_IDCODE、DBGMCU_CR / 读 `0x08000000` 向量表 / 读 `0x20053630` / `regs` / `g` / `qc` | `id.log` |
| 2 | `id2.txt` | 读 `0x200540A4` / `savebin` 两段各 16 KB | `id2.log` |
| 3 | `id3.txt` | 读 VTOR、CPUID、ICSR×5、SysTick CTRL/VAL×4 | `id3.log` |
| 4 | `id4.txt` | 读 `SystemTickCount`(0x20004418) ×7，间隔 400 ms | `id4.log` |

会话 1 的 `h` 与 `g` 都未生效：`h` 执行时**尚未建立目标连接**，返回
`J-Link connection not established yet but required for command`；
`regs` 返回 `CPU is not halted !`；`g` 返回 `CPU is not halted`。
**即本轮从未真正 halt 过目标**——三次会话中核心始终自由运行。

## 2. 板上固件身份（可复核的密码学级证据）

### 2.1 Boot 区（0x08000000，16 KB 转储）

`boot16k.bin` 与磁盘 `MDK-ARM_F435/cmake-generated/build-gcc-release/boot/X-Track-Boot.bin`
前 16384 字节**逐字节一致，差异字节数 0/16384**（boot 本体 14724 B，其余为 `0xFF`）。
向量表实读：SP=`0x20058000`、Reset=`0x08002881`（→ 处理函数 `0x08002880`），
与 boot map 的 `__Vectors 0x08000000` / `Reset_Handler 0x08002880` 精确吻合。

### 2.2 App 区（0x08010000，16 KB 转储 + 全镜像双零法复核）

App 向量表实读：SP=`0x20058000`、Reset=`0x0801B659`（→ `0x0801B658`），
与 App map 的 `Reset_Handler 0x0801B658` 精确吻合；VTOR 亦为该基址（§3.1）。

`0x08010400..0x0801045F`（app 基址 + 0x400）处为 **96 B `fw_header`**，
在磁盘 `.bin` 内是 `0xFF` 占位，板上已被 finalize。逐字段解析：

| 偏移 | 字段 | 板上实读 | 判定 |
| --- | --- | --- | --- |
| 0 | magic | `45 54 46 57` = `ETFW` | ✔ |
| 4 | header_ver | 1 | ✔ |
| 8 | version_code | `0x75F8` = **30200** | = 3*10000+2*100+0 |
| 12 | version_name | `3.2.0`（16B，0 填充） | ✔ |
| 28 | build_ts | 1788375368 = **2026-09-02 18:56:08 UTC** | — |
| 32 | hw_rev | 1 | ✔ |
| 36 | image_len | `0x93368` = **602984** | = 磁盘 bin 字节数 |
| 40 | image_sha256 | `d97534841302c16d…1f7401dd` | 见下 |
| 72 | layout_id | 1 | ✔ |
| 73 | min_boot_ver | 1 | ✔ |
| 74 | pad 18B | 全 `0xFF` | ✔ |
| 92 | header_crc32 | `7011438F` | 重算一致 |

**独立复核（不采信板上自述）**：按 `Tools/etu_pack.py` §1.2 的双零法
（头内 off40..71 与 off92..95 置 0 后对**整镜像**求 SHA-256），
以磁盘 `X-Track-App-GCC.bin` + 板上头字节重算：

```text
板上头内记录 : d97534841302c16d4e026820a6b854c8ee68cc256b0042024d1280001f7401dd
本机双零重算 : d97534841302c16d4e026820a6b854c8ee68cc256b0042024d1280001f7401dd   ← 一致
header_crc32 : 存储 7011438f / 重算 7011438f                                       ← 一致
反证(用 0xFF 占位头重算) : 1f83b1e7…（不同，证明该探针有鉴别力）
```

结论：**板上 App 区就是磁盘上的 `X-Track-App-GCC.bin`**，只是补上了 finalize 头。
（旁证：同一摘要 `d9753484…` 已记录于 `docs/ota-exec-notes/P3-2-acceptance-round1.md:50`
的 `header_double_zero_sha256`，与 P3-2 冻结记录自洽。）

## 3. 运行时状态

### 3.1 核心在跑应用

| 寄存器 | 实读 | 含义 |
| --- | --- | --- |
| `SCB->VTOR` (0xE000ED08) | `0x08010000` | App 向量表已装载 |
| `CPUID` (0xE000ED00) | `0x410FC241` | Cortex-M4 r0p1 |
| `ICSR` (0xE000ED04) ×5 | 恒 `0x00400000` | `VECTACTIVE=0`，不在任何异常处理中 |
| `SysTick CTRL` (0xE000E010) | `0x00010007` | ENABLE+TICKINT+CLKSOURCE，COUNTFLAG 已置 |
| `SysTick VAL` (0xE000E018) ×4 | 每次不同 | 计数器在走 |

### 3.2 应用代码确实在执行（决定性探针）

`SystemTickCount`（`delay.c` 的 `static volatile uint32_t`，map 定址 `0x20004418`）
7 次采样，每次间隔 400 ms：

```text
0x5A344B → 0x5A35DD → 0x5A3770 → 0x5A3904 → 0x5A3A96 → 0x5A3C29 → 0x5A3DBB
相邻增量：402 / 403 / 404 / 402 / 403 / 402
```

**每次增量都约等于 400 ms 的毫秒数**——SysTick 中断在正常处理，CPU 在执行应用代码。
这条排除了「MCU 卡在 HardFault / 死循环 / 中断被屏蔽」的全部可能。

### 3.3 RTT 存活，但应用静默

- `_SEGGER_RTT` 实读地址 `0x200540A4`，前 16 字节
  `53 45 47 47 45 52 20 52 54 54 00 …` = `SEGGER RTT`，签名吻合 App map。
- 控制块：`NumUpBuffers=3`、`NumDownBuffers=3`；logger 报
  `3 up-channels found: 0: Terminal（1024 bytes）/ 1: / 2:`。
- 有界采集 20 s（`-RTTChannel 0`），仅得 287 B 缓冲残留，**此后 0 字节**：

```text
OTA: HANDOFF vtor=0x08010000 primask=0 basepri=0 faultmask=0 control=0 systick=0x00000000 icsr=0x00000000 iser=0x00000000 ispr=0x00000000
Reset: NRST POR
QSPI: JEDEC=0xEF4018 whitelisted, OTA enabled
OTA: BCB already CONFIRMED vcode=20801
```

这 4 行来自 App 自身（`Libraries/OTA/ota_vtor_check.c:59`、
`USER/HAL/HAL_EEPROM.cpp:180`），是**启动期一次性输出**；
之后 20 s 无任何周期性日志——与「生产固件平时不打 RTT」一致。

### 3.4 被证伪的假设

会话 1 之前提出的「J-Link 把 MCU 顶在停机态，所以不广播」——
**证伪**：`DBGMCU_CR=0`、`regs` 报 `CPU is not halted`、`SysTick` 与
`SystemTickCount` 都在走。

## 4. 必须披露的副作用：会话 1 触发了一次 nRESET 复位

会话 1 的首条 `mem32` 建立连接时，J-Link 的普通 SWD 连接**两次失败**
（`Error: Failed to initialized DAP`），随后走了回退路径，原文：

```text
Connect fallback: Reset via Reset pin & Connect.
InitTarget() start
DAP initialized successfully.
```

即 **J-Link 通过 nRESET 引脚复位了目标后重新连接**。
这与我在授权申请中承诺的「不复位」有偏差，必须如实记录：

- 事实：该复位发生在 2026-09-12 约 16:2x；板上 RTT 的 `Reset: NRST POR` 与之吻合。
- 该路径不由脚本控制：脚本首条是 `h`（halt），**没有**任何 reset 指令；
  它是 J-Link 在连接失败后的自动回退，属于连接方式本身，无法用参数关闭。
- 本机**可以**避免：会话 2/3/4 都以 `mem32`/`savebin` 起手并通过了普通 DAP 连接
  （`reset-pin 回退次数: 0`），说明复位只在首次同步时需要。
- 影响：App 被重启一次（SD/QSPI 重新初始化）。**未做**拔插 SD 卡、未上下电。
- 与观测单 §2.3 的关系：该清单要求「停机窗口最小且必须 `g`」——本轮从未停机，
  但代价换成了「一次复位」。这是清单未预见的第三种状态，已在此登记。

## 5. 对「手机扫不到目标板」的判定

已被本轮证据**排除**的原因：

- 板子没上电 / 没接好 —— 排除（SWD 可读写，VTOR 正确）；
- 板上没有固件 / 烧的是旧固件 —— 排除（§2 逐字节 + 全镜像摘要）；
- MCU 卡死、HardFault、中断被屏蔽 —— 排除（§3.2）；
- J-Link 把 MCU 顶在停机态 —— 排除（§3.4）。

仍然**未排除**、需下一轮真机观测的：

1. 手机上的生产版 `com.wen.gaia.gaia` 占住了目标板的 BLE 连接，
   设备已连接时不再广播（步骤1 §3.3 提出的假设，本轮无法证实或证伪，
   因为本轮全程未在手机上做扫描）；
2. 固件 BLE 广播条件未满足（需 App 侧观测，不是板上静态可判）。

**一条可执行的新观测**：会话 1 的复位发生在扫描（15:55–16:08）**之后**，
板子已干净重启一次（`OTA: HANDOFF vtor=0x08010000`）。因此「复位后再扫一次」
是一次**全新的**观测，而不是重复既有扫描。

## 6. 如实记录：BCB 版本与镜像头版本不一致

- 板上 App 的 fw_header：`version_code = 30200`（3.2.0）。
- App 启动时自报：`OTA: BCB already CONFIRMED vcode=20801`（2.8.1）。
- `boot/src/boot_state_machine.c:452` 显示确认路径会把 `next.cur_vcode` 置为
  被确认镜像的 `version_code`。二者不一致，最直白的读法是
  **这块板当前镜像不是经 OTA 确认流程落地的**（例如 J-Link 直烧，BCB 未随之更新）。

**本轮未定性**：判定它是否为缺陷需要 boot 的确认时序（何时写 BCB、几次成功启动后写），
这超出「只读识别」范围。此处仅登记观测值，不作为结论。

## 7. 证据产物（均在项目内被忽略目录）

`\.cache\p3-3-t1a-step1-r1\jlink\`

| 文件 | 字节 | sha256 前 16 |
| --- | --- | --- |
| `id.log` / `id.txt` | 2758 / 88 | `946cbc92d161731b` / `29a57323cccf5d75` |
| `id2.log` / `id2.txt` | 2120 / 101 | `62507a46b43f32ae` / `89a5b2b31bc80061` |
| `id3.log` / `id3.txt` | 2593 / 347 | `92a20e1a7b0f4cd8` / `994c08267dfa8519` |
| `id4.log` / `id4.txt` | 2212 / 196 | `16d22c194e75b0cb` / `ca101dc3bfd5d91c` |
| `boot16k.bin` | 16384 | `882d18fb5e0c2d0f` |
| `app16k.bin` | 16384 | `a2f4133c43bf65f6` |
| `rtt-terminal.log` | 287 | `320e698d341a7d21` |

对照件（磁盘既有产物，非本轮生成）：
`X-Track-Boot.bin` 14724 B、`X-Track-App-GCC.bin` 602984 B
（sha256 `7328c1b15feff7214378065ca3e7d556ac803b59ebed7029a892d64f15e2153f`）。

## 8. 边界与配额

- **未做**：烧录、擦除、清数据、卸载、上下电、拔插 SD 卡、写任何目标寄存器、
  RTT 下行命令（`ping`/`livemap`/`dialplate`/`back` 一条未发）、
  WDT 或调试寄存器更改、MCU 源码改动。
- **做了但未在计划内的**：会话 1 由 J-Link 自动回退路径触发的一次 nRESET 复位（§4）。
- RTT 采集为有界 20 s，采集前后均确认无 `JLinkRTTLogger.exe` 残留；
  未停止用户可能开启的 RTT Viewer（若用户同时开着，读指针会被抢，本文件 287 B
  与「启动后静默」的结论需以此为条件解读）。
- A1 配额 **1 授权 / 0 消耗**；B1-M 3 / 0；正式验收 `NOT_RUN`；T2 维持 `ENV_BLOCKED`。
- 未读取或注入任何 secret；未修改生产工作流；未做项目外写入。
