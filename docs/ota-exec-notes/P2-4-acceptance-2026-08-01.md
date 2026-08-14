# P2-4 独立验收报告（2026-08-01）

## 1. 结论

**不通过。** P2-4 保持 `进行中`，P2 总进度保持 `3/6`。

本轮为非实现会话独立验收，未修复实现、未修改 P2-3、未修改冻结契约、未
commit/push。目标为 dirty worktree
`D:\github\my\E-Track-p2-4-20260731`，HEAD 独立核对为
`4cae0d4ad20f5a6bb60eaf8ec274a5adba377342`。完整 dirty 源码（含 untracked
文件、Keil dep/lnp 和截图）复制到
`D:\tmp\E-Track-p2-4-acceptance-20260801-034400` 后执行会写产物的验收命令。

## 2. Findings

### F1（阻断）：二次确认没有绑定随后实际导入的包

- `FirmwareUpdate::SelectRow()` 仅在打开确认框前调用 `Inspect()` 并把结果保存
  到页面的 `selectedInfo`（`FirmwareUpdate.cpp:752-758`）。
- 用户点击“开始导入”后，`StartImport()` 只按路径调用 `Begin(selectedPath)`
  （`FirmwareUpdate.cpp:797-807`）。
- `Session::Begin()` 会重新打开该路径、重新解析当前文件，并无条件用新结果覆盖
  内部 `packageInfo`（`OtaUpdate.cpp:296-328`），但没有与确认框显示的
  `selectedInfo`、文件长度或包身份作一致性比较。
- 因此在确认框显示期间替换同一路径文件（例如拔卡后替换为另一个仍合法、版本更高
  的 full/patch 包），实际进入两遍读取及 candidate apply 的可以是另一个包，
  而 UI 不会再次展示目标版本和类型供用户确认。

这使任务卡要求的“现版/目标版对比后二次确认”不能证明用户确认的就是实际导入包，
构成验收阻断。

### F2（阻断）：两遍之间追加文件内容不会 fail-closed

- `ota_sd_transfer_t` 在开始时缓存第一次检查得到的 `package_len`。
- 两遍循环都只读到固定的 `transfer->info.package_len`
  （`ota_sd.c:367-411`）；reader 接口没有重新查询文件长度的能力。
- 第二遍结束只比较这段固定前缀的 SHA-256/整包 CRC/payload CRC
  （`ota_sd.c:128-155`）。如果第一遍结束后仅向文件尾追加字节，原前缀完全相同，
  校验仍通过并执行 `ota_staging_finalize()`，写出 marker-last ETSL。

独立附加探针使用仓库 `toy-full.etu`：第一遍完成后将 reader 长度从 `748` 改为
`749` 并追加 `0x5A`，实际结果为：

```text
APPEND_CHANGE_RESULT=staged PHASE=4 NEW_READER_LEN=749
ORIGINAL_PACKAGE_LEN=748 FAIL_CLOSED=0
```

既有 22 项中的“between-pass change”只修改原长度范围内字节，能得到
`OTA_SD_ERR_FILE_CHANGED`；它没有覆盖文件追加/截断后的重新定长检查。该行为直接
违反验收项“文件两遍之间变化时 fail-closed”。

## 3. 范围与静态审计

以下项目独立检查通过：

