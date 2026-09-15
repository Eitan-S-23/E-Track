# P3-3 v9 最终独立验收报告（2026-09-15）

## 1. 结论

独立判定：**PASS，五项全部通过**。机器最终校验结果在 §5 记录。

| 判据 | 结果 | 本轮方式 |
| --- | --- | --- |
| C-DEV-CHECKS | PASS | 直接复用 v8 R1 原始 EXECUTED PASS |
| C-RELEASE-BUILD | PASS | 直接复用 v8 R1 原始 EXECUTED PASS |
| C-APK-INSTALL | PASS | 本轮执行离线补证复核 |
| C-TOY-LOOP | PASS | 直接复用 v8 R1 的 30203→30204 闭环 |
| C-REAL-LOOP | PASS | 直接复用 v8 R1 的 30204→30205 闭环 |

验收人：Codex 独立非实现会话。实现 agent 不需要再整改、构建或补测。
此结论不是宣布 Git 收口完成；本会话未 commit/push/merge、未登记 bundle_commit，
未覆盖实现认领或修改看板。后续 Git 收口由主 agent 经用户授权办理。

## 2. 最后一项的关闭依据

用户已明确确认：“旧包是我卸载的，接下来应该怎么做？”
原始日志中 11:35:31 旧 `.p33acceptance` 被卸载的事实保持不变；
卸载来源为用户自主操作，不是产品缺陷或 agent 越权，也不因此给 agent 追加卸载权限。

这条确认仅补 E01 的操作来源。新受验包的安装与身份不是靠人证证明：
v8 R1 已独立执行 dumpsys、pull、双侧签名及生产包核对，
本轮又实际读取这些原始记录，并重新计算 APK 哈希、验证 pull 原件签名。

- 新受验包：`com.wen.gaia.gaia.p33verify`，86 / 1.0.60；
  已绑定安装观测的 lastUpdateTime=2026-09-15 11:36:08。
- 受验件与独立 pull 件均为 46,699,140B，SHA-256：
  `85ce64dfe7952e3de215a8bf38af5a0766122b6da2bc6aa002bca92f7b6223e9`。
- 本轮 apksigner 验证通过，证书 SHA-256：
  `6f51a6a64e21b50b0d7cace2fdf0ca4b978fbdff1814d7bbab90fad08832e658`。
- 原独立生产包观测为 86 / 1.0.60，lastUpdateTime 仍为
  2026-07-10 19:05:06，与历史锚点一致。

本结论针对已绑定的安装执行与产物，不声称此刻手机连接或在装状态的新快照。
原始输出、用户确认与本轮命令记录在 v9 包内
`evidence/commands/`、`evidence/old-package-removal-context.json`
及 `evidence/adjudication/`，均由矩阵 SHA-256 绑定。

## 3. 为什么是 v9

v8 R2 曾准备重新执行六条手机只读命令，NOT_RUN 前检通过，但 USB 设备预检为空，
所以没有执行任何判据命令。该准备记录原样保留，仍为 NOT_RUN；
没有伪装新手机实测，也没有产生新的产品终态来替代 v8 R1。

原始安装取证并未缺失或污染，不应因为补一项用户来源确认而要求重采。
因此根据执行合同 §7.1 的证据阶段规则，把最后一项改为离线复核：
冻结命令发生真实变化，所以合同升为 v9；五项标准、源码、APK、固件和服务身份不变，
不原地改写 v8，也不删除 v8 R1 的 EVIDENCE_GAP 历史。

用户已授权继续完成正式验收；非实现验收会话仅审批该范围内的离线取证入口，
没有扩大设备、CI、部署、提交或发布权限。原始确认文件单独保留，不伪造额外用户原话。

## 4. 冻结与最小复核

- 合同：`docs/acceptance-contracts/P3-3-v9.contract.json`，FROZEN。
- 合同 SHA-256：
  `8B0FD07A8E01070D2EDA5745EA73EC0E6759911C45796C3289DADCE54A44950F`。
- 冻结提交：`ceaf8d2b7bb8e78968462af51a57ff1250731b61`。
- 冻结 tree：`4fd600a48a25654fe82db3cb6fd6f6338392bc48`。
- profile blob：`3769369d053aad028b67d7e2c17b5827b2b96f55`。
- 当前轮次：`P3-3-V9-ACCEPTANCE-20260915-R2`。
- 实际上一终态：`P3-3-V8-ACCEPTANCE-20260915-R1`。
- 上一矩阵 SHA-256：
  `634A57B09AB94CEE46F013CCB888884040DC95C23F2A42435B2B3641E35F409F`。

自动计划：1 项复核、4 项可复用；`changed_input_groups=[]`。
四项 REUSED 直接绑定 v8 R1 的原始 EXECUTED PASS，不跳过失败、不把中间复用冒充实测。
C-APK-INSTALL 本轮执行 3 条计划内离线命令，全部退出 0：
原样读取原始记录与用户确认、重新验证原件签名、重新计算两个 APK 哈希。

本轮无新 CI、构建、OTA、J-Link、烧录、安装、卸载、手机数据清理或服务部署。
BLE 提速、后台/锁屏及通知继续按用户裁定排除；P4-2 不因本卡通过而自动通过。
原构建警告和 v8 已记录的非阻断勘误不隐去，详细原始证据沿用 v8 R1。

## 5. 校验与交接

执行前 FROZEN + NOT_RUN：**VALIDATION=PASS**。
自动计划：**rerun=1，reusable=4**。
最终校验：**VALIDATION=PASS**，原始输出为：

    VALIDATION=PASS contract=P3-3-v9 round=P3-3-V9-ACCEPTANCE-20260915-R2 overall=PASS

原始输出保存于 `docs/acceptance-contracts/P3-3-v9/evidence/adjudication/final-validation.log`。
本结论已同时满足五项判据和合同/矩阵实物校验，不再只是“条件已满足但未落盘”。

复校命令：

    python -X utf8 -B -S Tools/acceptance/validate_bundle.py --contract docs/acceptance-contracts/P3-3-v9.contract.json --matrix docs/acceptance-contracts/P3-3-v9/P3-3-v9.evidence-matrix.json --repo-root . --previous-contract docs/acceptance-contracts/P3-3-v8.contract.json --previous-matrix docs/acceptance-contracts/P3-3-v8/P3-3-v8.evidence-matrix.json

交给主 agent 的当前入口是本 v9 报告及矩阵，不是仍保留 EVIDENCE_GAP 的历史 v8 R1。
Git 收口需先提交当前冻结包及其历史依赖，再以独立提交登记冻结索引；
PR 使用保留原提交 ID 的 merge commit 或受控 fast-forward，禁止 squash/rebase-merge。
未完成主工作树同步和必要归档前，不宣称整卡已收口；不得擅删唯一原始日志或 worktree。

## 6. 写入与运行边界

所有本轮主动输出位于指定 admission worktree 的
`docs/acceptance-contracts/P3-3-v8/evidence/r2/`、
`docs/acceptance-contracts/P3-3-v9/`、`docs/ota-exec-notes/` 及项目内 `.cache/`。
没有写入主工作树、系统临时目录或修改原冻结合同。
本轮设备预检启动的 ADB server 已清理，未触碰手机数据。

后半程已改用可读原生命令，不再用 Base64 包装。
一次路径检查中 cmd 把 JavaScript 箭头解析为重定向，在项目根生成了 0 字节 `[p`；
已核对其路径与大小并删除本轮误生成文件，不影响产品文件或验收观测。
该失败检查没有用作通过证据。
