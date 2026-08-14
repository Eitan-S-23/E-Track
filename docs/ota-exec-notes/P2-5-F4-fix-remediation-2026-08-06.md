# P2-5 F4 第二轮整改实现证据（2026-08-06，2026-08-07 补充）

> 2026-08-07 补充更正：第五轮独立验收证明最终同源 v20800 App 仍会在点击
> “文件管理”后以 `Reset: NRST WDT` 重启，且交付固件仍编入 RTT 下行调试命令。
> 后续实现会话已定位真实根因为 MainMenu 与 FirmwareUpdate 同时驻留导致 LVGL
> heap 耗尽：先发生 HardFault，主循环停止喂狗后才表现为 WDT reset。本文第 1-7
> 节保留扫描边界、量化和历史证据，第 8 节是 2026-08-06 阶段性结论；当前实现结论
> 以新增第 9 节为准。

## 0. 会话结论与边界

- 工作树：`D:\github\my\E-Track-p2-5-20260801`
- 分支：`p2-5-20260801`
- HEAD：`0023e5ff0af054438cbb2ed9e5bc99ae0e9b5c7e`
- 会话性质：实现会话，不执行验收签字，不 commit/push/merge。
- 整改依据：`.claude/prompt-F4-remediation.md`。

| 整改项 | 本轮结论 |
|---|---|
| §1 截断提示 | 已整改并用模拟器 301 条目录目视复核 |
| §2 强制量化 | 完成当前 SD 根目录和卡上最大目录实测；原 F4 触发根目录已不存在，精确条目数与修复前同目录总耗时不可恢复，因此不得声明本项完整通过 |
| §3.1 `SCAN_MAX` | 依据实测保留 `256`；观测上界下同步加载保守估计 `<0.32 s`，不支持升级异步加载 |
| §3.2 文案 | 已改为纯 ASCII `MORE FILES EXIST, NOT ALL SHOWN` |
| §3.3 BOM | 三个指定文件均为无 BOM |
| §3.4 申报 | 最终 tracked/untracked 与预存改动逐项申报 |

本轮关闭静态缺陷、完成可获得的真机量化、清理插桩并回刷生产 App，但没有执行
P2-5 完整 SD 升级链。因此 P2-5 不置完成，仍须非实现会话按
`.claude/prompt-P2-5-verification.md` 重新验收。

2026-08-07 的独立验收随后证伪了“仅靠扫描上界即可关闭真机入口故障”的阶段性判断。
扫描整改本身仍正确，但 WDT 是 HardFault 后的次生现象；正式补救、生产验证和剩余
阻塞见第 9 节。

## 1. 对应整改提示词 §1：截断提示

### 1.1 最终实现

`USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp` 的最终逻辑：

- `scanCount` 与 `rowCount` 分离，所有 `lv_fs_dir_read()` 返回条目均消耗
  `SCAN_MAX`，隐藏项和非 `.etu` 文件也计数。
- 循环条件同时受 `ROW_MAX=24` 和 `SCAN_MAX=256` 限制。
- 任一上限命中后额外读取一次 `probe`；只有读到真实后续条目才设置
  `moreEntries=true`，恰好读完不误报。
- `moreEntries` 分支先于 `TXT_EMPTY`，覆盖 `rowCount==0` 和只有返回上级行的场景。
- `deviceReady==false` 的 `TXT_FILE_INVALID` 保持最后写入，仍是最高优先级。

关键位置：

```text
FirmwareUpdate.cpp:575 while (rowCount < ROW_MAX && scanCount < SCAN_MAX)
FirmwareUpdate.cpp:581 ++scanCount
FirmwareUpdate.cpp:609 bool moreEntries = false
FirmwareUpdate.cpp:610 if (rowCount >= ROW_MAX || scanCount >= SCAN_MAX)
FirmwareUpdate.cpp:625 SetBrowserMessage(TXT_SCAN_LIMIT, "")
FirmwareUpdate.cpp:636 if (!deviceReady)
FirmwareUpdate.h:26 ROW_MAX = 24
FirmwareUpdate.h:27 SCAN_MAX = 256
```

### 1.2 模拟器截断目视

临时测试目录含 `300` 个 `.txt` 和 `test.etu`，共 `301` 项。模拟器直入
`Pages/FirmwareUpdate` 仅用于截图，最终已恢复 `Pages/Startup`；PC 文件系统路径也已
恢复 `LV_FS_PC_PATH "."`。

- 早期截图 `.cache/sim-trunc2.png` 经目视仅显示“无法打开目录 / LV_FS_DIR”，
  不构成截断提示证据，已由下述最终截图替代。
