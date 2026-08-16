# 验收会话提示词模板（派给独立验收 agent）

> 用途：把一张已「完成实现、待验收」的看板任务卡冻结成一份可直接派发的验收提示词。
> 撰写者：主会话或立卡方。执行者：**非实现会话**（强模型/验收侧）。
> 配套：`docs/ota-prompts/prompt-template-implementation.md`（执行侧模板）。
>
> 本文件分两部分：
> - **Part A 撰写检查表** —— 给撰写者看，**禁止复制进派发的 prompt**。
> - **Part B prompt 骨架** —— 复制到 `docs/ota-prompts/prompt-<卡ID>-acceptance.md`
>   后逐项填空。派单提示词是规范性文件，必须落在 `docs/ota-prompts/`（纳入 Governance
>   manifest 与 Acceptance Governance workflow），**不得放在 `.claude/`**。

---

# Part A：撰写检查表（不要复制到派发文件）

## A.1 验收侧的失控是真实成本，必须先设上限

P2-5 F4 独立验收（证据目录 `.acceptance-p2-5-f4/20260810-200500`）耗时约 **43 小时**，
产出 33 PASS / 0 FAIL / **33 NOT_OBSERVED**，真机 OTA 与封包一项未做。三个结构性根因：

| 根因 | 表现 | 本模板对应条款 |
|---|---|---|
| **审计递归** | 把「执行前审计 harness」理解成每次 harness 编辑都重建全链证明，做了 R3–R22 共 19 轮，审计生成器代码 768 KB，而被验收的生产改动只有 12 文件 / 350 行。矩阵冻结在 33 PASS 后又做 R18–R22 五轮，产品证据增量为 **0** | Part B §2 harness 冻结 + §3 轮次上限 |
| **门禁自指** | 917 ms 门禁 = 历史观测 817 ms + 100 ms 输入轮询，**不是产品需求**。实测 914.387 ms，余量 2.6 ms（0.28%），正常抖动即翻转结论 | Part B §4 门禁来源审查 |
| **边缘 fixture 误当强制项** | 某判据实际已被既有 fixture 覆盖同一行代码，真正独立的只是一个纯函数分支（宿主测试即可），却按模拟器路线试了 4 次，全部撞 Win32 `MAX_PATH` 260 上限 | Part B §5 路线选择前置 |

**结论**：验证基础设施的复杂度一旦超过被验证产品，验收就不再收敛，并且会把 harness
故障误报成产品 FAIL（P2-5 的 r3 报告 FAIL 结论即被后续 6/6 PASS 推翻，根因是截图
harness 干扰）。

## A.2 撰写完成前自检

- [ ] 已指明冻结合同路径与版本（`docs/acceptance-contracts/<卡ID>-v<n>.contract.json`）
- [ ] 已列出本卡全部数值门禁**及其来源分类**，历史观测值来源的已标注「需用户裁定」
- [ ] 已写明轮次上限，且收敛条件绑定机器生成的 rerun plan（非人工判断产品增量）
- [ ] 已要求失败分层（PRODUCT_FAIL / HARNESS_FAIL / EVIDENCE_GAP / ENV_BLOCKED）
- [ ] 已列出需用户物理配合的项，并禁止以其他方式替代
- [ ] prompt 里没有任何 `git commit/push/merge` 指令

---

# Part B：prompt 骨架（复制此段并填空）

