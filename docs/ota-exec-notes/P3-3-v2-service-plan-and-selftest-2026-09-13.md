# P3-3 受控 v2 测试服务：方案、实现与宿主自测 —— 2026-09-13（第五轮修订，源码 v2）

> 依据用户 2026-09-13 第三轮裁定第 1 条确立受控 v2 测试服务路线（原边界
> 声明继续有效：不证明 P4-2 通过、不实现正式发布链、不放宽 App 校验、
> 不直接注入 OtaService 状态）。
>
> **第五轮修订（P3-3-EXEC-AUTH-20260913 第二节，2026-09-13）**：
> - 真机 HTTPS 路线直接确定为 **Quick Tunnel**（§5 重写）：本轮测试专用、
>   不用 Cloudflare 账号、不读旧 token；v2 版把「随机 URL 与 APK 注入
>   冲突」列为排除理由的论证被用户裁定不成立——正确解法是执行顺序
>   （先隧道取地址→宿主端到端检查→注入唯一一次受验 APK 构建→绑定合同），
>   而非要求 URL 先于一切固定。
> - §6 D 序列去掉 adb reverse（本路线不需要），新增隧道生命周期管理
>   （8 小时窗口、地址变化即暂停、toy→真包切换只重启本机后端不动隧道）。
> - 状态语言按授权书第五节更新：已获条件授权的项标「已授权，待前检/执行」。
>
> **第四轮修订（2026-09-13 裁定第 2/3 条）**：
> - 修复三项实测缺陷：requestId 未贯通（日志/响应体/响应头三方统一）、
>   protocolVersion=2 误放行（补 409 PROTOCOL_UNSUPPORTED 门禁）、token
>   kind 与资产类型不符误分类 404（修正为 401 TOKEN_INVALID）；普通日志
>   签名参数脱敏。自测 13→**16 项**（原 13 项通过记录保留不改写）。
> - 新增 `tls_hostcheck.py`：以真实 CLI 参数 + TLS 启动服务的宿主 HTTPS
>   全链验证（测试 CA、双负例、curl Schannel 交叉），PASS。
> - 四件套迁入受管目录 `Tools/ota/p3-3-service/`（原
>   `docs/ota-exec-notes/tools/p3-3-v2-service/` 废弃），fixture 相对路径
>   基准改为仓库根；`Tools/provenance/manifest_profiles.json` 的
>   Validation profile required_paths 已补齐四件套与恢复 runner。
> - §5/§6 按「HTTPS 硬前置」重写：宿主 HTTPS 已实证，真机域名/证书路线
>   A/B 待批输入清单化；D5 重定义为完整清理与无残留验证。（第五轮已
>   被上节取代——路线 A/B 降为 Quick Tunnel 不可用时的备选。）

## 1. 设计（源码 v2，受管路径）

位置：`Tools/ota/p3-3-service/`（提交入库，git mv 保留历史）。

| 文件 | 身份（SHA-256） | 说明 |
| --- | --- | --- |
| `service.py` | `f71012de119811863d2274fd674a702c69a512f18ea73e3188be2233130ba009`（38,737 B / 842 行） | 服务实现（Python 3 纯标准库，`SERVICE_VERSION='2'`） |
| `service_config.json` | `2facafa60fb4c65944c55168d46a2fbf2b2de7ea05d46e47beffa850cc7ce39c`（2,589 B / 66 行） | 冻结配置：两份 fixture 四元组 + 测试 token key；fixture 相对路径以仓库根为基准 |
| `selftest.py` | `b96d4e2f05c84c3401c1dff14ee9c0f6e5dc7ee0a076e272180d2f4d4aa202b4`（45,777B / 988 行） | 宿主自测（**16 项**矩阵，§4） |
| `tls_hostcheck.py` | `f9202b6b47f50526e75710fd2b8048e87b24bb94ab07f82b88716a761821da6c`（14,937 B / 332 行） | 宿主 HTTPS 全链验证（§4.2） |

