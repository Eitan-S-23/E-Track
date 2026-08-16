# 任务：实现 OTA 看板任务卡 P1-7（boot 启动耗时与 POWER_EN 重复锁存修复）

> 本文件是 P1-7 实现会话的提示词。由 P2-5 独立验收会话（发现并立卡方）撰写，
> 落盘时间 2026-08-04。实现会话直接读本文件开工，不需要再让用户复述背景。

## 0. 你的身份与规约（先读，违反即作废）

你是 **P1-7 的实现会话**。本仓库 `AGENTS.md` 的「OTA 执行规约」对你强制生效：

1. **先读看板再动手**：`PLAN-OTA-EXEC.md` 是唯一任务与状态源。开工前先把 P1-7 卡
   状态改为「进行中」并写认领标识，**只改卡内「范围」列出的文件**。
2. **契约只读**：`PLAN-OTA.md` 与 `docs/ota-binary-contracts.md` 冻结。发现矛盾或
   不可实现 → 把 P1-7 置「阻塞」+ 在看板 §9 变更登记表登记，然后停止。
   **禁止就地修改契约继续实现**。
3. **完成必须附证据**：命令 + 关键输出、产物路径 + 时间戳、哈希。长输出落盘
   `docs/ota-exec-notes/P1-7-implementation-evidence-2026-08-04.md`。
   **你不自验收** —— 验收由另一个非实现会话执行。
4. **research 落盘**：编码前的检索/分析结论写进上面那个证据文档，不许只留在对话里。
5. **不提交**：禁止 `git commit` / `push` / `merge`，由主会话收口。
6. **收尾**：结束前回写 P1-7 卡状态，并在看板 §10 会话日志追加一行。
7. **绝对禁止** `git checkout -- <file>` / `git restore`：本 worktree 的未提交内容
   是唯一副本，覆盖即永久丢失。

全局准则：**一切输出、文档、注释、日志、提交信息用简体中文**（代码标识符除外）。

## 1. 必读文件（按顺序）

- `PLAN-OTA-EXEC.md` 的 **P1-7 卡**（含红线与验收条目）
- `docs/ota-exec-notes/P1-7-boot-startup-and-powerhold.md`
  —— §7 时钟缺陷 J-Link 实测、§8 PD2 重复锁存实测、§9 CMake 源清单归属核查
- `AGENTS.md`：「J-Link 自动烧录与 RTT 闭环调试」「GCC / Linux CI 源码可移植防坑」

## 2. 背景（**实测基线，非推断**）

- 复位到 App 第一行代码实测 **15.5 s**，全程黑屏。
- App 在 **t=15.00s 把 PD2 拉低 1 秒**。该动作与 `Power_EventMonitor()` 的关机动作
  完全相同，因此**电池供电且手指已松开时设备会在此刻关机 —— 当前固件在纯电池供电下
  无法开机**。此前未被发现，是因为所有观测都接了 J-Link/USB 外部供电。

实测 PD2（GPIOD ODT `0x40020C14` bit2）时序基线：

| 时刻 | PD2 | 来源 |
|---|---|---|
| t=0.00s | 0 | 复位默认（GPIO 未配置） |
| t=0.75s | 1 | boot `configure_power_hold()` 锁存 |
| **t=15.00s** | **0** | **App `Power_Init()` 重新拉低 —— 与关机动作相同** |
| t=16.00s | 1 | App 延时 1000ms 后重新锁存 |

## 3. 缺陷 A：boot 全程运行在 8.07 MHz

**现状**：`boot/platform/at32/boot_platform_at32.c:117` 的 `boot_platform_init()`
只调 `system_core_clock_update()`（**仅读寄存器反算频率，从不配 PLL**），
于是 boot 全程 8.07 MHz（HICK 复位默认值；实测 26 次 PC 采样，CycleCnt 每 500ms
推进 ≈4.03M）。而 `boot/src/boot_state_machine.c` 的 `BCB_STATE_CONFIRMED` 分支
**每次开机**调 `validate_internal_app()`，对 598,680 字节做软件 SHA-256
（实测 PC 热点为 `sha256_transform` 与 `memcpy`），于是被放大 36 倍。

**要求**：boot 以 288 MHz 运行，复位到 App 首行 ≤1.5 s。

**改法**：调用 `system_clock_config()`（定义于
`MDK-ARM_F435/Platform/Core/at32f435_437_clock.c:46`）。

