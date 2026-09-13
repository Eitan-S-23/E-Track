# P3-3 验收准入整改交付 —— 2026-09-12 批次（P3-3-IMPL-AUTH-20260912）

- 实现会话：Claude（P3-3 实现 agent，认领 `P3-3-IMPL-20260907` 不变）。
- 复核基线：`c89c58f44dec1745980f0f2a54e612af48f6d32c`（非审批 freeze_commit）。
- 授权：`docs/ota-prompts/prompt-P3-3-implementation.md`「2026-09-12 批次」章。
- 性质：**实现侧整改与开发自测交付，不是正式验收**。四类结果分开陈述：
  源码整改（§1）、开发自测（§2）、构建验证（§3）、独立验收（**NOT_RUN**，§4）。
- 执行 worktree：`D:\github\my\E-Track\.cache\worktrees\p3-3-admission`
  （独占），分支 `dev/flutter/apk/p3-3-admission`。

## 0. 提交链（含稳定提交与真实构建结果）

| 提交 | 内容 | 对应整改项 |
| --- | --- | --- |
| `b3f7a05` | 治理稿整合（任务书 2026-09-12 批次章、OTA-DEC-013、开发验证指南、政策回归、看板/研究记录） | 批次授权第 3 项 |
| `d98d978` | 观测 URL 编码凭据键校验绕过修复（规范化 query 后校验 + 公开端点白名单） | OBS-SEC-01 |
| `2c2b5f0` | 观测三结局区分（scan_not_started / scan_stream_error / target_not_seen）、唯一终止闸门、target 地址插值 | OBS-01/02/03 |
| `c1e4051` | 中止四阶段插桩（决定→停业务写→ABORT 收尾→终态发布）+ 延迟 ABORT 反例测试 + 操作单计时口径修正 | RC3-07/02 |
| `ee0266c` | B1-M 台账对账（三次写已用 3/剩余 0、失败轮时间线、设备副作用与授权来源审计） | OPS-01 |
| `e1edd9e` | 测试 const 修复第一轮（BluetoothDevice/StateError） | CI 整改 |
| `095421d` | 测试 const 修复第二轮（AdvertisementData 非 const 构造） | CI 整改 |
| `1e641f1` | build.yml Gradle 8.12→8.14 与 wrapper 对齐 | 构建基建整改 |
| `ab6ce3b` | scan_start_timeout 断言对齐带 waitedMs 的终止行格式 | CI 整改 |

**稳定提交 = `ab6ce3b5bab8bcb357e8a687b7bb099ab1a0ce0d`**（其后无源码/测试/workflow 改动）。
真实构建结果绑定该提交：dev-checks run 34730007317（双宿主全绿 + debug APK）、
build.yml run 34730618341（release APK + Windows 完整运行包，见 §3）。

## 1. 七项整改逐项交付

### 1.1 OBS-SEC-01：观测 URL 凭据参数校验绕过

- **真实改动**（`d98d978`）：观测 URL 安全校验从「检查原始 query 字符串是否含
  `token`/`signature` 等键名」改为「先按 RFC 3986 规范化解析 query（百分号解码、
  重复参数展开），再对每个解码后的键做凭据键匹配；同时引入公开端点显式白名单，
  只有白名单端点允许无凭据参数」。
- **负例鉴别力**：`%74oken`（编码绕过）、`sign%61ture`（编码绕过）、`Token`
  （大小写绕过）、重复 `?token=...&token=...`、`access_token` 别名均被拒绝；
  无凭据的公开端点（`/api/public/latest` 等）仍可用。反例已固化为
  `test_flutter_dev_checks.py` 的真实 runner 回归。
- **自测证据**：宿主回归 `tests/ota/test_flutter_dev_checks.py` 全绿；
  CI run 34730007317 ubuntu/windows analyze+test 全绿。
- **未覆盖项**：无真实网络负例（无凭据 URL 指向真实服务）；本地无 dart SDK，
  analyze 依赖 CI。

