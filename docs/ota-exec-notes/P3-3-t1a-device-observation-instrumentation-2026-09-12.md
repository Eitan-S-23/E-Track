# P3-3 T1a 设备观测调试代码（编进 APK，不再驱动 UI）—— 2026-09-12

> 触发：用户 2026-09-12「你就不能在 apk 中增加调试代码吗？用调试代码就能避免你查看
> ui 浪费时间了吧？」
> 依据：`PLAN-OTA-EXEC.md` §0、`docs/ota-exec-notes/P3-3-t1a-step1-device-observation-2026-09-12.md`
> §3.2 撤回说明、`docs/flutter-development-validation.md`、`app/bluetooth_flutter_Trace/AGENTS.md`。
> 本报告只覆盖**插桩实现与本地回归**；**未安装、未连接目标板、未发起 BLE 通信、未停机**。
> 正式验收保持 `NOT_RUN`；A1 配额 1 次**仍未消耗**。

## 1. 为什么改（上一轮的真实成本与错误来源）

上一轮步骤 1 的观测方式是**人工驱动 UI**：点进四级页面看设备卡片，读数靠截图判读。
由此产生两个问题：

1. **慢且不可复现**：每轮都要手点、截图、肉眼比对；同一现象无法用命令重放。
2. **结论本身不可靠**——日志出口恒定饱和。应用把「设备名称」的日志写在实际渲染
   的每一张卡片上（`BleController.getDeviceName()` 逐卡调用），因此扫描到 17 台时
   logcat 只出现约 5 台。据此写下的「目标板未出现在扫描结果中」是**从饱和出口推出的
   无效结论**（该轮报告 §3.2 已加撤回横幅）。

把观测做进 APK 的目标不是"更好看的日志"，而是**把观测从 UI 路径上摘下来**：
扫描结果直接逐台落 logcat，命中目标后自动完成绑定与身份读取，全程不需要人点界面。

## 2. 设计：三道闸门 + 固定行契约

### 2.1 三道闸门（任一不满足都不产生观测行为）

| 闸门 | 位置 | 缺省后果 |
| --- | --- | --- |
| 编译期显式启用 | `ota_device_observation.dart` 读 `TRACE_DEV_DEVICE_OBSERVATION`（默认 `false`） | 返回 `null`：不装配观测器，扫描监听不调用本文件，**行为与改动前一致** |
| 启用后配置完整 | target 与 sentinel 任一为空 ⇒ `problem` 非空 | **fail-closed**：只输出一行 `OTA_OBS config=INVALID problem=…`，不启动观测 |
| 产物自证注入生效 | `Tools/flutter/dev_apk.py` 在归档阶段要求 sentinel / 固件地址 / target 的**字面量**出现在产物 kernel blob | 拒绝写出产物记录与 APK，`apk_collect` 非零 |

第三道闸门是这次的要点：`--dart-define` 只是**构建意图**。若只记录"打算注入"，就可能
产出"声称设备观测就绪、实际没注入"的假阳性 APK。判据放在**产物内部**，不放在命令行上。

### 2.2 观测行契约（`OTA_OBS ` 前缀，字段顺序固定）

```
OTA_OBS config=enabled target=XTrace sentinel=OTAOBS<24hex>      ← 启动，带配置指纹
OTA_OBS scan total=<n> new=<k> seen=<n>                          ← 每批一次
OTA_OBS adv addr=.. name=.. rssi=.. connectable=.. uuids=.. mfg=..  ← 每台新设备一行
OTA_OBS target addr=.. name=.. rssi=.. matched_by=address|name|namePrefix
OTA_OBS connect addr=<小写地址> result=ok|fail
OTA_OBS identity addr=.. result=ok wire=.. model=.. vcode=.. hw=.. layout=.. boot=.. proto=.. window=.. sha=<64hex>
OTA_OBS done result=ok|connect_failed|identity_failed|identity_error    ← 唯一终止行
```

- `sentinel`：构建侧按 `(target, 固件查询地址)` 算出的指纹，运行期打进日志，
  用于把**手机上这台 APK**与 CI 记录的**那一次构建**对上；不一致即说明装的不是同一产物。
- `matched_by` 原样落盘：前缀兜底（部分 BLE 模块在配置名后追加短地址）可能误绑，
  事后必须能从日志识别。
- 终止行是**确定且唯一**的：连接失败 / 身份为空 / 身份抛异常 三种结局各有固定取值，
  logcat 侧不需要"没有错误行"这种推定。

### 2.3 关键实现决定