| 项目 | 结果 |
|---|---|
| branch / HEAD | `p2-4-20260731` / `4cae0d4ad20f5a6bb60eaf8ec274a5adba377342` |
| 冻结 `PLAN-OTA.md`、`docs/ota-binary-contracts.md` | 相对 HEAD 无 diff |
| P2-3 实现/证据路径 | 相对 HEAD 无变更；未运行 P2-3 专项验收 |
| legacy `X-Track` 新源计数 | `0` |
| `X-Track-App-AC5` 新源计数 | `6`（3 个源 + 3 个头） |
| GCC App source set | 仅 App 增加 `FirmwareUpdate.cpp`、`OtaUpdate.cpp`、`ota_sd.c` |
| 模拟器 XML | 新编译项唯一，无重复 |
| AC5 `--cpp11` | XML 与实际 dep 中 `FirmwareUpdate.cpp`、`OtaUpdate.cpp` 均存在 |
| App-AC5 lnp | `ota_sd.o`、`otaupdate.o`、`firmwareupdate.o` 各 1 次 |
| 生产入口 | `App.cpp` 唯一 `manager.Push("Pages/Startup")` |
| 临时 harness | 源码无 `P2_4_HW`、`HardwareTest` 或直达页面入口 |
| 越卡行为 | P2-4 新源无 BCB 提交、backup、自重启、CONFIRMED 路径 |
| 文件浏览 | 根 `/`、子目录拼接、目录保留、最终扩展名大小写不敏感 `.etu`、隐藏项/SVI 过滤均符合 RouteSelect 口径 |
| LVGL group | unload/disappear 使用 `ClearGroup()` 逐个移除本页对象；未在 unload/Pop 调用 `lv_group_remove_all_objs()` |
| 绘制红线 | 新页面无 shadow、`LV_EVENT_DRAW_POST`、`lv_draw_*`、mask 自绘 |
| 中文字体 | 新增中文字符对 `font_cn_16.c.chars` 检查 `missing=0` |

## 4. 独立测试与构建

### 4.1 宿主

```text
python tests/ota/test_ota_sd.py
=== summary: 22 checks, 0 failure(s) ===
P2_4_OTA_SD=PASS checks=22 failures=0
```

官方套件通过不抵消 F1/F2 的未覆盖阻断场景。

### 4.2 GCC App（fresh Release）

| 项目 | 结果 |
|---|---|
| configure / build | `rc=0 / rc=0` |
| errors | `0` |
| warnings | 存在；独立日志中 `warning:` 行 `631`，含仓库既有源码诊断、`376` 条 wchar ABI 链接告警及 `1` 条 RWX LOAD 告警 |
| FLASH | `594016 B / 960 KB (60.43%)` |
| RAM | `291528 B / 352 KB (80.88%)` |
| bin | `594016 B` |
| SHA-256 | `7D8E65411AD5C3D1EFA76BF302C73EE3EAFD79E2C552FBF666CAE1FE5372C50A` |

三个 P2-4 新源没有直接编译器 warning；项目级既有 warning 已如实保留。隔离源码
路径不同使含路径字符串的 GCC 产物尺寸/哈希不要求与实现会话声明逐位一致。

### 4.3 X-Track-App-AC5

强制重编 `App.cpp`、`AppFactory.cpp`、`MainMenu.cpp`、`FirmwareUpdate.cpp`、
`OtaUpdate.cpp`、`ota_sd.c` 后重新链接/fromelf：

```text
Program Size: Code=296312 RO-data=289376 RW-data=1332 ZI-data=495432
0 Error(s), 0 Warning(s)
```

- bin：`586492 B`
- SHA-256：`14845182E2B94CA5EE998F093E84DFAE22547577BAF8BF0DEC089A62719F50FF`

### 4.4 模拟器

- MSBuild `rc=0`，错误 `0`，仓库既有 warning 行 `102`。
- exe 时间戳从 `2026-08-01 02:33:20.238` 刷新为
  `2026-08-01 03:58:30.083`。
- fresh exe：`5876736 B`，SHA-256
  `044AE3F49A3B973D5540E1E272EBBCBF74E021AE1E93D30215B65D081C3BDEDF`。
- 启动 1：`Responding=True`、`IsHung=False`、WS `52.35 MB`、Private
  `88.26 MB`。
- 启动 2：`Responding=True`、`IsHung=False`、WS `52.37 MB`、Private
  `88.28 MB`。
- 两次结束后 `LVGL.Simulator` 残留进程 `0`。
- 三张专名截图已目视检查：确认页含 FULL/当前版本/目标版本/开始导入；ready 页为
  `100 / CANDIDATE READY`；生产图显示真实 Startup 动画。