### 1.2 OBS-01：扫描启动失败/流错误/未见目标三结局区分

- **真实改动**（`2c2b5f0`）：`BluetoothService.startObservationScan` 复用生产
  `startScan` 路径，真实转发平台启动拒绝（不再无条件 return true）与扫描流
  onError；observer 据此区分 `scan_not_started`（平台拒绝）/`scan_stream_error`
  （流错误）/`target_not_seen`（窗口到期未见目标）三个互斥终态。
- **负例鉴别力**：`bluetooth_service_observation_scan_test.dart` 四用例经
  **真实接线**（`_ScanProbeAdapter` 实现 `BluetoothAdapter` 契约 + 真实
  `BluetoothService`）验证：平台抛异常→`scan_not_started` 且不开窗口；流
  addError→`scan_stream_error`；正常空扫描→`target_not_seen` 且停扫；目标
  命中→绑定链路真实走通（connect 返回 false→`connect_failed`）。
- **自测证据**：CI run 34730007317 全绿（该测试文件全部通过）。
- **未覆盖项**：真机 BLE 栈的实际错误形态（本批无真机额度）。

### 1.3 OBS-02：观测 runner 唯一终止与有界结局

- **真实改动**（`2c2b5f0`）：`OtaDeviceObserver` 增加终态闸门（`_settled` 后
  任何迟到回调不再发终态/开窗/绑定）；启动、停扫、连接、身份读取、清理均
  有有界超时结局（`startTimeout`/`connectTimeout`/`identityTimeout`），迟到
  完成不得覆盖终态。
- **负例鉴别力**：`ota_device_observation_test.dart` 注入永不完成的
  `startScan`（超时收尾）、迟到的 connect 完成（终态不被覆盖、不再读身份）、
  迟到的启动完成（不再开窗）、清理钩子自身抛异常（不覆盖终态）、stopScan
  抛异常（终态行仍在）。
- **自测证据**：同上 CI 全绿。
- **未覆盖项**：native 操作未物理取消的边界在文档中如实声明（Future.timeout
  ≠ native 已取消），真机回收行为待实机验收。

### 1.4 RC3-07/02：中止计时四阶段区分

- **真实改动**（`c1e4051`）：单调时钟插桩拆为 `MONO_TERMINAL_DECIDED`（service
  侧决定）→`MONO_WRITE_STOP`（业务写停物理边界）→`MONO_ABORT_BEGIN/DONE`
  （ABORT 收尾）→`MONO_TERMINAL`（终态发布）；操作单 §1.2 修正为「30s 窗口
  判 FAIL_AT（中止决定），收尾时长单列观测不设门槛」，废除旧「`MONO_TERMINAL −
  锚点 < 30s`」无来源表述。
- **负例鉴别力**：延迟 ABORT 反例测试——旧打点在 FAIL_AT 即宣告终态，新插桩
  在 ABORT 收尾后才落 `MONO_TERMINAL`，测试断言两者的 monoUs 差可被识别。
- **自测证据**：CI 全绿；操作单口径修正提交 `ee0266c` 一并落盘。
- **未覆盖项**：真机 30s 无 durable 进展实测（A1 配额未消耗，待非实现会话）。

### 1.5 OBS-03：target 日志地址插值

- **真实改动**（`2c2b5f0`）：`OTA_OBS target` 行的地址从对象默认 toString 改为
  显式 `device.remoteId.str` 插值；断言完整 target 行含 `addr=AA:BB:CC:DD:EE:FF`
  并与 connect/readIdentity 收到的地址一致，不只断言 `matched_by`。
- **自测证据**：CI 全绿（第四用例显式断言地址行与绑定结局）。

### 1.6 OPS-01：B1-M 台账对账与边界审计

