# P3-7 立卡依据与分类补正

- 立卡会话: Claude(主会话，非本卡实现者)
- 立卡日期: 2026-09-03
- 锚定提交: `dd0a9952ca2edde8c236a4b1cc57a3ec8879ca0d`(main，P3-6 收口回写 PR #15 合并后)
- 来源: P3-6 独立验收通过并收口后遗留的两项治理欠账，见
  `docs/ota-exec-notes/P3-6-closeout.md` §8、§9。

## 1. 结论

新增一张卡 `P3-7`，范围三件事，都落在同一个文件的同一个步骤上：

1. 把三条可独立运行的**产品回归**接入
   `.github/workflows/firmware-build.yml` 的 host 测试步骤：
   `p3_1_verify_contract_alignment.py`、`p3_1_verify_text_isolation.py`、
   `p3_1_verify_portability.py`。
2. 同批扩 `paths` 触发器，使这些脚本自身被改动时能触发该 workflow，消除
   「改门禁自身却不触发门禁」的静默缺口。
3. 把步骤名 `Test Boot fw_header validator vectors` 与其实际执行内容对齐。

## 2. 为什么合成一张卡，而不是两张

两项欠账改的是同一个 Production `top_file` 的同一个步骤。拆两张卡意味着两轮
完整独立验收，而第一张合并后会使第二张的 Production 基线指纹漂移，第二轮必须
重算——为一行步骤名重命名付两轮验收成本，不成比例。P3-6 收口笔记 §8 已按同一
理由把两项并列登记为「同批处置」。

## 3. 逐脚本重新点数与实测裁定

P3-6 卡内裁定按「共 7 个」计数，**实际目录内为 8 个**，漏计
`p3_1_verify_portability.py`。本节按当前检出逐个实跑重新定案。

命令（每个脚本单独执行，记录退出码与耗时）：

    for f in tests/ota/p3_1_verify_*.py; do python -X utf8 -B "$f"; echo $?; done

| 脚本 | 退出码 | 耗时 | 外部耦合 | 裁定 | 理由 |
|---|---:|---:|---|---|---|
| `contract_alignment` | 0 | 0.33s | 无 | **产品回归，接入** | 47 项零漂移，纯静态比对源码与冻结合同文档 |
| `text_isolation` | 0 | 4.17s | 仅子进程调 `sys.executable` 跑同仓测试 | **产品回归，接入** | 3 用例零失败，验证明文零泄漏与 sink 守卫 |
| `portability` | 0 | 1.27s | 无 | **产品回归，接入** | 扫描 893 文件，阳性对照 1 命中、在编源 0 命中；`AGENTS.md`「GCC / Linux CI 源码可移植防坑」已把反斜杠 `#include` 定为硬失败红线 |
| `mutation` | 0 | 15.9s | `shutil.which("gcc")` | 验收工具，不接入 | 见 §4 更正二 |
| `production_binary` | 0 | — | 硬编码 `MDK-ARM_F435/cmake-generated/build-gcc-release` 与本机绝对工具链 `D:/singlechip/.../arm-none-eabi-nm.exe` | 验收工具，不接入 | CI 构建目录为 `/tmp/etfw`，且无该 Windows 路径；接入需改 P3-1 已冻结脚本 |
| `rx_ring_budget` | 0 | — | 同上，另需该目录下 `compile_commands.json` | 验收工具，不接入 | 同上 |
| `artifacts` | 0 | — | 硬编码 P3-1 该轮申报的 9 个产物 SHA-256 | 验收工具，永不接入 | 本机仍绿只因旧构建产物未被覆盖；换机器或重构建即失效 |
| `command_fidelity` | 1 | — | 需 `docs/acceptance-contracts/P3-1-v1/commands` | 验收工具，永不接入 | 该目录已随 v1→v2 消失，当前即为红 |

接入的三条本机合计约 5.8s，相对现有 job 时长可忽略。

## 4. 对 P3-6 分类裁定的两处更正

P3-6 的卡内文本是已验收内容，**不回改**；此处只记录更正，供后续引用以本节为准。

- **更正一（计数）**：`tests/ota/p3_1_verify_*.py` 是 8 个不是 7 个，
  `portability` 被整体漏计。它按性质属产品回归，本卡一并接入。
- **更正二（`mutation` 的理由）**：P3-6 把它归入「结构性绑定 P3-1 单轮状态」
  且称「分钟级开销」。实测为 15.9s，且它用 `shutil.which("gcc")` 定位编译器、
  只在 `.cache` 下操作源码副本，并不绑定本机路径或该轮产物——原理由两条都不
  成立。但结论仍维持不接入，正确理由是：它校验的是**测试自身的鉴别力**（注错
  后 harness 是否变红），属于每轮验收要证明的 harness 属性，不是每次推送要守
  的产品行为。此裁定就此闭合，不再作为遗留项。

## 5. 本批次治理耦合（新增卡必然触发）

新增 `#### P3-7` 标题落在 P2-6 之后、readiness 标记之前，
`tests/ota/test_acceptance_bundle.py` 的
`post_p26_task_ids()` 会强制要求 §8.1 矩阵**同序同项**，且顺序列严格 1..N。
因此同批必须一起改的有：

1. `PLAN-OTA-EXEC.md` §6 新增 P3-7 卡（状态 `待办`，不记任何哈希）。
2. `docs/ota-prompts/prompt-P3-7-implementation.md` 派工书（17 个必备小节）。
3. §8.1 新增第 7 行，原第 7-13 行顺延为 8-14，并更新可派单集合正文。
4. `tests/ota/test_acceptance_bundle.py` 中钉死的可派单集合由 5 项扩为 6 项，
   保持全等比较语义，不得放宽为子集。
5. §9 变更登记表登记本次治理变更；§10 追加会话日志行。
6. §1 阶段状态总表 P3 行订正为「进行中 2/7」。该行原为「1/6」：P3-6 完成后分子
   未回写（P3-6 收口回写批次遗漏），本次立卡又使分母由 6 变 7，一并订正。

`dependency_state` 据实为满足（P3-1、P3-6 均已合并入 main，三条脚本已是跟踪
文件），推导出的派单资格即为可派单——这正是必须动那条钉死断言的原因，与 P3-6
批次同构。

## 6. 冻结红线（验收不一定抓得住，故在派工书中固化）

- **不得重命名或移动 `tests/ota/p3_1_verify_*.py`**。看似「改名成
  `test_ota_*.py` 就自动匹配现有触发器」更省事，但这 8 个路径被
  `P3-1-v2` 与 `P3-6-v1` 两份冻结合同的 Validation manifest 逐路径绑定，改名会
  把「哈希漂移」升级为「文件缺失」，两份合同将无法按路径复算。正确做法是扩触
  发器。
- **不得删除 `Libraries/USB_MSC/msc_diskio.c.old`**。它是 `portability` 的唯一
  阳性对照来源；删掉后 `archived` 为空，脚本按 fail-closed 设计直接判失败。
- **不得修改 workflow 顶层 `name:` 与 `jobs.build.name`**
  （`Build firmware (arm-none-eabi-gcc)`）。分支必需检查按「workflow 名 / job
  名」标识，改步骤名是纯展示层、安全；改这两个会打断必需检查。
- **`mutation` 输出中出现 `FAIL` 字样属预期**（注错被检出即打印 FAIL），若将来
  有人接入它，不得据此「修绿」。

## 7. 已知代价（如实登记）

本批次会改动 `PLAN-OTA-EXEC.md`、`docs/ota-prompts/`、
`tests/ota/test_acceptance_bundle.py`，因此会使 `P3-1-v2` 与 `P3-6-v1` 两份已
冻结合同的 Governance 与 Validation 指纹进一步漂移。两者的 Governance 指纹在
P3-6 收口回写时即已漂移，可复现性由锚定提交承载，与 `docs/acceptance-execution-contract.md`
的既有处置一致；本批次不新增处置方式。

## 8. 复算命令

    python -X utf8 -B tests/ota/p3_1_verify_contract_alignment.py
    python -X utf8 -B tests/ota/p3_1_verify_text_isolation.py
    python -X utf8 -B tests/ota/p3_1_verify_portability.py
    python -X utf8 -B -m unittest tests.ota.test_acceptance_bundle