- **监听点只有一处**：`bluetooth_service.dart` 的 `_adapter.scanResults.listen(...)` 首行
  调 `_observeScanResults(results)`，在平台分支**之前**。饱和发生在 UI 渲染路径而不是
  扫描路径，因此这一处拿到的是全量批次。
- **绑定链：先停扫描 → 再连接 → 再读身份**。中央设备同时扫描与连接会互相挤占射频；
  读身份走 `OtaService.readDeviceInfo(address)`，**不需要导航到任何页面**。
- **绑定用平台原样地址的小写形式**，不是归一化 hex：服务侧 `_findDeviceByAddress`
  按 `remoteId.str.toLowerCase()` 比较。
- **观测器不依赖 GetX / 插件通道**：连接、读身份、启停扫描全部由构造参数注入，
  `ScanResult → ObservedAdvertisement` 的映射留在 `bluetooth_service.dart`，
  因此核心逻辑可在**纯单元测试**里离线驱动。

## 3. 改动清单（分支 `dev/flutter/apk/p3-3-t1a`）

| 文件 | 改动 | 作用 |
| --- | --- | --- |
| `lib/ota/ota_device_observation.dart` | 新增（约 310 行） | 配置/匹配/值对象/观测器；三道闸门的前两道 |
| `lib/services/bluetooth_service.dart` | +45 | 扫描监听接线 + 观测专用连接入口 + `ScanResult → 快照` 映射 |
| `lib/main.dart` | +10 | 启动后装配观测器（未启用返回 `null`） |
| `Tools/flutter/dev_apk.py` | +80/-2 | 观测配置解析与校验、`--dart-define` 生成、`collect` 阶段的产物内自证闸门 |
| `.github/workflows/flutter-dev-checks.yml` | +13 | 三个 `workflow_dispatch` 输入（`device_observation` / `observation_target` / `observation_firmware_latest_url`）与 job `env` 透传 |
| `tests/ota/test_flutter_dev_apk.py` | +120 | 5 个新回归用例（见 §4） |
| `test/ota/ota_device_observation_test.dart` | 新增（9 个用例） | 观测器离线回归 |

### 3.1 默认行为不变的证据

- workflow `env`：`${{ inputs.device_observation && 'true' || '' }}`，push 触发时
  `inputs` 为空 ⇒ 环境变量为空串 ⇒ `observation_config()` 返回 `None` ⇒
  `observation_defines()` 返回 `[]` ⇒ **`apk_build` 命令行里没有任何 `--dart-define`**
  （`test_device_observation_is_opt_in_and_absent_by_default` 直接断言这一点）。
- Dart 侧 `bool.fromEnvironment(..., defaultValue: false)`：未注入即为 `false`，
  `startFromBuild()` 返回 `null`，不启动扫描、不产生任何日志行
  （`startFromBuild 在默认构建下不装配观测器也不启动扫描` 断言 `started == 0`）。
- 观测代码**只读扫描结果、只写日志**，不改变任何控制流、超时或终止语义。

### 3.2 凭据边界（本次未触碰任何 secret）

- 注入的 `TRACE_CLOUDFLARE_FIRMWARE_LATEST_URL` 取**公开** Clients 基址
  `https://trace-update-public-staging.pages.dev` 拼接 `/api/public/firmware/latest`。
  该基址在仓库文档中明确登记为 non-secret（`cloudflare/update-service/docs/README.md`、
  `STAGING-SETUP.md`、`github-actions-secrets.staging.example.json`）。
- `observation_config()` 只接受 `https`、有主机名、无 `user:pass@`、无 fragment、
  查询串不含 `token|secret|signature|sig|apikey|api_key|access_key|auth`，
  并把这些拒绝写成用例。**未读取、未注入任何部署 token / Cloudflare API token /
  签名私钥**；也未开启 App 自更新端点，未改动生产工作流。
- 观测日志只输出 BLE 广播可见字段与设备身份字段；不输出任何签名下载 URL 或凭据。

### 3.3 端点可达性（只取状态码，未取回包体）

| 请求 | 结果 |
| --- | --- |
| `GET /api/public/latest` | `200` |
| `GET /api/public/firmware/latest`（不带身份参数） | `400` |

`400` 不带参数是**预期**：固件查询按契约要求带设备身份参数，缺参即拒绝——这与 §2 的
「第 2 步必须用真实身份发起查询」一致，不属于地址错误（错地址会是 `404`）。

## 4. 本地回归（非构建检查，允许范围）

| 命令 | 结果 |
| --- | --- |
| `python -B tests/ota/test_flutter_dev_apk.py` | `Ran 25 tests ... OK` |
| `python -B tests/ota/test_flutter_dev_checks.py` | `Ran 50 tests ... OK` |