- **真实改动**（`ee0266c`）：`P3-3-batch9-device-observation-sheet.md` §6.4
  配额表改已用 3/剩余 0；新增 §6.5 四小节：额度对账（r9/r20/r21 三次真实写）、
  25 目录时间线（整段 r1→r21 约 2h20m，报告的 58min 是 r9→r21 段，均如实
  保留）、设备副作用 5 行清单（logcat -c 违反操作单明令、ui.xml 覆盖、
  am force-stop、UI 自动化、APK 既有安装非本会话动作）、授权来源审计（主
  授权仅仓库内转述锚点、四类设备动作无锚点不追认）。原始日志未重写。
- **自测证据**：逐项引用原始产物（`runs/*/peripheral.log` stat、
  `b1m_connect.py` 源码、r1 `identity.md`）交叉核实，无自述采信。
- **未覆盖项**：原始聊天记录授权原文未入库（标缺失）；影响裁定留给非实现会话。

### 1.7 ADMIT-01/02/03：验收准备材料（见 §4-§8）

## 2. 开发自测（flutter-dev-checks）

| 项 | 值 |
| --- | --- |
| 稳定提交 | `ab6ce3b5bab8bcb357e8a687b7bb099ab1a0ce0d` |
| run | https://github.com/Eitan-S-23/E-Track/actions/runs/34730007317 |
| 结论 | **completed success**（ubuntu + windows 双宿主） |
| 范围 | `test_scope=all`（包 analyze + 全部单测/widget 测试）+ `build_apk=true` |
| analyze | ubuntu "No issues found! (ran in 15.3s)"；windows 同绿 |
| 测试 | ubuntu 全过 + debug APK 构建；windows 全过 |
| debug APK | `trace-dev-debug.apk`，131,513,046 B，SHA-256 `bb7ac4db15cc547f2cf7eb52b9b7cd6d694d4724c5fb8137421260505866633b`，`release_signing=false`，application_id `com.wen.gaia.gaia`，formal_acceptance=NOT_RUN |

宿主回归（本机，无 SDK 只跑 Python 入口）：

| 命令 | 结果 |
| --- | --- |
| `python -B tests/ota/test_flutter_dev_apk.py` | OK |
| `python -B tests/ota/test_acceptance_bundle.py AcceptanceExecutionPolicyTests PostP26SpecGovernanceTests` | OK（27 tests） |
| `python -B tests/ota/test_flutter_dev_checks.py`（本 worktree） | 1 error —— **环境性**：fixture 路径前缀（`.cache/worktrees/p3-3-admission/...` + 用例名 + fixture 子路径）超 Windows MAX_PATH 260，`git hash-object --stdin-paths` 报 `Filename too long`。同一代码在主 worktree（短路径）**50/50 全绿**；`dev_checks.py` 与该测试文件本批零改动。不修产品代码绕过。 |

CI 迭代过程（原始失败→修复，均有据）：

1. run 34728176600（e1edd9e 前）：analyze 红——3 处 `const_with_non_const` + 3 处 prefer_const → 修复 `e1edd9e`。
2. run 34728553672（e1edd9e）：analyze 仍红——analyze.log 证实列 26 指向 `const AdvertisementData(`（flutter_blue_plus 1.35.5 该构造器非 const），上轮误判 → 修复 `095421d`。
3. run 34729715805（1e641f1）：analyze 绿，测试 1 失败——`scan_start_timeout` 断言未含 `waitedMs=50` 后缀 → 修复 `ab6ce3b`。
4. run 34730007317（ab6ce3b）：**全绿**（终态）。

## 3. 构建验证（build.yml，build-only 授权 3 次已用 3）

