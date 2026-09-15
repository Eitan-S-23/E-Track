# BLE 提速与 Android 后台 OTA 需求落盘

## 用户要求与范围

2026-09-15，用户反馈 BLE OTA 传输慢、不能切后台，并希望从状态栏查看进度；
在收到“P3-4 测量提速，后台 OTA 与通知单独立卡”的说明后，要求“那么请你写入项目规范”。
本批只处理规范、任务边界和治理回归，不实现产品，不修改既有冻结验收资产。

核对基线：main / `8b3190ee4c2b3a9ccec68dc3d5b104825165dcb0`，tracked clean。
P3-3 已完成 Git 收口且 v9 五项 PASS；P3-4 待办。新增 P3-8 承接 Android 后台 OTA。
两卡不得回写为已实现，也不改变 P3-3 原实现认领、PASS 或历史失败记录。

## 只读观察

- `bluetooth_service.dart::writeOtaCharacteristicByAddress` 在移动端每次写入前调用
  `discoverServices()`；`ota_service.dart::writeChunk` 对每个分片走该入口。
  这是待测热点，不是已证实的唯一瓶颈，也不能据此承诺提速倍数。
- `HAL_Bluetooth.cpp::BT_Init` 当前 UART 配置为 115200。
- `ota_upgrade_page.dart::didChangeAppLifecycleState` 在 paused/inactive 时主动
  `pauseForBackground()`；transport 同时暂停发送和无进展计时。
- `UpdateForegroundService.kt` 是 App 自更新的 dataSync 服务，不是设备 OTA
  的执行所有者；普通通知或启动服务调用返回成功不足以证明 BLE 后台任务已被接管。

## 本批决定

`OTA-DEC-014` 记录用户需求及本会话的规范细化，权威行为落在跨系统合同：

- P3-4 增加链路分段计时和有证据支持的最小热点优化，再进行 AT 逐档实验。
  既有 `OTA-XC-BLE-TUNING` 门槛和统计定义不变，不把不同源码/参数组的最好结果拼接。
- P3-8 新增 Android 前台服务接管、后台/锁屏继续运行、通知栏阶段进度和安全回退。
  正常切后台不应停发；接管未完成、丢失或平台不支持时仍安全暂停/恢复。
  强制停止不保证持续运行，重新打开后只按已核验包身份和 MCU durable 事实恢复。
- 状态栏图标与下拉通知栏进度为平台支持目标，不承诺所有系统都在顶栏常驻百分比。
  发送完成、END ACK 和进度 100% 都不能替代重启后 GET_INFO 的目标版本/raw SHA 校验。

P3-8 只依赖已完成的 P3-3；不新增 P3-4 -> P3-8 或 P3-8 -> P3-5 硬依赖。
同改 Flutter transport 时仍须串行协调共享文件。P3-5 的既有依赖和十次断连门槛不变。
P3 总表随新卡按实际卡面更新为 5/8，不重开已完成卡。

## 验证计划与边界

修改根/App AGENTS、共享合同、决定登记、P3-4/P3-8 Spec、看板及既有治理测试。
补充条款、路由、权限及进度语义的机械回归；运行受影响治理测试并交独立代码复核。
治理 CI 等明确推送授权后执行，不用本地宿主回归冒充 CI 或产品实测。

当前产品实现、Flutter analyze/test、APK/EXE、吞吐和后台/锁屏真机验证均为本批 NOT_RUN。
未新增正式验收轮次、矩阵或执行配额。既有 Flutter 开发预授权不扩展为 AT 改速、
安装/卸载、OTA、J-Link、烧录、部署、提交主线或其他真机/远端操作授权。

## 写入审计