- 另从本轮重建 exe 独立抓取 Startup 图，确认仍从 `Pages/Startup` 进入并执行
  `Loading`/E-Track 动画，而非跳过启动页。

## 5. 真机证据

本轮没有重新植入已删除的 P2-4 硬件 harness，故没有伪称独立重做完整 SD 链路。
对实现会话原始资产作了独立复核：

- 原始 RTT 日志 SHA-256
  `16139D3B1EE1EDE8FBB5ADA622FBB96D7D3F2176726F5342A8FA2A70A959CD2F`，
  含两轮一致的目录、decoy 过滤、`20800 -> 20801`、完整 LVGL 路径和
  `success=1 progress=100` 行。
- `P2-4-FULL.etu` 独立解包/`--verify-fw-header` 通过；4096B candidate 与
  `p2-4-target-v2.8.1.bin` 逐字节一致，SHA-256 均为
  `075B1E5E5EBC7E56F06957E43206D1A37E5F8389396BA748809876A4DA8D3582`。
- 本轮 AC5 链接后的 map 严格唯一解析 `_SEGGER_RTT=0x2004B3D0`，真机
  `mem8` 重新读取到 `SEGGER RTT` 签名后才运行一个带 15 秒超时的 logger；
  logger 结束后残留为 `0`，新日志含生产 `OTA: HANDOFF` 且不含 `P2_4_HW`。
- logger 后最终独立探针：`PC=0x080496F2`（App 区）、
  `VTOR=0x08010000`、`CFSR=0x00000000`，RTT 签名仍正确，无 J-Link/logger
  残留进程。

由于未独立重做带 harness 的 SD 交互，原始硬件成功链仍列为残余风险；但 F1/F2
已由源码和独立宿主探针直接成立，足以阻断本卡，无需为了得到相同成功日志再次改写
并回刷设备。

## 6. 处置

- P2-4 保持 `进行中`。
- P2 总进度保持 `3/6`。
- 实现会话需关闭 F1/F2，并增加至少覆盖“确认后同路径包被替换”和“两遍间文件长度
  追加/截断”的回归，再交由新的非实现会话复验。
- P2-3、P2-5、P2-6 与冻结契约均不作改动。

## 7. 整改独立复验（仍不通过）

### 7.1 结论

**仍不通过。** F1 的确认身份绑定已关闭，宿主 reader 下的 F2 也已关闭；但 MCU
实际使用的 SdFat reader 长度不是实时值，追加/截断 fail-closed 在目标侧仍不能
成立。P2-4 保持 `进行中`，P2 总进度保持 `3/6`。

本轮继续使用同一 dirty worktree，复验前再次确认 HEAD 为
`4cae0d4ad20f5a6bb60eaf8ec274a5adba377342`。未修改生产实现、P2-3、
`PLAN-OTA.md` 或 `docs/ota-binary-contracts.md`，未 commit/push。

### 7.2 F3（阻断）：MCU 的“实时长度”回调读取打开句柄缓存

- `Session::GetSelectedFileSize()` 对当前打开的同一 `lv_fs_file_t` 执行
  `LV_FS_SEEK_END` 后 `lv_fs_tell()`（`OtaUpdate.cpp:612-639`）。
- MCU LVGL 驱动把 `LV_FS_SEEK_END` 映射为 `SdFile::seekEnd()`，且忽略其返回值
  （`lv_port_fs_sdfat.cpp:212-231`）。
- 本仓库 SdFat 的 `FatFile::seekEnd()` 实际为
  `seekSet(m_fileSize + offset)`（`FatFile.h:815-821`）；`fileSize()` 同样只返回
  成员 `m_fileSize`（`FatFile.h:364-366`）。该成员在打开文件时从目录项复制一次
  （`FatFile.cpp:540-555`），不是每次查询重新读取目录项。

因此，`reader.size()` 在宿主 fixture 中会看到可变的 `reader_fixture.len`，但 MCU
上文件保持打开时只会返回打开时长度。文件尾追加 1B 后原长度前缀完全相同，第二遍
SHA/CRC 仍可一致并进入 marker-last；截断时也不能保证返回
`OTA_SD_ERR_FILE_CHANGED`。这正是本次整改要关闭的目标场景，构成阻断。

