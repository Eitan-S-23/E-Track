# P2-5 独立验收（第二轮：F1 整改复验）

- 验收人：Claude（非实现会话，独立验收）
- 日期：2026-08-04
- 依据：`AGENTS.md` 「OTA 执行规约」§3「验收命令由非实现会话执行（实现者不自验收）」
- 工作区：`D:\github\my\E-Track-p2-5-20260801`，分支 `p2-5-20260801`，HEAD `614a3fc`
- 第一轮报告：`docs/ota-exec-notes/P2-5-acceptance-2026-08-03.md`（判定：不通过，阻断 2 未关闭，编号 F1）

---

## 1. 结论

**F1 已关闭（独立复现，含负对照与更严格判据）。但本卡不得置「完成」，保持 `进行中`，P2 保持 `4/6`。**

理由分离清晰：

- 软件侧：F1 缺陷已被真正修复（机制层，不是症状层），全部宿主回归零回退，双工具链构建、模拟器、边界检查全绿——本轮逐项独立重跑复现，不采信汇报数值。
- 卡内验收硬条件仍未满足：**「真机完整一轮 SD 升级：STAGED→重启→APPLYING→TEST_BOOT→CONFIRMED，RTT 全程留痕」至今无人执行**。第一轮因确定性缺陷「先修再测」而跳过，本轮缺陷已修，但真机链仍是空白。缺此证据不得置完成。

---

## 2. F1 整改的独立判定

### 2.1 修复形态复核（读源码，未修改）

`USER/main.cpp` 的 `OTA_ConfirmUpdate()` 已按方案 2 改造：喂狗被提到状态判断**之外**，只要 `HAL::OTA_WatchdogIsConfigured()` 为真就每圈 `HAL::OTA_WatchdogFeed()`；`g_ota_confirm_done` 只门控「是否再发起确认」，不再门控喂狗。

关键点在于 gate 的性质。`USER/HAL/HAL_EEPROM.cpp:121-152`：

```c
#define OTA_BOOT_TEST_WATCHDOG_DIV    WDT_CLK_DIV_256
#define OTA_BOOT_TEST_WATCHDOG_RELOAD 1561u
int HAL::OTA_WatchdogIsConfigured(void)
{
    return (int)(WDT->div_bit.div == (uint32_t)OTA_BOOT_TEST_WATCHDOG_DIV &&
                 WDT->rld_bit.rld == (uint32_t)OTA_BOOT_TEST_WATCHDOG_RELOAD);
}
```

这是**寄存器读**，不是软件状态读。与 boot 侧 `boot/platform/at32/boot_platform_at32.c` 的 `boot_platform_watchdog_start()` 参数（`WDT_CLK_DIV_256`，`BOOT_TEST_WATCHDOG_RELOAD = 1561`）逐项对号一致。

因此：`OTA_SnapshotState()` 仍保留的缓存语义、以及确认成功后仍保留的 `g_ota_state_snapshot = BCB_STATE_CONFIRMED` 改写，**现在都对喂狗无影响**——它们改的是软件快照，而喂狗判据来自硬件寄存器。F1 的因果链被从根上切断，而非绕过。判定：机制层修复，不是症状层遮盖。

### 2.2 独立探针（本会话自建，第二轮）

不复用实现方的 C13，自建探针 `docs/ota-exec-notes/P2-5-acceptance-feed-probe-r2.c`（7307B / 2026-08-04 15:39:03 / SHA-256 `5D3C3B06A0EBB94674D8DEAE5326B82901F219BEA1FE22D8952C4AED9528556D`）：

- 逐字照抄当前 `USER/main.cpp` 的编排，仅把 HAL 替换为计数器；
- 链接**真实**的 `Libraries/OTA/ota_confirm_health.c`，不做桩替换；
- 判据比实现方 C13 更严：不仅要求「确认后喂狗次数 > 0」和「尾部静默 < WDT 超时」，还要求**确认后逐窗最大喂狗间隔 < WDT 超时**（`max_gap_after_confirm`），排除「喂过几次然后长时间静默」的漏网形态；
- 增设 case B：确认永久失败的路径也必须持续喂狗。

