# P2-4 SD 文件管理页实现与本地取证（2026-08-01）

## 1. 状态与范围

- 基线：`4cae0d4ad20f5a6bb60eaf8ec274a5adba377342`。
- 独立 worktree：`D:\github\my\E-Track-p2-4-20260731`，分支
  `p2-4-20260731`。
- 本轮只实现 P2-4。`PLAN-OTA.md` 冻结 §5.2、
  `docs/ota-binary-contracts.md`、P2-3 实现/证据均未修改。
- 未实现 P2-5 的 backup 自拷、BCB=STAGED、重启提示或 CONFIRMED；
  未实现 P2-6 RAM 峰值回填。
- 首轮独立验收结论为“不通过”，两项阻断及原始证据保留在
  `P2-4-acceptance-2026-08-01.md`。本文第 7 节记录实现会话整改，结论仍仅为
  “整改完成，待独立复验”。
- 本文是实现会话自测证据，不是独立验收结论。P2-4 状态保持
  `进行中`，未 commit/push。

## 2. 实现结果

### 2.1 文件管理与确认 UI

- 新增 `Pages/FirmwareUpdate`，App target 与模拟器把主菜单原
  “关于设备”入口替换为“文件管理”；legacy target 仍保留原入口和行为。
- 复用 RouteSelect 的 LVGL 路径口径：根路径为 `/`，目录项由驱动返回的
  前导 `/` 判定，拼接后的文件路径继续使用 LVGL 路径，例如
  `/Navigation/update.etu`。
- 跳过隐藏项和 `System Volume Information`；目录始终显示，普通文件只接受
  最终扩展名为 `.etu` 的条目，大小写不敏感。
- 选包后先校验冻结 64B 外层头，再显示 FULL/PATCH、当前版本、目标版本和
  文件名；只有二次确认按钮才启动导入。
- 页面退出只移除本页拥有的 group 对象；未在 unload/Pop 后调用
  `lv_group_remove_all_objs()`。列表行关闭默认 layout 后显式做垂直居中。
- UI 仅使用普通 `lv_obj`、`lv_label`、`lv_bar` 和 timer；未使用 shadow、
  draw callback、mask 或自绘路径。

### 2.2 SD 到 staging 数据链

- 新增 `Libraries/OTA/ota_sd.{c,h}`，逐字段读取冻结 `.etu` 外层头，检查：
  magic、header CRC、flags、algorithm/key、hardware/layout/min boot、
  `target_vcode > current_vcode`、full/patch base 身份以及精确文件长度。
- 第一遍以 128B 缓冲顺序读取 SD，计算整包 SHA-256、整包 CRC32 和密文
  payload CRC32；payload CRC 通过后才调用既有 `ota_staging_begin()`。
- 第二遍按同一 128B 缓冲写 staging，复用既有 ETRJ 4KiB durable resume；
  已持久化前缀不擦除、不重写。
- 第二遍结束再次核对整包 SHA/CRC 与 payload CRC，文件在两遍之间发生变化时
  fail-closed；之后调用既有 `ota_staging_finalize()`，继续保持 ETSL marker-last。
- 新增 `OtaUpdate::Session` 连接 LVGL 文件 API、当前 App fw_header/raw SHA8、
  HAL staging IO 以及已验收的 full/patch candidate 校验器。成功边界是
  `CANDIDATE READY`，不越卡提交 BCB。

### 2.3 target 隔离

- `ota_sd.c`、`OtaUpdate.cpp`、`FirmwareUpdate.cpp` 只加入
  `X-Track-App-AC5` 和 GCC App source set；legacy `X-Track` 中新源计数为 0。
- `FirmwareUpdate.cpp` 与 `OtaUpdate.cpp` 所在 Keil group 的
  `<MiscControls>` 为 `--cpp11`；实际 App-AC5 dep 命令也包含 `--cpp11`。
- App-AC5 lnp 含 `ota_sd.o`、`otaupdate.o`、`firmwareupdate.o`。
- 模拟器项目中新增编译项均唯一，无重复 XML 项。

## 3. 宿主测试

命令：

```powershell
python tests/ota/test_ota_sd.py
```

结果：

```text
=== summary: 29 checks, 0 failure(s) ===
P2_4_OTA_SD=PASS checks=29 failures=0
```