架构不变：核心逻辑 `V2ServiceState` 与 HTTP 层（`ThreadingHTTPServer`
薄封装：路由、错误体统一格式、请求日志、可选 TLS）分离，核心类可直接
自测。

### 1.1 v1 语义（全部保留）

latest v2 响应精确 JSON / 十参数闭集合校验 / 处理顺序（参数→channel→
确认更新→426 App 门禁→409 兼容链→签发 URL）/ `UNKNOWN_DEVICE_MODEL`
不猜机型 / `CHANNEL_STOPPED` 不签发 URL；token v2 八参数精确集合、规范
消息 7 行 LF（67 字节）、HMAC-SHA256 → Base64URL 无 padding、TTL 300s
排他过期、purpose=public-ota 只允许 full|patch；下载完整 200 头集
（含 RFC 9530 `Content-Digest`）、单区间 Range/416/If-Range/206；可见性
410/409/404/切换作废；错误体与 App `OtaHttpError.fromBody` 读取键逐一对
齐。fixture 激活机制（`--active-release`）、启动时身份核验 fail-closed、
设备兼容参数（hw1/layout1/boot1/proto1）、测试 token key 隔离——均同
v1 文档记录，不变。

### 1.2 v2 修复（第四轮裁定第 2 条）

1. **requestId 贯通**：`do_GET` 一次生成 → 传给状态层
   `handle_latest`/`handle_download`（`request_id=None` 参数，None 时自
   生成保持直调路径语义）→ 响应体 `requestId`、响应头 `X-Request-Id`、
   日志 `req=` **三方同一 ID**。v1 缺陷实测：latest 响应体 requestId 与
   日志 req 不同（HTTP 层与状态层各生成一个）。
2. **协议门禁**：`SUPPORTED_PROTOCOL_VERSIONS = (1,)`；
   `protocolVersion < min 或 not in SUPPORTED` → 409
   `PROTOCOL_UNSUPPORTED`（契约 `ota-cross-system-contracts.md`「或协议
   版本不受支持时」）。错误体含 `minProtocolVersion`/`protocolVersion`/
   `releaseId`，与 Dart 读取键一致。v1 缺陷实测：protocolVersion=2 返回
   200（仅校验下限）。
3. **token kind 分类**：签名有效但 kind 与资产类型不符 → 401
   `TOKEN_INVALID`（契约「query 与 D1 资产类型或用途不一致时」；extra
   字段 `tokenKind`/`assetKind`）；`assetId` 不符保留 404
   `RELEASE_NOT_FOUND`。v1 缺陷实测：full 资产 + kind=patch token 返回
   404（分类错误）。
4. **日志脱敏**：普通请求日志中的签名 URL 参数替换为
   `signature=<redacted>`（模块级 `redact_path_for_log`；Base64URL 值域
   `[A-Za-z0-9_-]` 不含 `&`/`#`，正则安全）。

**边界声明（第四轮裁定原文口径）**：Python 中的「App 解析器镜像」是宿主
自测辅助，**不构成真实 Dart consumer 验证**；真实 App 消费行为留在 O2
观测（未批未执行）。

## 2. 与 App 端的互操作对齐（不放宽 App 校验）

同 v1（§2 全部内容继续有效）：App 走真实 HTTP（Dio）、不注入状态；
`FirmwareLatestInfo.parse` / `ota_download.dart` 的全部硬性判定均有自测
断言。v2 增补：协议门禁与 kind 分类的错误体字段名同样与
`OtaHttpError.fromBody` 读取键对齐。

## 3. 版本与变更纪律

`SERVICE_VERSION = '2'`。启动日志与 HTTP `Server:` 头携带版本。任何语义
变更必须升版本并重新自测；fixture 四元组与 `.cache/p3-3-assets/` 实物
绑定。相对路径一律以仓库根为基准（`find_repo_root` 识别 git worktree
的 `.git` 文件），服务目录在仓库内的位置变化不影响 fixture 定位。

## 4. 宿主自测（真实执行记录，2026-09-13，新路径）

### 4.1 矩阵自测 16 项