| 项 | 值 |
| --- | --- |
| 终态 run | https://github.com/Eitan-S-23/E-Track/actions/runs/34730618341（`ab6ce3b`） |
| 结论 | **completed success** |
| Build Android APK | success：Flutter 测试 319 passed/7 skipped（Linux skip 不计入 Windows 证据）；`app-release.apk` 46.7MB；Gradle 8.14（run 日志确认下载 gradle-8.14-bin.zip） |
| Build Windows EXE | success：Flutter 测试 326 passed；`ble_monitor.exe` 构建成功，完整运行包 zip 20,348,747 B |
| Deploy GitHub Pages | **skipped**（核对通过：manual dispatch 时 docs_changed=false） |
| Create GitHub Release | **skipped**（核对通过：publish_release=false） |
| 签名 | `android_release_signing_present=false`、`sideload_signing_present=false` → **release 模式 + debug 签名回退**（如日志所述 "falling back to debug signing"），不是固定生产签名 |

产物身份（下载到本机 `.cache-ci/` 复核后删除，避免大文件入库）：

| 产物 | size | SHA-256 |
| --- | --- | --- |
| `ble-monitor-android.apk`（release 模式，debug 签名） | 46,682,620 B | `2a5d5db991bf764afde0fd1b77eaee22b730a3c80cf81e0c51c66188ce4ac71b` |
| `ble-monitor-windows.zip`（完整运行包） | 20,348,747 B | `8bbbbea4f3eba6d73749c492a3df668b3fcbf2d55d6f507b4e450a1d72cac4ab` |
| `ble-monitor-windows.exe`（裸 exe，仅参考） | 93,184 B | `62dcecffcc7992d177733175b87032384c981ebeaf2c1a17ec6944f5eac8500e` |
| artifact zip（Android，上传侧） | 25,504,280 B | `1917f7c1a0252933b7f0c4675a028f69f3a47923545a599dacbabd0b82f30235` |
| artifact zip（Windows，上传侧） | 20,379,690 B | `a1f03b319aa95cc014b4d7c05f973cfb5aebac553dd2b620103f9d5a6eac6405` |

build.yml 修复：`1e641f1` 把 setup-gradle 与 `gradle wrapper` 两处硬编码 8.12
对齐到仓库 wrapper 的 8.14（e104022 升级，Flutter 3.47.4 最低要求）。首跑
34728280674 的 Android job 因此红（"Gradle version (8.12.0) is lower than
Flutter's minimum supported version of 8.14.0"）；第 2 轮 34729730300 验证
Gradle 阶段已过（红在同批 const 断言）；第 3 轮全绿。

warning/error：Flutter analyze 无 issue；构建日志无 error；debug 签名回退
提示 1 处（如实记录，见上表签名行）。

## 4. 独立验收状态：NOT_RUN

正式验收保持 **NOT_RUN**：无审批冻结合同、无 EXECUTED PASS/REUSED、无实机
操作。本批交付的合同/矩阵为**草案（DRAFT）**，冻结与执行由非实现会话审批。

## 5. ADMIT-01：正式验收合同草案

草案文件：`docs/acceptance-contracts/P3-3-v1.contract.json`（DRAFT）、
`docs/acceptance-contracts/P3-3-v1.evidence-matrix.json`（NOT_RUN 全项）。
结构与 schema 遵循 `etrack-acceptance-contract-v3` / `etrack-evidence-matrix-v2`。

### 5.1 判据框架（OTA-DEC-013 方案 A 的三类实机证据）

| 判据 | 内容 | 状态 |
| --- | --- | --- |
| C-APK-INSTALL | 受验 release APK 在实际 Android 手机实际安装并启动；记录包名/版本/设备/系统/安装结果/APK SHA-256；参与传输的必须是同一 APK | NOT_RUN（缺真机授权） |
| C-TOY-LOOP | 可启动受控 toy 包经手机 App→BLE→MCU 完整升级闭环；共同终点=重启后新连接 GET_INFO 的目标 versionCode 与完整 raw SHA-256 一致 | NOT_RUN（缺可启动 toy 资产+真机授权） |
| C-REAL-LOOP | 真实固件 OTA 包同上闭环；不得由 toy 代替 | NOT_RUN（缺真机授权） |