覆盖点包括：大小写 `.etu` 最终扩展名过滤、full/patch 头字段、版本和 base
身份拒绝、头/payload CRC、精确文件长度、两遍文件变更拒绝、marker-last、
4KiB durable resume 及已持久化块不擦不写；整改新增确认时整包 SHA-256 快照、
同路径同长度合法包替换拒绝、第一遍后追加及截断拒绝。

## 4. 构建与模拟器

### 4.1 GCC App

最终当前源码重建命令：

```powershell
cmake --build D:\p2-4-gcc-prod-final-20260731 \
  --target X_Track_App_GCC --parallel 8
```

结果：

```text
[100%] Built target X_Track_App_GCC
FLASH: 594888 B / 960 KB (60.52%)
RAM:   291528 B / 352 KB (80.88%)
```

- bin：`594888B`，时间戳 `2026-08-01 04:45:46.481`，SHA-256
  `B17D23EA4F0E6EB06B0A0E9CE37BB9F06FB5113C8D7121DE164CC4AE5619820E`。
- fresh Release 全量编译有警告、错误为 0；警告为仓库既有类别（含 wchar ABI、
  RWX LOAD 及既有源码告警）。P2-4 三个新源无新增编译器诊断；最终链接仍会像
  其他对象一样出现在项目级 wchar/RWX 警告中，未将警告伪装为零警告。

### 4.2 AC5 App

最终生产源码（已删除真机临时 harness）先精确重编 `ota_sd.c`、
`OtaUpdate.cpp`、`FirmwareUpdate.cpp`，一次性确认消费逻辑收口后再精确重编
`OtaUpdate.cpp` 并重新链接：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command \
  "& 'MDK-ARM_F435\build_f435.ps1' -Target 'X-Track-App-AC5' \
  -Sources @('..\Libraries\OTA\ota_sd.c', \
  '..\USER\App\Utils\OtaUpdate\OtaUpdate.cpp', \
  '..\USER\App\Pages\FirmwareUpdate\FirmwareUpdate.cpp')"

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command \
  "& 'MDK-ARM_F435\build_f435.ps1' -Target 'X-Track-App-AC5' \
  -Sources @('..\USER\App\Utils\OtaUpdate\OtaUpdate.cpp')"
```

结果：

```text
Program Size: Code=297132 RO-data=289372 RW-data=1332 ZI-data=495432
armlink/fromelf exit code 0
```

- `Track-App-AC5.bin`：`587308B`，时间戳 `2026-08-01 04:46:35.697`，
  SHA-256
  `AA3649CC56FF9B8D6D0B708CE13CB63656A1C9919D773E583A64683D006ACDA1`。
- App-AC5 全量构建记录为 `0 Error(s), 0 Warning(s)`；上述整改增量重建亦无
  编译警告输出。

### 4.3 模拟器

```powershell
& 'D:\vs2019\MSBuild\Current\Bin\MSBuild.exe' \
  'Simulator\LVGL.Simulator.sln' /m \
  /p:Configuration=Debug /p:Platform=x64 /v:minimal