```
cd Tools/ota/p3-3-service
PYTHONIOENCODING=utf-8 python -B selftest.py
  > <repo>/.cache/p3-3-v2-service-selftest.log 2>&1
```

结果（退出码 0）：**16 项全 PASS**（控制台中文在 GBK 终端显示为乱码，
日志文件为 UTF-8 正常）：

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
PASS  协议门禁（不低于最低版本但仍不受支持）→ 409   ← v2 新增（第 11 项）
PASS  token kind 不符（签名有效）→ 401              ← v2 新增（第 12 项）
PASS  线级 requestId 三方一致与日志脱敏             ← v2 新增（第 13 项）
---- selftest 总计 16 项，失败 0 项 ----
```

（前三项 v2 新增的编号沿用 selftest 内部 TESTS 列表顺序；原 13 项通过
记录保留不改写。）

新增三项要点：
- **协议门禁**：proto∈{2,3,255} → 409 + 字段断言；proto=0 → 409（下限
  分支）；proto=1 → 200 true（防误伤）；min 抬到 2 后 proto=1 → 409
  （双臂——「不低于最低版本但仍不受支持」与「低于最低版本」都覆盖）。
- **kind 分类**：真实 key 为 full 资产签 kind=patch token → 401
  TOKEN_INVALID + `tokenKind='patch'`/`assetKind='full'`；kind=recovery
  （验签层拒绝）→ 401；对照 assetId 不符（kind=full 签名有效）→ 404。
- **requestId 线级**：成功 latest / 篡改签名 401 / 下载 200 三场景断言
  `headers['x-request-id'] == body['requestId'] == 日志 req=`；错误/
  下载行断言 `signature=<redacted>` 出现且原签名值不出现；日志竞态用
  轮询等待（5s 上限，响应已到而日志未落 handler 的窗口）。

### 4.2 宿主 HTTPS 验证（tls_hostcheck.py，第四轮裁定第 3 条）

```
cd Tools/ota/p3-3-service
python tls_hostcheck.py
```

真实 CLI 启动参数（与 D1 形态一致，host/port/证书为宿主测试值）：

```
python service.py --config service_config.json --active-release toy-30201
  --host 127.0.0.1 --port 18443
  --public-base-url https://127.0.0.1:18443
  --tls-cert <repo>/.cache/p3-3-tls/server.pem
  --tls-key   <repo>/.cache/p3-3-tls/server.key
  --log-file  <repo>/.cache/p3-3-tls/tls-service.log
