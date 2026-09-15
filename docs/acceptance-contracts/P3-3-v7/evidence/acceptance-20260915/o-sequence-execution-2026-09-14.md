# P3-3 O 序列实机执行记录（v5 重跑轮，2026-09-14 晚）

- 执行会话: P3-3-IMPL-20260907（实现会话，独占 worktree
  `D:\github\my\E-Track\.cache\worktrees\p3-3-admission`，分支
  `dev/flutter/apk/p3-3-admission`）
- 依据: v5 冻结合同 `docs/acceptance-contracts/P3-3-v5.contract.json`
  （freeze_commit 6415226，bundle b2fc1ce，FREEZE-INDEX 登记提交 0f0becc）
  + 实机操作单 `P3-3-device-operation-sheet-2026-09-13.md`（O1-O5+D4+D5）
- 授权链: 修复轮整体授权（O2 缺陷修复→重建→finalize 烧板→BCB 恢复→
  重制包→合同升 v5 重冻结→O 序列重跑）+ 用户 2026-09-14「授权，此外你
  说的超授权问题也一并授权」+ 第五轮受验 APK 单独授权（build-only 第 5 笔）
- 本记录为实现会话实测留证；单轮判定（PASS/PRODUCT_FAIL/…）归属独立
  验收会话，本记录只登记事实与实现侧定性建议。

## 1. O1 latest 发现重测（v5 toy fixture，PASS）

- 21:33:38 起真机（序列号 10ADA4197U001CK，受验包
  com.wen.gaia.gaia.p33acceptance v86/1.0.60）latest 请求，服务日志
  `service-v5-20260914.log`：currentVersionCode=30200 → 200 返回
  3.2.1/30201 发现（v5 toy fixture，ETU 0219899d…）。
- 十参数含真实 currentImageSha（30200 的 24fc02ea…），endpoint 为公网
  Quick Tunnel https URL（r4 隧道 describing-substance-databases-past
  .trycloudflare.com）。

## 2. O2/O3 toy 3.2.1/30201 闭环（设备侧全链成功）

服务端三段证据（`service-v5-20260914.log`）：

| 时间 | 事件 |
| --- | --- |
| 21:33:38 | latest（30200）→ 200 发现 3.2.1 |
| 21:33:48 | download → 200，284,540B 完整 |
| 21:40:02/11 | latest×2（**30201+aeafc96e…**）→ 200 无更新（1138→no_update 响应） |

- BLE 传输 284,540B durable 完成（logcat MONO_BUDGET_RESET
  durable=284540），设备 WDT 复位重启（1894f9d 修复的 STAGED→复位
  路径实机生效）。
- **终点双值（toy）**: 21:40:02 latest 参数 currentVersionCode=30201 +
  currentImageSha=`aeafc96e77d372aea1e893a979f2368ba9176c4999a61090ceb2956cd4085298`
  ——App 经新连接 GET_INFO 报出的设备自报身份，与冻结 toy 目标镜像
  raw SHA 全等；服务端返回无更新自洽。
- **设备侧独立验证**（传输完成后 J-Link 只读，授权口径内）:
  - savebin 读回 App 区 [0x08010000, +603764) 与
    `toy-3.2.1-30201-final.bin`（aeafc96e…）比对：两次大块读各含
    一处「归零」伪影（3B@0x57B70 / 5B@0x57706，每次位置不同），
    mem8 小块精读两处均与磁盘全等——SWD 大块读传输伪影，非板上
    数据差异（已编程位只能 1→0，0 不能自发变 1，物理不可能性仲裁）。
    取证 `.cache/p3-3-o-verify/`（read_app*.jlink、reread*.jlink、
    app-region-readback*.bin）。
  - RTT 启动行（复位后采集，`o-verify-boot-rtt.log`）:
    `OTA: HANDOFF vtor=0x08010000` / `Reset: NRST WDT` /
    `QSPI: JEDEC=0xEF4018 whitelisted` / **`OTA: BCB already CONFIRMED
    vcode=30201`** ——设备端 BCB 状态机推进到 CONFIRMED 实证。
- **App 端复核环节**: toy 轮未单独取 logcat（该时段缓冲已滚动），
  用户表述「升级似乎成功了」；从服务日志时序看设备报出新身份的
  时间为传输完成后约 67 秒（21:40:02，传输约 21:38:5x 完成），
  **已超过 60 秒复核窗口**，与真包轮 O4 观察到的复核超时一致
  （见 §5）——toy 轮 App 复核大概率同样 timedOut。

## 3. C-APK-INSTALL 补测（在装 APK 双侧身份，PASS）

- 在装受验 APK `adb pull` → `.cache/p3-3-installed-apk-verify/
  installed-base.apk`：46,699,144B，SHA-256
  `2506e952da92fb2631b1325add4431cf60360efa9db4cbe641dddd3edf9d95af`
  ——与第五轮受验 APK（run 34781909023 产物）字节级全等。
