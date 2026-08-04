# P2-5 独立验收报告（非实现会话）

- 验收人：Claude（非实现会话，未参与 P2-5 实现）
- 日期：2026-08-03
- worktree：`D:\github\my\E-Track-p2-5-20260801`，HEAD=`614a3fc`（=origin/main），26 个未提交文件
- 被验对象：`docs/ota-exec-notes/P2-5-closures-2026-08-02.md` 所述 11 项阻断关闭
- 结论：**不通过（打回）**。10 项关闭属实，**阻断 2「确认后持续喂狗」未真正关闭**，
  且该缺陷直接证伪本卡验收硬条件「TEST_BOOT 运行超过一个 WDT 超时周期无 WDT reset」。
  卡保持 `进行中`，P2 保持 `4/6`。

---

## 1. 复现性核验（全部由本会话独立执行，未复用实现会话输出）

### 1.1 宿主测试（全绿，与实现会话声明一致）

| 命令 | 本会话实测 | 声明值 | 一致 |
|---|---|---|---|
| `python tests/ota/test_ota_backup.py` | `P2_5_OTA_BACKUP checks=108 failures=0`、`P2_5_OTA_CONFIRM_HEALTH checks=14 failures=0`、`P2_5_OTA_BACKUP_ALL=PASS` | 108/108、14/14 | ✅ |
| `python tests/ota/test_ota_update.py` | `P2_4_OTA_UPDATE=PASS scenarios=7` | 7/7 | ✅ |
| `python tests/ota/test_ota_sd.py` | `P2_4_OTA_SD_ALL=PASS core_checks=29 adapter_scenarios=5` | 29+5 | ✅ |
| `python tests/ota/test_ota_staging.py` | `P2_1_STAGING=PASS checks=48 failures=0` | 48/48 | ✅ |
| `python tests/ota/test_ota_package.py` | `P2_2_PACKAGE=PASS checks=102` | 102 | ✅ |
| `python tests/ota/test_ota_patch.py` | `167/167 checks passed` | 167/167 | ✅ |
| `python tests/boot/test_boot_state_machine.py` | `P1_3_STATE_MACHINE=PASS checks=96 failures=0` | 96/96 | ✅ |
| `python tests/boot/test_boot_protocols.py` | `19 checks, 0 failure(s)` | 19 | ✅ |
| `python tests/boot/test_fw_header_vectors.py` | `P1_1_FW_HEADER_VECTORS=PASS cases=16` | 16 | ✅ |
| `python tests/boot/test_p1_6_protocol.py` | `P1_6_PROTOCOL=PASS checks=21 failures=0` | 21/21 | ✅ |
| `python tests/ota-vectors/test_vectors.py` | `Ran 9 tests ... OK` | vectors OK | ✅ |

既有回归零回退属实。

### 1.2 构建（本会话重跑，数值逐项吻合）

- **GCC Release**（`MDK-ARM_F435/cmake-generated/do_build.bat release`）：
  - App `FLASH: 598664 B / 960 KB = 60.90%`、`RAM: 295648 B = 82.02%` —— 与声明**完全一致**
  - Boot `FLASH: 14236 B / 64 KB = 21.72%`
  - Boot bin SHA-256 = `5656466564891b54666325da4545f3f819ba38f50660ab4772809b5647135ab5`
    —— 与 PLAN-OTA-EXEC.md P2-3 记录的 `5656466564891B...7135AB5` **逐字符一致**，
    佐证 **boot 零改动**（`git status` 亦确认 `boot/` 无任何变更）
  - warning 为仓库既有类别（2-byte wchar_t ABI + RWX LOAD），**0 error**
- **AC5**（`UV4 -b -t X-Track-App-AC5`）：
  - `Program Size: Code=300900 RO-data=289372 RW-data=1324 ZI-data=499560` —— 与声明一致
  - `"...X-Track-App-AC5.axf" - 0 Error(s), 0 Warning(s).`
  - `Track-App-AC5.bin` = 591076 B，时间戳 2026/8/3 21:11:27（本次重建）
- **模拟器**：`MSBuild /t:Rebuild` 成功，exe 时间戳 2026/8/3 21:20:07；
  启动 `responding=True`、私有内存 88.45 MB，二次探测仍 `True`，进程可正常终止。
  仅有 LVGL 既有 C4267/C4018 warning。

### 1.3 边界遵守（全部属实）

- `git status` 显示 `boot/`、`PLAN-OTA.md`、`docs/ota-binary-contracts.md` **零改动**（冻结契约未动）。
- `git diff --check` 无输出（EOL/空白干净，阻断 11 属实）。
- 生产入口 `USER/App/App.cpp:178 manager.Push("Pages/Startup")`，唯一。
- 全仓检索无 `P2_5_TEST` / `P2_5_HW` / harness 残留。
- 未 commit / 未 push（工作区 26 个文件仍为未提交状态）。

---