```

结果（2026-09-13，openssl "OpenSSL 3.5.5" / curl 8.13.0 Schannel，
退出码 0）：

- 证书：测试 CA（`basicConstraints critical CA:TRUE`，30 天）+ 服务器证
  书（SAN `DNS:localhost,IP:127.0.0.1`，EKU serverAuth）；
  notBefore=Sep 13 09:31:44 2026 GMT / notAfter=Oct 13 09:31:44 2026 GMT。
- latest（真机十参数）200：requestId 头体一致，downloadUrl https 前缀。
- 整包下载 200：284,092 B，SHA-256 与冻结四元组一致（`fc4ae5a9…`）。
- DNS:localhost 名字路径 200（SAN DNS 校验走真实路径）。
- TLS 版本 TLSv1.3（服务端 minimum TLSv1_2）；subject/issuer 与测试
  CA 链一致。
- 负例 1：不加载测试 CA（仅系统信任库）→ 证书校验失败（非无校验 TLS）。
- 负例 2：客户端上限压 TLS 1.1 → 无法完成握手。
- curl `--cacert` 交叉（独立 TLS 实现）：HTTP 200、
  `ssl_verify_result=0`。
- 服务进程 terminate 干净退出，日志落 `.cache/p3-3-tls/`。

**Schannel 吊销说明（如实登记）**：Windows curl（Schannel 后端）默认强制
吊销检查；测试 CA 无 CRL/OCSP 端点时会报
`CERT_TRUST_REVOCATION_STATUS_UNKNOWN`。验证命令加
`--ssl-revoke-best-effort`——**仅对「吊销状态未知」放行，证书链校验仍
完整执行**（`ssl_verify_result=0` 断言不变）。真机执行不涉及 curl。

**边界声明**：测试 CA 仅供宿主验证服务的 TLS 实现与证书链配置，**不是**
App 侧公共可信证书；真机 O 序列使用的域名/证书链/有效期按 §5 路线另行
绑定。本脚本不放宽 App 校验、不安装任何系统 CA。

## 5. 真机 HTTPS 路线（已确定：Quick Tunnel；授权 P3-3-EXEC-AUTH-20260913 第二节）

**HTTPS 是当前受验 App 的硬前置**：App 端
`ota_firmware_latest.dart` 硬性要求 downloadUrl https；Android 13
（targetSdk≥28）禁止明文 latest；App 无 `badCertificateCallback`/
`SecurityContext`（**不得放宽**）；`dart:io` HttpClient 在 Android 只信任
系统 CA。

宿主侧已实证（§4.2）：服务的 TLS 实现与证书链配置可工作。真机路线按
授权第二节直接确定如下，**不再要求用户提供域名、DNS API token 或证书
策略**。

### 5.1 主路线：Cloudflare Quick Tunnel（已授权，待前检/执行）

- **形态**：一个测试专用 Quick Tunnel——`cloudflared tunnel --url
  http://127.0.0.1:<PORT>`，生成随机 `*.trycloudflare.com` HTTPS 地址；
  Cloudflare 边缘终止 TLS（边缘证书公共可信，App 侧 `dart:io` 系统信任
  库可直接校验，**不改变 App 的证书或 HTTPS 校验**）；隧道到本机服务走
  127.0.0.1 HTTP（本服务不绑局域网地址、无 `--tls-cert`）。
- **执行顺序（消除「随机 URL 与 APK 注入冲突」的正确解法）**：
  1. 启动隧道，取得实际 HTTPS 地址；
  2. 宿主端到端检查（§5.2）全过；
  3. 该地址注入唯一一次受验 APK 构建（dispatch
     `firmware_latest_url=https://<trycloudflare 地址>/api/public/firmware/latest`）；
  4. 地址绑定进合同（执行时回填，见 §7）。
- **账号边界**：Quick Tunnel 不使用用户的 Cloudflare 账号、不读取任何
  token（含旧环境 token），不触发云端写入单 §9 CF 账号规约的申报前置
  （该规约仅适用于 Named Tunnel/账号类操作，见云端写入单 §9 注记）。
- **暴露范围（授权原文口径）**：只暴露本服务的 latest/download 端点及
  两份已绑定测试 ETU（toy-30201 / real-30202 的 fixture 配置内资产）；
  不得暴露其他本机服务、文件、日志或管理接口（本服务实现无管理端口，
  127.0.0.1 绑定保证隧道只能到达本服务）。
- **窗口**：开放窗口最长 **8 小时**；本轮结束或到期即关闭（§6 D5）。
- **toy→真包切换**：只重启本机后端（`--active-release` 切换），**维持
  同一隧道进程和公网地址**；地址改变或隧道退出时暂停相关阶段，不偷偷
  换地址、不自动消耗额外 APK 构建。
- **本路线不需要 adb reverse**：不创建、不删除任何 adb reverse 映射
  （授权明示「不要沿用旧方案去创建或删除无关映射」）。
- **cloudflared 二进制获取**：下载到 admission worktree
  `.cache/p3-3-cloudflared/`（路径预检：写入位置在活动 worktree 内；
  不全局安装、不修改全局 PATH；下载源为官方发布渠道，落盘后登记 SHA-256）。

### 5.2 宿主端到端检查（注入 APK 前的门槛，全部通过才可消耗构建配额）

用真实 CLI 参数启动服务（127.0.0.1 HTTP 形态）+ 隧道，从公网地址执行：

1. `GET https://<隧道地址>/api/public/firmware/latest?…（真机十参数）` →
   200、schemaVersion=2、downloadUrl 为同一隧道地址的 https 前缀；