- 截图：`.cache/sim-trunc-final.png`
- 大小/时间：`4914 B`，`2026-08-06T20:46:10.7969682+08:00`
- SHA-256：`29861435E81FCD6CCB3EEA367302CE55A63C3E23D295F788C54AFFACEADC52B6`
- 目视结果：文件管理页底部显示 `MORE FILES EXIST, NOT ALL SHOWN`，没有显示
  `TXT_EMPTY`。
- 清理结果：模拟器 exe 目录删除 `301` 个临时文件，`.cache/sim-test-dir` 删除
  `301` 个源文件，最终两处残留均为 `0`。

## 2. 对应整改提示词 §2：GCC 真机量化

### 2.1 必须如实保留的缺口

2026-08-05 的 F4 独立验收只留下 `Reset: NRST WDT`，证明旧同步扫描路径耗时
`>10 s`；当时没有目录条目清单或计时插桩。第二轮量化时，SD 根目录内容已经变化，
原触发 F4 的大目录不再存在。

- 历史阻塞证据：`.cache/p2-5-verification/blocker-filemanager-wdt-reset.md`
- SHA-256：`D6A54CAEDF46800626ECAF60211533F5884AF264DC5D9DADE76DE2C6D29BE926`
- 当前根目录实测只有 `8` 项，不能反推或冒充原 F4 根目录条目数。
- 原 F4 根目录精确条目数：**不可恢复**。
- 修复前版本在原 F4 根目录的完整 `LoadFiles()` 总耗时：**不可恢复**，仅有
  `>10 s` 的 WDT 下界。

因此整改提示词 §2.3 中“触发 F4 的那个目录实际条目数”和“修复前同目录总耗时”
没有完整实测值。本报告不将当前目录或线性推算写成这两项的替代通过证据。

### 2.2 当前 SD 的实测数据

所有计时字段单位为微秒。临时固件直接用 `SEGGER_RTT_printf` 输出，采集前清理
`JLinkRTTLogger/JLinkGUIServer`，每次链接后从 GCC map 重查 RTT 地址并验证
`SEGGER RTT` 签名。

当前根目录证据：

```text
F4PROBE: path=/ entries=8 etu=1 dir=4 scanCount=8 more=0
         read_calls=9 read_avg_us=136 read_max_us=378
         read_total_us=1225 total_us=44941
F4FULL:  path=/ open=1 entries=8 etu=1 dir=4 hidden=2 other=1
         read_calls=9 read_avg_us=105 read_max_us=378
         read_total_us=947 total_us=1103
```

- 日志：`.cache/p1-7-unlock/run-20260806-191731/unlock-final-reset-rtt.log`
- SHA-256：`899FCC880C13539179F07BA494D5302EF95F33C8884C387DE2CFF31A0717613E`
- 当前修复版实际 `LoadFiles()`：`44.941 ms`，其中目录读取 `1.225 ms`；其余主要是
  5 行 UI 创建和页面更新。

卡上层级/文件数最大的已遍历目录：

```text
F4PATHMAX:   path=/MAP/16 entries=74 read_calls=75
             read_avg_us=29 read_max_us=304 total_us=2770
F4PATHFIXED: path=/MAP/16 entries=74 more=0 read_calls=75
             read_avg_us=27 read_max_us=215 total_us=2696

F4METRIC: p=/MAP/16/51857 n=96 full=4157 ra=29 rm=313 rt=2827
          fixed=4153 more=0 fa=29 fm=311 ft=2834
```

- 目录发现日志：`.cache/p1-7-unlock/run-20260806-200611/unlock-final-reset-rtt.log`
- SHA-256：`5D3BC25C5A52FA159B935EA855276E63C954AA378DBA5F346F7CD8CA42D01358`
- 最终紧凑日志：`.cache/p1-7-unlock/run-20260806-202255/unlock-final-reset-rtt.log`
- SHA-256：`25C6A551B2C8BF56E88F71E5379A884F0D70E8457F859095F5DB4A0ECEA0506E`
- `/MAP/16/51857` 完整遍历 `4.157 ms`，修复路径 `4.153 ms`，平均
  `29 us/read`，最坏 `313 us/read`。
- 全部采样的单次读取最坏值为根目录的 `378 us`；计算时向上取整为 `380 us`。

### 2.3 IWDG 裕度与 `SCAN_MAX` 推导

1. 每 32 个条目喂狗的观测上界：`32 * 380 us = 12.16 ms`。
2. 相对 `10000 ms` IWDG：`10000 / 12.16 = 822.37`，约 `822x` 裕度。
3. `SCAN_MAX=256` 加一次 probe 共 257 次读取：`257 * 380 us = 97.66 ms`。
4. 当前根目录 5 个可见行的非读取成本：`44.941 - 1.225 = 43.716 ms`。
5. 按该较慢样本线性放大到 24 行：`43.716 / 5 * 24 = 209.84 ms`。
6. 读取上界与 UI 成本合计：`97.66 + 209.84 = 307.50 ms`，保守记为
   `<0.32 s`。