构建与运行：

```
gcc -std=c99 -Wall -Wextra -O2 -ILibraries -Iboot/include \
    docs/ota-exec-notes/P2-5-acceptance-feed-probe-r2.c \
    Libraries/OTA/ota_confirm_health.c -o .cache/feed_probe_r2.exe
```

输出：

```
WDT_TIMEOUT_MS=9990
[A: TEST_BOOT, confirm succeeds]
  confirmed=1 confirmed_at_ms=30000
  feeds_total=9000 feeds_at_confirm=3000 feeds_after_confirm=6000
  last_feed_ms=90000 run_end_ms=90000 silence_after_last_feed_ms=0
  max_feed_gap_after_confirm_ms=10 (WDT timeout=9990)
[B: TEST_BOOT, confirm always fails]
  confirmed=0 confirmed_at_ms=0
  feeds_total=9000 feeds_at_confirm=0 feeds_after_confirm=9000
  last_feed_ms=90000 run_end_ms=90000 silence_after_last_feed_ms=0
  max_feed_gap_after_confirm_ms=0 (WDT timeout=9990)
P2_5_FEED_PROBE_R2=PASS failures=0
```

关键数字：确认后喂狗 6000 次，**确认后最大喂狗间隔 10ms，对比 WDT 超时 9990ms，余量约 999 倍**。确认永久失败时喂狗同样从不停止。

### 2.3 负对照（证明判据有鉴别力）

第一轮探针 `docs/ota-exec-notes/P2-5-acceptance-feed-probe.c`（5303B / 2026-08-03 20:39:08 / SHA-256 `D18A50B0...E2D622A2`，本会话未改动）照抄**缺陷版**编排，重跑仍然失败：

```
feeds_total=3000 feeds_at_confirm=3000 feeds_after_confirm=0
last_feed_ms=30000 run_end_ms=90000 silence_after_last_feed_ms=60000
FAIL: no watchdog feed after confirm -> IWDG resets at ~39990ms
FAIL: feed silence 60000ms >= WDT timeout 9990ms
P2_5_FEED_PROBE=FAIL failures=2
```

同一判据在缺陷版 FAIL、修复版 PASS，说明本轮 PASS 不是判据放水导致的假绿。

### 2.4 实现方 C13 回归审查

`tests/ota/test_ota_confirm_health.c:175-317`（11408B / 2026-08-04 14:42:42 / SHA-256 `226BE86C...C14AEC4`）新增 C13，照抄修复后控制流并**跨 `OTA_ConfirmUpdate()` 编排**，10ms 步进跑到 90000ms，三条断言：

```c
check("C13 confirm happened", confirmed_once == 1);
check("C13 feeds after confirm > 0", feed_count - feeds_at_confirm > 0u);
check("C13 feed silence < WDT timeout",
      90000u - last_feed_ms < (unsigned long)C13_WDT_TIMEOUT_MS);
```

判定：**方向正确、确实补上了漏检面**。第一轮 F1 之所以逃逸，正是因为 C12 只直呼 `ota_confirm_health_feed()` 而不过编排；C13 补的就是这条路。常量 `1561/256/40000` 与 boot 一致。

但 C13 是实现者自撰，按 §3 不构成独立证据；本轮判定以 §2.2/§2.3 的自建探针 + 负对照为准。C13 的价值是**防回归**，已确认可用。

附带核实「缺陷注入验证后已还原」：实现会话做缺陷注入时留下的备份 `.cache/p2-5/test_ota_confirm_health.c.bak` 与当前工作树 `tests/ota/test_ota_confirm_health.c` **SHA-256 逐字节一致**（均为 `226BE86CD97A8DF9A0F179AB257E3CD933DB7941BB71D6C97B8860572C14AEC4`），确认测试文件中无残留的缺陷版代码。

---

## 3. 宿主回归（本会话逐条重跑，全部 rc=0）