2. 按 downloadUrl 整包下载 toy ETU → 200、字节数与 SHA-256 与冻结
   四元组一致（`fc4ae5a9…` / 284,092 B）；
3. 证书链为 Cloudflare 边缘证书（公共可信——宿主默认信任库直接校验
   通过，无需加载任何测试 CA）；
4. 负例：路径外资源（如 `/`、`/api/ci/…`）不暴露本机其他内容（按服务
   实现返回 404/405，隧道不放大暴露面）。

结果（含隧道地址、时间戳、命令与响应摘要）落盘
`.cache/p3-3-v2-service/quicktunnel-hostcheck.log` 并回填本节，作为
O 序列与合同 EXT 条目的前置证据。

### 5.3 替代路线（仅 Quick Tunnel 确实不可用时集中申报，本轮不启用）

| 路线 | 说明 | 申报前置 |
| --- | --- | --- |
| 路线 A：自有域名 + Let's Encrypt DNS-01 + 局域网直连 | 用户域名 A/AAAA → PC 局域网 IP，DNS-01 签发公共可信证书，服务绑非回环地址 | 按 v2 版原 §5 路线 A 清单：域名、DNS-01 执行方式（手动 TXT 或 ACME+DNS token）、证书策略、局域网直连授权四项输入 |
| 路线 B：Cloudflare Named Tunnel | `cloudflared tunnel` 具名隧道 + DNS zone 绑定 | 按授权第二节末段与云端写入单 §9：先浏览器鉴权 → 核对 account ID 与资源归属 → 排除旧 token 覆盖；不得通过聊天索取或输出 token/cookie |

### 5.4 已排除路线（论证，维持）

| 路线 | 排除原因 |
| --- | --- |
| mkcert / 自签 / 用户 CA | 非公共可信；Android 系统信任库外（用户 CA 对 `dart:io` HttpClient 无效）→ 等效放宽校验，禁止 |
| 回环域名服务（localhost.direct / localcert.me 等） | 现状无法在本环境在线验证；依赖第三方可用性与续期；Quick Tunnel 已获批，无需引入 |
| adb reverse + HTTP | 仅端口转发，无 TLS、不解决证书信任；App 明文禁止；授权明示本路线不需要 adb reverse |

**真机执行绑定要求（O2 前置检查）**：隧道地址（完整 URL）、本地端口、
服务启动命令行（§6 D1 形态）、cloudflared 进程 PID、宿主端到端检查
记录（§5.2）全部落盘留证；8 小时窗口起止时间登记，窗口须覆盖剩余
O 序列全程。

## 6. 部署序列（已授权，待前检/执行；D1-D5，Quick Tunnel 路线）

执行 O 序列时的服务与隧道启停序列（无 adb reverse——授权明示本路线不需要，
不创建、不删除任何映射）：

