# P3-3 受控 v2 测试服务：方案、实现与宿主自测 —— 2026-09-13

> 依据用户 2026-09-13 第三轮裁定第 1 条：不接受 P4-2 作为 P3-3 唯一前置，
> 选择**独立的受控 v2 测试服务路线**——允许在项目内实现版本化测试服务、
> fixture 和针对性宿主自测，覆盖本卡使用的 latest、兼容门禁、token v2、
> 下载及摘要语义；不得放宽 App 校验，不得直接注入 OtaService 状态，不
> 扩展实现正式 register/D1/admin 发布链。
>
> **边界声明**：
> - 本服务**不证明 P4-2 通过**（未实现 register/D1/admin 发布链，也不经
>   这些链路；将来真实云端链须按届时实际 v2 实现重新审查）。
> - **启动对外服务或部署仍需具体授权**：本文 §6 部署申请待批；对手机
>   暴露端口（adb reverse）属于执行期动作，本批未执行。
> - 本批实际运行的仅为：宿主自测（进程内）与 CLI 冒烟（127.0.0.1 回环、
>   自消费、即起即停，见 §4）。

## 1. 设计（冻结源码 v1）

位置：`docs/ota-exec-notes/tools/p3-3-v2-service/`（提交入库）。

| 文件 | 身份（SHA-256） | 说明 |
| --- | --- | --- |
| `service.py` | `9869505723d0681dea3e3e38b0a83602e416688d6a9c03ada5655600d2d3ca0a`（34,497 B / 774 行） | 服务实现（Python 3 纯标准库） |
| `service_config.json` | `bb3372477aab79c36bb7a58bdc3b6db6f535383b5cdd27e8972d12824d981a5b`（2,613 B） | 冻结配置：两份 fixture 四元组 + 测试 token key |
| `selftest.py` | `60a414adae644c0e1f32d042dbd9262d37519d889288f8cf471105d7878d0287`（35,696 B / 795 行） | 宿主自测（13 项矩阵，§4） |

架构：核心逻辑 `V2ServiceState`（latest/download 处理、token 签发验签、
fixture 身份核验）与 HTTP 层（`ThreadingHTTPServer` 薄封装：路由、错误体
统一格式、请求日志、可选 TLS）分离，核心类可直接自测。

**语义覆盖（本卡使用的子集，对齐冻结契约
`docs/ota-cross-system-contracts.md` 与 App 端
`ota_firmware_latest.dart` / `ota_download.dart` fail-closed 解析器）**：

- latest：v2 响应精确 JSON（true 全字段 / false 精简体）、十参数闭集合
  校验（重复/未知/缺失/数值域）、处理顺序（参数→channel→确认更新→426
  App 门禁→409 兼容链 hardware→layout→Boot→protocol→签发 URL）、
  `UNKNOWN_DEVICE_MODEL` 不猜测机型、`CHANNEL_STOPPED` 不签发 URL。
- token v2：8 参数精确 query 集合、规范消息 7 行 LF（67 字节）、
  HMAC-SHA256 → Base64URL 无 padding、TTL 固定 300s、expiresAt 排他
  截止（`now >= expiresAt` 即 TOKEN_EXPIRED）、purpose=public-ota 只允许
  full|patch。
- 下载：完整 200 头集（`Content-Type: application/vnd.e-track.etu`、
  `Content-Length==sizeBytes`、强 ETag `"sha256-<hex>"`、
  `Accept-Ranges: bytes`、`Content-Disposition` 文件名、`X-Request-Id`、
  `X-Trace-Asset-Type: firmware`、RFC 9530 `Content-Digest`
  `sha-256=:<标准 Base64 含 padding>:`）；单区间 `Range: bytes=N-`
  （闭合区间/suffix/非十进制 → 400 `INVALID_PARAMETER`；N>=sizeBytes →
  416 + `Content-Range: bytes */size`）；If-Range 失配回退 200；206 带
  完整头集但按设计省略 Content-Digest（契约允许：该头若存在只表示本次
  response body）。
- 可见性（镜像真实链）：release 未被 stable 指针引用 → 410
  `ASSET_DISABLED`；archived → 409 `ASSET_ARCHIVED`；未知 releaseId →
  404；激活切换后旧 URL 作废。