- 证书指纹（apksigner verify --print-certs）:
  `f5e838ef0e2ae7a8b6c1c1240966e041b9aaaa92c092b7ce82c1dc02a45c9a80`
  （仅 v2 scheme，1 signer）——与冻结登记全等。

## 4. D4 服务切换 toy→real（22:08:20）

- 只停 toy 服务进程 → 从 `Tools/ota/p3-3-service/` 以
  `--active-release real-30202` 重启（同端口 8443、同 publicBaseUrl，
  cloudflared PID 21172 不动）。
- 启动日志 `service-v5-r20260914-real.log` 首条 22:08:20:
  activeStable=real-30202，fixtures 双登记（real 0c8ae468…/toy
  0219899d…），启动时对两 fixture 做了字节级核验。
- 22:08:39 公网 curl 验证：30201 查询 → 200 发现 3.2.2（ab0585f7…）。

## 5. O4 真包 3.2.2/30202 闭环（设备侧成功 + App 复核超时缺陷）

### 5.1 服务端与 App 端时间线（实测）

| 时间 | 事件 | 证据 |
| --- | --- | --- |
| 22:10:02/11 | 用户 latest×2（30201+aeafc96e）→ 200 发现 3.2.2 | 服务日志 |
| 22:10:28 | download → 200，284,573B 完整（token 签名校验通过） | 服务日志 |
| 22:10:34.605 | App 开始 BLE 传输（MONO_BUDGET_START） | logcat 23378 |
| 22:14:40.058 | 传输完成 284573/284573；22:14:40.327 MONO_BUDGET_RESET **durable=284573** | logcat |
| 22:14:40 | 设备复位（WDT），BCB STAGED→APPLYING→搬运→CONFIRMED | 推断+用户实证 |
| 22:14:41.121 | 复核第一轮 connect 失败：`OTA重连失败: PlatformException(requestMtu, device is disconnected)` | logcat |
| ~22:15:40 | 60 秒复核窗口耗尽 → timedOut → **UI「等待设备重启校验失败」** | 推定（窗口静默） |
| 22:16:17 | 再连仍失败（requestMtu, device is disconnected）——距复位 97 秒设备 BLE 仍不可连 | logcat |
| 22:16:18-22 | discoverServices 失败×3 | logcat |
| 22:16:24 | 用户重启 App（进程 23378→19380） | logcat |
| ~22:27 | 用户重连成功，设备信息显示 vcode 30202 | 用户实证+FBP 日志 |
| **22:32:20.907** | 用户点「检查更新」→ latest 参数 **currentVersionCode=30202 + currentImageSha=ab0585f7…**，服务端 200/114B 无更新 | 服务日志 |

### 5.2 终点双值（real）

- versionCode **30202** ✔ + 完整 raw SHA-256
  `ab0585f71b9a523863b582e8ed4cc47a279bf6e57c4a1038635593306746ab7e` ✔
  ——经重启后新连接 GET_INFO 设备自报（22:32:20 latest 请求参数），
  与冻结真包目标镜像全等；服务端 no_update 响应自洽。合同
  CMD-REAL-LOOP「重启后新连接 GET_INFO 的目标 versionCode 与完整
  raw SHA-256 与冻结目标镜像一致」的终点观测闭合。
- 不得由 toy 结果代替的约束满足：30202/ab0585f7 为 real 轮独立实测。

### 5.3 App 端复核环节缺陷（实现侧定性：PRODUCT_FAIL 候选）

- **现象**: 升级实际成功（设备在 30202 并 CONFIRMED），但 App 升级
  流程在「等待设备重启」环节报「等待设备重启校验失败」——假阴性。
- **机制**（logcat 取证）:
  1. `_waitForTargetIdentity` 60 秒总截止窗口从传输完成、设备复位
     前建立（ota_service.dart RC3-08⑤ 设计）；
  2. 设备从复位到 BLE 恢复可连接的实测耗时 > 60 秒（22:14:41 与
     22:16:17 两次连接尝试均 device is disconnected，≥97 秒不可连；
     22:27 前后才连上）。复核窗口内设备广播未恢复（FBP 扫描回调
     22:14:40-22:15:45 对 E3:49:E1:14:D6:CB 计数为 0）；
  3. 第一轮探测 connect 抛错后，后续探测轮的 connect 挂起（日志
     静默），外层 `.timeout(remaining)` 兜底放弃，窗口耗尽 →
     timedOut → REBOOT_RECONNECT_FAILED；
  4. toy 轮服务日志显示设备报新身份在传输完成后 ~67 秒——同模式，
     系统性时序问题（60 秒窗口 < 设备重启恢复耗时），非偶发。
