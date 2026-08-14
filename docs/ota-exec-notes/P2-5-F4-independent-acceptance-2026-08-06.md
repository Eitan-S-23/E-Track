# P2-5 F4 整改后独立验收报告（2026-08-06）

## 1. 结论

**不通过。P2-5 保持“阻塞”，P2 总进度保持 4/6。**

本轮在验收前强制快照阶段即命中生产清理硬失败：

```text
git diff --check
EXIT_CODE=2
```

输出包含 `MDK-ARM_F435/RTE/_X-Track-App-AC5/RTE_Components.h` 3 处尾随空白，
以及 `PLAN-OTA-EXEC.md` 9 处尾随空白。用户指令明确规定本节任一不满足即直接
判定不通过，并要求发现实现缺陷后停止扩展验证。因此本会话没有继续执行宿主回归、
fresh 构建、模拟器 fixture、烧录、RTT 或 SD OTA。

同时，项目内现有旧升级包也不具备本轮闭环资格：其已解包 candidate 为
`598680 B` / SHA-256
`4A329C374FB91AA68567CAE1485BF9B42FF32ED5CE3B22E5F848E04C4526A375`，
最终清理后的 finalized App 为 `598760 B` / SHA-256
`0FAB063BAB058370F36C5FAD0E1AF84AA08FF47B4B78602A992ABAECB6482EED`，
两者不一致。

## 2. 身份与边界

- 会话性质：非实现会话，独立验收。
- 活动 worktree：`D:\github\my\E-Track-p2-5-20260801`。
- HEAD：`0023e5ff0af054438cbb2ed9e5bc99ae0e9b5c7e`。
- F4 实现前基线：`0023e5f`，与当前 HEAD 相同；实现均为未提交工作树改动。
- 未修改任何实现代码。
- 未执行 commit、push、merge、rebase 或 stash。
- 本会话主动写入仅限本报告、`PLAN-OTA-EXEC.md` 验收留痕和
  `.acceptance-p2-5-f4/20260806-230519/` 证据目录。

## 3. 验收前快照

原始快照：
`.acceptance-p2-5-f4/20260806-230519/00-preflight-snapshot.txt`。

### 3.1 命令与退出码

| 命令 | 退出码 | 关键结果 |
|---|---:|---|
| `git rev-parse --show-toplevel` | 0 | `D:/github/my/E-Track-p2-5-20260801` |
| `git rev-parse HEAD` | 0 | `0023e5ff0af054438cbb2ed9e5bc99ae0e9b5c7e` |
| `git status --short --branch` | 0 | 6 个 tracked 修改、9 个 untracked 文件 |
| `git diff --stat 0023e5f` | 0 | 6 files, 84 insertions, 28 deletions |
| `git diff --name-status 0023e5f` | 0 | 6 个 tracked 修改文件 |
| `git diff --check` | **2** | 12 个 trailing-whitespace 报告 |

### 3.2 完整改动清单

Tracked 修改：

1. `MDK-ARM_F435/RTE/_X-Track-App-AC5/RTE_Components.h`
2. `MDK-ARM_F435/cmake-generated/compile_commands.json`
3. `PLAN-OTA-EXEC.md`
4. `Simulator/LVGL.Simulator/lv_fs_if/lv_fs_pc.c`
5. `USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp`
6. `USER/App/Pages/FirmwareUpdate/FirmwareUpdate.h`

验收开始前 untracked：

1. `.claude/prompt-F4-fix-implementation.md`
2. `.claude/prompt-F4-remediation.md`
3. `.claude/prompt-P2-5-verification.md`
4. `docs/ota-exec-notes/P2-5-F4-fix-2026-08-05.md`
5. `docs/ota-exec-notes/P2-5-F4-fix-remediation-2026-08-06.md`
6. `docs/ota-exec-notes/P2-5-F4-review-2026-08-06.md`
7. `docs/ota-exec-notes/P2-5-hardware-verification-2026-08-05.md`
8. `flash-app.jlink`
9. `flash-probe.jlink`

实现证据对 tracked 文件的申报与现状相符：两个 FirmwareUpdate 文件和看板为主动
改动，`lv_fs_pc.c` 为 BOM 清理，RTE 文件和 `compile_commands.json` 为预存或生成
改动。工作树并不干净，生成文件状态已如实列出。

## 4. 生产清理复核

完整静态审计：`.acceptance-p2-5-f4/20260806-230519/01-static-audit.md`。

