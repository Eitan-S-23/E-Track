# 开机数十秒黑屏 根因分析（boot 阶段性能缺陷）

- 发现时间：2026-08-04
- 发现场景：用户以 J-Link 供电上电（无需按开机键），原固件立即亮屏，当前固件需等待数十秒
- 分析会话性质：P2-5 独立验收会话（非实现会话）
- 结论：**boot 阶段性能缺陷，非功能性损坏**。不阻塞 P2-5 硬件验收（等待后可正常进入 App 与 U 盘模式）

## 1. 现象澄清

用户最初报告为「插 USB 后按开机键长时间黑屏」，后续澄清两点，决定性地改变了诊断方向：

1. 「u 盘程序之前是正常的」——是回归，不是操作问题
2. 「原来程序使用 jlink 供电时接上 JLink 直接就亮屏，现在却需要等待数十秒」
   ——**不是永久黑屏，是延迟亮屏；与 USB 无关，纯开机阶段问题**

## 2. 根因链（逐项有据）

### 2.1 架构变更：单体固件 → boot + App 两段

用户记忆中的「原来」固件是**单体镜像，根本没有 bootloader 阶段**。当前为
boot @0x08000000 + App @0x08010000。开机路径整段新增了一个 bootloader。

### 2.2 boot 全程运行在 8 MHz（无 PLL 配置）

`boot/platform/at32/boot_platform_at32.c` 的 `boot_platform_init()` 只调用
`system_core_clock_update()`——该函数仅**读寄存器反算频率**，不配置 PLL。

佐证：`MDK-ARM_F435/cmake-generated/CMakeLists.txt` 的 `BOOT_PROJECT_SOURCES`
（第 532-553 行）**不包含** `Platform/Core/at32f435_437_clock.c`，boot 目标里
根本没有编入时钟配置代码。该文件仅出现在 App 目标（第 189 行）。

- 复位默认：`HICK_VALUE = 8000000`（`RTE/Device/-AT32F435RGT7/at32f435_437_conf.h:50`）
  `system_core_clock_update()` 的 `CRM_SCLK_HICK` 分支在 `hickdiv` 为 RESET 时
  返回 `HICK_VALUE` = **8 MHz**，与实际相符（SysTick 延时是准的，非计时错误）
- App 侧：`Core_Init()` → `system_clock_config()`（`USER/main.cpp:199`），
  `crm_pll_config(CRM_PLL_SOURCE_HICK, 72, 1, CRM_PLL_FR_2)` = **288 MHz**

**boot 比 App 慢 36 倍。** 在此前提下任何全镜像校验都会被放大数十倍。

### 2.3 每次开机对整个 App 镜像做软件 SHA-256

`boot/src/boot_state_machine.c` 的 `BCB_STATE_CONFIRMED` 分支每次开机调用
`validate_internal_app()`，对全部 598,680 字节 App 镜像做软件 SHA-256
（`boot/src/boot_fw_header.c`，256 字节分块，无硬件加速）。

实测（反汇编 `build-gcc-release/boot/X-Track-Boot.elf` 的 `sha256_transform`，
`-Os`，0x08000270 起 288 字节）：压缩循环 **37 条指令/轮 × 64 轮**，
连消息扩展约 **3500 周期 / 64B 块**。

| 项 | 数值 |
|---|---|
| 镜像字节 | 598,680 |
| SHA 64B 块数 | 9,355 |
| SHA 总周期 | 32.7 M |
| 单遍 @ 8 MHz（boot 实际） | **4.09 s** |
| 单遍 @ 288 MHz（App 主频） | 0.11 s |

### 2.4 BCB 空白时一次开机跑两遍 SHA

`boot_state_machine_run()` 是 `for (transition = 0; transition <
BOOT_STATE_MAX_TRANSITIONS /* 16 */; ++transition)` 循环。当
`bcb_arbiter()` 返回 `BCB_ARBITER_NONE`（EEPROM 无有效 BCB，例如刚烧录）：

