"""P3-2 验收回写看板：字节级编辑，保留原混合行尾，绝不写入任何哈希。

看板是 Governance profile 的 top_file，写入哈希（含 commit SHA）会造成
「哈希写进被哈希文件」的不收敛自指，故全部哈希只落 docs/ota-exec-notes/。
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "PLAN-OTA-EXEC.md"

raw = BOARD.read_bytes()
text = raw.decode("utf-8")
orig = text

# ---- 1. §1 阶段总表：P3 进度 2/7 -> 3/7 ----
old_row = "| P3 | BLE+Flutter | 进行中 | 2/7 | P2-1/2 完成 |"
new_row = "| P3 | BLE+Flutter | 进行中 | 3/7 | P2-1/2 完成 |"
assert text.count(old_row) == 1, "§1 P3 行未唯一命中"
text = text.replace(old_row, new_row)

# ---- 2. P3-2 状态行：进行中 -> 完成，追加验收字段（不覆盖实现认领） ----
old_status = ("状态: 进行中 ｜ 认领: Claude(P3-2 实现 agent) / 2026-09-03 ｜ "
              "更新: 2026-09-03(实现完成待独立验收)")
new_status = (
    "状态: 完成(2026-09-03 非实现独立验收单轮结果 PASS, 轮次 "
    "P3-2-V1-FREEZE-20260903-01, 合同制正式验收, 12 判据全 EXECUTED PASS, "
    "待收口) ｜ 认领: Claude(P3-2 实现 agent) / 2026-09-03 ｜ "
    "验收: Claude(P3-2 非实现独立验收会话) / 2026-09-03 ｜ "
    "更新: 2026-09-03(实现完成; 同日非实现会话按 docs/acceptance-execution-contract.md "
    "冻结 P3-2-v1 合同+三类 manifest+证据矩阵, validate_bundle.py 通过, 单轮结果 PASS; "
    "收口未执行, 按 §0 规则 8 待主会话在用户确认后小步提交)"
)
assert text.count(old_status) == 1, "P3-2 状态行未唯一命中"
text = text.replace(old_status, new_status)

# ---- 3. P3-2 卡内追加独立验收与验收发现两行（插在 证据 行之后） ----
m = re.search(r"^- 证据: host 测试 114/114 断言 PASS.*?$", text, re.M)
assert m is not None, "P3-2 证据行未命中"
eol = "\r\n" if text[m.end():m.end() + 2] == "\r\n" else "\n"

added = (
    "- 独立验收: 轮次 P3-2-V1-FREEZE-20260903-01 ｜ 执行者 Claude(P3-2 非实现独立验收会话,"
    "非本卡实现者,本会话此前只立 P3-7 卡与冻结 P3-2 派工书) ｜ 单轮结果 PASS"
    "(取值域 PASS/PRODUCT_FAIL/HARNESS_FAIL/EVIDENCE_GAP/ENV_BLOCKED) ｜ "
    "12 判据全 EXECUTED,无 REUSED ｜ 独立复算手段: 不复用实现方任何解码脚本,按冻结契约条文"
    "自写四个 fail-closed 核验器(真机帧与摘要域分离 41 项、harness 静态属性与冻结向量逐字节"
    "核对 38 项、改动范围与生产红线 23 项、构建产物三方闭合与生产符号落位 14 项,合计 116 项"
    "零失败); 关键独立证据三条 —— ① 独立重算证明 raw 身份域与 fw_header 双零域互异且 "
    "INFO.image_sha256 全 32B 落在 raw 域(OTA-XC-IMAGE-IDENTITY 未被混域); ② 源码全量 clean "
    "重建 → etu_pack finalize 回填 → 包内板上 dump 三方逐字节同值,且 finalize 差异全部落在 "
    "0x400..0x45F,使 INFO 摘要绑定到本仓库源码而非「某个板上镜像」; ③ 三处红线单点注错"
    "(混域/机型改回 X-Track/BCB IO 不再 fail closed)各把 host harness 打红且均非编译错误,"
    "还原后复绿,证明 harness 有鉴别力 ｜ 另独立复现实现方声明的双产物字节可复现性,其中 Boot "
    "本轮真实重链后仍逐字节相同(实现方那轮 Boot 为 up-to-date 未重链),证据强度高于原申报 ｜ "
    "顺带确认本卡修掉了一处真实冻结契约违反: 旧占位链上报 model=X-Track 违反 "
    "OTA-XC-DEVICE-MODEL, 现设备实测上报 E-Track+NUL 恰 8B ｜ 验收报告 "
    "docs/ota-exec-notes/P3-2-acceptance-round1.md(全部哈希登记于此; 看板为 Governance "
    "top_file,不记哈希) + 冻结合同 docs/acceptance-contracts/P3-2-v1.contract.json + 证据矩阵 "
    "docs/acceptance-contracts/P3-2-v1/P3-2-v1.evidence-matrix.json + 三类 manifest + 命令日志 "
    "docs/acceptance-contracts/P3-2-v1/commands/ + 核验器 tests/ota/p3_2_verify_*.py"
    + eol +
    "- 验收发现(均不阻断,不构成本卡判据): F-1 MDK-ARM_F435/cmake-generated/CMakeLists.txt 被"
    "编辑器整体行尾归一,1 行真实改动(注册 ota_device_info.c)带出 547 行行尾伪变更; 该文件在 "
    "HEAD 内本为混合行尾且当时无 .gitattributes 保护,而 Tools/provenance/source_manifest.ps1 "
    "哈希的是工作区字节,Git 自身也给出 \"LF will be replaced by CRLF the next time Git touches "
    "it\" 警告 —— 即在纯 LF 工作副本上冻结的 Production 指纹先天不可复现,属指纹有效性问题而非"
    "排版偏好; 本会话按 P3-6 先例补 .gitattributes 行尾护栏 9 条(该文件不属任何 manifest "
    "profile,对三类指纹中性; git hash-object 过滤前后一致证明对入库字节亦中性),补后警告消失; "
    "未自行改回 CRLF(会使验收方兼任实现方,违反 §0 规则 4),亦未因空白差异退回本卡。"
    "F-2 本会话冻结的 docs/ota-prompts/prompt-P3-2-implementation.md 未把 MDK-ARM_F435/** 写入"
    "允许修改范围,而新增卡内产品源必须注册进 CMake 与 Keil 两条构建链; 逐行核对两处改动各只有"
    "一行/一组文件条目、无夹带,裁定为「范围内必要」不计越界,责任在派工书作者(本会话)而非实现方,"
    "后续派工书须显式写出构建注册路径。另两项候选发现在核实中自行消解: keil_uvprojx2cmake.py "
    "未入库故手改生成物是唯一可行路径; .cache-cmake-time-test.cmake 时间戳早于本卡约三周属既有残留"
    + eol +
    "- 范围外未观测(不影响完成判据): 实现方 §7.5 记录的 R10「seq=0x1234 回显铁证」因 J-Link USB "
    "链路故障需物理拔插/断电恢复而未完成,单轮分类 ENV_BLOCKED。本轮已用不依赖 seq 的独立证据覆盖"
    "同一风险: 帧内 32B 摘要必须等于板上镜像 raw SHA-256,而板上镜像又等于本仓库源码重建后 "
    "finalize 的镜像(三方逐字节闭合),一个更早的残留帧不可能携带与当前源码构建结果一致的摘要,"
    "故 R10 属加强项而非判据缺口"
)
insert_at = m.end() + len(eol)
text = text[:insert_at] + added + eol + text[insert_at:]

# ---- 4. §10 会话日志追加一行 ----
lines = text.split("\n")
last_idx = max(i for i, l in enumerate(lines) if l.strip())
log_eol = "\r" if lines[last_idx].endswith("\r") else ""
log = (
    "- 2026-09-03 ｜ Claude(P3-2 非实现独立验收会话 / 本会话此前只立 P3-7 卡与冻结 P3-2 派工书) "
    "｜ P3-2(独立验收 PASS,置完成待收口) / §1 阶段总表(P3 进度 2/7→3/7) ｜ "
    "不复用实现方任何解码脚本,按冻结契约条文自写四个 fail-closed 核验器共 116 项断言零失败: "
    "真机段独立重算坐实 raw 身份域与 fw_header 双零域互异且 INFO.image_sha256 全 32B 落在 raw 域; "
    "另补第三条腿把摘要绑到本仓库源码 —— 全量 clean 重建的 App bin 经 etu_pack finalize 回填后与"
    "包内板上 dump 三方逐字节同值,finalize 差异全部落在 0x400..0x45F; 三处红线单点注错各把 host "
    "harness 打红且均非编译错误、还原后复绿,证明 harness 有鉴别力; 独立复现双产物字节可复现性,"
    "其中 Boot 本轮真实重链后仍逐字节相同(强于实现方 up-to-date 申报)。冻结 P3-2-v1 合同+三类 "
    "manifest+证据矩阵,validate_bundle.py 通过。两项不阻断发现: CMakeLists.txt 行尾整体归一使"
    "工作区字节在 autocrlf 下不可复现(已按 P3-6 先例补 .gitattributes 护栏 9 条,不自行改回 CRLF "
    "以免验收方兼任实现方); 本会话自己冻结的 P3-2 派工书漏写 MDK-ARM_F435/** 允许范围,裁定构建"
    "注册为「范围内必要」不计实现方越界。未 commit/push/merge: 工作树上 P3-2 卡内改动、P3-7 立卡"
    "批次与本轮验收产出三批混在同一特性分支,收口须拆成互不夹带的独立提交,由主会话在用户确认后执行"
    + log_eol
)
lines.insert(last_idx + 1, log)
text = "\n".join(lines)

assert text != orig, "看板未发生变化"

# 哈希护栏：≥8 位十六进制且至少含一个字母（纯数字是日期/轮次号，不是哈希）
HASHLIKE = re.compile(r"\b(?=[0-9a-f]*[a-f])[0-9a-f]{8,}\b")
for name, chunk in (("追加内容", added), ("会话日志行", log), ("状态行", new_status)):
    hit = HASHLIKE.search(chunk)
    assert hit is None, f"{name}出现疑似哈希: {hit.group(0) if hit else ''}"

BOARD.write_bytes(text.encode("utf-8"))
print("BOARD_WRITEBACK_OK")
print(f"bytes {len(raw)} -> {len(text.encode('utf-8'))}")
print(f"lines {orig.count(chr(10))} -> {text.count(chr(10))}")
