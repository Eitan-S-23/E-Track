# P3-3 受控 v2 测试服务：方案、实现与宿主自测 —— 2026-09-13（第四轮修订，源码 v2）

> 依据用户 2026-09-13 第三轮裁定第 1 条确立受控 v2 测试服务路线（原边界
> 声明继续有效：不证明 P4-2 通过、不实现正式发布链、不放宽 App 校验、
> 不直接注入 OtaService 状态）。
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
>   A/B 待批输入清单化；D5 重定义为完整清理与无残留验证。

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

## 5. 真机 HTTPS 方案（硬前置；宿主已实证，路线待批）

**HTTPS 是当前受验 App 的硬前置**：App 端
`ota_firmware_latest.dart` 硬性要求 downloadUrl https；Android 13
（targetSdk≥28）禁止明文 latest；App 无 `badCertificateCallback`/
`SecurityContext`（**不得放宽**）；`dart:io` HttpClient 在 Android 只信任
系统 CA。**adb reverse 只转发端口，不提供 TLS，也不解决证书信任**——
手机侧必须看到公共可信证书链。

宿主侧已实证（§4.2）：服务的 TLS 实现（`--tls-cert`/`--tls-key`/
`--public-base-url`、minimum TLSv1_2）与证书链配置可工作。**剩余待办全部
在域名与公共可信证书侧**，按以下两条路线申报，由用户裁定：

### 路线 A（主推）：自有域名 + Let's Encrypt DNS-01 + 局域网直连

- 原理：用户自有域名一条 A/AAAA 记录指向 PC 局域网 IP（或测试期内
  网段），Let's Encrypt 通过 DNS-01（TXT 记录）签发公共可信证书（无需
  公网入站端口）；服务绑 `--host 0.0.0.0`（需另行授权），手机经局域网
  直连 `https://<域名>:<PORT>`；`--public-base-url` 与证书域名一致。
- 需用户提供/批准的输入：
  1. 域名（及其 DNS 提供商）；
  2. DNS-01 执行方式：手动 TXT（每次续期人工操作）或 ACME 客户端 +
     DNS API token（token 注入与存放位置须预检批准）；
  3. 证书有效期策略（Let's Encrypt 90 天，测试窗口内单次签发即可）；
  4. 局域网直连授权（服务绑非回环地址 + 手机访问 PC IP）。
- 优点：无第三方账号依赖、证书为标准公共 CA、URL 固定（可注入 APK
  构建参数）。

### 路线 B（备选）：Cloudflare Named Tunnel

- 原理：cloudflared 建立反向隧道，公网 `https://<子域>` 经 CF 边缘终止
  TLS（CF 证书公共可信）转发到本机服务；手机走公网回路，无需局域网
  直连授权。
- **须按第四轮裁定第 4 条流程申报后才可启动**：先说明具体目标账号、
  资源、域名和对外暴露范围；获批后**先发起浏览器鉴权请求刷新本地登录**，
  鉴权后核对实际 account ID 与目标资源归属，排除旧环境 token 覆盖新
  OAuth 登录；不得沿用未经核验的缓存身份，不得全局删除其他账号凭据，
  不输出 token/cookie。PowerShell/cloudflared 的启动缓存、日志和认证
  文件仍须做写入预检；浏览器鉴权不豁免项目外写入边界。
- 优点：无需 DNS-01 与局域网授权；缺点：引入 CF 账号依赖与写入面。

### 已排除路线（论证）

| 路线 | 排除原因 |
| --- | --- |
| Quick Tunnel（`cloudflared tunnel --url`） | URL 随机（`*.trycloudflare.com` 每次变化），与 APK 构建时注入的 `firmware_latest_url` 固定值冲突；不可绑定 |
| mkcert / 自签 / 用户 CA | 非公共可信；Android 系统信任库外（用户 CA 对 `dart:io` HttpClient 无效）→ 等效放宽校验，禁止 |
| 回环域名服务（localhost.direct / localcert.me 等） | 现状（域名、签发流程、有效期）无法在本环境在线验证（网页抓取被网络策略拦截）；依赖第三方可用性与续期；如用户已验证可用可作为路线 A 的替代申报 |
| adb reverse + HTTP | 仅端口转发，无 TLS、不解决证书信任；App 明文禁止（仅宿主自测形态） |

