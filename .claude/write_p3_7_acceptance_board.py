"""P3-7 验收回写看板（字节编辑，逐处保留原行尾）。

PLAN-OTA-EXEC.md 是混合行尾（CRLF 728 / 裸 LF 252），且是 Governance profile 的
top_file。两条硬约束：
1. 只能字节编辑，不能用会整体归一行尾的编辑器/工具，否则一处改动带出上百行伪 diff；
2. 看板内不得出现任何哈希（含 commit SHA）——看板字节被 Governance manifest 绑定，
   在其中记哈希会构造出「写哈希 -> 看板变 -> 指纹变 -> 哈希失效」的不收敛自指环。
   哈希与提交号一律落 docs/ota-exec-notes/。

本脚本改 5 处：P3-7 卡的 状态/验收/证据 三行 + 新增一行验收发现、§1 阶段总表 P3 行
的完成计数、§9 登记 v2 增量、§10 追加一行会话日志。
"""

import hashlib
import pathlib

ROOT = pathlib.Path("D:/github/my/E-Track")
BOARD = ROOT / "PLAN-OTA-EXEC.md"

# --- 1. 状态行（CRLF） ------------------------------------------------------
OLD_STATUS = (
    "状态: 进行中 ｜ 认领: Claude(P3-7 实现 agent, P3-7-WIRING-20260903) / 2026-09-03 ｜ "
    "更新: 2026-09-03(认领开工; 三件事同批完成) ｜ 2026-09-03(v2 打回补做: 追加第 4 条执行行 "
    "test_ota_device_info.py(置末位不动 9/10/11 序号, paths 一行不加、靠既有 test_ota_*.py "
    "通配覆盖以保持互镜); 修正 CI 反证选点两处空转并扩为 4 次, 每次按 CI 同序 12 条预演, "
    "红点全部恰落在目标行)"
)
NEW_STATUS = (
    "状态: 完成(2026-09-03 非实现独立验收第 3 轮 PASS, 轮次 P3-7-V1-FREEZE-20260903-R3, "
    "合同制正式验收, 冻结 P3-7-v1 合同+三类 manifest+证据矩阵, validate_bundle.py 通过, "
    "待收口) ｜ 认领: Claude(P3-7 实现 agent, P3-7-WIRING-20260903) / 2026-09-03 ｜ "
    "验收: Claude(P3-7 非实现独立验收会话) / 2026-09-03 ｜ "
    "更新: 2026-09-03(认领开工; 三件事同批完成) ｜ 2026-09-03(v2 打回补做: 追加第 4 条执行行 "
    "test_ota_device_info.py(置末位不动 9/10/11 序号, paths 一行不加、靠既有 test_ota_*.py "
    "通配覆盖以保持互镜); 修正 CI 反证选点两处空转并扩为 4 次, 每次按 CI 同序 12 条预演, "
    "红点全部恰落在目标行) ｜ 2026-09-03(独立验收三轮: 第 1 轮 PRODUCT_FAIL(注错选点空转), "
    "第 2 轮 EVIDENCE_GAP(唯一硬原因为零次真实 CI 运行); 用户放行后收口批次在特性分支 "
    "ota/p3-7-host-test-wiring 取得全部 11 条 CI 腿(正例 1+触发器反证 2+注错红 4+还原绿 4), "
    "两个验收核验器双绿, 第 3 轮判 PASS)"
)

# --- 2. 验收行（CRLF）：按派工书 v2 增量同步为 4 条接线 / 11 条腿 -----------
OLD_ACCEPT = (
    "- 验收: CI 日志出现三条脚本的实际执行输出与各自结论标记且 job 为绿; "
    "触发器反证(只改被接入脚本文件本身的一次推送能触发该 workflow); "
    "三次 fail-closed 反证(分别对合同对齐、文本隔离、可移植性三条判据注入可定界缺陷, "
    "观测变红后还原转绿)。仅有 workflow 文本 diff 或本地执行通过不算。"
)
NEW_ACCEPT = (
    "- 验收(按派工书 v2 同步, 增量已登记 §9): CI 日志出现四条脚本的实际执行输出与各自结论"
    "标记且 job 为绿; 触发器反证 2 条(新增精确条目覆盖一条、既有 test_ota_*.py 通配覆盖一条, "
    "各以一次只改该脚本自身的推送触发该 workflow); 四次 fail-closed 反证(分别对合同对齐、"
    "文本隔离、可移植性、设备身份四条判据注入可定界缺陷, 观测变红后还原转绿)。仅有 workflow "
    "文本 diff 或本地执行通过不算。注错选点须两级安全: 命令级(前置命令不得先红)与步骤级"
    "(不得打红更早的 CI 步骤, 否则目标步骤 skipped、反证空转)。"
)

