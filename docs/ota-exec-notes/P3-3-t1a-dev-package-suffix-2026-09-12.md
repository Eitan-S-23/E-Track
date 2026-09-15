# P3-3 T1a 载体方案乙：调试包独立包名（显式启用）—— 2026-09-12

> 依据：`docs/ota-exec-notes/P3-3-batch9-device-observation-sheet.md` §2.2 第 3 项、
> `docs/ota-exec-notes/P3-3-t1a-instrumentation-and-a1-gap-2026-09-11.md` §9.2/§9.5。
> 裁定：用户 2026-09-12 选定**乙**（"用乙吧"）。
> 本报告只覆盖载体改动与本地回归；**未安装、未连接目标板、未做 BLE 通信、未停机**。
> 正式验收保持 `NOT_RUN`；A1 配额 1 次**仍未消耗**。

## 1. 问题与目标

上一轮实测：dev debug APK 与手机已装发布版同为 `com.wen.gaia.gaia`，签名不同
⇒ `INSTALL_FAILED_UPDATE_INCOMPATIBLE`，无法安装（§9.2）。设备侧弹窗确认
不能绕过该检查。

乙方案：让**调试产物**使用独立 application id（`com.wen.gaia.gaia` + 后缀），
与发布版共存。约束（均为用户既有裁定）：

- **显式启用、默认不变**：不设置即与既有行为逐字节等价。
- **不碰任何密钥**、不改生产工作流、不卸载、不清数据。
- 启用后取值非法必须**尽早失败**，不得产出"看似可用"的假阳性产物。

## 2. 改动清单（提交 `f68884c`，分支 `dev/flutter/apk/p3-3-t1a`）

| 文件 | 改动 | 作用 |
| --- | --- | --- |
| `app/bluetooth_flutter_Trace/android/app/build.gradle.kts` | +23 | 仅 `debug` 构建类型、仅当 `TRACE_DEV_APP_ID_SUFFIX` 非空时设 `applicationIdSuffix`；取值不匹配 `^\.[A-Za-z][A-Za-z0-9_]*$` 直接 `error()` |
| `.github/workflows/flutter-dev-checks.yml` | +7 | 新增 `workflow_dispatch` 输入 `app_id_suffix`（默认空），经 job `env` 透传为 `TRACE_DEV_APP_ID_SUFFIX` |
| `Tools/flutter/dev_apk.py` | +61/-10 | `prepare` 校验后缀并记录期望 application id；`collect` 用 aapt2 从产物读取真实 application id 并比对，不符即失败 |
| `tests/ota/test_flutter_dev_apk.py` | +73/-10 | 后缀取值校验（含真实构建配置）、环境透传、产物身份读取与不一致拦截 |

### 2.1 默认行为不变的证据

- `env` 表达式 `${{ inputs.app_id_suffix || '' }}`：push 触发时 `inputs` 为空
  ⇒ 环境变量为空串 ⇒ Gradle 侧 `isNotEmpty()` 为假 ⇒ **不加后缀**，与改动前一致。
- `dev_apk.py` 只在显式非空时校验/比对；空值时期望值 = `build.gradle.kts` 中
  唯一 `applicationId` 字面量。
- 回归用例 `test_debug_application_id_suffix_is_explicit_and_validated` 对**真实**
  构建配置断言：`expected_application_id(ROOT, "") == "com.wen.gaia.gaia"`、
  `expected_application_id(ROOT, ".obs") == "com.wen.gaia.gaia.obs"`。

### 2.2 为什么在 CI 里读产物身份（而不是只信构建意图）

后缀只由 Gradle 应用，workflow 与 helper 都无法断言它真的生效。若只记录"打算
启用"，就可能在"实际仍是生产包名"的情况下产出被当成可共存的产物。因此
`collect` 阶段用 `aapt2 dump badging <apk>` 从 **APK 自身**读取 `package:` 行，
与期望值比对；不一致则**不写 artifacts、不出元数据**并返回非零，`apk_result=FAIL`。

元数据新增 `application_id` 字段，供后续追溯该产物实际身份。

## 3. 本地回归（非构建检查，允许范围）

| 命令 | 结果 |
| --- | --- |
| `python -B tests/ota/test_flutter_dev_apk.py` | `Ran 19 tests ... OK` |
| `python -B tests/ota/test_flutter_dev_checks.py` | `Ran 50 tests ... OK` |

两条都在本机（Windows，无 SDK、不触发任何构建）执行；用例本身是离线 fixture，
不下载 Gradle、不调用 Flutter/Gradle。

## 4. CI 证据