**真机执行绑定要求（O2 前置检查）**：域名、端口、证书链、notBefore/
notAfter、证书文件路径、完整启动命令行（D1 形态）全部落盘留证；证书
剩余有效期须覆盖整个 O 序列窗口。

## 6. 部署申请（待批，未执行；D1-D5 按第四轮裁定第 3 条重定义）

执行 O2 时的服务启动与清理序列（域名/证书按 §5 批准路线取值）：

| # | 操作 | 命令要点 | 留证 |
| --- | --- | --- | --- |
| D1 | 启动（toy 激活，TLS） | `python service.py --config service_config.json --active-release toy-30201 --host <按路线> --port <PORT> --public-base-url https://<域名>:<PORT> --tls-cert <cert.pem> --tls-key <key.pem> --log-file <repo>/.cache/p3-3-v2-service/service.log` | 启动日志（版本=2/fixture 身份/激活指针/TLS 绑定） |
| D2 | 端口转发（仅路线 A 局域网方案不需要；adb reverse 方案适用时） | **先 `adb -s 10ADA4197U001CK reverse --list` 检查现有映射；目标端口已有映射时不得直接覆盖**——停止并申报冲突，由用户裁定 | 检查回显 + 映射命令回显 |
| D3 | O2 观测期间 | 服务日志持续采集（每请求一行：脱敏路径/状态/字节数/req=） | 与 App logcat 的 requestId 交叉 |
| D4 | toy→真包切换（O3 PASS 后） | 停服务 → `--active-release real-30202` 重启（同 D1 参数） | 两段启动日志 + 停启时间戳 |
| D5 | **完整清理（含验证）** | ① `adb reverse --remove tcp:<PORT>`（本次建立的映射）→ ② 终止本次服务进程（记录 PID/退出码）→ ③ 日志归档到项目内 `.cache/`（含 service.log、启动命令行、证书身份）→ ④ **无残留验证**：`adb reverse --list` 不含本次映射、`Get-Process` 无本次服务进程（按 PID 核对，不按名字误杀）、`.cache` 内日志文件齐且有 SHA | 四步各自回显 |

- 授权口径：D1-D5 合并为一次部署会话申报；暴露范围按 §5 批准路线
  （路线 A = 局域网直连；路线 B = CF 隧道公网回路）。
- **D5 的清理是判据不是善后**：残留（映射/进程/日志缺失）记
  HARNESS_FAIL。
- 服务进程为长运行进程，执行方须在会话结束前确认无残留（同 J-Link
  logger 清残留纪律，按 PID 精确核对）。

## 7. 与合同/操作单的衔接

- 合同 external input `EXT-HTTP-TEST-SERVICE` 升 v2：描述改受管路径
  `Tools/ota/p3-3-service/` + 本文 §1 四件套 SHA-256（v2 值）；runner
  依赖经 Validation profile 冻结（`Tools/provenance/manifest_profiles.json`
  required_paths 含四件套 + `Tools/jlink/p1-6-common.ps1` +
  `Tools/jlink/test-p1-6-recovery-cmd.ps1`），**description 内哈希仅为
  辅助说明，不替代 profile 冻结依赖**；外部 fixture（`.cache/p3-3-assets/`
  两份 ETU + 恢复 Boot 产物）身份仍按 EXT 条目单独绑定。见合同修订。
- 操作单 O2「服务端请求日志」来源：本文 §6 D3 的 service.log。
- 受验 APK 构建命令中的 `firmware_latest_url` 值 = §5 批准路线的
  `https://<域名>:<PORT>/api/public/firmware/latest`。
- 云端写入单 B0-B4 暂停标注维持；若 §5 路线 B 获批，其账号/写入面申报
  并入云端写入单 CF 规约（见云端写入单修订）。
