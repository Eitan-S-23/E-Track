# P3-3 资产/服务/APK 准备方案与版本占用检查 —— 2026-09-13

> 依据：用户 2026-09-13 八条意见第 1、4、5 条。本文为**方案与盘点文档**，
> 未构建任何资产、未部署任何服务、未写任何设备、未改任何产品代码。

## 1. 版本占用检查（30201/30202 确认未被占用）

按用户裁定采用顺序 **当前 3.2.0(30200) → toy 3.2.1(30201) → 真包 3.2.2(30202)**。占用核查（全仓库检索 + 历史证据链）：

| 检查面 | 结果 |
| --- | --- |
| 源码/工具/契约（USER/Libraries/Tools/boot/PLAN-OTA.md/ota-binary-contracts.md） | 无 30201/30202/3.2.1/3.2.2 任何引用 |
| git 历史（`git log --all -S`） | 无任何提交引入过 30201/3.2.1 |
| git tag | 仓库无 `v3*` tag |
| 测试向量（tests/ota-vectors/expected.json） | 仅 20700/20800；golden vectors 的 toy 版本空间（2.7.x/2.8.x）与 3.2.x 无交集 |
| 冻结验收包（docs/acceptance-contracts/） | 无 3.2.1/3.2.2 资产 |
| OTA 历史链（板上 BCB 20801 = P1-3 验收 TEST_BOOT 确认的 2.8.1，见 `docs/ota-exec-notes/P1-3-P1-5-acceptance-2026-07-28.md:117-120`） | 3.2.x 空间无历史 OTA 落地 |

**结论：30201/30202 未被占用，可用。** 但注意 `USER/App/Version.h:28` 仍是
`VERSION_SOFTWARE "v2.7"`——板上 3.2.0 不是从 Version.h 推导的，而是 P3-2
验收时用 `etu_pack.py finalize --ver-name 3.2.0` 显式打上的（
`docs/ota-exec-notes/P3-2-implementation-evidence.md:200-203`）。3.2.1/3.2.2
资产沿用同一 finalize 显式版本路径，不动 Version.h。

## 2. 两类安全资产准备方案（toy 3.2.1 / 真包 3.2.2）

### 2.1 流程（全部既有工具，零产品代码改动）

| 步骤 | toy 3.2.1 | 真包 3.2.2 | 工具 |
| --- | --- | --- | --- |
| 1. 源镜像 | 主 worktree `X-Track-App-GCC.bin`（602984B，`7328c1b1…`，与板上运行镜像同源，**可启动性已有板上实机证据**） | 同左（若冻结点源码变化则从 freeze_commit 重建——见 2.3 待决） | 既有 GCC 产物 |
| 2. finalize | `etu_pack.py finalize --ver-name 3.2.1 --build-ts <T1>` | `etu_pack.py finalize --ver-name 3.2.2 --build-ts <T2>` | `Tools/etu_pack.py`（P3-2 先例） |
| 3. 封包 | `etu_pack.py pack-full --app <finalize后镜像> --target-vcode 30201` | 同左，30202 | `Tools/etu_pack.py` |
| 4. 离线验证 | `etu_unpack.py verify_fw_header` + 双零摘要复算 + 版本/长度/SHA 全项核对；`410` 检查模拟（30201>30200 ✔、30202>30201 ✔） | 同左 | 既有验证器 |
| 5. 落盘 | 项目内被忽略目录（如 `.cache/p3-3-assets/`），摘要四元组分记 | 同左 | — |

### 2.2 身份四元组（分开记录，不混用——用户第 4 条要求）

每份资产分别记录：
1. **原始 pre-finalize BIN SHA-256**（finalize 前的源镜像摘要，即 `7328c1b1…` 或重建产物）；
2. **最终镜像 raw SHA-256**（finalize 后含 fw_header 的完整镜像——GET_INFO 终点比对的就是它）；
3. **fw_header 双零摘要**（off40..71/off92..95 置 0 后整镜像 SHA——板上身份链口径）；
4. **ETU 包 SHA-256 + size**（封包产物）。

toy 与真包各自一套四元组 + 目标 versionCode/version_name + build_ts，分别绑定
`ART-TOY-{ETU,TARGET-IMAGE}` / `ART-REAL-{ETU,TARGET-IMAGE}`，不同包改名。

### 2.3 边界与待决点