| 条件 | 结果 | 证据 |
|---|---|---|
| `USER/App/App.cpp` 恢复 `Pages/Startup` | 通过 | 行 178 |
| `lv_fs_pc.c` 恢复生产路径 | 通过 | `LV_FS_PC_PATH "."`，当前 diff 仅去 BOM |
| 无 F4PROBE/临时 RTT 计时/测量宏 | 通过 | 生产目录精确 `rg` 无命中 |
| 无临时页面直达或验收编译开关 | 通过（静态） | `App.cpp` 相对基线无 diff |
| 三个指定文件 UTF-8 无 BOM | 通过 | 首三字节分别 `23 69 6E`、`23 69 66`、`23 20 50` |
| `USER/main.cpp` F1 修复未变 | 通过 | 相对 `0023e5f` 无 diff |
| 看门狗未关闭、未调大 | 通过 | enable=`1`，timeout=`10 * 1000` ms |
| 冻结契约和 `boot/` 未被 F4 修改 | 通过 | 相关路径无 diff |
| F4 新源码 include 使用正斜杠规则 | 通过 | 新 include 为本地 `wdg.h` |
| `git diff --check` 无错误 | **失败** | rc=`2`，12 项尾随空白 |

精确复现：

```powershell
Set-Location 'D:\github\my\E-Track-p2-5-20260801'
git diff --check
```

关键失败位置：

```text
MDK-ARM_F435/RTE/_X-Track-App-AC5/RTE_Components.h:5
MDK-ARM_F435/RTE/_X-Track-App-AC5/RTE_Components.h:6
MDK-ARM_F435/RTE/_X-Track-App-AC5/RTE_Components.h:14
PLAN-OTA-EXEC.md:505
PLAN-OTA-EXEC.md:512-514
PLAN-OTA-EXEC.md:717-721
```

## 5. F4 专项静态复核与量化复算

### 5.1 静态结论

当前实现的结构与整改目标一致：每个成功返回的目录项在任何过滤前递增
`scanCount`；`ROW_MAX` 和 `SCAN_MAX` 均有独立上限；命中上限后额外读取一次真实
probe，恰好读完不误报；`moreEntries` 优先于 `TXT_EMPTY`；`deviceReady==false`
最后覆盖消息，保持最高优先级。

这只是静态结论。由于 fail-fast，本会话没有构造 fixture 或操作真机，不能把它
记作用户要求的 10 个 F4 场景的独立动态证明。

### 5.2 原始量化证据核验

实现会话原始 RTT 日志的 SHA-256 与其报告一致：

| 文件 | SHA-256 |
|---|---|
| `run-20260806-191731/unlock-final-reset-rtt.log` | `899FCC880C13539179F07BA494D5302EF95F33C8884C387DE2CFF31A0717613E` |
| `run-20260806-200611/unlock-final-reset-rtt.log` | `5D3BC25C5A52FA159B935EA855276E63C954AA378DBA5F346F7CD8CA42D01358` |
| `run-20260806-202255/unlock-final-reset-rtt.log` | `25C6A551B2C8BF56E88F71E5379A884F0D70E8457F859095F5DB4A0ECEA0506E` |
| 历史 F4 blocker | `D6A54CAEDF46800626ECAF60211533F5884AF264DC5D9DADE76DE2C6D29BE926` |

独立复算：

| 量 | 结果 |
|---|---:|
| 当前 SD 根目录实际条目 | 8（1 ETU、4 目录） |
| 根目录单次读取平均/最坏 | 136 us / 378 us |
| 已测最大目录 | `/MAP/16/51857`，96 项 |
| 最大目录平均/最坏 | 29 us / 313 us |
| 修复后根目录 `LoadFiles()` | 44.941 ms |
| 修复前原 F4 目录总耗时 | 精确值不可恢复，仅有 WDT 证明的 `>10 s` 下界 |
| 32 项喂狗间隔 | `32 * 380 us = 12.16 ms` |
| 相对 10000 ms IWDG 裕度 | `822.368x` |
| 257 次读取最坏估计 | 97.66 ms |
| 24 行 UI 成本外推 | 209.8368 ms |
| 合计保守最坏估计 | 307.4968 ms |
| 整次加载相对 IWDG 裕度 | `32.521x` |

实现证据预先声明的 UI 阈值为 `<0.32 s`，上述算术可以复现。原 F4 根目录条目数
与修复前同目录总耗时仍不可恢复，本轮没有用当前 8 项目录冒充原始数据。

## 6. 构建产物与升级包