旧真机证据只覆盖未变化文件的正常成功链，不能证明新增长度变化语义；本轮没有把旧
成功 harness 当作整改通过证据。复验过程中实际两次刷入临时整改 harness，flash 与
verify 均成功，但 RTT 只得到重复 `P2_4_REMEDIATION_HW: open_fail`，没有形成有效的
追加/截断目标侧证据。此前“没有重新烧录 harness”的记录不准确，完整更正及生产恢复
见 §7.6；本轮未宣称真机整改通过。

### 7.3 已关闭项与独立探针

官方宿主套件重新编译并运行：

```text
python tests/ota/test_ota_sd.py
=== summary: 29 checks, 0 failure(s) ===
P2_4_OTA_SD=PASS checks=29 failures=0
```

测试源码确实改变 reader 长度并检查 `file_changed`/marker 擦除态；但它的
`reader_size()` 直接返回可变 fixture 字段，未覆盖上述 SdFat 缓存语义。正式测试
也没有直接构造 `Session::Inspect()`→`Session::Begin()` 的一次性确认链，故本轮
增加了不改仓库源码的临时验收探针：

- 用正式 `etu_pack.py` 对 `toy-new.bin` 重新制包并用 `etu_unpack.py
  --verify-fw-header` 验证，得到另一份合法且同为 `748B` 的 full `.etu`；两包
  SHA-256 不同，解包 candidate 与 `toy-new.bin` 一致。
- 真实 `OtaUpdate::Session` + LVGL 文件桩：`Inspect=ok`，替换后
  `Begin=file_changed`，再次 `Begin=file_changed`，且 `packageInfo` 保持已确认值，
  证明路径/头信息绑定、Begin 不覆盖及一次性消费已生效。
- `ota_sd` 全 IO 计数探针：合法同长度替换返回 `file_changed`，`ERASES=0`、
  `PROGRAMS=0`、marker=`0xFFFFFFFF`。
- 实际分配追加字节的长度探针：追加后长度 `749`、截断后长度 `747`，两例在可实时
  报长的 reader 上均返回 `file_changed`、phase=`ERROR`、marker=`0xFFFFFFFF`。

这些结果关闭原 F1，并证明 F2 修复在“reader.size 真正实时”的抽象层有效；它们不
能抵消 F3 的 MCU target 适配错误。

### 7.4 构建与模拟器复验

- fresh GCC Release App：构建成功，FLASH `594888B`、RAM `291528B`；日志
  `warning:` 631 行、`error:` 0 行。告警为仓库既有源码、wchar ABI 与 RWX LOAD
  类别，P2-4 三个新源只有项目级 wchar 链接告警，没有直接编译器诊断。
- AC5 App：强制重编 `App.cpp`、`AppFactory.cpp`、`MainMenu.cpp`、
  `FirmwareUpdate.cpp`、`OtaUpdate.cpp`、`ota_sd.c` 后重新链接/fromelf，结果
  `Program Size: Code=297132 RO-data=289372 RW-data=1332 ZI-data=495432`，
  armlink/fromelf rc=0，日志无 warning/error；`Track-App-AC5.bin=587308B`。
- 模拟器 `/t:Rebuild` 成功，既有 warning 102 行、error 0；fresh exe
  `5870592B`。连续两次启动均 `Responding=True`、`Hung=False`，工作集
  `52.34/51.94MB`、私有内存 `88.41/88.11MB`，最终残留进程 0。
- 专名截图 `.claude/p2-4-remediation-independent-startup-gui-20260801.png` 已目视
  确认为真实 `Pages/Startup` 的 `Loading` 电路动画，非直达其他页面。

### 7.5 最终处置

- P2-4 保持 `进行中`，P2 保持 `3/6`。
- 下一轮整改必须让 MCU 端长度查询重新读取路径/目录项或在每个检查点安全重开并
  stat，同步处理拔卡/重挂载后的旧句柄失效；正式回归还应覆盖真实
  `Session::Inspect()`→`Begin()` 和 target SdFat 语义。