7. 相对 `10000 ms` IWDG 的整次加载裕度保守约 `31x` 以上。

以上是基于已观测最坏单次读和较慢 UI 样本的保守外推，不是原 F4 大目录的直接实测。
现有数据表明 `SCAN_MAX=256` 的同步扫描本身处于亚秒量级，喂狗只是兜底而非避免
十几秒冻结的唯一手段。因此保留 `SCAN_MAX=256`，当前证据不支持升级到分帧/异步加载。

### 2.4 插桩清理与生产回刷

临时 `Arduino.h`、`SEGGER_RTT.h`、`__f4_*` 和 `F4PROBE/F4FULL/F4METRIC` 输出已从
`FirmwareUpdate.cpp` 删除。最终源码和 ELF 搜索结果：

```text
ELF_TEMP_MARKERS=0
LOADFILES_WDG_CALLS=1
8044fa4: bl 8018520 <WDG_ReloadCounter>
```

最终 GCC Release：

```powershell
cmake --build MDK-ARM_F435\cmake-generated\build-gcc-release --parallel
```

- build exit：`0`
- 既有 warning 行：`389`；`error:` 行：`0`
- App bin：`598760 B`，`2026-08-06T22:01:46.3006301+08:00`
- bin SHA-256：`57D33C3A1608132DC020334F9469E75318940C3A4EF4C966CA119283586847C1`
- ELF：`860056 B`，SHA-256
  `9B6B67E1990DD75E3C20C571579E14A1D15A503652613E307523763BF2FD1E5E`
- map：`2233053 B`，SHA-256
  `A9B1454D4A1D981640DD5BA3A486C6561FEB76175F7561A27668C88122D90B3F`
- build log：`.cache/p2-5-final/gcc-release-build.log`，SHA-256
  `FB6E77753D0A409A621DE255FD6632461617C8960161F89B4CFAA52D935939D6`

finalize/verify：

```powershell
python Tools\etu_pack.py finalize --app .cache\p2-5-final\X-Track-App-GCC-clean.finalized.bin --ver-name 2.8.0 --build-ts 1786022274
python Tools\jlink\prepare-bootstrap-app.py verify --input .cache\p2-5-final\X-Track-App-GCC-clean.finalized.bin --input-kind app
```

```text
image_len=598760 vcode=20800
image_sha256=0fab063bab058370f36c5fad0e1af84aa08ff47b4b78602a992abaecb6482eed
header_crc32=97377435
P1_5_APP_VERIFY=PASS kind=app len=598760 vcode=20800
```

finalized bin SHA-256：
`0FAB063BAB058370F36C5FAD0E1AF84AA08FF47B4B78602A992ABAECB6482EED`。
最终 EOL 归一化后重建的 raw bin SHA 仍为 `57D33C...847C1`，与该 finalized 文件的
源 raw bin 相同，因此生产回刷与最终源码产物一一对应。

回刷使用仓库 `Invoke-P1FlashApp`。前两次连接在 `InitTarget()` 处报
`Failed to initialized DAP`，均未执行 `loadbin`；间隔后第三次同参数
`AT32F435RGT7/SWD/1000` 成功：

```text
P1_5_APP_FLASH_VERIFY=PASS app=0x08010000 trailer_written=0
P2_5_F4_CLEAN_RESET=PASS pc=0x08029D20 vtor=0x08010000 cfsr=0x00000000
P2_5_F4_CLEAN_RTT=PASS address=0x20045E34 handoff=1 confirmed=20800 temp_markers=0
```

- summary：`.cache/p2-5-final/flash-clean-final/flash-clean-summary.log`
- summary SHA-256：`09F2146AA4EF4C016498411D8C61590562A98D8B2F52CCE9E6127619B393AD78`
- clean RTT：`.cache/p2-5-final/flash-clean-final/clean-rtt.log`
- clean RTT SHA-256：`A266CBF3756F12F49D8D5B63037298E62E7AD928AD960B4D1FE33AC15BB81FB8`
- 最终设备：`HANDOFF`、`BCB already CONFIRMED vcode=20800`，无 F4 临时标记。

## 3. 对应整改提示词 §3.1：`SCAN_MAX` 取值

最终决定：保留 `SCAN_MAX=256` 和每 32 项喂狗。