## 2. 阻断项（1 项，判定打回）

### F1｜阻断 2 未关闭：确认成功后喂狗立即停止，约 10 s 后被 IWDG 复位

**严重度**：高（证伪本卡验收硬条件；每轮 OTA 首启必发生一次非预期复位）

**位置**：`USER/main.cpp:38-50`（`OTA_SnapshotState`）、`USER/main.cpp:52-100`（`OTA_ConfirmUpdate`）

**机理**：

`OTA_SnapshotState()` 只在首次调用时读一次真实 BCB，此后恒返回缓存
`g_ota_state_snapshot`：

```c
static uint8_t OTA_SnapshotState()
{
    if(g_ota_state_snapped) { return g_ota_state_snapshot; }   // 之后永远走这里
    g_ota_state_snapshot = HAL::OTA_GetBcbState();
    g_ota_state_snapped = true;
    return g_ota_state_snapshot;
}
```

而喂狗**只在 `state == BCB_STATE_TEST_BOOT` 分支内**发生：

```c
if(state == BCB_STATE_TEST_BOOT)
{
    HAL::OTA_WatchdogFeed();                 // 唯一喂狗点
    ota_confirm_health_feed(&g_ota_health);
    if(g_ota_confirm_done) { return; }       // 注释称“继续喂狗直至重启”
    ...
    g_ota_confirm_done = HAL::OTA_ConfirmBoot();
    if(g_ota_confirm_done && g_ota_state_snapshot == BCB_STATE_TEST_BOOT)
    {
        g_ota_state_snapshot = BCB_STATE_CONFIRMED;   // ← 自我否定
    }
    return;
}
```

确认成功的**同一圈**就把快照改写为 `CONFIRMED`。下一圈 `OTA_SnapshotState()`
返回 `CONFIRMED`，`state == BCB_STATE_TEST_BOOT` 恒为假 → **喂狗分支再也不进入**。
因此 `if(g_ota_confirm_done) { return; }` 这行「确认后继续喂狗」的代码
**在任何执行路径下都不可达**，其注释描述的行为没有实现。

**为何会真的复位**：
- boot 仅在 `TEST_BOOT` 交接前起动独立看门狗
  （`boot/src/boot_main.c:199-205` → `boot_platform_watchdog_start()`，
  `boot/platform/at32/boot_platform_at32.c:802-809`：`wdt_divider_set(WDT_CLK_DIV_256)`、
  `wdt_reload_value_set(1561)`、`wdt_enable()`）。
- AT32 IWDG 一经 `wdt_enable()` 只能由复位清除，App 侧无法关闭。
- 超时 = 1561 × 256 ÷ 40 kHz(LICK) ≈ **9990 ms**。
- 全仓 App 侧喂狗点仅 `USER/main.cpp:66` 一处（已检索确认），无其他路径兜底。

**独立探针复现**（把 `main.cpp` 控制流逐行照抄，仅将 `HAL::` 换成计数器，
链接真实 `Libraries/OTA/ota_confirm_health.c`）：

源码：`docs/ota-exec-notes/P2-5-acceptance-feed-probe.c`

```
gcc -std=c99 -Wall -Wextra -O2 -ILibraries -Iboot/include \
    docs/ota-exec-notes/P2-5-acceptance-feed-probe.c \
    Libraries/OTA/ota_confirm_health.c -o .cache/feed_probe.exe
```

输出（模拟 TEST_BOOT 下 10 ms/圈跑 90 s）：

```
WDT_TIMEOUT_MS=9990
confirmed_at_ms=30000
feeds_total=3000 feeds_at_confirm=3000
feeds_after_confirm=0
last_feed_ms=30000 run_end_ms=90000
silence_after_last_feed_ms=60000
FAIL: no watchdog feed after confirm -> IWDG resets at ~39990ms
FAIL: feed silence 60000ms >= WDT timeout 9990ms
P2_5_FEED_PROBE=FAIL failures=2
```

即：30 s 处确认成功，此后喂狗次数 **0**，约 **39990 ms**（确认后 ~10 s）被 IWDG 复位。

**后果**：BCB 此时已是 `CONFIRMED`，复位后 boot 正常跳 App 且不再起看门狗，
**不会变砖、不会回滚**；但每轮 OTA 升级后的首个启动必然出现一次
**非预期整机复位（约开机 40 s 处）**。若复位时正在写 SD/轨迹，存在数据损失风险；
且直接违反本卡验收条件"TEST_BOOT 真机运行超过一个 WDT 超时周期无 WDT reset"。

**为何宿主测试没抓到**：`test_ota_confirm_health.c` 的 C12 只对
`ota_confirm_health_*` 直接调用 `feed()` 并断言 `feed_count` 增长
（`tests/ota/test_ota_confirm_health.c:147-172`），**从未经过 `OTA_ConfirmUpdate()`
的快照改写逻辑**。缺陷恰好落在被测单元与 `main.cpp` 编排之间的接缝上。
C12 的注释"健康门本身不持有确认完成状态"承认了这一点，但该卡的阻断 2 要求的是
编排层行为，单元级断言不构成关闭证据。