- 首次验收 F1/F2 记录完整保留，不覆盖、不改写历史证据。

### 7.6 真机操作更正与生产恢复

本轮临时 harness 的两次刷写证据位于
`.acceptance-p2-4/codex-revalidation/jlink-harness/flash-app-console.log` 与
`flash-app-run2-console.log`，两次均有 `loadbin`、`verifybin` 成功记录；对应 RTT
日志只有重复 `P2_4_REMEDIATION_HW: open_fail`，因此不作为整改通过证据。

发现板端仍运行 harness 后，立即用当前 AC5 生产 raw bin 重新生成并验证生产镜像：

- raw `MDK-ARM_F435/Track-App-AC5.bin`：`587308B`，SHA-256
  `5633049B742FDB54A32CDF9040FA9DCA090996FA5E7A893F38AFF540E2922389`；
- 最终清理使用 `etu_pack.py finalize --ver-name v2.8.0` 输出
  `.acceptance-p2-4/hw/X-Track-App-AC5-production-finalized.bin`，SHA-256
  `D15402CE6CBF9CA49CB678B59837EFEB2FC3E519FFEBCE6A3E0DE852F060A86F`；
- finalize 结果 `image_len=587308`、`vcode=20800`、`0x400=ETFW`，向量区
  `0x000..0x3ff` 与 raw bin 一致；再经 `pack-full`、`etu_unpack.py
  --verify-fw-header` 往返，`.acceptance-p2-4/hw/production-finalized-roundtrip.bin`
  与 finalized bin 逐字节一致且 SHA-256 相同；
- 使用 `AT32F435RGT7`、SWD 1000kHz 烧录 `0x08010000`。首次独立运行的
  `verifybin` 曾在 `0x0805F4D6` 得到一次 `expected 0x16/read 0x00`；没有据此
  盲目重复擦写，而是在同一 halted J-Link 会话中执行 `loadbin` 后立即执行整镜像
  `verifybin`，结果为 `Contents already match`、`Verify successful`。最终权威日志为
  `.acceptance-p2-4/hw/jlink-flash-verify-production-halted.log`；
- 当前生产 map 严格解析 `_SEGGER_RTT=0x2004B3D0`，板端该地址读到
  `SEGGER RTT`；旧 harness 地址 `0x2004C788` 不再是 RTT 控制块；
- 最终生产状态日志 `.acceptance-p2-4/hw/jlink-production-state.log` 显示
  `PC=0x08040288`（App 区）、`VTOR=0x08010000`、`CFSR=0x00000000`，生产 RTT
  签名有效；源码与当前 map 均无 harness 标记。此前 RTT 日志含
  `OTA: BCB already CONFIRMED vcode=20800`，不含 `P2_4_REMEDIATION_HW` 或
  `P2_4_HW`；J-Link/RTT logger/模拟器最终均无残留进程。

该恢复只用于撤销临时 harness，不改变 F3 阻断结论。P2-4 继续保持 `进行中`，P2
继续保持 `3/6`，未 commit/push。

## 8. F3 二次整改独立复验（通过）

### 8.1 结论

**通过。** F3 已关闭 MCU SdFat 打开句柄缓存导致的长度变化漏检；首次验收的 F1、
F2 与整改复验的 F3 均无剩余阻断。P2-4 可置 `完成`，P2 总进度更新为 `4/6`。

本轮继续在独立 worktree
`D:\github\my\E-Track-p2-4-20260731` 验收，HEAD 仍为
`4cae0d4ad20f5a6bb60eaf8ec274a5adba377342`。未 commit/push，未修改 P2-3、
`PLAN-OTA.md`、`docs/ota-binary-contracts.md`，未实现 P2-5/P2-6。

### 8.2 F3 目标侧语义