```
validate_internal_app()  →  commit_confirmed()  →  continue
   →  下一轮进 BCB_STATE_CONFIRMED  →  validate_internal_app() 再来一遍
```

即 **2 × 4.09 s = 8.19 s**。

### 2.5 额外 1 秒硬编码延时

`configure_power_hold()`（`boot_platform_at32.c:50-65`）内
`boot_platform_delay_ms(1000u)`。

### 2.6 屏幕点亮时机

`Display_Init()` 在 App 的 `HAL_Init()` 中，排在 `Usb_Init()` / `SD_Init()`
之后，而这些都在 boot 交接**之后**才发生。因此上述全部耗时期间均为黑屏。

### 时间账合计

```
2 遍 SHA @ 8 MHz   8.19 s
power hold 固定     1.00 s
------------------------
合计               ≈ 9.2 s
```

按保守的 3500 周期/块估算得 9.2 s；实际叠加 flash 等待周期、栈上 w[64] 访问、
分块 memcpy（2339 次）后更高，与用户「数十秒」的观感吻合。

## 3. 已证伪的排除项

| 假设 | 证伪依据 |
|---|---|
| P0-5 的 USB MSC 改动 | 新增保护全在 `#ifdef MSC_USE_QSPI_FLASH` 下，实际启用的是 `MSC_USE_SD_CARD`（`msc_diskio.h:50`） |
| EEPROM/QSPI 1000 次压测 | `CONFIG_EEPROM_BCB_STRESS`、`CONFIG_QSPI_SELFTEST_ENABLE` 在 `HAL_Config.h:35-44` 默认均为 0 |
| P2-5 的 backup 自拷 | `git show --stat 3f096c3` 为 App 侧，仅 OTA 进行中执行，不在开机路径 |
| boot 编译在 `-Og` | `Tools/jlink/deploy-ota-bootstrap.ps1:81` 用 `-DCMAKE_BUILD_TYPE=Release` → `-Os` |
| SysTick 配错导致延时放大 | `system_core_clock_update()` 的 HICK 分支正确返回 8 MHz，延时准确 |
| USB 相关 | J-Link 纯供电、不插 USB 同样复现 |

## 4. 修复方案

### 契约影响评估

`PLAN-OTA.md` 与 `docs/ota-binary-contracts.md` **均未规定 boot 主频**。
提高 boot 时钟是纯性能修复，不改变任何校验语义，**不触碰冻结契约**，
无需走 OTA 规约 §2 的「置阻塞 + 看板 §9 变更登记」流程。

反之，若选择「跳过/弱化 CONFIRMED 路径的 SHA 校验」来提速，则会改变
`PLAN-OTA.md:83`「镜像真伪始终以 fw_header SHA 为准」的语义，**必须**走 §2。
本方案不采用该路径。

### 主修：boot 配置 PLL

1. `BOOT_PROJECT_SOURCES` 增加：
   - `Platform/Core/at32f435_437_clock.c`（`system_clock_config()`）
   - `RTE/Device/-AT32F435RGT7/at32f435_437_pwc.c`
     （`system_clock_config()` 调用了 `pwc_ldo_output_voltage_set()`，
     pwc 目前不在 boot 目标中——这是本修复唯一的新增依赖缺口）

   其余依赖 `crm_*` / `flash_clock_divider_set` 所在的
   `at32f435_437_crm.c`、`at32f435_437_flash.c` **已在** boot 目标中。

2. `boot_platform_init()` 开头调用 `system_clock_config()`，再
   `system_core_clock_update()`（后者会读到新的 288 MHz 并据此配 SysTick）。

**收益：SHA 单遍 4.09 s → 0.11 s（36 倍），两遍合计 8.19 s → 0.22 s。**

### 次修（可独立评估，非必需）