- 已测最大目录 96 项的修复路径只有 `4.153 ms`。
- 使用全局观测最坏 `380 us/read` 外推，257 次读取约 `97.66 ms`。
- 加入较慢 UI 样本的 24 行成本后仍 `<0.32 s`，不是依靠喂狗维持十几秒阻塞。
- 降低 `SCAN_MAX` 会增加 `.etu` 位于大目录后部时的漏列概率；当前时延数据没有迫使
  降低上限。
- 若独立复验在另一张 SD 上测得显著更高的 `dir_read` 延迟，应重新套用本节公式；若
  “可接受时延”和“扫描任意位置 `.etu`”冲突，再升级异步加载。

## 4. 对应整改提示词 §3.2：提示文案

最终宏：

```c
#define TXT_SCAN_LIMIT "MORE FILES EXIST, NOT ALL SHOWN"
```

文案不再混淆 `ROW_MAX=24` 和 `SCAN_MAX=256`，语义是仍有文件未显示；保持纯 ASCII，
不依赖 `cn_16` 字体子集。

## 5. 对应整改提示词 §3.3：BOM

最终头三字节：

| 文件 | 头三字节 | BOM |
|---|---|---|
| `USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp` | `23 69 6E` | 否 |
| `USER/App/Pages/FirmwareUpdate/FirmwareUpdate.h` | `23 69 66` | 否 |
| `PLAN-OTA-EXEC.md` | `23 20 50` | 否 |

`FirmwareUpdate.cpp/.h`、`PLAN-OTA-EXEC.md` 最终均无 UTF-8 BOM。另将本轮触碰的
`FirmwareUpdate.cpp`、`lv_fs_pc.c` 和临时入口恢复后的 `App.cpp` 收敛为统一 CRLF，
避免 mixed EOL 状态。

## 6. 对应整改提示词 §3.4：改动申报

最终主动功能改动：

| 文件 | 说明 |
|---|---|
| `USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp` | 独立扫描上界、周期喂狗、真实 probe 截断判断、消息优先级、ASCII 提示 |
| `USER/App/Pages/FirmwareUpdate/FirmwareUpdate.h` | `SCAN_MAX=256` |
| `PLAN-OTA-EXEC.md` | 第一轮记录及本轮状态/会话日志回写 |
| `docs/ota-exec-notes/P2-5-F4-fix-remediation-2026-08-06.md` | 本证据 |

临时改动的最终状态：

| 文件/目录 | 最终状态 |
|---|---|
| `USER/App/App.cpp` | `Pages/FirmwareUpdate` 已恢复为 `Pages/Startup`，filtered hash 与 HEAD 相同，最终无 diff |
| `Simulator/LVGL.Simulator/lv_fs_if/lv_fs_pc.c` | `LV_FS_PC_PATH` 已恢复 `"."`；当前仅 BOM 去除 diff |
| `.cache/sim-test-dir` | 已删除 |
| `Simulator/Output/Debug/x64/file*.txt`、`test.etu` | 已删除，残留 0 |
| FirmwareUpdate RTT 插桩 | 已删除，源码/ELF临时标记 0 |

会话开始前已存在、未回退的改动：

| 文件 | 申报 |
|---|---|
| `MDK-ARM_F435/RTE/_X-Track-App-AC5/RTE_Components.h` | worktree 预存修改，本轮未主动编辑 |
| `MDK-ARM_F435/cmake-generated/compile_commands.json` | CMake 生成副产物，开始时已为 M；最终 Ninja 规则按工程定义再次 copy，未手工编辑 |
| `.claude/prompt-F4-fix-implementation.md`、`.claude/prompt-F4-remediation.md`、`.claude/prompt-P2-5-verification.md` | 会话开始前 untracked |
| 三份既有 P2-5 报告、`flash-app.jlink`、`flash-probe.jlink` | 会话开始前 untracked，未篡改验收结论 |

未改：`USER/main.cpp`、`HAL_Config.h`、`lv_conf.h`、`boot/`、冻结契约、既有验收报告、
F4 阻塞证据。

## 7. 最终验证

### 7.1 宿主全量

```powershell
python tests\ota\test_ota_backup.py
python tests\ota\test_ota_package.py
python tests\ota\test_ota_patch.py
python tests\ota\test_ota_sd.py
python tests\ota\test_ota_update.py
python tests\ota\test_ota_staging.py
python tests\boot\test_boot_state_machine.py
python tests\boot\test_fw_header_vectors.py
python tests\ota-vectors\test_vectors.py
```

| 项 | 结果 |
|---|---|
| backup | `108/108` |
| confirm health | `17/17` |
| P2-2 | `102` |
| P2-3 | `167/167` |
| P2-4 | core `29` + adapter `5` + update scenarios `7` |
| P2-1 | `48/0` |
| P1-3 | `96/0` |
| P1-1 | `16` |
| vectors | `Ran 9 tests ... OK` |