共同成功终点（两判据共用）：真实 `OtaService` 完成 INFO/latest/下载/长度与
整包 SHA 校验/BEGIN/DATA/END；MCU 确认 `durable_off == total_len` 且
`ACK_END` 成功；升级、重启、新连接 `GET_INFO` 的 versionCode 与 raw
SHA-256 与冻结目标镜像一致。GATT 写成功、UI 100%、END ACK、仍运行旧固件
均不足以通过。

### 5.2 缺口清单（如实，不填 PASS）

| 缺口 | 说明 |
| --- | --- |
| `freeze_commit`/`freeze_tree`/`profile_config_blob` | 草案为零值占位。冻结时必须绑定审批时刻的实际实现提交（≥`ab6ce3b`），由非实现会话填入并校验真实 git OID |
| 审批人/审批时间 | 空。未获得用户对 P3-3 正式合同的审批 |
| 受控 HTTP 测试服务 | 未部署。P4-2 未就绪时按任务书可用「版本化、符合冻结共享合同的受控 HTTP 测试服务」作为显式外部输入；服务部署需自身授权，本批未申请 |
| 可启动 toy 固件包 | **现无**。`tests/ota-vectors/` 的 golden vectors（见 §7.1）不具上板资格。需按任务书「经审定、保留真实 Boot/BCB/OTA 路径且具有合法 fw_header/向量的可启动受控固件包」另行构建/审定——由非实现会话在合同审批时一并裁定资产准入 |
| 真机操作授权与配额 | APK 安装、BLE 连接/注错、J-Link、断电等全部未授权（见任务书「未授予的操作与停止边界」）。B1-M 三次写已用尽，A1 1 次未消耗，均不覆盖升级闭环 |
| 设备/Boot 身份绑定 | 板侧身份已有只读证据（§6），手机侧序列号已知（§6.2），但「参与传输的同一受验 APK」尚不存在（release APK 为 debug 签名回退，非固定生产签名——安装可用性不受影响，但正式受验资产须在合同中绑定其确切 SHA 与签名类型） |

## 6. ADMIT-02：设备/Boot 身份与 runner 依赖

### 6.1 目标板（AT32F435，只读证据，2026-09-12）

来源：`docs/ota-exec-notes/P3-3-t1a-jlink-board-identification-2026-09-12.md`（全程只读，未烧录/未写寄存器/未 RTT 下行）。

| 项 | 值 |
| --- | --- |
| MCU | AT32F435RGT7（Cortex-M4 r0p1，CPUID `0x410FC241`） |
| 板上 Boot | = 磁盘 `X-Track-Boot.bin`（16KB 转储逐字节一致，boot 本体 14724 B） |
| 板上 App | = 磁盘 `X-Track-App-GCC.bin`（`0x08010000` 基址；finalize 头双零法全镜像 SHA `d97534841302c16d…1f7401dd` 重算一致） |
| 固件版本 | `3.2.0`（version_code 30200），build_ts 2026-09-02 18:56:08 UTC |
| fw_header 字段 | hw_rev=1、layout_id=1、min_boot_ver=1、image_len=602984 |
| 复位原因 | NRST POR |
| QSPI | JEDEC `0xEF4018`（Winbond 128Mbit），已白名单、OTA enabled |
| BCB | CONFIRMED vcode=20801（2.8.1）——与镜像头 3.2.0 不一致，正式验收前需裁定如何核对目标版本（如实记录，不自行解释） |
| 目标板 MAC | **未取得**（不产生 BLE 观测的只读轮次拿不到） |
| 运行态 | 应用全速运行（SysTick 增量 402-404ms/400ms 窗），RTT 存活但应用静默 |

### 6.2 测试手机（B1-M r1 identity.md，2026-09-11）