- 错误体：`{"errorCode","message","requestId"}`，兼容 409 的
  required/actual 字段名与 App `OtaHttpError.fromBody` 读取键逐一对齐
  （`requiredHardwareRevision`/`actualHardwareRevision`、
  `requiredLayoutId`/`actualLayoutId`、`minBootVersion`/`bootVersion`、
  `minProtocolVersion`/`protocolVersion`）；426 带 `minAppVersionCode`，
  均不含 asset/URL。

**明确不实现（如实声明，非本卡使用语义）**：register/D1/admin 发布链、
patch 资产与 base 镜像语义（本卡 fixture 均 full）、v1 兼容窗口、限流
（`RATE_LIMITED`/429）、`Cache-Control: immutable`（受控服务用 no-store）。
黄金向量 `XC-TOKEN-V2-GOLDEN` 为 patch token，故在 sign/verify 单元层验证
（§4 T1/T2），不经过 full-only 的 release 配置。

**fixture 激活机制**：channel 指针经 `--active-release <key>|stopped|none`
启动参数注入，不改冻结配置文件；toy→真包切换 = 停服务换参数重启，全程
命令行与日志可审计。启动时按 config 声明的 size/SHA-256 逐字节核验两份
fixture（`.cache/p3-3-assets/e-track-at32f435-v3.2.1-full.etu` /
`…v3.2.2-full.etu`），失配拒绝启动（fail-closed）。

**设备兼容参数**（板上实读 + 源码实证）：两个 release 均配置
hardwareRevision=1 / layoutId=1 / minBootVersion=1 / minProtocolVersion=1
（板 fw_header 实读 hw_rev=1/layout_id=1/min_boot_ver=1；MCU `BOOT_VERSION=1`；
App `supportedProtocolVersion=1`），真机查询必然通过四道门禁；门禁链的
拒绝语义由自测用内存配置注入偏差值验证（§4 T7/T8）。

**token key**：config 内为测试专用 key（keyVersion=1，非黄金向量 key、
非生产 key），与 `XC-TOKEN-V2-GOLDEN` 的 keyVersion=7 区分；黄金向量在
自测中以内存配置走生产代码路径复算。

## 2. 与 App 端的互操作对齐（不放宽 App 校验）

App 走真实 HTTP 请求（Dio），不注入任何 OtaService 状态。服务满足的
App 侧硬性判定（均有自测断言）：

- `FirmwareLatestInfo.parse`：schemaVersion==2、requestId 非空、true 分支
  无 errorCode、appId=='trace'、deviceModel/channel 回显（App wire model
  `E-Track\0` → 映射 `e-track-at32f435`，ota_device_info.dart:43）、
  versionCode/baseVersionCode u32 域、minAppVersionCode 0..2100000000、
  asset.fileName `^[A-Za-z0-9._-]+$` ≤128 且 `-full.etu` 结尾、sizeBytes
  1..0x180000（284092/284112 均在域内）、full 时 baseVersionCode==0 且
  baseImageSha256 键存在值 null、downloadUrl 绝对 https+host。
- `ota_download.dart`：validateStatus 放行集之外的 4xx 不会出现（服务
  只发 400/401/404/409/410/416/426）；416→RANGE_AT_END（响应带
  Content-Length，App drain 不挂起）；401 TOKEN_*→URL_EXPIRED；410→
  URL_EXPIRED；409 ASSET_ARCHIVED→ASSET_CONFLICT；强 ETag `^"[!#-~]+"$`；
  206 头校验集逐项（Accept-Ranges/Content-Range N-M-T/Content-Length/
  If-Range 一致 ETag）；200 Content-Length==sizeBytes；Content-Digest
  RFC 9530 对实收字节交叉核对。
- 错误体 requestId 与 `X-Request-Id` 头一致存在（App 缺 body requestId
  时回退读头）。

## 3. 版本与变更纪律

源码版本 `SERVICE_VERSION = '1'`（`service.py` 顶部常量）。启动日志与
HTTP `Server:` 头携带版本。任何语义变更必须升版本并重新自测；配置内
fixture 四元组与 `.cache/p3-3-assets/` 实物绑定，不接受只有哈希声明而
无实物的配置。

## 4. 宿主自测（真实执行记录）

命令（worktree 根目录）：

