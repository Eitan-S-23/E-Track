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

## 7. 下一步（待执行，按本报告同一分支）

1. 提交并推送本分支 WIP，派发 `.github/workflows/flutter-dev-checks.yml`
   （`build_apk=true`、`app_id_suffix=.dev`、`device_observation=true`、
   `observation_target=XTrace`、`observation_firmware_latest_url=<公开地址>`）。
2. 取双宿主结论 + debug APK 的 `apk_collect.log` 与 `trace-dev-debug.json`
   （其中 `device_observation` 应回填 target/sentinel/地址）。
3. 装机后由**只读 logcat** 得到全量扫描清单与（命中时）完整身份行；
   该步仍受既有授权约束（签名冲突即停止，不卸载、不清数据）。