- `Session::GetSelectedFileSize()` 保存逻辑偏移后先 `CloseFile()`，再按已确认的
  `selectedPath` 调用 `OpenSelectedFile()`；新句柄重新读取目录项长度，并恢复或钳制
  偏移。重开或恢复偏移失败时保持无可用旧句柄并返回读错误。
- 实际 LVGL `lv_fs_close()` 无论驱动 close 返回值如何都会清空 `file_d`、`drv` 和
  cache；MCU `fs_close()` 也会在 `SdFile::close()` 后无条件删除该 `SdFile` 对象。
  因此忽略 `lv_fs_close()` 返回值不会保留或复用旧读句柄。
- MCU `fs_open()` 每次重新分配 `SdFile` 并按归一化 LVGL 路径调用 `open()`；SdFat
  在新对象打开时从目录项重新装载 `m_fileSize`。正式宿主适配测试按该“每句柄缓存”
  行为建模，直接编译真实 `OtaUpdate.cpp`，不是可变长度的理想 reader 桩。
- `Inspect()` 的一次性确认快照包含完整 LVGL 路径、精确长度、已展示并保存的
  `packageInfo` 以及整包 SHA-256。`Begin()` 不覆盖 `packageInfo`，并在路径、长度、
  头信息或首遍整包 SHA 任一不匹配时 fail-closed。

### 8.3 宿主回归

独立执行 `python tests/ota/test_ota_sd.py`，结果为核心 `29/29` 与真实 Session 适配
场景 `5/5` 全部通过：

```text
CONFIRM_REPLACE result=file_changed opens=8 closes=8
APPEND_1B result=file_changed error=stage:file_changed opens=15 closes=15
TRUNCATE_1B result=file_changed error=stage:file_changed opens=15 closes=15
SECOND_PASS_REPLACE result=file_changed error=stage:file_changed opens=19 closes=19
UNAVAILABLE result=read error=stage:read opens=14 closes=14
P2_4_OTA_SD_ALL=PASS core_checks=29 adapter_scenarios=5
```

核心测试同时确认：合法同长度替换在任何 staging erase/program 前返回
`OTA_SD_ERR_FILE_CHANGED`，commit marker 为 `0xFFFFFFFF`；第一遍后追加 1B 或截断
1B 均返回 `OTA_SD_ERR_FILE_CHANGED`，marker 保持擦除态。原始日志为
`.acceptance-p2-4/f3-independent/host-29-plus-5.log`，SHA-256
`2DE41F7C0E245049A05FC61DDF2F231BC74639D08EEBA9D93EB3C0901497C3B9`。

### 8.4 构建与模拟器

- fresh GCC Release App：configure/build rc=0，共 379 步；FLASH `594936B`、RAM
  `291528B`，bin SHA-256
  `A6BD2B5DC5584478CBA41E2AB2593BF368C9D67AD25A33A5BEB480804ADAD181`。
  `warning:` 631 行、`error:` 0 行；均为仓库既有类别，`OtaUpdate.cpp` 仅有项目级
  wchar 链接告警，无直接编译器诊断。
- AC5 `X-Track-App-AC5`：强制重编 `OtaUpdate.cpp` 后 armlink/fromelf rc=0，日志
  warning/error 均为 0；`Program Size: Code=297188 RO-data=289372 RW-data=1332
  ZI-data=495432`。bin `587364B`，SHA-256
  `63826BD6DCBE0950CC17F6C27C80DB718FA24A18930D034AD503D73B5C673EE9`。
- 模拟器 `/t:Rebuild` rc=0，仓库既有 warning 102 行、error 0；fresh exe
  `5871104B`，时间戳 `2026-08-01 19:00:47.560`，SHA-256
  `EF12A37E5FCAA3D61165269F67886834ADAD0CAB2AC55775B01CCDFEED6277FE`。
- 连续两次启动分别为
  `Responding=True/Hung=False/WS=52.51MB/Private=88.25MB` 与
  `Responding=True/Hung=False/WS=52.49MB/Private=88.21MB`，残留进程均为 0。
  `.acceptance-p2-4/f3-independent/startup-1.png` 与 `startup-2.png` 已目视确认均为
  真实 `Pages/Startup` 的 `Loading` 电路动画。