- **不修改** Boot、BCB、OTA 校验逻辑（ota_backup.c/ota_package.c/boot_state_machine.c 零改动）；不写设备（纯离线制包）。
- **不手改二进制头**：fw_header 一律经 `etu_pack.py finalize` 回填。
- **toy 资产语义澄清（待非实现会话裁定）**：本方案 toy = 与真包同一镜像源、仅版本号不同的"可启动受控包"。任务书对 toy 的要求是"保留真实 Boot/BCB/OTA 路径且具有合法 fw_header"——同源镜像天然满足可启动性（板上实机运行中）；**如果**验收会话要求 toy 具备与真包可区分的功能性标记（不只是版本号），需另行说明鉴别判据，当前合同判据是 versionCode+raw SHA 区分，本方案已满足。
- **真包源镜像基线（待冻结时定）**：若 freeze_commit ≠ c89c58f 的源码树，602984B 镜像需从冻结点重建（GCC 全量构建）再 finalize/封包；若冻结点源码与 c89c58f 相同则可直接复用 `7328c1b1…`。这属于正常准备流程，非新增决策。
- **现有工具不满足时**：集中报告缺口，不绕过（用户第 4 条原文）。当前评估：etu_pack.py 的 finalize/pack-full/verify 链覆盖全部需求，无缺口。

## 3. 受验 APK 方案（用户第 5 条）

### 3.1 现状（本轮 build-only run 34730618341 实测日志）

```
Cloudflare update manifest URL is not configured; APK will use the legacy
GitHub latest manifest and no default firmware endpoint.
Cloudflare update payload public key is not configured; signed Cloudflare
manifests will fail closed.
Android release signing is not configured; falling back to debug signing.
```

即当前 release APK（`2a5d5db9…`）：**无固件 latest endpoint（dart-define 未注入）**、
**无签名公钥（Cloudflare 清单会 fail closed）**、debug 签名。

### 3.2 必须先解决的入口问题（构建前确认，避免构建后才发现不可用）

App 的固件升级入口 `TRACE_CLOUDFLARE_FIRMWARE_LATEST_URL` 在 build.yml 中由
`vars/secrets.TRACE_PUBLIC_UPDATE_SERVICE_URL` 推导；仓库 variables 当前为空
（`gh api actions/variables` → total_count=0），secrets 无法读取但 run 日志
证明该分支未走到（"not configured"）。因此：

**要使受验 APK 能对受控 HTTP 服务发真实 latest/下载请求，必须满足其一：**
- 方案 i：配置仓库 variable/secret `TRACE_PUBLIC_UPDATE_SERVICE_URL=<受控服务地址>`——**这是仓库配置变更，须用户授权**；此后任何 APK 构建都会注入该 endpoint；
- 方案 ii：用 dev-checks 的观测 APK 路径（`dev_apk.py:178` 经 `--dart-define=TRACE_CLOUDFLARE_FIRMWARE_LATEST_URL` 注入 `observation_firmware_latest_url` 输入）——但这产 debug APK，与"release 模式受验 APK"要求冲突；
- 方案 iii：改造 build.yml 加 workflow_dispatch 输入（类似 dev-checks 的 `observation_firmware_latest_url`）——**这是 workflow 改动，属本批授权允许的 build.yml 输入绑定范围，但改动后需新构建，而 build-only 配额已用尽 3/3**。

**结论：endpoint 注入方式需要用户裁定（推荐 iii，理由：不污染全局仓库配置、输入显式可审计；代价：需一次追加 build-only 配额）。** 注入的 endpoint 指向受控测试服务（§4）。

### 3.3 APK 身份绑定（安装判据用）

- 包名 `com.wen.gaia.gaia`；versionName/versionCode 以 pubspec（当前 `1.0.60+86`）为准，若冻结点有 bump 则按新值；
- **证书指纹**：debug 签名回退下为 CI debug keystore 指纹——须从 APK 实物提取（`keytool -printcert -jarfile`）并在合同绑定；**须先验证与手机上既有安装 `1.0.60(86)` 的签名是否一致**（既有 APK SHA `428a5d3a…` 同为 CI 产物，大概率同一 debug keystore，但须实物核验，不预设结论）；
- 冲突处理：若签名不一致 → **不默认卸载/清数据**，停下来报用户裁定（用户第 5 条原文）。

## 4. 受控 HTTP 测试服务方案（用户第 5 条，待批准后部署）

### 4.1 现状盘点

- 既有 staging 服务 `https://trace-update-public-staging.pages.dev`（T1a 观测轮用过）**仍在运行**：`/api/public/latest` 正常返回 JSON（versionCode 86）；`/api/public/firmware/latest` 缺 `deviceModel` 参数返回 400（参数校验 fail-closed，符合固件端点契约）；
- 该服务是**真实 staging 实例**（Cloudflare Pages，部署于 P4-2 前的早期验证），其 D1 数据是历史 fixture；
- 仓库内服务源码：`app/bluetooth_flutter_Trace/cloudflare/update-service/`（worker/src/firmware.ts 等）。