| 测试 | 结果 |
| --- | --- |
| `tests/ota/test_ota_backup.py` | `P2_5_OTA_BACKUP_ALL=PASS` 108/0 |
| `tests/ota/test_ota_confirm_health.c` | **17/0**（第一轮 14，C13 +3） |
| `tests/ota/test_ota_update.py` | `P2_4_OTA_UPDATE=PASS scenarios=7` |
| `tests/ota/test_ota_sd.py` | `P2_4_OTA_SD_ALL=PASS core_checks=29 adapter_scenarios=5` |
| staging | `P2_1_STAGING=PASS checks=48` |
| package | `P2_2_PACKAGE=PASS checks=102` |
| patch | 167/167 |
| 状态机 | `P1_3_STATE_MACHINE=PASS checks=96` |
| boot 协议 | `P1_1_BOOT_PROTOCOLS=PASS`（19 checks） |
| 固件头向量 | `P1_1_FW_HEADER_VECTORS=PASS cases=16` |
| P1-6 协议 | `P1_6_PROTOCOL=PASS checks=21` |
| ota-vectors | `Ran 9 tests OK` |

零回退。

---

## 4. 双工具链构建

### 4.1 GCC Release（`do_build.bat release`，rc=0）

- App FLASH **598680 B（60.90%）**，RAM 295648 B（82.02%），RW_IRAM2 160KB（100%）
- 相比第一轮 598664 B，**+16 B**——与「仅新增一处寄存器读 gate + 喂狗调用外提」的改动量级相称，无异常膨胀
- 仅仓库既有 wchar_t-ABI 与 RWX-LOAD 告警，0 error
- 产物时间戳 2026-08-04 15:46:32.580224300

### 4.2 Boot 零改动（关键安全边界）

- `X-Track-Boot.bin` 14236 B @ 2026-08-04 15:46:30.626833900
- SHA-256 `5656466564891b54666325da4545f3f819ba38f50660ab4772809b5647135ab5`
- 与 P2-3 记录**逐字符一致**；`git status -- boot/` 为空
- 判定：本次整改未触碰 bootloader

### 4.3 AC5（`X-Track-App-AC5`，uv4_rc=0）

- `0 Error(s), 0 Warning(s)`
- `Program Size: Code=300908 RO-data=289372 RW-data=1324 ZI-data=499560`（Code 第一轮 300900，**+8 B**）
- Build Time 00:02:11
- `.axf` 7345624 B @ 15:52:15.493522100；`.hex` 1662631 B @ 15:52:16.275271000；`Track-App-AC5.bin` 591084 B @ 15:52:17.070810300

### 4.4 模拟器（`/t:Rebuild`，MSBUILD_RC=0）

- `Simulator\Output\Debug\x64\LVGL.Simulator.exe` 5876224 B @ 2026-08-04 16:12:43.4326189
- SHA-256 `0C6B3A894827CB7F78B2A660DA5B8A1BB9425D1D28513ED6E296B1BB16AC9BAE`
- 按 AGENTS.md 要求验证**两次**启动：
  - run1：`responding=True`，private 88.3MB，WS 52.7MB，CPU 1.08s
  - run2：`responding=True`，private 88.2MB，WS 52.6MB，CPU 1.17s
  - 两次退出后 `left=0`，无残留进程
- 内存两次持平（88.3 → 88.2），无增长趋势

---

## 5. 边界与规约检查