活动根仅 `D:\github\my\E-Track`。全部目标在写前检查了规范化路径及完整父链，
无 reparse point；辅助脚本、原文件行尾快照和测试输出位于项目内
`.cache/ota-background-policy-20260915/`，TEMP/TMP/TMPDIR 同样收敛至此。
未运行历史临时脚本；保留 375 份既有未跟踪文件，不暂存、不提交、不推送。
`PLAN-OTA.md`、二进制合同、profile、验收校验器、FREEZE-INDEX、v9 合同/矩阵保留原字节。
混合 EOL 采用只恢复行尾的格式化步骤保留，不改变未修改行的字节。

## 实际验证

所有命令均使用 `cmd.exe`，显式工作目录为活动根。宿主回归经本会话专用
`.cache/ota-background-policy-20260915/policy_tools.py` 的 `test` 模式启动：
`-B -S` 禁用字节码与 site 启动代码，TEMP/TMP/TMPDIR 位于该缓存的 `tmp/`，
fixture Git 配置隔离在同一目录，不读取全局 hooks。该辅助脚本不是后续产品或验收入口。

| 实际测试子命令 | 结果 | 原始记录（均在上述缓存目录） |
|---|---|---|
| `python -X utf8 -B -S tests/ota/test_acceptance_bundle.py PostP26SpecGovernanceTests GovernancePromptScopeTests AcceptanceExecutionPolicyTests` | 首跑 37 项通过，exit 0，1.841s | `governance-01.stdout.log`、`governance-01.stderr.log`、`governance-01.json` |
| `python -X utf8 -B -S tests/ota/test_acceptance_bundle.py PostP26SpecGovernanceTests` | 独立复核修订后，只重跑相关 22 项，通过，exit 0，0.660s | `governance-02.stdout.log`、`governance-02.stderr.log`、`governance-02.json` |

JSON 记录实际 Python 可执行路径、命令、cwd、退出码与日志 SHA-256。unittest 的结果
位于 stderr，两次 SHA-256 分别为：

- 首跑：`dc1690d5ef53fa017a437561ef8d2caef60e4cc0c82bbf427594689133f10b2b`。
- 修订后：`c4eb8daadd6d1e24d349e9472076d48d58da2bd41d4f27d3b03e2cde54b02708`。

独立只读 agent `ota_policy_review` 完成集中审查并指出两项普通规范问题，本批均修正：

1. 初稿 `durable=512 / total=1024` 进度示例不符合真实 MCU 整 4KB 提交或包尾语义。
   改为 `4096/8192=50%`，治理测试不再只检查常量存在，而是解析示例，校验数值边界、
   二进制合同 §4.2.2/§5.5 的提交粒度与百分比；旧例会被拒绝。
2. 初稿把 P3-4 的生产参数正式回填降为“准备审查建议”。卡面与 Spec 均恢复独立复核、
   审批后回填所选 baud/timeout/retry，明确选择参数不等于放宽性能门槛，并补双向断言。

同时采纳非阻断维护建议：源码热点注明 2026-09-15 基线，测试守护长期测量原则，
不永久钉死尚待优化的实现事实。修订后的有界确认通过，两项发现关闭，未发现新问题。
此审查及宿主回归不是产品独立验收，不产生新的正式验收轮次。

`git --no-optional-locks diff --check` 为 exit 2，仅标出看板 43/652/653/654 行保留的
CRLF 行尾；未将其改成 LF 来制造通过。随后运行：

```cmd
git --no-optional-locks -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --check
```

结果 exit 0；该次命令保留普通空白检查并允许原 CRLF，不修改仓库配置。
原有 7 份被修改文件的 CRLF 数量均与本会话字节快照一致，其中看板为 729 行。
两份新 Markdown 使用 LF。

本会话 `policy_tools.py audit` 为 PASS：HEAD/index 未变，仅有预期 tracked 文档和
治理测试差异，7 份受保护文件及 375 份既有未跟踪文件 SHA-256 全部保持；所有受控
缓存、快照、日志和临时目录均在活动项目内。未发现主动项目外写入。
最终报告及看板的验证回写不改变产品/profile 输入，也不将仍待授权的远端治理 CI、
Flutter analyze/test/APK/EXE、真实吞吐或后台/锁屏观测改记为 PASS。