| 项 | 值 |
| --- | --- |
| 序列号 | `10ADA4197U001CK` |
| 机型 | vivo V2312A（product PD2312），Android 13（SDK 33） |
| 既有应用 | `com.wen.gaia.gaia` 1.0.60（versionCode 86，release），APK SHA-256 `428a5d3a…`，firstInstall 2026-06-30 |
| 注意 | 既有安装是 B1-M 之外的历史动作；正式验收须按合同安装**受验 APK** 并重记身份 |

### 6.3 PC 蓝牙适配器（外设侧，仅 B1-M harness 用）

device_id `\\?\USB#VID_2C0A&PID_8761#00E04C239987…`（来源 capcheck.py 实测）。
正式验收的 BLE 主路径是手机→MCU，不依赖该适配器。

### 6.4 runner 依赖（正式合同 commands 须绑定）

| 依赖 | 说明 |
| --- | --- |
| GitHub Actions 临时 runner | dev-checks/build.yml 均为 GitHub 托管；SDK Flutter stable 3.47.4（run 日志 cache key `flutter-pub-*-stable-3.47.4-x64-*`） |
| Gradle | 8.14（build.yml 已对齐 wrapper；dev 路径由 `dev_apk.py:android_versions()` 从 wrapper properties 读取） |
| 本机 Python 入口 | `tests/ota/test_flutter_dev_apk.py`、`tests/ota/test_flutter_dev_checks.py`、`tests/ota/test_acceptance_bundle.py`（宿主回归，无需 dart SDK） |
| 验收校验器 | `Tools/acceptance/validate_bundle.py`（v3 语义：FROZEN 需审批字段+真实 OID；NOT_RUN 矩阵做执行前检） |
| 真机侧 | adb（只读身份核对）、J-Link（AT32F435RGT7 全名/SWD 1000kHz，既有防坑清单）、logcat 采集（受控、不清缓冲）——正式执行时按合同逐项绑定 |
| profile 覆盖 | Flutter profile 含 `app/bluetooth_flutter_Trace/{lib,android,windows,assets,…}/` + `pubspec.{yaml,lock}` + `.github/workflows/build.yml`；生产固件输入在 Production profile。合同冻结时按 `Tools/provenance/manifest_profiles.json` 引用 |

## 7. ADMIT-03：安全资产清单（toy/真包，独立来源与身份）

### 7.1 golden vectors（**不具上板资格**，仅解析/拒绝测试）

| 资产 | size | SHA-256 | 内容 |
| --- | --- | --- | --- |
| `tests/ota-vectors/toy-old.bin` | 4,096 B | `3081fa0afc5bb2f3a7d456a249cd8f07d9517d257e581e9562bf3eb102eadb1b` | v2.7.0（20700），gen_vectors.py 生成 |
| `tests/ota-vectors/toy-new.bin` | 4,096 B | `f68f357c708c2d65…`（expected.json 全量哈希见该文件） | v2.8.0（20800） |
| `tests/ota-vectors/toy-full.etu` | 748 B | `d8e26e51cf574570d69842b6dcc926c7becb2f050a2f996702c1075fc1617bfc` | full 包：target_vcode 20800、alg 1、key 1、payload 684B |
| `tests/ota-vectors/toy-patch.etu` | 213 B | `bf1ac6c9708110b4c100b62e7d735e493a22c2a6e89cd24594427ef80663eb6e` | patch 包：base 20700→target 20800、payload 149B |

**边界声明（任务书原文约束）**：这些 golden vectors 仅凭名称或解析通过不能
证明可启动；不满足条件的向量只用于对应解析/拒绝测试，**不得直接刷入并要求
启动，不得旁路完整性、防错板或防降级检查来制造成功**。C-TOY-LOOP 判据所需
的「可启动受控固件包」是**独立资产**，须由非实现会话审定后才进入合同。

### 7.2 真包候选（存在但未封包）

