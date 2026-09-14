# P3-3 第六轮受验 APK 与三缺陷实机验证执行 —— 2026-09-14（r6）

> 依据：用户 2026-09-14 飞书指令「1授权」（第六轮受验 APK 构建额度 +
> 三缺陷实机验证）。三缺陷修复实现见
> `P3-3-reboot-window-and-ui-fixes-2026-09-14.md`（第十一轮：复核窗口
> 60s→180s 假阴性、版本号 3.2.1 式反解显示、「重新读取身份解锁」按钮
> Wrap 换行防截断），实现提交 `7d2856e`，CI 整改提交 `ce30190`，双宿主
> 全绿 run `34861159023`。
>
> **性质**：离线制包 + 宿主受控服务 + CI APK 构建。零真机写入（未连
> J-Link，未读写设备/BCB/App 区）、零云端写入（D1/R2/CF 生产后台未动）。
> tracked 改动 = `service_config.json`（新增 real-30203 fixture 身份）。

## 1. 背景：为什么需要 3.2.3 fixture

设备当前 = O4 真包闭环后的 **30202**（`ab0585f7…` 终点双值，2026-09-14
22:32:20 确认）。v5 既有 fixture 中 toy-30201（低版本）与 real-30202
（同版本）均无法触发升级。复核窗口/版本号显示的实机验证需要一次真实
升级闭环，故制 **3.2.3（30203）** 目标包。

## 2. 3.2.3 fixture 制包（与 v5 同源同法）

- **源镜像**：`.cache/bg/app-gcc/X-Track-App-GCC.bin`（`1894f9d` GCC
  构建，603,764 B，SHA-256 `4b16048f…30ec`）——与 v5 toy/真包同源，即
  板上 3.2.0-fixed 本体；本轮固件源码零改动（三缺陷修复全部在 App 侧），
  源镜像 SHA 复核全等后直接使用，无需重建。
- **目录**：`.cache/p3-3-assets-v6/`（v5 目录 12 文件原样保留不动，v5
  冻结包证据完整性所需）。

制包命令（工具身份与 v5 轮一致：`etu_pack.py` blob `8a413ed3…`，
`etu_unpack.py` blob `86409ec3…`，零改动）：

```
python Tools/etu_pack.py finalize \
  --app .cache/p3-3-assets-v6/real-3.2.3-pre-finalize.bin \
  --out .cache/p3-3-assets-v6/real-3.2.3-30203-final.bin \
  --ver-name 3.2.3 --build-ts 1789400336 --hw-rev 1 --layout-id 1 --min-boot 1

python Tools/etu_pack.py pack-full \
  --app .cache/p3-3-assets-v6/real-3.2.3-30203-final.bin \
  --out .cache/p3-3-assets-v6/real-3.2.3-30203-full.etu --target-vcode 30203
```

密钥口径同 v5：开发密钥 key_id=1（未设 OTA_AES_KEY，预期 warn 行一次）。

## 3. 离线验证（verify_v6.py 全 PASS，rc=0）

脚本 `.cache/p3-3-assets-v6/verify_v6.py`、报告
`verify_v6_report.txt`。判据复刻 v5 §5（单包版）：

| 验证 | 结果 |
| --- | --- |
| A pre-finalize 副本 == bg 构建原件 | PASS（`4b16048f…` 逐字节相等） |
| B finalize 与 pre-finalize 差异范围 | PASS（仅 0x400..0x45E，75B，本体零差异） |
| C fw_header 独立解码（ETFW/ver=1/vcode=30203/version_name=3.2.3/build_ts=1789400336/hw=1/layout=1/min_boot=1/image_len=603764） | 全 PASS |
| D 双零摘要独立复算 == 头内 off40..71 域值 | PASS（`1a605794…4bd28`） |
| D 整镜像 raw SHA == finalize stdout | PASS（`3a282768…144a3`） |
| E header_crc32 复算 == 头内域值 == 工具输出 | PASS（`0xFFC15EC2`） |
| G 与 v5 真包(30202)最终镜像差异仅 0x408..0x45F（41B 版本身份字段） | PASS（同源升级链：30200→30201→30202→30203 四环同本体） |
| I 升级检查模拟 30203 > 设备当前 30202 | PASS |
| etu_unpack --verify-fw-header | OK（candidate_len=603764、target_vcode=30203、image_sha256 与封包一致） |
| candidate 与 finalize 镜像逐字节比对 | 一致 |
| 规范名副本与原始产物逐字节比对 | 一致 |

### 3.1 资产身份四元组（v6，登记键）