- summary：`.cache/p2-5-final/host-tests/host-tests-summary.log`
- SHA-256：`B3C16ED983F65FA5F5F156C8B70F10244AA1D582F039761DE227AD74FB49CD42`

### 7.2 模拟器最终生产入口

```powershell
& 'D:\vs2019\MSBuild\Current\Bin\MSBuild.exe' 'Simulator\LVGL.Simulator.sln' /m /nr:false /p:Configuration=Debug /p:Platform=x64 /v:minimal
```

- build exit：`0`
- exe：`5875712 B`，`2026-08-06T22:01:38.1771898+08:00`
- exe SHA-256：`69CC3131E23971EF2E1F11FBC1CDC5605D4D025CF64F3EE640ADB191A703EC18`
- build log：`.cache/p2-5-final/simulator-build.log`，SHA-256
  `4C1370420A8294B54DC82DBEE0B4E8047E60B003726E3FB12601A948705FD718`
- 连续两次启动均选择真实 `240x320` `lv_sim_visual_studio` 窗口；早晚探测均
  `responding=True`、`hung=False`，`RESIDUAL=0`。
- run log：`.cache/p2-5-final/simulator-launches.log`，SHA-256
  `C1D02890B76732D89DC6F245C3B317686C6B42B9FD92222E81D3206CBCB0763E`
- 两张最终 Startup 截图 SHA-256：
  `648DB1389A80191B66D4E093B9066C77C99BE3D68DD7E2A023499DEF90A540AC`、
  `1112D85F1FC6A909D1C3C44CE3C1DD52EFBD0DF3AC52B485B1674AF9C3DC5DDB`。

### 7.3 未执行项

- AC5 构建未执行；整改提示词 §4 明确 AC5 预存链问题不属于本卡。
- 没有重跑 P2-5 完整 SD 升级 `STAGED→APPLYING→TEST_BOOT→CONFIRMED`。
- 没有获得原 F4 根目录的精确条目数和修复前同目录计时。

## 8. 2026-08-06 阶段性判定（已被第 9 节补充更正）

第二轮静态整改、当前介质量化、清理版构建/回刷和回归验证均已完成；但整改提示词
§2 要求的原触发目录精确数据因介质状态变化不可恢复。本实现会话不得据此声称 F4 或
P2-5 已通过。P2-5 保持阻塞/待复验状态，下一步由非实现会话重新执行
`.claude/prompt-P2-5-verification.md`，并决定现有量化缺口是否需要重新构造等价真机目录
补测。

## 9. 2026-08-07 第五轮验收后补充整改

### 9.1 独立验收打回与结论更正

第五轮独立验收使用 fresh GCC App/Boot、fresh v20801 ETU、fresh map 与单一 RTT
logger 重跑，宿主回归、GCC、模拟器、F4 fixture 和包一致性均通过，但真机点击
“文件管理”后列表从未可操作即重启，RTT 明确记录 `Reset: NRST WDT`。同时验收
确认最终 App 仍编入 `CONFIG_RTT_DEBUG_CMD_ENABLE=1` 对应的 `RttDebugCmd_Poll`、
`RTTCMD:` 字符串和下行命令白名单。

- 验收报告：`docs/ota-exec-notes/P2-5-F4-independent-acceptance-2026-08-07.md`
- 原始 WDT：`.acceptance-p2-5-f4/20260807-003111/hardware-ota/44-rtt-f4-ui.log`
- 结论：第五轮验收不通过，P2-5 保持 `阻塞`，P2 保持 `4/6`。

本轮实现调试表明，2026-08-05/07 看到的 WDT 不是 `LoadFiles()` 扫描自身超过
10 秒，而是 LVGL heap 耗尽触发 HardFault 后，主循环停止调用 `HAL_Update()`，
最终 IWDG 到期产生的次生复位。第 2 节的目录读取量化仍有效，但不再作为旧 WDT
根因证明。

### 9.2 根因定位

先用临时 RTT/输入探针重走真实 MainMenu 编码器路径，并逐步缩小变量：

1. 仅把页面切换动画改为 `LOAD_ANIM_NONE` 无效。页面在约 `844 ms` 内完成设备检查、
   UI 创建和 6 行列表加载，随后仍出现 `Reset: NRST WDT`。这排除了“切换动画本身”
   和“单次扫描超过 10 秒”。
2. 将确认页和工作页改为按需创建后，页面可进入，但 MainMenu 继续缓存时内存仍不足。
3. 内存探针显示：browser UI 创建后 LVGL heap `free=8804`、`biggest=7152`；加入
   6 行后仅 `free=3636`、`biggest=3584`；随后的真实焦点移动触发 precise bus fault，
   `CFSR=0x00008200`、`BFAR=0x160000e7`。
