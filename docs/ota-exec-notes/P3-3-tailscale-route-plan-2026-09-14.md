# P3-3 服务路线 A（Tailscale）执行预案 —— 2026-09-14 03:4x

> 性质：预研文档。用户决策选 A 后按本预案执行；选 B（重赌 Quick Tunnel）
> 则弃用本预案。不改变任何已冻结事实；合同升 v5 时本预案作为编制输入。
> 前置事实：r3 隧道死亡登记与路线二选一说明见
> `P3-3-exec-ledger-and-pending-2026-09-14.md` §7。

## 1. 路线骨架

| 组件 | 角色 | 说明 |
| --- | --- | --- |
| 电脑 tailscaled | tailnet 节点 + HTTPS 终端 | `tailscale serve` 监听 443，自动申请并续期 `机器名.<tailnet>.ts.net` 的 Let's Encrypt 证书（系统默认信任库信任，**App 校验不放宽**） |
| 受控 v2 服务 | 不变 | 仍以 HTTP 监听 `127.0.0.1:8443`（与 Quick Tunnel 轮完全相同的代码与启动参数形态） |
| 手机 Tailscale App | tailnet 节点 | 手机加入同一 tailnet 后经 MagicDNS 解析 `机器名.ts.net` |
| 替换关系 | `tailscale serve` 取代 cloudflared | 同为「TLS 终止 → 转发 127.0.0.1:8443」形态，服务代码零改动 |

地址形态（与 Quick Tunnel 轮的关键差异）：**域名固定**。
`https://<机器名>.<tailnet>.ts.net/api/public/firmware/latest`（无端口后缀，
tailscale serve 监听 443）。tailscaled 重启、网络抖动、进程死亡均不改变
域名——结构性根治 r1-r3 的「进程死亡=域名失效=APK 报废」循环。

网络路径：手机与电脑同在手机热点 L2 网段，Tailscale 大概率建立 LAN 直连
P2P（不耗蜂窝流量）；若走 DERP 中继，流量也仅元数据级。App→服务链路与
BLE 连接板卡互不冲突（VPN 与 BLE 并存正常；手机热点共享流量不经 VPN，
电脑上网不受影响）。

## 2. 部署步骤（决策后执行序）

用户侧（约 10 分钟，一次性）：

1. 电脑安装 Tailscale（winget 或官网安装包），浏览器登录（Google/GitHub/
   微软账号一键，免费 plan：3 用户 100 设备，够用）。
2. 手机安装 Tailscale App（应用商店），登录**同一账号**，开关保持开启。
3. 把管理台里显示的 `机器名.<tailnet>.ts.net`（电脑那台）告诉 agent。
   注：tailnet 的 MagicDNS 与 HTTPS 证书功能默认开启（HTTPS 需在
   admin console → DNS → HTTPS Certificates 确认启用；个别新 tailnet
   需手动开，一步开关）。

agent 侧（用户给出机器名后，约 5 分钟）：

4. `tailscale serve` 配置 443→127.0.0.1:8443 转发并后台化
   （语法随版本：`tailscale serve --bg http://127.0.0.1:8443` 或等价；
   执行时以 `tailscale serve --help` 实测为准）。
5. 启动受控 v2 服务（与 r3 轮同命令形态，仅换 `--public-base-url`：
   `python service.py --public-base-url https://<机器名>.<tailnet>.ts.net
   --active-release toy-30201 ...`，启动双 fixture 核验）。
6. D2 宿主端到端检查：`python d2_hostcheck.py https://<机器名>.<tailnet>.ts.net`
   ——脚本零改动（BASE 参数化），期望 14/14 ALL PASS（含证书链默认信任库
   校验项，LE 证书应通过）。
7. 向用户申请第五轮 APK 构建授权 → build.yml dispatch
   `-f firmware_latest_url=https://<机器名>.<tailnet>.ts.net/api/public/firmware/latest
   -f release_application_id_suffix=.p33acceptance`（其余不变）。
8. 装机与身份五元组实测（同前四轮流程）。
9. 合同 v5 冻结（parent 绑 v4，task_id 不变），O1-O5 执行。

## 3. 合同 v5 变更点清单（相对 v4）

- `version` 5、`parent_contract_sha256` = v4 定稿哈希（4AABC513…）。
- EXT-HTTP-TEST-SERVICE `fingerprint` 重写：部署形态 Quick Tunnel→
  Tailscale（ts.net 域名 + LE 证书 + tailscale serve 转发）；r1-r3 三条
  隧道死亡史保留登记；D2 日志绑定新轮。
- 暴露面描述更新：「无 CF 账号」→「Tailscale 免费账号；tailnet 仅含
  电脑与测试手机两台设备；服务暴露面仍仅 latest/download 端点与两份
  绑定 ETU」。
- CMD-RELEASE-BUILD / C-RELEASE-BUILD / C-APK-INSTALL：绑定第五轮 run
  与新 APK 实测值（构建后回填）。
- CMD-DEV-CHECKS：代码零改动，run 34774089038 证据继续有效（freeze_commit
  仍为 bed3aa0，v5 不新增源码提交）。
- draft_note：登记 r3 死亡→路线决策→v5 修订链。

## 4. 风险与开放问题

| 项 | 评估 |
| --- | --- |
| ts.net 证书信任 | LE 链默认信任库信任；D2 第 3 项实测兜底，失败即停（不放宽 App 校验） |
| tailscale serve 语法版本差 | 执行时 `--help` 实测；不影响路线成立性 |
| 手机 VPN 与 BLE 共存 | Android 上 VPN 与蓝牙互不冲突；App BLE 扫描/连接不受影响 |
| 手机重启后 VPN 丢失 | Tailscale App 可设 Always-on；若丢失，App 检查更新失败→重新打开即恢复（域名不变，无级联损失） |
| tailnet 安全暴露面 | 仅两设备；服务无注册端点；admin console 可随时移除设备。不放宽 App 校验、无静态直链，协议不变 |
| 蜂窝抖动 | 域名不变，tailscaled 自动重连；APK 不因网络事件报废 |

## 5. D5 清理（Tailscale 模式）

1. 按记录的服务 PID 终止受控服务。
2. `tailscale serve --off`（或等价命令）移除 443 转发配置。
3. （可选，征询用户）手机/电脑 Tailscale 登出或从管理台移除设备。
4. 日志归档与无残留验证（同前口径）。