- 2.4 的第二遍 SHA 冗余：`commit_confirmed()` 之后已持有校验通过的 header，
  重进 CONFIRMED 分支再算一次属重复工作。消除它不改变校验语义（同样的校验，
  只是不重复做）。
- `configure_power_hold()` 的 1 秒硬延时：评估其是否为电源时序必需。

### 交接后主频状态

`boot_handoff_to_app()` 交接后 App 仍会自行调用 `Core_Init()` →
`system_clock_config()` 重配时钟，因此 boot 提高主频**不影响 App 侧行为**；
但实现时应确认交接前的外设状态（尤其 QSPI 分频、UART 波特率）与新主频一致。

## 5. 对 P2-5 的影响

**不阻塞。** 该缺陷表现为「慢」而非「坏」：等待后屏幕正常点亮，
App 与 U 盘模式功能正常，SD 卡可正常写入 `.etu` 包。
P2-5 硬件验收（STAGED→APPLYING→TEST_BOOT→CONFIRMED）可照常进行，
仅每次重启需多等约十几秒。

## 6. 流程归属建议

- 本缺陷属 boot（P1 阶段产物），**不在 P2-5 卡范围内**，按 OTA 规约 §1
  「不越卡内范围改文件」，不应在 P2-5 卡下顺手修改。
- 本会话为 P2-5 **独立验收会话**，按 §3「实现者不自验收」，不宜自行实施该修复，
  否则将丧失对该修复的独立验收资格。
- 建议：新开缺陷卡（或挂回相应 P1 卡）交由实现会话执行，本会话保留验收位。

## 7. J-Link 实测复核（2026-08-04，本会话，实测取代第 2 节推算）

用户指示「当前 JLink 是连接着的，你不可以使用 debug 吗？」后，改用在线测量。
以下全部为**实测数值**，脚本与产物在 `.cache/usb-diag/`。

### 7.1 关键前提：芯片内固件与磁盘上任何一份构建都不匹配

先做这一步，否则所有符号化结论都不可信。

| 对比 | 结果 |
|---|---|
| App 头 0x08010000 vs `Track-App-AC5.bin` | 512 字节中仅 2 字节不同（初始 SP：文件 0x2004DD58 / 芯片 0x2004CD40），中断向量全同 |
| App 头 vs `X-Track-App-GCC.bin` | 211/512 不同 |
| App 代码体 0x08037800 / 0x08046000 | 与 AC5 构建差异 **98.1% / 97.1%** —— 头部相同但代码整体偏移 |
| boot 头 0x08000000 vs `X-Track-Boot.bin` | 58/256 不同，且**每处差异恰为 −8**（芯片 Reset=0x08002899 / 文件=0x080028A1），SP 相同 |

结论：芯片上是**较早的 AC5 系 App + 较早的 boot**。此前基于磁盘 `.axf` / `.elf`
的地址符号化（`children_repos`、`check_card_programming`、`MainMenu::*` 等）
**全部无效**，已废弃。boot 侧因偏移为常数 −8，符号化时仍可用（见 7.4）。

### 7.2 App 侧健康，问题完全在 boot 之前

- DWT CYCCNT 两次 1 s 窗口：289,014,117 / 288,979,484 周期 → **288 MHz**，
  `CRM_CFG=0x0000900A`（sclksts=PLL）——App 主频正常
- 上电至今完整 RTT 日志（Up[0]@0x2004B478，WrOff=287/RdOff=0，从未回卷也从未被消费）：
  ```
  HANDOFF vtor=0x08010000
  Reset: NRST POR
  QSPI: JEDEC=0xEF4018 whitelisted, OTA enabled
  OTA: BCB already CONFIRMED vcode=20800
  ```
  末行只可能由 `loop()` 中的 `OTA_ConfirmUpdate()` 打印（`USER/main.cpp:91,103`
  是 `OTA_ConfirmBoot` 的唯一调用路径）→ **`setup()` 已整段跑完**，
  `Usb_Init()` / `SD_Init()` / `Display_Init()` 全部返回