4. 临时对全部 MainMenu 后继页禁用缓存虽可进入确认页，但返回时 MainMenu 重建与
   FirmwareUpdate 完整对象树形成第二个内存峰值，仍会 WDT；因此不能做全局缓存改动。
5. 最终采用仅针对 FirmwareUpdate 的 MainMenu 缓存释放，并在 FirmwareUpdate Pop
   前主动清空自身对象树，进入、返回和再次进入均稳定。

关键原始证据：

| 证据 | 关键结果 | SHA-256 |
|---|---|---|
| `.cache/p2-5-f4-remediation-20260807/anim-none-r1/real-input-rtt.log` | `LOAD_ANIM_NONE` 后仍 WDT；页面加载约 `844 ms` | `43DDD0ACBADB466CFFEED4EE768C969E4CC5EF32A559D24C33AA5A589A4E6CB2` |
| `.cache/p2-5-f4-remediation-20260807/mem-trace-r1/browser-mem-rtt.log` | 6 行后 `free=3636`、`biggest=3584` | `732C7BCD559A68195320529A9EF991B349BF74F3C2B1D7949B2077BDC3134FCD` |
| `.cache/p2-5-f4-remediation-20260807/mem-trace-r1/confirm-mem-rtt.log` | 焦点移动后 precise bus fault | `2EBB37CF3A1FC1E62FDD1717FA14C28449F201F02E228AEA84BE52A5710AFA42` |

### 9.3 正式实现

正式功能差异如下：

| 文件 | 实现 |
|---|---|
| `USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp` | 首屏只创建浏览 UI；`ShowConfirm()` 首次使用时创建确认 UI；`StartImport()` 首次使用时创建工作 UI；`Back()` 在 Pop 前调用 `ReleaseUI()`；`onViewUnload()` 复用同一清理路径 |
| `USER/App/Pages/FirmwareUpdate/FirmwareUpdate.h` | 声明 `ReleaseUI()`，并保留 `SCAN_MAX=256` |
| `USER/App/Pages/Menu/MainMenu.cpp` | 仅进入 `Pages/FirmwareUpdate` 前把当前 MainMenu 实例的 `IsCached` 置 false；Push 失败则恢复原值，其他页面缓存策略不变 |
| `USER/App/Config/Config.h` | `CONFIG_RTT_DEBUG_CMD_ENABLE` 从 `1` 改为 `0`，生产构建移除 RTT 下行命令 |

扫描路径继续保留第一、二轮已验证的全部修复：所有目录项消耗 `SCAN_MAX`、每 32 项
喂狗、扫描/可见行上限后的真实 probe、截断提示优先于 `TXT_EMPTY`、设备不可用提示
最高优先级、恰好读完不误报，以及纯 ASCII 文案。

最终源码位置：

```text
FirmwareUpdate.cpp:261  CreateUI() 仅创建 browser UI
FirmwareUpdate.cpp:790  ShowConfirm() 按需 CreateConfirmUI()
FirmwareUpdate.cpp:831  StartImport() 按需 CreateWorkUI()
FirmwareUpdate.cpp:1013 Back()
FirmwareUpdate.cpp:1028 ReleaseUI()
MainMenu.cpp:723         仅 FirmwareUpdate Push 前禁用当前页缓存
Config.h:157             CONFIG_RTT_DEBUG_CMD_ENABLE 0
```

### 9.4 真机调试版闭环

临时 trace 版保留 RTT 下行和输入注入仅用于自动重走真实 encoder 路径。正式清理前
取得以下闭环：

- MainMenu 打开文件管理，6 行列表完成创建。
- 移动焦点到 `P2-5-FULL.etu`，打开版本确认页，再取消返回列表。
- 物理返回触发 FirmwareUpdate `ReleaseUI()`，MainMenu 重新加载。
- 第二次进入文件管理仍成功，无 WDT、无 HardFault。

关键日志：

| 日志 | 结果 | SHA-256 |
|---|---|---|
| `.cache/p2-5-f4-remediation-20260807/scoped-cache-r1/entry-focus-confirm-rtt.log` | 首次进入、焦点移动、确认页成功 | `75392FA849E374E217AA175E9C8DF3F6CC27E278CF7A1D7CA388A8AE2230B82B` |
| `.cache/p2-5-f4-remediation-20260807/scoped-cache-r1/physical-back-reenter-rtt.log` | 取消、物理返回、MainMenu 重建、第二次进入成功 | `DF7E2973A2D540790FCB0A0B2DAE86A31C9463F5FE5FE3FA2EE5BEB8E68D7129` |

该证据验证真实页面生命周期和编码器事件路径，但不是最终生产固件的独立验收签字。

### 9.5 最终生产构建与清理审计