# --- 3. 证据行（CRLF）：追加验收侧产出 --------------------------------------
OLD_EVID_TAIL = (
    "治理测试 65/65; CI 正例+触发器反证+CI 版四次反证按 §0 规则 8 待主会话推送后回填其 §5)"
)
NEW_EVID_TAIL = (
    "治理测试 65/65; §5 已由收口批次回填至 11 条腿) ｜ "
    "docs/ota-exec-notes/P3-7-acceptance-round1.md、-round2.md、-round3.md(三轮独立验收记录, "
    "全部哈希与 run/commit 标识登记于此) ｜ docs/acceptance-contracts/P3-7-v1.contract.json"
    "(冻结合同) ｜ docs/acceptance-contracts/P3-7-v1/(证据包: 三类 manifest、命令原始日志、"
    "11 次 CI 运行的元数据/步骤日志/改动文件清单、证据矩阵) ｜ "
    ".claude/verification-report-p3-7.md(审查评分)"
)

# --- 4. 新增验收发现行（插在证据行之后，CRLF） ------------------------------
FINDINGS = (
    "- 验收发现(均不阻断本卡): F-4 P3-6 的冻结 harness tests/ota/p3_6_verify_ci_wiring.py "
    "现为红(2 项失败), 红因唯一且可归属——本卡按派工书授权把该步骤改名, 而该 harness 把旧"
    "步骤名钉死; P3-6 证据包在其冻结提交上仍可校验, 属「每轮证据包只在其冻结提交上可校验」"
    "的设计结果而非回归, 不回改 P3-6 冻结字节, 如需在 main 上重新可跑须另行立卡并出 P3-6 "
    "新版本合同。F-5 第 4 条接线 test_ota_device_info.py 原不在本卡范围, 经用户裁定不另立"
    "新卡, 改以同 task_id 的派工书 v2 承接(见 §9)。局限二则如实登记: 两条触发器反证的提交"
    "所在临时分支已按计划删除, 提交本身不被任何 ref 指向(门禁复算只读冻结证据文件、不含 "
    "git 调用, 故不受影响, 受影响的仅是人工按 SHA 追溯); CI 证据门禁只比红/绿两次提交的"
    "改动文件路径集合, 不比同一文件的 blob 哈希。另: 本轮 CI 证据由验收会话自行推送产生, "
    "取证方与被验方同源, 可核部分为分支端态相对基线在 Libraries/、USER/、boot/、"
    "MDK-ARM_F435/ 四个红线目录上 diff 为空且每次注错/还原提交恰含一个文件。"
)

# --- 5. §1 阶段总表 P3 行（CRLF） -------------------------------------------
OLD_P3_ROW = "| P3 | BLE+Flutter | 进行中 | 3/7 | P2-1/2 完成 |"
NEW_P3_ROW = "| P3 | BLE+Flutter | 进行中 | 4/7 | P2-1/2 完成 |"

# --- 6. §9 登记行（该表末行为裸 LF） ----------------------------------------
S9_ANCHOR = "分类补正与逐脚本实跑取证落 docs/ota-exec-notes/P3-7-card-creation.md"
S9_ROW = (
    "| 2026-09-03 | P3-7 / 非实现独立验收会话(第 2 轮) | 第 2 轮验收发现 F-5: 本卡在 CI 步骤"
    "末位新接的第 4 条执行行 tests/ota/test_ota_device_info.py 不在立卡时的卡内范围与派工书 "
    "v1 完成判据内, 属实现方自行扩范围; 但该脚本是 P3-2 的产品回归, 接入本身正确且已实测"
    "有效, 退回会丢掉一条真实门禁 | 初议另立新卡承接该增量 | 用户裁定: **不另立新卡**(会让"
    "项目计划变臃肿), 改以同一 task_id 的派工书升版承接 —— docs/ota-prompts/"
    "prompt-P3-7-implementation.md 出 spec_version=2 并以 parent_spec_sha256 绑定 v1 字节, "
    "四项实质增量为: 接线 3 条扩为 4 条; paths 闭包判定改为实算覆盖(该脚本靠既有 "
    "test_ota_*.py 通配覆盖, 不加冗余精确条目); fail-closed 反证 3 次扩为 4 次并新增"
    "「注错选点两级安全」硬前置(命令级+CI 步骤级); 触发器反证 1 条扩为 2 条(新增精确条目"
    "一条、既有通配一条)。看板本卡验收字段同步为 v2 标准。不改任何冻结合同、二进制契约"
    "与产品代码 | 已执行/已升版\n"
)