### 4.2 方案（两个选项，待用户选择）

**方案 A：复用现有 staging Pages + 新增固件 fixture（推荐，零部署）**

- 位置/域名：`https://trace-update-public-staging.pages.dev`（既有实例，不动生产渠道）；
- 手机访问：HTTPS 公网可达（T1a 观测轮已验证手机可达该域名）；
- 代码/fixture 版本：以当前仓库 `cloudflare/update-service` 部署的版本 + 在其 D1 登记固件 release fixture（`register-firmware-release.mjs` / `upload-firmware-r2-asset.mjs` 既有脚本）；fixture = toy/真包 ETU 的 release 元数据（target_vcode 30201/30202、sha、size、URL 指向 R2 或 Pages 静态资产）；
- latest/download/token 行为：走真实 `/api/public/firmware/latest?appId=…&deviceModel=…` 与下载端点，不旁路任何检查（token 行为按该端点既有实现）；
- 资产身份：ETU 文件 sha/size + D1 登记记录快照；
- 日志位置：Cloudflare Pages/Worker 请求日志 + App 侧抓包/日志（观测插桩）；
- 有效期/清理：fixture 登记与 R2 资产在验收轮结束后由后续授权删除；
- **不宣称**真实 P4-2 register/R2/D1 链已通过——fixture 是测试输入，不是生产链证明。
- **风险**：该 staging 实例当前 D1 里 `/api/public/latest` 返回的是 APK 更新数据（86）；固件端点是独立路径（firmware.ts），互不干扰；但 D1 写入（登记 fixture）是对既有 staging 资源的写入，**需用户批准**（"不得触碰真实用户数据"——staging D1 非生产数据，但写入动作本身需授权）。

**方案 B：全新独立测试服务实例**

- 从仓库源码在独立 Pages 项目/workers.dev 域名部署一个全新实例，D1 从零初始化，只灌 fixture；
- 优点：与既有 staging 完全隔离；缺点：需要 Cloudflare 部署授权 + 新域名（App endpoint 注入指向它）；
- 部署命令与 STAGING-SETUP.md 流程既有。

**待用户裁定：A 或 B。** 两者都不触碰生产发布渠道与真实用户数据。

## 5. 升级顺序与 BCB 阻断的关系

板上 3.2.0(30200) → toy 3.2.1(30201) 满足 `ota_backup.c:410`（候选严格高于当前镜像）；真包 3.2.2 再叠加。但 **BCB 20801≠30200 的前置阻断（`ota_backup.c:385`）在任何目标版本下都存在**，见 `P3-3-bcb-blocker-clarification-2026-09-13.md`。执行顺序按用户第 6 条：

```
交接材料及 schema 修正（本轮）
→ BCB/镜像身份问题澄清（已落盘，恢复方案待裁定）
→ 两类安全资产及服务/APK 方案确定（本文，待裁定 endpoint 注入方式与服务选项）
→ 必要准备和自测（资产构建+离线验证；按需追加 build-only 配额的受验 APK 构建）
→ 非实现会话审查精确合同
→ 用户审批 → 冻结及 NOT_RUN 前检 → 分阶段实机执行
```

## 6. 待用户裁定/授权清单（本文产出）

| # | 事项 | 选项 | 建议 |
| --- | --- | --- | --- |
| 1 | 受验 APK endpoint 注入方式 | i 仓库 variable / ii dev APK / iii build.yml dispatch 输入 | iii（需追加 build-only 运行数） |
| 2 | 受控 HTTP 服务 | A 复用 staging+fixture / B 全新实例 | A |
| 3 | staging D1 fixture 写入授权 | 批准/不批准（方案 A 前置） | — |
| 4 | BCB 最小恢复方案 A 失败后是否允许进入 B（TEST_BOOT 流程） | 见 BCB 澄清文档 §4 | 待 toy 闭环实机观测后再定 |
| 5 | 资产构建启动授权（离线制包，不写设备） | 授权后即可执行 §2 流程 | 用户第 4 条已授权"允许在项目内准备和离线验证资产"——**视为已授权，待合同冻结点确定源镜像基线后执行** |

## 7. 边界声明

- 本轮零构建、零部署、零真机操作、零产品代码改动；云端只做了两次 GET 探测（公开端点可达性，不写任何数据）。
- staging 服务现状探测（latest 返回 86、firmware 400 deviceModel）是公开只读观测，结果如实记录。