### 3.1 依赖缺口

boot 目标当前没编入所需文件，需在
`MDK-ARM_F435/cmake-generated/CMakeLists.txt` 的 `BOOT_PROJECT_SOURCES`
（当前 531-553 行）追加两行：

```cmake
"${CMAKE_CURRENT_LIST_DIR}/../Platform/Core/at32f435_437_clock.c"
"${CMAKE_CURRENT_LIST_DIR}/../RTE/Device/-AT32F435RGT7/at32f435_437_pwc.c"
```

pwc 是因为 `system_clock_config()` 内部调 `pwc_ldo_output_voltage_set()`。

### 3.2 关于「这算不算违规手改生成物」—— 已核实，不算，别再纠结

- 该文件只有 **140-503 行**由 `keil_uvprojx2cmake.py` 生成；505 行以后的
  `APP_PROJECT_SOURCES` 增删、`BOOT_PROJECT_SOURCES`、app/boot 两套 linker 规则、
  `P1_6_TEST_ENABLE` / `P2_*_TEST_ENABLE` option **全部是历次 OTA 卡手写维护的**
  （先例 P0-4 / P1-2 / P1-6，见 `docs/ota-exec-notes/P0-4-eeprom-bcb.md:32`）。
- **Keil 根本没有 boot target**：`proj.uvprojx` 只有 `X-Track` 与
  `X-Track-App-AC5`（与 P1-2 冻结矩阵一致，`X-Track-Boot` 是 GCC/CMake 独有目标）。
  脚本没有 boot 目标可依据，源文件加进 Keil 也**不会**进入 `BOOT_PROJECT_SOURCES`。
- 况且这两个文件**本就已在 Keil 工程中**（`proj.uvprojx` 4466/9214 与 RTE 9998），
  脚本已把它们生成到 `PROJECT_SOURCES` 的 189/216 行 ——「先加进 Keil 再重新生成」
  是**空操作**。
- 完整核查命令与输出见证据文档 §9。
- **禁止重跑 `keil_uvprojx2cmake.py`**：会冲掉 505 行以后全部 OTA 手写块，
  boot 目标整个消失，CI 的 `--target X_Track_Boot` 直接报 no such target。

### 3.3 需自行评估并把结论写进证据文档的两点

1. `at32f435_437_clock.c` 里还有 `extend_sram_512k()`。boot **不要调用**它；
   确认不调用时它是否仍被链接进来、对 `boot.bin ≤64KB` 的影响
   （当前 14,236 B，余量充足，但要给出数字）。
2. boot 把主频提到 288 MHz 后再跳 App，而 App 自己也会配一次时钟。检查
   `boot/platform/at32/boot_handoff_at32.c` 的交接路径是否需要把时钟/SysTick
   恢复到复位态，还是让 App 重配即可。
   **这是本卡唯一的新增交接风险，必须实测验证，不得靠推断下结论。**

### 3.4 时间预算（重要，防止你误判自己没达标）

`≤1.5 s` 这个验收值里，**有 1000 ms 是 boot `configure_power_hold()` 刻意的按键
防抖延时**（见 §4.1），不是浪费。剩给 SHA-256 与其余初始化的只有约 500 ms。

按 36 倍加速**估算**（非实测）：当前 15.5 s 中约 14.5 s 是 8 MHz 下的 SHA 与初始化，
提频后约 400 ms，加上 1000 ms 防抖 ≈ **1.4 s**。

所以：实测落在 1.3~1.5 s **属于通过**。**不要**因为"离 1.5s 太近"而去动 SHA
校验（红线 1），也**不要**去砍掉防抖延时（红线 4）。若实测显著超过 1.5 s，
说明另有问题，先定位再改，并在证据文档写清定位过程。

## 4. 缺陷 B：boot 与 App 重复锁存 POWER_EN

**现状**：boot 的 `configure_power_hold()`（`boot_platform_at32.c:50-65`）已完成
「拉低 → 延时 1000ms → 拉高」并锁存 PD2；App 的 `HAL::Power_Init()`
（`MDK-ARM_F435/Platform/HAL/HAL_Power.cpp:108-111`）又**无条件重做一遍**同样序列：