| 检查项 | 结果 |
| --- | --- |
| 冻结契约 `PLAN-OTA.md` / `docs/ota-binary-contracts.md` | 零 diff（§2 满足） |
| `boot/` 目录 | 零 diff |
| 全仓 `git diff --check` | rc=0，无空白/EOL 违规 |
| `MDK-ARM_F435/RTE/**` | 内容零差异（`git diff --numstat` 空，仅 EOL 提示） |
| HEAD | 仍为 `614a3fc`，分支 `p2-5-20260801` 无 ahead 标记 ⇒ 未 commit/push（§5 满足） |
| 生产入口 | `USER/App/App.cpp:178 manager.Push("Pages/Startup")` 完好 |
| 测试/调试残留 | `USER/`、`Libraries/OTA/` 中 `P2_5_TEST|P2_5_HW|OTA_FORCE_|_TEST_HOOK|TODO_P2_5` 零命中 |
| 第一轮报告完整性 | `P2-5-acceptance-2026-08-03.md` 11294B @ 2026-08-03 21:32:26 / SHA-256 `47B78C05...ACA6028EE`，与第一轮记录逐项一致 ⇒ 实现方未篡改验收报告 |
| 第一轮探针完整性 | `P2-5-acceptance-feed-probe.c` 5303B @ 2026-08-03 20:39:08 / SHA-256 `D18A50B0...E2D622A2`，未被改动 |
| 看板回写（§6/§1） | P2-5 卡 `进行中`；总表 P2 `4/6`；证据栏含 C13 与 `17/17`；新增「F1 整改」条目；§10 追加 2026-08-03 实现会话日志行；第一轮验收行原文保留未改 ⇒ 汇报与看板一致 |

本会话自身产生的临时物（`MDK-ARM_F435/build_ac5.log`、`.cache/feed_probe_r1.exe`、`.cache/feed_probe_r2.exe`）已删除并复查不存在。AC5 构建曾使 uVision 重新生成 `MDK-ARM_F435/RTE/_X-Track-App-AC5/RTE_Components.h`（3 行注释尾随空格），已用反向 Edit 逐行还原（**未使用 `git checkout/restore`**，因 §5 禁止提交，工作区未提交文件是唯一副本），复查内容零差异。

---

## 6. 仍未关闭的项（不构成 F1 的复发，但阻止本卡置完成）

以下均为**卡内验收硬条件**，至今无任何会话执行：

1. **真机完整一轮 SD 升级**：STAGED→重启→APPLYING→TEST_BOOT→CONFIRMED，RTT 全程留痕。
2. **TEST_BOOT 存活验证**：真机上跨过 ≥1 个 WDT 周期（9990ms）**且**确认后继续存活 ≥30s 无复位。这是 F1 修复的**唯一物理终检**——宿主探针能证明控制流对，不能证明 `WDT->div_bit/rld_bit` 在真实 boot 交接后确实等于 `256/1561`（若 boot 实际写入值与 App 侧常量有任何偏差，gate 恒假，喂狗一次都不会发生，宿主测试对此完全盲）。
3. **TEST_BOOT 期间拒绝发起新 OTA** 的真机验证。

第 2 项是本轮最需要强调的残余风险：修复的正确性依赖「App 侧常量 == boot 侧实际写入寄存器值」这一跨侧假设。本会话已在源码层对号（§2.1），但源码一致 ≠ 运行期寄存器一致（编译器/启动顺序/boot 版本漂移都可能介入）。**只有真机 RTT 能终检。**

真机链执行时必须遵循 `AGENTS.md` 的 J-Link 防卡死清单：重查 `X-Track.map` 取 `_SEGGER_RTT` → `mem8` 验 `SEGGER RTT` 签名 → 读 down descriptor → 发 `gpsreset`/`livemap` → 启动**单个** `JLinkRTTLogger` 且带超时。任何来自旧 RTT 地址、残留 logger 或错误回显的日志一律作污染日志重测。

---

## 7. 判定汇总

- **F1（阻断 2「确认后持续喂狗」）：关闭。** 依据：机制层修复（寄存器 gate 不受快照改写影响）+ 本会话自建更严探针 PASS（确认后最大喂狗间隔 10ms vs 超时 9990ms）+ 负对照仍 FAIL + C13 防回归就位。
- **本卡：不得置完成，保持 `进行中`；P2 保持 `4/6`。** 依据：卡内「真机完整一轮 SD 升级 + RTT 全程留痕」未执行，且 F1 修复缺物理终检。
- 本会话未修改任何实现文件，未运行板卡命令，未 commit/push，未自验收。