- **根因归属**: App 侧复核窗口设计（60 秒固定窗口从复位前起算）与
  设备实际重启恢复耗时（BCB 搬运 603,764B + App 启动 + BLE 栈起播）
  不匹配；叠加探测 connect 无独立短超时、挂起吞掉剩余窗口。
- **建议处置**（按执行合同 §7.3 集中整改）: 并入 #48 整改批次——
  窗口延长（如 180s）或改为「首次可连接后起算」、探测链各环节独立
  短超时、失败文案区分「设备未在窗口内恢复」（可稍后重试）与
  「升级失败」。O4 不重跑（设备已 CONFIRMED 30202，回滚成本高），
  修复后随重冻结验收。
- **附带观察**: App 重启后新进程 19380 启动时 `BleController.startScan`
  的 snackbar 在无 Overlay 上下文抛 Null check operator 异常
  （ble_controller.dart:123，UI 启动时序问题，不阻断主流程，登记
  供整改参考）。

### 5.4 升级历史缺陷（登记，不在 v5 判据内）

- `getUpgradeHistory()` 自初始版本（2ce8cd5）起为桩（`return const []`），
  无写入端——UI「升级历史」永远显示暂无记录。占位实现，建议与
  #48（码表页扫描）和 §5.3 复核窗口缺陷一并整改。

## 6. O5 验收后只读身份复核（双包名，PASS）

`adb shell dumpsys package` 双包名只读（取证
`.cache/p3-3-o-verify/o5-final-identity.log`）:

| 包 | versionCode/Name | 时间 | 状态 |
| --- | --- | --- | --- |
| com.wen.gaia.gaia.p33acceptance | 86 / 1.0.60 | 装入 2026-09-14 13:05:12 | 受验包在装，身份与冻结基准一致 |
| com.wen.gaia.gaia | 86 / 1.0.60 | lastUpdate **2026-07-10** | **全程未动**（O 序列零触碰承诺兑现） |

双包名并存确认（pm list packages）✔。

## 7. D5 完整清理（四步，PASS）

留证 `.cache/p3-3-v2-service/d5-cleanup-20260914.log`：

1. cloudflared PID 21172 终止（taskkill /F，exit 0）；
2. 服务 python PID 21932（real-30202 轮，命令行核验后）终止（exit 0）；
3. 日志归档：全部在 worktree `.cache/` 内——toy 轮
   `service-v5-20260914.log`（SHA 1f6d2f7e…）、real 轮
   `service-v5-r20260914-real.log`（SHA 27828291…）、隧道
   `tunnel-r4-20260914.log`（.cache/p3-3-cloudflared/，SHA de2bd8b2…）
   及本轮全部日志 SHA 已记录在 d5 清理日志；
4. 无残留验证：两 PID 均不存在、8443 无监听、无 cloudflared 进程。
- adb reverse：`reverse --list` 为空，无需清理。

## 8. 额度对账（本轮）

| 项 | 授权 | 实际 |
| --- | --- | --- |
| APK 构建（build-only） | 5 笔单独授权 | 5/5 已用（c1c89084/56301807/b9c0bdd5/d241f7ca/2506e952）；第 6 笔仅当隧道再死时申请，未用 |
| J-Link（O 序列，传输完成后只读） | 修复轮整体授权口径 | toy 轮：savebin×2 + mem8 仲裁×2 + RTT 签名 1 + 复位 1 + RTT logger 1；real 轮（O4）：零 J-Link（终点双值按操作单以 App 侧证据闭合） |
| 设备复位 | O 序列闭环组成（固件正常状态机） | toy 1 次（固件自复位）+ RTT 取证复位 1 次；real 1 次（固件自复位） |
| 服务/隧道 | D1-D5 部署授权 | toy 启动 1 + D4 切换 1 + D5 清理，全程同隧道同地址 |

## 9. 待独立验收会话裁定的事项

1. C-TOY-LOOP / C-REAL-LOOP 单轮判定（本记录 §2/§5 为事实输入；
   App 复核超时缺陷的判据影响归属由验收会话按合同 state_chain 裁定）。
2. C-DEV-CHECKS / C-RELEASE-BUILD / C-APK-INSTALL 正式判定与矩阵回填。
3. §5.3 复核窗口缺陷与 §5.4 升级历史桩的整改排期（建议并入 #48）。

## 10. 板卡终态

- App 区 = 3.2.2/30202（ab0585f7…，设备自报 + 服务端核对），BCB
  CONFIRMED（设备端状态机实证推断：升级后正常运行且报 CONFIRMED
  语义身份；RTT 直接采证未做，按操作单 App 侧证据为准）。
- 生产 Boot 全区未动（O 序列零烧录；r2 恢复终态保持）。
- 手机侧：生产包 com.wen.gaia.gaia 未动，受验包 p33acceptance 在装。