最终源码修改时间均早于 fresh 构建产物。GCC App/Boot 使用 clean-first 重新构建，
原始输出：

- 构建日志：`.cache/p2-5-f4-remediation-20260807/final-production-r1/fresh-gcc-app-boot-build.log`
- build：`PASS`，warning 行 `634`，error 行 `0`
- App raw bin：`598392 B`，`2026-08-07T18:12:41.3502010+08:00`
- App raw SHA-256：`F3AB9149D1F7C6E3051E269DEF5F8C669C6A8F872704A078D60CEC14953B44ED`
- App ELF：`859680 B`，SHA-256 `017E45C66F77505A2A22FAA39AD1FBA85CB21CB50C88E5CA7625B4EA91873E3E`
- App map：`2232628 B`，SHA-256 `38B52DABB9657077D976B429DBA67A312F24535A79EA90D72481B25D3E7A2749`
- Boot bin：`14724 B`，SHA-256 `5842FF3E19BA9E1EAAEA10F27E825C7B6EFC278B200531014B0DBA61264F6594`
- 构建日志 SHA-256：`CC0E52AED61978F2FD7007F36402DD80E135396511F9667EC990F2BAEBFD0220`

生产 marker 审计使用 `arm-none-eabi-nm -C` 和 `arm-none-eabi-strings` 检查 fresh
ELF/bin：

```text
ELF_SYMBOL_MARKERS=0
ELF_STRING_MARKERS=0
BIN_STRING_MARKERS=0
CONFIG_RTT_DEBUG_CMD_ENABLE=0
RTT_MAP=0x20045e14 _SEGGER_RTT
```

被检查的临时项包括 `F4TRACE`、`F4PROBE`、`RTTCMD:`、`RttDebugCmd_Poll` 和输入
注入符号。最终 `App.cpp` 仍从 `Pages/Startup` 启动，`lv_fs_pc.c` 的
`LV_FS_PC_PATH` 为 `"."`。

- marker 审计：`.cache/p2-5-f4-remediation-20260807/final-production-r1/production-marker-audit.log`
- 审计时间：`2026-08-07T19:00:20+08:00`
- 审计日志 SHA-256：`371C9BC89F3D7B8BAC5CCAFFDCDBC8A930E07FBAFEB772570A70D9686F0F5F85`

### 9.6 回归、模拟器与 fixture

11 组宿主测试全部返回 0：

```text
P1-1 fw header vectors: 16
P1-1 boot protocols: 19/0
P1-3 state machine: 96/0
P1-6 protocol: 21/0
test_vectors.py: Ran 9 ... OK
P2-1 staging: 48/0
P2-2 package: 102
P2-3 patch: 167/167
P2-4 SD: 29 + 5 + scenarios 7
P2-5 backup: 108/0
P2-5 confirm health: 17/0
```

- summary：`.cache/p2-5-f4-remediation-20260807/final-production-r1/host-tests-summary.log`
- summary SHA-256：`878BDA26ABB0277E2F0CBD52FE0F56FC788BB7A78A3EBF3043EEC4C32112FA6A`

F4 宿主 harness 通过：

```text
MIXED scan=256 rows=0 reads=257 more=1
ROWMAX rows=24 reads=25 more=1
EXACT_SCAN scan=256 reads=257 more=0
DEVICE_PRIORITY message=4
F4_SCAN_HARNESS=PASS
```

模拟器 `/t:Rebuild` 成功，最终 exe `5877248 B`，SHA-256
`D36260D1E5218089F84C644EB425D2A092AE2217D5761F7C1B8F9BE0FB4C83E8`。
五类 fixture 最终均进入文件页并经截图目视确认：扫描截断、可见行截断、恰好 256
项不误报、仅上级行截断、小目录选择并打开确认页。

首轮批量 fixture 中 `trunc-root`、`rowmax-root`、`small-root` 曾在 Startup 阶段偶发
Win32 hung，尚未进入本次修改页面；逐项复跑三项均 `BROWSER_READY=True`、
`RESPONDING=True`、`HUNG=False`。另做两次独立 Startup，均响应、无 hung、残留
进程 0。该偶发情况不隐去，也不当作页面修复失败或通过证据。

- 复跑日志：`.cache/p2-5-f4-remediation-20260807/final-production-r1/sim-fixtures-rerun.log`
- 复跑日志 SHA-256：`48732024BF20505A96B958B7EC866CC7EE6AEE4D275E7234DD02E086F4F55EB6`
- Startup 日志：`.cache/p2-5-f4-remediation-20260807/final-production-r1/startup-repeat.log`
- Startup 日志 SHA-256：`B1DA554DDAFDB654E067212AC7C8735D60B626837C1AF71E1A9177BE4B6505F3`