| 资产 | size | SHA-256 | 来源 |
| --- | --- | --- | --- |
| `X-Track-App-GCC.bin`（真包原始镜像候选） | 602,984 B | `7328c1b15feff7214378065ca3e7d556ac803b59ebed7029a892d64f15e2153f` | 主 worktree 2026-09-03 构建 @ `c89c58f`，即 §6.1 板上实测固件的原镜像 |

- 该 `.bin` 是板上正在运行的固件镜像（finalize 前形态，头区 `0xFF` 占位）。
  生成可上板的 `.etu` 需要 `Tools/etu_pack.py` 封包（AES key_id/alg、target
  versionCode、兼容字段），封包产物身份须在合同中另行绑定。
- **可启动依据**：板上实机运行中（§6.1 运行态证据）——真包「升级后可启动」
  的目标镜像若选该版本，则目标镜像自身可启动性已有实机证据；升级链路仍需
  实机闭环证明。
- **升级目标版本缺口**：真包闭环要求升级到「目标 versionCode + raw SHA 与
  冻结目标镜像一致」。当前板上已是 3.2.0（30200）；若目标=当前版本则无法
  体现升级（防降级/同版本刷写需合同裁定），若目标=更新版本则该版本镜像尚
  不存在。**此缺口留给非实现会话在合同审批时确定目标版本与对应镜像**。

### 7.3 受验 APK 候选（本批产物，见 §3 产物表）

`ble-monitor-android.apk`（46,682,620 B，SHA-256 `2a5d5db9…`，release 模式
debug 签名回退）。固定生产签名未配置（secrets 缺失），正式合同须明确接受
该签名类型或先配置签名——如实记录，不冒充固定签名。

### 7.4 HTTP 服务输入

正式合同可用「版本化、符合冻结共享合同的受控 HTTP 测试服务」作为显式外部
输入（任务书授权范围）。要求：APK 经受控配置发真实 HTTP latest/下载请求，
不旁路 latest/兼容/token/摘要检查，不把包直接注入 service 状态；绑定测试
服务/fixture 身份并标注**不宣称真实 P4-2 register/R2/D1 链已通过**。服务
部署或远端写入需自身授权——本批未部署。

## 8. 剩余授权配额

| 授权 | 额度 | 已用 | 剩余 |
| --- | --- | --- | --- |
| build.yml build-only | 3 | 3（34728280674 / 34729730300 / 34730618341） | **0** |
| acceptance-governance dispatch | 3 | 1（34728291114，绿） | 2 |
| flutter-dev-checks（持续预授权） | — | 本批 4 次（均有修复/输入变化依据） | 不限（按 §7.3.2 规则） |
| 真机操作 | 0 新增 | — | **0**（B1-M 3/3 用尽；A1 0/1） |

## 9. 移交非实现会话的事项

1. 审批/冻结 `P3-3-v1` 合同：填 `freeze_commit`/`freeze_tree`/
   `profile_config_blob`（真实 OID）、审批人/时间，跑
   `validate_bundle.py` 执行前检（FROZEN + NOT_RUN）。
2. 裁定可启动 toy 资产准入与真包目标版本（§5.2、§7.2 缺口）。
3. 裁定 BCB vcode 20801 与镜像 3.2.0 不一致的核对口径（§6.1）。
4. 审批实机操作授权与配额（APK 安装/连接/升级闭环/J-Link/断电），按执行
   合同阶段化执行。
5. 裁定 B1-M 越界动作（logcat -c 等，§1.6）对既有证据的影响。
6. 决定受控 HTTP 测试服务的部署与身份绑定（§7.4）。

## 10. 会话边界声明

- 本会话未执行任何真机操作、未烧录、未写任何设备状态；未合并、未发布、
  未部署、未创建 release/tag/candidate。
- 大文件产物（APK/EXE/zip）下载到项目内 `.cache-ci/` 复核哈希后已删除，
  不入库；仓库内无新增大文件。
- 开发自测与构建验证通过**不等于**正式验收；P3-3 看板保持「进行中」、
  认领不变，正式验收 NOT_RUN。