### 8.5 范围、硬件证据与处置

- 生产入口仍唯一为 `manager.Push("Pages/Startup")`；新增源码无 `P2_4_HW`、
  `P2_4_REMEDIATION_HW`、BCB、backup、reset、CONFIRMED、TEST_BOOT 或 APPLYING
  逻辑。P2-5/P2-6 未越卡实现。
- 新源只进入 `X-Track-App-AC5`、GCC App 与模拟器；legacy target 新源计数为 0。
  AC5 dep 中 `FirmwareUpdate.cpp`、`OtaUpdate.cpp` 均实际带 `--cpp11`，模拟器三个
  compile 项各唯一一次。
- `git diff --check` 无错误；14 个非证据目录 untracked 文本文件独立检查无行尾空白
  或缺失 EOF newline。冻结契约与 P2-3 指定实现/证据文件相对 HEAD 的 diff 为 0。
- 本轮不再刷写 F3 固件。此前真实 MCU/SD 成功链已经覆盖未改变的目录浏览、`.ETU`
  过滤、版本对比、确认、两遍 staging 和 candidate 逐字节结果；F3 仅替换 Session
  文件句柄刷新语义，该语义已由真实 Session 缓存句柄回归和实际 LVGL/SdFat 源码
  对号独立闭环，旧硬件证据足够复用，无需再次植入 harness。
- 无刷写生产探针重新确认 RTT 地址 `0x2004B3D0` 的 `SEGGER RTT` 签名有效，
  `PC=0x08045B3E`、`VTOR=0x08010000`、`CFSR=0x00000000`，探针后已继续运行；
  J-Link、RTT logger、模拟器最终均无残留进程。

最终处置：P2-4 置 `完成`，P2 更新为 `4/6`；保留 §1-§7 的历史拒绝与更正记录，
不覆盖旧证据。未 commit/push。

## 9. 提交、合并与 Main CI 收口

本节只归档 P2-4 已通过独立验收后的提交、合并与主干 CI 结果，不重新验收 P2-4，
不修改卡片 `完成`、P2 `4/6` 状态，也不认领或实现 P2-5。

- P2-4 已验证提交为
  `8ccc1d0c6f5beb554393e2240d52616f236cf8ec`；PR #1 使用 merge commit 合入
  `main`，merge SHA 为 `614a3fc759768c4e00764e9b6e254574b93d89f0`。该 merge
  commit 的第二父提交仍为上述已验证提交，未 squash 或 rebase。
- `main` 的 `MCU Firmware Build` run `30703282359` 以 merge SHA
  `614a3fc759768c4e00764e9b6e254574b93d89f0` 为 head，结论为 `success`。
- App artifact `firmware-2.7-nightly.63` 中 `X-Track-App-GCC.bin` 为
  `594956B`，SHA-256
  `12B59FFBC8F72FEBA6D2866A1D59A0AE23C931774ECCD408F2C706A9F5E6DF72`。
- Boot artifact `boot-2.7-nightly.63` 中 `X-Track-Boot.bin` 为 `14236B`，
  SHA-256
  `435C332E1A3FAEDCD262D05E639784BF6173FE680DAA3343949CFBAD52B9E4AA`。
- CI 的 OTA App 布局断言通过：`flash=0x08010000/0xf0000`、
  `vector=0x08010000/0x20c`、`header=0x08010400/96`；下载后的 App 再检查确认
  96B raw fw_header placeholder 全为 `0xFF`。Boot artifact 与 handoff 断言也通过。
- 构建日志含 `635` 行 `warning:`、`0` 行 `error:`；其中 3 行是 P2-4 新对象命中的
  仓库既有 2-byte/4-byte `wchar_t` 链接告警类别，未伪装为零告警构建。
- `Register firmware to Cloudflare` 与 `Create GitHub Release` job 均为
  `skipped`；合并后的 Release 审计新增数为 `0`，未正式发布、未注册 Cloudflare。