### 9.7 OTA 包与最终设备状态

同一 fresh raw App 分别 finalize 为 v20800/v20801，并生成 full ETU：

| 产物 | 大小 | SHA-256 |
|---|---:|---|
| `X-Track-App-GCC-v20800-final.bin` | `598392 B` | `1ED64882E483EE20902FE6951A1DDDDC5204CB31211BF1A46049EE726FF5A1B5` |
| `X-Track-App-GCC-v20801-final.bin` | `598392 B` | `644AFD12C983FB8AF48234A9CFF1709AA1BBA03AFCFF8F8E625CD1B6E46E84ED` |
| `P2-5-FULL-remediation-v20801.etu` | `281025 B` | `F1D4C417E4609AA4A16F45EC9671E0288D6110BA3C6794F4D1A4A46C99B955A3` |
| 解包 candidate | `598392 B` | `644AFD12C983FB8AF48234A9CFF1709AA1BBA03AFCFF8F8E625CD1B6E46E84ED` |

解包 candidate 与 v20801 finalized App 逐字节一致。该 ETU 仅保存在项目内，未写入
物理 SD `E:`，因为本实现会话没有获得该路径写入授权，也未执行完整 OTA 闭环。

最终 v20800 生产 App 已烧回设备：

```text
P1_5_APP_FLASH_VERIFY=PASS app=0x08010000 trailer_written=0
RTT=0x20045E14，SEGGER RTT 签名通过
SD_IsReady@0x2004520C=1
VTOR=0x08010000
CFSR=0x00000000
RTT: Reset: NRST SW
RTT: OTA: BCB already CONFIRMED vcode=20800
```

15 秒最终生产 RTT 未出现 WDT 或 HardFault。该结果证明生产清理版可正常启动，但因
最终生产态已关闭 RTT 下行命令且本轮未获物理 SD 写入授权，没有在该固件上自动执行
完整文件选择和 OTA；不能替代下一轮独立验收。

### 9.8 改动与文件系统申报

相对 HEAD `0023e5f` 的实际 tracked 内容差异为：

- `MDK-ARM_F435/cmake-generated/compile_commands.json`：fresh CMake 生成差异，未手工编辑。
- `PLAN-OTA-EXEC.md`：状态和会话证据回写。
- `Simulator/LVGL.Simulator/lv_fs_if/lv_fs_pc.c`：仅去除 BOM，路径最终为 `"."`。
- `USER/App/Config/Config.h`：关闭生产 RTT debug 命令。
- `USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp/.h`：扫描边界、按需 UI 和退出前释放。
- `USER/App/Pages/Menu/MainMenu.cpp`：仅 FirmwareUpdate 使用的缓存释放策略。

`USER/App/App.cpp`、`USER/App/Utils/OtaUpdate/OtaUpdate.cpp`、
`USER/lv_port/lv_port_indev.cpp`、`Tools/jlink/jlink-common.ps1` 在 `git status` 中可能因
mixed EOL/stat cache 显示 `.M`，但 worktree/index/HEAD 规范化 blob 相同，`git diff`
为空，不作为内容改动申报。`MDK-ARM_F435/RTE/_X-Track-App-AC5/RTE_Components.h`
曾有会话前预存行尾空白，第四轮验收后已精确收敛，最终无 diff。

SEGGER 工具运行时自动更新项目外配置
`C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini`。修改前记录为 `483 B`、SHA-256
`E661BD98032563B70776792296ECFC7E36D86ECF2921836DFADEB389D7914284`；最终为
`859 B`、`2026-08-07T18:35:22.8143538+08:00`、SHA-256
`D4FB1AD31E202D8C54307F664B5AA8EE08121252A04D5A7ACACFA60D6239E4B9`。这是 J-Link
DLL 自动持久化的连接/运行设置，不是仓库代码或固件内容。用户已明确授权本次自动
更新；未清理、未恢复，也没有据此扩展任何其他项目外写入权限。

### 9.9 当前判定

正式实现、生产调试命令清理、fresh 构建、宿主回归、模拟器 fixture、包一致性和
v20800 生产回刷均已完成。真实 encoder trace 版已关闭入口、确认、返回和二次进入的
OOM/WDT 链，但 v20801 ETU 尚未写入物理 SD，完整
`STAGED -> APPLYING -> TEST_BOOT -> CONFIRMED` 真机闭环未执行。

因此本实现会话仍不得声称 P2-5 通过：P2-5 保持 `阻塞`，P2 保持 `4/6`。下一步必须
由非实现会话按 `.claude/prompt-P2-5-verification.md` 独立重验；若需要写 `E:` 并执行
最终 OTA，须另行取得该路径的明确授权。
