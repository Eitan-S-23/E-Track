# P3-3 执行台账与待决事项 —— 2026-09-14（03:3x 建档，晚间三次更新）

> 性质：集中交付材料（#47 的一部分）。汇总本轮（2026-09-13 起）全部
> 额度消耗、作废轮、有效资产与待用户决策事项，供审阅与追认。
> 事实来源：`P3-3-speedometer-real-ble-fix-2026-09-14.md`（主执行笔记）、
> `P3-3-acceptance-apk-build-2026-09-13.md`、`P3-3-recovery-execution-2026-09-13.md`、
> `P3-3-recovery-execution-2026-09-14-r2.md`、服务日志与 tunnel.log 原始记录。

## 1. 当前状态快照（2026-09-14 晚 三次更新：v5 冻结完成）

| 项 | 状态 |
| --- | --- |
| 实现分支 | `dev/flutter/apk/p3-3-admission`，HEAD `1894f9d`（bed3aa0 五项 UI 整改 + O2 缺陷修复「Apply/Stage 提交 BCB STAGED 并复位」，修复版已重建+finalize+烧板+恢复）；其后 HEAD 链 `6415226`（O2 修复证据批次）→`475ece5`（v5 DRAFT：合同+四 EXT 证据+NOT_RUN 矩阵）→`b2fc1ce`（v5 FROZEN=bundle_commit）→本提交（FREEZE-INDEX v5 行登记+看板/台账回写） |
| CI | flutter-dev-checks run 34774089038 双宿主全绿（analyze+tests，bed3aa0 时点）；`1894f9d` 固件侧为本机 GCC 构建（`.cache/bg/app-gcc`），CI 重跑随 v5 轮 |
| v4 冻结包 | 已定稿并登记（bundle `a548d43`，DRAFT→FROZEN 全链 2026-09-14 03:0x；执行门禁 PASS）——**但 EXT-HTTP/C-RELEASE-BUILD 绑定的 r3 隧道与第四轮 APK 已失效（见 §3），且源镜像绑定旧 `7328c1b1…`（O2 缺陷版本），待升 v5**——**已升 v5 完成**（v5 bundle `b2fc1ce`，2026-09-14 晚三提交链定稿登记，validate_bundle 两轮 PASS；v4 包字节不动、仍可在其 bundle_commit `a548d43` 上复校，v5 经 parent_contract_sha256 `4AABC513…` 绑定取代其判定） |
| r3 Quick Tunnel | **已死**（03:09-03:12，蜂窝链路瞬断杀进程；域名随进程永久失效） |
| 受控服务 | **v5 实例存活**（20:21:05 起，PID 22316，`--active-release toy-30201`，供 v5 toy fixture `0219899d…`；启动双 fixture 逐字节核验 PASS，本机+公网 latest/下载字节级验证均过，见 P3-3-offline-assets-v5-rebuild-2026-09-14.md §7）。旧 r4 实例（17:01:54-20:21，供旧 toy `fc4ae5a9…`）已按 PID 精确核验后停止，其 O1/O2 请求日志完整保留 `service-r4-20260914.log` |
| 板卡 | **烧录事故已恢复**（2026-09-14 晚，恢复轮 20260914-r2 全 PASS）：生产 Boot（全区原样）+ 3.2.0-fixed App(30200) + BCB CONFIRMED/30200；App 启动序列完整，黑屏解除。事故与恢复全记录见主执行笔记 §16 |
| 手机 | **第五轮受验 App 在装**（p33acceptance，`2506e952…`，run 34781909023，r4 endpoint 注入；用户装机并确认升级页元数据与冻结基准全等）；r4 隧道与服务均存活，App 检查更新可用 |
| O 序列 | **v5 轮全部执行完成（2026-09-14 晚，用户实测配合）**：O1 重测 PASS（21:33 latest 30200→发现 3.2.1）；O2/O3 toy 闭环设备侧全链成功（传输 284,540B durable、WDT 复位、终点双值 30201+aeafc96e 设备自报、J-Link 读回仲裁+RTT CONFIRMED vcode=30201——`1894f9d` 修复实机验证成功，v4 轮 REBOOT_RECONNECT_FAILED 消除）；C-APK-INSTALL 补测 PASS（在装 APK 2506e952… 字节全等+证书 f5e838ef…）；D4 切换 real-30202 完成（隧道不动）；O4 真包闭环：设备侧成功（App 区=30202+ab0585f7 终点双值 22:32:20 latest 参数闭合、服务端 no_update 自洽）**但 App 复核环节超时缺陷**——60 秒重启复核窗口内设备 BLE 未恢复（复位后≥97s 仍 disconnected），UI 假阴性「等待设备重启校验失败」；toy 轮同模式（~67s），系统性时序问题，实现侧定性 PRODUCT_FAIL 候选、建议并入 #48 整改不重跑；附带登记：升级历史桩（return const []）、App 启动 snackbar Null check 异常；O5 双包名只读 PASS（生产包 lastUpdateTime 2026-07-10 全程未动）；D5 四步清理 PASS（隧道/服务按 PID 终止、归档 SHA、无残留）。全程留证 P3-3-o-sequence-execution-2026-09-14.md；单轮判定归独立验收会话 |