# --- 7. §10 会话日志（末行为 CRLF） -----------------------------------------
S10_LINE = (
    "- 2026-09-03 ｜ Claude(P3-7 非实现独立验收会话 / 收口批次) ｜ P3-7(三轮独立验收, 第 3 轮 "
    "PASS, 置完成待收口) + §1 阶段总表(P3 进度 3/7→4/7) ｜ 第 1 轮 PRODUCT_FAIL: 四次注错选点"
    "中有两处会先红在更早的命令上, 属空转反证。第 2 轮 EVIDENCE_GAP: 实现方已按打回补做"
    "到位, 但零次真实 CI 运行, 而本卡验收标的恰恰就是 CI 行为, 本地跑再多也不构成证据。"
    "用户放行推送后, 收口批次在特性分支取得全部 11 条腿: 正例 1、触发器反证 2、注错红 4、"
    "还原绿 4。两条触发器反证走「临时建 master 分支单文件推送后删除」路线, 因为该 workflow "
    "的 push 只在 main/master 触发, 而 pull_request 的 paths 按整个 PR diff 判定(PR diff 里"
    "永远含被改的 workflow 自身), PR 同步事件无法证明 paths 闭包。取证中作废一次注错并留档"
    "为通用规则: 反证三首次尝试的缺陷让 arm-none-eabi-gcc 编译失败, CI 在更早的 Build "
    "firmware 步骤就红了, 目标步骤整步 skipped、目标行从未执行——本地按命令同序跑一遍看不见"
    "固件编译, 故注错选点必须两级判定(命令级+CI 步骤级), 重做改用 #if 0 包裹的阳性样本并"
    "先在本机跑同配置 GCC 构建证明编译不受影响。本轮另修两处本方 harness 缺陷: 一是 CI 证据"
    "核验器的双向鉴别力自检在真实 run 号回填后, 常量字面替换全部失配, 退化成「11 个变异全红"
    "但红因清一色是证据文件缺失」的零鉴别力状态, 改按常量名整行改写并加残留断言后恢复; 二是"
    "派工书 v2 的写入脚本吞掉了「## 任务类型」章节标题, 被治理自测当场抓红(它抓的是验收方的"
    "错), 修后 65/65 复绿。交付比对基线由 HEAD 改为固定 commit 常量, 因为交付一旦提交, "
    "对 HEAD 比 diff 会退化成恒真。另记一条执行纪律: 两个验收核验器会调起 "
    "test_acceptance_bundle 在仓库根建临时目录, 必须串行跑, 并发会互相看见对方的临时目录"
    "而报假红。不阻断发现与局限见本卡验收发现字段。未 commit/push/merge 之外的动作留主会话"
    "在用户确认后收口; 看板不记哈希, 全部哈希与 run/commit 标识落 "
    "docs/ota-exec-notes/P3-7-acceptance-round3.md"
)


def replace_once(data, old, new, label):
    ob, nb = old.encode("utf-8"), new.encode("utf-8")
    count = data.count(ob)
    assert count == 1, f"{label}: 锚点出现 {count} 次，期望 1"
    return data.replace(ob, nb, 1)


def main():
    b = BOARD.read_bytes()
    before = (b.count(b"\r\n"), b.count(b"\n") - b.count(b"\r\n"), len(b))
    print(f"改前: CRLF={before[0]} bareLF={before[1]} len={before[2]} "
          f"sha256={hashlib.sha256(b).hexdigest().upper()[:24]}")

    b = replace_once(b, OLD_STATUS, NEW_STATUS, "状态行")
    b = replace_once(b, OLD_ACCEPT, NEW_ACCEPT, "验收行")
    b = replace_once(b, OLD_EVID_TAIL, NEW_EVID_TAIL, "证据行尾")
    b = replace_once(b, OLD_P3_ROW, NEW_P3_ROW, "§1 P3 行")

    # 验收发现行：插在证据行之后（证据行以 CRLF 结束）
    tail = NEW_EVID_TAIL.encode("utf-8") + b"\r\n"
    assert b.count(tail) == 1, "证据行尾 + CRLF 不唯一"
    b = b.replace(tail, tail + FINDINGS.encode("utf-8") + b"\r\n", 1)

    # §9：在立卡批次那一行之后追加新行（该表用裸 LF）
    anchor = S9_ANCHOR.encode("utf-8")
    assert b.count(anchor) == 1, "§9 锚点不唯一"
    i = b.index(anchor)
    j = b.index(b"\n", i) + 1
    assert b[j - 2:j - 1] != b"\r", "§9 末行意外为 CRLF"
    b = b[:j] + S9_ROW.encode("utf-8") + b[j:]

    # §10：文件末尾追加一行（末行为 CRLF）
    assert b.endswith(b"\r\n"), "文件末尾不是 CRLF"
    b = b + S10_LINE.encode("utf-8") + b"\r\n"

    after = (b.count(b"\r\n"), b.count(b"\n") - b.count(b"\r\n"), len(b))
    print(f"改后: CRLF={after[0]} bareLF={after[1]} len={after[2]} "
          f"sha256={hashlib.sha256(b).hexdigest().upper()[:24]}")
    print(f"行尾增量: CRLF +{after[0] - before[0]} 裸LF +{after[1] - before[1]}")
    BOARD.write_bytes(b)


if __name__ == "__main__":
    main()