**建议修法**（择一，勿在测试里绕过）：
1. 确认成功后**不改写快照**，改用独立的 `g_ota_confirm_done` 控制"是否再发起确认"，
   喂狗继续由 `state == TEST_BOOT` 驱动；或
2. 把喂狗提到状态判断之外：只要 `HAL::OTA_WatchdogIsConfigured()` 为真就每圈喂狗
   （语义最直白，且与"WDT 只能复位清除"的物理事实对齐）。

无论哪种，都必须补一条**跨 `OTA_ConfirmUpdate()` 编排**的回归
（可直接复用本报告的探针判据：确认后一个 WDT 周期内喂狗次数必须 > 0）。

---

## 3. 已确认关闭的 10 项

| # | 阻断 | 独立核验结论 |
|---|---|---|
| 1 | 健康门编排 | ✅ `main.cpp:191-197` init 先于 `setup()`，`mark_hal_ready` 在 `setup()` 末尾（`main.cpp:162`）；C10/C11 锁死正反序 |
| 3 | 前置 BCB 仲裁 | ✅ `RequireConfirmedBcb()` 在 `Begin`(`OtaUpdate.cpp:362`)/`Apply`(`:446`)/`Stage`(`:557`) 摆动作前；`BEGIN_NON_CONFIRMED begin=busy opens=5` 零擦写 |
| 4 | Stage 绑定 candidate | ✅ `candidateReady`+vcode/len/sha8 三元；`Inspect`/`Begin`/`Close`/`Step` 失败均 `InvalidateCandidate()`；`STAGE_BEFORE_APPLY=candidate_not_applied` |
| 5 | marker-last 重试 | ✅ `ota_backup.c:528` 提交前重擦 candidate 槽头；`commit_slot_header` 28B 字段 + 4B marker 两次独立 program；T4 断言 marker 后无写、半写 marker 保持擦除态 |
| 6 | BCB 提交三元语义 | ✅ `classify_commit()` 提交后**重新仲裁**分类 STAGED/CONFIRMED/UNKNOWN，`ERR_COMMIT_AMBIGUOUS` 上抛 `OTA_SD_ERR_COMMIT_UNKNOWN` 禁覆盖；T6 覆盖 |
| 7 | STAGED 双槽复核 | ✅ `verify_slot_final()` 含 ETSL 字段 + 全镜像 CRC + `slot_fw_header_matches()` 全项 + `require_newer_than` 降级拒绝；另有 `cur_vcode` vs App header 核对（`:385`） |
| 8 | 失败输出/program_count | ✅ `program_verify()` flash 写成功即 `(*program_count)++`（读回失败也计）；各失败分支 return 前均 `*out = info` |
| 9 | result_name/注释 | ✅ 补 `staged_commit`/`busy`/`commit_unknown` 三条映射；`ota_sd.h:48` 注释已改为"含 BCB 提交" |
| 10 | 测试加固 | ✅ T1-T10 + C0-C12 + Session 7 场景；**但对阻断 2 的覆盖无效，见 F1** |
| 11 | EOL | ✅ `git diff --check` 无输出 |

---

## 4. 未执行项（不构成本次打回理由）

真机环节本次**未执行**（J-Link 烧录/RTT）：因 F1 属编排层确定性缺陷，
真机复现只会得到"确认后约 10 s 复位"，先修再测更经济，避免无谓刷写。
待 F1 整改后，真机验收仍须覆盖：

- STAGED→重启→APPLYING→TEST_BOOT→CONFIRMED 全链 RTT 留痕；
- TEST_BOOT 运行**超过一个 WDT 超时周期（≥10 s）**且确认后继续运行 ≥30 s 无复位；
- TEST_BOOT 期间发起 OTA 被拒且零副作用。

真机操作须遵守 AGENTS.md J-Link 防坑清单（重查 map → 验 `SEGGER RTT` 签名 →
读 down descriptor → 单 logger）。

---

## 5. 验收结论

- **判定：不通过（打回）**，阻断项 1 条（F1）。
- P2-5 卡保持 `进行中`，P2 进度保持 `4/6`。
- 实现质量总体高：11 项中 10 项关闭扎实，双槽复核与三元提交语义的设计正确且
  测试覆盖到位，构建与边界纪律无瑕疵。F1 是单一编排缺陷，修复面很小
  （`main.cpp` 数行），但因其证伪卡内验收硬条件，不能放行。
- 本会话未修改任何实现文件，未 commit/push；新增文件仅
  `docs/ota-exec-notes/P2-5-acceptance-2026-08-03.md`（本报告）与
  `docs/ota-exec-notes/P2-5-acceptance-feed-probe.c`（可复现探针）。