以下是验收开始时已存在的实现会话产物，仅记录元数据，**不是本会话 fresh 构建
结果**：

| 产物 | 大小 | 时间戳 | SHA-256 |
|---|---:|---|---|
| GCC App raw bin | 598760 B | 2026-08-06T22:01:46.3006301+08:00 | `57D33C3A1608132DC020334F9469E75318940C3A4EF4C966CA119283586847C1` |
| GCC App ELF | 860056 B | 2026-08-06T22:01:46.1073149+08:00 | `9B6B67E1990DD75E3C20C571579E14A1D15A503652613E307523763BF2FD1E5E` |
| GCC App map | 2233053 B | 2026-08-06T22:01:46.1151256+08:00 | `A9B1454D4A1D981640DD5BA3A486C6561FEB76175F7561A27668C88122D90B3F` |
| GCC Boot bin | 14724 B | 2026-08-05T23:24:37.2806521+08:00 | `5842FF3E19BA9E1EAAEA10F27E825C7B6EFC278B200531014B0DBA61264F6594` |
| GCC Boot ELF | 36860 B | 2026-08-05T23:24:36.2776539+08:00 | `D21713CA2C1EFEAC949F8EC0FFDDACAC439FED6BF26F9C65641BEE24464FDABC` |
| finalized App | 598760 B | 2026-08-06T21:17:56.3664765+08:00 | `0FAB063BAB058370F36C5FAD0E1AF84AA08FF47B4B78602A992ABAECB6482EED` |
| 旧 `P2-5-FULL.etu` | 281042 B | 2026-08-04T17:37:55.2365410+08:00 | `9142837D527E99FF92814265DDD470853D99A2320EEAF546ADE11A1AF44635ED` |
| 旧包已解包 candidate | 598680 B | 2026-08-05T19:31:25.0513500+08:00 | `4A329C374FB91AA68567CAE1485BF9B42FF32ED5CE3B22E5F848E04C4526A375` |

Boot 现有 bin 小于 64 KiB，但本会话没有 fresh 重建，也没有独立复核三个 LOAD
segment 的 RWX 属性。旧包 candidate 与 finalized App 大小和哈希均不一致，
逐字节一致性条件明确失败；未生成新的 target_vcode 大于基线的生产 `.etu`。

## 7. RTT 与真机

当前已有 GCC map 中 `_SEGGER_RTT` 文本符号地址为 `0x20045E34`，但本会话没有
烧录或连接设备，也没有执行 `mem8 <addr> 16`，因此没有新的 RTT 签名证据，且没有
沿用旧地址得出任何硬件结论。

未执行：

- 真机 F4 文件管理页操作与 UI 耗时。
- `Reset: NRST WDT` 负向检查。
- `.etu` 可见、选择和二次确认。
- STAGED → APPLYING → TEST_BOOT → CONFIRMED。
- 90 秒 TEST_BOOT RTT 采集。
- 第二次普通复位后 `BCB already CONFIRMED`。
- TEST_BOOT 期间新 OTA 门禁。

原因均为本报告 §4 的清理硬失败触发 fail-fast；此外现有 `.etu` 与最终 App 不一致，
即使继续也不具备有效闭环前提。

## 8. 验收矩阵

| 验收项 | 结果 |
|---|---|
| F4 两个阻断和四个整改项全部独立关闭 | 未完成动态证明 |
| 临时插桩、页面直达、测试路径清理 | 静态通过 |
| F4 边界无静默截断、无 WDT、无不可接受冻结 | 未执行动态验收 |
| 全部宿主回归无回退 | 未执行 |
| fresh GCC App/Boot | 未执行 |
| AC5 正式尝试 | 未执行 |
| 模拟器重建与连续两次 Startup | 未执行 |
| `git diff --check` | **失败** |
| 最终 `.etu` candidate 等于最终 F4 App | **失败** |
| 真机完整 OTA 闭环 | 未执行 |
| TEST_BOOT 新 OTA 门禁 | 未执行 |

任一失败均足以阻断 P2-5；本轮已有两个明确失败项。

## 9. 回写与证据

- P2-5 状态保持 `阻塞`。
- P2 总进度保持 `4/6`。
- 已在 P2-5 卡内追加本轮阻塞记录。
- 已在 `PLAN-OTA-EXEC.md` §10 增加本轮会话日志。
- 原始证据目录：`.acceptance-p2-5-f4/20260806-230519/`。
- 未执行 commit、push 或 merge。

报告生成时间：2026-08-06 23:15:22 +08:00。