新增 5 个 runner 用例：默认不注入、注入确实到达 `apk_build`（含指纹与键序无关性）、
非法/含凭据/不完整配置在**构建计划阶段**即失败、`collect` 拒绝缺 sentinel/地址/target
或无 kernel blob 的产物、`collect` 正例记录 `device_observation` 元数据。

Dart 侧 9 个用例**本机 NOT_RUN**：本机无 Flutter/Dart SDK（`flutter` 不在 PATH，
`.cache/flutter-dev-checks` 下无已落盘 SDK），且 `AGENTS.md` 禁止本地构建。
其执行证据只能来自 CI。

## 5. 未验证的假设（必须显式记账）

**唯一未经本机实证的假设**：`--dart-define` 注入的**取值**会以字面量形式出现在调试
构建的 `assets/flutter_assets/kernel_blob.bin` 中。

- 已实证的部分：该 blob 确实包含源码字面量（上一轮在真实 debug APK 中命中 `OTA_MONO`
  ×4、`蓝牙控制器初始化成功` ×2 等）。
- 未实证的部分：注入值（而非仅键名）也落在 blob 里。
- **后果方向是安全的**：若假设不成立，`apk_collect` 会**拒绝**该产物并让本次运行变红，
  不会产出"看似可用"的假阳性 APK。届时按日志改为在构建后另取判据（例如直接核对
  `--dart-define` 参数与产物运行期首行 `config=enabled … sentinel=…` 的一致性），
  而不是放宽这一闸门。

## 6. 未做 / 未授权事项

- 未安装 APK 到任何手机、未连接目标板、未进行任何 BLE 通信、未 J-Link 停机/烧录/
  断电、未插拔 SD、未清除应用数据。
- 未合并、未发布、未部署、未触发生产工作流。
- 正式验收 `NOT_RUN`；T2 的暂时 `ENV_BLOCKED` 不变；A1 单轮观测配额仍为 1 次未消耗。

## 7. 首轮 dev CI 结论与整改（实测，2026-09-12）

推送提交 `1c2dc6d` 后触发 run `34686430345`（push）与 `34686437572`
（dispatch，`build_apk=true` / `app_id_suffix=.dev` / `device_observation=true` /
`observation_target=XTrace`），**双宿主同时打红**：

| 宿主 | `analyze` | `tests` | `apk_*` |
| --- | --- | --- | --- |
| ubuntu-latest | FAIL(1) | FAIL(1) | 全部 `NOT_RUN`（未产出 APK） |
| windows-2022 | FAIL(1) | FAIL(1) | 不适用（APK 仅在 Linux 构建） |

三项根因，**一项是真实缺陷，两项是 lint**：

1. **真实缺陷（测试抓到，实现改）**：`match()` 只在 target 含冒号时才走归一化
   地址比较，于是 `AABBCCDDEEFF` 这种无分隔符写法落到名字分支返回 `none`。改为
   「含分隔符，或去分隔符后恰好 12 位 hex」即做归一化比较；比较仍是**全等**
   而非子串，故 `aabb` 短名字的误命中防护不变。
2. `prefer_const_declarations`：`startFromBuild()` 内 `final config` 指向
   `static const`，改 `const`。
3. `non_constant_identifier_names`：测试局部变量 `target_line` → `targetLine`。

整改提交 `f68b680`。本机离线回归保持全绿（25 OK / 50 OK）。

### 7.1 次轮 dev CI：双宿主全绿，debug APK 产出

整改后同一提交 `f68b680` 触发 run `34686910798`（push）与 `34686919457`
（dispatch，同上五个输入），**全部通过**：

| 宿主 | `analyze` | `tests` | `apk_result` |
| --- | --- | --- | --- |
| ubuntu-latest | PASS（No issues found） | PASS（`+298 ~7` All tests passed） | **PASS** |
| windows-2022 | PASS（No issues found） | PASS | `NOT_REQUESTED`（APK 仅 Linux） |

`apk_collect.log` 实录（原样，未改写）：

```json
{"artifact_kind": "development-debug-apk", "formal_acceptance": "NOT_RUN",
 "commit": "f68b6808f41af24b25406030ac64b4adb54c8927",
 "sha256": "594521196c1c69616c83af484471c8d00b4aa5ab823b3f54b7639e0230726472",
 "bytes": 131502370, "file": "trace-dev-debug.apk", "release_signing": false,
 "application_id": "com.wen.gaia.gaia.dev",
 "device_observation": {"enabled": true, "target": "XTrace",
   "sentinel": "OTAOBS25728d5efc16a857bf0f7b05",
   "firmware_latest_url": "https://trace-update-public-staging.pages.dev/api/public/firmware/latest"}}
```