## 2. APK 构建额度账（build.yml dispatch，逐笔授权链）

| # | Run | APK SHA-256（前 8 位） | 授权依据 | 消耗与状态 |
| --- | --- | --- | --- | --- |
| 1 | 34757419111 | c1c89084 | P3-3-EXEC-AUTH-20260913 第四节唯一 1 次 build-only 额度 | 已消耗；v3 轮 APK，随码表演示稿发现作废 |
| 2 | 34768946670 | 56301807 | 用户 2026-09-14 飞书指令「授权」（第二轮整改受验 APK） | 已消耗；整改中间轮，随下一轮替换装机作废 |
| 3 | 34772842511 | b9c0bdd5 | 用户 2026-09-14 飞书指令「授权」（第三轮受验 APK） | 已消耗；第 5 项整改后随第四轮替换作废 |
| 4 | 34774834925 | d241f7ca | 用户 2026-09-14 飞书指令「授权」（第四轮受验 APK） | 已消耗；r3 endpoint 注入，随 r3 隧道死亡作废 |
| 5 | 34781909023 | 2506e952 | 用户 2026-09-14 飞书指令「授权」（04:4x，r4 轮第五轮受验 APK） | 已消耗；**当前在装**（r4 endpoint 注入，用户装机确认） |
| 6 | （待定） | — | 待 v5 轮按需申请 | 仅当 r4 隧道再死亡需换 endpoint 时 |

累计已消耗 5 笔（1 笔授权单额度 + 4 笔用户逐轮飞书授权）。

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

## 5. REC 超授权待追认（1 项）——已销账

恢复执行（20260913-r1）中 REC 命令会话实际执行 11 个，授权口径为 10 个
（超 1 个），已如实登记于 `P3-3-recovery-execution-2026-09-13.md`。该偏差
发生在恢复流程收尾确认阶段（多执行一次只读性质确认命令），未影响板卡
最终一致态。**用户已于 2026-09-14 晚追认**（「授权，此外你说的超授权
问题也一并授权」，同批批准恢复轮 r2 执行），本项销账，不再列为待决。

## 6. 当前有效资产（未受隧道死亡影响）