| # | 操作 | 命令要点 | 留证 |
| --- | --- | --- | --- |
| D1 | 启动（服务 + 隧道，两个独立进程） | ① `python service.py --config service_config.json --active-release toy-30201 --host 127.0.0.1 --port <PORT> --public-base-url https://<隧道地址> --log-file <repo>/.cache/p3-3-v2-service/service.log`（**HTTP 形态，无 --tls-cert/--tls-key**——TLS 由隧道边缘终止）；② `<repo>/.cache/p3-3-cloudflared/cloudflared.exe tunnel --url http://127.0.0.1:<PORT>`（Quick Tunnel，不读账号 token；日志重定向到项目内 `.cache/p3-3-cloudflared/tunnel.log`）；③ 从隧道日志捕获实际 `https://<随机>.trycloudflare.com` 地址，回填 `--public-base-url` 后重启一次服务（或以地址启动顺序：先隧道后服务，避免二次重启） | 启动日志（版本=2/fixture 身份/激活指针）+ 隧道日志含地址行 + 两进程 PID + 窗口起始时间戳 |
| D2 | 宿主端到端检查（§5.2；注入 APK 的门槛） | latest 真机十参数 → 200；downloadUrl 同隧道地址 https；整包下载 SHA 与冻结四元组一致；负例路径不放大暴露 | `quicktunnel-hostcheck.log`（地址/时间戳/命令/响应摘要） |
| D3 | O2 观测期间 | 服务日志持续采集（每请求一行：脱敏路径/状态/字节数/req=）；隧道进程保持运行 | 与 App logcat 的 requestId 交叉 |
| D4 | toy→真包切换（O3 PASS 后） | **只停服务** → `--active-release real-30202` 重启（同 D1 参数，含同一 `--public-base-url`）；**隧道进程不动**（授权原文：维持同一隧道进程和公网地址）。地址改变或隧道退出 → 暂停相关阶段并申报，不换地址、不追加 APK 构建 | 两段服务启动/停止日志 + 时间戳（隧道 PID 不变即留证） |
| D5 | **完整清理（含验证）** | ① 按记录的 PID 终止隧道进程（cloudflared，不按名字误杀）→ ② 按记录的 PID 终止本次服务进程（记录退出码）→ ③ 日志与证据归档到项目内 `.cache/p3-3-v2-service/`（service.log、tunnel.log、启动命令行、地址、窗口起止）→ ④ **无残留验证**：`Get-Process` 按两 PID 核对均不存在、`Get-NetTCPConnection -LocalPort <PORT>` 无监听、`.cache` 内日志文件齐且有 SHA | 四步各自回显 |

- 授权口径：D1-D5 属于 P3-3-EXEC-AUTH-20260913 第二节的隧道与服务管理
  授权范围（创建并运行本轮短期公网隧道，只暴露本服务 latest/download 端点
  及两份已绑定测试 ETU；开放窗口最长 8 小时，本轮结束或到期即关闭）。
- **8 小时窗口**：D1 启动时登记起始时间戳；窗口到期或 O 序列/清理完成即
  执行 D5 关闭。窗口内未完成的相关阶段暂停并申报，不自动续窗口。
- **D5 的清理是判据不是善后**：残留（隧道进程/服务进程/监听端口/日志缺失）
  记 HARNESS_FAIL。
- 服务与隧道均为长运行进程，执行方须在会话结束前确认无残留（同 J-Link
  logger 清残留纪律，按 PID 精确核对）。
- cloudflared 的启动缓存/日志默认路径若在用户目录（`~/.cloudflared/`），
  须以项目内参数（`--no-autoupdate`、日志重定向、`--origincert` 不涉及——
  Quick Tunnel 不用证书）收敛到 worktree `.cache/` 内；执行前按全局
  「非项目目录写入边界」做路径预检。

## 7. 与合同/操作单的衔接

- 合同 external input `EXT-HTTP-TEST-SERVICE`：描述改受管路径
  `Tools/ota/p3-3-service/` + 本文 §1 四件套 SHA-256（v2 值）+ **Quick
  Tunnel 路线（§5.1）**；隧道地址按合同「执行时回填」规则绑定（§6 D1/D2
  留证 + `quicktunnel-hostcheck.log`），不预先写死随机 URL。runner 依赖经
  Validation profile 冻结（`Tools/provenance/manifest_profiles.json`
  required_paths 含四件套 + `Tools/jlink/p1-6-common.ps1` +
  `Tools/jlink/test-p1-6-recovery-cmd.ps1`），**description 内哈希仅为
  辅助说明，不替代 profile 冻结依赖**；外部 fixture（`.cache/p3-3-assets/`
  两份 ETU + 恢复 Boot 产物）身份仍按 EXT 条目单独绑定。见合同修订。
- 操作单 O2「服务端请求日志」来源：本文 §6 D3 的 service.log。
- 受验 APK 构建命令中的 `firmware_latest_url` 值 = §5.1 隧道地址的
  `https://<随机>.trycloudflare.com/api/public/firmware/latest`（§5.2 宿主
  检查通过后才注入，唯一一次 build-only 配额）。
- 云端写入单 B0-B4 暂停标注维持（Quick Tunnel 不触发其 §9 CF 账号规约：
  不使用账号、不读 token，见云端写入单 §9 注记）。
