# P3-3 v6 独立验收报告（2026-09-15）

## 1. 单轮结论

**总体：EVIDENCE_GAP，不能签发 PASS；不判 PRODUCT_FAIL。**

验收人：Codex 独立验收会话（P3-3-ACCEPT-20260915-V6），未参与 P3-3 实现。
轮次：`P3-3-V6-FREEZE-20260915-R1`。

执行前检查已通过，但冻结命令与执行规约、只读验收授权之间存在冲突；
真包外部输入也没有一致地绑定 v6 目标。依用户“发现合同与契约矛盾则停止”的要求，
本轮停止五条合同命令，只完成安全的本地证据复核、缺口汇总和证据封包。
没有重派 CI、调用手机、连接 J-Link、重刷固件、重跑 OTA 或拉起服务。

本报告不将“前检通过”“历史实现自测通过”或“用户实测成功”冒充完整独立 PASS。
同样，不因本轮未重跑 toy 就否定历史设备端成功证据。

## 2. 冻结身份与执行范围

| 项 | 独立核对值 |
| --- | --- |
| 工作树 | `D:\github\my\E-Track\.cache\worktrees\p3-3-admission` |
| 分支 | `dev/flutter/apk/p3-3-admission` |
| 执行 HEAD | `c3cc8ca640f5e91a2063bb136384a52b416e542f` |
| freeze_commit | `0fb167cf4c44a6e4741e5a42fcd4945cf29f7780` |
| freeze_tree | `b3d1d311645d584c48419b546a061c5648da740f` |
| profile_config_blob | `3769369d053aad028b67d7e2c17b5827b2b96f55` |
| 已登记 bundle_commit | `3f7ca7e124c8cc36cbf78fb0eeea9a14b3fe88dc`（准入包，不是本报告提交） |
| 合同 SHA-256 | `b445c209c20da0bc52473950c47d6e1807ef74c23377495f7cb48c6a2b70c171` |
| 起始矩阵 SHA-256 | `37a64a107dfe84a531909865b02c90ca25e3cccc26634bf575744459e62ef6b9` |

已读执行合同、AGENTS 独立验收 14 条及看板 §0/P3-3 记录。
Git 冻结对象、祖先关系及 profile 工作树门禁通过。
`ce301906736d7b4209a09ad7e42ce080fb7a19a6` 确为冻结提交直接父提交；
`git diff ce30190 0fb167c -- app/` 为空。完整提交差异只含看板、两份文档和
`Tools/ota/p3-3-service/service_config.json`，没有 workflow 或 App 构建输入改动。

v3/v4/v5 已查矩阵及索引均为 FROZEN+NOT_RUN 准入记录，没有独立
EXECUTED PASS 来源。本轮不声称 REUSED，按交接命令未传 `--previous-*`；
不能把实现侧的“第十轮/第十一轮”自动当作已完成的独立验收轮次。
后继正式轮次必须携带本轮真实前驱，不能省略本轮 EVIDENCE_GAP。

## 3. 集中发现

### G01：五条冻结命令均无法如实登记为本轮获准执行的命令

影响：全部五项 required 判据。归类：验收定义/证据绑定缺口，不是产品行为失败。

依据：执行合同 §3 要求精确命令，§4 要求真实命令记录；
`Tools/acceptance/validate_bundle.py:999` 对矩阵命令与冻结字符串逐字比较。

- `P3-3-v6.contract.json:83` 的 CMD-DEV-CHECKS 是
  `gh workflow run` 加中文执行说明，而本轮应只读复核两个既有 run。
- `P3-3-v6.contract.json:100` 的 CMD-RELEASE-BUILD 包含新 dispatch、
  watch 和中文说明；既不是本轮获准的历史构建核验命令，也不能按该文本重新构建。
- `P3-3-v6.contract.json:116` 的 CMD-APK-INSTALL 仍为
  `<由验收会话绑定：...>`。
- `P3-3-v6.contract.json:129`、`:143` 的两条闭环命令仍为
  App/BLE/J-Link 操作占位符，而本轮禁止实机闭环及 J-Link。

不能把实际 `gh run view`、`dumpsys` 或日志读取的输出挂到另一个没有执行过的
冻结字符串上，也不能现场填完占位符后继续使用旧合同 SHA。
本轮矩阵因此保留空 commands，而不是伪造退出码 0。

同批应处理的归档定义：ART-DEV-LOGS 在合同 `:159` 写成
`evidence/dev-checks/` 目录式路径，而校验器 `:1382` 要求每个 artifact
是可读取、可哈希的文件。正式归档需统一为明确的文件型产物，不能把目录记录成文件。
这不要求重跑 CI。

### G02：真包与服务的外部输入身份仍混用 v5/v6

影响：C-REAL-LOOP；服务旧记录同时关联两轮，应按实际消费者明确区分。
归类：冻结输入身份冲突，不是 30203 固件损坏。

合同 `:66` 的 EXT-REAL-ETU.fingerprint 仍是：

