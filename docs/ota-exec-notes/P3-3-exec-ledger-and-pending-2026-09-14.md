# P3-3 执行台账与待决事项 —— 2026-09-14 03:3x

> 性质：集中交付材料（#47 的一部分）。汇总本轮（2026-09-13 起）全部
> 额度消耗、作废轮、有效资产与待用户决策事项，供审阅与追认。
> 事实来源：`P3-3-speedometer-real-ble-fix-2026-09-14.md`（主执行笔记）、
> `P3-3-acceptance-apk-build-2026-09-13.md`、`P3-3-recovery-execution-2026-09-13.md`、
> 服务日志与 tunnel.log 原始记录。

## 1. 当前状态快照（2026-09-14 03:3x 本地）

| 项 | 状态 |
| --- | --- |
| 实现分支 | `dev/flutter/apk/p3-3-admission`，HEAD `bed3aa0`（5 项 UI 整改全链完成，用户实测全部确认） |
| CI | flutter-dev-checks run 34774089038 双宿主全绿（analyze+tests） |
| v4 冻结包 | 已定稿并登记（bundle `a548d43`，DRAFT→FROZEN 全链 2026-09-14 03:0x；执行门禁 PASS）——**但 EXT-HTTP/C-RELEASE-BUILD 绑定的 r3 隧道与第四轮 APK 已失效（见 §3），待升 v5** |
| r3 Quick Tunnel | **已死**（03:09-03:12，蜂窝链路瞬断杀进程；域名随进程永久失效） |
| 受控服务 | python 进程同死；代码/fixture 未损（`Tools/ota/p3-3-service/` 四件套哈希不变） |
| 板卡 | BCB 恢复一致态（CONFIRMED vcode=30200）维持；恢复执行（20260913-r1）以来未进行任何 J-Link/OTA 操作 |
| 手机 | 第四轮受验 App（p33acceptance，d241f7ca…）在装；**endpoint 已失效，App 检查更新不可用** |
| O 序列 | O1-O5 均未执行；待服务路线决策 + 新 APK + 合同 v5 |

## 2. APK 构建额度账（build.yml dispatch，逐笔授权链）

| # | Run | APK SHA-256（前 8 位） | 授权依据 | 消耗与状态 |
| --- | --- | --- | --- | --- |
| 1 | 34757419111 | c1c89084 | P3-3-EXEC-AUTH-20260913 第四节唯一 1 次 build-only 额度 | 已消耗；v3 轮 APK，随码表演示稿发现作废 |
| 2 | 34768946670 | 56301807 | 用户 2026-09-14 飞书指令「授权」（第二轮整改受验 APK） | 已消耗；整改中间轮，随下一轮替换装机作废 |
| 3 | 34772842511 | b9c0bdd5 | 用户 2026-09-14 飞书指令「授权」（第三轮受验 APK） | 已消耗；第 5 项整改后随第四轮替换作废 |
| 4 | 34774834925 | d241f7ca | 用户 2026-09-14 飞书指令「授权」（第四轮受验 APK） | 已消耗；用户实测 5 项整改全部确认，**但 r3 隧道死亡导致注入 endpoint 失效，App 服务侧功能不可用** |
| 5 | （待定） | — | 待路线决策后向用户申请 | 计划绑定 v5 合同与新 endpoint |

累计已消耗 4 笔（1 笔授权单额度 + 3 笔用户逐轮飞书授权）。

## 3. 作废轮总账（如实登记，均保留原始证据）

| 作废项 | 作废原因 | 证据位置 |
| --- | --- | --- |
| v3 冻结包（bundle `421bd290`，freeze `a178ecc`） | 用户实测发现受验 App 码表「设备」页为三台写死假设备演示稿，决策「现在立刻修，验收重来」；freeze_commit 后 profile 内出现新提交，执行门禁必红 | 主执行笔记 §4；FREEZE-INDEX 备注行 |
| APK c1c89084（run 34757419111） | 同上（源码演进） | §4 |
| APK 56301807（run 34768946670） | 整改中间轮，第 5 项整改后源码再变 | §7/§10 |
| APK b9c0bdd5（run 34772842511） | 同上 | §10 |
| **APK d241f7ca（run 34774834925）** | **r3 隧道死亡 → 注入 endpoint 永久失效**（App 本体与 5 项整改无缺陷，纯服务侧失联） | §12 |
| r1 隧道 feed-recipients-copper-ellis | 8h 窗口自然到期路径上死亡（2026-09-13 20:26Z） | http-test-service evidence |
| r2 隧道 ideas-coastal-province-enrollment | D2 检查后无声死亡（2026-09-14 00:33 后） | tunnel-r2-20260914.log |
| **r3 隧道 started-monitors-shower-cherry** | 蜂窝链路瞬断（UDP 不可达）→ QUIC 断链 → 进程死亡（2026-09-14 03:12 本地；存活约 1.4h） | tunnel.log；主执行笔记 §12 |
| v3 轮 O1/O2 证据（20260913-r1/） | 用户决策中止本轮（O1 已完成、O2 进行中停止），留作作废轮证据不参与判定 | §4 |