```text
# 任务：独立验收 OTA 看板任务卡 <卡ID>（<一句话标题>）

> 本文件是 <卡ID> 验收会话的提示词。落盘时间 <YYYY-MM-DD>。
> 你**不是**本卡的实现者。实现证据见 <实现证据文档路径>。

## 0. 你的身份与规约（先读，违反即作废）

你是 **<卡ID> 的独立验收会话**。强制生效：

1. `AGENTS.md`「独立验收执行规约」+ `docs/acceptance-execution-contract.md` v2。
2. **不得覆盖实现认领人**。你只在证据栏追加「验收人 + 轮次 + 单轮结果」。
3. 单轮结果固定五种，**必须分层**，不得混同：
   `PASS` / `PRODUCT_FAIL` / `HARNESS_FAIL` / `EVIDENCE_GAP` / `ENV_BLOCKED`。
   **harness 失败绝不能写成产品不通过**（P2-5 曾因此误报 FAIL 后被推翻）。
4. **不提交**：禁止 `git commit` / `push` / `merge`，由主会话收口。
5. **绝对禁止** `git checkout -- <file>` / `git restore`。
6. 收尾：回写卡状态（只改状态字段允许的四种取值），看板 §10 追加一行。

全局准则：**一切输出用简体中文**（代码标识符除外）。

## 1. 冻结合同（唯一标准）

- 合同：`docs/acceptance-contracts/<卡ID>-v<n>.contract.json`，状态必须为 `FROZEN`
- 矩阵：`.acceptance-<卡ID>/<round>/evidence-matrix.json`
- **本 prompt 不是标准**。prompt 只解释合同，冲突时以合同为准
  （`docs/acceptance-execution-contract.md` §1.2）。
- 验收开始后**不得原地改合同**。新增或改变门禁必须升版本重新审批：
  同一 `task_id`、版本严格加一、用 `parent_contract_sha256` 绑定上一份。

三类 manifest 生成命令见 `docs/acceptance-execution-contract.md` §5，profile 范围
唯一定义在 `Tools/provenance/manifest_profiles.json`，不得手写范围。

最终校验（失败不得宣告通过）：

  python Tools/acceptance/validate_bundle.py \
    --contract docs/acceptance-contracts/<卡ID>-v<n>.contract.json \
    --matrix .acceptance-<卡ID>/<round>/evidence-matrix.json \
    --repo-root <本轮精确 Git worktree>

## 2. harness 一次性冻结（防审计递归，硬约束）

1. **开工第一步**：确定 harness 全集（runner、探针、截图脚本、注错脚本），
   跑一次 dry-run 确认可用，然后**冻结**。
2. 冻结后 harness 若必须修改：**只对被改文件做增量审计**
   （语法/AST、常量结论、动态加载、强杀路径、路径边界），
   **不得**因一次编辑就重建绑定全部历史审计产物的证明链。
3. 完整 provenance 复核**只做两次**：封包前一次、最终报告前一次。
4. `docs/acceptance-execution-contract.md` 的「结论作废」条款**只在发现 required
   outcome 被硬编码时触发**，不适用于每次 harness 编辑。不要扩大解释。
5. harness 必须 fail-closed：缺日志、超时、地址漂移、解析失败、进程异常一律失败，
   禁止常量 PASS、无条件汇总字段，禁止用「没有错误日志」推定通过。
6. 至少保留一个负例或故障注入，证明判据具有鉴别力。

**红线**：验证基础设施的规模不得超过被验证的产品改动。若你发现自己在为
「证明 harness 可信」而写新 harness，**立即停止并上报** —— 这就是 P2-5 的失控路径。

## 3. 轮次上限与收敛条件（硬约束）

- 计划轮次：**<n> 轮**（默认 3）。达到上限仍未收敛 → 停止并上报，不得自行加轮。
- **开新轮次的唯一判据是机器生成的 rerun plan，不是人工回答**。开轮前先用
  `validate_bundle.py --write-rerun-plan` 生成计划（失效规则见
  `docs/acceptance-execution-contract.md:168`）。若 `rerun_criteria` 为空，
  且不存在任何 required 命令、产物或证据缺口，**不得开启新轮次**。
- 因 `HARNESS_FAIL`、`EVIDENCE_GAP`、`ENV_BLOCKED` 修复后**重新采集同一条产品观测值
  是允许的**（这类轮次的 rerun plan 非空或存在 required 缺口）。不得用「产品值没变」
  为由拒绝重采，也不得反过来用「换个说法就是新观测」为由绕过上一条。
- 矩阵一旦冻结在某个结果集上，除以下情况不得重开：
  ① 发现 required outcome 被硬编码；② 产品源（Production manifest 稳定指纹）变化；
  ③ 自动 rerun plan 判定该判据必须重跑；④ 用户裁定重开。

## 4. 门禁来源审查（防门禁自指，先做再测）

**在跑任何性能/耗时判据之前**，逐条检查数值门禁来源，只允许三类：

- `product_sla`：产品需求或规格
- `protocol_contract`：协议/契约推导
- `safety_ratio`：明确的安全比例

若某门禁实际是「历史观测值 + 极小余量」→ **停止该判据，请用户裁定**。
不得由你自行放宽，也不得硬扛。历史测量值只能作基线或告警阈值。

同时检查余量：实测与门槛的余量若小于正常抖动幅度，该判据**不具鉴别力**，
必须在报告中如实标注，不得凭一次通过就写 PASS。

## 5. 路线选择前置（防边缘 fixture 浪费）

对每个判据，动手前先回答两问：

1. **是否已被既有 fixture 覆盖同一代码路径？** 是 → 标注覆盖来源，不重复搭环境。
2. **最省的可信路线是什么？** 纯函数 → 宿主测试；需要 LVGL/文件系统 → 模拟器；
   只有涉及真实外设/时序/供电才上真机。

已知环境上限（撞上就换路线，不要反复试）：
- Win32 物理路径 `MAX_PATH` = 260，构造超长 LVGL 路径的模拟器方案不可行
- <本卡相关的其他已知环境上限>

同一路线连续 2 次因环境限制失败 → 换路线或标 `ENV_BLOCKED`，不要试第 3 次。

## 6. 本卡判据与执行要点

<逐条列出合同里的 required 判据，给出：判据ID、要观测什么、用哪条路线、
 已知坑。不要在此重复合同正文，只写执行要点。>

1. <判据ID>：<观测目标> ｜ 路线：<宿主/模拟器/真机> ｜ 注意：<已知坑>
2. ...

需用户物理配合的项（**你做不了，如实标注「待用户配合」，
不得以其他方式替代或声称通过**）：

- <例如：拔掉 J-Link 与 USB 后电池供电开机；拔卡拷贝 .etu 后插回>

## 7. 真机执行纪律（若本卡涉及）

严格按 `AGENTS.md`「J-Link 闭环防卡死清单」。RTT 地址必须从**本次烧录目标本次
链接生成的 map** 取 `_SEGGER_RTT`：

- GCC 生产：`MDK-ARM_F435\cmake-generated\build-gcc-release\app-gcc\X-Track-App-GCC.map`
- AC5 辅助：`MDK-ARM_F435\Listings-App-AC5\X-Track-App-AC5.map`

顺序：查 map → `mem8 <RTT> 16` 验「SEGGER RTT」签名 → 读 down descriptor →
启动**单个** `JLinkRTTLogger` 且带明确超时。启动前清残留：

  Stop-Process -Name JLinkRTTLogger -Force -ErrorAction SilentlyContinue

污染日志（旧 RTT 地址 / 残留 logger / 错误命令回显 / 与当前源码不匹配）一律标记
污染并重测，不得参与判定。

设备风险：烧录会 halt MCU，可能把传输中的 SD 卡打成软复位救不回的挂死态
（现象 `SD_IsReady=0`、stat 全 0、瓦片消失）。恢复方式是拔插 SD 卡或整机断电，
**不是代码 bug**，不要去改代码。

## 8. 交付清单

- 最终矩阵：每项判据填 `result` / `execution` / `observed` / `evidence`，
  `observed` 必须是可与 gate 机械比较的布尔值、带单位数值或完整状态链。
- 紧凑证据包（`docs/acceptance-execution-contract.md` §8）：冻结合同、最终矩阵、
  三类 manifest、rerun plan（若复用）、命令输出、决定性原始日志、最终产物、
  外部输入证据。**默认不保留完整构建目录与源码副本。**
- 验收报告：逐判据结论 + 单轮结果分类 + **未观测项如实列出及原因**。
- 若出现 `HARNESS_FAIL`：明确写「这是验证工具问题，不是产品不通过」。
- 回写卡状态 + 看板 §10 追加一行。
- **不 commit**。
```