```
cd docs/ota-exec-notes/tools/p3-3-v2-service
PYTHONIOENCODING=utf-8 python -B selftest.py
  > <repo>/.cache/p3-3-v2-service-selftest.log 2>&1
```

结果（2026-09-13，本机 Python 3.13+，退出码 0）：

```
PASS  黄金向量签名（独立复算+生产路径+参数顺序）
PASS  黄金向量验签与排他过期边界
PASS  真实配置 fixture 身份核验
PASS  配置加载 fail-closed（9 类拒绝）
PASS  latest 参数闭集合校验
PASS  latest 业务语义与 App 解析器镜像
PASS  latest 门禁顺序（426 先于 409）
PASS  latest 四维兼容链顺序与错误体字段
PASS  download token 八参数与签名拒绝
PASS  download token TTL 排他过期
PASS  下载可见性（410/409/404/切换作废）
PASS  Range/If-Range/416/摘要复算
PASS  线级回环（真实 HTTP 全链）
---- selftest 总计 13 项，失败 0 项 ----
```

测试矩阵要点（`selftest.py` 顶部 docstring 有完整清单）：

- **T1/T2 黄金向量**：独立复算 HMAC hex `0e68d9df…9bb35` 与 Base64URL
  `DmjZ33S6…uzU`、规范消息 67 字节、URL 参数顺序与冻结契约逐字节一致、
  verify 接受黄金 token、expiresAt 排他边界（`now==expiresAt` 拒绝、
  `expiresAt-1` 通过）。
- **T3/T4 fail-closed**：真实配置身份核验通过；篡改 sha/size/路径、
  channel 指向未知或 archived、非 300 TTL、kind=patch、非法 state、
  full 带 base 字段共 9 类全部拒绝构造。
- **T5-T8 latest**：参数闭集合 13 个负例；NO_UPDATE 精简体/stopped/
  激活语义（30200→30201→切真包→30202）/更高版本不推；App 解析器镜像
  逐字段；426 先于 409（app 86 < 99999 且 hw 不匹配 → 必须 426）；
  无更新时不评估 426；四维兼容链顺序与错误体字段名逐一断言（同时
  注入四维不匹配只报 hardware，不折叠）。
- **T9-T12 download**：八参数 10 个拒绝负例；TTL 边界（299s 通过、
  300s 整过期）；可见性 410/409/404/切换作废；200 头集 + RFC 9530 摘要
  复算 + 206 字节切片 + If-Range 失配 200 + 416 + 3 类非法 Range 400。
- **T13 线级回环**：ThreadingHTTPServer + urllib 真实 HTTP：latest→
  完整下载（284,092 B 字节一致）→断点续传 206→416→签名篡改 401→未知
  路径 404。

**CLI 冒烟**（覆盖 `main()` 参数接线/日志落盘；127.0.0.1 回环、自消费、
即起即停）：

```
python -B service.py --config service_config.json \
  --active-release toy-30201 --host 127.0.0.1 --port 18080 \
  --public-base-url http://127.0.0.1:18080 \
  --log-file <repo>/.cache/p3-3-v2-service/smoke.log
```

真实输出（关键行）：

```
SMOKE latest: versionCode=30201 updateAvailable=True requestId=1e53ce84...
SMOKE download: status=200 len=284092 sha16=fc4ae5a9fd1a9c13
SMOKE duplicate-param: status=400 body={"errorCode":"INVALID_PARAMETER",
  "message":"duplicate query param: channel","requestId":"03eddf83..."}
SMOKE PASS
服务启动 version=1 scheme=http listen=127.0.0.1:18080
  activeStable=toy-30201 fixtures=real-30202:…:284112:0a2eb26a481d,
  toy-30201:…:284092:fc4ae5a9fd1a
```

**自测发现并修复的缺陷（如实记录，均在交付前修复）**：

1. `Release._validate` 用 camelCase 名取 snake_case 属性（AttributeError，
   全部用例即红）→ 修为 snake_case。
2. 416 响应缺 `Content-Length`（HTTP/1.1 keep-alive 下 App `_drainBody`
   会挂到 60s 空闲超时）→ 补齐；自测断言 `Content-Length == len(body)`。
3. 状态层错误体缺 `requestId`（契约 OTA-XC-HTTP-ERROR 必含；此前仅
   HTTP 层兜底）→ `ServiceError` 携带 requestId，直调与线级两条路径
   错误体一致；黄金向量测试同步断言 `exc.request_id` 回传。