- 背光已满亮：TMR2 使能计数，pr=999，**c3dt=1000**，PB10 处于 MUX/AF 模式。
  写入该值的唯一路径是 `Backlight_SetGradual(1000,1000)` 的 lv_anim
  （`MDK-ARM_F435/Platform/HAL/HAL_Display.cpp:154`）→ LVGL 动画引擎在跑
- 显示总线在传输：SPI1 ctrl1=0x344（SPIEN+MSTEN）、ctrl2=0x02（DMATEN），
  sts 由 0xC1 变 0x43 且 BF 置位

### 7.3 实测启动耗时 **15.5 秒**

方法：把 RTT 签名首字（0x2004B3D0）清零 → `r` + `g` → 每 500 ms 轮询该地址，
签名重现即等于 App 的 `SEGGER_RTT_Init()` 已执行。

```
*** RTT 签名出现于第 31 个样本 -> 复位后约 15.5 秒 ***
```

即**复位到 App 第一行代码之间有 15.5 s**，此期间背光仍是 `Backlight_Init()`
设的 0，屏幕全黑——与「按下开机键很久都是黑屏」完全吻合。
（第 2 节静态推算为 ≈9.2 s，偏低；以本实测 15.5 s 为准。）

### 7.4 实测 boot 主频 **8.07 MHz**，热点为 SHA-256

方法：清签名 → `r` + `g` → 26 × [`sleep 500`, `h`, `regs`, `g`] 采 PC。

- 26 个样本 PC **全部**落在 0x08000000–0x0800FFFF（boot 区），无一进入 App 区
- CycleCnt 每 500 ms 推进 ≈0x3D8000 ≈ 4.03 M 周期
  （样本 2 → 27：0x003D8B6F → 0x0640A817，100.8 M 周期 / 12.5 s）
  → **8.07 MHz**，正是 HICK 复位默认值
- 两个热点簇符号化（`Tools/addr2line.exe -e build-gcc-release/boot/X-Track-Boot.elf`，
  原地址与 +8 修正后结果一致，函数体足够大不受常数偏移影响）：

  | 地址簇 | 符号 |
  |---|---|
  | 0x080002xx–0x080003xx | `sha256_transform`（`boot_sha256.c`） |
  | 0x080032xx | `memcpy` |

这直接对应第 2.3 节：`boot_state_machine.c:578` 的 `BCB_STATE_CONFIRMED` 分支
每次开机调用 `validate_internal_app()` → `boot_fw_header_validate_ex()`
（`boot_fw_header.c:165-188`）对全部 598,680 字节按 256 字节分块
（2,339 次 `reader->read` + memcpy）做软件 SHA-256。

**至此根因链闭合且全程可测**：boot 停留在 8 MHz（`boot_platform_init()` 只调
`system_core_clock_update()` 读频率，从不调 `system_clock_config()` 配 PLL）
→ 全镜像软件 SHA-256 被放大 36 倍 → 15.5 s 黑屏 → App 起来后一切正常。

### 7.5 对第 4 节修复方案的影响

修复方案不变，且被实测进一步支持：

- **不得**动 SHA。`PLAN-OTA.md:83`「镜像真伪始终以 fw_header SHA 为准 —
  禁止跳过/弱化 SHA 校验来提速」是冻结契约，改它必须走 OTA 规约 §2
- **只修时钟**：`boot_platform_init()` 调用 `system_clock_config()`。
  按 8.07 MHz → 288 MHz 折算，15.5 s → **约 0.43 s**
- 实施时注意 `system_clock_config()` 内部会调 `crm_reset()`，它会清掉此前所有
  `crm_periph_clock_enable()`——调用顺序必须放在任何外设时钟使能**之前**

### 7.6 尚未验证项