- `apk_verify`：`Verified using v2 scheme (APK Signature Scheme v2): true`，
  `Number of signers: 1`，`release_signing: false` —— debug 签名，不是发布签名。
- 运行产物 id：`flutter-dev-debug-apk-f68b6808f41af24b25406030ac64b4adb54c8927-34686919457-1`
  （75,241,871 B 压缩包；本轮**未整包下载**，APK 哈希取自 `apk_collect.log`）。
- **`application_id = com.wen.gaia.gaia.dev`**：与生产包名不同，即"乙"方案实测生效
  ——设备观测 APK 与手机现存生产版**不构成同包升级关系**，因此不触发既有授权里
  的"签名冲突即停止"分支；它可并存安装，不需要卸载或清数据。

### 7.2 §5 的唯一未验证假设已被闸门实证

`apk_collect` 的闸门要求 sentinel / 固件地址 / target 三个**字面量**出现在产物
`assets/flutter_assets/kernel_blob.bin` 中，否则拒绝归档。本次归档通过，即：

> **`--dart-define` 注入的是键**之外**，其取值确实以字面量形式落进了 debug 构建的 kernel blob。**

§5 记录的"未实证项"因此**转为已实证**，不需要改为弱判据。运行期首行
`OTA_OBS config=enabled target=XTrace sentinel=OTAOBS25728d5efc16a857bf0f7b05`
应与上表一致——不一致即说明手机上装的不是这次构建的产物。

### 7.3 本轮**已实证**的链条

失败运行仍产出了 Linux 端 `result.json`，其中 `apk_build` 的**计划 argv** 为：

```
flutter build apk --debug --no-pub --target-platform=android-arm,android-arm64 \
  --dart-define=TRACE_DEV_DEVICE_OBSERVATION=true \
  --dart-define=TRACE_DEV_OBSERVATION_TARGET=XTrace \
  --dart-define=TRACE_DEV_OBSERVATION_SENTINEL=OTAOBS25728d5efc16a857bf0f7b05 \
  --dart-define=TRACE_CLOUDFLARE_FIRMWARE_LATEST_URL=https://trace-update-public-staging.pages.dev/api/public/firmware/latest
```

即 **`workflow_dispatch` 输入 → job `env` → `observation_config()` 校验 →
`--dart-define` 生成 → 构建命令** 这条链已由真实运行记录证实；Windows 端
`result.json` 不含任何观测字面量，也反证了注入只发生在被显式请求的档位。

## 8. 未完成 / 需独立验收的部分

**已完成的开发侧工作到此为止**：插桩、闸门、回归、双宿主 CI、debug APK 全部落地
并有原始证据。以下不在本次范围内：

1. **未装机、未连接任何真实设备**：未安装 APK 到手机、未连接目标板、未发起任何
   BLE 通信、未 J-Link 停机/烧录/断电、未插拔 SD、未清除应用数据。**A1 单轮观测
   配额 1 次仍未消耗**。
2. **正式验收保持 `NOT_RUN`**；T2 的暂时 `ENV_BLOCKED` 不变。debug APK 不是发布
   产物，开发自测不是独立验收。
3. 未合并、未发布、未部署、未触发任何生产工作流。
4. 共享看板（`PLAN-OTA-EXEC.md`）与其余共享文档带前序会话的未提交改动，按既有
   串行化约定由主会话统一回写，本分支未触碰。

**交给独立验收的最小判据**（每项都有上面的原始证据可复核）：

- 默认（未注入）构建**零观测行为**：`apk_build` 命令行无 `--dart-define`
  （`test_device_observation_is_opt_in_and_absent_by_default` + §7.3 的 Windows 反证）。
- 显式启用时**注入确实到达构建命令**，且**产物内自证**通过（§7.1/§7.2）。
- 观测行契约固定且终止行唯一（9 个 Dart 用例，CI `test/ota` 全量在跑）。
- 设备观测 APK 与生产版**不同包名**，不构成签名冲突（§7.1 的 `application_id`）。

## 9. 后续（待执行，需另行授权）

1. 装机后由**只读 logcat** 得到全量扫描清单与（命中时）完整身份行；
   该步仍受既有授权约束（签名冲突即停止，不卸载、不清数据）。
2. 用真实身份发起固件候选查询并核验 `.etu`（步骤 2）。