## 5. 手机访问方式与 HTTPS 方案（执行前人工验证的外部依赖）

**为什么必须 HTTPS**：App 端 `ota_firmware_latest.dart` 硬性要求
downloadUrl 为 https；Android 13（targetSdk≥28）禁止明文 latest；App 无
`badCertificateCallback`/`SecurityContext`（不得放宽）；`dart:io`
HttpClient 在 Android 只信任系统 CA → 证书必须公共可信，自签证书不可用。

**方案（主）**：PC 起服务 + `adb reverse tcp:<PORT> tcp:<PORT>`（手机侧
`127.0.0.1:<PORT>` → PC 端口）+ 公开 DNS 解析到 127.0.0.1 的回环域名
（localhost.direct / localcert.me 一类服务签发的公共可信证书）。
`--public-base-url https://<回环域名>:<PORT>` 与证书域名一致。

- **外部依赖标注**：回环域名证书服务的现状（域名、签发流程、有效期）
  无法在本环境在线验证（两次网页抓取被网络策略拦截）——**执行前人工
  验证**，hostname/端口/证书文件全部为 CLI 参数（`--tls-cert` /
  `--tls-key` / `--public-base-url`），不写死。
- **备选**：用户自有域名 + DNS-01 证书 + 局域网访问（服务绑
  `--host 0.0.0.0` 需另行授权）；或用户提供已验证的其他公共可信回环
  方案。由用户裁定。
- `--tls-cert`/`--tls-key` 缺省时纯 HTTP（仅宿主自测用，启动日志有
  warning；真机执行不得使用）。

## 6. 部署申请（待批，未执行）

执行 O2 时的服务启动序列（具体回环域名/端口/证书路径以执行前人工
验证结果为准）：

| # | 操作 | 命令要点 | 留证 |
| --- | --- | --- | --- |
| D1 | 启动（toy 激活） | `python service.py --config service_config.json --active-release toy-30201 --host 127.0.0.1 --port <PORT> --public-base-url https://<回环域名>:<PORT> --tls-cert <cert.pem> --tls-key <key.pem>` | 启动日志（版本/fixture 身份/激活指针） |
| D2 | 端口转发 | `adb -s 10ADA4197U001CK reverse tcp:<PORT> tcp:<PORT>` | 命令回显 |
| D3 | O2 观测期间 | 服务日志 `<repo>/.cache/p3-3-v2-service/service.log`（每请求一行：路径/状态/字节数/requestId）持续采集 | 与 App logcat 的 requestId 交叉 |
| D4 | toy→真包切换（O3 PASS 后） | 停服务 → `--active-release real-30202` 重启（同 D1 参数） | 两段启动日志 + 停启时间戳 |
| D5 | 关闭 | `adb reverse --remove tcp:<PORT>` → 终止服务进程 | 清理回显 |

- 授权口径：D1-D5 合并为一次部署会话申报；端口仅经 adb reverse 暴露给
  测试手机，不绑定非回环地址；日志全部落项目内 `.cache/p3-3-v2-service/`。
- 服务进程为长运行进程，执行方须在会话结束前确认无残留（同 J-Link
  logger 清残留纪律）。

## 7. 与合同/操作单的衔接

- 合同 external input `EXT-HTTP-TEST-SERVICE` 描述更新：由「P4-2 前置」
  改为「受控 v2 测试服务（本文档，冻结源码 v1 + 三件套哈希 + fixture
  四元组）」；fingerprint 绑定本文档 §1 三件套 SHA-256。见
  `P3-3-v1.contract.json` 修订（同批提交）。
- 操作单 O2「服务端请求日志」来源：本文 §6 D3 的 service.log（不再依赖
  云端写入单执行方）。
- 受验 APK 构建命令中的 `firmware_latest_url` 值 = §6 D1 的
  `https://<回环域名>:<PORT>/api/public/firmware/latest`（方式 iii 已
  落地，提交 `63db787`）。
- 云端写入单 B0-B4 暂停期间的替代：本服务覆盖 latest/门禁/token/下载/
  摘要语义；R2 对象键上传、channel 指针云端写入、githubUrl 等正式链
  仍按暂停标注处理（见 `P3-3-cloud-write-sheet-2026-09-13.md` 修订）。