- 用户场景是「插着 USB 上电」，而本轮探测时 USB 未接
  （DCFG DevAddr=0、DSTS SUSPSTS=1）。插 USB 是否让 15.5 s 进一步变长，
  需用户实际插线上电后复测
- 15.5 s 与第 2 节推算 9.2 s 的差额（约 6 s）尚未逐项归因；PC 采样显示全程
  都在 SHA/memcpy，倾向于是 flash 等待周期与分块开销高于保守估算，
  但未单独计量

## 8. 第二缺陷：boot 与 App 重复锁存 POWER_EN（PD2），实测有 1 秒撤保持窗口

由用户提问触发：「当前 app 程序是有持久化供电 io 的，boot 程序中有吗？」

### 8.1 结论先行

boot **有**供电保持，所以不需要全程按住开机键。真正的问题是
**App 在 boot 已锁存之后又重做了一遍「拉低 1 秒再拉高」**，形成一个
主动撤除供电保持的 1 秒窗口。这是与第 7 节时钟缺陷**相互独立**的第二个缺陷。

### 8.2 极性判定（反查关机路径，非假设）

`MDK-ARM_F435/Platform/HAL/HAL_Power.cpp:174` 的 `Power_EventMonitor()`
执行关机时写的是 `digitalWrite(CONFIG_POWER_EN_PIN, LOW)`
→ **PD2 高 = 保持供电，PD2 低 = 断电**。
`CONFIG_POWER_EN_PIN = PD2`（`USER/HAL/HAL_Config.h:114`），
`CONFIG_POWER_WAIT_TIME = 1000`（同文件 :115）。

### 8.3 两处锁存代码

| 位置 | 代码 | 时机 |
|---|---|---|
| boot | `boot_platform_at32.c:50-65` `configure_power_hold()`：GPIOD PIN2 推挽输出 → `gpio_bits_reset` → `boot_platform_delay_ms(1000)` → `gpio_bits_set` | `boot_platform_init()` 内**第一个**调用，早于 recovery key / UART / EEPROM |
| App | `HAL_Power.cpp:108-111` `Power_Init()`：`pinMode(OUTPUT)` → `digitalWrite(LOW)` → `delay(1000)` → `digitalWrite(HIGH)` | `HAL_Init()` 内第一个调用 |

App 那段是**单体固件时代**的遗留：当时它是唯一锁存点，且在复位后几毫秒执行，
用户手指还按在开机键上，"拉低 1 秒"只是上电防抖。现在 boot 已经做过同样的防抖
并锁存，App 再做一遍就变成了主动撤保持。

### 8.4 实测 PD2 时序

方法：`r` + `g`，此后每 250 ms 读一次 GPIOD ODT（`0x40020C14`）bit2，共 84 样本 ≈21 s。
脚本 `.cache/usb-diag/pd2.jlink`。

```
t= 0.00s  ODT=0x00000000  PD2=0   复位默认 / boot 拉低
t= 0.75s  ODT=0x00000004  PD2=1   boot configure_power_hold() 锁存
t=15.00s  ODT=0x00000000  PD2=0   ★ App Power_Init() 再次拉低
t=16.00s  ODT=0x00000004  PD2=1   App 延时 1000ms 后重新锁存
末样本 t=20.75s PD2=1
```

t=0.75s 与 boot 的 1000 ms 延时吻合（采样粒度 250 ms）；
t=15.00s 与第 7.3 节实测的 App 启动点（≈15.5 s，500 ms 粒度）为同一事件簇。

### 8.5 后果分级（其一未证实，需实机观察）

- **手指已松开**（15 秒后必然已松）：t=15.00–16.00 s 期间供电保持被撤除。
  是否真正掉电取决于 PD2 所驱动电源使能端的外部维持能力（电容/并联按键路径），
  **无法从代码判定，需原理图或实机观察**。若确实掉电，表现为
  「开机 → 黑屏 15 秒 → 自动断电 → 循环」，即**电池供电下根本无法开机**。