```cpp
pinMode(CONFIG_POWER_EN_PIN, OUTPUT);
digitalWrite(CONFIG_POWER_EN_PIN, LOW);   // ← 与 Power_EventMonitor() 的关机动作完全相同
delay(CONFIG_POWER_WAIT_TIME);            // 1000 ms
digitalWrite(CONFIG_POWER_EN_PIN, HIGH);
```

该序列在单体固件时代是唯一锁存点，且在复位后数毫秒执行（手指仍按住按键顶住供电）；
现在中间隔了 15 s 的 boot，语义变成「**主动撤除供电保持 1 秒**」。

极性依据：`HAL_Power.cpp:174` 的 `Power_EventMonitor()` 关机动作就是
`digitalWrite(CONFIG_POWER_EN_PIN, LOW)`。即 **PD2 低 = 断电**，由项目自身代码证明，
无需另做断电实验。

### 4.1 boot 侧那段「拉低→1000ms→拉高」是刻意设计，必须保留

它的语义是**按键防抖 / 有意开机确认**：PD2 保持低 1 秒期间不锁存供电，若用户在
1 秒内松手则设备断电不开机，从而过滤误触。boot 现在是复位后第一段代码，
**这个防抖放在 boot 是正确的**。

它之所以在电池供电下没出事，正是因为 t<1s 时用户手指还按着按键，硬件按键通路顶住供电
—— 与单体固件时代 `Power_Init()` 能工作的原因完全相同。

**不得**以"boot 也在拉低，一起优化掉"为理由删除它。删掉会导致任何瞬时误触都直接
锁存供电开机。

### 4.2 App 侧要求：语义是「确保为高」，不是「跳过整段」

**要求**：App 在由 boot 交接进入时**不再拉低 PD2**，只保证其维持高电平。

写成「确保 PD2 为高」而不是「什么都不做」的理由：即使出现某种未预期的进入路径
（PD2 尚未被锁存），这个写法依然能把电源锁住；而「跳过整段」在那种路径下会导致
用户松手即断电。两者代价相同，请采用前者。

**判别手段**：编译期宏 `OTA_TARGET_APP`（`CMakeLists.txt:704` 已为
`X_Track_App_GCC` 定义；boot 侧是 682 的 `OTA_TARGET_BOOT`）。

编译期宏在此**足够**，理由：OTA App 位于 0x08010000，复位向量在 boot 的
0x08000000 区域，因此 OTA App **物理上不可能脱离 boot 独立运行**。不需要再上
运行时检测（`Libraries/OTA/ota_vtor_check.c` 的 handoff 变量可作日志用途，
但不要为判别而引入新的运行时依赖）。

**易踩点**：`pinMode(PD2, OUTPUT)` 本身可能瞬时改变引脚电平。OTA 路径下必须保证
**全程不出现低电平样本**，注意 ODT 写值与 `pinMode` 的先后次序 —— 先确保 ODT 为高
再配模式，而不是反过来。

## 5. 红线（踩中即整卡作废重来）

- **红线 1（契约）**：禁止以「跳过/弱化 CONFIRMED 路径的 SHA 校验」来提速。那会改变
  `PLAN-OTA.md:83`「镜像真伪始终以 fw_header SHA 为准」的语义，**必须**先走规约 §2
  + 看板 §9。本卡不采用该路径。
- **红线 2（契约，极易踩）**：`system_clock_config()` 必须插在 `boot_platform_init()`
  **第一行**。两个理由缺一即出事：
  - ① 其内部调 `crm_reset()`，会清掉此前所有 `crm_periph_clock_enable()`；
  - ② `SysTick_Config()` 取的是 `system_core_clock` **变量值**，若先配 SysTick 再提
    主频，boot 内**全部毫秒计时被压缩 36 倍**，`BOOT_RECOVERY_HOLD_MS = 3000`
    实际变成 ≈83 ms，**直接破坏** `PLAN-OTA.md:23`「raw recovery 只允许在持续按住
    编码器按键 ≥3s 的物理在场条件下进入」。

  正确顺序：`system_clock_config()` → `system_core_clock_update()` →
  `SysTick_Config()` → `configure_power_hold()` → …
- **红线 3**：不得删除 App `Power_Init()` 的上电防抖逻辑本身（legacy / 非 OTA target
  仍是唯一锁存点），只允许在「由 boot 交接进入」的路径上跳过拉低-延时段。
- **红线 4**：不得删除或缩短 boot `configure_power_hold()` 的「拉低→1000ms→拉高」
  防抖段（理由见 §4.1）。它占掉 ≤1.5s 预算里的 1000ms 是**预期行为**。