```

- 最终 exe：`5869568B`，时间戳 `2026-08-01 04:45:36.411`，SHA-256
  `C7010889464EF764B29CFCD1E8F66FEC1673A82987B153DE18367AC36018A0DB`。
- 二次确认截图：`.claude/p2-4-file-manager-confirm.png`，SHA-256
  `5BB8FFDFB5AFD2FBF3D43EB1AB22B5061C7789D8AC72BC225B89A6EA6EB4CA48`。
- candidate ready 截图：`.claude/p2-4-file-manager-ready.png`，SHA-256
  `05689887D27C0399ED79F71CE92FE29732DDDD7106ADA2166D5B1D136EE03D84`。
- 恢复生产入口后的 Startup 截图：
  `.claude/p2-4-production-startup-final.png`，SHA-256
  `36251BFEEE939A6DF4BF2ECFD8FD4E4A31D150AF428BCC0042442D65BCA0C759`；
  已目视确认真实 Startup 动画仍执行。
- 整改后的最终 Startup 截图：
  `.claude/p2-4-remediation-production-startup.png`，SHA-256
  `370326003F49323DA7D2DAA0284BF4696199A4E787636162D3A5CB07CFF6CED8`；
  未调用含错误硬编码路径的 `.claude/cap.ps1`，已目视确认真实 Startup 动画。
- 整改后最终独立启动两次：

```text
launch 1: Responding=True Hung=False WS=52.39MB Private=88.31MB
launch 2: Responding=True Hung=False WS=52.34MB Private=88.21MB
leftovers=0
```

## 5. 真机 SD / J-Link / RTT

### 5.1 夹具

| 文件 | 长度 | SHA-256 |
|---|---:|---|
| `P2-4-FULL.etu` | 430B | `1EED98EBD7094E337A4B45B8A8A1F8AEEF94C7F69BBD7EE4BE5E6BD4F7940232` |
| `p2-4-target-v2.8.1.bin` | 4096B | `075B1E5E5EBC7E56F06957E43206D1A37E5F8389396BA748809876A4DA8D3582` |

`etu_unpack.py --verify-fw-header` 对夹具通过，解包 candidate 与目标 bin
逐字节一致。临时硬件 App 以当前版 `2.8.0 / 20800` finalize：

```text
P1_5_APP_VERIFY=PASS kind=app len=587988 vcode=20800
sha256=135c3ee395a32dcb2c184c52c6a30d797f3620f1899849d71cead3259a054f1d
```

### 5.2 烧录、地址与日志

- 使用 `AT32F435RGT7 / SWD / 1000kHz`，在 `0x08010000` 对 finalized App
  执行 `loadbin` + `verifybin`，J-Link 报 `Verify successful.`。
- 从本次链接后的 App-AC5 map 严格匹配唯一符号行：

```text
_SEGGER_RTT  0x2004b3d0  Data  168  segger_rtt.o(.bss)
```

- `mem8 0x2004B3D0,16` 读到 `SEGGER RTT` 签名后才启动单一 logger；采集
  40 秒并确认退出后无残留 `JLinkRTTLogger`。
- RTT 原始日志 SHA-256：
  `16139D3B1EE1EDE8FBB5ADA622FBB96D7D3F2176726F5342A8FA2A70A959CD2F`。
- 采集到两轮一致结果，单轮关键行如下：

```text
P2_4_HW: fixture ready=1 dir=1 package=1 decoy=1 bytes=430
P2_4_HW: browser path=/P2-4 rows=2 package_index=1 decoy_visible=0
P2_4_HW: confirm current=20800 target=20801 kind=1 path=/P2-4/P2-4-FULL.ETU
P2_4_HW: result success=1 progress=100 kind=1 target=20801 error=none
```

这些行证明真实 MCU LVGL/SdFat 路径完成目录和文件创建、`.ETU` 大小写过滤、
`.txt` 排除、版本对比、二次确认、SD 两遍 staging 和 full candidate 校验。
本卡停在 `CANDIDATE READY`，未写 BCB/重启，符合 P2-4/P2-5 边界。

取证后已完全删除临时包字节、自动选择/确认回调、RTT 专用输出和直达页面入口；
生产 `App.cpp` 已恢复唯一 `manager.Push("Pages/Startup")`，并重新完成 AC5、
模拟器和 GCC 构建。

最终生产 AC5 bin 又以 `2.8.0 / 20800` finalize 后回刷板卡：镜像
`586492B`，SHA-256
`F601F2880F7ADAD2FA61759499DE423ED5F0AC3FCB9C3194D5334D53DF84C07F`，
`verifybin` 通过。初次 2.5 秒探针采样时 Boot 尚未完成 handoff，未将该瞬态
当作恢复成功；继续运行后的单 logger 取得：

```text
OTA: HANDOFF vtor=0x08010000 primask=0 basepri=0 faultmask=0 control=4 ...
Reset: NRST SW
QSPI: JEDEC=0xEF4018 whitelisted, OTA enabled
OTA: BCB already CONFIRMED vcode=20800
```

该生产恢复日志 SHA-256 为
`6BC7F5D762D76EBCC0CCD449E5968716702384CB18E0A9C9AAB314E0A8C354B6`，
不含任何 `P2_4_HW` 行。随后无复位 halt 探针得到
`PC=0x08048AB4`、`VTOR=0x08010000`、`CFSR=0x00000000`，确认设备最终稳定
运行生产 App。

## 6. 最终静态审计

最终检查结果：

```text
git diff --check + untracked text check  PASS
frozen OTA docs                         UNCHANGED
P2-3 implementation/evidence files      UNCHANGED
RTE_Components.h                        UNCHANGED
Keil legacy/App new-source counts       0 / 3
Keil XML + actual dep --cpp11            PASS
App lnp three new objects                PASS
simulator XML parse/unique entries       PASS
font_cn_16 required characters           missing=0
debug harness/shadow/custom draw         absent
BCB/backup/reset/CONFIRMED markers       absent
production entry                         Pages/Startup
production board restore                 remediation did not flash; prior independent probe retained
residual simulator/RTT logger processes  0 / 0
```

结论仅限“实现与本地取证完成，等待非实现会话独立验收”，不自行宣布 P2-4
独立验收通过。

## 7. 独立验收打回后的整改

### 7.1 二次确认绑定实际导入包

- `Session::Inspect()` 不再只读 64B 头：它在同一打开文件上计算整包 SHA-256，
  仅在头校验、长度稳定和整包哈希全部成功后，保存一次性确认快照：LVGL 全路径、
  精确长度、已展示的包头信息和整包 SHA-256。
- `Session::Begin()` 要求调用路径与快照路径完全一致，并先比较重开文件的实时长度
  与已展示头信息；它不再用重开文件的 `transfer.info` 覆盖确认页信息。正确路径的
  begin 尝试会消费快照，失败后必须重新选择并确认。
- `ota_sd_transfer_begin()` 接收确认时的期望 SHA-256。第一遍完成后，整包 SHA
  必须与确认快照一致，才允许调用 `ota_staging_begin()`；因此同路径被替换成另一
  个同长度、头字段仍合法的包时，返回 `OTA_SD_ERR_FILE_CHANGED`，且 staging
  擦除次数为 0、commit marker 保持擦除态。

### 7.2 两遍读取期间长度变化 fail-closed

- `ota_sd_reader_t` 新增实时 `size()` 回调；LVGL 实现通过当前文件的
  `LV_FS_SEEK_END`/`lv_fs_tell()` 取长度并恢复原读位置。模拟器 PC driver 与 MCU
  SdFat driver 均已静态核对支持该语义，且目标侧已有同类调用。
- 状态机在传输 begin、每个 UI 工作步、第一遍转 staging 前、第二遍结束及
  marker-last finalize 前核对实时长度。读失败时也会复查长度，以便把截断明确归类
  为 `OTA_SD_ERR_FILE_CHANGED`。
- 回归在第一遍结束后分别把 reader 长度增加 1B、减少 1B；两例均返回
  `file_changed`，commit marker 保持 `0xFFFFFFFF`，不再出现追加后 `staged`。

### 7.3 整改验证边界

- 宿主：`29/29`，`-Wall -Wextra -Werror`。
- GCC App：零 error，仓库既有 warning 仍存在并如实记录；FLASH `594888B`，
  RAM `291528B`。
- AC5 App：受影响源精确重编、armlink/fromelf 均为 0，编译器无 warning 输出；
  最终 Program Size 与哈希见 §4.2。
- 模拟器：最终 exe 重建，两次启动均响应、未挂起、无残留，真实 Startup 截图已
  目视检查。
- 本次整改没有重新植入真机 SD harness，也没有烧录新产物；原始真机链仅作为
  既有支持证据，仍由后续独立复验决定是否需要补跑。P2-4 保持 `进行中`，P2
  保持 `3/6`。

## 8. F3：MCU SdFat 句柄缓存二次整改

### 8.1 根因关闭

独立整改复验指出，§7.2 对 MCU `LV_FS_SEEK_END` 的判断不成立：SdFat
`FatFile::seekEnd()` 和 `fileSize()` 都读取打开句柄缓存的 `m_fileSize`，不能发现
另一写入者在第一遍后对目录项执行的追加或截断。

本轮只改 `OtaUpdate::Session` 文件适配层，不改 `ota_sd` 状态机、P2-3 或冻结契约：

- `OpenSelectedFile()` 在每个新句柄打开后读取一次该句柄的长度并恢复到偏移 0；
- `GetSelectedFileSize()` 保存当前逻辑偏移，先关闭旧句柄，再按 `selectedPath`
  重新打开；新 `SdFile` 会从目录项重新装载 `m_fileSize`；
- 新长度小于当前偏移时只将恢复偏移钳制到新 EOF，随后 `ota_sd` 按期望长度比较并
  返回 `OTA_SD_ERR_FILE_CHANGED`；
- 重开或恢复偏移失败时关闭当前句柄并返回读错误。拔卡、重挂载或路径失效后不会
  继续使用旧 SdFat 文件对象。

该处理同时刷新后续读取所用的主句柄，而不是只额外打开一个 stat 句柄。因此同长度
路径替换或重挂载后，第二遍读取也绑定到当前路径对象，最终仍受整包 SHA/CRC 比较
保护。

### 8.2 正式回归

新增：

- `tests/ota/test_ota_update.cpp`：直接编译真实 `OtaUpdate.cpp`；
- `tests/ota/stubs/lvgl/lvgl.h`：最小 LVGL FS 接口；
- `tests/ota/test_ota_update.py`：生成另一份同长度合法 full `.etu`，以
  `-Wall -Wextra -Werror` 构建并运行测试；
- `tests/ota/test_ota_sd.py`：官方 P2-4 入口现在串联核心测试与适配层测试，临时
  产物只写入仓库内 `.cache` 唯一目录并自动清理。

文件桩按 SdFat 语义实现：每个打开句柄缓存打开瞬间的长度和内容快照，底层路径变化
不会更新旧句柄。最终结果：

```text
P2_4_OTA_SD=PASS checks=29 failures=0
CONFIRM_REPLACE result=file_changed opens=8 closes=8
APPEND_1B result=file_changed error=stage:file_changed opens=15 closes=15
TRUNCATE_1B result=file_changed error=stage:file_changed opens=15 closes=15
SECOND_PASS_REPLACE result=file_changed error=stage:file_changed opens=19 closes=19
UNAVAILABLE result=read error=stage:read opens=14 closes=14
P2_4_OTA_UPDATE=PASS scenarios=5
P2_4_OTA_SD_ALL=PASS core_checks=29 adapter_scenarios=5
```

`UNAVAILABLE` 的 open/close 数相等，证明重开失败前旧对象已经销毁；该场景不会退回
缓存句柄继续走 marker-last。

### 8.3 构建与模拟器

- fresh GCC Release App：仓库内 `.cache/p2-4-f3-gcc-release` 全量配置并编译
  `379` 个步骤，rc=0；FLASH `594936B`、RAM `291528B`。存在仓库既有源码、
  newlib syscall、wchar ABI、RWX LOAD 与 CMake 长路径 warning，error 为 0；
  `OtaUpdate.cpp` 没有直接编译器诊断。bin SHA-256：
  `2AB4F89CCEB0773DA4C0732DA0E569C22C13E2CAEBBFDA68858B1D440E55D770`。
- AC5 `X-Track-App-AC5`：精确重编 `OtaUpdate.cpp` 后 armlink/fromelf rc=0，
  编译/链接无 warning 输出；`Program Size: Code=297188 RO-data=289372
  RW-data=1332 ZI-data=495432`。`Track-App-AC5.bin=587364B`，SHA-256：
  `63826BD6DCBE0950CC17F6C27C80DB718FA24A18930D034AD503D73B5C673EE9`。
- 模拟器先 `/t:Rebuild`，最终源码注释收口后再增量重编 `OtaUpdate.cpp` 并链接；
  fresh exe `5871104B`，时间戳 `2026-08-01 18:09:43.920`，SHA-256：
  `07FFFCFBF43E6C3A67C1BF48E295AB38E6A9AB9389C0F054ED327765C3F3D650`。
  构建有仓库既有 warning，error 为 0。
- 连续两次启动均为真实 `Pages/Startup` 的 `Loading` 电路动画，截图为
  `.claude/p2-4-f3-remediation-startup-1.png` 和
  `.claude/p2-4-f3-remediation-startup-2.png`，均已目视检查。运行状态分别为
  `Responding=True/Hung=False/WS=51.60MB/Private=88.27MB` 和
  `Responding=True/Hung=False/WS=52.39MB/Private=88.21MB`，残留进程 0。

### 8.4 边界与状态

- `PLAN-OTA.md`、`docs/ota-binary-contracts.md`、P2-3 实现/证据相对 HEAD 无
  变更；生产入口仍唯一为 `manager.Push("Pages/Startup")`；源码无
  `P2_4_HW`、`P2_4_REMEDIATION_HW` 或临时 `HardwareTest`。
- 本轮没有重新植入硬件 harness，也没有烧录新产物。板上继续保持独立验收 §7.6
  已恢复并验证的生产 App 状态。
- P2-4 继续保持 `进行中`，P2 继续保持 `3/6`。本节仅声明实现整改完成，等待新的
  非实现会话独立复验，不自行宣布验收通过。