- **手指仍按着**：按键路径顶住这 1 秒，t=16 s 重新锁存，表现即用户报告的
  「按很久才亮」。

**本会话全部观测均为 J-Link 或 USB 外部供电**，外部供电会完全掩盖该窗口——
这正是它此前未被发现的原因。

**判别实验（用户可自行完成，无需工具）**：电池供电按开机键，**在 15 秒之前松手**，
观察设备是否在 15 秒左右自行断电/重启。断电 → 缺陷成立且为硬故障；
正常亮屏 → 仅为风险窗口，硬件有余量兜住。

### 8.6 修复方向与实施红线

修复方向：App 的 `Power_Init()` 在「由 boot 交接进入」时应跳过拉低-延时序列，
只确保 PD2 维持高电平。识别手段已存在——`Libraries/OTA/ota_vtor_check.c` 已捕获
handoff 状态（`g_ota_handoff_vtor`），且 App target 有 `OTA_TARGET_APP` 编译期宏。

**实施红线（与第 7 节时钟修复的交互，极易踩）**：
`boot_platform_init()` 当前顺序是
`system_core_clock_update()` → `SysTick_Config(system_core_clock/1000)` →
`configure_power_hold()` → `configure_recovery_key()` → …

插入 `system_clock_config()` 时**必须放在函数第一行**，理由有二，缺一即出事：

1. `system_clock_config()` 内部调用 `crm_reset()`，会清掉此前所有
   `crm_periph_clock_enable()`。若放在 `configure_*()` 之后，GPIO/UART/I2C 时钟被清空。
2. `SysTick_Config()` 用的是 `system_core_clock` 变量值。若先配 SysTick 再提主频，
   SysTick 会按 8 MHz 配置却运行在 288 MHz，**boot 内所有毫秒计时被压缩 36 倍**——
   包括 `configure_power_hold()` 的 1000 ms 防抖，以及
   `boot_platform_recovery_key_held()` 的 `BOOT_RECOVERY_HOLD_MS = 3000`。
   后者会把 `PLAN-OTA.md:23`「raw recovery 只允许在持续按住编码器按键 ≥3s 的物理
   在场条件下进入」实际削成 ≈83 ms，**这是直接破坏冻结契约**，必须避免。

即：正确顺序为 `system_clock_config()` → `system_core_clock_update()` →
`SysTick_Config()` → `configure_power_hold()` → …

### 8.7 契约影响

`PLAN-OTA.md` 与 `docs/ota-binary-contracts.md` 对 boot 主频、启动时间、上电时序
**均无条款**（对「主频/时钟/MHz/启动时间/上电/power/POWER_EN/PD2/供电」全文检索零命中）。
两处修复均为纯实现缺陷修正，不触碰冻结契约，无需走 OTA 规约 §2 / 看板 §9。

反例（必须走 §9 的做法）：以「跳过或弱化 CONFIRMED 路径的 SHA 校验」来提速，
会改变 `PLAN-OTA.md:83` 语义；以及上述 8.6 红线 2 若被踩中，会实际削弱
`PLAN-OTA.md:23` 的 3 秒物理在场条件。


## 9. CMake 源清单归属核查（回答「能否先在 Keil 工程添加」）

修复缺陷 A 需要 boot 目标链入 `system_clock_config()`，即新增两个源文件依赖。
自然的想法是「先加进 Keil 工程，再用 `keil_uvprojx2cmake.py` 重新生成 CMake」，
从而避免手改生成物。**该路线在本仓库不成立**，核查如下。

### 9.1 核查命令与结果