| # | 项 | 值 |
| --- | --- | --- |
| 1 | pre-finalize 源 SHA-256 | `4b16048f5970c9cef924690a62031e232cd1d2fb8c1b8af85c18993cfdf830ec`（603,764 B，与 v5 同源） |
| 2 | 最终完整镜像 raw SHA-256 | `3a2827683cbd2b557dd5d441927d1a490b3b28fe11f8d7a4b4b5c86a594144a3`（603,764 B） |
| 3 | fw_header 双零摘要 | `1a60579440c6feb79fa52f488dfcc0d6ff893eda36533d32ff08e4685094bd28` |
| 4 | ETU 包 SHA-256 / size | `a543f952dcd1b0f57770669e253b29e9a93b7ffb94263bc7bdc3b1bdf4ef1915` / 284,608 B |

ETU 外层属性：`target_vcode=30203 flags=0x000b key_id=1
nonce=1f50df7f9d9d69ab637a3981e9eec98a`。规范文件名
`e-track-at32f435-v3.2.3-full.etu`（releaseTag
`mcu-e-track-at32f435-v3.2.3`，云端登记未申请，B0-B4 仍暂停）。

**GET_INFO 终点比对标准 = 第 2 行 raw SHA**（v6 合同 C-REAL-LOOP 类判据
候选值 `3a282768…`）。

## 4. 服务 fixture 注册与 r6 实例

- **配置**：`Tools/ota/p3-3-service/service_config.json` 新增
  `real-30203` release（targetImageSha256=`3a282768…`，asset
  `a543f952…`/284,608B，path 指向 `.cache/p3-3-assets-v6/`）。
  toy-30201/real-30202 原样保留。本轮唯一 tracked 改动。
- **r5 Quick Tunnel**：2026-09-14 23:4x 起，域名
  `quality-lap-aggregate-comment.trycloudflare.com`，cloudflared PID
  3868（`--no-autoupdate tunnel --url http://127.0.0.1:8443`，日志
  `.cache/p3-3-cloudflared/tunnel-r5-20260914.log`）。预检无残留进程、
  8443 空闲。
- **v6 服务实例**：23:42:39 起，脱离托管形式（`(python service.py … &)`，
  规避 harness 退出带走进程的 §13.4 教训），参数
  `--active-release real-30203 --host 127.0.0.1 --port 8443
  --public-base-url https://quality-lap-aggregate-comment.trycloudflare.com
  --log-file .cache/p3-3-v2-service/service-v6-20260914.log`。
- **启动横幅**（`service-v6-restart.stdout`）：三 fixture fail-closed
  核验通过——`real-30202:…0c8ae468, real-30203:…284608:a543f952,
  toy-30201:…0219899d`（real-30203 SHA 与四元组第 4 行一致）。

## 5. D2 宿主检查（本机 + 公网全链路）

| 检查 | 结果 |
| --- | --- |
| 本机 `/latest`（currentVersionCode=30202 十参数） | 200，updateAvailable=true，3.2.3/30203，targetImageSha256=`3a282768…`，asset `a543f952…`/284,608B，downloadUrl 指向 r5 域名 |
| 公网 `/latest`（经 r5 隧道） | 200 同身份（probe 落盘 `v6-latest-probe.json`） |
| 公网签名 downloadUrl 下载 | 284,608 B，SHA `a543f952…`，与本地实物逐字节全等（`v6-download-probe.etu`，cmp 全等） |

请求日志：`.cache/p3-3-v2-service/service-v6-20260914.log`。

## 6. 第六轮受验 APK 构建（用户授权额度，进行中）

```
gh workflow run build.yml --ref dev/flutter/apk/p3-3-admission \
  -f publish_release=false -f replace_existing_release=false \
  -f firmware_latest_url=https://quality-lap-aggregate-comment.trycloudflare.com/api/public/firmware/latest \
  -f release_application_id_suffix=.p33acceptance
```

Run `34864052541`（2026-09-14 15:43:42Z 起，**success**，Build Android
APK / Build Windows EXE 均 success，Pages/Release skipped）。构建源 =
`ce30190`（三缺陷修复 + CI 整改后 HEAD）。

**第六轮 APK 身份（本机实测）**：

| 项 | 值 |
| --- | --- |
| 文件 | `.cache/p3-3-apk-r6/ble-monitor-android.apk`，46,699,144 B |
| SHA-256 | `fb6a91e69a0ad30dc0b9c79a69c5e638d376898d6e313836191f2b40ebf80a13` |
| applicationId | `com.wen.gaia.gaia.p33acceptance`（`.p33acceptance` 后缀注入，覆盖安装第五轮在装包；生产包不动） |
| versionCode/Name | 86 / 1.0.60（pubspec 未动，装机后 dumpsys 复核） |
| endpoint 注入 | 构建日志旁证：`DISPATCH_FIRMWARE_LATEST_URL: https://quality-lap-aggregate-comment.trycloudflare.com/api/public/firmware/latest` |