| 项 | 身份 |
| --- | --- |
| 板卡 | 生产 Boot（全区原样）+ **3.2.0-fixed App(30200)** + BCB CONFIRMED vcode=30200 一致态（恢复轮 20260914-r2 判据四条满足，留证 `P3-3-recovery-execution-2026-09-14-r2.md`） |
| 3.2.0-fixed 源镜像 | `.cache/p3-3-fix-flash/app-3.2.0-fixed-final.bin`，603,764B，SHA-256 `d7cc4194…a38e488`；头 image_sha256 `24fc02ea…728126`（S5 板上快照全等）；构建链 `.cache/bg/app-gcc/`（commit `1894f9d` 的 GCC 产物，仅差 0x400 头区） |
| toy fixture（**v5，当前生效**） | `e-track-at32f435-v3.2.1-full.etu`（`.cache/p3-3-assets-v5/`），284,540B，SHA-256 `0219899d…d55410c5`；终点基准 raw SHA `aeafc96e…085298` + vcode 30201；源=`1894f9d` 修复版 GCC 构建（O2 修复已含，与板上 3.2.0-fixed 本体逐字节同源）；离线验证 A-I 全 PASS（P3-3-offline-assets-v5-rebuild-2026-09-14.md） |
| 真包 fixture（**v5，当前生效**） | `e-track-at32f435-v3.2.2-full.etu`（`.cache/p3-3-assets-v5/`），284,573B，SHA-256 `0c8ae468…0590f6f`；终点基准 raw SHA `ab0585f7…46ab7e` + vcode 30202；与 toy 同源，仅版本身份字段差异（38 字节，0x408..0x45F） |
| v4 旧资产（保全不清理） | `.cache/p3-3-assets/` 8 文件原样保留（v4 冻结包证据完整性所需），四元组仍按原轮登记（toy `fc4ae5a9`/`43ee943a`、真包 `0a2eb26a`/`c9582213`），已不再被服务引用 |
| 受控服务代码 | `Tools/ota/p3-3-service/` 四件套（v2，哈希见合同 EXT-HTTP；16 项宿主自测 + D2 14/14 记录有效） |
| 源码实现 | `bed3aa0` 整改链（3b5dd4b→9e619a6→4156cf2→bed3aa0）；CI run 34774089038 双宿主绿 |
| 真机链路佐证 | 2026-09-14 02:16/02:45 两条真机 latest 200 请求（含连接板卡后真实 currentImageSha），证明 App→公网→服务链路在隧道存活期完整工作（主执行笔记 §12） |
| 已装侧版本佐证 | 装机时 dumpsys versionCode=86/versionName=1.0.60 实测；已装侧证书指纹实测（dumpsys→pull→apksigner）**未完成**（USB 断连），待补 |

## 7. 待用户决策：服务路线（二选一）——已决策并执行（B 路线）

2026-09-14 03:3x 建档时待决；用户随后选择 **B（Quick Tunnel 第四条）**，
r4 轮已于 04:2x-04:4x 执行完毕：r4 隧道起（域名
`describing-substance-databases-past.trycloudflare.com`）→ D2 14/14 →
第五轮 APK 构建装机 → O1 实测通过 → O2 实测暴露产品缺陷（已修复待重跑）。
**当前 r4 隧道（04:22:26 起）与脱离托管服务（17:01:54 起）均存活**，
无需再次路线决策；Tailscale 预案保留（`dcbd74b` 看板第七轮记录），
仅当 r4 再死亡时启用。

## 8. 会话累计写入边界事件（沿用登记）

1. 主仓 `.cache/p3-3-apk-r3/` 空目录壳（第三轮 gh run download cwd 漂移
   越界后回收，句柄未释放暂无法删除）——项目外残留之一，内容为空无损失，
   待句柄释放后清理。
2. **第二次 cwd 漂移越界（2026-09-14 04:4x，§13.4 已登记）**：第五轮 APK
   下载时新 turn 后 Bash cwd 重置回主仓，`gh run download` 落到主仓
   `D:\github\my\E-Track\.cache\p3-3-apk-r5\`；已 mv 回本 worktree（APK
   哈希复核一致），主仓空目录壳因句柄占用暂无法删除，待句柄释放后
   清理。防再犯：后续命令一律显式绝对路径/先 `cd` 至 worktree。
3. 烧录事故（2026-09-14 晚，主执行笔记 §16）：实现 agent 在授权的
   「重建固件」步骤烧录未 finalize 的裸构建镜像，触发 boot 设计内回滚
   （BCB=ROLLBACK→恢复等待死等→黑屏）。无持久损伤，经 finalize 重烧 +
   恢复轮 r2 全 PASS 恢复；责任在实现 agent 流程把关（GCC 产物烧板前
   必须 finalize 的教训已登记 AGENTS.md 之外的主执行笔记 §16.2）。
4. **第三次 cwd 漂移（2026-09-14 ~20:5x，纯只读零写入）**：v5 冻结取证
   段（取 CI 作业时序）新 turn 后 Bash cwd 再次重置回主仓，3 条只读命令
   在主仓执行（`gh run view 34844438554` + `ls docs/acceptance-contracts/`；
   `grep` FREEZE-INDEX + `git log`/`git show --stat a548d43`；`git log
   --follow` + `git status --short` + `grep`）。均为只读、零写入、无残留
   （主仓既有脏文件为会话开始前状态，未触碰）；本段后续写入前已发现并
   切回显式 `cd` worktree。防再犯措施不变：每 turn 写入动作前一律显式
   绝对路径/先 `cd` 至 worktree。