其他禁止项：不改 `boot/src/**` 任何校验逻辑；不改冻结契约；不越卡去做
`cmake-ota.cmake` 抽取（存量跨卡风险，须另立卡）；`#include` 一律用正斜杠
（Linux GCC 不把 `\` 当路径分隔符，本机 Windows 编过不代表 CI 绿）。

## 6. 构建验证（全部要留命令与关键输出）

GCC（OTA 官方产物，与 CI 一致；构建目录必须落在**项目内**，禁止写到 `D:\tmp`、
`%TEMP%` 等项目外路径）：

```bash
cmake -S MDK-ARM_F435/cmake-generated -B MDK-ARM_F435/cmake-generated/build-gcc-release \
  -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_OBJECT_PATH_MAX=1024
cmake --build MDK-ARM_F435/cmake-generated/build-gcc-release \
  --target X_Track_App_GCC X_Track_Boot --parallel
```

宿主回归（CI 同款，必须全绿）：

```bash
python3 tests/boot/test_fw_header_vectors.py
python3 tests/boot/test_boot_protocols.py
python3 tests/boot/test_boot_state_machine.py
python3 tests/ota/test_ota_staging.py
python3 tests/ota/test_ota_package.py
python3 tests/ota/test_ota_patch.py
```

AC5 侧（legacy 路径不能被缺陷 B 的改动弄坏）：

```bat
build_f435_and_simulator.bat --no-pause
```

需报告 `Program Size` 行与产物时间戳；有 warning 要明说「有警告、零错误」，
不得把警告伪装成成功细节。

## 7. 真机自测（J-Link；正式验收由非实现会话重跑）

严格按 `AGENTS.md`「J-Link 闭环防卡死清单」：烧录后**重查
`MDK-ARM_F435/Listings/X-Track.map`（或对应 boot map）取 `_SEGGER_RTT`** →
`mem8 <RTT> 16` 验「SEGGER RTT」签名 → 读 down descriptor → 启动**单个**
`JLinkRTTLogger` 且带明确超时。启动前先：

```powershell
Stop-Process -Name JLinkRTTLogger -Force -ErrorAction SilentlyContinue
```

任何来自旧 RTT 地址 / 残留 logger / 错误命令回显的日志一律标记**污染**并重测，
不得参与判定。

对照 P1-7 卡的验收条目自测（方法在证据文档 §7.3 / §8.4）：

1. 复位到 RTT 签名出现 **≤1.5 s**（基线 15.5 s）。方法：清零 `_SEGGER_RTT` 签名首字
   → `r` + `g` → 轮询该地址等签名重现。
2. PD2（GPIOD ODT `0x40020C14` bit2）在 boot 锁存拉高后**不再出现回到 0 的样本**
   （基线 t=15.00s 掉 0、t=16.00s 回 1）。
3. 恢复模式仍需**持续按住 ≥3 s**，短按不进入；boot 侧 1000ms 防抖延时仍是真实 1 s
   （防红线 2 被踩中而不自知）。
4. boot 主频实测 288 MHz（DWT CYCCNT `0xE0001004` 增量，或读 CRM_CFG sclksts），
   且 `boot.bin ≤64KB` 不回退（P1-1 硬约束）。
5. 电池供电（拔掉 J-Link 与 USB）按开机键可正常进 App。
   **需用户物理配合，你自己做不了 —— 如实标注为「待用户配合」，不得以其他方式
   替代或声称通过。** 注意前四条都在外部供电下跑，而外部供电正是掩盖本 bug 的环境。

⚠️ 烧录会 halt MCU，可能把传输中的 SD 卡打成软复位救不回的挂死态（现象：
`SD_IsReady=0`、LiveMap stat 全 0、瓦片消失）。恢复方式是拔插 SD 卡或整机断电，
**不是代码 bug**，别去改代码。

## 8. 交付清单

- 证据文档 `docs/ota-exec-notes/P1-7-implementation-evidence-2026-08-04.md`：
  research 结论、逐条改动理由、全部构建/回归/真机命令与关键输出、产物路径+时间戳、
  §3.3 两个评估点的结论、以及**你没做到的项**（如验收 5）如实列出。
- 回写 P1-7 卡状态 + 看板 §10 追加一行会话日志。
- **不 commit**。改完停下，等非实现会话验收、主会话收口。