- 目标 30202；
- raw SHA `ab0585f71b9a523863b582e8ed4cc47a279bf6e57c4a1038635593306746ab7e`；
- ETU SHA `0c8ae468948d8e85af0e8eaf3ec52e046f1b6a3cdba88f9bd8478790f0590f6f`；
- size 284573。

其 evidence_sha256 也确实绑定 v5 的 real-etu-asset.md。
同一合同的 C-REAL-LOOP、ART-REAL-ETU/目标镜像以及本轮要求则明确是
30203、raw `3a282768...`、ETU `a543f952...`、284608B。
不能同时满足“与 EXT-REAL-ETU 四元组全等”和 30203 终点。

EXT-HTTP-TEST-SERVICE 的 fingerprint/evidence 仍绑定 r4 域名、
v5 服务和第五轮 APK；v6 description 追加的事实却是 r5 域名及第六轮 APK。
不能靠在旧字段旁追加叙述，把旧 fingerprint/证据哈希自动转换为新身份。
toy 的 r4 历史服务本身不是错误，应保留其真实历史归属，而非一概作废。

EXT-BOARD-STATE 的 30200 恢复记录作为历史起点保留，本轮没有把它误判为
“板上必须仍是 30200”，也没有为了使其相等而回退当前设备。

### 已修复的纯封包缺口

v6 入场目录缺少四份 external 证据，但 v5 中存在与冻结 SHA 完全相同的原件。
本轮已逐字节复制到 v6 规定路径，原件未改，源/目标/size/SHA 见
`evidence/acceptance-20260915/copy-manifest.json`。

这些仍是 v5 历史证据，补齐文件只解决包内可读取性，**不解决 G02**。
没有修改合同、profile、校验器或历史冻结包。

## 4. 五判据判定

| 判据 | 本轮结果 | 实际完成与未覆盖 |
| --- | --- | --- |
| C-DEV-CHECKS | EVIDENCE_GAP | G01 阻断正式执行；冻结对象已核对。未请求 GitHub job/analyze/test 原始日志，不能独立确认两轮双宿主结论。 |
| C-RELEASE-BUILD | EVIDENCE_GAP | 本地 APK size/SHA 与交付值一致；提交父子关系及构建输入差异已核对。G01 阻断；GitHub run、Windows 完整运行包、aapt/签名未继续核验。 |
| C-APK-INSTALL | EVIDENCE_GAP | G01 阻断后没有调用手机。r6 dumpsys/pull/双侧 apksigner 尚未补做；不以第五轮签名结果替代第六轮。 |
| C-TOY-LOOP | EVIDENCE_GAP | toy 文件身份、历史新版本查询和 CONFIRMED RTT 有原始证据，App 改动范围论证有代码支持；但占位命令无法落账，所复核材料不足以直接填全六状态。未回退、未重跑。 |
| C-REAL-LOOP | EVIDENCE_GAP | 30203 文件身份与三次新身份查询确实一致；G01/G02 阻断，HTTP 终点不能直接代替完整 BLE 状态轨迹。没有新 OTA。 |

矩阵遵循执行合同 §4 的正式 schema：单判据使用 `NOT_OBSERVED`、
`failure_owner=null`、`observed=null`，notes 中记录上述 EVIDENCE_GAP。
这是未获得完整 gate 观测，不是把目标布尔值填成 false，也不是伪造状态链。
`execution=EXECUTED` 沿用本轮非 REUSED 记录形式，不能解读为已经执行占位合同命令。

### 4.1 已独立复算的产物

| 实物 | size/B | SHA-256 |
| --- | ---: | --- |
| r6 APK | 46699144 | `fb6a91e69a0ad30dc0b9c79a69c5e638d376898d6e313836191f2b40ebf80a13` |
| toy 3.2.1 ETU | 284540 | `0219899dd993f61f2c75eaec7002bc9c24e0fc629a60e87046e74266d55410c5` |
| toy 3.2.1 目标镜像 | 603764 | `aeafc96e77d372aea1e893a979f2368ba9176c4999a61090ceb2956cd4085298` |
| real 3.2.3 ETU | 284608 | `a543f952dcd1b0f57770669e253b29e9a93b7ffb94263bc7bdc3b1bdf4ef1915` |
| real 3.2.3 目标镜像 | 603764 | `3a2827683cbd2b557dd5d441927d1a490b3b28fe11f8d7a4b4b5c86a594144a3` |

原始实物仍在用户指定的项目内 .cache 目录，未改字节，也未重新制包。
这些哈希只证明本地文件身份，不等于手机在装身份或完整 OTA gate。

### 4.2 闭环材料与代码演进的具体裁定

toy 原始服务日志首次新身份为 **21:40:15.699**，随后是
21:40:23.420、21:40:28.439，均为 30201 和完整目标 raw SHA。
因此本报告不沿用实现叙述中的 21:40:02/11。历史 RTT 原文确有
`OTA: BCB already CONFIRMED vcode=30201`。

实际审查 `git diff 6415226 0fb167c -- app/`：
改动集中于版本名显示、Wrap 布局、180s 总复核窗口/20s 单次探测及对应测试，
支持“传输核心未改”的范围论证；但重启复核是实际行为改动，并非纯文案。
旧执行记录 §2 同时明确 toy 时段 App logcat 已滚动、未独立保留。
这些材料不能自动产生 `ota_package_verified`、durable 完成、
ACK_END 及新连接 GET_INFO 的全部原始状态观测。