交付载体（46.7MB 超飞书 30MB 上限，沿用 r4 轮方式）：GitHub artifact
原始 zip `.cache/p3-3-apk-r6/android-apk-artifact.zip`，25,509,009 B，
SHA-256 `0edf01eec20a1bb1af9d30b8259b2a8f915207cbaa20db86e340b9ea8e5baf1a`；
zip 内层 APK 解出哈希复核 = `fb6a91e6…` 全等。

## 7. 待办（已全部完成，2026-09-15 回填）

- [x] run `34864052541` 结论与 APK 五元组（见 §6）
- [x] 用户装机（p33acceptance 覆盖安装第六轮 APK，生产包
  com.wen.gaia.gaia 全程未动未卸载）
- [x] 实机验证三项——**用户 2026-09-15 飞书确认「实测OTA没有问题」**
  （针对三缺陷的综合实测结论；同消息反馈两个非缺陷类体验问题，见
  `P3-3-ble-speed-and-background-research-2026-09-15.md`，用户裁定暂缓
  实施不进本轮冻结范围）：
  - **V1 复核窗口 PASS**：升级流程无「等待设备重启校验失败」假阴性
    报错（对照 O4 轮 60s 窗口必假阴性：设备 BLE 恢复实测 ≥97s）；
    180s 新窗口内复核完成，服务日志 00:06:05 起设备已以新身份查询。
  - **V2 版本号显示 PASS**：身份卡按契约 §0.6 反解显示
    `v3.2.3`（对照修复前裸 vcode `30203`）。
  - **V3 按钮截断 PASS**：终止态场景「检查更新」与
    「重新读取身份解锁」两按钮 Wrap 布局共存无截断（CI 组件测试已
    覆盖，实机自然出现时随综合实测确认）。
- [x] 实测证据与服务请求日志核对（见 §7.1）
- [x] D 清理（见 §7.2）

## 7.1 实测证据：服务请求日志时间线（service-v6-20260914.log）

设备视角完整升级闭环（App=第六轮 APK fb6a91e6…，含三缺陷修复）：

| 时刻 | 请求 | 说明 |
| --- | --- | --- |
| 23:43:06 / 23:43:19 | latest，currentVersionCode=**30202** | App 检查更新（发现 3.2.3/30203） |
| 23:43:23 | download 284,608 B | ETU 下载（v6 真包） |
| 23:59:30 / 00:00:11 | latest，currentVersionCode=**30202**+currentImageSha=**ab0585f7…** | 第二次完整流程（检查更新，自报身份与 v5 真包终点双值全等） |
| 00:00:15 | download 284,608 B | ETU 下载 |
| （传输+重启+复核） | — | BLE 传输约 2~3 分钟 → 设备重启 → 180s 复核窗口内确认 |
| **00:06:05 / 00:06:08 / 00:07:22** | latest，currentVersionCode=**30203**+currentImageSha=**3a282768…** → 200 no_update（114 B）×3 | **设备自报新身份与服务端注册全等**：30202→30203 升级成功且复核后无更新可用，闭环自洽 |

currentImageSha `3a282768…` 与 §3.1 四元组第 2 行（GET_INFO 终点比对
标准）全等；`30203 > 30202` 升级判定与 §3 判据 I 一致。

## 7.2 D 清理（2026-09-15 执行）

- r5 Quick Tunnel（cloudflared PID 3868）与 v6 服务（service.py PID
  17520，`--active-release real-30203`）均按 PID 核验命令行身份后
  `taskkill /F` 终止（进程路径全等核验：隧道为 admission worktree 项目内
  cloudflared.exe 指向 127.0.0.1:8443，服务为同 worktree
  `Tools/ota/p3-3-service/service.py`）。
- 残留验证：cloudflared 进程零残留、8443 端口零监听。
- 日志已落项目内（`service-v6-20260914.log`、
  `tunnel-r5-20260914.log`），无需搬移归档。

## 8. 边界声明

- 零真机操作：未连 J-Link，未读写设备、BCB、App 区、QSPI 槽。
- 零云端写入：受控测试服务为宿主本地进程 + Quick Tunnel 转发（B 路线
  既有授权范围）；GitHub Actions build.yml dispatch 按用户 2026-09-14
  「1授权」执行。
- 零产品代码改动：固件/App 源码零变化；tracked 改动仅
  `service_config.json`。
- 全部命令显式 `cd` admission worktree 执行，产物落项目内忽略目录。