```
$ grep -o "<TargetName>[^<]*</TargetName>" MDK-ARM_F435/proj.uvprojx
<TargetName>X-Track</TargetName>
<TargetName>X-Track-App-AC5</TargetName>

$ grep -n "add_executable\|^set(.*_SOURCES" MDK-ARM_F435/cmake-generated/CMakeLists.txt
140:set(PROJECT_SOURCES
505:set(APP_PROJECT_SOURCES ${PROJECT_SOURCES})
531:set(BOOT_PROJECT_SOURCES
559:add_executable(X_Track ${PROJECT_SOURCES})
560:add_executable(X_Track_App_GCC ${APP_PROJECT_SOURCES})
563:add_executable(X_Track_Boot ${BOOT_PROJECT_SOURCES})

$ grep -n "at32f435_437_clock.c\|at32f435_437_pwc.c" MDK-ARM_F435/cmake-generated/CMakeLists.txt
189:    ".../../Platform/Core/at32f435_437_clock.c"
216:    ".../../RTE/Device/-AT32F435RGT7/at32f435_437_pwc.c"

$ grep -n "at32f435_437_clock.c\|at32f435_437_pwc.c" MDK-ARM_F435/proj.uvprojx
4466/4468, 9214/9216  <FilePath>.\Platform\Coret32f435_437_clock.c
9998                  RTE\Device\-AT32F435RGT7t32f435_437_pwc.c
```

### 9.2 三条结论

1. **Keil 没有 boot target。** `proj.uvprojx` 只有 `X-Track`（legacy AC5）与
   `X-Track-App-AC5`。这与 P1-2 冻结的目标矩阵一致：`X-Track-Boot` 是 GCC/CMake
   独有目标，本就没有 Keil 对应物。脚本没有 boot 目标可读，**永远不会**生成
   `BOOT_PROJECT_SOURCES`。

2. **这两个文件本就已在 Keil 工程中。** `at32f435_437_clock.c` 在 uvprojx 的
   4466/9214，`at32f435_437_pwc.c` 是 RTE 组件实例（9998）。脚本已经把它们生成到
   `PROJECT_SOURCES` 的 189/216 行。所以「先加 Keil」是**空操作**——它们已经在，
   缺的只是 boot 目标那份独立清单。

3. **`BOOT_PROJECT_SOURCES` 不是生成物。** 脚本产出的只有 `PROJECT_SOURCES`
   (140-503) 与 `add_executable(X_Track ...)`。505 行之后的
   `APP_PROJECT_SOURCES` 增删、`BOOT_PROJECT_SOURCES`、app/boot linker script 规则、
   `P1_6_TEST_ENABLE` / `P2_*_TEST_ENABLE` option 全部是历次 OTA 卡手写追加的。
   P0-4 已明确采用此做法（`docs/ota-exec-notes/P0-4-eeprom-bcb.md:32`：
   「生成脚本仍为权威，但 P0-4 新增文件需手填 CMakeLists 以保 CI 不红」）。

### 9.3 对 P1-7 的处置

P1-7 按既有惯例，在 `BOOT_PROJECT_SOURCES` 手写追加两行，与 P0-4/P1-2/P1-6 一致，
**不属于**违规手改生成物。

AGENTS.md「不要因为 CI 红就去手改 `cmake-generated/CMakeLists.txt`」针对的是
**可移植性问题**（如反斜杠 include）——那类问题应改生成脚本或手写源。新增 OTA 专有
目标的源依赖不在其列。

### 9.4 遗留的存量风险（不在 P1-7 范围）

若有人重跑 `keil_uvprojx2cmake.py`，会冲掉 505 行以后**全部** OTA 手写内容，
不止 P1-7 这两行。该风险是存量、跨卡的，P1-7 只是又加两行、不改变其量级。
根治方案（把 OTA 段抽成 `MDK-ARM_F435/cmake-generated/cmake-ota.cmake`，
生成文件末尾只留一行 `include(cmake-ota.cmake)`，并把该 `include` 写进
生成脚本的模板）属于工具治理，需另立卡，**不得**在 P1-7 内顺手做（越卡）。