全部运行使用同一工作流 `.github/workflows/flutter-dev-checks.yml`，仓库
`Eitan-S-23/E-Track`，SDK 通道 `stable`、Flutter `3.47.3`
（`frameworkRevision e8113bf45620cbeb8aff64947ee4c93e16adb4cf`、Dart `3.13.3`）。

| # | run id | 触发 | 提交 | 后缀 | 结论 | 产物 `application_id` |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `34625637734` | push | `f68884c2` | 空 | success | `com.wen.gaia.gaia` |
| 2 | `34625661886` | dispatch | `f68884c2` | `.dev` | **failure** | 未产出（见 §4.2） |
| 3 | `34625874627` | push | `24d86311` | 空 | success | `com.wen.gaia.gaia` |
| 4 | `34625885805` | dispatch | `24d86311` | `.dev` | success | `com.wen.gaia.gaia.dev` |

运行 3/4 是修复后的正式证据；运行 1 作为修复前的默认行为旁证；运行 2 是 §4.2
记录的失败，保留不删。

### 4.1 逐运行结果

**运行 3 — `34625874627`（push，默认无后缀）**
<https://github.com/Eitan-S-23/E-Track/actions/runs/34625874627>

- Linux 宿主：`development_result=PASS`、`scope=all`、`apk_requested=True`、
  `apk_result=PASS`、`lockfile_unchanged=True`、`source_after_restored.clean=true`。
- 测试：`01:32 +289 ~7: All tests passed!`；分析：`No issues found! (ran in 15.1s)`。
- `apk_collect.log`：
  `{"commit": "24d863114afd608ea79f864afac1662c16c44b5b",
  "sha256": "62141ebfadf55ca9d57eb0d4d71c9344592d447bf085188af027dec0b352783d",
  "bytes": 131488170, "release_signing": false,
  "application_id": "com.wen.gaia.gaia", "formal_acceptance": "NOT_RUN"}`
- Windows 宿主 `Windows-2022Server-10.0.20348-SP0`：`development_result=PASS`、
  `apk_requested=False`、`apk_result=NOT_REQUESTED`。
- `apk_verify.log`：v2 方案 `true`、v1/v3/v3.1/v4 `false`、`Number of signers: 1`
  —— 与 `release_signing=false`（debug 签名）一致。

**运行 4 — `34625885805`（workflow_dispatch，`app_id_suffix=.dev`）**
<https://github.com/Eitan-S-23/E-Track/actions/runs/34625885805>

- Linux 宿主：同上各项均 PASS（`source_after_restored.clean=true`、
  `01:32 +289 ~7: All tests passed!`、`No issues found! (ran in 14.6s)`）。
- `apk_collect.log`：
  `{"commit": "24d863114afd608ea79f864afac1662c16c44b5b",
  "sha256": "e38bb36568c4a0150135159c28b8122f76a67d5eb7950e3474747d631c72011a",
  "bytes": 131487798, "release_signing": false,
  "application_id": "com.wen.gaia.gaia.dev", "formal_acceptance": "NOT_RUN"}`
- 该 `application_id` 由 `collect` 阶段用 `aapt2 dump badging` **从 APK 自身读出**，
  不是构建意图；即 §2.2 的失败闸门在本次运行中实际执行且通过。

### 4.2 运行 2 的失败与修复（保留记录）

`34625661886` 在 `f68884c2` 上以 `.dev` 派发，双宿主均在
“Verify debug APK helper”步骤失败：
`ValueError: Debug APK declares application id com.example.fixture, expected com.example.fixture.dev`。

- **根因**：`dev_checks.contained_environment()` 会整份拷贝 `os.environ`，因此
  workflow 的 job `env`（`TRACE_DEV_APP_ID_SUFFIX=.dev`）透传进了离线 fixture，
  改变了 fixture 的期望值——是测试隔离缺陷，不是产品缺陷。
- **修复**（提交 `24d86311`）：`tests/ota/test_flutter_dev_apk.py` 的 `setUp` 显式
  `base.pop(APK.APPLICATION_ID_ENV, None)`，并注明该路径由两个显式用例覆盖。
  本机在 环境未设置 / `.dev` / 非法值 三种环境变量状态下各跑一次，
  均为 `Ran 19 tests ... OK`。
- 运行 3/4 即该修复后的复跑结果。

### 4.3 产物本地独立复核（不采信 CI 结论）

下载运行 4 的 APK 产物（`gh api .../artifacts/10274975471/zip`，curl 断点续传），
再**本机独立**解析产物内 `AndroidManifest.xml`（AXML）字符串池：

| 项 | 值 |
| --- | --- |
| 产物 zip sha256 | 见 `.cache/p3-3-t1a/apk-dev/`（不入库） |
| `trace-dev-debug.apk` sha256 | `e38bb36568c4a0150135159c28b8122f76a67d5eb7950e3474747d631c72011a` |
| `trace-dev-debug.apk` 字节数 | 131487798 |
| 与 CI `apk_collect.log` 记录 | **逐字节一致** |