r6 原始日志的 23:43 两条请求使用全零 currentImageSha，
不能据此声称该两条已经绑定了设备真实 raw 身份；带真实 30202/ab0585f7
起点的查询在 23:59:30、00:00:11。00:00:15 服务记录发送 284608B；
00:06:05.449、00:06:08.608、00:07:22.431 三次查询均为
30203 和完整 `3a282768...4144a3`，这一点与交付结论一致。
但 HTTP 请求身份字段、114B 响应长度及实现侧叙述，不能单独证明
BLE durable/ACK_END、自动复核窗口用时或请求来源的全部细节。
没有把服务端发送字节数冒充 App 端整包 SHA 校验通过。

用户“实测 OTA 没有问题”的反馈作为事实背景保留，不被否定；
本轮不足的是完整、可按冻结命令归属的证据，而非已经观察到当前产品失败。
上述未覆盖项应先定位和补交既有原始记录，不能直接推导出“整卡必须重刷”。

## 5. 最小后续范围

1. 在后继合同一次性修正 G01/G02 及开发日志产物路径：
   冻结真实的既有 CI/产物/手机只读取证命令、离线闭环审查入口与正确的 v6
   外部身份；不能原地修改 v6，也不能把本报告伪装成 v6 PASS。
2. 补全尚未完成的只读项目：指定 CI run 原始日志、Windows 完整运行包、
   r6 在装受验包 dumpsys/pull/双侧证书及生产包只读确认。
   已核对的本地文件与原始日志保留，不重复构建或制包。
3. 对 toy/real 六状态先补交已存在的 App/BLE 原始证据或可审计的直接推导链，
   保留 toy 代码演进论证。若确实无法补齐，才讨论最小补测。
   toy 若需补测，额外授权至少涉及合法低版本基线的回退/恢复方案
   （包括 App/BCB 一致性与明确次数）及一次 toy OTA/证据采集；
   J-Link 若需要仍单列，不能从本轮只读授权推导。**本报告不授权这些操作。**
4. 后继轮按实际前驱计算最小计划；不因合同/封包整改重开 BCB 恢复、
   全量构建、P4-2 或历史固件战役。计划本身不追加额度。

BLE 速度及前台/锁屏限制严格按用户裁定排除，不记为失败，也不成为补测前置。
本轮不验证 P4-2 通过，不操作 Cloudflare 账号或缓存凭据。

## 6. 验证、证据与写入审计

执行前检查（UTC 2026-09-14T17:41:11.793Z 起，退出码 0）：

    python -X utf8 -B -S Tools/acceptance/validate_bundle.py --contract docs/acceptance-contracts/P3-3-v6.contract.json --matrix docs/acceptance-contracts/P3-3-v6/P3-3-v6.evidence-matrix.json --repo-root .

输出：

    VALIDATION=PASS contract=P3-3-v6 round=P3-3-V6-FREEZE-20260915-R1 overall=NOT_RUN

最终校验（UTC 2026-09-14T18:00:41.189Z 起，退出码 0）已执行同一命令：

    VALIDATION=PASS contract=P3-3-v6 round=P3-3-V6-FREEZE-20260915-R1 overall=EVIDENCE_GAP

前后两次校验均通过；最终 PASS 指“本份 EVIDENCE_GAP 矩阵与证据包可校验”，
不指产品验收通过。G01/G02 是独立语义审查发现，不会被仅核对结构、
Git 对象和文件哈希的校验器自动消除。原始退出码/stdout/stderr 已落
`evidence/acceptance-20260915/final-validation.json`。另行执行 `git diff --check`
退出码 0、无输出。

审查输出及实际观测：
`docs/acceptance-contracts/P3-3-v6/evidence/acceptance-20260915/review-outputs.json`。
原始入口矩阵、两份实现记录、toy/r6 服务日志及 toy RTT 已逐字节归档；
矩阵 evidence_hashes 绑定各份原件与本轮输出，不把实现记录伪称为本轮硬件采集。
最终验证器输出单独归档，避免矩阵/自身校验结果形成哈希自引用。

主动输出仅为本报告、获准矩阵和该 v6 包内证据；全部目标写入前均按绝对路径、
目录边界和祖先 reparse 属性检查，见 write-preflight.json。
没有主动项目外输出，没有删除或覆盖既有无关文件。
本轮所有 shell 命令显式指定 admission worktree，并使用 cmd.exe，
未启动会产生用户目录缓存的 PowerShell。

CI dispatch/build-only/治理 CI 新增消耗均为 0；手机命令、MCU 命令、
复位、服务/隧道启动、云端操作均为 0。
原有 .cache-ci/、.claude/p33_* 等未跟踪文件保留不动。
看板按本轮显式只读范围未改，实现认领人未覆盖，任务未宣告完成；
合同、冻结索引和两份共享契约未改。未提交、推送、合并或发布。