## 4. v4 冻结包处置说明

v4 合同（`P3-3-v4.contract.json`，bundle `a548d43`，FREEZE-INDEX 已登记）在
定稿约 40 分钟后因 r3 隧道死亡而失去事实基础：

- EXT-HTTP-TEST-SERVICE fingerprint 绑定 r3 隧道地址与 cloudflared/python
  PID（均已死亡）；
- C-RELEASE-BUILD / C-APK-INSTALL 绑定第四轮 APK 及其 endpoint 注入事实
  （endpoint 已永久失效）。

按治理规约：合同内容变化必须保持同一 `task_id`、版本加一（v5）并用
`parent_contract_sha256` 绑定 v4；v4 包字节不动、FREEZE-INDEX 行按「只增
不改」保留（其复校语义仍可在 bundle_commit 上自校，但判定已由 v5 取代，
处置方式与 v3→v4 相同）。

## 5. REC 超授权待追认（1 项）

恢复执行（20260913-r1）中 REC 命令会话实际执行 11 个，授权口径为 10 个
（超 1 个），已如实登记于 `P3-3-recovery-execution-2026-09-13.md`。该偏差
发生在恢复流程收尾确认阶段（多执行一次只读性质确认命令），未影响板卡
最终一致态。**待用户追认**。

## 6. 当前有效资产（未受隧道死亡影响）

| 项 | 身份 |
| --- | --- |
| 板卡 | BCB CONFIRMED vcode=30200 一致态（恢复判据四条满足）；板上 App 3.2.0(30200) |
| toy fixture | `e-track-at32f435-v3.2.1-full.etu`，284,092B，SHA-256 `fc4ae5a9…`；终点基准 raw SHA `43ee943a…` + vcode 30201 |
| 真包 fixture | `e-track-at32f435-v3.2.2-full.etu`，284,112B，SHA-256 `0a2eb26a…`；终点基准 raw SHA `c9582213…` + vcode 30202 |
| 受控服务代码 | `Tools/ota/p3-3-service/` 四件套（v2，哈希见合同 EXT-HTTP；16 项宿主自测 + D2 14/14 记录有效） |
| 源码实现 | `bed3aa0` 整改链（3b5dd4b→9e619a6→4156cf2→bed3aa0）；CI run 34774089038 双宿主绿 |
| 真机链路佐证 | 2026-09-14 02:16/02:45 两条真机 latest 200 请求（含连接板卡后真实 currentImageSha），证明 App→公网→服务链路在隧道存活期完整工作（主执行笔记 §12） |
| 已装侧版本佐证 | 装机时 dumpsys versionCode=86/versionName=1.0.60 实测；已装侧证书指纹实测（dumpsys→pull→apksigner）**未完成**（USB 断连），待补 |

## 7. 待用户决策：服务路线（二选一）

两案均需：合同 v5 冻结 + 第五轮 APK 构建授权 + 重新装机。差别只在地址
稳定性：

- **A. Tailscale**（推荐）：`https://<机器名>.<tailnet>.ts.net` 固定域名 +
  Let's Encrypt 证书（系统默认信任，无需放宽 App 校验）；进程/网络中断
  自动重连且**域名不变**。代价：电脑与手机各装 Tailscale 客户端并登录
  同一免费账号（手机显示 VPN 图标）；合同 EXT-HTTP 暴露面描述更新
  （原「无 CF 账号」变「Tailscale 账号」）。
- **B. Quick Tunnel 第四条**：零新安装。按 r1-r3 实测寿命约 3min-2.6h，
  需将「隧道→宿主检查→APK 构建（约 9 分钟）→装机→O1-O5 全程」压入
  窗口；蜂窝再抖动一次即再烧一轮构建授权。

决策后执行链（两案相同）：路线部署 → D2 宿主端到端检查 → 用户授权第五轮
APK 构建 → 装机与身份实测 → 合同 v5 冻结（parent 绑 v4）→ O1-O5 →
D5 清理 → 集中交付。

## 8. 会话累计写入边界事件（沿用登记）

主仓 `.cache/p3-3-apk-r3/` 空目录壳（第三轮 gh run download cwd 漂移
越界后回收，句柄未释放暂无法删除）——唯一项目外残留，内容为空无损失，
待句柄释放后清理。