`AndroidManifest.xml` 字符串池（UTF-16，`stringCount=111`）中 `com.wen.gaia*` 条目：

```text
len= 30  'com.wen.gaia.gaia.MainActivity'
len= 41  'com.wen.gaia.gaia.UpdateForegroundService'
len= 21  'com.wen.gaia.gaia.dev'
len= 62  'com.wen.gaia.gaia.dev.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION'
len= 38  'com.wen.gaia.gaia.dev.androidx-startup'
len= 34  'com.wen.gaia.gaia.dev.fileprovider'
len= 44  'com.wen.gaia.gaia.dev.flutter.share_provider'
```

- 正向：精确等于 `com.wen.gaia.gaia.dev` 的条目 → 1（= 包名）。
- 负向：精确等于 `com.wen.gaia.gaia` 的条目 → **0**（生产包名未残留）。
- 对照：精确等于 `com.wen.gaia.zzz` → 0（证明探针不是恒真）。
- 判定：**PASS**。

两点必须写进后续步骤的接口约定：

1. `${applicationId}` 占位符全部解析为带后缀的 id
   （`…dev.fileprovider` 等）——共享数据/FileProvider 的 authority 自洽。
2. `namespace` 未变：组件类名仍是 `com.wen.gaia.gaia.MainActivity`、
   `com.wen.gaia.gaia.UpdateForegroundService`。因此启动命令必须写成
   `adb shell am start -n com.wen.gaia.gaia.dev/com.wen.gaia.gaia.MainActivity`，
   不能把包名与类名混为同一个后缀形式。

## 5. 边界

- **未接触任何 secret**：改动不含 `secrets.` 引用、不含签名密钥读取；`TRACE_DEV_APP_ID_SUFFIX`
  是包名后缀（非凭据），必须原样到达 Gradle 才可能生效，`environment()` 的清洗
  只针对 `ANDROID_RELEASE_*` / `SIDELOAD_*`。
- **未改生产工作流**：仅改 `flutter-dev-checks.yml`；`build.yml` 未动。
- **设备侧**：本轮只做了只读核对（`adb devices -l` 与 PnP 枚举），**未安装、未 grant、
  未卸载、未清数据、未停机、未烧录**。核对结果见 §6。
- **产物边界**：本地只写 `.cache/`（被忽略）与既有 `docs/ota-exec-notes/`；未做项目外写入。
- 已知文档漂移：`docs/flutter-development-validation.md` 描述了 dev APK 的构建与
  记录字段但未提该开关；该文件当前带有**其他未提交改动**，本轮不与其混提，
  留待协调后单独回写。

## 6. 载体交付后的第一次只读核对：设备缺失（阻断，非缺陷）

运行目录：`.cache/p3-3-t1a-step1-r1/`（项目内；原始输出
`step1-precheck.md`、`pnputil-connected.txt`、`apk-manifest-strings.json`）。

- 已把 CI 产物落到 `trace-dev-debug.apk` 并**主机侧复算**：
  `sha256=e38bb365…c72011a`、`bytes=131487798`，与 CI `apk_collect.log` 逐字节一致。
- `adb devices -l`：服务器在跑（PID 18568，`127.0.0.1:5037`），**设备列表为空**。
- `pnputil /enum-devices /connected`：只有主机自带外设（HP Truevision HD 摄像头
  `VID_064E`、Realtek Bluetooth 5.3 适配器 `VID_2C0A`、Intel、HP），
  **没有任何 Android / USB 调试接口**。
- 判定：**不是**「已连接但未授权」（那种情况 adb 会列出 `unauthorized`），
  而是测试手机在物理层未接入。
- 因此步骤 1 的其余动作（安装、授权、启动、BLE 连接、服务发现、通知订阅、
  GET_INFO、有界 logcat）**全部未执行**；A1 配额仍为 1 授权 / 0 消耗。
- 已提取的待用信息（设备接入后直接使用）：
  - dev APK 包名 `com.wen.gaia.gaia.dev`，`versionName 1.0.60+86`
    （与 pubspec 一致，也与手机已装生产版同版本号）；
  - 启动命令必须为 `am start -n com.wen.gaia.gaia.dev/com.wen.gaia.gaia.MainActivity`；
  - 需授权的运行时权限：`BLUETOOTH_SCAN`、`BLUETOOTH_CONNECT`、
    `ACCESS_FINE_LOCATION`、`POST_NOTIFICATIONS`（清单共声明 18 项，见 JSON）。
